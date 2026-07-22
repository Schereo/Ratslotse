"""Render the daily/weekly digest as an HTML email.

The classifier produces a list of `matches` (one per relevant article) plus a
Telegram-formatted text. For email we re-render the matches into a simple,
robust HTML table-free layout that survives most mail clients, with links back
to the web frontend (ratslotse.de) instead of Telegram's inline buttons.
"""
from __future__ import annotations

import html
import os
from collections import defaultdict

# Public base URL of the web frontend; matches link here.
APP_BASE_URL = os.environ.get("APP_BASE_URL", "https://ratslotse.de").rstrip("/")


def _esc(text: str) -> str:
    return html.escape(text or "")


def _display_date(pub_date: str) -> str:
    d = (pub_date or "").split("-")
    return f"{d[2]}.{d[1]}.{d[0]}" if len(d) == 3 else pub_date


def render_digest_email(
    topics: list,
    matches: list[dict],
    pub_date: str,
) -> tuple[str, str, str]:
    """Return (subject, html_body, text_body) for the given matches.

    `topics` is a list of objects/dicts with `id` and `name` (TopicRow works);
    `matches` is the classifier output ([{topic_id, title, summary, pub_date, …}]).
    Returns an empty-state mail when there are no matches.
    """
    topic_name = {}
    for t in topics:
        tid = getattr(t, "id", None) if not isinstance(t, dict) else t.get("id")
        name = getattr(t, "name", None) if not isinstance(t, dict) else t.get("name")
        topic_name[tid] = name or "Thema"

    display = _display_date(pub_date)
    subject = f"Ratslotse – Digest {display}"
    topics_url = f"{APP_BASE_URL}/topics"

    if not matches:
        names = ", ".join(_esc(topic_name[k]) for k in topic_name) or "deinen Themen"
        body_html = _wrap(
            display,
            f"<p style='margin:0 0 16px'>Heute keine Artikel zu deinen Themen gefunden:</p>"
            f"<p style='margin:0;color:#475569'><em>{names}</em></p>",
            topics_url,
        )
        body_text = f"Ratslotse – Digest {display}\n\nHeute keine Artikel zu deinen Themen gefunden.\n\n{topics_url}\n"
        return subject, body_html, body_text

    # Group matches by topic (preserve topic order from `topics`).
    by_topic: dict[int, list[dict]] = defaultdict(list)
    for m in matches:
        by_topic[m["topic_id"]].append(m)
    ordered_topic_ids = [t.id if not isinstance(t, dict) else t["id"] for t in topics]
    ordered_topic_ids = [tid for tid in ordered_topic_ids if tid in by_topic]

    sections_html: list[str] = []
    text_lines: list[str] = [f"Ratslotse – Digest {display}", ""]
    for tid in ordered_topic_ids:
        name = _esc(topic_name.get(tid, "Thema"))
        sections_html.append(
            f"<h2 style='margin:24px 0 8px;font-size:16px;color:#0f172a'>{name}</h2>"
        )
        text_lines.append(f"## {topic_name.get(tid, 'Thema')}")
        for m in by_topic[tid]:
            cont = " 🔄" if m.get("is_continuation") else ""
            sections_html.append(
                "<div style='margin:0 0 14px;padding:12px 14px;background:#f8fafc;"
                "border-radius:8px'>"
                f"<div style='font-weight:600;color:#0f172a'>{_esc(m['title'])}{cont}</div>"
                f"<div style='margin-top:4px;color:#475569;font-size:14px'>{_esc(m['summary'])}</div>"
                "</div>"
            )
            text_lines.append(f"- {m['title']}{cont}\n  {m['summary']}")
        text_lines.append("")

    n = len(matches)
    intro = f"<p style='margin:0 0 8px;color:#475569'>{n} neue{'r' if n == 1 else ''} Treffer zu deinen Themen.</p>"
    body_html = _wrap(display, intro + "".join(sections_html), topics_url)
    text_lines.append(f"Alle Treffer ansehen: {topics_url}")
    return subject, body_html, "\n".join(text_lines)


def render_html_email(subject: str, body_html_or_text: str, greeting_name: str | None = None) -> str:
    """Wrap an already-formatted message (Telegram-style HTML with \\n line
    breaks) in the Ratslotse email shell. Used for the weekly digest and council
    notifications, which produce a single formatted block rather than matches.
    ``greeting_name`` ergänzt eine persönliche Anrede („Moin Tim,")."""
    greeting = (
        f"<div style='margin-top:16px;font-size:14px'>Moin {greeting_name},</div>"
        if greeting_name
        else ""
    )
    return (
        "<div style='max-width:600px;margin:0 auto;padding:24px 16px;"
        "font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#0f172a'>"
        "<div style='font-size:20px;font-weight:700;color:#2563eb'>Ratslotse</div>"
        f"{greeting}"
        f"<div style='margin-top:16px;white-space:pre-wrap;font-size:14px;line-height:1.5'>{body_html_or_text}</div>"
        "<hr style='margin:28px 0 16px;border:none;border-top:1px solid #e2e8f0'>"
        f"<a href='{APP_BASE_URL}' style='color:#2563eb;text-decoration:none;font-size:14px'>"
        "Zu Ratslotse →</a>"
        "<div style='margin-top:16px;color:#94a3b8;font-size:12px'>"
        "Du bekommst diese E-Mail, weil du bei Ratslotse die E-Mail-Zustellung aktiviert hast. "
        "Den Kanal änderst du jederzeit unter „Mein Konto“.</div>"
        "</div>"
    )


def _wrap(display_date: str, inner_html: str, topics_url: str) -> str:
    """Wrap section HTML in a minimal, mail-client-safe document."""
    return (
        "<div style='max-width:600px;margin:0 auto;padding:24px 16px;"
        "font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#0f172a'>"
        "<div style='font-size:20px;font-weight:700;color:#2563eb'>Ratslotse</div>"
        f"<div style='margin-top:2px;color:#64748b;font-size:14px'>NWZ-Digest · {display_date}</div>"
        f"<div style='margin-top:20px'>{inner_html}</div>"
        "<hr style='margin:28px 0 16px;border:none;border-top:1px solid #e2e8f0'>"
        f"<a href='{topics_url}' style='color:#2563eb;text-decoration:none;font-size:14px'>"
        "Themen &amp; Treffer im Web verwalten →</a>"
        "<div style='margin-top:16px;color:#94a3b8;font-size:12px'>"
        "Du bekommst diese E-Mail, weil du bei Ratslotse die E-Mail-Zustellung aktiviert hast. "
        "Den Kanal änderst du jederzeit unter „Mein Konto“.</div>"
        "</div>"
    )
