#!/usr/bin/env python3
"""Listen und Abschnitte aus den Plan-Dokumenten — ohne Sprachmodell, von Hand gesetzt.

Manche Pläne legen ihre Orte selbst fest, in einer Tabelle oder einem Kapitel je Ort:

- **Lärmaktionsplan** (Anlage 280381 zu 24/0293/1): Kapitel 18 nennt neun Straßenabschnitte, für
  die er Tempo 30 vorschlägt — jeder Abschnitt endet mit „Vorschlag:“ und nennt seine Enden
  („zwischen Zeughausstraße und dem Knotenpunkt Prinzessinweg“). Dazu Tabelle 13, die Rangfolge
  der 30 Straßen mit den höchsten Lärmkennziffern.
- **Wärmeplan** (Anlage 306748 zu 26/0236): Tabelle 4, die elf Wärmenetzeignungsgebiete mit
  Ortsteil und Wärmebedarf.

Was wo steht, ist hier von Hand gesetzt (``SECTIONS``, ``WNG_AREAS``); das Skript liest die
Zitate und Tabellenzeilen aus den PDFs, schneidet die Straßen auf ihre Abschnitte zu und schreibt
``council/plan_lists/<plan>.json`` (eingecheckt). Die Seite liest nur diese Dateien.

Woher die Linien kommen: aus dem Ortskatalog der Ratsdaten (OpenStreetMap). Drei Enden fehlen
dort — Hausbäker Weg, Zeughausstraße und die A 28 an der Anschlussstelle Oldenburg-Kreyenbrück
(die Cloppenburger Straße kreuzt sie dort); sie sind einmal über Overpass geholt (``~/.cache/ratslotse/plan-quellen/osm/laerm-anker.json``).
Geometrie © OpenStreetMap-Mitwirkende, ODbL.

    python scripts/plan_listen.py            # Dateien schreiben (braucht PDFs und Katalog)
    python scripts/plan_listen.py --pruefen  # Dateien prüfen; mit PDFs auch: Zitat auf der Seite
"""
from __future__ import annotations

import argparse
import datetime as dt
import heapq
import json
import math
import re
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))
sys.path.insert(0, str(WURZEL / "scripts"))

from council import geo, places, plan_state, plans  # noqa: E402

CACHE = Path.home() / ".cache" / "ratslotse" / "plan-quellen"
OSM_ANCHORS = CACHE / "osm" / "laerm-anker.json"

DOCUMENTS = {
    "laermaktionsplan": {"document_id": 280381, "template": "24/0293/1",
                         "label": "Fortschreibung des Lärmaktionsplans (2. Entwurf, Mai 2024)"},
    "waermeplan": {"document_id": 306748, "template": "26/0236", "label": "Abschlussbericht Kommunale Wärmeplanung"},
}

#: Die Abschnitte des Lärmaktionsplans, für die er Tempo 30 vorschlägt — je Abschnitt: Kapitel,
#: Straße (Katalog), die beiden Enden des ERSTEN Schritts (Katalog-Slug oder ``osm:Name``; ``None``
#: = die ganze Straße), die Seite des Vorschlags, eine Wendung aus dem Satz, der den Abschnitt
#: nennt, und der Abschnitt in Kurzform. Kapitel 18.3.5 hat keinen Vorschlag und fehlt deshalb.
SECTIONS: list[dict] = [
    {"code": "18.2.1", "street": "nadorster-strasse", "start": "gertrudenfriedhof", "end": "hochheider-weg",
     "page": 64, "phrase": "im unteren Abschnitt der Nadorster Straße", "stretch": "Gertrudenfriedhof bis Hochheider Weg"},
    {"code": "18.2.2", "street": "hauptstrasse", "start": "wienstrasse", "end": "edewechter-landstrasse",
     "page": 68, "phrase": "durchgängige Tempo-30-Regelung an der Hauptstraße",
     "stretch": "Marktplatz Eversten bis Edewechter Landstraße / Eichenstraße"},
    {"code": "18.2.3", "street": "hundsmuehler-strasse", "start": "osm:Hausbäker Weg", "end": "hauptstrasse",
     "page": 75, "phrase": "zunächst im Abschnitt zwischen dem Hausbäker Weg", "stretch": "Hausbäker Weg bis Hauptstraße"},
    {"code": "18.2.4", "street": "cloppenburger-strasse", "start": "osm:A 28", "end": "bremer-strasse",
     "page": 81, "phrase": "zunächst eine Tempo-30-Regelung zwischen der BAB-Anschlussstelle",
     "stretch": "Anschlussstelle Oldenburg-Kreyenbrück bis Bremer Straße"},
    {"code": "18.2.5", "street": "bremer-strasse", "start": None, "end": None,
     "page": 85, "phrase": "Höchstgeschwindigkeit auf der Bremer Straße auf 30 km/h", "stretch": "ganze Straße"},
    {"code": "18.3.1", "street": "ofener-strasse", "start": "osm:Zeughausstraße", "end": "prinzessinweg",
     "page": 90, "phrase": "zunächst nur für den entsprechend identifizierten Hotspotabschnitt",
     "stretch": "Zeughausstraße bis Prinzessinweg"},
    {"code": "18.3.2", "street": "alexanderstrasse", "start": "gertrudenfriedhof", "end": "melkbrink",
     "page": 95, "phrase": "zunächst im Abschnitt zwischen dem Gertrudenfriedhof",
     "stretch": "Gertrudenfriedhof bis Melkbrink / Lambertistraße"},
    {"code": "18.3.3", "street": "donnerschweer-strasse", "start": "karlstrasse", "end": "ammergaustrasse",
     "page": 100, "phrase": "den Abschnitt von der Einmündung Karlstraße", "stretch": "Karlstraße bis Ammergaustraße"},
    {"code": "18.3.4", "street": "damm", "start": None, "end": None,
     "page": 106, "phrase": "auf ganzer Strecke eine Geschwindigkeitsbegrenzung", "stretch": "ganze Straße, sobald die Cäcilienbrücke wieder offen ist"},
]
#: Tabelle 13 des Lärmaktionsplans.
HOTSPOT_PAGE = 55
HOTSPOT_CAPTION = "Tabelle 13: Rangfolge höchster Lärmkennziffern"

#: Tabelle 4 des Wärmeplans und die Seiten, auf denen jedes Gebiet beschrieben ist.
#: Tabellen 27–29 (S. 153, 155): die Ruhigen Gebiete. Nachgezeichnet sind sie in ``scripts/plan_karten.py``;
#: hier stehen alle, auch die zu kleinen, so wie das Dokument sie zählt.
QUIET_PAGE, QUIET_CAPTION = 153, ("Tabelle 27: Ergebnis der Verschneidung — die Flächen 3 und 9 klammert der Plan "
                                  "aus (mögliche Suchräume für Windenergie)")
GREEN_PAGE = 155
CEMETERY_CAPTION = "Tabelle 28: Ergebnis der Überlagerung - Friedhöfe"
RECREATION_CAPTION = "Tabelle 29: Ergebnis der Überlagerung - Erholungsflächen"
WNG_PAGE = 79
WNG_CAPTION = "Tabelle 4: Übersicht über definierte Wärmenetzeignungsgebiete in Oldenburg"
#: Ortsteil laut Tabelle → Ortsbereiche von Ratslotse. Ist der Name des Gebiets selbst ein
#: Ortsbereich („WNG Ohmstede“ im Ortsteil Donnerschwee), zählt er dazu.
WNG_AREAS: dict[str, tuple[str, ...]] = {
    "Innenstadt": ("innenstadt",), "Wechloy": ("wechloy",), "Donnerschwee": ("donnerschwee",),
    "Ziegelhofviertel": ("ziegelhof",), "Dietrichsfeld": ("dietrichsfeld",),
    "Bloherfelde / Eversten": ("bloherfelde", "eversten"), "Eversten": ("eversten",),
    "Kreyenbrück": ("kreyenbrueck",), "Tweelbäke": ("tweelbaeke",),
    "Ehnernviertel / Ziegelhof": ("ehnernviertel", "ziegelhof"),
}

#: Ein Ende gilt als getroffen, wenn es so nah (Meter) an der Straße liegt.
ANCHOR_MAX_M = 90
#: So lang darf ein Abschnitt sein — kürzer ist ein Ankerfehler, länger die halbe Stadt.
SECTION_MIN_M, SECTION_MAX_M = 150, 6000
GEOMETRY_DIGITS = 5
GEOMETRY_STEP = 0.00008


# ── Text ────────────────────────────────────────────────────────────────────

def _pages(document_id: int) -> list[str]:
    import pymupdf
    from plan_massnahmen import holen, sauber
    with pymupdf.open(holen(document_id)) as doc:
        return [sauber(str(doc[i].get_text())) for i in range(doc.page_count)]


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _sentence(page: str, phrase: str) -> str:
    """Der ganze Satz, in dem ``phrase`` steht."""
    at = page.find(phrase)
    if at < 0:
        raise SystemExit(f"„{phrase}“ steht nicht auf der Seite")
    starts = [m.end() for m in re.finditer(r"(?<=[.:])\s+(?=[A-ZÄÖÜ])", page[:at])]
    start = starts[-1] if starts else 0
    end = re.search(r"\.(?=\s+[A-ZÄÖÜ„]|\s*$)", page[at:])
    return page[start: at + (end.end() if end else len(page) - at)].strip()


def hotspots(page: str) -> list[dict]:
    """Tabelle 13: „1 4 Cloppenburger Straße 2 1 Nadorster Straße 3 2 Stiftsweg 4 Wehdestraße …“."""
    body = page.split("Bezeichnung", 1)[1].split("Tabelle 13", 1)[0]
    rows = []
    for m in re.finditer(r"(\d{1,2}) (?:(\d{1,2}) )?([A-ZÄÖÜ][^\d]+?)(?= \d{1,2} |\s*$)", body.strip()):
        rows.append({"rank": int(m.group(1)), "rank_before": int(m.group(2)) if m.group(2) else None,
                     "name": m.group(3).strip()})
    return rows


def _unbreak(name: str) -> str:
    """„Hausbäkenniederung- Everstenmoor“: Trennung am Zeilenende zurücknehmen."""
    return re.sub(r"- (?=[A-ZÄÖÜ])", "-", name.strip())


def quiet_areas(page: str) -> list[list[str]]:
    """Tabelle 27: „1 Swarte Moor 2,6 2 Alexanderheide 17,7 …“ → [Nummer, Bezeichnung, Hektar]."""
    body = _flat(page.split("Flächengröße [ha]", 1)[1].split("Tabelle 27", 1)[0])
    return [[m.group(1), _unbreak(m.group(2)), m.group(3)]
            for m in re.finditer(r"(\d{1,2}) (.+?) (\d+,\d)(?= |$)", body)]


def green_areas(page: str) -> tuple[list[list[str]], list[list[str]]]:
    """Tabellen 28 und 29: „101 Waldfriedhof Ofenerdiek 10,0 1,3% …“ → [Nummer, Name, Hektar, Anteil leise]."""
    head = "LDEN < 60 dB(A)"
    first, rest = page.split(head, 1)[1].split("Tabelle 28", 1)
    second = rest.split(head, 1)[1].split("Tabelle 29", 1)[0]
    def rows(body: str) -> list[list[str]]:
        return [[m.group(1), _unbreak(m.group(2)), m.group(3), m.group(4)]
                for m in re.finditer(r"(\d{3}) (.+?) (\d+,\d) (\d+,\d%)", _flat(body))]
    return rows(first), rows(second)


def heat_areas(pages: list[str]) -> list[dict]:
    """Tabelle 4 und je Gebiet die Seite, auf der es beschrieben ist."""
    table = pages[WNG_PAGE - 1].split("Wärmeliniendichte", 1)[1]
    rows = []
    for m in re.finditer(r"WNG (\d+) (.+?) WNG (.+?) ([\d,]+) GWh/a ([\d,]+) MWh/m\*a", table):
        code, district, name = m.group(1), m.group(2).rstrip(". "), m.group(3).strip()
        page = next((n for n, t in enumerate(pages, 1) if n > WNG_PAGE
                     and re.search(rf"WNG {code} {re.escape(name.split()[0][:6])}[^ ]* ?[^ ]*\.? Eignungsgebiet", t)), None)
        # „WNG Stadtkern“ heißt in der Spalte „Gebiet“ schlicht „Stadtkern“ — die Kennung trägt das Kürzel schon.
        rows.append({"code": f"WNG {code}", "district": district, "name": name,
                     "demand": f"{m.group(4)} GWh/a", "density": f"{m.group(5)} MWh/m*a", "page": page})
    return rows


# ── Linien ──────────────────────────────────────────────────────────────────

def _metres(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Abstand zweier (lon, lat) in Metern — für Oldenburgs Breite genau genug."""
    dx = (a[0] - b[0]) * 111_320 * math.cos(math.radians(53.14))
    dy = (a[1] - b[1]) * 110_540
    return math.hypot(dx, dy)


def _lines(shape: dict) -> list[list[tuple[float, float]]]:
    kind, coords = shape.get("type"), shape.get("coordinates") or []
    if kind == "LineString":
        return [[tuple(p[:2]) for p in coords]]
    if kind in ("MultiLineString", "Polygon"):
        return [[tuple(p[:2]) for p in line] for line in coords]
    if kind == "MultiPolygon":
        return [[tuple(p[:2]) for p in ring] for poly in coords for ring in poly]
    if kind == "Point":
        return [[tuple(coords[:2])]]
    return []


def _anchor_points(anchor: str, catalog: dict, osm: list[dict]) -> list[tuple[float, float]]:
    if anchor.startswith("osm:"):
        name = anchor[4:]
        pts = []
        for e in osm:
            tags = e.get("tags") or {}
            if name not in (tags.get("name"), tags.get("ref")):
                continue
            if e["type"] == "node":
                pts.append((e["lon"], e["lat"]))
            pts += [(g["lon"], g["lat"]) for g in e.get("geometry") or []]
        return pts
    row = catalog.get(anchor)
    if row is None:
        return []
    if row.get("geojson"):
        return [p for line in _lines(json.loads(row["geojson"])) for p in line]
    return [(row["lon"], row["lat"])]


def _path(lines: list[list[tuple[float, float]]], a: tuple[float, float], b: tuple[float, float]) -> list[tuple[float, float]]:
    """Kürzester Weg über die Stücke einer Straße von a nach b (die Stücke sind OSM-Wege in
    beliebiger Reihenfolge, oft beide Fahrbahnen)."""
    def key(p: tuple[float, float]) -> tuple[float, float]:
        return (round(p[0], 6), round(p[1], 6))
    graph: dict[tuple[float, float], list[tuple[float, tuple[float, float]]]] = {}
    for line in lines:
        for p, q in zip(line, line[1:]):
            d = _metres(p, q)
            graph.setdefault(key(p), []).append((d, key(q)))
            graph.setdefault(key(q), []).append((d, key(p)))
    start, goal = key(a), key(b)
    dist = {start: 0.0}
    prev: dict[tuple[float, float], tuple[float, float]] = {}
    queue = [(0.0, start)]
    while queue:
        d, node = heapq.heappop(queue)
        if node == goal:
            break
        if d > dist.get(node, math.inf):
            continue
        for w, nxt in graph.get(node, []):
            if d + w < dist.get(nxt, math.inf):
                dist[nxt] = d + w
                prev[nxt] = node
                heapq.heappush(queue, (d + w, nxt))
    if goal not in dist:
        raise SystemExit(f"Kein Weg über die Straße von {a} nach {b}")
    out = [goal]
    while out[-1] != start:
        out.append(prev[out[-1]])
    return out[::-1]


def _nearest(lines: list[list[tuple[float, float]]], targets: list[tuple[float, float]]) -> tuple[tuple[float, float], float]:
    best, best_d = None, math.inf
    for line in lines:
        for p in line:
            for t in targets:
                d = _metres(p, t)
                if d < best_d:
                    best, best_d = p, d
    assert best is not None
    return best, best_d


def _thin(line: list[tuple[float, float]]) -> list[list[float]]:
    kept = [line[0]]
    for p in line[1:-1]:
        if abs(p[0] - kept[-1][0]) + abs(p[1] - kept[-1][1]) >= GEOMETRY_STEP:
            kept.append(p)
    kept.append(line[-1])
    return [[round(x, GEOMETRY_DIGITS), round(y, GEOMETRY_DIGITS)] for x, y in kept]


def _length(lines: list[list[list[float]]]) -> float:
    return sum(_metres((p[0], p[1]), (q[0], q[1])) for line in lines for p, q in zip(line, line[1:]))


def _areas(shape: dict) -> dict[str, float]:
    """Ortsbereiche, durch die ein Abschnitt läuft — Anteil am längsten Stück = 1."""
    votes = geo.ortsbereiche_der_geometrie(shape)
    by_name = {p.name: p.id for p in places.primary_places()}
    top = max(votes.values(), default=0)
    return {by_name[n]: round(v / top, 2) for n, v in sorted(votes.items(), key=lambda kv: -kv[1])
            if n in by_name and top}


def section(entry: dict, catalog: dict, osm: list[dict]) -> dict:
    row = catalog[entry["street"]]
    # Der Katalog kennt gleichnamige Stücke außerhalb der Stadt („Bremer Straße“ in Hatten) — nur was in
    # Oldenburg liegt, zählt.
    inside = geo.auf_stadtgebiet_beschneiden(json.loads(row["geojson"]))
    if not inside:
        raise SystemExit(f"{entry['code']}: {row['name']} liegt nicht im Stadtgebiet")
    lines = _lines(inside)
    if entry["start"] is None:
        parts = [_thin(line) for line in lines if len(line) >= 2]
    else:
        ends = []
        for anchor in (entry["start"], entry["end"]):
            targets = _anchor_points(anchor, catalog, osm)
            if not targets:
                raise SystemExit(f"{entry['code']}: Ende „{anchor}“ ist unbekannt")
            point, dist = _nearest(lines, targets)
            if dist > ANCHOR_MAX_M:
                raise SystemExit(f"{entry['code']}: „{anchor}“ liegt {dist:.0f} m neben der Straße")
            ends.append(point)
        parts = [_thin(_path(lines, ends[0], ends[1]))]
    shape = {"type": "MultiLineString", "coordinates": parts}
    flat = [p for line in parts for p in line]
    mid = flat[len(flat) // 2]
    return {"code": entry["code"], "name": row["name"], "street": entry["street"], "stretch": entry["stretch"],
            "page": entry["page"], "geometry": shape, "lat": mid[1], "lon": mid[0],
            "length_m": round(_length(parts)), "districts": _areas(shape)}


# ── Schreiben und Prüfen ────────────────────────────────────────────────────

def build_noise(store) -> dict:
    doc = DOCUMENTS["laermaktionsplan"]
    pages = _pages(doc["document_id"])
    osm = json.loads(OSM_ANCHORS.read_text(encoding="utf-8"))["elements"]
    slugs = [e["street"] for e in SECTIONS] + [a for e in SECTIONS for a in (e["start"], e["end"])
                                               if a and not a.startswith("osm:")]
    catalog = store.plan_catalog_places(slugs)
    sections = []
    for entry in SECTIONS:
        out = section(entry, catalog, osm)
        out["quote"] = _sentence(pages[entry["page"] - 1], entry["phrase"])
        sections.append(out)
    rows = hotspots(pages[HOTSPOT_PAGE - 1])
    cemeteries, recreation = green_areas(pages[GREEN_PAGE - 1])
    share = "Anteil unter 60 dB(A)"
    return {"plan": "laermaktionsplan", "document": doc, "sections": sections, "lists": [{
        "key": "hotspots", "title": "Lärm-Schwerpunkte", "caption": HOTSPOT_CAPTION, "page": HOTSPOT_PAGE,
        "columns": ["Rang", "Rang 2015", "Straße"], "name_column": 2,
        "rows": [{"cells": [str(r["rank"]), str(r["rank_before"]) if r["rank_before"] else "–", r["name"]]} for r in rows],
    }, {
        "key": "quiet_areas", "title": "Ruhige Gebiete", "caption": QUIET_CAPTION, "page": QUIET_PAGE,
        "columns": ["Nr.", "Gebiet", "Fläche (ha)"], "name_column": 1,
        "rows": [{"cells": r} for r in quiet_areas(pages[QUIET_PAGE - 1])],
    }, {
        "key": "quiet_cemeteries", "title": "Friedhöfe als Ruhige Gebiete", "caption": CEMETERY_CAPTION,
        "page": GREEN_PAGE, "columns": ["Nr.", "Friedhof", "Fläche (ha)", share], "name_column": 1,
        "rows": [{"cells": r} for r in cemeteries],
    }, {
        "key": "quiet_recreation", "title": "Erholungsflächen als Ruhige Gebiete", "caption": RECREATION_CAPTION,
        "page": GREEN_PAGE, "columns": ["Nr.", "Erholungsfläche", "Fläche (ha)", share], "name_column": 1,
        "rows": [{"cells": r} for r in recreation],
    }]}


def build_heat() -> dict:
    doc = DOCUMENTS["waermeplan"]
    pages = _pages(doc["document_id"])
    rows = heat_areas(pages)
    primary = {p.id for p in places.primary_places()}
    by_name = {p.name.lower(): p.id for p in places.primary_places()}
    out_rows = []
    for r in rows:
        areas = list(WNG_AREAS[r["district"]])
        own = by_name.get(r["name"].lower())
        if own and own not in areas:
            areas.append(own)
        assert all(a in primary for a in areas), areas
        out_rows.append({"cells": [r["code"], r["district"], r["name"], r["demand"], r["density"]],
                         "page": r["page"], "districts": areas, "label": f"Eignungsgebiet „WNG {r['name']}“"})
    return {"plan": "waermeplan", "document": doc, "sections": [], "lists": [{
        "key": "heat_network_areas", "title": "Wärmenetzeignungsgebiete", "caption": WNG_CAPTION, "page": WNG_PAGE,
        "columns": ["Kennung", "Ortsteil", "Gebiet", "Wärmebedarf heute", "Wärmeliniendichte"], "name_column": 2,
        "rows": out_rows,
    }]}


def check(key: str, data: dict, pages: list[str] | None = None) -> list[str]:
    """Form und Plausibilität ohne PDF; mit ``pages`` auch: Zitat und Tabellenzeilen stehen dort."""
    problems = []
    primary = {p.id for p in places.primary_places()}
    if key not in plans.PLANS:
        problems.append(f"{key}: unbekannter Plan")
    codes = [s["code"] for s in data.get("sections", [])]
    if len(set(codes)) != len(codes):
        problems.append(f"{key}: doppelte Abschnitte")
    for s in data.get("sections", []):
        where = f"{key} {s['code']}"
        if not (SECTION_MIN_M <= s["length_m"] <= SECTION_MAX_M):
            problems.append(f"{where}: {s['length_m']} m lang — Anker prüfen")
        if abs(_length(s["geometry"]["coordinates"]) - s["length_m"]) > 5:
            problems.append(f"{where}: Länge passt nicht zur Linie")
        # Wie geo.auf_stadtgebiet_beschneiden: Ein Stück gehört zur Stadt, wenn ein Punkt darin liegt — an
        # den Rändern der Ortsbereiche liegen einzelne Punkte zwischen zwei Polygonen.
        outside = [line[0] for line in s["geometry"]["coordinates"]
                   if not any(geo.ortsbereich_for(p[1], p[0]) for p in line)]
        if outside:
            problems.append(f"{where}: {len(outside)} Stücke liegen außerhalb Oldenburgs, z. B. bei {outside[0]}")
        if not s["districts"] or not set(s["districts"]) <= primary:
            problems.append(f"{where}: Ortsbereiche fehlen oder sind unbekannt")
        if not re.search(r"vorgeschlagen|Vorschlag|sollte", s["quote"]):
            problems.append(f"{where}: Das Zitat ist nicht der Vorschlag")
        if pages is not None and _flat(s["quote"]) not in _flat(pages[s["page"] - 1]):
            problems.append(f"{where}: Zitat steht nicht auf S. {s['page']}")
    for lst in data.get("lists", []):
        where = f"{key} {lst['key']}"
        if not 0 <= lst.get("name_column", -1) < len(lst["columns"]):
            problems.append(f"{where}: name_column fehlt oder zeigt ins Leere")
        if any(len(r["cells"]) != len(lst["columns"]) for r in lst["rows"]):
            problems.append(f"{where}: Zeile mit falscher Spaltenzahl")
        for r in lst["rows"]:
            if not set(r.get("districts", [])) <= primary:
                problems.append(f"{where}: unbekannter Ortsbereich in {r['cells']}")
        if lst["key"] == "hotspots":
            ranks = [int(r["cells"][0]) for r in lst["rows"]]
            if ranks != list(range(1, len(ranks) + 1)):
                problems.append(f"{where}: Rangfolge lückenhaft")
        if pages is not None:
            page = _unbreak(_flat(pages[lst["page"] - 1]))
            for r in lst["rows"]:
                missing = [c for c in r["cells"] if c != "–" and c.replace("*", "") not in page.replace("*", "")]
                if missing:
                    problems.append(f"{where}: {missing} steht nicht auf S. {lst['page']}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--db", default=str(WURZEL / "data" / "council.sqlite"))
    ap.add_argument("--pruefen", action="store_true")
    args = ap.parse_args(argv)
    if args.pruefen:
        problems = []
        for key in plan_state.list_keys():
            data = plan_state.plan_lists(key) or {}
            doc = data.get("document") or {}
            pdf = CACHE / f"{doc.get('document_id')}.pdf"
            pages = _pages(doc["document_id"]) if pdf.exists() else None
            problems += check(key, data, pages)
        print("\n".join(problems) or f"✓ {len(plan_state.list_keys())} Dateien passen")
        return 1 if problems else 0
    from council.store import CouncilStore
    store = CouncilStore(args.db)
    try:
        plan_state.LISTS_DIR.mkdir(exist_ok=True)
        for data in (build_noise(store), build_heat()):
            data = {"plan": data["plan"], "method": "Von Hand gesetzt nach dem Dokument; Zitate und Tabellenzeilen "
                    "aus dem PDF gelesen (scripts/plan_listen.py). Linien: Ortskatalog der Ratsdaten, "
                    "© OpenStreetMap-Mitwirkende, ODbL", "generated": dt.date.today().isoformat(),
                    **{k: v for k, v in data.items() if k != "plan"}}
            problems = check(data["plan"], data)
            if problems:
                print("\n".join(problems))
                return 1
            path = plan_state.LISTS_DIR / f"{data['plan']}.json"
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            print(f"geschrieben: {path.relative_to(WURZEL)} ({len(data['sections'])} Abschnitte, "
                  f"{sum(len(lst['rows']) for lst in data['lists'])} Tabellenzeilen)")
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    sys.exit(main())
