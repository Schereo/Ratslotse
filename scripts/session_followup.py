#!/usr/bin/env python3
"""Search NWZ articles for coverage of council sessions that took place recently.

For each past session that users subscribed to, this script:
  1. Extracts keywords from the committee name and agenda items
  2. Searches NWZ articles published in the days after the session
  3. Uses GPT to verify which articles actually cover the session outcome
  4. Sends matching articles to subscribers as a follow-up

Run daily via cron: 0 14 * * * /path/to/.venv/bin/python /path/to/scripts/session_followup.py

The script retries each session until either articles are found or the search
window closes (DAYS_AFTER_SESSION days post-session), then marks it as done.
"""
from __future__ import annotations

import json
import os
import re
import sys
import textwrap
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from nwz.llm import chat_complete
from nwz.store import Store
from nwz.telegram_bot import reply, telegram_ready
from council.store import CouncilStore

NWZ_DB = ROOT / "data" / "nwz.sqlite"
COUNCIL_DB = ROOT / "data" / "council.sqlite"

SESSION_URL_BASE = "https://buergerinfo.oldenburg.de/si0057.php?__ksinr="

# How many days after the session to search for NWZ articles
DAYS_AFTER_SESSION = 4
# Only check sessions that happened between these many days ago
DAYS_MIN = 1
DAYS_MAX = 6

_STOPWORDS = frozenset({
    "ausschuss", "für", "und", "der", "die", "das", "des", "dem", "den",
    "von", "in", "zu", "im", "an", "am", "auf", "bei", "mit", "nach",
    "über", "unter", "vor", "aus", "durch", "gegen", "ohne", "eine",
    "einer", "eines", "einem", "einen", "sitzung", "punkt", "beim",
    "sowie", "auch", "oder", "nicht", "sind", "wird", "wird", "werden",
    "haben", "kann", "vom", "zur", "beim", "wird",
})


def _extract_keywords(committee: str, agenda_items: list[dict]) -> list[str]:
    """Extract meaningful search terms from committee name and agenda item titles."""
    text = committee + " " + " ".join(
        i["title"] for i in agenda_items if i.get("is_public")
    )
    words = re.findall(r'\b[A-Za-zÄÖÜäöüß]{4,}\b', text)
    seen: set[str] = set()
    result: list[str] = []
    for w in words:
        lower = w.lower()
        if lower not in _STOPWORDS and lower not in seen:
            seen.add(lower)
            result.append(w)
    return result[:12]


def _verify_with_gpt(
    session: dict,
    agenda_items: list[dict],
    candidates: list[dict],
) -> list[dict]:
    """Ask GPT which candidate articles report on the outcome of this session."""
    items_text = "\n".join(
        f"  {i['item_number']}: {i['title']}" + (f" [{i['vorlage_nr']}]" if i.get("vorlage_nr") else "")
        for i in agenda_items
        if i.get("is_public")
    ) or "  (keine öffentlichen TOPs)"

    articles_text = "\n\n".join(
        f"[{idx + 1}] refid={a['refid']} ({a.get('pub_date', '')})\n"
        f"Titel: {a.get('title', '')}\n"
        f"Untertitel: {a.get('subtitle', '')}\n"
        f"Text: {(a.get('content_text') or '').replace(chr(10), ' ')}"
        for idx, a in enumerate(candidates)
    )

    d = session["session_date"].split("-")
    display_date = f"{d[2]}.{d[1]}.{d[0]}" if len(d) == 3 else session["session_date"]

    prompt = textwrap.dedent(f"""\
        Folgende Stadtratssitzung hat stattgefunden:
        Ausschuss: {session["committee"]}
        Datum: {display_date}

        Tagesordnung:
        {items_text}

        Hier sind NWZ-Artikel aus den Tagen nach dieser Sitzung:

        {articles_text}

        Aufgabe: Welche Artikel berichten über Ergebnisse, Beschlüsse oder Reaktionen
        zu dieser Sitzung oder ihren Tagesordnungspunkten?
        Schreibe für jeden passenden Artikel 1–2 Sätze Zusammenfassung was beschlossen
        oder berichtet wurde.

        Format:
        {{
          "articles": [
            {{"refid": "...", "summary": "Was wurde beschlossen/berichtet."}}
          ]
        }}

        Leere Liste wenn kein Artikel zur Sitzung passt. Nur JSON.
    """)

    resp = chat_complete(
        model="openai/gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
        max_tokens=512,
    )
    data = json.loads(resp.choices[0].message.content)

    refid_to_article = {a["refid"]: a for a in candidates}
    result = []
    for item in data.get("articles", []):
        refid = item.get("refid", "")
        if refid in refid_to_article:
            art = dict(refid_to_article[refid])
            art["gpt_summary"] = item.get("summary", "")
            result.append(art)
    return result


def _esc(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _format_message(session: dict, articles: list[dict]) -> str:
    d = session["session_date"].split("-")
    display_date = f"{d[2]}.{d[1]}.{d[0]}" if len(d) == 3 else session["session_date"]
    session_url = f"{SESSION_URL_BASE}{session['ksinr']}"

    lines = [
        f"📋 <b>Nachbericht: {_esc(session['committee'])}</b>",
        f"Sitzung vom {display_date}\n",
    ]
    for a in articles:
        lines.append(f"• <b>{_esc(a.get('title', ''))}</b>")
        lines.append(f"  {_esc(a.get('gpt_summary', ''))}")
    lines.append("")
    lines.append(f'<a href="{session_url}">Zur Sitzungsseite →</a>')
    return "\n".join(lines)


def main() -> None:
    today = date.today()
    date_from = (today - timedelta(days=DAYS_MAX)).isoformat()
    date_to = (today - timedelta(days=DAYS_MIN)).isoformat()

    nwz_store = Store(NWZ_DB)
    council_store = CouncilStore(COUNCIL_DB)
    all_subs = nwz_store.get_all_subscriptions()

    if not all_subs:
        print("No committee subscriptions found.")
        nwz_store.close()
        council_store.close()
        return

    sessions = council_store.past_sessions_in_window(date_from, date_to)
    print(f"Found {len(sessions)} session(s) in window {date_from} – {date_to}.")

    followups_sent = 0

    for session in sessions:
        ksinr = session["ksinr"]

        pending = [
            chat_id for chat_id, names in all_subs.items()
            if session["committee"] in names
            and not council_store.followup_already_sent(ksinr, chat_id)
        ]
        if not pending:
            continue

        agenda_items = council_store.agenda_items(ksinr)
        if not agenda_items:
            print(f"  {session['session_date']} {session['committee']}: no agenda items, skipping.")
            continue

        keywords = _extract_keywords(session["committee"], agenda_items)
        if not keywords:
            print(f"  {session['session_date']} {session['committee']}: no keywords extracted.")
            continue

        article_date_from = session["session_date"]
        article_date_to = (
            date.fromisoformat(session["session_date"]) + timedelta(days=DAYS_AFTER_SESSION)
        ).isoformat()

        print(f"  {session['session_date']} {session['committee']}: searching '{' OR '.join(keywords[:4])}…'")
        candidates = nwz_store.search_any_terms(
            keywords, date_from=article_date_from, date_to=article_date_to, limit=20
        )

        if not candidates:
            window_closed = today > date.fromisoformat(article_date_to)
            if window_closed:
                print(f"    No articles found, window closed — marking done.")
                for chat_id in pending:
                    council_store.mark_followup_sent(ksinr, chat_id)
            else:
                print(f"    No articles yet, will retry tomorrow.")
            continue

        print(f"    {len(candidates)} candidate(s) found, verifying with GPT…")
        matches = _verify_with_gpt(session, agenda_items, candidates)

        if not matches:
            window_closed = today > date.fromisoformat(article_date_to)
            if window_closed:
                print(f"    GPT: no relevant articles, window closed — marking done.")
                for chat_id in pending:
                    council_store.mark_followup_sent(ksinr, chat_id)
            else:
                print(f"    GPT: no relevant articles yet, will retry tomorrow.")
            continue

        print(f"    {len(matches)} relevant article(s) — sending to {len(pending)} user(s).")
        message = _format_message(session, matches)

        for chat_id in pending:
            if telegram_ready():
                reply(chat_id, message)
            council_store.mark_followup_sent(ksinr, chat_id)
            followups_sent += 1

    nwz_store.close()
    council_store.close()
    print(f"Done — {followups_sent} follow-up notification(s) sent.")


if __name__ == "__main__":
    main()
