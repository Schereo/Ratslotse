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
) -> tuple[str, list[dict]]:
    """Call OpenAI to match articles to topics.

    Returns (telegram_message, raw_matches) where raw_matches is a list of
    {"topic_id", "catalog", "refid", "pub_date", "title", "summary"} dicts
    ready to pass to Store.save_article_matches().
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

    system = textwrap.dedent(f"""\
        Du bist ein Redaktionsassistent, der Zeitungsartikel der Nordwest-Zeitung (NWZ)
        nach thematischen Interessen des Lesers filtert und zusammenfasst.
        Ausgabe: kompaktes Deutsch, präzise, ohne Floskeln.
        Heute: {pub_date}.
    """)

    prompt = textwrap.dedent(f"""\
        Hier sind die Themen des Lesers:
        {topics_list}

        Und hier die Artikel der NWZ-Ausgabe ({pub_date}):

        {articles_block}

        Aufgabe:
        Für jedes Thema: finde passende Artikel (0–5 Stück).
        Schreibe keine Zusammenfassung für Themen ohne passende Artikel.
        Gib die Antwort als JSON zurück:

        {{
          "digest": [
            {{
              "topic": "Themenname",
              "articles": [
                {{
                  "refid": "...",
                  "title": "...",
                  "summary": "1–2 Sätze auf Deutsch"
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
            parts.append(f"• <b>{title}</b>\n  {summary}{page_info}")

    if not has_content:
        return ""

    return "\n".join(parts)


def _esc(text: str) -> str:
    """Escape HTML special chars for Telegram HTML parse mode."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
