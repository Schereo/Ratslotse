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
Stücke, nur laufend eintreffende Äußerungen. Dort steht die Auswahl deshalb
schon VOR der Aufnahme fest (``planned_indices``, an die Sitzungs-Obergrenze
gedeckelt) — nur die ausgewählten Fenster werden während der Aufnahme in eine
eigene kleine Rohton-Datei je Fenster gepuffert, alles andere wird sofort
verworfen. Am Ende schneidet ``finalize_streaming_chunks`` diese wenigen
Dateien mit ffmpeg zu MP3, dann greift dieselbe Auswahl (``retain``). Eine
frühere Fassung schrieb den GANZEN Rohton mit (bei 6 h ~690 MB) und wählte
erst danach aus — auf demselben Server-Datenträger, der schon einmal durch
Release-Snapshots vollgelaufen war, ein unnötiges Risiko (Review-Befund
24.09.2026). ``STREAM_KEEP_CAP`` deckelt den Speicherbedarf zusätzlich gegen
eine zu hoch gesetzte ``COUNCIL_STT_BEHALTEN``.

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
import math
import os
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

#: Wie viele Sitzungen aufgehoben bleiben — ältere fliegen beim nächsten Lauf
#: raus (nicht nach Alter der Dateien, sondern nach Anzahl der Sitzungen: so
#: bleibt der Speicherbedarf beschränkt, unabhängig vom Sitzungstakt).
SESSIONS_KEEP = 3

#: Obergrenze für den Streaming-Weg (``planned_indices``), UNABHÄNGIG von
#: ``COUNCIL_STT_BEHALTEN``: Dort wird für jedes geplante Fenster eine eigene
#: Rohton-Datei WÄHREND der Aufnahme gepuffert (16 kHz·16-bit·mono =
#: 32 kB/s·30 s ≈ 960 KB je Fenster). Ohne diesen Deckel könnte eine hoch
#: gesetzte Konfiguration die Aufbewahrung selbst wieder zum Plattenfüller
#: machen — mit 40 Fenstern sind es höchstens ~38 MB gleichzeitig.
STREAM_KEEP_CAP = 40


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


def planned_indices(max_seconds: float, chunk_seconds: int, keep: int | None = None) -> set[int]:
    """Welche Fenster-Indizes eine höchstens ``max_seconds`` lange Sitzung
    aufheben wird — berechnet VOR der Aufnahme (der Streaming-Weg kennt keine
    fertigen Stücke, um erst danach auszuwählen). ``keep`` wird zusätzlich an
    ``STREAM_KEEP_CAP`` gedeckelt, damit das Mitschreiben selbst bei einer
    hoch gesetzten ``COUNCIL_STT_BEHALTEN`` beschränkt bleibt.

    Da die Sitzung meist kürzer endet als ``max_seconds`` (Schlussformel vor
    der Kappungsgrenze), bleiben manche geplanten Indizes ungenutzt — das ist
    beabsichtigt: Die Auswahl deckt den WORST CASE ab, nicht den Regelfall."""
    if not enabled() or max_seconds <= 0 or chunk_seconds <= 0:
        return set()
    keep = min(_behalten() if keep is None else keep, STREAM_KEEP_CAP)
    n_max = max(1, math.ceil(max_seconds / chunk_seconds))
    return set(select_indices(n_max, keep))


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


def finalize_streaming_chunks(ksinr: int, raw_dir: Path, segments: list[tuple[float, str]],
                              weg: str = "gladia", chunk_seconds: int = 30,
                              sample_rate: int = 16_000) -> None:
    """Für den Streaming-Weg: ``raw_dir`` enthält NUR die bereits während der
    Aufnahme ausgewählten Fenster (``planned_indices``), je eine kleine
    ``chunk_NNN.pcm``-Datei (16-bit-PCM, mono, ``sample_rate``) — hier wird
    jede einzeln zu MP3 geschnitten, dann greift dieselbe Auswahl noch einmal
    (``retain``; sie verändert nichts mehr, weil schon vorausgewählt wurde).
    Der Vergleichstext je Stück kommt aus den ``segments``, die Gladia für
    dieses Zeitfenster geliefert hat — nicht aus einer eigenen
    Transkription."""
    if not enabled():
        return
    try:
        from council import livestream
        exe = livestream.ffmpeg_bin()
        if not exe:
            log.warning("STT-Aufbewahrung: ffmpeg fehlt — Streaming-Stücke übersprungen")
            return
        items: list[tuple[Path, str]] = []
        for pcm in sorted(raw_dir.glob("chunk_*.pcm")):
            idx = int(pcm.stem.split("_")[1])
            mp3 = raw_dir / f"{pcm.stem}.mp3"
            cmd = [exe, "-nostdin", "-y", "-loglevel", "error",
                   "-f", "s16le", "-ar", str(sample_rate), "-ac", "1", "-i", str(pcm),
                   "-b:a", "32k", str(mp3)]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            lo, hi = idx * chunk_seconds, (idx + 1) * chunk_seconds
            text = " ".join(t for s, t in segments if lo <= s < hi)
            items.append((mp3, text))
        retain(ksinr, weg, items)
    except Exception:  # noqa: BLE001 — darf den Mitschnitt nie stören
        log.exception("STT-Aufbewahrung (Streaming) für Sitzung %s fehlgeschlagen", ksinr)
