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


def _clip(text: str, n: int) -> str:
    """Quelltext auf ~n Zeichen kappen — aber an einer SATZ-/Zeilengrenze.
    Ein mitten in der Zahl abgeschnittener Satz („…mit rund 1") hat das LLM
    nachweislich zum Erfinden der fehlenden Ziffern verleitet (Review-Finding)."""
    if len(text) <= n:
        return text
    cut = text[:n]
    for sep in ("\n", ". "):
        pos = cut.rfind(sep)
        if pos > n * 0.6:  # nicht zu viel wegwerfen, falls Sätze sehr lang sind
            return cut[:pos + 1].rstrip()
    return cut


def fetch_wikipedia(name: str) -> tuple[str, str] | None:
    """Plaintext-Extrakt des deutschen Wikipedia-Artikels zum Oldenburger
    Stadtteil → (text, url). Direkte Titel zuerst, dann Volltextsuche; nur
    Oldenburg-relevante Artikel (viele kleine Stadtteile haben gar keinen →
    None, dann tragen Ratsdaten)."""
    for title in (_WIKI_OVERRIDE.get(name, name), f"{name} (Oldenburg)", f"{name} (Oldb)"):
        got = _wiki_extract(title)
        if got and _relevant(got[0], name):
            return _clip(got[0], 8000), got[1]
    for title in _wiki_search(f"{name} Oldenburg Stadtteil"):
        # Der Artikel muss nach dem Stadtteil BENANNT sein — sonst grabscht die
        # Suche einen Artikel, der den Namen nur beiläufig erwähnt (z. B.
        # „Oldenburger Hundehütte" für „Innenstadt").
        if name.lower() not in title.lower():
            continue
        got = _wiki_extract(title)
        if got and _relevant(got[0], name):
            return _clip(got[0], 8000), got[1]
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
        return (_clip(text, 4000), url) if len(text) > 400 else None
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
        # Wichtigste Beschlüsse zuerst (council.importance) — so drehen sich die
        # „ratspolitik"-Fragen um bedeutsame statt beliebige Beschlüsse.
        decs = sorted(det.get("decisions") or [],
                      key=lambda d: (d.get("importance") or 0), reverse=True)
        for d in decs[:6]:
            bits = [d.get("session_date", "")[:10], d.get("title", "").strip()]
            if d.get("outcome"):
                bits.append(f"[{d['outcome']}]")
            if d.get("amount_eur"):
                bits.append(f"{int(d['amount_eur']):,} €".replace(",", "."))
            lines.append("- " + " ".join(b for b in bits if b))
    return _clip("\n".join(lines), 4000)


# --- Anreicherung: Locator-Karte + Wikimedia-Commons-Bild --------------------

_NOMINATIM = "https://nominatim.openstreetmap.org/search"
_OVERPASS = "https://overpass-api.de/api/interpreter"
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


def street_line(name: str, max_km: float = 2.0) -> list | None:
    """Geometrie einer benannten Straße in Oldenburg als Liste von Linienzügen
    (GeoJSON-Reihenfolge [[[lon,lat], …], …]) — aber NUR, wenn die Straße
    **kompakt** ist (Gesamt-Ausdehnung < max_km). Mehrfach vergebene bzw. weit
    verstreute Namen (z. B. mehrere „Mittelwege") werden so verworfen, damit nie
    eine falsche Stelle markiert wird. Best-effort über Overpass."""
    name = (name or "").strip()
    if len(name) < 3 or '"' in name or "\\" in name:
        return None
    lo1, la1, lo2, la2 = _OL_BBOX
    query = (f'[out:json][timeout:20];way["highway"]["name"="{name}"]'
             f'({la1},{lo1},{la2},{lo2});out geom;')
    try:
        r = requests.get(_OVERPASS, headers=_UA, timeout=25, params={"data": query})
        if r.status_code != 200:
            return None
        ways = [e for e in r.json().get("elements", [])
                if e.get("type") == "way" and e.get("geometry")]
        if not ways:
            return None
        pts = [(p["lat"], p["lon"]) for w in ways for p in w["geometry"]]
        la = [p[0] for p in pts]
        lo = [p[1] for p in pts]
        extent = max((max(la) - min(la)) * 111, (max(lo) - min(lo)) * 67)
        if extent > max_km:                       # verstreut/mehrdeutig → keine Karte
            return None
        return [[[p["lon"], p["lat"]] for p in w["geometry"]] for w in ways]
    except (requests.RequestException, ValueError, KeyError):
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


def wikipedia_page_url(subject: str) -> str | None:
    """Kanonische URL des deutschen Wikipedia-Artikels zum Subjekt (Person, Ort,
    Bauwerk) — für einen **präzisen** „Quelle"-Link auf genau dieses Ding statt
    auf die Gebiets-Seite (z. B. „Hermann Lehmkuhl" statt „Bloherfelde"). None
    bei Begriffsklärung oder fehlendem Artikel."""
    subject = (subject or "").strip()
    if len(subject) < 3:
        return None
    try:
        s = requests.get(_WIKI_SUMMARY + subject.replace(" ", "_"), headers=_UA, timeout=20)
        if s.status_code != 200:
            return None
        summary = s.json()
        if summary.get("type") == "disambiguation":
            return None
        return ((summary.get("content_urls") or {}).get("desktop") or {}).get("page") or None
    except (requests.RequestException, ValueError, KeyError):
        return None


def enrich_row(row: dict, subject: str, *, area_type: str | None = None,
               area_key: str | None = None) -> None:
    """Row best-effort mit Bild, Karte und präzisem Quelle-Link anreichern
    (verändert `row` in place). `subject` = zentrales reales Ding der Frage.

    Die Kartenlogik ist bewusst zurückhaltend, damit NIE eine falsche Stelle
    gezeigt wird — in absteigender Genauigkeit:
    - kompakte, eindeutige Straße → **Linie** (Overpass, Ausdehnungs-Guard);
    - bekannter Einzelort (hat einen Wikipedia-Artikel/Foto) → **Punkt**;
    - sonst, falls die Frage einem Stadtteil zuzuordnen ist, das ganze
      **Gebiet** als Polygon (wir besitzen die Polygone → immer verlässlich).
    Reine, mehrdeutige Straßennamen ohne kompakte Geometrie bekommen KEINEN
    Pin (mehrere „Mittelwege" würden sonst am falschen Ort landen). Und meint
    das Subjekt nur „Oldenburg" als Ganzes (Bewegungen, stadtweite Themen),
    gibt es keinen Pin — ein Marker mitten in der Innenstadt trägt nichts."""
    subject = (subject or "").strip()
    if geo.is_city_generic(subject):
        subject = ""  # ganze Stadt → kein Foto-/Karten-Subjekt (Gebiets-Fallback bleibt)
    if not subject and area_type != "stadtteil":
        return
    img = commons_image(subject) if subject else None
    if img:
        row.update({"image_url": img["url"], "image_author": img["author"],
                    "image_license": img["license"], "image_license_url": img["license_url"],
                    "image_source_url": img["source_url"]})
    line = street_line(subject) if subject else None
    if line:
        pts = [pt for seg in line for pt in seg]  # [lon, lat]
        row["lat"] = sum(p[1] for p in pts) / len(pts)
        row["lon"] = sum(p[0] for p in pts) / len(pts)
        row["place_label"] = subject
        row["geojson"] = json.dumps({"type": "MultiLineString", "coordinates": line}, ensure_ascii=False)
    elif img:                                     # bekannter Einzelort → Punkt vertretbar
        coords = geocode_place(subject)
        if coords:
            row["lat"], row["lon"], row["place_label"] = coords[0], coords[1], subject
    if row.get("lat") is None:
        # Noch kein Punkt/keine Linie → das ganze GEBIET einzeichnen: den
        # Stadtteil des Subjekts, sonst den Stadtteil der Frage selbst.
        poly_name = subject if geo.is_stadtteil(subject) else (
            area_key if area_type == "stadtteil" else None)
        poly = geo.stadtteil_polygon(poly_name) if poly_name else None
        center = geo.stadtteil_center(poly_name) if poly else None
        if poly and center:
            row["lat"], row["lon"] = center
            row["place_label"] = poly_name
            row["geojson"] = json.dumps(poly, ensure_ascii=False)
    # „Quelle"-Link präzisieren: bei Wikipedia-Fragen auf den Artikel des
    # konkreten Subjekts verlinken (die Frage stammt aus dem Gebiets-Artikel,
    # aber die Person/Sache hat eine eigene, hilfreichere Seite).
    if subject and row.get("source_type") == "wikipedia":
        page = wikipedia_page_url(subject)
        if page:
            row["source_ref"] = page


# --- Prompt + Generierung ----------------------------------------------------

_SYSTEM = (
    "Du erstellst ein allgemeinverständliches Quiz über Oldenburg für interessierte "
    "Bürger:innen. Fragen sollen Spaß machen, FAIR sein und etwas über die Stadt "
    "beibringen — NICHT technisch-bürokratisch (keine Aktenzeichen, Bebauungsplan-"
    "Nummern, Paragraphen oder Sitzungs-Formalien) und NICHT bloßes Detail-Trivia zu "
    "obskuren Randfiguren oder Jahreszahlen, die niemand kennt. Eine Frage ist gut, "
    "wenn ihre Auflösung einen Aha-Moment auslöst: Die Erklärung soll etwas "
    "Einprägsames, Überraschendes oder Verständnis-Stiftendes vermitteln — nicht nur "
    "die richtige Antwort wiederholen. Lieber bekannte, bedeutsame Dinge als beliebige "
    "Fakten. Zwei harte Regeln: (1) RELEVANZ — keine belanglosen Verfahrens-Zahlen "
    "(wie viele Menschen zu einem Workshop kamen, wie viele Ideen oder Stellungnahmen "
    "eingingen, exakte Sitzungs- oder Beschlussdaten); daraus lernt niemand etwas über "
    "die Stadt. (2) EINDEUTIGKEIT — jede Frage steht FÜR SICH und benennt das gemeinte "
    "Ding konkret (Stadtteil, Projekt, Ort ausschreiben), nie vage von dem Stadtteil "
    "oder dem neuen Quartier sprechen."
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
- Allgemeinverständlich und FAIR: Die Mehrheit der Fragen leicht bis mittel,
  nur wenige schwer. Keine Aktenzeichen/Paragraphen, keine obskuren Randfiguren
  oder beliebigen Jahreszahlen — bevorzuge Bekanntes und Bedeutsames.
- "explanation" = 1 einprägsamer Satz mit dem WARUM/Aha-Effekt. Sie darf die
  richtige Antwort weder wörtlich noch sinngemäß bloß wiederholen, sondern
  liefert mindestens EINE zusätzliche, quellengedeckte Information: ein Warum,
  eine Folge, einen Heute-Bezug oder einen Vergleichsanker (bei Zahlen immer!).
  Selbsttest: Streiche die Antwort aus der explanation — bleibt nichts Neues,
  schreib sie neu. Formuliere über die STADT, nie über die Quelle (kein „laut
  Quelle", kein „der Artikel sagt" — die Quelle wird separat verlinkt). Gibt
  die Quelle keinen Zusatzfakt her, lass die Frage weg.
- SPRACHE & OPTIONEN: Frage und Optionen sind korrektes, natürliches Deutsch
  (Bezüge/Numerus prüfen). Alle vier Optionen haben ähnliche Länge, gleichen
  Stil und gleiche Granularität (keine tagesgenauen neben jahresgenauen
  Angaben); die richtige darf nicht die längste oder präziseste sein. Keine
  absurden oder witzigen Distraktoren — jede falsche Option muss eine Antwort
  sein, die eine informierte Bürgerin ernsthaft erwägen könnte.
- DATEN & UNSICHERES: Die richtige Antwort ist NIE ein exaktes Tagesdatum;
  Jahreszahl-Antworten nur, wenn das Jahr selbst etwas erzählt (Gründung,
  Eingemeindung, Zerstörung) — und die falschen Jahre liegen deutlich
  auseinander. Kein „könnte" in Fragen: Bei mehrdeutiger Quellenlage nach der
  überlieferten/dokumentierten Deutung fragen. Benennungen (Straßen, Schulen,
  Plätze) nur behaupten, wenn die Quelle sie ausdrücklich nennt; Personen, die
  die Quelle als NS-belastet oder völkisch ausweist, nie als neutrale oder
  positive Quiz-Antwort verwenden.
- Verteile über die Kategorien: {cats}.
  · geschichte = Gründung/Eingemeindung/Namensherkunft/historische Ereignisse
  · orte = Wahrzeichen, Bauwerke, Parks, Plätze, Straßen
  · menschen = bekannte Personen, Ratsmitglieder
  · ratspolitik = aktuelle Beschlüsse/Projekte des Stadtrats (nur aus Ratsdaten) —
    WAS wurde beschlossen und warum ist es bedeutsam, nicht das genaue Datum eines
    Verfahrensschritts. Das Projekt/den Ort konkret benennen.
  · schaetzen = eine SCHÄTZFRAGE als Slider: setze "qtype":"estimate" mit
    "answer_value" (die richtige Zahl), "unit" (z. B. Einwohner, Hektar, Euro,
    Jahr) und "range_min"/"range_max" (plausible Slider-Grenzen, der Wert liegt
    klar dazwischen — aber NICHT in der Mitte der Spanne: wähle die Grenzen
    asymmetrisch, sonst ist der unbewegte Slider schon die Lösung) — STATT
    options/correct_index. NUR sinnvolle, einprägsame
    Größen (Einwohnerzahl, Fläche, Gründungsjahr, Bausumme großer Projekte,
    Entfernung) — NIEMALS belanglose Zählungen (Workshop-Teilnehmer, eingereichte
    Ideen/Stellungnahmen, Zahl der Sitzungen).
- ZUSATZINFOS je Frage (optional, nur wenn aus den Quellen sinnvoll):
  · "hint" = ein kurzer Tipp (1 Satz), der beim Nachdenken hilft, OHNE die
    Antwort zu verraten — besonders bei schwereren Fragen.
  · "detail" = 2–3 Sätze ausführlichere Erklärung (nur aus den Quellen).
  · "subject" = das zentrale REALE Ding der Frage (Gebäude, Wahrzeichen, Ort,
    Straße oder Person), exakt wie der deutsche Wikipedia-Artikel heißt (z. B.
    "Schloss Oldenburg", "Cäcilienbrücke") — nur für Foto & Karte. Weglassen,
    wenn es kein konkretes reales Ding gibt — insbesondere NICHT bei Bewegungen,
    Organisationen, Vereinen oder wenn nur die ganze Stadt gemeint ist (ein
    Karten-Pin auf ganz Oldenburg hilft niemandem).
  · "topic" = bei Rats-/Projekt-Fragen ein kurzes Such-Stichwort, mit dem man
    verwandte Beschlüsse findet (z. B. "Lebensquartier", "Fliegerhorst",
    "Cäcilienbrücke"). Damit verlinken wir „Beschlüsse dazu". Nur setzen, wenn es
    ein echtes Ratsthema ist (v. a. Kategorie ratspolitik).
- Wenn eine Kategorie aus den Quellen nicht seriös bedienbar ist, lass sie weg.
- Sprache: Deutsch. difficulty ∈ leicht|mittel|schwer.

Antworte mit NUR JSON (Multiple Choice ODER, für schaetzen, qtype=estimate):
{{"questions": [
  {{"category": "geschichte", "difficulty": "leicht",
    "question": "…?", "options": ["A","B","C","D"], "correct_index": 0,
    "explanation": "1 einprägsamer Satz mit dem Aha-Effekt (nicht die Antwort wiederholen)",
    "hint": "kurzer Tipp, ohne die Lösung zu verraten",
    "detail": "2–3 Sätze mehr Kontext aus den Quellen",
    "subject": "Schloss Oldenburg", "topic": "Schloss Oldenburg",
    "source": "kurze Herkunft, z. B. 'Wikipedia' oder 'Ratsbeschluss 2025'"}},
  {{"category": "schaetzen", "difficulty": "mittel", "qtype": "estimate",
    "question": "Wie viele Einwohner hat der Beispiel-Stadtteil etwa?",
    "answer_value": 12000, "unit": "Einwohner", "range_min": 2000, "range_max": 30000,
    "explanation": "Damit ist der Stadtteil für sich so groß wie eine Kleinstadt — bis zur Eingemeindung war er eine eigene Gemeinde.",
    "source": "Wikipedia"}}
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
        # Mittelpunkts-Guard: Antwort im mittleren Fünftel = der unbewegte
        # Slider gewinnt (Review-Finding) → Frage verwerfen.
        and abs((v - lo) / (hi - lo) - 0.5) > 0.10
        and isinstance(q.get("unit"), str) and bool(q["unit"].strip())
    )


def _valid(q: dict) -> bool:
    # Schätzfragen MÜSSEN Slider sein — als MC mit vier Zahlen-Optionen sind sie
    # weder fair noch lehrreich (Review-Finding: 3 von 5 kamen als MC).
    if q.get("category") == "schaetzen" and q.get("qtype") != "estimate":
        return False
    return _valid_estimate(q) if q.get("qtype") == "estimate" else _valid_mc(q)


def _extra_texts(q: dict) -> str:
    """Erklärung/Detail/Tipp einer Frage als Block für den Verify-Pass —
    Halluzinationen leben erfahrungsgemäß in den ZUSATZTEXTEN, nicht in der
    Antwort selbst (Review-Findings: erfundener „Reichstag", falsche Zahlen)."""
    bits = [q.get("explanation"), q.get("detail"), q.get("hint")]
    return "\n".join(b for b in bits if b)


def verify_question(sources: str, q: dict) -> bool:
    """Günstiger Zweit-Check: ist die richtige Antwort eindeutig aus den Quellen
    belegt (bei MC auch: andere klar falsch), beantwortet sie die Frage logisch
    sinnvoll, und enthalten Erklärung/Detail/Tipp nichts Unbelegtes? Sieht
    denselben (vollen) Quellstring wie die Generierung — ein kürzeres Fenster
    hat korrekte Ratsdaten-Fragen systematisch verworfen (fail-closed). Bei
    Zweifel/Fehler → verwerfen."""
    extra = _extra_texts(q)
    extra_block = (f"\nErklärungstexte der Frage:\n{extra}\n" if extra else "")
    checks = (
        "Antworte nur mit JA, wenn ALLES zutrifft, sonst NEIN:\n"
        "1. Der Wert/die Antwort ist EINDEUTIG aus dem Quelltext belegt.\n"
        "2. Die Antwort beantwortet die gestellte Frage logisch sinnvoll "
        "(keine Zirkelfrage, kein falscher Bezug).\n"
        "3. Keine Aussage der Erklärungstexte widerspricht dem Quelltext oder "
        "behauptet Fakten, die dort nicht stehen."
    )
    if q.get("qtype") == "estimate":
        prompt = (
            f"Quelltext:\n{sources}\n\n"
            f"Schätzfrage: {q['question']}\n"
            f"Behaupteter richtiger Wert: {q['answer_value']} {q.get('unit', '')}\n"
            f"{extra_block}\n{checks}"
        )
    else:
        correct = q["options"][q["correct_index"]]
        others = ", ".join(o for i, o in enumerate(q["options"]) if i != q["correct_index"])
        prompt = (
            f"Quelltext:\n{sources}\n\n"
            f"Frage: {q['question']}\n"
            f"Als richtig markierte Antwort: {correct}\n"
            f"Andere Antworten: {others}\n"
            f"{extra_block}\n{checks}\n"
            "Zusätzlich müssen die anderen Antworten klar falsch sein."
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
            "hint": (q.get("hint") or "").strip()[:200] or None,
            "topic": (q.get("topic") or "").strip()[:80] or None,
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
        # Foto (Commons) + Locator-Karte + präziser Quelle-Link — best-effort, Netz.
        if enrich:
            enrich_row(row, q.get("subject") or "", area_type=area_type, area_key=area_key)
        rows.append(row)
    return rows
