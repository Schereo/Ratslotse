#!/usr/bin/env python3
"""Backfill: classify the last 30 days of NWZ articles against all users' topics.

Run once after deploying the article archive feature:
    .venv/bin/python scripts/classify_archive.py

Already-classified (chat_id, topic_id, pub_date) triples are skipped, so
the script is safe to re-run or interrupt and resume.
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
from nwz.classify import build_digest

DB = ROOT / "data" / "nwz.sqlite"
LOOKBACK_DAYS = 30


def main() -> None:
    store = Store(DB)
    cutoff = (date.today() - timedelta(days=LOOKBACK_DAYS)).isoformat()

    all_user_topics = store.get_all_user_topics()
    if not all_user_topics:
        print("No users/topics found.")
        return

    all_dates = [d for d in store.edition_dates() if d >= cutoff]
    if not all_dates:
        print(f"No editions stored for the last {LOOKBACK_DAYS} days.")
        return

    print(f"Found {len(all_dates)} edition(s) from {all_dates[-1]} to {all_dates[0]}.")
    print(f"Processing {len(all_user_topics)} user(s).\n")

    total_calls = 0
    total_matches = 0

    for chat_id, topics in all_user_topics.items():
        print(f"User {chat_id} — {len(topics)} topic(s)")
        for topic in topics:
            already_classified = store.classified_pub_dates_for_topic(chat_id, topic.id)
            pending = [d for d in all_dates if d not in already_classified]
            if not pending:
                print(f"  [{topic.id}] {topic.name}: already fully classified, skipping.")
                continue

            print(f"  [{topic.id}] {topic.name}: classifying {len(pending)} edition(s)…")
            topic_dict = [{"id": topic.id, "name": topic.name, "description": topic.description}]

            for pub_date in pending:
                articles = store.articles_for_date(pub_date)
                store.mark_edition_classified(chat_id, topic.id, pub_date)
                if not articles:
                    continue
                _, matches = build_digest(articles, topic_dict, pub_date)
                store.save_article_matches(chat_id, matches)
                total_calls += 1
                total_matches += len(matches)
                if matches:
                    print(f"    {pub_date}: {len(matches)} match(es)")

    store.close()
    print(f"\nDone — {total_calls} GPT call(s), {total_matches} match(es) stored.")


if __name__ == "__main__":
    main()
