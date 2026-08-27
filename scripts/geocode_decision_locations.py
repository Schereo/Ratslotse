#!/usr/bin/env python3
"""Neue Beschluss-Orte geokodieren und daraus den Stadtteil ableiten.

Bereits vorhandene Entitäts-Geocodes werden zuerst kostenlos übernommen. Für
amtliche Stadtteile nutzen wir die lokalen Polygone; nur übrige Orte gehen mit
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

from council import geo  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from scripts.geocode_entities import geocode  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"


def process(council_db: Path, *, limit: int | None = None, sleep: float = 1.1) -> dict:
    store = CouncilStore(council_db)
    reused = store.hydrate_location_geo_from_entities()
    districts = store.backfill_location_stadtteile()
    rows = store.locations_to_geocode(limit=limit)
    print(f"Orts-Geocoding: reused={reused}, pending={len(rows)}", flush=True)
    located = missed = failed = 0
    for index, row in enumerate(rows, start=1):
        try:
            if row["kind"] == "stadtteil" and geo.stadtteil_center(row["name"]):
                lat, lon = geo.stadtteil_center(row["name"])
                shape = geo.stadtteil_polygon(row["name"])
                result = (lat, lon, json.dumps(shape, separators=(",", ":")))
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
        if sleep and row["kind"] != "stadtteil":
            time.sleep(sleep)
        if index % 20 == 0 or index == len(rows):
            print(
                f"Fortschritt: {index}/{len(rows)}, located={located}, "
                f"missed={missed}, failed={failed}",
                flush=True,
            )
    store.close()
    return {"reused": reused, "districts": districts, "pending": len(rows), "located": located,
            "missed": missed, "failed": failed}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--sleep", type=float, default=1.1)
    args = ap.parse_args()
    stats = process(args.db, limit=args.limit, sleep=args.sleep)
    print("Orts-Geocoding: " + ", ".join(f"{key}={value}" for key, value in stats.items()))
    return 1 if stats["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
