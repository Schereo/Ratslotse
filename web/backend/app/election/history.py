"""Der Verlauf des Wahlabends — ein Punkt je Stand, über den Deploy hinweg.

Der Votemanager liefert immer nur den JETZIGEN Stand; „wie stand es um
19:30?" beantwortet keine seiner CSVs. Also schreibt der Dienst sich den
Verlauf selbst mit: nach jedem Zusammensetzen des Live-Bildes ein Punkt —
aber nur, wenn er etwas Neues sagt. Ein Abend, an dem alle 60 Sekunden
dasselbe Bild entsteht, soll keine 600 gleichen Punkte tragen.

Warum eine Datei und nicht nur der Speicher: Ein Deploy startet den Dienst
neu, und ein Wahlabend, dessen Verlauf dabei verschwindet, ist keiner. Die
Datei liegt unter ``data/`` (gitignored), verlegen lässt sie sich über
``WAHLABEND_HISTORY_FILE``. Sie ist Bequemlichkeit, keine Zusage: Ist der
Pfad nicht schreibbar, wird das einmal geloggt und der Abend läuft im
Speicher weiter — ein kaputter Pfad darf den Endpunkt nicht umbringen.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

from ..antworten import ElectionHistoryPoint, ElectionNight

#: Repo-Wurzel: web/backend/app/election/ -> vier Ebenen hoch.
ROOT = Path(__file__).resolve().parents[4]
#: Obergrenze. Ein Wahlabend ist keine 24 Stunden lang; die ältesten fliegen raus.
MAX_POINTS = 1_440

_log = logging.getLogger("ratslotse.web.wahlabend")
#: Erneuert wird im Hintergrund-Thread (``service.live``), gelesen im Request.
_lock = threading.RLock()
_points: list[ElectionHistoryPoint] = []
#: Der Pfad, aus dem ``_points`` stammt — ``None``: noch nichts geladen.
_loaded: Path | None = None
_write_warned = False


def path() -> Path:
    """Wohin der Verlauf geschrieben wird."""
    override = os.environ.get("WAHLABEND_HISTORY_FILE")
    return Path(override) if override else ROOT / "data" / "wahlabend-verlauf.json"


# ------------------------------------------------------------------ Datei

def _point_from(raw: Any) -> ElectionHistoryPoint | None:
    """Ein Punkt aus der Datei — oder ``None``, wenn die Zeile nicht passt.
    Eine halb geschriebene Datei soll den Abend nicht anhalten."""
    if not isinstance(raw, dict):
        return None
    at, counted = raw.get("at"), raw.get("districts_counted")
    shares, seats = raw.get("shares"), raw.get("seats")
    if not isinstance(at, str) or not isinstance(counted, int) or isinstance(counted, bool):
        return None
    if not isinstance(shares, dict) or not isinstance(seats, dict):
        return None
    return ElectionHistoryPoint(
        at=at,
        districts_counted=counted,
        shares={str(k): float(v) for k, v in shares.items() if isinstance(v, (int, float))},
        seats={str(k): int(v) for k, v in seats.items() if isinstance(v, int)},
    )


def _load() -> None:
    """Beim ersten Zugriff — und nach einem Pfadwechsel — die Datei lesen."""
    global _points, _loaded
    file = path()
    if _loaded == file:
        return
    _loaded, _points = file, []
    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return
    except (OSError, ValueError) as e:
        _log.warning("Wahlabend-Verlauf %s ist nicht lesbar (%s) — der Abend beginnt im Speicher.", file, e)
        return
    if isinstance(raw, list):
        _points = [p for p in (_point_from(r) for r in raw) if p is not None][-MAX_POINTS:]


def _save() -> None:
    """Erst daneben schreiben, dann umbenennen — ein Absturz mittendrin darf
    keine halbe Datei hinterlassen."""
    global _write_warned
    file = path()
    tmp = file.with_name(f"{file.name}.{os.getpid()}.tmp")
    try:
        file.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(_points, ensure_ascii=False), encoding="utf-8")
        tmp.replace(file)
        _write_warned = False
    except OSError as e:
        if not _write_warned:  # einmal warnen, nicht einmal je Minute
            _write_warned = True
            _log.warning("Wahlabend-Verlauf %s ist nicht schreibbar (%s) — er läuft nur im Speicher weiter.", file, e)
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


# ------------------------------------------------------------------ Punkte

def points() -> list[ElectionHistoryPoint]:
    """Der ganze Verlauf, ältester Punkt zuerst."""
    with _lock:
        _load()
        return list(_points)


def from_night(night: ElectionNight, at: str | None = None) -> ElectionHistoryPoint:
    """Der Auszug eines fertigen Bildes: Stand, Anteile, Sitze."""
    shares: dict[str, float] = {}
    seats: dict[str, int] = {}
    for p in night["parties"]:
        votes, share, seat = p["votes"], p["share_pct"], p["seats"]
        if votes and votes > 0 and share is not None:
            shares[p["slug"]] = share
        if seat:
            seats[p["slug"]] = seat
    return ElectionHistoryPoint(
        at=at or night["computed_at"],
        districts_counted=night["progress"]["districts_counted"],
        shares=shares,
        seats=seats,
    )


def _same(a: ElectionHistoryPoint, b: ElectionHistoryPoint) -> bool:
    """Gleich heißt: derselbe Stand — die Uhrzeit zählt nicht mit."""
    return (a["districts_counted"] == b["districts_counted"]
            and a["shares"] == b["shares"] and a["seats"] == b["seats"])


def add(point: ElectionHistoryPoint) -> list[ElectionHistoryPoint]:
    """Anhängen, wenn sich etwas geändert hat; sonst bleibt alles, wie es ist."""
    with _lock:
        _load()
        if _points and _same(_points[-1], point):
            return list(_points)
        _points.append(point)
        del _points[:-MAX_POINTS]
        _save()
        return list(_points)


def record(night: ElectionNight) -> list[ElectionHistoryPoint]:
    """Den Punkt eines Live-Bildes anhängen und den ganzen Verlauf liefern.

    Vor der Auszählung gibt es nichts anzuhängen — ein Nachmittag voller
    Nullstände wäre kein Verlauf."""
    if night["phase"] == "before":
        return points()
    return add(from_night(night))


def reset() -> None:
    """Speicher leeren und beim nächsten Zugriff neu laden (Tests,
    ``service.reset``)."""
    global _points, _loaded, _write_warned
    with _lock:
        _points, _loaded, _write_warned = [], None, False
