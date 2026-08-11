#!/usr/bin/env python3
"""Send committee meeting summaries to subscribed users.
Run daily via cron: 0 7 * * *
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from nwz import notify
from nwz.store import Store
from nwz import digest_email
from council.store import CouncilStore
from council.scraper import CouncilScraper
from council.committee_summary import sitzungskopf, summarize_agenda
from council.ergebnisse import sitzung_href

NWZ_DB = ROOT / "data" / "nwz.sqlite"
COUNCIL_DB = ROOT / "data" / "council.sqlite"


def _agenda_hash(agenda_items) -> str:
    """Stable fingerprint of the agenda; changes if any item is added/edited/removed."""
    payload = "\n".join(
        f"{i.item_number}\t{i.title}\t{i.vorlage_nr or ''}\t{int(i.is_public)}"
        for i in agenda_items
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _stunden_bis(session_date: str, session_time: str) -> float:
    """Stunden von jetzt bis zum Sitzungsbeginn — negativ, wenn sie vorbei ist.

    Für das 48-Stunden-Fenster der Änderungsmeldung (Design 30a). Ohne
    brauchbare Zeitangabe zählt 18 Uhr; Ratssitzungen beginnen abends, und die
    Entscheidung „noch melden oder nicht" verträgt die Unschärfe.
    """
    from datetime import datetime

    try:
        tag = datetime.strptime(str(session_date)[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return 0.0  # unbekanntes Datum → wie „steht kurz bevor" behandeln
    stunde, minute = 18, 0
    try:
        stunde, minute = (int(x) for x in str(session_time or "")[:5].split(":"))
    except ValueError:
        pass
    beginn = tag.replace(hour=stunde, minute=minute)
    return (beginn - datetime.now()).total_seconds() / 3600


_ALT_LINK = re.compile(r"\s*<a href=\"[^\"]*si0057[^\"]*\">[^<]*</a>\s*$")
_ALT_KOPF = re.compile(r"\A<b>[^<]*</b>\n📅[^\n]*\n(?:📍[^\n]*\n)?\n")


def _ohne_altlink(summary: str | None) -> str | None:
    """Gecachte Zusammenfassungen aus der Zeit, als `summarize_agenda` den
    Ratsinfo-Link selbst anhängte. Ohne diesen Schnitt stünden in der Mail zwei
    Wege zur Tagesordnung — der alte im Text, der neue als Knopf darunter.
    Neu erzeugte Zusammenfassungen enthalten den Link nicht mehr, der Ausdruck
    trifft dann einfach nichts."""
    return summary if summary is None else _ALT_LINK.sub("", summary)


def _ohne_altkopf(summary: str | None) -> str | None:
    """Dasselbe für den Kopf, den `summarize_agenda` früher mitcachte.

    In diesen Altbeständen steckt eine Ortsmarke ohne Ort (der Ort fehlte in
    den Sitzungsdaten). Der Kopf kommt jetzt frisch vom Aufrufer — der alte
    muss also weg, sonst stünde er zweimal in der Mail, einmal davon falsch.
    """
    return summary if summary is None else _ALT_KOPF.sub("", summary)


def main() -> dict:
    """Gibt die Kennzahlen des Laufs für die Cron-Übersicht zurück."""
    nwz_store = Store(NWZ_DB)
    all_subs = nwz_store.get_all_subscriptions()       # {owner_id: [committee_name]}
    targets = nwz_store.get_subscription_targets()     # {owner_id: {channel, chat, email}}

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
        # Design 30a: Eine Änderungsmeldung lohnt nur kurz vor der Sitzung.
        # Ändert sich eine Tagesordnung drei Wochen vorher, ist das Verwaltung,
        # keine Nachricht — und für die Betroffenen nur eine Störung mehr.
        nah_dran = _stunden_bis(session.session_date, session.session_time) <= 48
        for owner_id, names in all_subs.items():
            if session.committee not in names:
                continue
            # „Themen-Treffer gewinnt": Wer für diese Sitzung schon weiß, welcher
            # TOP ihn betrifft (aus check_council), braucht die Gremien-Meldung
            # nicht zusätzlich.
            if nwz_store.has_agenda_match(owner_id, ksinr):
                continue
            last_hash = council_store.get_last_notified_hash(ksinr, owner_id)
            if last_hash is None:
                pending_new.append(owner_id)
            elif last_hash and last_hash != agenda_hash and nah_dran:
                pending_update.append(owner_id)

        if not pending_new and not pending_update:
            continue

        # The summary depends only on the session — compute once and cache.
        # A cached '' means "only routine TOPs" (still a valid cache hit).
        summary = _ohne_altkopf(_ohne_altlink(council_store.get_cached_summary(ksinr, agenda_hash)))
        if summary is None:
            try:
                summary = summarize_agenda(
                    committee=session.committee,
                    session_date=session.session_date,
                    agenda_items=session.agenda_items,
                )
            except Exception as exc:  # noqa: BLE001
                # Ein LLM-Fehler bei EINER Sitzung (Provider-Content-Filter, ein
                # unretrybarer API-Fehler, kaputte Antwort) darf nicht den ganzen
                # Lauf für alle Konten abbrechen. summary=None ist ein gültiger
                # Zustand: Die Benachrichtigung geht dann ohne Zusammenfassung
                # raus (nur mit Link), und die nächste Runde versucht es erneut.
                print(f"  ⚠️ summarize_agenda fehlgeschlagen für {session.committee} "
                      f"am {session.session_date}: {exc!r} — Meldung geht ohne Zusammenfassung raus")
                summary = None
            # None = LLM-Antwort unbrauchbar → NICHT cachen (sonst stünde für
            # diese Tagesordnung dauerhaft eine falsche Aussage fest); die
            # Benachrichtigung geht trotzdem raus, nur ohne Zusammenfassung.
            if summary is not None:
                council_store.save_summary(ksinr, agenda_hash, summary)

        # Der Weg zurück in die App ist derselbe, egal ob die Zusammenfassung
        # geklappt hat: Knopf auf die Sitzung, Ratsinfo als leiser Nebenlink.
        wege = (digest_email.knopf(sitzung_href(ksinr), "Tagesordnung ansehen")
                + digest_email.nebenlink(session.url, "Im Ratsinformationssystem öffnen"))
        # Ein Kopf für alle drei Fälle, aus frischen Sitzungsdaten — vorher gab
        # es zwei: einen aus der Zusammenfassung (mit deutschem Datum) und
        # einen hier (mit ISO-Datum), je nachdem, ob das LLM geliefert hatte.
        kopf = sitzungskopf(session.committee, session.session_date,
                            session.session_time, session.location)

        if summary:
            base_message = kopf + "\n\n" + summary + wege
        elif summary == "":
            base_message = kopf + "<p>Die Tagesordnung enthält nur Routine-Punkte.</p>" + wege
        else:  # Zusammenfassung fehlgeschlagen — nichts behaupten, nur verlinken.
            base_message = kopf + wege

        subject = f"{session.committee}: Tagesordnung ist da"
        for owner_id in pending_new:
            if owner_id not in targets:
                continue
            print(f"  {session.session_date} {session.committee} → owner {owner_id} (neu)")
            notify.einreihen(nwz_store, owner_id, notify.N1_TAGESORDNUNG,
                             subject, base_message, sitzung_href(ksinr))
            council_store.mark_notified(ksinr, owner_id, agenda_hash)
            notifications_sent += 1

        update_prefix = "<p><b>Die Tagesordnung hat sich geändert.</b></p>\n"
        update_subject = f"{session.committee}: Tagesordnung geändert"
        for owner_id in pending_update:
            if owner_id not in targets:
                continue
            print(f"  {session.session_date} {session.committee} → owner {owner_id} (Änderung)")
            notify.einreihen(nwz_store, owner_id, notify.N1_TAGESORDNUNG,
                             update_subject, update_prefix + base_message, sitzung_href(ksinr))
            council_store.mark_notified(ksinr, owner_id, agenda_hash)
            notifications_sent += 1

    council_store.close()

    # Der 7-Uhr-Lauf ist zugleich der Wecker der Warteschlange: Was über Nacht
    # anfiel (Nachtruhe 21–7), geht jetzt raus.
    stats: dict = {}
    zugestellt = notify.zustellen(nwz_store, stats=stats)
    nwz_store.close()

    print(f"Done — {notifications_sent} Meldung(en) eingereiht, {zugestellt} zugestellt.")
    return {
        "Gremien": len(committees),
        "Sitzungen mit Tagesordnung": len(session_ids),
        "Termine im Kalender": len(scheduled),
        "Benachrichtigungen": notifications_sent,
        **stats,
    }


if __name__ == "__main__":
    from nwz.alerts import run_guarded
    run_guarded("check_committees", main)
