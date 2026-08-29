"""Persistente öffentliche Projektion des kommunalen Problemtrackers."""
from __future__ import annotations

import ipaddress
import json
import math
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from .domain import PROBLEM_CATEGORIES, PROBLEM_STATUSES, PUBLIC_SOURCE_KINDS, SCOPE_KINDS
from .schema import sql_enum


def _is_public_http_url(value: object) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or any(char.isspace() for char in value)
        or "\\" in value
    ):
        return False
    try:
        parsed = urlparse(value)
        _ = parsed.port  # Invalid port syntax raises ValueError.
        host = parsed.hostname
        if host is None or parsed.username is not None or parsed.password is not None:
            return False
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            ascii_host = host.encode("idna").decode("ascii")
            labels = ascii_host.rstrip(".").split(".")
            valid_host = (
                len(labels) >= 2
                and len(ascii_host) <= 253
                and all(
                    0 < len(label) <= 63
                    and re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", label)
                    for label in labels
                )
            )
        else:
            valid_host = address.is_global
    except (UnicodeError, ValueError):
        return False
    return parsed.scheme.lower() in {"http", "https"} and valid_host


def _invalid_public_source(prefix: str = "") -> str:
    source_kind = f"{prefix}source_kind"
    source_url = f"{prefix}source_url"
    return f"""(
        {source_kind} IS NULL
        OR {source_kind} NOT IN ({sql_enum(PUBLIC_SOURCE_KINDS)})
        OR ({source_kind} != 'Ratslotse-Prüfung' AND {source_url} IS NULL)
        OR ({source_url} IS NOT NULL AND valid_public_http_url({source_url}) = 0)
    )"""


SCHEMA = f"""
CREATE TABLE IF NOT EXISTS civic_problems (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    title               TEXT NOT NULL,
    summary             TEXT NOT NULL,
    category            TEXT NOT NULL,
    tags_json            TEXT NOT NULL DEFAULT '[]',
    scope_kind           TEXT NOT NULL,
    location_label       TEXT NOT NULL DEFAULT '',
    latitude             REAL,
    longitude            REAL,
    geometry_json        TEXT,
    status               TEXT NOT NULL DEFAULT 'new',
    confidence           TEXT NOT NULL DEFAULT 'unconfirmed',
    unique_reporters     INTEGER NOT NULL DEFAULT 0,
    current_observations INTEGER NOT NULL DEFAULT 0,
    total_observations   INTEGER NOT NULL DEFAULT 0,
    first_observed_at    TEXT NOT NULL,
    last_observed_at     TEXT NOT NULL,
    published_at         TEXT,
    updated_at           TEXT NOT NULL,
    CHECK (category IN ({sql_enum(PROBLEM_CATEGORIES)})),
    CHECK (scope_kind IN ({sql_enum(SCOPE_KINDS)})),
    CHECK (status IN ({sql_enum(PROBLEM_STATUSES)})),
    CHECK (confidence IN ('unconfirmed', 'supported', 'verified')),
    CHECK (unique_reporters >= 0),
    CHECK (published_at IS NULL OR unique_reporters >= 1),
    CHECK (current_observations >= 0),
    CHECK (total_observations >= current_observations),
    CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
    CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180)
);
CREATE INDEX IF NOT EXISTS idx_civic_problems_public
    ON civic_problems(published_at, last_observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_civic_problems_category
    ON civic_problems(category, published_at);

CREATE TRIGGER IF NOT EXISTS trg_civic_problems_create_private
BEFORE INSERT ON civic_problems
WHEN NEW.published_at IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'problems must be created unpublished');
END;
CREATE TRIGGER IF NOT EXISTS trg_civic_problems_human_publication_gate
BEFORE UPDATE OF published_at ON civic_problems
WHEN OLD.published_at IS NULL
     AND NEW.published_at IS NOT NULL
     AND NOT EXISTS (
         SELECT 1
         FROM civic_reports AS report
         JOIN civic_moderation_decisions AS decision
           ON decision.report_id = report.id
          AND decision.problem_id = NEW.id
         JOIN civic_ai_assessments AS assessment
           ON assessment.id = decision.ai_assessment_id
          AND assessment.report_id = report.id
         WHERE report.problem_id = NEW.id
           AND report.status = 'accepted'
           AND assessment.verdict = 'suitable'
           AND assessment.report_revision = report.content_revision
           AND decision.outcome IN ('assigned_existing_problem', 'approved_for_new_problem')
     )
BEGIN
    SELECT RAISE(ABORT, 'publication requires AI assessment and human approval');
END;

CREATE TABLE IF NOT EXISTS civic_problem_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id  INTEGER NOT NULL,
    kind        TEXT NOT NULL,
    title       TEXT NOT NULL,
    detail      TEXT NOT NULL DEFAULT '',
    source_kind TEXT,
    source_url  TEXT,
    event_at    TEXT NOT NULL,
    published_at TEXT,
    FOREIGN KEY (problem_id) REFERENCES civic_problems(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_civic_problem_events_public
    ON civic_problem_events(problem_id, published_at, event_at DESC);

CREATE TRIGGER IF NOT EXISTS trg_civic_problem_events_public_source_insert
BEFORE INSERT ON civic_problem_events
WHEN NEW.published_at IS NOT NULL AND {_invalid_public_source("NEW.")}
BEGIN
    SELECT RAISE(ABORT, 'invalid public event source');
END;
CREATE TRIGGER IF NOT EXISTS trg_civic_problem_events_public_source_update
BEFORE UPDATE OF source_kind, source_url, published_at ON civic_problem_events
WHEN NEW.published_at IS NOT NULL AND {_invalid_public_source("NEW.")}
BEGIN
    SELECT RAISE(ABORT, 'invalid public event source');
END;
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def report_frequency(independent_reports: int) -> str:
    if independent_reports < 1:
        raise ValueError("Veröffentlichte Probleme benötigen mindestens eine Meldung.")
    if independent_reports == 1:
        return "once"
    if independent_reports <= 4:
        return "several"
    if independent_reports <= 9:
        return "many"
    return "very_many"


def _is_finite_number(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
    )


def _is_coordinate(value: object, minimum: float, maximum: float) -> bool:
    return _is_finite_number(value) and minimum <= value <= maximum


def _is_geo_position(value: object) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) >= 2
        and all(_is_finite_number(coordinate) for coordinate in value)
        and _is_coordinate(value[0], -180, 180)
        and _is_coordinate(value[1], -90, 90)
    )


def _is_linear_ring(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) >= 4
        and all(_is_geo_position(position) for position in value)
        and value[0][:2] == value[-1][:2]
    )


def _is_polygon_coordinates(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(_is_linear_ring(ring) for ring in value)


def _canonical_problem_geometry(
    scope_kind: str,
    geometry: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if scope_kind == "route":
        if not (
            isinstance(geometry, dict)
            and geometry.get("type") == "LineString"
            and isinstance(geometry.get("coordinates"), list)
            and len(geometry["coordinates"]) >= 2
            and all(_is_geo_position(position) for position in geometry["coordinates"])
        ):
            raise ValueError("Eine Route benötigt eine gültige GeoJSON-LineString.")
        return {"type": "LineString", "coordinates": geometry["coordinates"]}
    if scope_kind == "area":
        valid = isinstance(geometry, dict) and (
            (
                geometry.get("type") == "Polygon"
                and _is_polygon_coordinates(geometry.get("coordinates"))
            )
            or (
                geometry.get("type") == "MultiPolygon"
                and isinstance(geometry.get("coordinates"), list)
                and bool(geometry["coordinates"])
                and all(
                    _is_polygon_coordinates(polygon)
                    for polygon in geometry["coordinates"]
                )
            )
        )
        if not valid:
            raise ValueError("Ein Gebiet benötigt geschlossene GeoJSON-Polygonringe.")
        return {"type": geometry["type"], "coordinates": geometry["coordinates"]}
    if geometry is not None:
        raise ValueError("Nur Routen und Gebiete verwenden eine GeoJSON-Geometrie.")
    return None


def _json_object(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _public_geometry(scope_kind: str, raw: str | None) -> dict[str, Any] | None:
    try:
        return _canonical_problem_geometry(scope_kind, _json_object(raw))
    except ValueError:
        return None


def _public_coordinates(
    scope_kind: str,
    latitude: object,
    longitude: object,
) -> tuple[float | int | None, float | int | None]:
    if (
        scope_kind in {"point", "facility"}
        and _is_coordinate(latitude, -90, 90)
        and _is_coordinate(longitude, -180, 180)
    ):
        return latitude, longitude
    return None, None


class ProblemStore:
    """Owns problemtracker persistence and exposes only explicit public views."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, timeout=15, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.create_function(
            "valid_public_http_url",
            1,
            lambda value: int(_is_public_http_url(value)),
            deterministic=True,
        )
        self._conn.executescript(SCHEMA)
        # Alte, vor der Rollen-/Quellenpflicht veröffentlichte Ereignisse
        # bleiben gespeichert, werden aber nicht weiter öffentlich projiziert.
        self._conn.execute(
            f"""UPDATE civic_problem_events
                SET published_at = NULL
                WHERE published_at IS NOT NULL AND {_invalid_public_source()}"""
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def create_problem(
        self,
        *,
        title: str,
        summary: str,
        category: str,
        scope_kind: str,
        location_label: str = "",
        latitude: float | None = None,
        longitude: float | None = None,
        geometry: dict[str, Any] | None = None,
        status: str = "new",
        confidence: str = "unconfirmed",
        tags: Iterable[str] = (),
        first_observed_at: str | None = None,
        last_observed_at: str | None = None,
    ) -> int:
        """Create a problem projection.

        This is deliberately an internal store operation, not a public write API.
        Publication is a separate operation guarded by both review stages.
        """
        if category not in PROBLEM_CATEGORIES:
            raise ValueError("Unbekannte Problemkategorie.")
        if scope_kind not in SCOPE_KINDS:
            raise ValueError("Unbekannter geografischer Bezug.")
        if status not in PROBLEM_STATUSES:
            raise ValueError("Unbekannter Problemstatus.")
        if scope_kind in {"point", "facility"}:
            if not (
                _is_coordinate(latitude, -90, 90)
                and _is_coordinate(longitude, -180, 180)
            ):
                raise ValueError("Punkt und Einrichtung benötigen gültige Koordinaten.")
        elif latitude is not None or longitude is not None:
            raise ValueError("Routen, Gebiete und stadtweite Probleme verwenden keine Punktkoordinaten.")
        canonical_geometry = _canonical_problem_geometry(scope_kind, geometry)
        now = _now()
        first = first_observed_at or now
        last = last_observed_at or first
        with self._conn:
            cur = self._conn.execute(
                """INSERT INTO civic_problems (
                       title, summary, category, tags_json, scope_kind, location_label,
                       latitude, longitude, geometry_json, status, confidence,
                       unique_reporters, current_observations, total_observations,
                       first_observed_at, last_observed_at, published_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    title.strip(), summary.strip(), category.strip(),
                    json.dumps(list(tags), ensure_ascii=False), scope_kind,
                    location_label.strip(), latitude, longitude,
                    json.dumps(canonical_geometry, ensure_ascii=False) if canonical_geometry else None,
                    status, confidence, 0, 0, 0, first, last, None, now,
                ),
            )
        return int(cur.lastrowid)

    def publish_problem(self, problem_id: int) -> None:
        """Publish an approved aggregate; fail closed without both review stages."""
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            counts = self._conn.execute(
                """SELECT COUNT(DISTINCT report.reporter_id) AS independent_reports,
                          COUNT(DISTINCT CASE WHEN observation.withdrawn_at IS NULL
                                             THEN observation.id END) AS current_observations,
                          COUNT(DISTINCT observation.id) AS total_observations,
                          MIN(CASE WHEN observation.withdrawn_at IS NULL
                                   THEN observation.observed_at END) AS first_observed_at,
                          MAX(CASE WHEN observation.withdrawn_at IS NULL
                                   THEN observation.observed_at END) AS last_observed_at
                   FROM civic_reports AS report
                   JOIN civic_moderation_decisions AS decision
                     ON decision.report_id = report.id
                    AND decision.problem_id = ?
                   JOIN civic_ai_assessments AS assessment
                     ON assessment.id = decision.ai_assessment_id
                    AND assessment.report_id = report.id
                   LEFT JOIN civic_report_observations AS observation
                     ON observation.report_id = report.id
                   WHERE report.problem_id = ?
                     AND report.status = 'accepted'
                     AND assessment.verdict = 'suitable'
                     AND assessment.report_revision = report.content_revision
                     AND decision.outcome IN (
                         'assigned_existing_problem', 'approved_for_new_problem'
                     )""",
                (problem_id, problem_id),
            ).fetchone()
            if not counts or counts["independent_reports"] < 1:
                raise ValueError("Vor der Veröffentlichung ist eine KI-Vorprüfung erforderlich.")
            now = _now()
            updated = self._conn.execute(
                """UPDATE civic_problems
                   SET unique_reporters = ?, current_observations = ?,
                       total_observations = ?, first_observed_at = ?,
                       last_observed_at = ?, published_at = ?, updated_at = ?
                   WHERE id = ? AND published_at IS NULL""",
                (
                    counts["independent_reports"],
                    counts["current_observations"],
                    counts["total_observations"],
                    counts["first_observed_at"] or now,
                    counts["last_observed_at"] or now,
                    now,
                    now,
                    problem_id,
                ),
            )
            if updated.rowcount != 1:
                raise ValueError("Problem nicht gefunden oder bereits veröffentlicht.")
            self._conn.commit()
        except sqlite3.OperationalError as error:
            self._conn.rollback()
            if "no such table" not in str(error):
                raise
            raise ValueError("Vor der Veröffentlichung ist eine KI-Vorprüfung erforderlich.") from error
        except Exception:
            self._conn.rollback()
            raise

    def add_public_event(
        self,
        problem_id: int,
        *,
        kind: str,
        title: str,
        detail: str = "",
        source_kind: str,
        source_url: str | None = None,
        event_at: str | None = None,
    ) -> int:
        if source_kind not in PUBLIC_SOURCE_KINDS:
            raise ValueError("Öffentliche Ereignisse benötigen ein gültiges Rollenlabel.")
        if source_url and not _is_public_http_url(source_url):
            raise ValueError("Quellen benötigen eine öffentliche HTTP-Adresse.")
        if source_kind != "Ratslotse-Prüfung" and not source_url:
            raise ValueError("Externe Reaktionen benötigen eine überprüfbare Quelle.")
        now = _now()
        with self._conn:
            cur = self._conn.execute(
                """INSERT INTO civic_problem_events
                       (problem_id, kind, title, detail, source_kind, source_url,
                        event_at, published_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (problem_id, kind, title.strip(), detail.strip(), source_kind,
                 source_url, event_at or now, now),
            )
        return int(cur.lastrowid)

    def list_public_problems(
        self,
        *,
        category: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["published_at IS NOT NULL", "unique_reporters >= 1"]
        params: list[Any] = []
        if category:
            clauses.append("category = ?")
            params.append(category)
        if status:
            clauses.append("status = ?")
            params.append(status)
        rows = self._conn.execute(
            f"SELECT * FROM civic_problems WHERE {' AND '.join(clauses)} "
            "ORDER BY last_observed_at DESC, id DESC",
            params,
        ).fetchall()
        return [self._public_problem(row, include_details=False) for row in rows]

    def get_public_problem(self, problem_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM civic_problems WHERE id = ? AND published_at IS NOT NULL "
            "AND unique_reporters >= 1",
            (problem_id,),
        ).fetchone()
        return self._public_problem(row, include_details=True) if row else None

    def _public_problem(self, row: sqlite3.Row, *, include_details: bool) -> dict[str, Any]:
        latitude, longitude = _public_coordinates(
            row["scope_kind"], row["latitude"], row["longitude"]
        )
        problem = {
            "id": row["id"],
            "title": row["title"],
            "category": row["category"],
            "scope_kind": row["scope_kind"],
            "location_label": row["location_label"],
            "latitude": latitude,
            "longitude": longitude,
            "geometry": _public_geometry(row["scope_kind"], row["geometry_json"]),
            "status": row["status"],
            "frequency": report_frequency(row["unique_reporters"]),
        }
        if include_details:
            problem.update({
                "summary": row["summary"],
                "tags": json.loads(row["tags_json"] or "[]"),
                "confidence": row["confidence"],
                "independent_reports": row["unique_reporters"],
                "last_observed_at": row["last_observed_at"],
                "published_at": row["published_at"],
                "updated_at": row["updated_at"],
            })
            events = self._conn.execute(
                """SELECT kind, title, detail, source_kind, source_url, event_at
                   FROM civic_problem_events
                   WHERE problem_id = ? AND published_at IS NOT NULL
                   ORDER BY event_at DESC, id DESC""",
                (row["id"],),
            ).fetchall()
            problem["events"] = [dict(event) for event in events]
        return problem
