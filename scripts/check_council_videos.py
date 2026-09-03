#!/usr/bin/env python3
"""Vorläufige Abstimmungsergebnisse aus der O1-Videoaufzeichnung holen.

oldenburg eins lädt die Aufzeichnung jeder Ratssitzung tags darauf auf
YouTube; die Auto-Untertitel liefern die Abstimmungsergebnisse 1–2 Monate
vor dem amtlichen Protokoll (Verfahren und Messung: ``council/videos.py``).

Kandidaten sind Ratssitzungen der letzten Wochen, die noch keine
Protokoll-Beschlüsse und noch keine YouTube-Ergebnisse haben. Vorläufige
Ergebnisse direkt aus dem Livestream bleiben ausdrücklich offen, damit echte
Video-Links und Zeitmarken nachgereicht werden. Je Kandidat:
Video suchen → Untertitel ziehen → streng lesen → speichern. Fehlt das
Video oder fehlen die Untertitel noch (YouTube braucht nach dem Upload
Stunden für die Spracherkennung), versucht es der nächste Lauf wieder —
der Kandidat bleibt offen, bis Ergebnisse da sind oder das Protokoll ihn
überholt.

Run daily via cron, e.g. ``30 10 * * *``.
"""
from __future__ import annotations

import logging
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import videos  # noqa: E402
from council.store import CouncilStore  # noqa: E402

log = logging.getLogger(__name__)

COUNCIL_DB = ROOT / "data" / "council.sqlite"
#: Nach ~6 Wochen ist entweder das Protokoll da oder das Video kommt nicht mehr.
LOOKBACK_DAYS = 42


def main() -> dict:
    """Gibt die Kennzahlen des Laufs für die Cron-Übersicht zurück."""
    store = CouncilStore(COUNCIL_DB)
    since = (date.today() - timedelta(days=LOOKBACK_DAYS)).isoformat()
    candidates = store.sessions_needing_video_check(since)
    stats = {"kandidaten": len(candidates), "videos_gefunden": 0,
             "ohne_untertitel": 0, "ergebnisse_gespeichert": 0}
    workdir = Path(tempfile.gettempdir()) / "council-videos"
    for s in candidates:
        video = videos.find_video(s["session_date"])
        if not video:
            log.info("Kein Video für Sitzung %s (%s)", s["ksinr"], s["session_date"])
            continue
        stats["videos_gefunden"] += 1
        transcript = videos.fetch_transcript(video["video_id"], workdir)
        if not transcript:
            # Untertitel kommen Stunden bis Tage nach dem Upload — nicht
            # jedes Video bekommt welche (1 von 7 im Prüfbestand).
            stats["ohne_untertitel"] += 1
            log.info("Video %s noch ohne Untertitel (Sitzung %s)",
                     video["video_id"], s["ksinr"])
            continue
        agenda = [it for it in store.agenda_items(s["ksinr"]) if it.get("is_public")]
        results = videos.extract_results(transcript, agenda)
        if results:
            n = store.save_video_results(s["ksinr"], video["video_id"],
                                         videos.MODEL, results)
            stats["ergebnisse_gespeichert"] += n
            log.info("Sitzung %s: %d vorläufige Ergebnisse aus Video %s",
                     s["ksinr"], n, video["video_id"])
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from kern.alerts import run_guarded

    run_guarded("check_council_videos", main)
