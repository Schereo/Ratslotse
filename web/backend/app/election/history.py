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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..antworten import ElectionHistoryPoint, ElectionNight, MayorHistoryPoint, MayorLeadChange, MayorNight

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
#: Der Verlauf einer Mehrheitswahl (Stichwahl), je Wahl-Slug: Pfad und Punkte.
_mayor: dict[str, tuple[Path, list[MayorHistoryPoint]]] = {}


def path() -> Path:
    """Wohin der Verlauf geschrieben wird — eine Datei JE WAHL.

    Bis 09/2026 hieß sie für alle Zeiten ``wahlabend-verlauf.json``. Zwei
    Wahlabende hintereinander hätten sich damit dieselbe Datei geteilt, und
    der zweite hätte an die Punkte des ersten angehängt: eine Kurve, die
    mitten in der Nacht von 133 ausgezählten Bezirken auf null zurückspringt.
    Der Verlauf des 13.09.2026 liegt eingefroren in
    ``kommunalwahl/referenz-2026/verlauf.json``.
    """
    override = os.environ.get("WAHLABEND_HISTORY_FILE")
    if override:
        return Path(override)
    from . import elections
    return ROOT / "data" / f"wahlabend-verlauf-{elections.active().slug}.json"


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


def _umzug(ziel: Path) -> None:
    """Die namenlose Datei von vor 09/2026 auf ihren Wahl-Namen ziehen.

    Auf Prod liegt der Verlauf des 13.09.2026 als ``wahlabend-verlauf.json``;
    ohne diesen Schritt liefe die Seite nach dem Deploy mit leerer Kurve
    weiter — kein Fehler, keine Meldung, nur ein verschwundener Abend.
    Idempotent, und der Schritt darf verschwinden, sobald alle Umgebungen
    einmal gestartet sind (dasselbe Muster wie ``store._umzug_von_nwz``).
    """
    alt = ziel.with_name("wahlabend-verlauf.json")
    if ziel.exists() or not alt.is_file():
        return
    try:
        alt.replace(ziel)
        _log.warning("Wahlabend-Verlauf umgezogen: %s -> %s", alt.name, ziel.name)
    except OSError as e:
        _log.warning("Wahlabend-Verlauf %s ließ sich nicht auf %s umziehen (%s).", alt.name, ziel.name, e)


def _load() -> None:
    """Beim ersten Zugriff — und nach einem Pfadwechsel — die Datei lesen."""
    global _points, _loaded
    file = path()
    _umzug(file)
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
    _write(path(), _points)


def _write(file: Path, rows: list[Any]) -> None:
    """Erst daneben schreiben, dann umbenennen — ein Absturz mittendrin darf
    keine halbe Datei hinterlassen."""
    global _write_warned
    tmp = file.with_name(f"{file.name}.{os.getpid()}.tmp")
    try:
        file.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
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
        _mayor.clear()


# ------------------------------------------------------------------ Stichwahl (docs/plan-stichwahl-spannung.md S3)
#
# Dieselbe Datei-Logik, ein anderer Punkt: Eine Mehrheitswahl hat keine Sitze,
# dafür eine Hochrechnung und eine Chance — und die Frage des Abends, wer
# vorn liegt. Je Wahl-Slug eine Datei; die Stichwahl heißt anders als die
# Ratswahl, also teilen sich die beiden Abende nichts.

def mayor_path(slug: str) -> Path:
    override = os.environ.get("WAHLABEND_HISTORY_FILE")
    if override:
        o = Path(override)
        return o.with_name(f"{o.stem}-{slug}{o.suffix or '.json'}")
    return ROOT / "data" / f"wahlabend-verlauf-{slug}.json"


def _mayor_point_from(raw: Any) -> MayorHistoryPoint | None:
    if not isinstance(raw, dict):
        return None
    at, n = raw.get("at"), raw.get("reports_received")
    if not isinstance(at, str) or not isinstance(n, int) or isinstance(n, bool):
        return None
    shares, proj = raw.get("shares"), raw.get("projected_shares")
    if not isinstance(shares, dict) or not isinstance(proj, dict):
        return None
    votes_raw = raw.get("votes")
    votes: dict[Any, Any] = votes_raw if isinstance(votes_raw, dict) else {}
    chance = raw.get("chance_pct")
    leader = raw.get("leader")
    return MayorHistoryPoint(
        at=at, reports_received=n,
        shares={str(k): float(v) for k, v in shares.items() if isinstance(v, (int, float))},
        votes={str(k): int(v) for k, v in votes.items() if isinstance(v, int) and not isinstance(v, bool)},
        projected_shares={str(k): float(v) for k, v in proj.items() if isinstance(v, (int, float))},
        chance_pct=int(chance) if isinstance(chance, int) and not isinstance(chance, bool) else None,
        leader=leader if isinstance(leader, str) else None,
    )


def _mayor_store(slug: str) -> list[MayorHistoryPoint]:
    """Die Punkte dieser Wahl — beim ersten Zugriff (und nach einem
    Pfadwechsel) aus der Datei."""
    file = mayor_path(slug)
    gemerkt = _mayor.get(slug)
    if gemerkt and gemerkt[0] == file:
        return gemerkt[1]
    rows: list[MayorHistoryPoint] = []
    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raw = []
    except (OSError, ValueError) as e:
        _log.warning("Stichwahl-Verlauf %s ist nicht lesbar (%s) — der Abend beginnt im Speicher.", file, e)
        raw = []
    if isinstance(raw, list):
        rows = [p for p in (_mayor_point_from(r) for r in raw) if p is not None][-MAX_POINTS:]
    _mayor[slug] = (file, rows)
    return rows


def mayor_points(slug: str) -> list[MayorHistoryPoint]:
    with _lock:
        return list(_mayor_store(slug))


def mayor_leader(shares: dict[str, float], votes: dict[str, int | None]) -> str | None:
    """Wer vorn liegt — nach Stimmen, ``None`` bei Gleichstand oder ohne."""
    mit = [(v, slug) for slug, v in votes.items() if v is not None and v > 0]
    if not mit:
        return None
    mit.sort(reverse=True)
    if len(mit) > 1 and mit[0][0] == mit[1][0]:
        return None
    return mit[0][1]


def from_mayor_night(night: MayorNight, at: str | None = None) -> MayorHistoryPoint:
    """Der Auszug eines fertigen Standes: Ist, Hochrechnung, Chance, Führung."""
    shares = {c["slug"]: c["share_pct"] for c in night["candidates"]
              if c["votes"] and c["votes"] > 0 and c["share_pct"] is not None}
    proj = night.get("projection")
    return MayorHistoryPoint(
        at=at or night["fetched_at"] or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        reports_received=night["reports_received"],
        shares=shares,
        votes={c["slug"]: c["votes"] for c in night["candidates"] if c["votes"] is not None},
        projected_shares=dict(proj["shares"]) if proj else {},
        chance_pct=proj["chance_pct"] if proj else None,
        leader=mayor_leader(shares, {c["slug"]: c["votes"] for c in night["candidates"]}),
    )


def _mayor_same(a: MayorHistoryPoint, b: MayorHistoryPoint) -> bool:
    """Gleich heißt: derselbe Stand — die Uhrzeit zählt nicht mit. Die
    Hochrechnung zählt mit: Sie ändert sich nur, wenn sich ein Bezirk ändert."""
    return (a["reports_received"] == b["reports_received"] and a["shares"] == b["shares"]
            and a["projected_shares"] == b["projected_shares"])


def add_mayor(slug: str, point: MayorHistoryPoint) -> list[MayorHistoryPoint]:
    with _lock:
        rows = _mayor_store(slug)
        if rows and _mayor_same(rows[-1], point):
            return list(rows)
        rows.append(point)
        del rows[:-MAX_POINTS]
        _write(mayor_path(slug), rows)
        return list(rows)


def record_mayor(slug: str, night: MayorNight) -> list[MayorHistoryPoint]:
    """Den Punkt eines Live-Standes anhängen und den Verlauf liefern; vor
    der Auszählung nur lesen."""
    if night["phase"] == "before" or night["reports_received"] <= 0:
        return mayor_points(slug)
    return add_mayor(slug, from_mayor_night(night))


def lead_changes(points: list[MayorHistoryPoint]) -> list[MayorLeadChange]:
    """Wo zwischen zwei Ständen wechselte, wer vorn liegt. Ein Gleichstand
    dazwischen zählt nicht als Wechsel — erst der nächste Stand mit einer
    Führung entscheidet, ob sie eine andere ist."""
    out: list[MayorLeadChange] = []
    vorher: str | None = None
    for p in points:
        leader = p["leader"]
        if leader is None:
            continue
        if vorher is not None and leader != vorher:
            out.append(MayorLeadChange(at=p["at"], reports_received=p["reports_received"],
                                       leader=leader, previous=vorher))
        vorher = leader
    return out
