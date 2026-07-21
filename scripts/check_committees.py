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
from nwz.delivery import deliver_message
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
    all_subs = nwz_store.get_all_subscriptions()       # {owner_id: [committee_name]}
    targets = nwz_store.get_subscription_targets()     # {owner_id: {channel, chat, email}}
    nwz_store.close()

    # Daten werden auch OHNE Abonnements aktualisiert — die Web-App zeigt
    # Sitzungen und Terminplan für alle Nutzer:innen, nicht nur Abonnenten.
    council_store = CouncilStore(COUNCIL_DB)
    scraper = CouncilScraper()

    print("Refreshing committee list from Gremienübersicht…")
    committees = scraper.fetch_committee_list()
    council_store.save_committees(committees)
    print(f"  Saved {len(committees)} committees")

    print("Scanning upcoming council sessions…")
    session_ids, scheduled = scraper.upcoming_calendar(months_ahead=3)
    # Terminierte Sitzungen ohne veröffentlichte Tagesordnung (kein ksinr im
    # Kalender-HTML) — sonst bleibt ein frisch publizierter Terminplan unsichtbar.
    council_store.replace_scheduled_sessions(scheduled)
    print(f"  Found {len(session_ids)} sessions with agenda, {len(scheduled)} scheduled dates")

    notifications_sent = 0

    for ksinr in session_ids:
        session = scraper.fetch_session(ksinr)
        if not session:
            continue

        council_store.save_session(session)

        if not all_subs:
            continue
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
        for owner_id, names in all_subs.items():
            if session.committee not in names:
                continue
            last_hash = council_store.get_last_notified_hash(ksinr, owner_id)
            if last_hash is None:
                pending_new.append(owner_id)
            elif last_hash and last_hash != agenda_hash:
                pending_update.append(owner_id)

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
            # None = LLM-Antwort unbrauchbar → NICHT cachen (sonst stünde für
            # diese Tagesordnung dauerhaft eine falsche Aussage fest); die
            # Benachrichtigung geht trotzdem raus, nur ohne Zusammenfassung.
            if summary is not None:
                council_store.save_summary(ksinr, agenda_hash, summary)

        if summary:
            base_message = summary
        elif summary == "":
            base_message = (
                f"<b>{session.committee}</b>\n"
                f"📅 {session.session_date}  {session.session_time} Uhr\n\n"
                f"Tagesordnung enthält nur Routine-TOPs.\n"
                f'<a href="{session.url}">Tagesordnung →</a>'
            )
        else:  # Zusammenfassung fehlgeschlagen — nichts behaupten, nur verlinken.
            base_message = (
                f"<b>{session.committee}</b>\n"
                f"📅 {session.session_date}  {session.session_time} Uhr\n\n"
                f'<a href="{session.url}">Tagesordnung →</a>'
            )

        subject = f"Ratslotse – {session.committee}"
        for owner_id in pending_new:
            target = targets.get(owner_id)
            if not target:
                continue
            print(f"  {session.session_date} {session.committee} → owner {owner_id} (neu)")
            deliver_message(target, base_message, email_subject=subject)
            council_store.mark_notified(ksinr, owner_id, agenda_hash)
            notifications_sent += 1

        update_prefix = "🔄 <b>Tagesordnung wurde aktualisiert</b>\n\n"
        for owner_id in pending_update:
            target = targets.get(owner_id)
            if not target:
                continue
            print(f"  {session.session_date} {session.committee} → owner {owner_id} (Änderung)")
            deliver_message(target, update_prefix + base_message, email_subject=subject)
            council_store.mark_notified(ksinr, owner_id, agenda_hash)
            notifications_sent += 1

    council_store.close()
    print(f"Done — {notifications_sent} notification(s) sent.")


if __name__ == "__main__":
    from nwz.alerts import run_guarded
    run_guarded("check_committees", main)
