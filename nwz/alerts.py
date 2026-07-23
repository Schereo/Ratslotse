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


def _record_run(name: str, started: "datetime", status: str,
                stats: dict | None, error: str | None) -> None:
    """Den Lauf in ``job_runs`` schreiben — best effort, nie den Job stören.

    Der Pfad entspricht dem der Cron-Skripte (``<repo>/data/nwz.sqlite``); ein
    eigener Store wird nur kurz für die eine Zeile geöffnet, damit run_guarded
    ohne Zutun der Skripte funktioniert.
    """
    try:
        from datetime import datetime
        from pathlib import Path

        from .store import Store

        finished = datetime.utcnow()
        db = Path(os.environ.get("NWZ_DB") or Path(__file__).resolve().parent.parent / "data" / "nwz.sqlite")
        store = Store(db)
        try:
            store.record_job_run(
                name, started.isoformat(timespec="seconds"), finished.isoformat(timespec="seconds"),
                status, round((finished - started).total_seconds(), 1), stats, error,
            )
        finally:
            store.close()
    except Exception:  # noqa: BLE001 — Protokollierung ist Beiwerk
        logger.exception("job_run für %s konnte nicht protokolliert werden", name)


def run_guarded(name: str, fn: Callable[[], object]) -> None:
    """Run a cron entrypoint; on crash alert the admin, then re-raise so cron/
    systemd still see a non-zero exit and log the traceback.

    Jeder Lauf landet zusätzlich in ``job_runs`` (Dauer, Status, Fehler). Gibt
    ``fn`` ein dict zurück, wird es als Kennzahlen des Laufs gespeichert und im
    Admin-Panel angezeigt — die Schlüssel sind bewusst sprechend, damit neue
    Jobs keine Übersetzungstabelle brauchen.
    """
    from datetime import datetime

    started = datetime.utcnow()
    try:
        result = fn()
    except Exception as exc:
        detail = html.escape(f"{type(exc).__name__}: {exc}")
        _record_run(name, started, "error", None, f"{type(exc).__name__}: {exc}")
        notify_admin(f"⚠️ Cron <b>{html.escape(name)}</b> ist fehlgeschlagen:\n<code>{detail}</code>")
        traceback.print_exc(file=sys.stderr)
        raise
    _record_run(name, started, "ok", result if isinstance(result, dict) else None, None)
