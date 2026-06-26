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
HEADERS = {"User-Agent": "Ratslotse/1.0 (https://ratslotse.de; civic info, one-time geocoding)"}
# Oldenburg bounding box. viewbox is left,top,right,bottom = lon_l,lat_t,lon_r,lat_b.
VIEWBOX = "8.10,53.22,8.30,53.08"
LAT_MIN, LAT_MAX, LON_MIN, LON_MAX = 53.08, 53.22, 8.10, 8.30
_GEOM = ("LineString", "MultiLineString", "Polygon", "MultiPolygon")


def geocode(name: str) -> tuple | None:
    """``(lat, lon, geojson_str|None)`` for a name in Oldenburg, or None if it doesn't
    resolve inside the city box. Keeps line/polygon geometry; bare points fall back to
    just the centre (lat/lon)."""
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


def process(council_db: Path, sleep: float = 1.1, limit: int | None = None) -> dict:
    store = CouncilStore(council_db)
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
    args = ap.parse_args()
    st = process(args.db, args.sleep, args.limit)
    print(f"\n=== done: {st['located']} located ({st['with_shape']} with drawn shape), "
          f"{st['not_found']} not found, {st['errors']} errors ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
