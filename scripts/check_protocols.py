#!/usr/bin/env python3
"""Pick up newly published council protocols.

Protocols appear days–weeks after a session. This re-scans the last ~90 days and
parses any session whose public protocol is now available but not yet stored.
Idempotent — already-parsed sessions are skipped.

Run daily via cron, e.g. ``0 9 * * *``.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from scripts.backfill_protocols import process_range  # noqa: E402
from scripts.classify_decisions import process as classify_decisions  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"
LOOKBACK_DAYS = 90


def main() -> None:
    since = (date.today() - timedelta(days=LOOKBACK_DAYS)).isoformat()
    print(f"Checking for new protocols since {since}…")
    stats = process_range(COUNCIL_DB, since=since)
    print(f"Done — {stats['parsed']} newly parsed, {stats['no_protocol']} still without "
          f"protocol, {stats['failed']} failed.")
    # Classify any decisions still without a policy field — including the ones just
    # parsed above. Idempotent, so it doubles as the daily classification catch-up.
    cstats = classify_decisions(COUNCIL_DB)
    print(f"Classified {cstats['classified']} decision(s), {cstats['failed']} failed "
          f"→ ${cstats['cost']:.4f}.")


if __name__ == "__main__":
    main()
