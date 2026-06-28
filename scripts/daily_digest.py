#!/usr/bin/env python3
"""Fetch today's NWZ, classify by each user's topics, send personalised Telegram digests.
Run daily via cron: 30 6 * * * /path/to/.venv/bin/python /path/to/scripts/daily_digest.py
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from nwz.api import NWZClient, from_env
from nwz.parse import parse_publication
from nwz.store import Store
from nwz.classify import build_digest
from nwz.delivery import deliver_digest

FOLDER = 8389  # Oldenburger Nachrichten
DB = ROOT / "data" / "nwz.sqlite"
BACKFILL_LOOKBACK = 14  # days
CONTINUATION_LOOKBACK = 5  # days for Doppelstory-Erkennung


def _backfill_missing(client: NWZClient, store: Store, folder: int) -> None:
    """Fetch and store any editions from the last BACKFILL_LOOKBACK days missing from the DB."""
    recent_editions = client.available(folder, limit=BACKFILL_LOOKBACK)
    stored_dates = set(store.edition_dates())
    missing = [e for e in recent_editions if e.publication_date not in stored_dates]
    if not missing:
        return
    print(f"Backfilling {len(missing)} missing edition(s)…")
    for e in missing:
        print(f"  Fetching {e.publication_date} catalog={e.catalog}…", flush=True)
        xml = client.content_xml(e.catalog)
        _, articles = parse_publication(xml)
        store.save_edition(e, articles)
        print(f"  → {len(articles)} articles stored.")


def main() -> None:
    client = from_env()
    store = Store(DB)

    owner_digests = store.get_all_owner_digests()
    if not owner_digests:
        print("No topics saved for any owner — nothing to do.")
        return

    _backfill_missing(client, store, FOLDER)

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

    cutoff = (date.today() - timedelta(days=CONTINUATION_LOOKBACK)).isoformat()

    for owner in owner_digests:
        owner_id = owner["owner_id"]
        topics = owner["topics"]
        # Build recent context for Doppelstory-Erkennung
        recent_context: dict[str, list[str]] = {}
        for t in topics:
            recent = store.get_article_matches(owner_id, t.id, limit=20)
            titles = [m["title"] for m in recent
                      if cutoff <= m["pub_date"] < ed.publication_date]
            if titles:
                recent_context[t.name] = titles

        topic_dicts = [{"id": t.id, "name": t.name, "description": t.description} for t in topics]
        print(f"  Owner {owner_id} ({owner['delivery_channel']}): classifying against {len(topics)} topic(s)...")
        digest, matches = build_digest(
            articles, topic_dicts, ed.publication_date,
            recent_context=recent_context or None,
        )
        refid_to_id = store.save_article_matches(owner_id, matches)
        for t in topics:
            store.mark_edition_classified(owner_id, t.id, ed.publication_date)

        topic_names = ", ".join(t.name for t in topics)
        empty_text = (
            f"📰 <b>NWZ Digest – {ed.publication_date}</b>\n\n"
            f"Heute keine Artikel zu deinen Themen gefunden:\n<i>{topic_names}</i>"
        )
        sent = deliver_digest(
            owner, topics, digest, matches, refid_to_id, ed.publication_date,
            empty_text=empty_text,
        )
        print(f"  Owner {owner_id}: {len(matches)} match(es), delivered via {sent or 'nothing'}.")


if __name__ == "__main__":
    from nwz.alerts import run_guarded
    run_guarded("daily_digest", main)
