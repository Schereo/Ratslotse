#!/usr/bin/env python3
"""Tragweite-Score (RL-U16) per LLM nachfüllen.

Bewertet Beschlüsse ohne ``impact`` in 20er-Batches nach fester Rubrik
(Betroffene · Geld · Bindung · Präzedenz). Wöchentlich in
``scripts/weekly_enrich.py`` (500er-Tranche, VOR dem Wichtigkeits-Score,
damit die 50/50-Mischung frische Werte sieht); Erstlauf einzeln::

    python scripts/rate_impact.py --limit 500
    python scripts/rate_impact.py            # alles Fehlende

Vor dem ersten Prod-Lauf: ``scripts/eval_impact.py`` (Golden-Set) bestehen.
"""
from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council.impact import BATCH_SIZE, rate_batch  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def process(db_path: Path, limit: int | None, workers: int) -> tuple[int, int]:
    store = CouncilStore(db_path)
    try:
        todo = store.decisions_needing_impact(limit)
        batches = [todo[i : i + BATCH_SIZE] for i in range(0, len(todo), BATCH_SIZE)]
        rated = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for results in pool.map(rate_batch, batches):
                for did, score, reason in results:
                    store.save_impact(did, score, reason)
                    rated += 1
        return len(todo), rated
    finally:
        store.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Tragweite der Beschlüsse bewerten (LLM)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()

    todo, rated = process(Path(args.db), args.limit, args.workers)
    print(f"Tragweite: {rated}/{todo} Beschlüsse bewertet", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
