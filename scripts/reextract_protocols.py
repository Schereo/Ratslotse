#!/usr/bin/env python3
"""Re-extract decisions from already-downloaded protocol text.

Protocol PDFs are stored as raw_text in council_protocols. This re-runs the
(improved) LLM extraction over that stored text — no re-download — and replaces
the decisions/attendance. Use after changing the extraction prompt/schema, e.g.
to add sub-vote granularity.

Usage::

    python scripts/reextract_protocols.py            # all stored protocols
    python scripts/reextract_protocols.py --limit 5  # just the first few (test)
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import protocols  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"
PRICE_IN, PRICE_OUT = 0.435, 0.87


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--limit", type=int, default=0, help="0 = all")
    ap.add_argument("--delay", type=float, default=0.3)
    args = ap.parse_args()

    store = CouncilStore(args.db)
    rows = store.get_protocols_raw()
    if args.limit:
        rows = rows[:args.limit]
    print(f"Re-extracting {len(rows)} protocol(s)…")

    done = failed = 0
    tok_in = tok_out = 0
    for p in rows:
        ksinr = p["ksinr"]
        try:
            data, usage = protocols.extract_protocol(p["raw_text"])
            store.save_protocol(
                ksinr, {"document_id": p["document_id"], "url": p["document_url"]},
                {"protocol_nr": data.get("protocol_nr"),
                 "session_start": data.get("session_start"),
                 "session_end": data.get("session_end")},
                p["raw_text"], p["n_pages"], protocols.MODEL,
                data.get("decisions", []), data.get("attendance", []),
            )
            tok_in += usage.prompt_tokens
            tok_out += usage.completion_tokens
            done += 1
            n_dec = sum(1 for d in data.get("decisions", []))
            n_sub = sum(len(d.get("sub_votes") or []) for d in data.get("decisions", []))
            print(f"  [{ksinr}] {n_dec} Beschlüsse (+{n_sub} Teilabstimmungen)")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  [{ksinr}] FAILED: {exc!r}")
        if args.delay:
            time.sleep(args.delay)

    store.close()
    cost = tok_in / 1e6 * PRICE_IN + tok_out / 1e6 * PRICE_OUT
    print(f"\n=== done: {done} re-extracted, {failed} failed — ${cost:.4f} ===")
    return 1 if failed and not done else 0


if __name__ == "__main__":
    raise SystemExit(main())
