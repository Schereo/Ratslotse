#!/usr/bin/env python3
"""Neue Beschluss-Orte geokodieren und daraus den Ortsbereich ableiten.

Bereits vorhandene Entitäts-Geocodes werden zuerst kostenlos übernommen. Für
Ratslotse-Ortsbereiche nutzen wir die lokalen Polygone; nur übrige Orte gehen mit
höchstens einem Request pro Sekunde an Nominatim/Overpass.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import geo, places  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from scripts.geocode_entities import geocode  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"


def process(council_db: Path, *, limit: int | None = None, sleep: float = 1.1,
            erneut: bool = False) -> dict:
    store = CouncilStore(council_db)
    curated = store.apply_curated_location_geocodes()
    reused = store.hydrate_location_geo_from_entities()
    districts = store.backfill_location_districts()
    # Der Rest, den kein Geocoder je findet: Orte, die ihren Stadtteil im
    # eigenen Namen tragen („GS Drielake", „Bürgerhaus Ofenerdiek").
    aus_namen = store.backfill_location_districts_from_name()
    catalog_links = store.backfill_location_place_ids()
    rows = store.locations_to_geocode(limit=limit, retry_failed=erneut)
    print(f"Orts-Geocoding: reused={reused}, pending={len(rows)}", flush=True)
    located = missed = failed = 0
    for index, row in enumerate(rows, start=1):
        local = False
        try:
            catalog_place = places.resolve(row["name"])
            if catalog_place and catalog_place.lat is not None and catalog_place.lon is not None:
                result = (catalog_place.lat, catalog_place.lon, None)
                local = True
            elif row["kind"] == "district" and geo.ortsbereich_center(row["name"]):
                lat, lon = geo.ortsbereich_center(row["name"])
                shape = geo.ortsbereich_polygon(row["name"])
                result = (lat, lon, json.dumps(shape, separators=(",", ":")))
                local = True
            else:
                result = geocode(row["name"])
        except Exception as exc:  # noqa: BLE001 — Netzwerkfehler beim nächsten Lauf erneut versuchen
            failed += 1
            print(f"! {row['name']}: {exc!r}", flush=True)
            continue
        if result:
            store.set_location_geo(row["slug"], result[0], result[1], result[2])
            located += 1
        else:
            store.set_location_geo(row["slug"], None, None, None)
            missed += 1
        if sleep and not local:
            time.sleep(sleep)
        if index % 20 == 0 or index == len(rows):
            print(
                f"Fortschritt: {index}/{len(rows)}, located={located}, "
                f"missed={missed}, failed={failed}",
                flush=True,
            )
    # Nach dem Geocoden noch einmal ableiten: Was gerade Koordinaten bekommen
    # hat, hat noch keinen Stadtteil — und ohne diesen zweiten Durchgang wären
    # die frisch geocodierten Straßen sofort wieder Waisen.
    districts += store.backfill_location_districts()
    korrigiert = (store.korrigiere_widerspruechliche_stadtteile()
                  + store.korrigiere_gleichnamige_stadtteile())
    store.close()
    return {"curated": curated, "reused": reused, "districts": districts,
            "districts_from_name": aus_namen, "korrigiert": korrigiert,
            "catalog_links": catalog_links,
            "pending": len(rows), "located": located,
            "missed": missed, "failed": failed}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--erneut", action="store_true",
                    help="auch Orte erneut versuchen, bei denen das Geocoding schon "
                         "einmal misslungen ist (Overpass/Nominatim antworten nicht "
                         "jeden Tag gleich)")
    ap.add_argument("--sleep", type=float, default=1.1)
    args = ap.parse_args()
    stats = process(args.db, limit=args.limit, sleep=args.sleep, erneut=args.erneut)
    print("Orts-Geocoding: " + ", ".join(f"{key}={value}" for key, value in stats.items()))
    return 1 if stats["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
