#!/usr/bin/env python3
"""Pläne der Stadt von Hand zuordnen (docs/plan-ziele-plaene.md, Phase 1).

Im Betrieb baut ``check_protocols.py`` die Tabellen ``council_plan_items`` und
``council_plan_links`` jede Nacht neu. Auf dev laufen keine Crons — dort
(nach jedem Deploy, ``deploy-dev.yml``) und nach einem Abzug
(``scripts/lokale_daten.py setz``) entstehen sie über dieses Skript. Ohne
Modell, rund eine Sekunde.

    python scripts/build_plans.py
    python scripts/build_plans.py --db /pfad/zur/council.sqlite
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council import plan_tracking  # noqa: E402
from council.store import CouncilStore  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Pläne der Stadt neu zuordnen")
    ap.add_argument("--db", type=Path, default=ROOT / "data" / "council.sqlite")
    args = ap.parse_args()
    store = CouncilStore(args.db)
    try:
        print(json.dumps(plan_tracking.build(store), ensure_ascii=False))
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
