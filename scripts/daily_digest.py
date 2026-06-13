#!/usr/bin/env python3
"""Fetch today's NWZ, classify by each user's topics, send personalised Telegram digests.
Run daily via cron: 30 6 * * * /path/to/.venv/bin/python /path/to/scripts/daily_digest.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from nwz.api import from_env
from nwz.parse import parse_publication
from nwz.store import Store
from nwz.classify import build_digest
from nwz.telegram_bot import reply, telegram_ready

FOLDER = 8389  # Oldenburger Nachrichten
DB = ROOT / "data" / "nwz.sqlite"


def main() -> None:
    client = from_env()
    store = Store(DB)

    all_user_topics = store.get_all_user_topics()
    if not all_user_topics:
        print("No topics saved for any user — nothing to do.")
        return

    editions = client.available(FOLDER, limit=1)
    if not editions:
        print("No edition available.")
        return

    ed = editions[0]
    today = date.today().isoformat()
    if ed.publication_date != today:
        print(f"Latest edition is {ed.publication_date}, not today ({today}).")

    if not store.has_edition(ed.catalog, ed.content_version):
        print(f"Fetching {ed.publication_date} catalog={ed.catalog}...")
        xml = client.content_xml(ed.catalog)
        _, articles = parse_publication(xml)
        store.save_edition(ed, articles)
        print(f"Stored {len(articles)} articles.")

    articles = store.articles_for_date(ed.publication_date)
    print(f"Got {len(articles)} articles for {ed.publication_date}.")

    for chat_id, topics in all_user_topics.items():
        topic_dicts = [{"id": t.id, "name": t.name, "description": t.description} for t in topics]
        print(f"  User {chat_id}: classifying against {len(topics)} topic(s)...")
        digest, matches = build_digest(articles, topic_dicts, ed.publication_date)
        store.save_article_matches(chat_id, matches)
        for t in topics:
            store.mark_edition_classified(chat_id, t.id, ed.publication_date)
        if telegram_ready():
            if digest:
                reply(chat_id, digest)
                print(f"  User {chat_id}: digest sent ({len(matches)} match(es) stored).")
            else:
                topic_names = ", ".join(t.name for t in topics)
                reply(chat_id, f"📰 <b>NWZ Digest – {ed.publication_date}</b>\n\nHeute keine Artikel zu deinen Themen gefunden:\n<i>{topic_names}</i>")
                print(f"  User {chat_id}: no matches, notification sent.")
        else:
            print("Telegram not configured (set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID in .env).")


if __name__ == "__main__":
    main()
