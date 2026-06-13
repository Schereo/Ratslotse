#!/usr/bin/env python3
"""Send committee meeting summaries to subscribed users.
Run daily via cron: 0 7 * * *
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from nwz.store import Store
from nwz.telegram_bot import reply
from council.store import CouncilStore
from council.scraper import CouncilScraper
from council.committee_summary import summarize_agenda

NWZ_DB = ROOT / "data" / "nwz.sqlite"
COUNCIL_DB = ROOT / "data" / "council.sqlite"


def main() -> None:
    nwz_store = Store(NWZ_DB)
    all_subs = nwz_store.get_all_subscriptions()
    nwz_store.close()

    if not all_subs:
        print("No subscriptions found, nothing to do.")
        return

    council_store = CouncilStore(COUNCIL_DB)
    scraper = CouncilScraper()

    print("Refreshing committee list from Gremienübersicht…")
    committees = scraper.fetch_committee_list()
    council_store.save_committees(committees)
    print(f"  Saved {len(committees)} committees")

    print("Scanning upcoming council sessions…")
    session_ids = scraper.upcoming_session_ids(months_ahead=3)
    print(f"  Found {len(session_ids)} sessions")

    notifications_sent = 0

    for ksinr in session_ids:
        session = scraper.fetch_session(ksinr)
        if not session:
            continue

        council_store.save_session(session)

        if not session.is_future or not session.agenda_items:
            continue

        # Find users subscribed to this committee
        interested = [
            chat_id
            for chat_id, names in all_subs.items()
            if session.committee in names
        ]
        if not interested:
            continue

        for chat_id in interested:
            if council_store.was_notified(ksinr, chat_id):
                continue

            print(f"  {session.session_date} {session.committee} → user {chat_id}")
            summary = summarize_agenda(
                committee=session.committee,
                session_date=session.session_date,
                session_time=session.session_time,
                location=session.location,
                agenda_items=session.agenda_items,
                session_url=session.url,
            )

            if summary:
                reply(chat_id, summary)
            else:
                fallback = (
                    f"<b>{session.committee}</b>\n"
                    f"📅 {session.session_date}  {session.session_time} Uhr\n\n"
                    f"Tagesordnung enthält nur Routine-TOPs.\n"
                    f'<a href="{session.url}">Tagesordnung →</a>'
                )
                reply(chat_id, fallback)

            council_store.mark_notified(ksinr, chat_id)
            notifications_sent += 1

    council_store.close()
    print(f"Done — {notifications_sent} notification(s) sent.")


if __name__ == "__main__":
    main()
