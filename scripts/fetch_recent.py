#!/usr/bin/env python3
"""Fetch the N most recent editions of one NWZ title into SQLite."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from nwz.api import TITLES, from_env  # noqa: E402
from nwz.parse import parse_publication  # noqa: E402
from nwz.store import Store  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", type=int, default=8389,
                    help="NWZ folder id (default 8389 = Oldenburger Nachrichten)")
    ap.add_argument("--limit", type=int, default=10,
                    help="Number of recent editions to fetch")
    ap.add_argument("--db", type=Path, default=ROOT / "data" / "nwz.sqlite")
    ap.add_argument("--force", action="store_true",
                    help="Re-fetch even if already stored at current content_version")
    args = ap.parse_args()

    title_name = TITLES.get(args.folder, f"folder {args.folder}")
    print(f"Title: {title_name} (folder {args.folder})")

    client = from_env()
    store = Store(args.db)

    editions = client.available(args.folder, limit=args.limit)
    print(f"Found {len(editions)} editions, oldest={editions[-1].publication_date}, newest={editions[0].publication_date}")

    for i, e in enumerate(editions, 1):
        if not args.force and store.has_edition(e.catalog, e.content_version):
            print(f"  [{i:2d}/{len(editions)}] {e.publication_date} catalog={e.catalog}  SKIP (already stored)")
            continue
        print(f"  [{i:2d}/{len(editions)}] {e.publication_date} catalog={e.catalog}  fetching...", flush=True)
        xml = client.content_xml(e.catalog)
        meta, articles = parse_publication(xml)
        store.save_edition(e, articles)
        chars = sum(len(a.content_text) for a in articles)
        print(f"      → {len(articles)} articles, {chars:,} chars body text")

    print("\n=== summary ===")
    for date, title, pages, n_art, body in store.edition_summary():
        print(f"  {date}  {title[:50]:<50s}  pages={pages:>3d}  articles={n_art:>3d}  body={body or 0:>8,d}c")


if __name__ == "__main__":
    main()
