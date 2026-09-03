#!/usr/bin/env python3
"""Geocode place/street/area entities via OpenStreetMap (Nominatim) for the map on
their Themen page.

For every ``ort`` entity not yet geocoded, looks it up in Nominatim restricted to the
Oldenburg bounding box, and stores the centre point plus — where available — the drawn
geometry (street line / area polygon as GeoJSON) in ``council_entity_meta``. Entities
that don't resolve are marked as tried (won't be retried). Idempotent.

Respects the Nominatim usage policy: a valid User-Agent and ≤ 1 request/second. A
one-time backfill for ~400 places; not for bulk/abusive use.

    python scripts/geocode_entities.py
    python scripts/geocode_entities.py --limit 10     # smoke test
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OVERPASS = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "Ratslotse/1.0 (https://ratslotse.de; civic info, one-time geocoding)"}
# Oldenburg bounding box. viewbox is left,top,right,bottom = lon_l,lat_t,lon_r,lat_b.
VIEWBOX = "8.10,53.22,8.30,53.08"
LAT_MIN, LAT_MAX, LON_MIN, LON_MAX = 53.08, 53.22, 8.10, 8.30
_GEOM = ("LineString", "MultiLineString", "Polygon", "MultiPolygon")
# Names ending in a street-type word → fetch the WHOLE street from Overpass (all
# segments), not just the single segment Nominatim happens to return.
_STREET_RE = re.compile(r"(stra(ss|ß)e|weg|allee|platz|ring|damm|wall|markt|chaussee|stieg|twiete|kamp|gang)$", re.I)
#: Ortsarten, die IMMER als Straße geholt werden — was die Ortserkennung schon
#: als Straße eingetragen hat, muss kein Namensmuster noch einmal erraten.
_STREET_KINDS = frozenset({"street", "square"})


#: Wie oft der Overpass-Weg in diesem Prozess nicht geliefert hat. Der Aufrufer
#: schreibt die Zahlen in seine Kennzahlen: Ein Lauf, der 500 Straßen „geholt"
#: hat, dabei aber 500 Overpass-Ausfälle zählt, hat NICHT das getan, was er
#: sollte (s. `geocode`).
overpass_ausfaelle = {"fehler": 0, "ohne_treffer": 0, "nicht_erreichbar": 0,
                      "strassen_versucht": 0}

#: Ergebnis der Erreichbarkeitsprobe, einmal je Prozess. ``None`` = noch nicht
#: gemessen.
_overpass_bereit: bool | None = None


def overpass_bereit(url: str = OVERPASS) -> bool:
    """Antwortet Overpass überhaupt? EINMAL je Lauf gemessen.

    **Warum das vor die Arbeit gehört.** Am 03.09.2026 war overpass-api.de von
    beiden VPS aus nicht erreichbar (Errno 101 über das NAT-Gateway). Ohne
    Probe lief der Reparaturlauf trotzdem 513-mal in denselben Fehler, fiel
    jedes Mal still auf Nominatim zurück und meldete am Ende
    ``located=513, missed=2, failed=0``. Die Probe macht daraus EINE Messung
    mit klarer Ansage — und spart die 513 vergeblichen Versuche.

    Gefragt wird der Endpunkt, der auch benutzt wird: ``/api/status`` einiger
    Spiegel antwortete, während ``/api/interpreter`` in den Timeout lief.
    """
    global _overpass_bereit
    if _overpass_bereit is None:
        try:
            antwort = requests.post(
                url, data={"data": "[out:json][timeout:10];out count;"},
                headers=HEADERS, timeout=15)
            antwort.raise_for_status()
            _overpass_bereit = True
        except Exception as fehler:  # noqa: BLE001 — genau das ist die Auskunft
            _overpass_bereit = False
            logging.getLogger(__name__).error(
                "OVERPASS NICHT ERREICHBAR (%s: %s). Straßen bekommen in diesem "
                "Lauf nur EIN Nominatim-Segment statt der ganzen Straße — und "
                "damit nur einen Teil ihrer Ortsbereiche. Der Bestand geht über "
                "den Workflow „Ops: Straßen vollständig nachtragen\" "
                "(scripts/strassen_snapshot.py).",
                type(fehler).__name__, str(fehler)[:200])
    return _overpass_bereit


def _is_street(name: str, kind: str | None = None) -> bool:
    """Ist das ein Straßenname — also: ganze Geometrie bei Overpass holen?

    **Die ART schlägt den Namen.** Bis 09/2026 entschied allein das
    Namensmuster oben, und es kennt nur die geläufigen Endungen. Am
    Prod-Bestand (03.09.2026 gemessen) fielen damit 96 der 570 Straßen durch:
    „Tweelbäker Tredde", „Am Schmeel", „Babenend", „Watertucht",
    „Huntemannstr" (abgekürzt, ohne Punkt). Sie gingen an Nominatim, und das
    liefert EIN Segment statt der ganzen Straße — der Rest der Straße samt
    seiner Ortsbereiche fehlte. „Tweelbäker Tredde" lag damit ganz in
    Tweelbäke, obwohl 51 von 85 Stützpunkten der vollen Straße in Krusenbusch
    liegen; im Einrichtungs-Assistenten stand sie deshalb unter „direkt
    nebenan", während sie mitten durch den eigenen Stadtteil führt (Tims
    Befund, 03.09.2026).

    ``kind`` ist die Ortsart aus ``council_locations`` — die Ortserkennung hat
    dort längst „street" stehen. Wo es die Art nicht gibt (Entitäten), bleibt
    es beim Namensmuster, ergänzt um die Muster des Stores: abgekürzte
    Straßen („…str") und die Namen, die vorne statt hinten erkennbar sind
    („Am Schmeel", „Unter den Eichen").
    """
    from council.store import CouncilStore

    if (kind or "").strip().lower() in _STREET_KINDS:
        return True
    name = name.strip()
    return bool(_STREET_RE.search(name)) or CouncilStore._looks_like_street(name)


def overpass_street(name: str) -> tuple | None:
    """Full geometry of a named street within Oldenburg as a MultiLineString (all
    segments merged), via Overpass. None if the street isn't found."""
    q = (f'[out:json][timeout:25];'
         f'way["name"="{name}"]["highway"]({LAT_MIN},{LON_MIN},{LAT_MAX},{LON_MAX});'
         f'out geom;')
    r = requests.post(OVERPASS, data={"data": q}, headers=HEADERS, timeout=45)
    r.raise_for_status()
    lines = [[[p["lon"], p["lat"]] for p in el.get("geometry", [])]
             for el in r.json().get("elements", []) if el.get("geometry")]
    lines = [ln for ln in lines if len(ln) >= 2]
    if not lines:
        return None
    pts = [p for ln in lines for p in ln]
    lat = sum(p[1] for p in pts) / len(pts)
    lon = sum(p[0] for p in pts) / len(pts)
    geojson = json.dumps({"type": "MultiLineString", "coordinates": lines}, separators=(",", ":"))
    return lat, lon, geojson


def nominatim(name: str) -> tuple | None:
    """``(lat, lon, geojson_str|None)`` for a name in Oldenburg via Nominatim, or None
    if it doesn't resolve inside the city box. Keeps line/polygon geometry; bare points
    fall back to just the centre (lat/lon)."""
    params = {"q": f"{name}, Oldenburg", "format": "jsonv2", "polygon_geojson": 1,
              "limit": 1, "countrycodes": "de", "viewbox": VIEWBOX, "bounded": 1}
    r = requests.get(NOMINATIM, params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    arr = r.json()
    if not arr:
        return None
    hit = arr[0]
    lat, lon = float(hit["lat"]), float(hit["lon"])
    if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
        return None  # outside Oldenburg → reject as a mis-geocode
    gj = hit.get("geojson")
    geojson = json.dumps(gj, separators=(",", ":")) if gj and gj.get("type") in _GEOM else None
    return lat, lon, geojson


def geocode(name: str, kind: str | None = None) -> tuple | None:
    """Route by name: a street → its full geometry from Overpass (fall back to Nominatim
    if Overpass fails); anything else → Nominatim point/polygon.

    Die Straßen-Geometrie wird auf das Stadtgebiet beschnitten. Overpass sucht
    in einem RECHTECK um Oldenburg, und das ist größer als die Stadt: Bei
    häufigen Namen kam der gleichnamige Weg der Nachbargemeinde mit ins
    Ergebnis, alle Segmente wurden verschmolzen, und der Mittelpunkt lag
    irgendwo dazwischen — „Alter Postweg" war so für den Stadtteil-Filter
    verloren, obwohl sein Oldenburger Teil sauber in Kreyenbrück liegt.
    """
    if _is_street(name, kind):
        overpass_ausfaelle["strassen_versucht"] += 1
        if not overpass_bereit():
            # Die Probe hat es schon gemeldet; hier wird nur gezählt, damit die
            # Kennzahlen des Laufs die Wahrheit sagen.
            overpass_ausfaelle["nicht_erreichbar"] += 1
            return nominatim(name)
        try:
            res = overpass_street(name)
            if res:
                return _auf_stadtgebiet(res)
            overpass_ausfaelle["ohne_treffer"] += 1
        except Exception as fehler:  # noqa: BLE001 — Nominatim ist der Rückfall
            # NICHT still: Am 03.09.2026 war overpass-api.de von beiden VPS aus
            # gar nicht erreichbar (Errno 101 über das NAT-Gateway). Der stumme
            # Rückfall ließ das wie einen gelungenen Lauf aussehen —
            # `located=513, missed=2, failed=0` —, während 498 Straßen ein
            # Nominatim-Einzelsegment bekamen statt der ganzen Straße. Ein
            # ausgefallener Dienst muss sich wie ein Ausfall lesen.
            overpass_ausfaelle["fehler"] += 1
            if overpass_ausfaelle["fehler"] <= 3:
                logging.getLogger(__name__).warning(
                    "Overpass nicht erreichbar (%s: %s) — %r fällt auf Nominatim "
                    "zurück und bekommt damit nur EIN Straßensegment. Der ganze "
                    "Bestand geht über scripts/strassen_snapshot.py.",
                    type(fehler).__name__, fehler, name)
    return nominatim(name)


def _auf_stadtgebiet(res: tuple) -> tuple | None:
    """(lat, lon, geojson) auf den Oldenburger Teil eindampfen."""
    from council import geo

    lat, lon, gj = res
    if not gj:
        return res
    beschnitten = geo.auf_stadtgebiet_beschneiden(gj)
    if not beschnitten:
        return None                      # nichts davon liegt in Oldenburg
    punkte = geo._geometrie_punkte(beschnitten)
    if not punkte:
        return None
    # Mittelpunkt NEU aus dem beschnittenen Teil — der alte gehörte zur
    # Mischgeometrie und lag oft in keinem Ortsbereich.
    mitte_lat = (min(p[0] for p in punkte) + max(p[0] for p in punkte)) / 2
    mitte_lon = (min(p[1] for p in punkte) + max(p[1] for p in punkte)) / 2
    return mitte_lat, mitte_lon, json.dumps(beschnitten, separators=(",", ":"))


def process(council_db: Path, sleep: float = 1.1, limit: int | None = None, reset: bool = False) -> dict:
    store = CouncilStore(council_db)
    if reset:
        n = store.reset_geo()
        print(f"reset geo for {n} entit(y/ies) — re-geocoding all.", flush=True)
    ents = store.entities_to_geocode()
    if limit:
        ents = ents[:limit]
    print(f"{len(ents)} place entit(y/ies) to geocode (~{sleep:.1f}s each).", flush=True)
    hit = shape = miss = err = 0
    for i, e in enumerate(ents, 1):
        try:
            res = geocode(e["name"])
        except Exception as exc:  # noqa: BLE001 — network/parse → mark tried, move on
            print(f"  ! {e['name']}: {exc!r}", flush=True)
            res, err = None, err + 1
        if res:
            store.set_entity_geo(e["slug"], res[0], res[1], res[2])
            hit += 1
            shape += 1 if res[2] else 0
        else:
            store.set_entity_geo(e["slug"], None, None, None)  # mark tried
            miss += 1
        if i % 20 == 0 or i == len(ents):
            print(f"  [{i}/{len(ents)}] {hit} located ({shape} with shape), {miss} not found", flush=True)
        time.sleep(sleep)
    store.close()
    return {"located": hit, "with_shape": shape, "not_found": miss, "errors": err}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--sleep", type=float, default=1.1)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--reset", action="store_true", help="clear prior geo and re-geocode all places")
    args = ap.parse_args()
    st = process(args.db, args.sleep, args.limit, args.reset)
    print(f"\n=== done: {st['located']} located ({st['with_shape']} with drawn shape), "
          f"{st['not_found']} not found, {st['errors']} errors ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
