#!/usr/bin/env python3
"""Send a weekly NWZ digest with highlights to every user.
Run every Friday via cron: 0 17 * * 5 /path/to/.venv/bin/python /path/to/scripts/weekly_digest.py
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from nwz.store import Store
from nwz.classify import build_weekly_digest
from nwz.delivery import deliver_message

DB = ROOT / "data" / "nwz.sqlite"


def main() -> None:
    store = Store(DB)
    owner_digests = store.get_all_owner_digests()
    if not owner_digests:
        print("No topics saved — nothing to do.")
        return

    today = date.today()
    date_to = today.isoformat()
    date_from = (today - timedelta(days=6)).isoformat()
    print(f"Weekly digest for {date_from} – {date_to}")

    all_articles = store.articles_in_range(date_from, date_to)
    print(f"  {len(all_articles)} total NWZ articles in range for highlights.")

    for owner in owner_digests:
        owner_id = owner["owner_id"]
        matches = store.get_weekly_matches(owner_id, date_from, date_to)
        if not matches:
            print(f"  Owner {owner_id}: no matches this week, skipping.")
            continue

        print(f"  Owner {owner_id}: {len(matches)} match(es) — building digest…")
        msg = build_weekly_digest(matches, date_from, date_to, all_articles=all_articles)
        if not msg:
            print(f"  Owner {owner_id}: empty digest, skipping.")
            continue

        sent = deliver_message(owner, msg, email_subject=f"Ratslotse – Wochenrückblick {date_from} – {date_to}")
        print(f"  Owner {owner_id}: delivered via {sent or 'nothing'}.")


if __name__ == "__main__":
    main()
