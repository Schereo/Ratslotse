"""Admin failure alerts for unattended cron jobs.

Wraps a cron entrypoint so a crash is logged with a full traceback (visible in
journald / the cron log), reported to a human via email, and still re-raised,
surfacing a non-zero exit.

The email goes to ``ALERT_EMAIL`` (fallback ``WEB_ADMIN_EMAIL``) via Resend and
is strictly best-effort: without ``RESEND_API_KEY`` — or if sending itself
fails — the alert still lands in the log, and the alerting path never raises.
Callers must load ``.env`` before invoking ``run_guarded`` (the cron scripts
do this at import time).
"""
from __future__ import annotations

import html
import logging
import os
import re
import sys
import traceback
from typing import Callable

logger = logging.getLogger("nwz.alerts")


def notify_admin(text: str) -> None:
    """Record an admin-facing failure notice: always logs; additionally sends a
    best-effort email to ALERT_EMAIL / WEB_ADMIN_EMAIL. Never raises.

    ``text`` may contain simple HTML (<b>/<code>); the plain-text part strips it.
    """
    logger.error("admin alert: %s", text)
    recipient = os.environ.get("ALERT_EMAIL") or os.environ.get("WEB_ADMIN_EMAIL")
    if not recipient:
        return
    try:
        from .email import email_ready, send_email

        if not email_ready():
            return
        send_email(
            recipient,
            "Ratslotse – Cron-Alarm",
            "<div style='max-width:560px;margin:0 auto;padding:24px 16px;"
            "font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#0f172a'>"
            "<div style='font-size:20px;font-weight:700;color:#2563eb'>Ratslotse</div>"
            f"<p style='margin:20px 0 8px;white-space:pre-wrap'>{text}</p>"
            "<p style='margin-top:20px;color:#94a3b8;font-size:12px'>"
            "Automatischer Alarm eines Cron-Jobs — Details im Server-Log.</p>"
            "</div>",
            text=re.sub(r"<[^>]+>", "", text),
        )
    except Exception:
        logger.exception("admin alert email failed")


def run_guarded(name: str, fn: Callable[[], None]) -> None:
    """Run a cron entrypoint; on crash alert the admin, then re-raise so cron/
    systemd still see a non-zero exit and log the traceback."""
    try:
        fn()
    except Exception as exc:
        detail = html.escape(f"{type(exc).__name__}: {exc}")
        notify_admin(f"⚠️ Cron <b>{html.escape(name)}</b> ist fehlgeschlagen:\n<code>{detail}</code>")
        traceback.print_exc(file=sys.stderr)
        raise
