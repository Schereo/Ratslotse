#!/usr/bin/env python3
"""Send committee meeting summaries to subscribed users.
Run daily via cron: 0 7 * * *
"""
from __future__ import annotations

import hashlib
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


def _agenda_hash(agenda_items) -> str:
    """Stable fingerprint of the agenda; changes if any item is added/edited/removed."""
    payload = "\n".join(
        f"{i.item_number}\t{i.title}\t{i.vorlage_nr or ''}\t{int(i.is_public)}"
        for i in agenda_items
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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

        # Compute agenda hash once; drives both caching and change detection.
        agenda_hash = _agenda_hash(session.agenda_items)

        # Categorise subscribers:
        # - pending_new:    never notified before
        # - pending_update: notified before but the agenda has since changed
        # Rows migrated from before hash-tracking have hash==''; treat them as
        # "already notified, skip" to avoid a one-off spurious update blast.
        pending_new: list[int] = []
        pending_update: list[int] = []
        for chat_id, names in all_subs.items():
            if session.committee not in names:
                continue
            last_hash = council_store.get_last_notified_hash(ksinr, chat_id)
            if last_hash is None:
                pending_new.append(chat_id)
            elif last_hash and last_hash != agenda_hash:
                pending_update.append(chat_id)

        if not pending_new and not pending_update:
            continue

        # The summary depends only on the session — compute once and cache.
        # A cached '' means "only routine TOPs" (still a valid cache hit).
        summary = council_store.get_cached_summary(ksinr, agenda_hash)
        if summary is None:
            summary = summarize_agenda(
                committee=session.committee,
                session_date=session.session_date,
                session_time=session.session_time,
                location=session.location,
                agenda_items=session.agenda_items,
                session_url=session.url,
            )
            council_store.save_summary(ksinr, agenda_hash, summary)

        base_message = summary or (
            f"<b>{session.committee}</b>\n"
            f"📅 {session.session_date}  {session.session_time} Uhr\n\n"
            f"Tagesordnung enthält nur Routine-TOPs.\n"
            f'<a href="{session.url}">Tagesordnung →</a>'
        )

        for chat_id in pending_new:
            print(f"  {session.session_date} {session.committee} → user {chat_id} (neu)")
            reply(chat_id, base_message)
            council_store.mark_notified(ksinr, chat_id, agenda_hash)
            notifications_sent += 1

        update_prefix = "🔄 <b>Tagesordnung wurde aktualisiert</b>\n\n"
        for chat_id in pending_update:
            print(f"  {session.session_date} {session.committee} → user {chat_id} (Änderung)")
            reply(chat_id, update_prefix + base_message)
            council_store.mark_notified(ksinr, chat_id, agenda_hash)
            notifications_sent += 1

    council_store.close()
    print(f"Done — {notifications_sent} notification(s) sent.")


if __name__ == "__main__":
    main()
