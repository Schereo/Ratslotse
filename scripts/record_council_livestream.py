#!/usr/bin/env python3
"""Ratssitzung live aus dem O1-Stream mitschneiden → vorläufige Ergebnisse.

Läuft täglich am Nachmittag (Cron auf dem UTC-Server: ``0 13 * * *``): Gibt es heute
eine Ratssitzung ohne Ergebnisse, wartet der Job bis kurz vor Sitzungsbeginn,
schneidet den O1-Stream mit, transkribiert parallel zur Aufnahme und liest
die Abstimmungsergebnisse mit derselben strengen Extraktion wie der
YouTube-Weg (``council/videos.py``). Die Ergebnisse stehen damit noch am
Sitzungsabend auf der Seite — als vorläufiger Stand ohne Video-Sprung-Links
(``video_id=''``); die YouTube-Fassung reicht Links und exakte Timestamps
nach, das Protokoll ersetzt später beides.

An Tagen ohne Ratssitzung ist der Lauf ein billiger Leerlauf (Kennzahl
``sitzung_heute: 0``) — die Überfällig-Ampel braucht den täglichen Takt.

Achtung Zeitzonen: ``session_time`` ist lokale Zeit (Europe/Berlin), der
Server läuft auf UTC.
"""
from __future__ import annotations

import logging
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import livestream, videos  # noqa: E402
from council.store import CouncilStore  # noqa: E402

log = logging.getLogger(__name__)

COUNCIL_DB = ROOT / "data" / "council.sqlite"
TZ = ZoneInfo("Europe/Berlin")
#: Aufnahme beginnt etwas vor der angesetzten Zeit — der Stream läuft eh.
LEAD_MINUTES = 5
#: Länger als das wartet der Job nicht auf den Sitzungsbeginn (Schutz
#: gegen kaputte session_time; der 13-Uhr-UTC-Cron läuft in Oldenburg je nach
#: Sommerzeit um 14 oder 15 Uhr und wartet z. B. bis zur 17-Uhr-Sitzung).
MAX_WAIT_HOURS = 5
#: Jeder Lauf bekommt darunter ein eigenes temporäres Verzeichnis. Ein
#: abgebrochener Vorgängerlauf darf seine ``chunk_*.mp3`` nie in einen Retry
#: hineinreichen.
RECORDING_ROOT = Path(tempfile.gettempdir()) / "council-livestream"


def _record_fresh(ksinr: int) -> list[tuple[float, str]]:
    """Eine Aufnahme in einem garantiert leeren, danach gelöschten Run-Pfad."""
    RECORDING_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f"{ksinr}-", dir=RECORDING_ROOT
    ) as run_dir:
        return livestream.record_and_transcribe(Path(run_dir))


def main() -> dict:
    """Gibt die Kennzahlen des Laufs für die Cron-Übersicht zurück."""
    store = CouncilStore(COUNCIL_DB)
    today = datetime.now(TZ).date().isoformat()
    candidates = [
        s for s in store.sessions_needing_video_check(today)
        if s["session_date"][:10] == today
        # Der YouTube-Lauf soll Livestream-Ergebnisse weiter sehen; dieser
        # Recorder selbst darf eine bereits ausgewertete Sitzung nicht erneut
        # mitschneiden.
        and not store.get_video_results(s["ksinr"])
    ]
    if not candidates:
        return {"sitzung_heute": 0}
    s = candidates[0]
    stats = {"sitzung_heute": 1, "ksinr": s["ksinr"]}

    # Bis kurz vor Sitzungsbeginn schlafen (session_time ist lokale Zeit).
    try:
        h, m = (int(x) for x in str(s["session_time"]).split(":")[:2])
        start = datetime.now(TZ).replace(hour=h, minute=m, second=0,
                                         microsecond=0)
    except (ValueError, TypeError):
        log.warning("Sitzung %s ohne lesbare Startzeit (%r) — Aufnahme sofort",
                    s["ksinr"], s.get("session_time"))
        start = datetime.now(TZ)
    wait = (start - timedelta(minutes=LEAD_MINUTES)) - datetime.now(TZ)
    if wait.total_seconds() > MAX_WAIT_HOURS * 3600:
        log.warning("Sitzungsbeginn %s liegt > %d h voraus — abgebrochen",
                    start, MAX_WAIT_HOURS)
        return {**stats, "abgebrochen": "startzeit"}
    if wait.total_seconds() > 0:
        log.info("Warte %d min bis Aufnahmebeginn (Sitzung %s um %s)",
                 wait.total_seconds() // 60, s["ksinr"], s["session_time"])
        time.sleep(wait.total_seconds())

    t0 = time.monotonic()
    segments = _record_fresh(s["ksinr"])
    stats["aufnahme_min"] = int((time.monotonic() - t0) / 60)
    stats["transkript_segmente"] = len(segments)
    if not segments:
        return stats

    agenda = [it for it in store.agenda_items(s["ksinr"]) if it.get("is_public")]
    results = videos.extract_results(segments, agenda)
    # video_id='': Ergebnis aus dem Livestream — Sprung-Links reicht die
    # YouTube-Fassung nach (deren Lauf ersetzt diese Zeilen komplett).
    stats["ergebnisse"] = store.save_video_results(
        s["ksinr"], "", livestream.STT_MODEL + "+" + videos.MODEL, results)
    log.info("Sitzung %s: %d vorläufige Ergebnisse aus dem Livestream",
             s["ksinr"], stats["ergebnisse"])
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    from kern.alerts import run_guarded

    run_guarded("record_council_livestream", main)
