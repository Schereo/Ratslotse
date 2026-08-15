#!/usr/bin/env python3
"""(Re)build the decisions full-text index (council_decisions_fts) for hybrid search.

Pure SQLite (no LLM, no fastembed), instant. Run after new decisions are parsed; the
daily cron calls it too::

    python scripts/build_decisions_fts.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    args = ap.parse_args()
    store = CouncilStore(args.db)
    n = store.rebuild_fts()
    store.close()
    print(f"=== FTS rebuilt: {n} decisions indexed ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
