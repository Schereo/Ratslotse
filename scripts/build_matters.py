#!/usr/bin/env python3
"""Grundakten von Hand neu aufbauen (docs/plan-akte.md, Phase 1).

Im Betrieb baut ``check_protocols.py`` sie jede Nacht neu. Auf dev laufen
keine Crons — dort und nach einem Abzug (``scripts/lokale_daten.py setz``)
entstehen sie nur über dieses Skript. Ohne LLM, rund eine Sekunde.

    python scripts/build_matters.py
    python scripts/build_matters.py --db /pfad/zur/council.sqlite
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council import matters  # noqa: E402
from council.store import CouncilStore  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Grundakten neu aufbauen")
    ap.add_argument("--db", type=Path, default=ROOT / "data" / "council.sqlite")
    args = ap.parse_args()
    store = CouncilStore(args.db)
    try:
        print(json.dumps(matters.build(store), ensure_ascii=False))
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
