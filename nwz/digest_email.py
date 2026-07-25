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
