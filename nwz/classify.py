from __future__ import annotations

import json
import os
import textwrap
from typing import Any

from openai import OpenAI

MODEL = "gpt-4o"
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client


def _format_articles(articles: list[dict]) -> str:
    lines: list[str] = []
    for i, a in enumerate(articles, 1):
        text = (a.get("content_text") or "")[:900].replace("\n", " ")
        lines.append(
            f"[{i}] refid={a['refid']}\n"
            f"Rubrik: {a.get('category_name','')}\n"
            f"Titel: {a.get('title','')}\n"
            f"Untertitel: {a.get('subtitle','')}\n"
            f"Text: {text}"
        )
    return "\n\n".join(lines)


def build_digest(
    articles: list[dict],
    topics: list[dict],  # [{"id": int, "name": str, "description": str}]
    pub_date: str,
    recent_context: dict[str, list[str]] | None = None,  # {topic_name: [recently_sent_titles]}
) -> tuple[str, list[dict]]:
    """Call OpenAI to match articles to topics.

    Returns (telegram_message, raw_matches) where raw_matches is a list of
    {"topic_id", "catalog", "refid", "pub_date", "title", "summary", "is_continuation"} dicts
    ready to pass to Store.save_article_matches().

    recent_context: if provided, GPT flags articles that are continuations of already-sent stories.
    """
    client = _get_client()
    refid_to_page = {a["refid"]: a.get("page") for a in articles}
    refid_to_catalog = {a["refid"]: a["catalog"] for a in articles}
    refid_to_pub_date = {a["refid"]: a.get("publication_date", pub_date) for a in articles}
    name_to_id = {t["name"]: t.get("id", 0) for t in topics}

    topics_list = "\n".join(
        f"{i}. Name: {t['name']}\n   Beschreibung: {t['description']}"
        for i, t in enumerate(topics, 1)
    )
    articles_block = _format_articles(articles)

    context_block = ""
    if recent_context:
        lines = ["Bereits versendete Artikel der letzten Tage (für Duplikaterkennung):"]
        for topic_name, titles in recent_context.items():
            title_list = "; ".join(f'"{t}"' for t in titles[:6])
            lines.append(f'  Thema "{topic_name}": {title_list}')
        context_block = "\n".join(lines) + "\n\n"

    continuation_instruction = (
        'Setze "is_continuation": true wenn ein Artikel erkennbar eine Fortsetzung '
        "einer der oben gelisteten Geschichten ist (gleicher Vorfall, gleiche Debatte). "
        'Sonst false.\n' if context_block else ""
    )

    system = textwrap.dedent(f"""\
        Du bist ein Redaktionsassistent, der Zeitungsartikel der Nordwest-Zeitung (NWZ)
        nach thematischen Interessen des Lesers filtert und zusammenfasst.
        Ausgabe: kompaktes Deutsch, präzise, ohne Floskeln.
        Heute: {pub_date}.
    """)

    prompt = textwrap.dedent(f"""\
        Hier sind die Themen des Lesers:
        {topics_list}

        {context_block}Und hier die Artikel der NWZ-Ausgabe ({pub_date}):

        {articles_block}

        Aufgabe:
        Für jedes Thema: finde passende Artikel (0–5 Stück).
        Schreibe keine Zusammenfassung für Themen ohne passende Artikel.
        {continuation_instruction}Gib die Antwort als JSON zurück:

        {{
          "digest": [
            {{
              "topic": "Themenname",
              "articles": [
                {{
                  "refid": "...",
                  "title": "...",
                  "summary": "1–2 Sätze auf Deutsch",
                  "is_continuation": false
                }}
              ]
            }}
          ]
        }}

        Nur JSON, kein weiterer Text.
    """)

    resp = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        max_tokens=2048,
    )

    raw = resp.choices[0].message.content.strip()
    data: dict[str, Any] = json.loads(raw)

    raw_matches = [
        {
            "topic_id": name_to_id.get(te["topic"], 0),
            "catalog": refid_to_catalog.get(art["refid"], 0),
            "refid": art["refid"],
            "pub_date": refid_to_pub_date.get(art["refid"], pub_date),
            "title": art.get("title", ""),
            "summary": art.get("summary", ""),
            "is_continuation": bool(art.get("is_continuation", False)),
        }
        for te in data.get("digest", [])
        for art in te.get("articles", [])
        if art.get("refid")
    ]

    return _format_telegram(data, pub_date, refid_to_page), raw_matches


def _format_telegram(
    data: dict,
    pub_date: str,
    refid_to_page: dict[str, int | None],
) -> str:
    parts: list[str] = [f"<b>NWZ Digest – {pub_date}</b>\n"]
    has_content = False

    for topic in data.get("digest", []):
        arts = topic.get("articles", [])
        if not arts:
            continue
        has_content = True
        parts.append(f"\n📌 <b>{_esc(topic['topic'])}</b>")
        for a in arts:
            title = _esc(a.get("title", ""))
            summary = _esc(a.get("summary", ""))
            refid = a.get("refid", "")
            page = refid_to_page.get(refid)
            page_info = f"\n  <i>Seite {page}</i>" if page else ""
            prefix = "🔄" if a.get("is_continuation") else "•"
            parts.append(f"{prefix} <b>{title}</b>\n  {summary}{page_info}")

    if not has_content:
        return ""

    return "\n".join(parts)


def build_weekly_digest(
    matches: list[dict],  # from store.get_weekly_matches
    date_from: str,
    date_to: str,
) -> str:
    """Build a weekly summary with GPT-ranked highlights.

    matches: list of dicts with topic_name, title, summary, pub_date, page, is_continuation.
    Returns a formatted Telegram HTML string, or '' if nothing to send.
    """
    if not matches:
        return ""

    # Group by topic
    by_topic: dict[str, list[dict]] = {}
    for m in matches:
        by_topic.setdefault(m["topic_name"], []).append(m)

    highlights: list[dict] = []
    if len(matches) >= 3:
        client = _get_client()
        lines = []
        for m in matches:
            page_info = f"Seite {m['page']}" if m.get("page") else ""
            cont = " [Fortsetzung]" if m.get("is_continuation") else ""
            page_str = f" · {page_info}" if page_info else ""
            lines.append(
                f"- [{_esc(m['topic_name'])}]{page_str}{cont}: "
                f"{m['title']} — {m['summary']}"
            )
        articles_block = "\n".join(lines)

        prompt = textwrap.dedent(f"""\
            Hier sind alle Artikel aus dem NWZ-Nachrichtenarchiv der Woche \
({date_from} bis {date_to}):

{articles_block}

Wähle die 3–5 Artikel, die für die Oldenburger Lokalpolitik diese Woche \
am bedeutsamsten waren. Begründe in einem knappen Satz, warum jeder wichtig ist.

Ausgabe als JSON:
{{
  "highlights": [
    {{"title": "...", "reason": "1 Satz"}}
  ]
}}

Nur JSON, kein weiterer Text.\
        """)

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "Du bist ein politischer Redakteur für Oldenburger Lokalpolitik."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=600,
        )
        data = json.loads(resp.choices[0].message.content.strip())
        highlights = data.get("highlights", [])

    # Format date range header
    def _fmt(iso: str) -> str:
        y, m, d = iso.split("-")
        return f"{d}.{m}.{y}"

    parts: list[str] = [f"📅 <b>NWZ Wochenrückblick ({_fmt(date_from)}–{_fmt(date_to)})</b>\n"]

    if highlights:
        parts.append("⭐ <b>Highlights der Woche</b>")
        for h in highlights:
            parts.append(f"• <b>{_esc(h.get('title', ''))}</b>\n  <i>{_esc(h.get('reason', ''))}</i>")
        parts.append("")

    for topic_name, arts in by_topic.items():
        parts.append(f"📌 <b>{_esc(topic_name)}</b> ({len(arts)} Artikel)")
        for a in arts:
            prefix = "🔄" if a.get("is_continuation") else "•"
            page_info = f" · <i>Seite {a['page']}</i>" if a.get("page") else ""
            parts.append(
                f"{prefix} <b>{_esc(a['title'])}</b>{page_info}\n  {_esc(a['summary'])}"
            )
        parts.append("")

    return "\n".join(parts).rstrip()


def _esc(text: str) -> str:
    """Escape HTML special chars for Telegram HTML parse mode."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
