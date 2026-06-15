from __future__ import annotations

import json
import os
import textwrap
from typing import Any

from openai import OpenAI

MODEL = "openai/gpt-4o"
VERIFY_MODEL = "openai/gpt-4o-mini"
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.environ["OPENROUTER_API_KEY"],
            base_url="https://openrouter.ai/api/v1",
        )
    return _client


def _verify_match(client: OpenAI, topic: dict, article: dict) -> bool:
    """Cheap second-pass check: does the article genuinely deal with the topic?

    Returns True only if the topic is a central, explicit subject of the article.
    Keyword overlap, thematic kinship or nationwide references without the local/
    concrete angle the topic asks for do not count.
    """
    text = (article.get("content_text") or "")[:1500].replace("\n", " ")
    resp = client.chat.completions.create(
        model=VERIFY_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        max_tokens=20,
        messages=[
            {
                "role": "system",
                "content": (
                    "Du prüfst, ob ein Zeitungsartikel WIRKLICH vom angegebenen Thema handelt. "
                    "Strenges Kriterium: Das Thema muss ein ZENTRALER Gegenstand des Artikels sein. "
                    "Eine bloße beiläufige Erwähnung reicht NICHT — insbesondere zählt es nicht, wenn "
                    "das Thema nur in einer Abstimmungsliste, Aufzählung, Klammer oder Randnotiz "
                    "vorkommt, während der Artikel eigentlich von etwas anderem handelt "
                    "(z.B. ein Artikel über einen Stadion-Beschluss, der eine Partei nur in der "
                    "Ja/Nein-Stimmenliste nennt). Ebenso zählen Stichwort-Überschneidung (z.B. das "
                    "Wort 'grün'), thematische Verwandtschaft oder bundesweite Bezüge ohne den im "
                    "Thema geforderten lokalen/konkreten Bezug NICHT. Frage dich: Würde ein Leser "
                    "sagen, dieser Artikel handelt von dem Thema? Antworte nur als JSON: "
                    "{\"relevant\": true/false}."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Thema: {topic.get('name','')}\n"
                    f"Themen-Beschreibung: {topic.get('description','')}\n\n"
                    f"Artikel-Titel: {article.get('title','')}\n"
                    f"Artikel-Text: {text}"
                ),
            },
        ],
    )
    try:
        return bool(json.loads(resp.choices[0].message.content).get("relevant", False))
    except (json.JSONDecodeError, AttributeError):
        return True  # on parse failure, don't drop a possibly-valid match


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

        STRENGES Relevanzkriterium — ein Artikel passt NUR, wenn das Thema
        ein zentraler Gegenstand des Artikels selbst ist. Der Bezug muss
        explizit im Artikeltext stehen, nicht erschlossen oder vermutet werden.

        Ein Artikel passt NICHT, wenn:
        - er nur THEMATISCH VERWANDT ist (z. B. allgemein Kultur/Politik/Sport
          in Oldenburg), das konkrete Thema aber nicht behandelt;
        - der Bezug nur SPEKULATIV ist ("könnte für X interessant sein",
          "X könnte sich damit beschäftigen", "illustriert Engagement, das
          politisch relevant sein könnte"). Solche Vermutungen sind verboten.
        - das Thema eine Organisation/Partei/Person ist und diese im Artikel
          gar nicht VORKOMMT — eine bloße inhaltliche Nähe genügt nicht.

        Im Zweifel: NICHT aufnehmen. Lieber kein Treffer als ein falscher.
        Die Zusammenfassung muss belegen, WO im Artikel das Thema vorkommt;
        wenn du das nicht ohne Spekulation kannst, ist es kein Treffer.
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
        temperature=0,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        max_tokens=2048,
    )

    raw = resp.choices[0].message.content.strip()
    data: dict[str, Any] = json.loads(raw)

    # Second-pass verification: re-check every candidate match individually with a
    # cheap model. The first pass classifies all topics + all articles in one call,
    # which tends to over-match broad topics (e.g. a party name triggering on the
    # keyword "grün"). Verifying one (topic, article) pair at a time is far more
    # reliable and drops keyword-only / off-topic false positives.
    name_to_topic = {t["name"]: t for t in topics}
    refid_to_article = {a["refid"]: a for a in articles}
    for te in data.get("digest", []):
        topic = name_to_topic.get(te.get("topic"))
        kept = []
        for art in te.get("articles", []):
            article = refid_to_article.get(art.get("refid"))
            if topic is None or article is None:
                kept.append(art)  # cannot verify — keep rather than silently drop
            elif _verify_match(client, topic, article):
                kept.append(art)
        te["articles"] = kept

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
    all_articles: list[dict] | None = None,  # from store.articles_in_range
) -> str:
    """Build a weekly summary with GPT-ranked highlights.

    matches: list of dicts with topic_name, title, summary, pub_date, page, is_continuation.
    all_articles: if provided, highlights are chosen from ALL NWZ articles (not just topic matches).
    Returns a formatted Telegram HTML string, or '' if nothing to send.
    """
    if not matches:
        return ""

    # Group by topic
    by_topic: dict[str, list[dict]] = {}
    for m in matches:
        by_topic.setdefault(m["topic_name"], []).append(m)

    highlights: list[dict] = []
    source = all_articles if all_articles else matches
    if len(source) >= 3:
        client = _get_client()
        if all_articles:
            lines = []
            for a in all_articles:
                page_str = f"Seite {a['page']} · " if a.get("page") else ""
                cat = a.get("category_name") or ""
                date_str = a.get("publication_date", "")
                lines.append(f"- {page_str}{cat} ({date_str}): {a['title']}")
            articles_block = "\n".join(lines)
        else:
            lines = []
            for m in matches:
                page_info = f"Seite {m['page']}" if m.get("page") else ""
                cont = " [Fortsetzung]" if m.get("is_continuation") else ""
                page_str = f" · {page_info}" if page_info else ""
                lines.append(
                    f"- [{m['topic_name']}]{page_str}{cont}: "
                    f"{m['title']} — {m['summary']}"
                )
            articles_block = "\n".join(lines)

        prompt = textwrap.dedent(f"""\
            Hier sind alle Artikel der NWZ-Ausgaben der Woche \
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
            model="openai/gpt-4o-mini",
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
