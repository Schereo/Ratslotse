"""Die Sitzungs-Transkripte, gegen die Video- und Live-Suite messen.

**Warum ein Zwischenspeicher außerhalb des Repos.** Die Suiten
``video-ergebnisse`` und ``live-verfolgung`` brauchen das Transkript einer
ganzen Ratssitzung. Gespeichert wird im Betrieb keins: Der Mitschnitt löscht
seine Audio-Stücke nach dem Lauf (``scripts/record_council_livestream.py``),
und der YouTube-Weg liest die Untertitel in ein temporäres Verzeichnis. Die
Untertitel sind O1s Aufzeichnung, nicht unsere — sie gehören nicht in ein
öffentliches Repo. Sie liegen deshalb in ``~/.cache/ratslotse/transkripte``
(wie der Datenabzug, von allen Worktrees geteilt), und die Fälle nennen nur
Sitzung, Video und Sekunden.

Holen, einmal je Rechner::

    python eval/transkripte.py

YouTube sperrt Rechenzentrums-Adressen; auf dem Server geht das nur mit
``RATSLOTSE_PROXY_*`` (``kern/proxy.py``), am Arbeitsplatz ohne. yt-dlp liegt
bewusst nicht in ``requirements.txt`` (``council/videos.py``):
``.venv/bin/pip install yt-dlp``.

**Die Untertitel sind nicht das Audio des Betriebs.** Im Mitschnitt
transkribiert Gemini das O1-Audio; hier liest die Suite YouTubes
Auto-Untertitel derselben Sitzung. Beide verschlucken Punkte in TOP-Nummern
(„141" für 14.1) und verschreiben Namen — die Fallen, auf die die Prompts
eingestellt sind, stecken in beiden. Für den Modellvergleich zählt, dass alle
Kandidaten denselben Text bekommen.
"""
from __future__ import annotations

import os
from pathlib import Path

#: Sitzung → YouTube-Video. Nur Sitzungen, zu denen es eine Niederschrift gibt
#: (die Video-Suite misst gegen deren Ergebnisse). Die Ratssitzung vom
#: 13.04.2026 (``H1etSOmOtEQ``) hat keine Untertitel.
SITZUNGEN: dict[int, str] = {
    4695: "ogs6D7Qdh60",   # Rat 29.06.2026
    4692: "OZ2OUkwR6e0",   # Rat 01.06.2026
    4628: "5SNPSh0EI94",   # Rat 16.03.2026
}


def ordner() -> Path:
    return Path(os.environ.get("RATSLOTSE_TRANSKRIPTE")
                or Path.home() / ".cache" / "ratslotse" / "transkripte")


def pfad(video_id: str) -> Path:
    return ordner() / f"{video_id}.de-orig.json3"


def fehlend(video_ids: list[str] | None = None) -> str | None:
    """``None`` = alle da; sonst der Grund für den Bericht."""
    ids = video_ids if video_ids is not None else list(SITZUNGEN.values())
    fehlt = [v for v in ids if not pfad(v).exists()]
    if not fehlt:
        return None
    return (f"braucht die YouTube-Untertitel der Ratssitzungen in {ordner()} "
            f"(fehlen: {', '.join(fehlt)}; holen mit `python eval/transkripte.py`)")


def laden(video_id: str) -> list[tuple[float, str]]:
    """[(Sekunden, Text)] — derselbe Leser wie im Betrieb, ohne Abruf."""
    from council import videos
    if not pfad(video_id).exists():
        raise FileNotFoundError(fehlend([video_id]))
    segmente = videos.fetch_transcript(video_id, ordner())
    if not segmente:
        raise ValueError(f"{pfad(video_id)} enthält keine Untertitel")
    return segmente


def holen() -> int:
    from council import videos
    ordner().mkdir(parents=True, exist_ok=True)
    rot = 0
    for ksinr, vid in SITZUNGEN.items():
        seg = videos.fetch_transcript(vid, ordner())
        print(f"  {ksinr} {vid}: {len(seg) if seg else 'KEINE'} Segmente")
        rot |= not seg
    return 1 if rot else 0


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(holen())
