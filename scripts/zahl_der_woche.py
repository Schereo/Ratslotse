#!/usr/bin/env python3
"""Die Zahl der Woche für „Heute“ wählen und in Alltagssprache schreiben.

Täglich; neu gewählt wird nur, wenn ein Kandidat dazukam oder der gewählte
wegfiel — sonst kostet der Lauf nichts. Was gesammelt, gewählt und geprüft
wird, steht in ``council/week_number.py``::

    python scripts/zahl_der_woche.py            # der Cron-Weg
    python scripts/zahl_der_woche.py --probe    # Kandidaten und Vorschlag zeigen, nichts speichern
    python scripts/zahl_der_woche.py --neu      # auch ohne neuen Kandidaten neu wählen

crontab (Prod), nach ``check_protocols`` (9 Uhr, schreibt die Kurzfassungen)
und dem ersten Lauf von ``vorlagen_dossiers`` (10 Uhr)::

    30 11 * * * cd ~/app && .venv/bin/python scripts/zahl_der_woche.py >> data/zahl_der_woche.log 2>&1
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import week_number  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from kern.alerts import run_guarded  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def main() -> dict:
    ap = argparse.ArgumentParser(description="Zahl der Woche (LLM)")
    ap.add_argument("--probe", action="store_true", help="Kandidaten und Vorschlag zeigen, NICHTS speichern")
    ap.add_argument("--neu", action="store_true", help="auch ohne neuen Kandidaten neu wählen")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()
    store = CouncilStore(Path(args.db))
    try:
        if args.probe:
            cands = week_number.candidates(store)
            for c in cands:
                print(json.dumps(week_number._prompt_view(c), ensure_ascii=False)[:240])
            karte, quelle, kosten = week_number.choose(cands) if cands else (None, None, 0.0)
            print("→", quelle, json.dumps(karte, ensure_ascii=False), f"{kosten:.4f} $")
            return {"Probe": len(cands)}
        kennzahlen = week_number.run(store, force=args.neu)
    finally:
        store.close()
    print(f"Zahl der Woche: {kennzahlen}", flush=True)
    return kennzahlen


if __name__ == "__main__":
    raise SystemExit(run_guarded("zahl_der_woche", main))
