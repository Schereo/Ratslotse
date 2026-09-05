"""Ratssitzung live aus dem O1-Stream mitschneiden und transkribieren.

oldenburg eins überträgt die Ratssitzung im eigenen TV-Stream —
selbst gehostetes HLS auf ``cdn.oeins.de``, vom Server frei abrufbar
(gemessen 01.09.2026: kein Token, kein Referer, kein Geo-Block). Damit
braucht der Weg zu den Abstimmungsergebnissen kein YouTube mehr: Die
YouTube-Untertitel waren nur der Umweg, und YouTube blockt Rechenzentrums-
IPs ohnehin hart (s. ``council/videos.py``).

Ablauf: ffmpeg nimmt den Stream als Mono-MP3 in kurzen Stücken auf
(Segment-Muxer, ``CHUNK_SECONDS``). Jedes fertige Stück wird noch WÄHREND der Aufnahme
transkribiert (Gemini nimmt Audio direkt, über den vorhandenen
OpenRouter-Stack); meldet ein Stück die Schlussformel der Sitzungsleitung,
stoppt die Aufnahme. Die Transkript-Segmente tragen Zeitmarken relativ zum
Aufnahmestart und gehen in dieselbe strenge Extraktion wie beim
YouTube-Weg (``videos.extract_results``).

Drei gemessene Fallen der Audio-Transkription:
- ``temperature=0`` lässt Gemini bei Audio in Wiederholungsschleifen
  kollabieren („so ein so ein so ein …", 90-s-Probe am 01.09.); mit 0.3
  war dieselbe Pipeline auf echtem Sitzungs-Audio ausgezeichnet. Der
  Loop-Wächter fängt Restfälle und wiederholt einmal wärmer.
- Ist im Stück KEINE Rede zur Sache (Warteschleife vor Sitzungsbeginn,
  Musik, Jingles), fabuliert Gemini — vom Prompt geprimt — eine komplette
  fiktive Ratssitzung bis ans Token-Limit (Live-Probe 01.09. im
  Morgenprogramm: 58.000 Zeichen aus 80 s Audio, erfundene Vergaben „aus
  Aichach"). Zwei mechanische Wächter dagegen: mehr als ~25 Zeichen je
  Audio-Sekunde ist keine Transkription, und Zeitmarken hinter dem
  Stück-Ende sind Fortschreibung — dort wird gekappt.
- Das statische johnvansickle-ffmpeg segfaultet auf der VM am
  MPEG-TS-Demux; das BtbN-Build (``~/bin/ffmpeg``) läuft.

Die Ergebnisse landen mit ``video_id=''`` in ``council_video_results`` —
das Frontend zeigt sie dann ohne Video-Sprung-Link. Sobald die
YouTube-Fassung verfügbar wird (Zubringer oder O1-Genehmigung), ersetzt
der YouTube-Lauf die Zeilen samt echten Video-Timestamps; das Protokoll
ersetzt später beides.
"""
from __future__ import annotations

import base64
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from kern import llm

log = logging.getLogger(__name__)

STREAM_URL = os.environ.get("COUNCIL_STREAM_URL",
                            "https://cdn.oeins.de/sd480/index.m3u8")
STT_MODEL = os.environ.get("COUNCIL_STT_MODEL", "google/gemini-2.5-flash")
#: Länge eines Audio-Stücks. Bis 09/2026 zehn Minuten — reichte für die
#: Abstimmungsergebnisse am Abend, nicht für „welcher TOP läuft gerade":
#: Die Live-Verfolgung (``council/livetracker.py``) sieht die Sitzung erst,
#: wenn ein Stück fertig ist, ihr Verzug ist also mindestens die Stücklänge.
#: Mit zwei Minuten liegt er bei ~2,5 Minuten (Stück + Transkription +
#: Tracker); die Transkription kostet je Audio-Minute dasselbe.
CHUNK_SECONDS = int(os.environ.get("COUNCIL_CHUNK_SECONDS", "120"))
#: Längste gemessene Ratssitzung (01.06.2026) lief 5 h — mit Luft.
MAX_HOURS = float(os.environ.get("COUNCIL_RECORD_MAX_HOURS", "6"))

#: Womit die Leitung den öffentlichen Teil beendet — danach ist im Stream
#: nichts mehr zu holen (nichtöffentlicher Teil läuft ohne Kamera).
CLOSING_RE = re.compile(
    # „schließe (ich) (hiermit/damit) den öffentlichen Teil / die Sitzung"
    r"schlie(?:ß|ss)e\s+(?:\w+\s+){0,2}d(?:ie|en)\s+(?:öffentliche[nr]?\s+"
    r"(?:Teil|Sitzung)|Sitzung)"
    # „der öffentliche Teil der (Rats)Sitzung ist (damit) (dann) geschlossen"
    # — die ASR verschreibt „Ratssitzung" gern (Ratsetzung/Ratsitzung),
    # deshalb hängt das Muster nicht am Wort selbst.
    r"|öffentliche[nr]?\s+Teil\s+(?:\w+\s+){0,3}ist\s+"
    r"(?:\w+\s+){0,2}geschlossen"
    r"|beende\s+die\s+(?:öffentliche\s+)?Sitzung",
    re.I)

TRANSCRIBE_PROMPT = (
    "Transkribiere diese Aufnahme einer deutschen Ratssitzung woertlich "
    "und vollstaendig. Beginne jeden Absatz mit einer Zeitmarke [mm:ss] "
    "relativ zum Anfang der Aufnahme, etwa alle 20-30 Sekunden. "
    "Nur das Transkript, kein Kommentar.")

_MARK_RE = re.compile(r"\[\s*(\d{1,2}):(\d{2})\s*\]")


def ffmpeg_bin() -> str | None:
    """``~/bin/ffmpeg`` (statisches BtbN-Build, ohne Root installierbar)
    vor dem PATH — bewusst keine requirements-Abhängigkeit."""
    cand = Path.home() / "bin" / "ffmpeg"
    if cand.exists():
        return str(cand)
    return shutil.which("ffmpeg")


def start_recording(dest_dir: Path, max_seconds: int | None = None) -> subprocess.Popen | None:
    """ffmpeg starten: Stream → Mono-MP3-Stücke à ``CHUNK_SECONDS``.

    Der Segment-Muxer schreibt ``chunk_000.mp3, chunk_001.mp3, …`` und
    macht jedes Stück fertig, sobald das nächste beginnt — die
    Transkription kann also parallel zur laufenden Aufnahme arbeiten."""
    exe = ffmpeg_bin()
    if not exe:
        log.warning("ffmpeg nicht installiert — Mitschnitt übersprungen "
                    "(statisches Build nach ~/bin/ffmpeg legen)")
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    cmd = [exe, "-nostdin", "-y", "-loglevel", "error", "-i", STREAM_URL,
           "-t", str(int(max_seconds or MAX_HOURS * 3600)),
           "-vn", "-ac", "1", "-b:a", "32k",
           "-f", "segment", "-segment_time", str(CHUNK_SECONDS),
           "-reset_timestamps", "1",
           str(dest_dir / "chunk_%03d.mp3")]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)


def _looks_looped(text: str) -> bool:
    """Der Gemini-Audio-Kollaps wiederholt eine kurze Phrase endlos —
    ein 6-Wort-Fenster, das mehr als zehnmal vorkommt, ist keine Rede."""
    words = text.split()
    if len(words) < 80:
        return False
    window = " ".join(words[len(words) // 2:len(words) // 2 + 6])
    return len(window) > 8 and text.count(window) > 10


#: Zügige deutsche Rede liegt bei ~15 Zeichen je Sekunde; alles deutlich
#: darüber ist fabuliert (gemessen: 58k Zeichen aus 80 s Musik = 725/s).
MAX_CHARS_PER_SECOND = 25


def audio_seconds(path: Path) -> float:
    """Dauer eines Mono-32k-MP3 aus der Dateigröße (32 kbit/s = 4000 B/s) —
    genau genug für die Plausibilitäts-Wächter, ohne ffprobe-Aufruf."""
    return path.stat().st_size / 4000


def _looks_fabricated(text: str, duration: float) -> bool:
    return duration > 0 and len(text) > max(400.0, duration * MAX_CHARS_PER_SECOND)


def transcribe_chunk(path: Path, attempt: int = 0) -> str:
    """Ein Audio-Stück → Transkript mit [mm:ss]-Marken ('' bei Ausfall)."""
    audio = base64.b64encode(path.read_bytes()).decode()
    resp = llm.chat_complete(
        model=STT_MODEL, _feature="livestream_transcript",
        _allow_empty_response=True,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": TRANSCRIBE_PROMPT},
            {"type": "input_audio",
             "input_audio": {"data": audio, "format": "mp3"}},
        ]}],
        # 0 kollabiert bei Audio in Wiederholungsschleifen (s. Docstring).
        temperature=0.3 if attempt == 0 else 0.6,
        max_tokens=16_000,
    )
    if not getattr(resp, "choices", None):
        if attempt < 2:
            return transcribe_chunk(path, attempt + 1)
        log.warning("Transkription %s: dreimal leere Antwort", path.name)
        return ""
    text = (resp.choices[0].message.content or "").strip()
    if _looks_looped(text):
        if attempt < 1:
            log.info("Transkription %s: Wiederholungsschleife, Retry wärmer",
                     path.name)
            return transcribe_chunk(path, attempt + 1)
        log.warning("Transkription %s: bleibt in der Schleife — verworfen",
                    path.name)
        return ""
    if _looks_fabricated(text, audio_seconds(path)):
        # Kein Retry: Wo keine Rede ist, wird jeder Versuch fabulieren
        # (Warteschleife vor Sitzungsbeginn, Musik). Das Stück fällt aus —
        # verpasst wird dadurch nichts.
        log.warning("Transkription %s: %d Zeichen aus %.0f s Audio — "
                    "fabuliert, verworfen", path.name, len(text),
                    audio_seconds(path))
        return ""
    return text


def parse_segments(text: str, chunk_offset: int,
                   chunk_seconds: float | None = None) -> list[tuple[float, str]]:
    """Transkript mit [mm:ss]-Marken → [(Sekunden seit Aufnahmestart, Absatz)].

    Ohne Marken (Modell hat die Anweisung ignoriert) trägt der ganze Text
    den Stück-Anfang — grob, aber die Extraktion braucht die Zeit nur für
    den Timestamp, nicht für die Zuordnung.

    Marken HINTER dem Stück-Ende (plus Toleranz) sind Fortschreibung über
    das Audio hinaus — ab dort wird gekappt (dritte Falle im Docstring)."""
    if not text:
        return []
    cutoff = (chunk_seconds + 30) if chunk_seconds else None
    parts = _MARK_RE.split(text)
    # split liefert [vorspann, mm, ss, text, mm, ss, text, ...]
    if len(parts) < 4:
        return _spread(text, chunk_offset, chunk_seconds)
    segments: list[tuple[float, str]] = []
    lead = parts[0].strip()
    if lead:
        segments.append((float(chunk_offset), lead))
    for i in range(1, len(parts) - 2, 3):
        mm, ss, body = int(parts[i]), int(parts[i + 1]), parts[i + 2].strip()
        mark = mm * 60 + ss
        if cutoff is not None and mark > cutoff:
            log.info("Zeitmarke %d:%02d hinter Stück-Ende — Rest gekappt", mm, ss)
            break
        if body:
            segments.append((chunk_offset + mark, body))
    return segments


def _spread(text: str, chunk_offset: int,
            chunk_seconds: float | None) -> list[tuple[float, str]]:
    """Text ohne Zeitmarken über das Stück verteilen — nach Zeichenanteil
    der Absätze. Grob, aber besser als alles auf die erste Sekunde zu legen
    (in 2 von 23 Stücken der Probe vom 31.08. fehlten die Marken ganz);
    für die Live-Verfolgung zählt, WANN im Stück etwas gesagt wurde."""
    paras = [p.strip() for p in re.split(r"\n+", text) if p.strip()]
    if not chunk_seconds or len(paras) < 2:
        return [(float(chunk_offset), text.strip())]
    total = sum(len(p) for p in paras) or 1
    out: list[tuple[float, str]] = []
    pos = 0
    for p in paras:
        out.append((chunk_offset + chunk_seconds * pos / total, p))
        pos += len(p)
    return out


def record_and_transcribe(dest_dir: Path,
                          max_seconds: int | None = None,
                          poll_seconds: int = 20,
                          on_chunk=None) -> list[tuple[float, str]]:
    """Aufnehmen + parallel transkribieren, bis die Schlussformel fällt.

    Gibt die Transkript-Segmente der ganzen Sitzung zurück (für
    ``videos.extract_results``). Ein Stück gilt als fertig, sobald sein
    Nachfolger existiert — das letzte, sobald ffmpeg beendet ist.

    ``on_chunk(idx, segments, closing)`` wird je fertigem Stück gerufen,
    mit dessen Segmenten und ob die Schlussformel darin fiel — der Haken
    für die Live-Verfolgung. Ein Fehler darin bricht die Aufnahme NICHT ab:
    Der Live-Stand ist Zugabe, die Ergebnisse am Abend sind der Auftrag."""
    proc = start_recording(dest_dir, max_seconds)
    if proc is None:
        return []
    segments: list[tuple[float, str]] = []
    done: set[int] = set()
    closing = False
    exit_code: int | None = None
    try:
        while True:
            exit_code = proc.poll()
            running = exit_code is None
            chunks = sorted(dest_dir.glob("chunk_*.mp3"))
            for idx, path in enumerate(chunks):
                finished = (idx < len(chunks) - 1) or not running
                if idx in done or not finished:
                    continue
                done.add(idx)
                text = transcribe_chunk(path)
                chunk_segments = parse_segments(text, idx * CHUNK_SECONDS,
                                                audio_seconds(path))
                segments.extend(chunk_segments)
                log.info("Stück %d transkribiert (%d Zeichen)", idx, len(text))
                if CLOSING_RE.search(text):
                    log.info("Schlussformel im Stück %d — Aufnahme endet", idx)
                    closing = True
                if on_chunk is not None:
                    try:
                        on_chunk(idx, chunk_segments, closing)
                    except Exception:  # noqa: BLE001 — Live-Stand ist Zugabe
                        log.exception("Live-Verfolgung für Stück %d fehlgeschlagen", idx)
            if closing and running:
                proc.terminate()
            if not running and len(done) >= len(chunks):
                break
            time.sleep(poll_seconds)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
    # Eine erkannte Schlussformel beendet ffmpeg absichtlich per SIGTERM.
    # Jeder andere Fehler muss den Cron-Lauf fehlschlagen lassen: Ein still
    # akzeptierter Teilmitschnitt würde unvollständige Ergebnisse veröffentlichen
    # und in Kombination mit alten Chunks wie ein erfolgreicher Retry wirken.
    if exit_code not in (None, 0) and not closing:
        raise RuntimeError(
            f"ffmpeg-Aufnahme mit Exitcode {exit_code} abgebrochen "
            f"({len(done)} fertige Stücke)"
        )
    return segments
