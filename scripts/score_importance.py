#!/usr/bin/env python3
"""Wichtigkeits-Score aller Ratsbeschlüsse (neu) berechnen.

Schreibt ``council_decisions.importance`` (0–100) aus vier Signalen — Geldbetrag,
Umstrittenheit, Verbindlichkeit & Gremien-Ebene, Beratungsaufwand
(``council/importance.py``). **Kein LLM, kein Netz** — reine Heuristik über die
schon gescrapten Daten, also billig und beliebig oft wiederholbar. Läuft
wöchentlich in ``scripts/weekly_enrich.py`` und lässt sich für den Erstlauf
einzeln aufrufen::

    python scripts/score_importance.py
    python scripts/score_importance.py --only-missing
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def main() -> int:
    ap = argparse.ArgumentParser(description="Wichtigkeits-Score der Beschlüsse berechnen")
    ap.add_argument("--only-missing", action="store_true",
                    help="nur Beschlüsse ohne bisherigen Score bewerten")
    ap.add_argument("--db", default=str(COUNCIL_DB), help="Pfad zur council.sqlite")
    args = ap.parse_args()

    store = CouncilStore(Path(args.db))
    try:
        n = store.backfill_importance(only_missing=args.only_missing)
    finally:
        store.close()
    print(f"Wichtigkeits-Score aktualisiert: {n} Beschlüsse", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
