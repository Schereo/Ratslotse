#!/usr/bin/env python3
"""Extract € amounts from council decisions into amount_eur (regex, no LLM, instant).

Stores the largest recognised euro amount per decision as a scale indicator for the
"Ausgaben nach Themenfeld" view. Idempotent; ``--only-missing`` for the daily cron.

Usage::

    python scripts/extract_amounts.py
    python scripts/extract_amounts.py --only-missing
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import money  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"


def process(council_db: Path, only_missing: bool = False) -> dict:
    store = CouncilStore(council_db)
    decs = store.decisions_for_amount(only_missing=only_missing)
    rows = [(money.largest_amount(f"{d['title'] or ''}. {d['beschluss'] or ''}"), d["id"]) for d in decs]
    store.set_amounts(rows)
    store.close()
    return {"decisions": len(rows), "with_amount": sum(1 for a, _ in rows if a)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--only-missing", action="store_true")
    args = ap.parse_args()
    stats = process(args.db, args.only_missing)
    print(f"=== done: {stats['with_amount']}/{stats['decisions']} decisions with a € amount ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
