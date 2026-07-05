"""Quizfragen generieren — Multiple-Choice über Oldenburgs Stadtteile & Themen.

Gegroundet in mehreren Quellen (nie frei erfunden):
- **Wikipedia** (deutscher Artikel je Stadtteil): Geschichte, Wahrzeichen,
  Personen, Einwohnerzahlen — der allgemeinverständliche Grundstoff.
- **oldenburg.de** (best-effort Volltext der Stadtteil-/Themenseite).
- **Eigene Ratsdaten**: verortete Entitäten + ihre Beschlüsse (Ergebnisse,
  €-Beträge) für die Kategorie „aktuelle Ratspolitik" und Schätzfragen.

Ein zweiter, günstiger **Verify-Pass** prüft je Frage, ob die als richtig
markierte Antwort eindeutig aus dem Quelltext belegt ist; nur bestandene
Fragen werden zurückgegeben. Der Aufbau folgt den bestehenden Pipelines
(`council/topics.py`, `council/recaps.py`): Netz/LLM in Worker-Threads,
DB-Schreiben im Main-Thread (im Backfill-Skript).
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re

import requests
from bs4 import BeautifulSoup

from nwz import llm
from council import geo

MODEL = os.environ.get("COUNCIL_QUIZ_MODEL", "deepseek/deepseek-v4-pro")
VERIFY_MODEL = os.environ.get("COUNCIL_QUIZ_VERIFY_MODEL", "openai/gpt-4o-mini")

CATEGORIES = ["geschichte", "orte", "menschen", "ratspolitik", "schaetzen"]
DIFFICULTIES = ("leicht", "mittel", "schwer")

_UA = {"User-Agent": "Ratslotse-Quiz/1.0 (ratslotse.de; Kommunalpolitik-Quiz)"}
_WIKI_API = "https://de.wikipedia.org/w/api.php"
# Stadtteile, deren Oldenburg-Artikel nicht direkt unter dem Namen liegt.
_WIKI_OVERRIDE = {
    "Fliegerhorst": "Fliegerhorst Oldenburg",
    "Nordmoslesfehn": "Moslesfehn",
    "Drielaker-Moor": "Drielake",
}


# --- Quellen -----------------------------------------------------------------

def _wiki_extract(title: str) -> tuple[str, str] | None:
    try:
        r = requests.get(_WIKI_API, headers=_UA, timeout=20, params={
            "action": "query", "format": "json", "prop": "extracts",
            "explaintext": 1, "redirects": 1, "titles": title,
        })
        r.raise_for_status()
        for pid, page in r.json().get("query", {}).get("pages", {}).items():
            if pid != "-1" and page.get("extract"):
                text = re.sub(r"\n{3,}", "\n\n", page["extract"]).strip()
                url = "https://de.wikipedia.org/wiki/" + page["title"].replace(" ", "_")
                return text, url
    except (requests.RequestException, ValueError):
        pass
    return None


def _wiki_search(query: str) -> list[str]:
    try:
        r = requests.get(_WIKI_API, headers=_UA, timeout=20, params={
            "action": "query", "format": "json", "list": "search",
            "srsearch": query, "srlimit": 5})
        r.raise_for_status()
        return [h["title"] for h in r.json().get("query", {}).get("search", [])]
    except (requests.RequestException, ValueError):
        return []


def _relevant(text: str, name: str) -> bool:
    """Der Artikel muss wirklich um den Oldenburger Stadtteil gehen — schützt
    vor generischen Treffern (allgemeiner „Fliegerhorst", falscher „Ziegelhof")."""
    low = text.lower()
    return len(text) > 1000 and "oldenburg" in low and name.lower() in low


def fetch_wikipedia(name: str) -> tuple[str, str] | None:
    """Plaintext-Extrakt des deutschen Wikipedia-Artikels zum Oldenburger
    Stadtteil → (text, url). Direkte Titel zuerst, dann Volltextsuche; nur
    Oldenburg-relevante Artikel (viele kleine Stadtteile haben gar keinen →
    None, dann tragen Ratsdaten)."""
    for title in (_WIKI_OVERRIDE.get(name, name), f"{name} (Oldenburg)", f"{name} (Oldb)"):
        got = _wiki_extract(title)
        if got and _relevant(got[0], name):
            return got[0][:8000], got[1]
    for title in _wiki_search(f"{name} Oldenburg Stadtteil"):
        # Der Artikel muss nach dem Stadtteil BENANNT sein — sonst grabscht die
        # Suche einen Artikel, der den Namen nur beiläufig erwähnt (z. B.
        # „Oldenburger Hundehütte" für „Innenstadt").
        if name.lower() not in title.lower():
            continue
        got = _wiki_extract(title)
        if got and _relevant(got[0], name):
            return got[0][:8000], got[1]
    return None


def fetch_stadt_text(name: str) -> tuple[str, str] | None:
    """Best-effort Volltext einer oldenburg.de-Seite zum Stadtteil über die
    Website-Suche (`/metanavigation/suche.html?q=`). None bei Misserfolg —
    Wikipedia + Ratsdaten tragen dann. Die Stadt-Seiten sind meist Service-
    Inhalte, also nur ergänzend."""
    try:
        r = requests.get("https://www.oldenburg.de/metanavigation/suche.html",
                         headers=_UA, timeout=15, params={"q": name})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        href = None
        for a in soup.find_all("a", href=True):
            h = a["href"]
            if h.startswith("/startseite/") and h.endswith(".html") and name.lower() in a.get_text().lower():
                href = h
                break
        if not href:
            return None
        url = "https://www.oldenburg.de" + href
        page = requests.get(url, headers=_UA, timeout=15)
        page.raise_for_status()
        psoup = BeautifulSoup(page.text, "html.parser")
        for tag in psoup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        main = psoup.select_one("main, #content, .content") or psoup.body
        text = re.sub(r"\s{2,}", " ", main.get_text(" ", strip=True)) if main else ""
        return (text[:4000], url) if len(text) > 400 else None
    except (requests.RequestException, ValueError):
        return None


def council_facts(store, *, stadtteil: str | None = None, slug: str | None = None) -> str:
    """Ratsdaten-Kontext als Text: für einen Stadtteil die dort verorteten
    Entitäten + jüngste Beschlüsse, für ein Thema (slug) die Entität selbst.
    Leerer String, wenn nichts vorliegt."""
    lines: list[str] = []
    slugs: list[str] = []
    if slug:
        slugs = [slug]
    elif stadtteil:
        for e in store.list_entities_geo():
            if geo.stadtteil_for(e["lat"], e["lon"]) == stadtteil:
                slugs.append(e["slug"])
    for s in slugs[:8]:
        det = store.entity_detail(s)
        if not det:
            continue
        ent = det.get("entity") or {}
        if det.get("description"):
            lines.append(f"{ent.get('name', s)}: {det['description']}")
        for d in (det.get("decisions") or [])[:6]:
            bits = [d.get("session_date", "")[:10], d.get("title", "").strip()]
            if d.get("outcome"):
                bits.append(f"[{d['outcome']}]")
            if d.get("amount_eur"):
                bits.append(f"{int(d['amount_eur']):,} €".replace(",", "."))
            lines.append("- " + " ".join(b for b in bits if b))
    return "\n".join(lines)[:4000]


# --- Anreicherung: Locator-Karte + Wikimedia-Commons-Bild --------------------

_NOMINATIM = "https://nominatim.openstreetmap.org/search"
_WIKI_SUMMARY = "https://de.wikipedia.org/api/rest_v1/page/summary/"
_COMMONS_API = "https://commons.wikimedia.org/w/api.php"
# Oldenburg grob (verwirft Nominatim-Treffer außerhalb der Stadt): lon/lat.
_OL_BBOX = (8.13, 53.10, 8.31, 53.23)
# Freie Lizenzen, die wir MIT Nennung nutzen dürfen (Präfix, case-insensitiv).
_FREE_LICENSES = ("cc0", "cc-zero", "public domain", "cc by", "cc-by", "pdm")


def _strip_html(s: str | None) -> str:
    return re.sub(r"\s+", " ", BeautifulSoup(s or "", "html.parser").get_text()).strip()


def geocode_place(place: str) -> tuple[float, float] | None:
    """Koordinaten eines Orts/einer Straße in Oldenburg (Nominatim, best-effort).
    Treffer außerhalb Oldenburgs werden verworfen (kein spuriöser Marker)."""
    place = (place or "").strip()
    if len(place) < 3:
        return None
    try:
        r = requests.get(_NOMINATIM, headers=_UA, timeout=20, params={
            "q": f"{place}, Oldenburg (Oldenburg), Deutschland", "format": "json",
            "limit": 1, "viewbox": "8.13,53.23,8.31,53.10", "bounded": 1,
        })
        r.raise_for_status()
        hits = r.json()
        if not hits:
            return None
        lat, lon = float(hits[0]["lat"]), float(hits[0]["lon"])
        lo1, la1, lo2, la2 = _OL_BBOX
        if la1 <= lat <= la2 and lo1 <= lon <= lo2:
            return lat, lon
    except (requests.RequestException, ValueError, KeyError, IndexError):
        pass
    return None


def _license_ok(short: str | None) -> bool:
    s = (short or "").strip().lower()
    return bool(s) and any(s.startswith(p) for p in _FREE_LICENSES)


def commons_image(subject: str) -> dict | None:
    """Frei lizenziertes Foto zum Thema von Wikimedia Commons — via Lead-Bild des
    deutschen Wikipedia-Artikels. Liefert URL + Bildnachweis (Autor, Lizenz,
    Quelle) oder None. NUR Commons-Bilder mit freier Lizenz (Fair-Use raus)."""
    subject = (subject or "").strip()
    if len(subject) < 3:
        return None
    try:
        s = requests.get(_WIKI_SUMMARY + subject.replace(" ", "_"), headers=_UA, timeout=20)
        if s.status_code != 200:
            return None
        summary = s.json()
        img = (summary.get("originalimage") or {}).get("source") or ""
        if "/wikipedia/commons/" not in img:  # lokale/Fair-Use-Bilder ausschließen
            return None
        fname = img.rsplit("/", 1)[-1]
        c = requests.get(_COMMONS_API, headers=_UA, timeout=20, params={
            "action": "query", "format": "json", "titles": f"File:{fname}",
            "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": 640,
        })
        c.raise_for_status()
        pages = c.json().get("query", {}).get("pages", {})
        info = next(iter(pages.values()), {}).get("imageinfo", [{}])[0]
        meta = info.get("extmetadata", {})
        def mv(k):  # noqa: E306
            return (meta.get(k) or {}).get("value")
        if not _license_ok(mv("LicenseShortName")):
            return None
        return {
            "url": info.get("thumburl") or img,
            "author": (_strip_html(mv("Artist")) or "unbekannt")[:120],
            "license": mv("LicenseShortName"),
            "license_url": mv("LicenseUrl"),
            "source_url": info.get("descriptionurl")
                or summary.get("content_urls", {}).get("desktop", {}).get("page"),
        }
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return None


def enrich_row(row: dict, subject: str) -> None:
    """Row mit Bild (Commons) und Koordinaten (Nominatim) zum Thema anreichern —
    best-effort, verändert `row` in place. `subject` = zentrales reales Ding."""
    subject = (subject or "").strip()
    if not subject:
        return
    img = commons_image(subject)
    if img:
        row.update({"image_url": img["url"], "image_author": img["author"],
                    "image_license": img["license"], "image_license_url": img["license_url"],
                    "image_source_url": img["source_url"]})
    coords = geocode_place(subject)
    if coords:
        row["lat"], row["lon"], row["place_label"] = coords[0], coords[1], subject


# --- Prompt + Generierung ----------------------------------------------------

_SYSTEM = (
    "Du erstellst ein allgemeinverständliches Quiz über Oldenburg für interessierte "
    "Bürger:innen. Fragen sollen Spaß machen und Wissen über die Stadt vermitteln — "
    "NICHT technisch-bürokratisch (keine Fragen nach Aktenzeichen, Bebauungsplan-Nummern, "
    "Paragraphen oder Sitzungs-Formalien)."
)


def _user_prompt(area_label: str, sources: str, n: int) -> str:
    cats = ", ".join(CATEGORIES)
    return f"""Erstelle {n} Quizfragen über „{area_label}" (Oldenburg). Die meisten sind Multiple Choice; Schätzfragen dürfen Slider-Fragen sein (siehe unten).

QUELLEN (nur hieraus Fakten nehmen — NICHTS erfinden):
{sources}

Regeln:
- Jede Frage hat GENAU 4 Antwortmöglichkeiten, davon genau eine richtig.
- Die richtige Antwort muss EINDEUTIG aus den Quellen belegbar sein; die drei
  falschen plausibel, aber klar falsch.
- Allgemeinverständlich, nicht technisch. Keine Aktenzeichen/Paragraphen.
- Verteile über die Kategorien: {cats}.
  · geschichte = Gründung/Eingemeindung/Namensherkunft/historische Ereignisse
  · orte = Wahrzeichen, Bauwerke, Parks, Plätze, Straßen
  · menschen = bekannte Personen, Ratsmitglieder
  · ratspolitik = aktuelle Beschlüsse/Projekte des Stadtrats (nur aus Ratsdaten)
  · schaetzen = eine SCHÄTZFRAGE als Slider: setze "qtype":"estimate" mit
    "answer_value" (die richtige Zahl), "unit" (z. B. Einwohner, Hektar, Euro,
    Jahr) und "range_min"/"range_max" (plausible Slider-Grenzen, der Wert liegt
    klar dazwischen) — STATT options/correct_index.
- ZUSATZINFOS je Frage (optional, nur wenn aus den Quellen sinnvoll):
  · "detail" = 2–3 Sätze ausführlichere Erklärung (nur aus den Quellen).
  · "subject" = das zentrale REALE Ding der Frage (Gebäude, Wahrzeichen, Ort,
    Straße oder Person), exakt wie der deutsche Wikipedia-Artikel heißt (z. B.
    "Schloss Oldenburg", "Cäcilienbrücke") — nur für Foto & Karte. Weglassen,
    wenn es kein konkretes reales Ding gibt.
- Wenn eine Kategorie aus den Quellen nicht seriös bedienbar ist, lass sie weg.
- Sprache: Deutsch. difficulty ∈ leicht|mittel|schwer.

Antworte mit NUR JSON (Multiple Choice ODER, für schaetzen, qtype=estimate):
{{"questions": [
  {{"category": "geschichte", "difficulty": "leicht",
    "question": "…?", "options": ["A","B","C","D"], "correct_index": 0,
    "explanation": "1 kurzer Satz, warum richtig",
    "detail": "2–3 Sätze mehr Kontext aus den Quellen",
    "subject": "Schloss Oldenburg",
    "source": "kurze Herkunft, z. B. 'Wikipedia' oder 'Ratsbeschluss 2025'"}},
  {{"category": "schaetzen", "difficulty": "mittel", "qtype": "estimate",
    "question": "Wie viele Einwohner hat der Stadtteil etwa?",
    "answer_value": 12000, "unit": "Einwohner", "range_min": 2000, "range_max": 30000,
    "explanation": "laut Quelle rund 12.000", "source": "Wikipedia"}}
]}}"""


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _content_hash(area_type: str, area_key: str, question: str) -> str:
    return hashlib.sha256(f"{area_type}|{area_key}|{_norm(question)}".encode()).hexdigest()[:32]


def _parse(content: str) -> list[dict]:
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        content = content[content.find("{"):]
    data = json.loads(content)
    return data.get("questions", []) if isinstance(data, dict) else []


def _valid_mc(q: dict) -> bool:
    opts = q.get("options")
    ci = q.get("correct_index")
    return (
        isinstance(q.get("question"), str) and len(q["question"]) > 8
        and isinstance(opts, list) and len(opts) == 4
        and all(isinstance(o, str) and o.strip() for o in opts)
        and len(set(_norm(o) for o in opts)) == 4
        and isinstance(ci, int) and 0 <= ci < 4
        and q.get("category") in CATEGORIES
    )


def _valid_estimate(q: dict) -> bool:
    """Schätzfrage-Slider: numerischer Wert klar innerhalb der Slider-Grenzen,
    Einheit gesetzt."""
    v, lo, hi = q.get("answer_value"), q.get("range_min"), q.get("range_max")
    return (
        isinstance(q.get("question"), str) and len(q["question"]) > 8
        and q.get("category") in CATEGORIES
        and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (v, lo, hi))
        and lo < v < hi
        and isinstance(q.get("unit"), str) and bool(q["unit"].strip())
    )


def _valid(q: dict) -> bool:
    return _valid_estimate(q) if q.get("qtype") == "estimate" else _valid_mc(q)


def verify_question(sources: str, q: dict) -> bool:
    """Günstiger Zweit-Check: ist die richtige Antwort eindeutig aus den Quellen
    belegt (bei MC auch: andere klar falsch)? Bei Zweifel/Fehler → verwerfen."""
    if q.get("qtype") == "estimate":
        prompt = (
            f"Quelltext:\n{sources[:6000]}\n\n"
            f"Schätzfrage: {q['question']}\n"
            f"Behaupteter richtiger Wert: {q['answer_value']} {q.get('unit', '')}\n\n"
            "Ist dieser Zahlenwert EINDEUTIG aus dem Quelltext belegt (exakt oder sehr nah)? "
            "Antworte nur mit JA oder NEIN."
        )
    else:
        correct = q["options"][q["correct_index"]]
        others = ", ".join(o for i, o in enumerate(q["options"]) if i != q["correct_index"])
        prompt = (
            f"Quelltext:\n{sources[:6000]}\n\n"
            f"Frage: {q['question']}\n"
            f"Als richtig markierte Antwort: {correct}\n"
            f"Andere Antworten: {others}\n\n"
            "Ist die richtige Antwort EINDEUTIG aus dem Quelltext belegt UND sind die anderen "
            "klar falsch? Antworte nur mit JA oder NEIN."
        )
    try:
        resp = llm.chat_complete(
            model=VERIFY_MODEL, _feature="quiz_verify", temperature=0, max_tokens=5,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip().upper().startswith("JA")
    except Exception:  # noqa: BLE001 — im Zweifel behalten wir die Frage nicht
        return False


def generate_for_area(area_type: str, area_key: str, area_label: str, sources: str,
                      *, n: int = 8, source_type: str, source_ref: str,
                      verify: bool = True, enrich: bool = True) -> list[dict]:
    """Fragen für ein Gebiet generieren, validieren, (optional) verifizieren und
    (optional) mit Bild/Karte anreichern. Gibt speicherfertige Dict-Zeilen
    zurück (mit content_hash)."""
    if len((sources or "").strip()) < 200:
        return []  # zu wenig Quellstoff für seriöse Fragen
    resp = llm.chat_complete(
        model=MODEL, _feature="quiz_generation", temperature=0.4, max_tokens=4000,
        response_format={"type": "json_object"},
        extra_body={"reasoning": {"enabled": False}},
        messages=[{"role": "system", "content": _SYSTEM},
                  {"role": "user", "content": _user_prompt(area_label, sources, n)}],
    )
    raw = _parse(resp.choices[0].message.content or "")
    rows: list[dict] = []
    seen: set[str] = set()
    for q in raw:
        if not _valid(q):
            continue
        h = _content_hash(area_type, area_key, q["question"])
        if h in seen:
            continue
        if verify and not verify_question(sources, q):
            continue
        seen.add(h)
        row = {
            "area_type": area_type, "area_key": area_key,
            "category": q["category"],
            "difficulty": q.get("difficulty") if q.get("difficulty") in DIFFICULTIES else "mittel",
            "question": q["question"].strip(),
            "explanation": (q.get("explanation") or "").strip()[:300] or None,
            "detail": (q.get("detail") or "").strip()[:600] or None,
            "source_type": source_type, "source_ref": source_ref,
            "content_hash": h,
        }
        if q.get("qtype") == "estimate":
            row.update({
                "qtype": "estimate", "options": [], "correct_index": 0,
                "answer_value": float(q["answer_value"]),
                "answer_unit": q["unit"].strip()[:40],
                "range_min": float(q["range_min"]), "range_max": float(q["range_max"]),
            })
        else:
            # Antworten mischen — das LLM legt die richtige Antwort sonst gern auf
            # Position A (gameable).
            opts = [o.strip() for o in q["options"]]
            correct_val = opts[q["correct_index"]]
            random.shuffle(opts)
            row.update({"qtype": "mc", "options": opts, "correct_index": opts.index(correct_val)})
        # Foto (Commons) + Locator-Karte zum realen Thema — best-effort, Netz.
        if enrich:
            enrich_row(row, q.get("subject") or "")
        rows.append(row)
    return rows
