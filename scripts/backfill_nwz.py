#!/usr/bin/env python3
"""Backfill the NWZ database from the archive back to a given date.

``available5.php`` only returns ~30 editions around a reference date, so the
plain ``available`` call can't reach far into the past. ``available_archive``
walks the reference date backwards in overlapping windows to enumerate the whole
archive in a date range — this script then stores every edition not already
present.

Idempotent: editions already stored at the current ``content_version`` are
skipped unless ``--force`` is given. A failure on one edition is logged and the
backfill continues with the rest.

Usage::

    python scripts/backfill_nwz.py                      # back to 2026-01-01
    python scripts/backfill_nwz.py --since 2026-03-01   # custom start date
    python scripts/backfill_nwz.py --folder 8389        # explicit title
    python scripts/backfill_nwz.py --force              # re-fetch even if stored
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

from nwz.api import TITLES, from_env  # noqa: E402
from nwz.parse import parse_publication  # noqa: E402
from nwz.store import Store  # noqa: E402

DEFAULT_SINCE = "2026-01-01"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--folder", type=int, default=8389,
                    help="NWZ folder id (default 8389 = Oldenburger Nachrichten)")
    ap.add_argument("--db", type=Path, default=ROOT / "data" / "nwz.sqlite")
    ap.add_argument("--since", default=DEFAULT_SINCE,
                    help=f"Oldest publication date to backfill, YYYY-MM-DD (default {DEFAULT_SINCE})")
    ap.add_argument("--until", default=date.today().isoformat(),
                    help="Newest publication date to backfill (default today)")
    ap.add_argument("--force", action="store_true",
                    help="Re-fetch even if already stored at current content_version")
    ap.add_argument("--delay", type=float, default=0.4,
                    help="Seconds to wait between fetches, to be gentle on the API (default 0.4)")
    args = ap.parse_args()

    title_name = TITLES.get(args.folder, f"folder {args.folder}")
    print(f"Title: {title_name} (folder {args.folder})")
    print(f"Range: {args.since} … {args.until}")

    client = from_env()
    store = Store(args.db)

    print("Enumerating archive (walking date windows)…", flush=True)
    editions = client.available_archive(args.folder, since=args.since, until=args.until)
    if not editions:
        print("No editions found in range — check credentials / subscription.")
        return 1
    print(f"Archive exposes {len(editions)} edition(s): "
          f"{editions[0].publication_date} … {editions[-1].publication_date}")

    fetched = skipped = failed = 0
    for i, e in enumerate(editions, 1):
        tag = f"[{i:3d}/{len(editions)}] {e.publication_date} catalog={e.catalog}"
        if not args.force and store.has_edition(e.catalog, e.content_version):
            print(f"  {tag}  SKIP (already stored)")
            skipped += 1
            continue
        try:
            print(f"  {tag}  fetching...", flush=True)
            xml = client.content_xml(e.catalog)
            meta, articles = parse_publication(xml)
            store.save_edition(e, articles)
            chars = sum(len(a.content_text) for a in articles)
            print(f"      → {len(articles)} articles, {chars:,} chars body text")
            fetched += 1
            if args.delay:
                time.sleep(args.delay)
        except Exception as exc:  # noqa: BLE001 — keep going on a bad edition
            print(f"      ! FAILED: {exc!r}")
            failed += 1

    print(f"\n=== done: {fetched} fetched, {skipped} skipped, {failed} failed ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
