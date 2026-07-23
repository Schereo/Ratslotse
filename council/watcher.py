from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nwz import llm, prompts
from .scraper import CouncilScraper, CouncilSession
from .store import CouncilStore

BASE_URL = "https://buergerinfo.oldenburg.de"
MODEL = "openai/gpt-4o-mini"


def _classify_agenda(session: CouncilSession, topics: list[dict]) -> dict[int, list[str]]:
    """
    Returns {topic_id: [item_numbers_matched]}.
    Only called for future sessions with agenda items.
    """
    if not session.agenda_items or not topics:
        return {}

    items_text = "\n".join(
        f"{i.item_number}: {i.title}" + (f" [{i.vorlage_nr}]" if i.vorlage_nr else "")
        for i in session.agenda_items
        if i.is_public
    )
    topics_text = "\n".join(
        f"{idx + 1}. {t['name']}: {t['description']}"
        for idx, t in enumerate(topics)
    )

    system = prompts.get("council_watcher_system")
    prompt = prompts.render(
        "council_watcher_user",
        committee=session.committee,
        session_date=session.session_date,
        items_text=items_text,
        topics_text=topics_text,
    )

    resp = llm.chat_complete(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        max_tokens=512,
    )
    data = json.loads(resp.choices[0].message.content)

    result: dict[int, list[str]] = {}
    for m in data.get("matches", []):
        idx = m.get("topic_index", 0) - 1
        nums = m.get("item_numbers", [])
        if 0 <= idx < len(topics) and nums:
            result[idx] = nums
    return result


def _format_alert(session: CouncilSession, topic_matches: dict[int, list[str]], topics: list[dict]) -> str:
    item_map = {i.item_number: i for i in session.agenda_items}
    parts = [
        "🏛️ <b>Stadtratssitzung – Ihr Thema wird diskutiert</b>\n",
        f"<b>{_esc(session.committee)}</b>",
        f"📅 {session.session_date.replace('-', '.')} · {session.session_time} Uhr",
    ]
    if session.location:
        parts.append(f"📍 {_esc(session.location)}")
    parts.append("")

    for topic_idx, item_numbers in topic_matches.items():
        topic = topics[topic_idx]
        parts.append(f"📌 <b>{_esc(topic['name'])}</b>")
        for num in item_numbers:
            item = item_map.get(num)
            title = item.title if item else num
            vorlage = f" [{_esc(item.vorlage_nr)}]" if item and item.vorlage_nr else ""
            parts.append(f"• {_esc(num)}: {_esc(title)}{vorlage}")
        parts.append("")

    parts.append(f'<a href="{session.url}">Zur Tagesordnung →</a>')
    return "\n".join(parts)


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _agenda_hash(agenda_items) -> str:
    """Stabiler Fingerabdruck der Tagesordnung — ändert sich, sobald ein TOP
    hinzukommt, wegfällt oder umformuliert wird."""
    import hashlib

    payload = "\n".join(
        f"{i.item_number}\t{i.title}\t{i.vorlage_nr or ''}\t{int(i.is_public)}"
        for i in agenda_items
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_watcher(
    db_path: str | Path,
    owners: list[dict],
    months_ahead: int = 3,
    nwz_store=None,
    stats: dict | None = None,
) -> list[str]:
    """
    Scrape upcoming sessions once, classify their agendas per owner, persist
    the matches (RL-902) and send alerts. Returns the alert messages sent.

    owners: get_all_owner_digests()-Zeilen — je {owner_id, topics: [TopicRow],
            delivery_channel, email, push_tokens}.
    nwz_store: offener nwz.store.Store für die Treffer-Persistenz; ohne ihn
            (Tests) wird klassifiziert und alarmiert, aber nichts gemerkt —
            dann läuft die Klassifikation beim nächsten Mal erneut.
    stats: optionales dict, in das der Lauf seine Kennzahlen schreibt (für die
            Cron-Übersicht im Admin-Panel).
    """
    from nwz.delivery import deliver_message

    scraper = CouncilScraper()
    store = CouncilStore(db_path)

    print("Scanning council calendar…")
    session_ids, scheduled = scraper.upcoming_calendar(months_ahead=months_ahead)
    # Terminplan mitschreiben: Sitzungen ohne veröffentlichte Tagesordnung
    # haben noch keinen ksinr, sollen aber in der App schon sichtbar sein.
    store.replace_scheduled_sessions(scheduled)
    print(f"  Found {len(session_ids)} sessions with agenda, {len(scheduled)} scheduled dates")
    if stats is not None:
        stats["Sitzungen mit Tagesordnung"] = len(session_ids)
        stats["Termine im Kalender"] = len(scheduled)

    alerts_sent: list[str] = []

    for ksinr in session_ids:
        session = scraper.fetch_session(ksinr)
        if not session:
            continue

        store.save_session(session)

        # Nur kommende Sitzungen mit Tagesordnung sind für Themen relevant.
        if not session.is_future or not session.agenda_items:
            continue

        agenda_hash = _agenda_hash(session.agenda_items)

        for owner in owners:
            # Je Nutzer:in klassifizieren — aber nur, wenn sich die
            # Tagesordnung seit ihrer letzten Klassifikation geändert hat.
            if nwz_store is not None:
                known = nwz_store.agenda_classified_hash(owner["owner_id"], ksinr)
                if known == agenda_hash:
                    continue

            topics = [
                {"id": t.id, "name": t.name, "description": t.description}
                for t in owner["topics"]
            ]
            if not topics:
                continue

            print(f"  {session.session_date} {session.committee}: "
                  f"{len(session.agenda_items)} items → classifying for owner {owner['owner_id']}…")
            matches = _classify_agenda(session, topics)

            if nwz_store is not None:
                nwz_store.replace_agenda_matches(
                    owner["owner_id"], ksinr, agenda_hash,
                    {topics[idx]["id"]: nums for idx, nums in matches.items()},
                )

            for topic_idx, item_numbers in matches.items():
                topic_id = topics[topic_idx]["id"]
                if store.alert_already_sent(ksinr, topic_id):
                    continue
                msg = _format_alert(session, {topic_idx: item_numbers}, topics)
                print(f"    Match: topic={topics[topic_idx]['name']!r} items={item_numbers}")
                deliver_message(owner, msg, email_subject="Ratslotse – Ihr Thema im Stadtrat")
                alerts_sent.append(msg)
                store.mark_alert_sent(ksinr, topic_id)

    store.close()
    return alerts_sent
