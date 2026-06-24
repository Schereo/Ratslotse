#!/usr/bin/env python3
"""Backfill parsed council protocols (decisions + attendance) over a date range.

Walks the council calendar month by month, and for every past session that has a
public protocol not yet parsed, downloads the PDF, extracts structured data via
the LLM and stores it. Idempotent (skips already-parsed sessions) and tolerant of
a single bad protocol.

Usage::

    python scripts/backfill_protocols.py                    # 2023-01 → today
    python scripts/backfill_protocols.py --since 2025-01-01
    python scripts/backfill_protocols.py --force            # re-parse everything
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import protocols  # noqa: E402
from council.scraper import CouncilScraper  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"
DEFAULT_SINCE = "2023-01-01"

# deepseek-v4-pro OpenRouter pricing ($/1M tokens). Only used for the printout.
PRICE_IN, PRICE_OUT = 0.435, 0.87


def _months(since: str, until: str):
    y, m = int(since[:4]), int(since[5:7])
    ey, em = int(until[:4]), int(until[5:7])
    while (y, m) <= (ey, em):
        yield y, m
        m += 1
        if m > 12:
            y, m = y + 1, 1


def process_range(
    council_db: Path,
    since: str,
    until: str | None = None,
    force: bool = False,
    delay: float = 0.3,
) -> dict:
    """Parse all protocols with a session date in [since, until]. Returns stats."""
    until = until or date.today().isoformat()
    scraper = CouncilScraper(delay=delay)
    store = CouncilStore(council_db)
    today = date.today().isoformat()

    parsed = skipped = no_protocol = failed = 0
    tok_in = tok_out = 0

    for y, m in _months(since, until):
        ids = scraper.session_ids_for_month(y, m)
        for ksinr in ids:
            if not force and store.has_protocol(ksinr):
                skipped += 1
                continue
            try:
                doc = protocols.find_protocol(ksinr)
            except Exception as exc:  # noqa: BLE001
                print(f"  [{ksinr}] find_protocol error: {exc!r}")
                continue
            if not doc:
                no_protocol += 1
                continue
            session = scraper.fetch_session(ksinr)
            if not session or session.session_date < since or session.session_date > until:
                continue
            if session.session_date > today:
                continue  # future session shouldn't have a protocol
            store.save_session(session)
            try:
                text, n_pages = protocols.extract_pdf_text(doc["url"])
                data, usage = protocols.extract_protocol(text)
                store.save_protocol(
                    ksinr, doc,
                    {"protocol_nr": data.get("protocol_nr"),
                     "session_start": data.get("session_start"),
                     "session_end": data.get("session_end")},
                    text, n_pages, protocols.MODEL,
                    data.get("decisions", []), data.get("attendance", []),
                )
                tok_in += usage.prompt_tokens
                tok_out += usage.completion_tokens
                parsed += 1
                print(f"  [{ksinr}] {session.session_date} {session.committee[:40]} → "
                      f"{len(data.get('decisions', []))} Beschlüsse, {len(data.get('attendance', []))} Teilnehmer")
            except Exception as exc:  # noqa: BLE001 — keep going on a bad protocol
                store.mark_protocol_failed(ksinr, doc)
                failed += 1
                print(f"  [{ksinr}] FAILED: {exc!r}")
            if delay:
                time.sleep(delay)

    store.close()
    cost = tok_in / 1e6 * PRICE_IN + tok_out / 1e6 * PRICE_OUT
    return {"parsed": parsed, "skipped": skipped, "no_protocol": no_protocol,
            "failed": failed, "tokens_in": tok_in, "tokens_out": tok_out, "cost": cost}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--since", default=DEFAULT_SINCE)
    ap.add_argument("--until", default=date.today().isoformat())
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--delay", type=float, default=0.3)
    args = ap.parse_args()

    print(f"Backfilling protocols {args.since} … {args.until}")
    stats = process_range(args.db, args.since, args.until, args.force, args.delay)
    print(f"\n=== done: {stats['parsed']} parsed, {stats['skipped']} skipped, "
          f"{stats['no_protocol']} without protocol, {stats['failed']} failed ===")
    print(f"Tokens: {stats['tokens_in']:,} in + {stats['tokens_out']:,} out  "
          f"→ ${stats['cost']:.4f} (deepseek-v4-pro)")
    return 1 if stats["failed"] and not stats["parsed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
