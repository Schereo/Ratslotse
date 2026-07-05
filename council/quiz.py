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


# --- Prompt + Generierung ----------------------------------------------------

_SYSTEM = (
    "Du erstellst ein allgemeinverständliches Quiz über Oldenburg für interessierte "
    "Bürger:innen. Fragen sollen Spaß machen und Wissen über die Stadt vermitteln — "
    "NICHT technisch-bürokratisch (keine Fragen nach Aktenzeichen, Bebauungsplan-Nummern, "
    "Paragraphen oder Sitzungs-Formalien)."
)


def _user_prompt(area_label: str, sources: str, n: int) -> str:
    cats = ", ".join(CATEGORIES)
    return f"""Erstelle {n} Multiple-Choice-Quizfragen über „{area_label}" (Oldenburg).

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
  · schaetzen = eine Schätzfrage mit 4 Zahl-Bereichen (Einwohner, Fläche, €-Betrag)
- Wenn eine Kategorie aus den Quellen nicht seriös bedienbar ist, lass sie weg.
- Sprache: Deutsch. difficulty ∈ leicht|mittel|schwer.

Antworte mit NUR JSON:
{{"questions": [
  {{"category": "geschichte", "difficulty": "leicht",
    "question": "…?", "options": ["A","B","C","D"], "correct_index": 0,
    "explanation": "1 kurzer Satz, warum richtig",
    "source": "geschichte|orte … kurze Herkunft, z. B. 'Wikipedia' oder 'Ratsbeschluss 2025'"}}
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


def _valid(q: dict) -> bool:
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


def verify_question(sources: str, q: dict) -> bool:
    """Günstiger Zweit-Check: ist die richtige Antwort eindeutig aus den Quellen
    belegt und die anderen klar falsch? Bei Zweifel/Fehler → verwerfen."""
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
                      verify: bool = True) -> list[dict]:
    """Fragen für ein Gebiet generieren, validieren, (optional) verifizieren.
    Gibt speicherfertige Dict-Zeilen zurück (mit content_hash)."""
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
        rows.append({
            "area_type": area_type, "area_key": area_key,
            "category": q["category"],
            "difficulty": q.get("difficulty") if q.get("difficulty") in DIFFICULTIES else "mittel",
            "question": q["question"].strip(),
            "options": [o.strip() for o in q["options"]],
            "correct_index": q["correct_index"],
            "explanation": (q.get("explanation") or "").strip()[:300] or None,
            "source_type": source_type, "source_ref": source_ref,
            "content_hash": h,
        })
    return rows
