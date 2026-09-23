"""Ausgewählte Audio-Stücke des Sitzungs-Mitschnitts aufbewahren.

**Anlass.** ``eval/run_stt.py`` kann die Transkriptions-Qualität nicht
messen, weil nirgends Sitzungs-Audio liegt: Der Mitschnitt
(``scripts/record_council_livestream.py``) löscht seine Stücke bislang nach
jedem Lauf — absichtlich, damit ein abgebrochener Lauf keine alten Stücke in
einen Retry reicht (``council/livestream.py``). Tim hat am 23.09.2026
zugestimmt, je Sitzung eine kleine, feste Auswahl des öffentlichen
Livestream-Tons aufzuheben.

**Auswahl nach fester Regel**, nicht zufällig (reproduzierbar, s.
``select_indices``): die ersten zwei Stücke — Stille bzw. Vorprogramm vor
Sitzungsbeginn, der Mitschnitt startet ``LEAD_MINUTES`` früher — sind immer
dabei, der Rest gleichmäßig verteilt bis zur Obergrenze
``COUNCIL_STT_BEHALTEN`` (Vorgabe 20, ``0`` schaltet ab).

**Zwei Wege liefern Stücke unterschiedlich.** Läuft die Sitzung über den
Stück-Weg (``council/livestream.py``, ohne ``GLADIA_API_KEY`` oder als
Rückfall), gibt es echte 30-Sekunden-MP3s — ``retain`` kopiert direkt davon.
Läuft sie streamend über Gladia (``council/stream_stt.py``), gibt es keine
Stücke, nur laufend eintreffende Äußerungen; dafür schneidet
``retain_from_raw`` den mitgeschriebenen Rohton nachträglich mit ffmpeg in
gleich lange Stücke, bevor dieselbe Auswahl greift.

Neben jedem aufgehobenen Stück landet, was der PRODUKTIONSWEG tatsächlich
transkribiert hat (``<name>.<weg>.txt``, ``weg`` = ``chunks`` oder
``gladia``) — als Vergleichswert, nicht als Referenz. Die Referenz für die
Eval kommt aus ``eval/stt_referenz.py`` (YouTube-Untertitel derselben
Sitzung, als ``<name>.txt``).

**Kein Schreiben hier darf den laufenden Mitschnitt stören**: jeder Fehler
wird geloggt, nie geworfen — der Sitzungsabend gehört den Ergebnissen, nicht
der Eval.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

#: Wie viele Sitzungen aufgehoben bleiben — ältere fliegen beim nächsten Lauf
#: raus (nicht nach Alter der Dateien, sondern nach Anzahl der Sitzungen: so
#: bleibt der Speicherbedarf beschränkt, unabhängig vom Sitzungstakt).
SESSIONS_KEEP = 3


def _behalten() -> int:
    """``COUNCIL_STT_BEHALTEN`` — Stücke je Sitzung, ``0`` schaltet ab.
    Eine einzige Variable für „an" und „wie viele": ein zusätzlicher
    An/Aus-Schalter hätte nur widersprüchliche Zustände ermöglicht
    (an, aber Anzahl 0)."""
    try:
        return int(os.environ.get("COUNCIL_STT_BEHALTEN", "20"))
    except ValueError:
        log.warning("COUNCIL_STT_BEHALTEN keine Zahl — Vorgabe 20")
        return 20


def enabled() -> bool:
    return _behalten() > 0


def base_dir() -> Path:
    """Dieselbe Umgebungsvariable wie ``eval/run_stt.py::ordner()`` — sonst
    fände die Suite nicht, was hier abgelegt wird."""
    return Path(os.environ.get("RATSLOTSE_STT_AUDIO")
                or Path.home() / ".cache" / "ratslotse" / "stt")


def session_dir(ksinr: int) -> Path:
    return base_dir() / str(ksinr)


def select_indices(n: int, keep: int | None = None) -> list[int]:
    """Welche der ``n`` Stücke (Index 0..n-1) aufgehoben werden.

    Die ersten zwei sind IMMER dabei (Stille/Vorprogramm vor
    Sitzungsbeginn), der Rest gleichmäßig verteilt über die übrige Sitzung —
    „jedes n-te" statt der letzten oder ersten ``keep`` Stücke, damit die
    Auswahl die ganze Sitzung abdeckt (Anfang, Mitte, Ende)."""
    keep = _behalten() if keep is None else keep
    if n <= 0 or keep <= 0:
        return []
    lead = min(2, n, keep)
    chosen = list(range(lead))
    budget = keep - lead
    rest = n - lead
    if budget > 0 and rest > 0:
        step = max(1, rest // budget)
        i = lead
        while i < n and len(chosen) < keep:
            chosen.append(i)
            i += step
    return chosen[:keep]


def _cleanup_old(base: Path, keep_sessions: int = SESSIONS_KEEP) -> None:
    if not base.is_dir():
        return
    sitzungen = sorted(
        (d for d in base.iterdir() if d.is_dir()),
        key=lambda d: d.stat().st_mtime, reverse=True)
    for alt in sitzungen[keep_sessions:]:
        shutil.rmtree(alt, ignore_errors=True)


def retain(ksinr: int, weg: str, items: list[tuple[Path, str]]) -> None:
    """``items``: die Stücke der Sitzung in Reihenfolge, je (Pfad zum
    Audio-Stück, Text — was der laufende Weg dafür transkribiert hat).
    Kopiert die nach ``select_indices`` ausgewählten nach
    ``session_dir(ksinr)`` und räumt ältere Sitzungen weg. Wirft nie."""
    if not enabled() or not items:
        return
    try:
        gewaehlt = select_indices(len(items))
        if not gewaehlt:
            return
        dest = session_dir(ksinr)
        dest.mkdir(parents=True, exist_ok=True)
        kopiert = 0
        for idx in gewaehlt:
            path, text = items[idx]
            if not path.exists():
                continue
            target = dest / path.name
            shutil.copyfile(path, target)
            (dest / f"{target.stem}.{weg}.txt").write_text(text or "", encoding="utf-8")
            kopiert += 1
        log.info("STT-Aufbewahrung: %d/%d Stücke aus Sitzung %s (Weg %s) nach %s",
                 kopiert, len(items), ksinr, weg, dest)
        _cleanup_old(base_dir())
    except Exception:  # noqa: BLE001 — darf den Mitschnitt nie stören
        log.exception("STT-Aufbewahrung für Sitzung %s fehlgeschlagen", ksinr)


def retain_from_raw(ksinr: int, raw_pcm: Path, segments: list[tuple[float, str]],
                    weg: str = "gladia", chunk_seconds: int = 30,
                    sample_rate: int = 16_000) -> None:
    """Für den Streaming-Weg: Der mitgeschriebene Rohton (16-bit-PCM, mono,
    ``sample_rate``) hat keine Stück-Grenzen — die schneidet ffmpeg
    nachträglich, wie ``livestream.start_recording`` es beim Aufnehmen tut,
    dann greift dieselbe Auswahl (``retain``). Der Vergleichstext je Stück
    kommt aus den ``segments``, die Gladia für dieses Zeitfenster geliefert
    hat — nicht aus einer eigenen Transkription."""
    if not enabled():
        return
    try:
        from council import livestream
        exe = livestream.ffmpeg_bin()
        if not exe:
            log.warning("STT-Aufbewahrung: ffmpeg fehlt — Streaming-Stücke übersprungen")
            return
        out_dir = raw_pcm.parent / "stt-chunks"
        out_dir.mkdir(exist_ok=True)
        cmd = [exe, "-nostdin", "-y", "-loglevel", "error",
               "-f", "s16le", "-ar", str(sample_rate), "-ac", "1", "-i", str(raw_pcm),
               "-b:a", "32k", "-f", "segment", "-segment_time", str(chunk_seconds),
               "-reset_timestamps", "1", str(out_dir / "chunk_%03d.mp3")]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        chunks = sorted(out_dir.glob("chunk_*.mp3"))
        items = []
        for idx, path in enumerate(chunks):
            lo, hi = idx * chunk_seconds, (idx + 1) * chunk_seconds
            text = " ".join(t for s, t in segments if lo <= s < hi)
            items.append((path, text))
        retain(ksinr, weg, items)
        shutil.rmtree(out_dir, ignore_errors=True)
    except Exception:  # noqa: BLE001 — darf den Mitschnitt nie stören
        log.exception("STT-Aufbewahrung (Streaming) für Sitzung %s fehlgeschlagen", ksinr)
