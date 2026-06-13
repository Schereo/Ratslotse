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
from nwz.telegram_bot import reply, telegram_ready

DB = ROOT / "data" / "nwz.sqlite"


def main() -> None:
    store = Store(DB)
    all_user_topics = store.get_all_user_topics()
    if not all_user_topics:
        print("No topics saved — nothing to do.")
        return

    today = date.today()
    date_to = today.isoformat()
    date_from = (today - timedelta(days=6)).isoformat()
    print(f"Weekly digest for {date_from} – {date_to}")

    all_articles = store.articles_in_range(date_from, date_to)
    print(f"  {len(all_articles)} total NWZ articles in range for highlights.")

    for chat_id in all_user_topics:
        matches = store.get_weekly_matches(chat_id, date_from, date_to)
        if not matches:
            print(f"  User {chat_id}: no matches this week, skipping.")
            continue

        print(f"  User {chat_id}: {len(matches)} match(es) — building digest…")
        msg = build_weekly_digest(matches, date_from, date_to, all_articles=all_articles)
        if not msg:
            print(f"  User {chat_id}: empty digest, skipping.")
            continue

        if telegram_ready():
            reply(chat_id, msg)
            print(f"  User {chat_id}: sent.")
        else:
            print("Telegram not configured (set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID in .env).")


if __name__ == "__main__":
    main()
