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
from typing import TYPE_CHECKING
from collections.abc import Callable

if TYPE_CHECKING:  # nur für Typprüfer — zur Laufzeit importiert
    # `_record_run` nimmt einen `datetime` entgegen, holt ihn aber selbst nie:
    # Das Modul importiert `datetime` bewusst erst IN den Funktionen, damit ein
    # Import-Fehler nie einen Cronjob mitreißt. Ohne diesen Block zeigt die
    # Annotation auf einen Namen, den es auf Modulebene nicht gibt — harmlos,
    # solange `from __future__ import annotations` gilt (Annotationen bleiben
    # Zeichenketten), aber irreführend für jeden, der sie auflösen will.
    from datetime import datetime

logger = logging.getLogger("kern.alerts")


def notify_admin(text: str, betreff: str = "Ratslotse – Cron-Alarm",
                 fusszeile: str = "Automatischer Alarm eines Cron-Jobs — "
                                  "Details im Server-Log.") -> None:
    """Record an admin-facing failure notice: always logs; additionally sends a
    best-effort email to ALERT_EMAIL / WEB_ADMIN_EMAIL. Never raises.

    ``text`` may contain simple HTML (<b>/<code>); the plain-text part strips it.

    ``betreff``/``fusszeile`` sind überschreibbar, weil nicht jede Nachricht an
    diese Adresse ein Absturz ist: ``check_finanzdaten`` meldet damit einen
    **Hinweis** („der Jahresabschluss 2025 bleibt aus"). Als „Cron-Alarm"
    betitelt läse ihn niemand mehr als das, was er ist.
    """
    logger.error("admin alert: %s", text)
    recipient = os.environ.get("ALERT_EMAIL") or os.environ.get("WEB_ADMIN_EMAIL")
    if not recipient:
        return
    try:
        from .digest_email import render_html_email
        from .email import email_ready, send_email

        if not email_ready():
            return
        send_email(
            recipient,
            betreff,
            render_html_email(
                betreff,
                f"<div style='white-space:pre-wrap'>{text}</div>",
                held="alarm",
                kicker="Betrieb",
                # „Ratslotse – Cron-Alarm" → „Cron-Alarm": Die Marke steht schon
                # in der Kopfzeile der Hülle, doppelt wäre sie Rauschen.
                title=re.sub(r"^Ratslotse\s*[–-]\s*", "", betreff),
                fusszeile=fusszeile,
            ),
            text=re.sub(r"<[^>]+>", "", text),
        )
    except Exception:
        logger.exception("admin alert email failed")


def _record_run(name: str, started: datetime, status: str,
                stats: dict | None, error: str | None) -> None:
    """Den Lauf in ``job_runs`` schreiben — best effort, nie den Job stören.

    Der Pfad entspricht dem der Cron-Skripte (``<repo>/data/ratslotse.sqlite``); ein
    eigener Store wird nur kurz für die eine Zeile geöffnet, damit run_guarded
    ohne Zutun der Skripte funktioniert.
    """
    try:
        from datetime import datetime
        from pathlib import Path

        from .store import Store

        finished = datetime.utcnow()
        db = Path(os.environ.get("RATSLOTSE_DB") or Path(__file__).resolve().parent.parent / "data" / "ratslotse.sqlite")
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


#: Reservierter Schlüssel INNERHALB der Kennzahlen eines Laufs: darunter steht
#: eine Liste der Unterschritte statt einer Zahl. Nur ``weekly_enrich`` füllt
#: sie heute; das Admin-Panel klappt sie unter dem Elternjob auf. Der Name
#: steht hier und nicht in ``kern/jobs.py``, weil er zum **Kennzahlen-Vertrag**
#: gehört: Wer ihn liest (`web/backend/app/routers/admin.py`) und wer ihn
#: schreibt (`scripts/weekly_enrich.py`) meinen dieselbe Stelle.
SCHRITTE_SCHLUESSEL = "Schritte"


class JobFehler(RuntimeError):
    """Ein Lauf, der teilweise gelungen ist — und seine Kennzahlen mitbringt.

    **Wogegen das steht.** ``run_guarded`` verwarf bei einer Exception die
    Kennzahlen komplett (``_record_run(..., "error", None, ...)``). Ausgerechnet
    an dem Tag, an dem ``weekly_enrich`` einen Schritt verliert, stand in
    ``job_runs`` also nur „error" und der Traceback — welcher der 18 Schritte
    es war, musste man aus dem Log fischen. Wer eine solche Bilanz hat, wirft
    diesen Fehler und behält sie.
    """

    def __init__(self, nachricht: str, kennzahlen: dict | None = None):
        super().__init__(nachricht)
        self.kennzahlen = kennzahlen or {}


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
        # Kennzahlen auch im Fehlerfall — sofern der Fehler welche mitbringt
        # (s. JobFehler). Ein gescheiterter Lauf ist der, bei dem die Bilanz
        # am meisten wert ist.
        kennzahlen = getattr(exc, "kennzahlen", None)
        _record_run(name, started, "error",
                    kennzahlen if isinstance(kennzahlen, dict) else None,
                    f"{type(exc).__name__}: {exc}")
        notify_admin(f"⚠️ Cron <b>{html.escape(name)}</b> ist fehlgeschlagen:\n<code>{detail}</code>")
        traceback.print_exc(file=sys.stderr)
        raise
    _record_run(name, started, "ok", result if isinstance(result, dict) else None, None)
