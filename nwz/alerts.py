"""Admin failure alerts for unattended cron jobs.

Wraps a cron entrypoint so a crash is logged with a full traceback (visible in
journald / the cron log) and still re-raised, surfacing a non-zero exit.
"""
from __future__ import annotations

import html
import logging
import sys
import traceback
from typing import Callable

logger = logging.getLogger("nwz.alerts")


def notify_admin(text: str) -> None:
    """Record an admin-facing failure notice. Currently logs only (surfaces in
    journald / the cron log); never raises."""
    logger.error("admin alert: %s", text)


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
