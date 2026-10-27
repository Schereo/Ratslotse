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

Nebenher die **Live-Verfolgung** (``council/livetracker``): Welcher TOP läuft
gerade, wer spricht — in ``council_live_state``, für die Live-Karte in Web
und App. Sie ist Zugabe: Fällt sie aus, läuft der Mitschnitt weiter.

Zwei Wege für die Transkription: Mit ``GLADIA_API_KEY`` läuft das Audio
streamend (``council/stream_stt.py``, Verzug wenige Sekunden, Fenster von 15 s
für die Verfolgung); ohne Schlüssel — oder wenn die Streaming-Sitzung nicht
zustande kommt — in Audio-Stücken (``council/livestream.py``).

Das ganze Transkript landet zusätzlich als Text mit Uhrzeiten in
``data/transkripte/rat-<datum>-<ksinr>.txt`` — Gladias eigene Ablage ist
lückenhaft (s. ``_Transcript``).

An Tagen ohne Ratssitzung ist der Lauf ein billiger Leerlauf (Kennzahl
``sitzung_heute: 0``) — die Überfällig-Ampel braucht den täglichen Takt.

Achtung Zeitzonen: ``session_time`` ist lokale Zeit (Europe/Berlin), der
Server läuft auf UTC.

Generalprobe vor einer Sitzung (auf dem Server)::

    .venv/bin/python scripts/record_council_livestream.py --probe 60
"""
from __future__ import annotations

import logging
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import livestream, livetracker, stream_stt, stt_retain, videos  # noqa: E402
from council.store import CouncilStore  # noqa: E402

# Für den gewählten Rat (``_roster``); importiert wird erst dort, damit ein
# Fehler im Wahl-Code nie den Mitschnitt verhindert.
sys.path.insert(0, str(ROOT / "web" / "backend"))

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
#: Das ganze Transkript jeder Sitzung, als Text mit Uhrzeiten (``_Transcript``).
TRANSCRIPT_DIR = ROOT / "data" / "transkripte"


class _Transcript:
    """Das Transkript einer Sitzung als eigene Datei, eine Zeile je Äußerung.

    Gladia hebt die Live-Sitzungen zwar auf, aber nicht verlässlich: Am
    26.10.2026 fehlten in der ersten der drei Sitzungen die ersten 19 Minuten
    (Eröffnung bis Einwohnerfragestunde), obwohl sie live ankamen und die
    Live-Verfolgung daraus TOP 2 bis 5 erkannte. Die beiden anderen waren
    vollständig. Deshalb schreibt der Recorder selbst mit.

    Beim Streaming kommt jede Äußerung sofort in die Datei (``add``), damit
    auch ein abgebrochener Lauf seinen Text behält; am Ende schreibt
    ``write_all`` sie sortiert und vollständig neu, auch für den Stück-Weg.
    Ein Schreibfehler kostet nur die Datei, nie den Mitschnitt."""

    def __init__(self, ksinr: int, started_at: datetime, folder: Path | None = None):
        self.ksinr = ksinr
        self.started_at = started_at
        folder = folder or TRANSCRIPT_DIR
        self.path = folder / f"rat-{started_at.date().isoformat()}-{ksinr}.txt"
        self._broken = False
        try:
            folder.mkdir(parents=True, exist_ok=True)
            self.path.write_text(self._head(), encoding="utf-8")
        except OSError:
            self._fail()

    def _head(self, weg: str | None = None) -> str:
        zusatz = f", Weg {weg}" if weg else ""
        return (f"# Ratssitzung {self.ksinr} am {self.started_at.date().isoformat()}, "
                f"Mitschnitt ab {self.started_at.strftime('%H:%M:%S')}{zusatz}\n")

    def _line(self, start: float, text: str) -> str:
        clock = (self.started_at + timedelta(seconds=start)).strftime("%H:%M:%S")
        return f"[{clock}] {text}\n"

    def _fail(self) -> None:
        if not self._broken:
            log.exception("Transkript-Datei %s nicht schreibbar", self.path)
        self._broken = True

    def add(self, start: float, end: float, text: str) -> None:
        """Haken ``on_segment`` des Streaming-Wegs."""
        if self._broken:
            return
        try:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(self._line(start, text))
        except OSError:
            self._fail()

    def write_all(self, segments: list[tuple[float, str]], weg: str) -> None:
        tmp = self.path.with_suffix(".tmp")
        try:
            tmp.write_text(self._head(weg) + "".join(self._line(a, t) for a, t in sorted(segments)),
                           encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            log.exception("Transkript-Datei %s nicht geschrieben", self.path)


def _record_fresh(ksinr: int, on_chunk=None,
                  stop: threading.Event | None = None) -> list[tuple[float, str]]:
    """Eine Aufnahme in einem garantiert leeren, danach gelöschten Run-Pfad.

    Vor dem Löschen wird eine feste Auswahl der Stücke aufgehoben
    (``stt_retain``) — der Run-Pfad existiert dafür noch, das Verzeichnis
    fliegt erst beim Verlassen des ``with``-Blocks weg."""
    RECORDING_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f"{ksinr}-", dir=RECORDING_ROOT
    ) as run_dir:
        run_path = Path(run_dir)
        texte: dict[int, str] = {}
        segments = livestream.record_and_transcribe(
            run_path, on_chunk=on_chunk, stop=stop,
            on_transcribed=lambda idx, path, text: texte.__setitem__(idx, text))
        stuecke = sorted(run_path.glob("chunk_*.mp3"))
        stt_retain.retain(ksinr, "chunks",
                          [(p, texte.get(i, "")) for i, p in enumerate(stuecke)])
        return segments


def _roster(store: CouncilStore, session: dict) -> list[dict] | None:
    """Das Sprecher-Verzeichnis zu Beginn einer Wahlperiode — oder None für
    die Vorgabe des Trackers (die Anwesenheitsliste der letzten Ratssitzung).

    Die erste Sitzung des neuen Rats (02.11.2026) hat keine Vorgängerin mit
    ihm: Die letzte Liste zeigt den alten, gut die Hälfte der Gewählten fehlte
    im Verzeichnis und im Gladia-Vokabular. Bis eine Sitzung der neuen
    Wahlperiode ihre Liste hat, gilt deshalb der gewählte Rat samt neuer
    Verwaltungsspitze; die Dezernent*innen kommen aus der letzten Liste."""
    try:
        from app.election import elected

        neu = elected.live_roster()
    except Exception:  # noqa: BLE001 — dann eben die alte Liste
        log.exception("Gewählter Rat für Sitzung %s nicht lesbar", session["ksinr"])
        return None
    if neu is None:
        return None
    beginn, rows = neu
    if session["session_date"][:10] < beginn:
        return None
    if store.council_roster_before(session["ksinr"], since=beginn):
        return None  # Die neue Wahlperiode hat schon eine echte Liste.
    namen = {r["name"] for r in rows}
    verwaltung = [p for p in store.council_roster_before(session["ksinr"])
                  if p["role"] == "administration" and p["name"] not in namen]
    log.info("Sitzung %s: Verzeichnis aus dem gewählten Rat (%d Personen, %d aus der Verwaltung)",
             session["ksinr"], len(rows), len(verwaltung))
    return rows + verwaltung


def _tracker(store: CouncilStore, ksinr: int, window_seconds: int,
             people: list[dict] | None = None) -> livetracker.LiveTracker | None:
    """Die Live-Verfolgung anwerfen — oder ohne sie aufnehmen, wenn sie
    schon beim Aufbau scheitert (fehlende Tagesordnung, DB-Fehler)."""
    try:
        return livetracker.LiveTracker(store, ksinr, window_seconds, people=people)
    except Exception:  # noqa: BLE001 — Zugabe, s. Modulkopf
        log.exception("Live-Verfolgung für Sitzung %s nicht gestartet", ksinr)
        return None


def _record(ksinr: int, tracker: livetracker.LiveTracker | None,
            transcript: _Transcript | None = None) -> tuple[list[tuple[float, str]], str]:
    """Streamend, wenn möglich; sonst (oder wenn die Streaming-Sitzung nicht
    zustande kommt) in Stücken. Gibt die Segmente und den gegangenen Weg."""
    if stream_stt.configured():
        try:
            return stream_stt.record_and_transcribe(
                on_window=tracker.on_window if tracker else None,
                people=tracker.people if tracker else None,
                stop=tracker.session_over if tracker else None,
                on_segment=transcript.add if transcript else None,
                ksinr=ksinr), "gladia"
        except stream_stt.StreamUnavailable as exc:
            log.warning("Streaming nicht möglich (%s) — Rückfall auf Stücke", exc)
            if tracker:
                tracker.chunk_seconds = livestream.CHUNK_SECONDS
    return _record_fresh(ksinr, on_chunk=tracker.on_chunk if tracker else None,
                         stop=tracker.session_over if tracker else None), "chunks"


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
    window = stream_stt.WINDOW_SECONDS if stream_stt.configured() else livestream.CHUNK_SECONDS
    people = _roster(store, s)
    stats["verzeichnis"] = "gewaehlt" if people is not None else "anwesenheit"
    tracker = _tracker(store, s["ksinr"], window, people)
    transcript = _Transcript(s["ksinr"], datetime.now(TZ))
    try:
        segments, stats["stt"] = _record(s["ksinr"], tracker, transcript)
    finally:
        # Auch nach einem Abbruch darf die Karte nicht „gerade" sagen.
        if tracker:
            try:
                tracker.finish()
            except Exception:  # noqa: BLE001
                log.exception("Live-Stand für Sitzung %s nicht abgeschlossen", s["ksinr"])
    stats["aufnahme_min"] = int((time.monotonic() - t0) / 60)
    stats["transkript_segmente"] = len(segments)
    if segments:
        # Nach einem Abbruch kommt der Lauf nicht hierher; was beim Streaming
        # schon in der Datei stand, bleibt dann so stehen.
        transcript.write_all(segments, stats["stt"])
        log.info("Sitzung %s: Transkript in %s", s["ksinr"], transcript.path)
    if tracker:
        stats["live_staende"] = tracker.updates
        # Hat die Live-Verfolgung die Aufnahme beendet (Sitzung vorbei)?
        stats["sitzung_vorbei"] = int(tracker.session_over.is_set())
    if not segments:
        return stats

    agenda = [it for it in store.agenda_items(s["ksinr"]) if it.get("is_public")]
    results = videos.extract_results(segments, agenda)
    # video_id='': Ergebnis aus dem Livestream — Sprung-Links reicht die
    # YouTube-Fassung nach (deren Lauf ersetzt diese Zeilen komplett).
    stt_label = "gladia/solaria-1" if stats["stt"] == "gladia" else livestream.STT_MODEL
    stats["ergebnisse"] = store.save_video_results(
        s["ksinr"], "", stt_label + "+" + videos.MODEL, results)
    log.info("Sitzung %s: %d vorläufige Ergebnisse aus dem Livestream",
             s["ksinr"], stats["ergebnisse"])
    return stats


def probe(seconds: int) -> dict:
    """Generalprobe ohne Sitzung: ``seconds`` lang den O1-Stream über den
    Streaming-Weg transkribieren und die Fenster ausgeben — auf dem Server
    vor einer Ratssitzung, damit Schlüssel, ffmpeg und Netz VOR dem Abend
    geprüft sind (live lässt sich nichts mehr nachbessern)."""
    t0 = time.monotonic()
    fenster: list[str] = []

    def zeigen(a: float, b: float, segs: list[tuple[float, str]], closing: bool) -> None:
        text = " | ".join(t[:80] for _, t in segs)
        fenster.append(text)
        log.info("Fenster %5.1f–%5.1f s (nach %4.1f s): %s", a, b, time.monotonic() - t0, text)

    if not stream_stt.configured():
        log.error("GLADIA_API_KEY fehlt — es liefe der Stück-Weg")
        return {"streaming": False}
    segs = stream_stt.record_and_transcribe(on_window=zeigen, max_seconds=seconds, people=[])
    return {"streaming": True, "sekunden": seconds, "segmente": len(segs),
            "zeichen": sum(len(t) for _, t in segs), "fenster": len(fenster)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    if len(sys.argv) > 2 and sys.argv[1] == "--probe":
        print(probe(int(sys.argv[2])))
        sys.exit(0)
    from kern.alerts import run_guarded

    run_guarded("record_council_livestream", main)
