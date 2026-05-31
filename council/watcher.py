from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path
from typing import Any

from openai import OpenAI

from .scraper import CouncilScraper, CouncilSession
from .store import CouncilStore

BASE_URL = "https://buergerinfo.oldenburg.de"
MODEL = "gpt-4o"
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client


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

    system = textwrap.dedent("""\
        Du analysierst Tagesordnungspunkte (TOP) der Oldenburger Stadtratssitzungen
        und ordnest sie den Interessengebieten des Nutzers zu.
        Antworte ausschließlich als JSON.
    """)

    prompt = textwrap.dedent(f"""\
        Sitzung: {session.committee}, {session.session_date}

        Öffentliche Tagesordnungspunkte:
        {items_text}

        Themen des Nutzers:
        {topics_text}

        Gib für jedes Thema an, welche TOP-Nummern passen (leer wenn keiner passt).
        Format:
        {{
          "matches": [
            {{"topic_index": 1, "item_numbers": ["Ö 6.1", "Ö 6.2"]}},
            {{"topic_index": 2, "item_numbers": []}}
          ]
        }}
    """)

    resp = _get_client().chat.completions.create(
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


def run_watcher(
    db_path: str | Path,
    topics: list[dict],
    months_ahead: int = 3,
    chat_id: int | str | None = None,
) -> list[str]:
    """
    Scrape upcoming sessions, classify new ones against topics, send alerts.
    Returns list of alert messages sent.
    topics: [{"id": int, "name": str, "description": str}]
    chat_id: Telegram chat to send alerts to; defaults to TELEGRAM_CHAT_ID env var.
    """
    import os
    from nwz.telegram_bot import reply, telegram_ready

    if chat_id is None:
        chat_id = int(os.environ.get("TELEGRAM_CHAT_ID", 0))

    scraper = CouncilScraper()
    store = CouncilStore(db_path)

    print("Scanning council calendar…")
    session_ids = scraper.upcoming_session_ids(months_ahead=months_ahead)
    print(f"  Found {len(session_ids)} sessions in next {months_ahead} months")

    alerts_sent: list[str] = []

    for ksinr in session_ids:
        already_has_agenda = store.has_session_with_agenda(ksinr)

        session = scraper.fetch_session(ksinr)
        if not session:
            continue

        store.save_session(session)

        # Only classify future sessions with newly discovered agendas
        if already_has_agenda:
            continue
        if not session.is_future:
            continue
        if not session.agenda_items:
            print(f"  {session.session_date} {session.committee}: no agenda yet, skipping")
            continue

        print(f"  {session.session_date} {session.committee}: {len(session.agenda_items)} items → classifying…")
        matches = _classify_agenda(session, topics)

        for topic_idx, item_numbers in matches.items():
            topic_id = topics[topic_idx]["id"]
            if store.alert_already_sent(ksinr, topic_id):
                continue
            msg = _format_alert(session, {topic_idx: item_numbers}, topics)
            print(f"    Match: topic={topics[topic_idx]['name']!r} items={item_numbers}")
            if telegram_ready():
                reply(chat_id, msg)
            alerts_sent.append(msg)
            store.mark_alert_sent(ksinr, topic_id)

    store.close()
    return alerts_sent
