#!/usr/bin/env python3
"""Interessantheits-Score (RL-U11) per LLM nachfüllen.

Bewertet Beschlüsse ohne ``interest`` in 20er-Batches (Gesprächswert fürs
„Fundstück des Tages" — bewusst getrennt vom heuristischen Wichtigkeits-Score).
Neueste zuerst; wöchentlich in ``scripts/weekly_enrich.py`` (500er-Tranche),
für den Erstlauf über den Bestand einzeln aufrufbar::

    python scripts/rate_interest.py --limit 500
    python scripts/rate_interest.py            # alles Fehlende
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

from council.interest import BATCH_SIZE, rate_batch  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def process(db_path: Path, limit: int | None, workers: int) -> tuple[int, int]:
    store = CouncilStore(db_path)
    try:
        todo = store.decisions_needing_interest(limit)
        batches = [todo[i : i + BATCH_SIZE] for i in range(0, len(todo), BATCH_SIZE)]
        rated = 0
        # LLM-Calls in Workern, DB-Schreiben im Main-Thread (SQLite-Konvention).
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for results in pool.map(rate_batch, batches):
                for did, score, reason in results:
                    store.save_interest(did, score, reason)
                    rated += 1
        return len(todo), rated
    finally:
        store.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Interessantheit der Beschlüsse bewerten (LLM)")
    ap.add_argument("--limit", type=int, default=None, help="max. Beschlüsse in diesem Lauf")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()

    todo, rated = process(Path(args.db), args.limit, args.workers)
    print(f"Interessantheit: {rated}/{todo} Beschlüsse bewertet", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
