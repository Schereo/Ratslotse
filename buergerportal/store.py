"""Persistente, rein lesende öffentliche Problemprojektion."""
from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from typing import Any

from .domain import PROBLEM_CATEGORIES, PROBLEM_STATUSES, SCOPE_KINDS


def _sql_enum(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS civic_problem_schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS civic_problems (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    example_key         TEXT UNIQUE,
    title               TEXT NOT NULL,
    summary             TEXT NOT NULL,
    category            TEXT NOT NULL CHECK (category IN ({_sql_enum(PROBLEM_CATEGORIES)})),
    tags_json            TEXT NOT NULL DEFAULT '[]',
    scope_kind           TEXT NOT NULL CHECK (scope_kind IN ({_sql_enum(SCOPE_KINDS)})),
    location_label       TEXT NOT NULL DEFAULT '',
    latitude             REAL,
    longitude            REAL,
    geometry_json        TEXT,
    status               TEXT NOT NULL DEFAULT 'new' CHECK (status IN ({_sql_enum(PROBLEM_STATUSES)})),
    independent_reports  INTEGER NOT NULL DEFAULT 0 CHECK (independent_reports >= 0),
    first_observed_at    TEXT NOT NULL,
    last_observed_at     TEXT NOT NULL,
    published_at         TEXT,
    updated_at           TEXT NOT NULL,
    is_fictional         INTEGER NOT NULL DEFAULT 0 CHECK (is_fictional IN (0, 1)),
    CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
    CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
    CHECK (published_at IS NULL OR independent_reports >= 1)
);
CREATE INDEX IF NOT EXISTS idx_civic_problems_public
    ON civic_problems(published_at, last_observed_at DESC);
"""


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


def _is_number(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _is_coordinate(value: object, minimum: float, maximum: float) -> bool:
    return _is_number(value) and minimum <= value <= maximum


def _is_position(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) >= 2
        and all(_is_number(coordinate) for coordinate in value)
        and _is_coordinate(value[0], -180, 180)
        and _is_coordinate(value[1], -90, 90)
    )


def _is_ring(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) >= 4
        and all(_is_position(position) for position in value)
        and value[0][:2] == value[-1][:2]
    )


def _is_polygon(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(_is_ring(ring) for ring in value)


def _public_geometry(scope_kind: str, raw: str | None) -> dict[str, Any] | None:
    if not raw or scope_kind not in {"route", "area"}:
        return None
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    coordinates = value.get("coordinates")
    if (
        scope_kind == "route"
        and value.get("type") == "LineString"
        and isinstance(coordinates, list)
        and len(coordinates) >= 2
        and all(_is_position(position) for position in coordinates)
    ):
        return {"type": "LineString", "coordinates": coordinates}
    if scope_kind != "area":
        return None
    if value.get("type") == "Polygon" and _is_polygon(coordinates):
        return {"type": "Polygon", "coordinates": coordinates}
    if (
        value.get("type") == "MultiPolygon"
        and isinstance(coordinates, list)
        and bool(coordinates)
        and all(_is_polygon(polygon) for polygon in coordinates)
    ):
        return {"type": "MultiPolygon", "coordinates": coordinates}
    return None


class ProblemStore:
    """Besitzt nur die öffentliche Projektion und bietet keine Schreib-API."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, timeout=15, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._migrate()

    def _migrate(self) -> None:
        # Version 1 legt die eigenständige öffentliche Projektion an. Ein alter
        # Bürgerportal-Prototyp kann die Tabelle bereits mit `unique_reporters`
        # besitzen; CREATE TABLE IF NOT EXISTS lässt dessen Daten unangetastet.
        self._conn.executescript(_SCHEMA)
        columns = {
            str(row["name"])
            for row in self._conn.execute("PRAGMA table_info(civic_problems)")
        }
        with self._conn:
            # Version 2 passt genau diese alte Projektion additiv an. Keine
            # Tabelle und kein öffentlicher Datensatz wird dabei ersetzt.
            if "independent_reports" not in columns:
                self._conn.execute(
                    "ALTER TABLE civic_problems ADD COLUMN independent_reports "
                    "INTEGER NOT NULL DEFAULT 0"
                )
                if "unique_reporters" in columns:
                    self._conn.execute(
                        "UPDATE civic_problems SET independent_reports = unique_reporters"
                    )
            if "example_key" not in columns:
                self._conn.execute("ALTER TABLE civic_problems ADD COLUMN example_key TEXT")
            if "is_fictional" not in columns:
                self._conn.execute(
                    "ALTER TABLE civic_problems ADD COLUMN is_fictional "
                    "INTEGER NOT NULL DEFAULT 0"
                )
            self._conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_civic_problems_example_key "
                "ON civic_problems(example_key) WHERE example_key IS NOT NULL"
            )
            self._conn.executemany(
                "INSERT OR IGNORE INTO civic_problem_schema_migrations(version) VALUES (?)",
                ((1,), (2,)),
            )

    def close(self) -> None:
        self._conn.close()

    def list_public_problems(
        self,
        *,
        category: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["published_at IS NOT NULL", "independent_reports >= 1"]
        params: list[str] = []
        if category is not None:
            clauses.append("category = ?")
            params.append(category)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        rows = self._conn.execute(
            f"""SELECT id, title, category, scope_kind, location_label,
                       latitude, longitude, geometry_json, status,
                       independent_reports, is_fictional
                FROM civic_problems
                WHERE {' AND '.join(clauses)}
                ORDER BY last_observed_at DESC, id DESC""",
            params,
        ).fetchall()
        return [self._public_summary(row) for row in rows]

    @staticmethod
    def _public_summary(row: sqlite3.Row) -> dict[str, Any]:
        point_scope = row["scope_kind"] in {"point", "facility"}
        valid_point = (
            point_scope
            and _is_coordinate(row["latitude"], -90, 90)
            and _is_coordinate(row["longitude"], -180, 180)
        )
        latitude = row["latitude"] if valid_point else None
        longitude = row["longitude"] if valid_point else None
        return {
            "id": row["id"],
            "title": row["title"],
            "category": row["category"],
            "scope_kind": row["scope_kind"],
            "location_label": row["location_label"],
            "latitude": latitude,
            "longitude": longitude,
            "geometry": _public_geometry(row["scope_kind"], row["geometry_json"]),
            "status": row["status"],
            "frequency": report_frequency(row["independent_reports"]),
            "fictional": bool(row["is_fictional"]),
        }
