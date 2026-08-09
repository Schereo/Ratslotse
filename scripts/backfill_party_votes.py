#!/usr/bin/env python3
"""Teilvoten-Backfill: parst den Abstimmungssatz (raw_result) aller Beschlüsse
und füllt council_decision_votes — welche Fraktion stimmte laut Protokoll
dagegen bzw. enthielt sich (council/votes.py, konservativ: nur ausdrücklich
Benanntes, Gruppen bleiben Gruppen).

Rein lokal (kein Netz, kein LLM), idempotent — je Beschluss werden die Zeilen
ersetzt. Neue Protokolle brauchen den Lauf nicht (der Import parst selbst);
das Skript holt den Bestand nach::

    python scripts/backfill_party_votes.py
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council.store import CouncilStore  # noqa: E402
from council.votes import parse_raw_result  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"


def process(db: Path) -> dict:
    store = CouncilStore(db)
    rows = store.decisions_with_raw_result()
    n_with, n_rows = 0, 0
    stances: Counter = Counter()
    for r in rows:
        votes = parse_raw_result(r["raw_result"])
        store.save_decision_votes(r["id"], votes)
        if votes:
            n_with += 1
            n_rows += len(votes)
            stances.update(s for _, s in votes)
    store.close()
    return {"decisions": len(rows), "mit_voten": n_with, "zeilen": n_rows, **dict(stances)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    args = ap.parse_args()
    stats = process(args.db)
    print(f"=== {stats['decisions']} Abstimmungssätze geprüft, "
          f"{stats['mit_voten']} mit benannten Fraktionen, {stats['zeilen']} Voten-Zeilen ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
