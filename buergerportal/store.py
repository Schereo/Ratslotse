"""Persistente öffentliche Projektion des kommunalen Problemtrackers."""
from __future__ import annotations

import ipaddress
import json
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
    unique_reporters     INTEGER NOT NULL DEFAULT 1,
    current_observations INTEGER NOT NULL DEFAULT 1,
    total_observations   INTEGER NOT NULL DEFAULT 1,
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


def report_frequency(unique_reporters: int) -> str:
    if unique_reporters < 1:
        raise ValueError("Veröffentlichte Probleme benötigen mindestens eine Meldung.")
    if unique_reporters == 1:
        return "once"
    if unique_reporters <= 4:
        return "several"
    if unique_reporters <= 9:
        return "many"
    return "very_many"


def _json_object(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


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
        unique_reporters: int = 1,
        current_observations: int = 1,
        total_observations: int = 1,
        tags: Iterable[str] = (),
        first_observed_at: str | None = None,
        last_observed_at: str | None = None,
        published: bool = False,
    ) -> int:
        """Create a problem projection.

        This is deliberately an internal store operation, not a public write API.
        Publication remains an explicit moderator action in later slices.
        """
        if category not in PROBLEM_CATEGORIES:
            raise ValueError("Unbekannte Problemkategorie.")
        if scope_kind not in SCOPE_KINDS:
            raise ValueError("Unbekannter geografischer Bezug.")
        if status not in PROBLEM_STATUSES:
            raise ValueError("Unbekannter Problemstatus.")
        if scope_kind in {"point", "facility"} and (latitude is None or longitude is None):
            raise ValueError("Punkt und Einrichtung benötigen Koordinaten.")
        if published and unique_reporters < 1:
            raise ValueError("Veröffentlichte Probleme benötigen mindestens eine Meldung.")
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
                    json.dumps(geometry, ensure_ascii=False) if geometry else None,
                    status, confidence, unique_reporters, current_observations,
                    total_observations, first, last, now if published else None, now,
                ),
            )
        return int(cur.lastrowid)

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
        problem = {
            "id": row["id"],
            "title": row["title"],
            "category": row["category"],
            "scope_kind": row["scope_kind"],
            "location_label": row["location_label"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "geometry": _json_object(row["geometry_json"]),
            "status": row["status"],
            "frequency": report_frequency(row["unique_reporters"]),
        }
        if include_details:
            problem.update({
                "summary": row["summary"],
                "tags": json.loads(row["tags_json"] or "[]"),
                "confidence": row["confidence"],
                "unique_reporters": row["unique_reporters"],
                "current_observations": row["current_observations"],
                "total_observations": row["total_observations"],
                "first_observed_at": row["first_observed_at"],
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
