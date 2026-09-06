"""Streaming-Transkription des O1-Streams — für die Live-Verfolgung in Sekunden.

Der Weg über Audio-Stücke (``council/livestream.py``) sieht die Sitzung erst,
wenn ein Stück fertig ist; sein Verzug ist mindestens die Stücklänge. Hier
läuft das Audio stattdessen als PCM-Strom über einen Websocket an Gladia
(EU-Region), und jede fertige Äußerung kommt nach wenigen Sekunden mit
Zeitmarke zurück. Gemessen 06.09.2026 an der Ratssitzung vom 31.08.:

- Echtzeit (10-min-Ausschnitt): eine fertige Äußerung kommt im Median 5,2 s
  nach ihrem Ende an (p90 9,2 s); Äußerungen dauern im Median 4,4 s; Text
  je Minute wie bei Gemini. Bei 5-facher Geschwindigkeit staut es sich —
  der Dienst ist für Echtzeit gebaut, 2-fach hält er noch.
- Ganze Sitzung (3 h 49 min, 2-fach): 1.565 Segmente, Neuverbindung an der
  Sitzungsgrenze ohne Verlust; die Live-Verfolgung mit 15-s-Fenstern plus
  ausgelösten Fenstern: 1.081 Aufrufe (297 ausgelöst), 1,06 $, Sprecher in
  896 von 969 Fenstern mit Text. Ein Aufruf oder eine Worterteilung steht
  damit ~7 s nach dem Satz auf der Karte (Text 5 s + Tracker 1,2 s); ein
  reguläres Fenster spätestens nach ~27 s.

Was bleibt gleich: Die Segmente haben dieselbe Form wie beim Stück-Weg
(``(Sekunden seit Aufnahmestart, Text)``), gehen also unverändert in
``videos.extract_results``; und die Live-Verfolgung (``council/livetracker``)
bekommt sie in Fenstern von ``WINDOW_SECONDS`` — und sofort, wenn ein
Punkt aufgerufen oder das Wort erteilt wird (``TRIGGER_RE``) — über
``LiveTracker.on_window(t_from, t_to, segments, closing)``.

Was anders ist:

- **Wortliste.** Gladia nimmt ein eigenes Vokabular an (phonetischer
  Abgleich). Hinein gehen die Nachnamen aus der Anwesenheitsliste der
  vorigen Ratssitzung und die Fraktionsnamen — genau die Wörter, die die
  Erkennung sonst verschreibt („Bark" statt Baak, „BSC" statt BSW).
- **Sitzungsgrenze.** Eine Gladia-Sitzung darf höchstens drei Stunden
  dauern, eine Ratssitzung dauert bis zu fünf. Nach ``SESSION_MAX_SECONDS``
  wird neu verbunden; die Zeitmarken der neuen Sitzung bekommen den
  Versatz der bereits gesendeten Sekunden.
- **Kein Datei-Zwischenschritt.** ffmpeg liefert 16-kHz-PCM in eine Pipe;
  es entstehen keine MP3-Stücke.

Ohne ``GLADIA_API_KEY`` ist der Weg aus (``configured()``), und der
Mitschnitt-Job nimmt die Stücke. Scheitert der Verbindungsaufbau, wirft
``open_session`` ``StreamUnavailable`` — der Job fällt dann auf die Stücke
zurück, statt den Abend zu verlieren.
"""
from __future__ import annotations

import json
import logging
import os
import queue
import re
import subprocess
import threading
import time
from collections.abc import Callable

import httpx
import websockets.sync.client as ws_client

from council import livestream

log = logging.getLogger(__name__)

API_KEY = os.environ.get("GLADIA_API_KEY", "")
REGION = os.environ.get("GLADIA_REGION", "eu-west")
INIT_URL = "https://api.gladia.io/v2/live"
#: Wie oft die Live-Verfolgung ein Fenster bekommt. Der Tracker kostet je
#: Aufruf ~0,1 ct und braucht ~1,5 s; mit 15 s sind das ~900 Aufrufe je
#: Ratssitzung (rund 1 $).
WINDOW_SECONDS = int(os.environ.get("COUNCIL_LIVE_WINDOW_SECONDS", "15"))
#: Wie lange nach dem Fenster-Ende auf Nachzügler gewartet wird — eine
#: Äußerung, die über die Grenze läuft, kommt erst mit ihrem Ende.
SETTLE_SECONDS = 6
#: Gladia: höchstens 3 h je Sitzung. Mit Luft davor neu verbinden.
SESSION_MAX_SECONDS = int(2.5 * 3600)
SAMPLE_RATE = 16_000
FRAME_SECONDS = 0.1
FRAME_BYTES = int(SAMPLE_RATE * 2 * FRAME_SECONDS)  # 16 bit mono
#: Fraktionen und Gruppen im Rat — die Erkennung hört sonst „BSC".
PARTY_TERMS = ["SPD", "CDU", "FDP", "AfD", "BSW", "Volt", "Grünen", "Bündnis 90",
               "Für Oldenburg", "Die Linke", "Fraktion", "Tagesordnungspunkt",
               "Beschlussvorschlag", "Dringlichkeitsantrag", "Veränderungssperre"]


class StreamUnavailable(RuntimeError):
    """Kein Streaming möglich (Schlüssel fehlt, Sitzung nicht eröffnet)."""


def configured() -> bool:
    return bool(API_KEY)


def vocabulary(people: list[dict]) -> list[str]:
    """Nachnamen des Verzeichnisses plus Fraktionen — ohne Dubletten,
    Reihenfolge stabil (Tests und Logs sollen lesbar bleiben)."""
    seen: dict[str, None] = {}
    for p in people or []:
        name = (p.get("name") or "").strip()
        if name:
            seen.setdefault(name.split()[-1], None)
    for term in PARTY_TERMS:
        seen.setdefault(term, None)
    return list(seen)


def session_config(vocab: list[str]) -> dict:
    return {
        "encoding": "wav/pcm", "sample_rate": SAMPLE_RATE, "bit_depth": 16, "channels": 1,
        "language_config": {"languages": ["de"], "code_switching": False},
        # Pausen von 0,3 s schließen eine Äußerung; spätestens nach 15 s
        # kommt sie auch ohne Pause — sonst hinge ein langer Redebeitrag am
        # Stück in der Warteschlange.
        "endpointing": 0.3, "maximum_duration_without_endpointing": 15,
        "realtime_processing": {
            "custom_vocabulary": bool(vocab),
            "custom_vocabulary_config": {"vocabulary": vocab, "default_intensity": 0.5},
        },
        "messages_config": {
            "receive_partial_transcripts": False, "receive_final_transcripts": True,
            "receive_speech_events": False, "receive_lifecycle_events": True,
            "receive_acknowledgments": False, "receive_errors": True,
        },
    }


def open_session(vocab: list[str]) -> str:
    """Sitzung eröffnen → Websocket-URL (Token liegt in der URL)."""
    if not API_KEY:
        raise StreamUnavailable("GLADIA_API_KEY fehlt")
    try:
        r = httpx.post(INIT_URL, params={"region": REGION},
                       headers={"x-gladia-key": API_KEY},
                       json=session_config(vocab), timeout=30)
        r.raise_for_status()
        return r.json()["url"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise StreamUnavailable(f"Gladia-Sitzung nicht eröffnet: {exc}") from exc


def parse_transcript(raw: str | bytes) -> tuple[float, float, str] | None:
    """Websocket-Nachricht → (start, end, text) einer FERTIGEN Äußerung, sonst None."""
    try:
        msg = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if msg.get("type") != "transcript" or not (msg.get("data") or {}).get("is_final"):
        return None
    u = msg["data"].get("utterance") or {}
    text = (u.get("text") or "").strip()
    if not text:
        return None
    return float(u.get("start") or 0.0), float(u.get("end") or 0.0), text


def ffmpeg_pcm(source: str) -> subprocess.Popen | None:
    """ffmpeg: Quelle (HLS-URL oder Datei) → 16-kHz-Mono-PCM auf stdout."""
    exe = livestream.ffmpeg_bin()
    if not exe:
        log.warning("ffmpeg nicht installiert — Streaming übersprungen")
        return None
    cmd = [exe, "-nostdin", "-loglevel", "error", "-i", source,
           "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "-"]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)


#: Was ein Fenster SOFORT auslöst, statt auf die nächste Grenze zu warten:
#: Die Leitung ruft einen Punkt auf oder erteilt das Wort. Genau diese
#: Sätze sollen in Sekunden auf der Karte stehen; alles andere darf den
#: Takt abwarten.
TRIGGER_RE = re.compile(
    r"Tagesordnungspunkt|\bPunkt\s+\d|\bTOP\s+\d|das Wort|\b(?:Herr|Frau)\s+[A-ZÄÖÜ]"
    r"|Abstimmung|abstimmen|dafür|dagegen|Enthaltung|Dringlichkeitsantrag", re.I)
#: Zwei ausgelöste Fenster liegen mindestens so weit auseinander — sonst
#: löste jede Anrede in einer Rede einen Aufruf aus.
TRIGGER_GAP_SECONDS = 4.0


class Windower:
    """Reicht die Segmente in Fenstern an die Live-Verfolgung.

    Regulär alle ``window_seconds`` Audio: Fenster ``[t_from, t_to)`` wird
    ausgeliefert, sobald das Audio ``SETTLE_SECONDS`` über ``t_to`` hinaus
    ist — so lange dauert es, bis eine Äußerung an der Grenze fertig
    gemeldet ist. Dazu SOFORT, wenn ein Segment nach ``TRIGGER_RE`` einen
    Aufruf oder eine Worterteilung trägt: Dann endet das Fenster an der
    aktuellen Audio-Position. Nachzügler gehen mit dem nächsten Fenster
    mit (der Tracker ordnet nach Zeitmarke, nicht nach Ankunft).

    ``on_window(t_from, t_to, segments, closing)`` — passt auf
    ``LiveTracker.on_window``."""

    def __init__(self, on_window: Callable[[float, float, list[tuple[float, str]], bool], None] | None,
                 window_seconds: int = WINDOW_SECONDS, settle: float = SETTLE_SECONDS,
                 trigger=TRIGGER_RE):
        self.on_window = on_window
        self.window = window_seconds
        self.settle = settle
        self.trigger = trigger
        self.pending: list[tuple[float, str]] = []
        self.audio = 0.0
        self.t_from = 0.0
        self.next_boundary = float(window_seconds)
        self.dispatched = 0
        self.triggered = 0

    def add(self, segment: tuple[float, str]) -> None:
        self.pending.append(segment)
        if (self.trigger is not None and self.trigger.search(segment[1])
                and self.audio - self.t_from >= TRIGGER_GAP_SECONDS):
            self.triggered += 1
            self._dispatch(self.audio, False)

    def advance(self, audio_seconds: float) -> None:
        self.audio = audio_seconds
        while audio_seconds >= self.next_boundary + self.settle:
            self._dispatch(self.next_boundary, False)

    def close(self) -> None:
        """Alles Ausstehende als letztes Fenster mit ``closing=True``."""
        self._dispatch(max(self.audio, self.t_from), True)

    def _dispatch(self, t_to: float, closing: bool) -> None:
        segs, self.pending = self.pending, []
        t_from = self.t_from
        if self.on_window is not None:
            try:
                self.on_window(t_from, t_to, segs, closing)
            except Exception:  # noqa: BLE001 — Live-Stand ist Zugabe
                log.exception("Live-Verfolgung für Fenster %.0f–%.0f s fehlgeschlagen", t_from, t_to)
        self.dispatched += 1
        self.t_from = t_to
        while self.next_boundary <= t_to:
            self.next_boundary += self.window


class _Link:
    """Eine Gladia-Sitzung: Websocket plus Leser-Thread, der fertige
    Äußerungen in eine Warteschlange legt. ``offset`` = Audio-Sekunden,
    die VOR dieser Sitzung gesendet wurden (Neuverbindung)."""

    def __init__(self, url: str, offset: float):
        self.ws = ws_client.connect(url, max_size=None, open_timeout=30)
        self.offset = offset
        self.queue: queue.Queue = queue.Queue()
        self.ended = threading.Event()
        self.failed: BaseException | None = None
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self) -> None:
        try:
            for raw in self.ws:
                seg = parse_transcript(raw)
                if seg:
                    self.queue.put((seg[0] + self.offset, seg[1] + self.offset, seg[2]))
                    continue
                try:
                    kind = json.loads(raw).get("type")
                except (json.JSONDecodeError, TypeError, AttributeError):
                    kind = None
                if kind == "error":
                    log.warning("Gladia meldet: %s", str(raw)[:300])
                if kind == "end_session":
                    break
        except BaseException as exc:  # noqa: BLE001 — wird im Hauptstrang gemeldet
            self.failed = exc
        finally:
            self.ended.set()

    def send(self, frame: bytes) -> None:
        self.ws.send(frame)

    def stop(self, wait: float = 30) -> None:
        try:
            self.ws.send(json.dumps({"type": "stop_recording"}))
        except Exception:  # noqa: BLE001
            pass
        self.ended.wait(wait)
        try:
            self.ws.close()
        except Exception:  # noqa: BLE001
            pass


def _retire(link: _Link, drain: Callable[[], None]) -> None:
    """Alte Sitzung ausklingen lassen: Nachzügler werden noch eingesammelt."""
    link.stop(30)
    drain()


def record_and_transcribe(on_window=None, source: str | None = None,
                          max_seconds: int | None = None, pace: float | None = None,
                          people: list[dict] | None = None,
                          window_seconds: int = WINDOW_SECONDS,
                          on_segment=None, stop: threading.Event | None = None) -> list[tuple[float, str]]:
    """Stream mitschneiden und streamend transkribieren, bis die
    Schlussformel fällt — die Streaming-Fassung von
    ``livestream.record_and_transcribe``.

    ``source`` ist die HLS-Adresse (Vorgabe ``livestream.STREAM_URL``) oder
    eine Datei; ``pace`` > 0 bremst eine Datei auf das Vielfache der
    Echtzeit (nur für Messungen — ein Live-Stream liefert von selbst in
    Echtzeit). ``on_window(t_from, t_to, segments, closing)`` je
    ``window_seconds`` und bei jedem Aufruf/jeder Worterteilung;
    ``on_segment(start, end, text)`` je fertiger Äußerung, sobald sie da ist
    (die Live-Probe im Admin-Panel); ``stop`` beendet die Aufnahme von außen.
    """
    vocab = vocabulary(people or [])
    url = open_session(vocab)  # wirft StreamUnavailable → Rückfall auf Stücke
    proc = ffmpeg_pcm(source or livestream.STREAM_URL)
    if proc is None or proc.stdout is None:
        return []
    limit = max_seconds or livestream.MAX_HOURS * 3600
    windower = Windower(on_window, window_seconds)
    segments: list[tuple[float, str]] = []
    link = _Link(url, 0.0)
    sent = 0.0
    session_started = 0.0
    closing = False
    t0 = time.monotonic()

    def drain() -> None:
        nonlocal closing
        while True:
            try:
                start, end, text = link.queue.get_nowait()
            except queue.Empty:
                return
            seg = (start, text)
            segments.append(seg)
            if on_segment is not None:
                try:
                    on_segment(start, end, text)
                except Exception:  # noqa: BLE001 — Zuschauer, kein Auftrag
                    log.exception("on_segment fehlgeschlagen")
            windower.add(seg)
            if livestream.closing_at(text, start):
                log.info("Schlussformel bei %.0f s — Aufnahme endet", start)
                closing = True

    try:
        while not closing and sent < limit and not (stop is not None and stop.is_set()):
            frame = proc.stdout.read(FRAME_BYTES)
            if not frame:
                break
            if link.failed is not None or link.ended.is_set():
                log.warning("Gladia-Verbindung abgerissen bei %.0f s — neu verbinden", sent)
                link.stop(2)
                link = _Link(open_session(vocab), sent)
                session_started = sent
            elif sent - session_started >= SESSION_MAX_SECONDS:
                # Erst die neue Sitzung, dann die alte im Hintergrund
                # schließen: Wer hier wartete, staute den Live-Stream in
                # der ffmpeg-Pipe und schöbe den Verzug um die Wartezeit.
                log.info("Gladia-Sitzungsgrenze bei %.0f s — neu verbinden", sent)
                old, link = link, _Link(open_session(vocab), sent)
                session_started = sent
                threading.Thread(target=_retire, args=(old, drain), daemon=True).start()
            link.send(frame)
            sent += FRAME_SECONDS
            drain()
            windower.advance(sent)
            if pace:
                behind = sent / pace - (time.monotonic() - t0)
                if behind > 0:
                    time.sleep(behind)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        link.stop(30)
        drain()
        windower.close()
    segments.sort(key=lambda s: s[0])
    log.info("Streaming beendet: %.0f s Audio, %d Segmente, %d Fenster (%d ausgelöst)",
             sent, len(segments), windower.dispatched, windower.triggered)
    return segments
