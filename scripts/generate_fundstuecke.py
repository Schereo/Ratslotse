#!/usr/bin/env python3
"""Fundstücke des Tages (RL-U11) im Voraus generieren.

Füllt fehlende Kalendertage von heute bis ``--days`` in die Zukunft — je Tag
ein kuratierter Beschluss (Jahrestage zuerst, sonst Top-Interessantheit) mit
1-Satz-Story. Idempotent: vorhandene Tage bleiben unangetastet, die Karten
liegen prüfbar in ``council_fundstuecke``. Wöchentlich in
``scripts/weekly_enrich.py`` (21 Tage Vorlauf); Erstlauf einzeln::

    python scripts/generate_fundstuecke.py --days 21
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council.fundstueck import generate_for_day  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def main() -> int:
    ap = argparse.ArgumentParser(description="Fundstücke des Tages vorab generieren")
    ap.add_argument("--days", type=int, default=21, help="Tage Vorlauf ab heute")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()

    store = CouncilStore(Path(args.db))
    try:
        wanted = [(date.today() + timedelta(days=i)).isoformat() for i in range(args.days)]
        present = store.fundstueck_days_present(wanted)
        missing = [d for d in wanted if d not in present]
        done = sum(1 for d in missing if generate_for_day(store, date.fromisoformat(d)))
        print(
            f"Fundstücke: {done}/{len(missing)} fehlende Tage gefüllt "
            f"({len(present)} lagen schon vor)",
            flush=True,
        )
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
