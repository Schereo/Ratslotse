"""Admin failure alerts for unattended cron jobs.

A crashing cron previously failed silently (only visible in journald). These
helpers send a best-effort Telegram message to the admin (TELEGRAM_CHAT_ID) and
re-raise, so the failure is both *noticed* and still surfaces a non-zero exit.
"""
from __future__ import annotations

import html
import logging
import sys
import traceback
from typing import Callable

logger = logging.getLogger("nwz.alerts")


def notify_admin(text: str) -> None:
    """Send a best-effort Telegram message to the admin. Never raises."""
    try:
        from nwz.telegram_bot import send_message, telegram_ready

        if not telegram_ready():
            logger.warning("admin alert skipped — Telegram not configured")
            return
        send_message(text)
    except Exception:  # noqa: BLE001 — alerting must never crash the caller
        logger.exception("admin alert failed")


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
