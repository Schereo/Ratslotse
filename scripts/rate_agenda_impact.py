#!/usr/bin/env python3
"""Tragweite der kommenden Tagesordnungspunkte bewerten (RL-U16 für TOPs).

Dieselbe Rubrik wie bei den Beschlüssen (Betroffene · Geld · Bindung ·
Präzedenz), nur vor der Sitzung statt nach dem Protokoll — die Wochen-Karte
wählt damit aus, was sie hervorhebt. Vorher entschied eine Heuristik aus
Verfahrenssignalen; die stellte einen Museumsbericht über eine
Satzungsänderung (Befund 15.08.).

Läuft täglich hinter ``check_committees.py`` (neue Tagesordnungen kommen dort
herein) und kostet wenig: rund 30–60 Punkte je Woche in 20er-Batches::

    python scripts/rate_agenda_impact.py --limit 200
    python scripts/rate_agenda_impact.py --tage 21   # Vorlauf-Fenster

Bewertet werden nur öffentliche Punkte kommender Sitzungen; Formalien fliegen
vorher raus. Bereits Bewertetes wird nie erneut bezahlt (Tabelle
``agenda_item_impact``, Schlüssel ksinr + item_number).
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

from council.impact import BATCH_SIZE, rate_agenda_batch  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def process(db_path: Path, limit: int | None, tage: int, workers: int) -> tuple[int, int]:
    store = CouncilStore(db_path)
    try:
        todo = store.agenda_items_needing_impact(limit, tage_voraus=tage)
        # Der Prompt spricht über „id" — Tagesordnungspunkte haben keine, also
        # bekommt jeder eine laufende Nummer und wird danach zurückgeordnet.
        for i, it in enumerate(todo):
            it["id"] = i
        nach_id = {it["id"]: it for it in todo}
        batches = [todo[i : i + BATCH_SIZE] for i in range(0, len(todo), BATCH_SIZE)]
        rated = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for results in pool.map(rate_agenda_batch, batches):
                for iid, score, reason in results:
                    it = nach_id.get(iid)
                    if not it:
                        continue
                    store.save_agenda_impact(it["ksinr"], it["item_number"], score, reason)
                    rated += 1
        return len(todo), rated
    finally:
        store.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Tragweite der Tagesordnungspunkte bewerten (LLM)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--tage", type=int, default=21, help="Vorlauf in Tagen (Default 21)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()

    todo, rated = process(Path(args.db), args.limit, args.tage, args.workers)
    print(f"Tragweite (TOPs): {rated}/{todo} Punkte bewertet", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
