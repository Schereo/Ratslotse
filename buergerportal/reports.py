"""Private Meldeentwürfe, Meldungen und Beobachtungen des Bürgerportals.

Dieses Modul besitzt ausschließlich das private Schreibmodell. Öffentliche
Problemprojektionen werden nur über :mod:`buergerportal.store` gelesen.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal, cast

from .domain import OLDENBURG_BOUNDS, PROBLEM_CATEGORIES, SCOPE_KINDS


ReportState = Literal["draft", "submitted"]
_SQLITE_INTEGER_MAX = 2**63 - 1
_IDEMPOTENCY_KEY = re.compile(r"[A-Za-z0-9._:-]{8,128}")


def _sql_enum(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


_INVARIANT_TRIGGERS = (
    """CREATE TRIGGER trg_civic_reports_owner_insert
           BEFORE INSERT ON civic_reports
           WHEN NOT EXISTS (
               SELECT 1 FROM web_users
               WHERE id = NEW.reporter_id AND status = 'active' AND email_verified = 1
           )
           BEGIN
               SELECT RAISE(ABORT, 'report owner must be a verified account');
           END""",
    """CREATE TRIGGER trg_civic_reports_owner_update
           BEFORE UPDATE OF reporter_id ON civic_reports
           WHEN NOT EXISTS (
               SELECT 1 FROM web_users
               WHERE id = NEW.reporter_id AND status = 'active' AND email_verified = 1
           )
           BEGIN
               SELECT RAISE(ABORT, 'report owner must be a verified account');
           END""",
    """CREATE TRIGGER trg_civic_reports_submitted_content_no_update
           BEFORE UPDATE OF
               reporter_id, draft_text, confirmed_text, category, scope_kind,
               location_label, latitude, longitude, observed_at, status,
               submitted_at
           ON civic_reports
           WHEN OLD.status = 'submitted'
           BEGIN
               SELECT RAISE(ABORT, 'submitted reports are immutable');
           END""",
    """CREATE TRIGGER trg_civic_reports_draft_content_requires_revision
           BEFORE UPDATE OF
               draft_text, category, scope_kind, location_label,
               latitude, longitude, observed_at
           ON civic_reports
           WHEN OLD.status = 'draft'
            AND (
                NEW.draft_text IS NOT OLD.draft_text
                OR NEW.category IS NOT OLD.category
                OR NEW.scope_kind IS NOT OLD.scope_kind
                OR NEW.location_label IS NOT OLD.location_label
                OR NEW.latitude IS NOT OLD.latitude
                OR NEW.longitude IS NOT OLD.longitude
                OR NEW.observed_at IS NOT OLD.observed_at
            )
            AND NEW.content_revision != OLD.content_revision + 1
           BEGIN
               SELECT RAISE(ABORT, 'draft content requires new revision');
           END""",
    """CREATE TRIGGER trg_civic_reports_submission_requires_revision
           BEFORE UPDATE OF status ON civic_reports
           WHEN OLD.status = 'draft' AND NEW.status = 'submitted'
            AND NEW.content_revision != OLD.content_revision + 1
           BEGIN
               SELECT RAISE(ABORT, 'submission requires new revision');
           END""",
    """CREATE TRIGGER trg_civic_report_observations_match_revision
           BEFORE INSERT ON civic_report_observations
           WHEN NOT EXISTS (
               SELECT 1 FROM civic_reports AS report
               WHERE report.id = NEW.report_id
                 AND report.status = 'submitted'
                 AND (
                     (
                         NOT EXISTS (
                             SELECT 1 FROM civic_report_observations
                             WHERE report_id = NEW.report_id
                         )
                         AND NEW.content_revision = report.content_revision
                     )
                     OR
                     (
                         EXISTS (
                             SELECT 1 FROM civic_report_observations
                             WHERE report_id = NEW.report_id
                         )
                         AND NEW.content_revision = report.content_revision + 1
                     )
                 )
           )
           BEGIN
               SELECT RAISE(ABORT, 'observation must match submitted report revision');
           END""",
    """CREATE TRIGGER trg_civic_reports_revision_requires_observation
           BEFORE UPDATE OF content_revision ON civic_reports
           WHEN NEW.content_revision != OLD.content_revision
            AND NOT (
                (
                    OLD.status = 'draft'
                    AND NEW.status IN ('draft', 'submitted')
                    AND NEW.content_revision = OLD.content_revision + 1
                )
                OR
                (
                    OLD.status = 'submitted' AND NEW.status = 'submitted'
                    AND NEW.content_revision = OLD.content_revision + 1
                    AND EXISTS (
                        SELECT 1 FROM civic_report_observations
                        WHERE report_id = NEW.id
                          AND content_revision = NEW.content_revision
                    )
                )
            )
           BEGIN
               SELECT RAISE(ABORT, 'report revision requires observation');
           END""",
    """CREATE TRIGGER trg_civic_reports_submitted_insert_observation
           AFTER INSERT ON civic_reports
           WHEN NEW.status = 'submitted'
           BEGIN
               INSERT INTO civic_report_observations (
                   report_id, content_revision, text, observed_at, created_at
               ) VALUES (
                   NEW.id, NEW.content_revision, NEW.confirmed_text,
                   NEW.observed_at, NEW.submitted_at
               );
           END""",
    """CREATE TRIGGER trg_civic_reports_submission_observation
           AFTER UPDATE OF status ON civic_reports
           WHEN OLD.status = 'draft' AND NEW.status = 'submitted'
           BEGIN
               INSERT INTO civic_report_observations (
                   report_id, content_revision, text, observed_at, created_at
               ) VALUES (
                   NEW.id, NEW.content_revision, NEW.confirmed_text,
                   NEW.observed_at, NEW.submitted_at
               );
           END""",
    """CREATE TRIGGER trg_civic_report_observation_advances_revision
           AFTER INSERT ON civic_report_observations
           WHEN NEW.content_revision > (
               SELECT content_revision FROM civic_reports WHERE id = NEW.report_id
           )
           BEGIN
               UPDATE civic_reports
               SET content_revision = NEW.content_revision,
                   updated_at = NEW.created_at
               WHERE id = NEW.report_id;
           END""",
    """CREATE TRIGGER trg_civic_report_observations_no_update
           BEFORE UPDATE ON civic_report_observations
           BEGIN
               SELECT RAISE(ABORT, 'report observations are immutable');
           END""",
    """CREATE TRIGGER trg_civic_report_observations_no_direct_delete
           BEFORE DELETE ON civic_report_observations
           WHEN EXISTS (
               SELECT 1 FROM civic_reports WHERE id = OLD.report_id
           )
           BEGIN
               SELECT RAISE(ABORT, 'report observations are append-only');
           END""",
)

_TRIGGER_NAMES = (
    "trg_civic_reports_owner_insert",
    "trg_civic_reports_owner_update",
    "trg_civic_reports_submitted_content_no_update",
    "trg_civic_reports_draft_content_requires_revision",
    "trg_civic_reports_submission_requires_revision",
    "trg_civic_report_observations_match_revision",
    "trg_civic_reports_revision_requires_observation",
    "trg_civic_reports_submitted_insert_observation",
    "trg_civic_reports_submission_observation",
    "trg_civic_report_observation_advances_revision",
    "trg_civic_report_observations_no_update",
    "trg_civic_report_observations_no_direct_delete",
)

_INVARIANT_MIGRATION_STATEMENTS = (
    *(f"DROP TRIGGER IF EXISTS {name}" for name in _TRIGGER_NAMES),
    """UPDATE civic_report_observations AS observation
       SET content_revision = (
           SELECT COUNT(*) FROM civic_report_observations AS prior
           WHERE prior.report_id = observation.report_id
             AND prior.id <= observation.id
       )
       WHERE content_revision = 0""",
    """UPDATE civic_reports
       SET content_revision = MAX(
           content_revision,
           COALESCE((
               SELECT MAX(content_revision)
               FROM civic_report_observations
               WHERE report_id = civic_reports.id
           ), CASE WHEN status = 'submitted' THEN 1 ELSE 0 END)
       )""",
    """INSERT INTO civic_report_observations (
           report_id, content_revision, text, observed_at, created_at
       )
       SELECT id, content_revision, confirmed_text, observed_at, submitted_at
       FROM civic_reports AS report
       WHERE status = 'submitted'
         AND NOT EXISTS (
             SELECT 1 FROM civic_report_observations
             WHERE report_id = report.id
         )""",
    """CREATE INDEX IF NOT EXISTS idx_civic_reports_owner
           ON civic_reports(reporter_id, updated_at DESC)""",
    """CREATE INDEX IF NOT EXISTS idx_civic_report_observations_report
           ON civic_report_observations(report_id, content_revision)""",
    """CREATE UNIQUE INDEX IF NOT EXISTS
           uq_civic_report_observations_revision
           ON civic_report_observations(report_id, content_revision)""",
    *_INVARIANT_TRIGGERS,
)

_IDEMPOTENCY_MIGRATION_STATEMENTS = (
    "DROP TRIGGER IF EXISTS trg_civic_reports_idempotency_pair_insert",
    "DROP TRIGGER IF EXISTS trg_civic_reports_idempotency_pair_update",
    "DROP TRIGGER IF EXISTS trg_civic_reports_idempotency_no_update",
    """CREATE UNIQUE INDEX IF NOT EXISTS uq_civic_reports_owner_idempotency
           ON civic_reports(reporter_id, idempotency_key)
           WHERE idempotency_key IS NOT NULL""",
    """CREATE TRIGGER trg_civic_reports_idempotency_pair_insert
           BEFORE INSERT ON civic_reports
           WHEN (NEW.idempotency_key IS NULL) != (NEW.creation_fingerprint IS NULL)
           BEGIN
               SELECT RAISE(ABORT, 'idempotency key requires request fingerprint');
           END""",
    """CREATE TRIGGER trg_civic_reports_idempotency_pair_update
           BEFORE UPDATE OF idempotency_key, creation_fingerprint ON civic_reports
           WHEN (NEW.idempotency_key IS NULL) != (NEW.creation_fingerprint IS NULL)
           BEGIN
               SELECT RAISE(ABORT, 'idempotency key requires request fingerprint');
           END""",
    """CREATE TRIGGER trg_civic_reports_idempotency_no_update
           BEFORE UPDATE OF idempotency_key, creation_fingerprint ON civic_reports
           WHEN NEW.idempotency_key IS NOT OLD.idempotency_key
             OR NEW.creation_fingerprint IS NOT OLD.creation_fingerprint
           BEGIN
               SELECT RAISE(ABORT, 'report creation identity is immutable');
           END""",
)


_MIGRATIONS: tuple[tuple[int, tuple[str, ...]], ...] = (
    (
        1,
        (
            f"""CREATE TABLE civic_reports (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    reporter_id       INTEGER NOT NULL,
                    draft_text        TEXT NOT NULL,
                    confirmed_text    TEXT,
                    category          TEXT NOT NULL,
                    scope_kind        TEXT NOT NULL,
                    location_label    TEXT NOT NULL DEFAULT '',
                    latitude          REAL,
                    longitude         REAL,
                    observed_at       TEXT NOT NULL,
                    status            TEXT NOT NULL DEFAULT 'draft',
                    content_revision  INTEGER NOT NULL DEFAULT 0,
                    submitted_at      TEXT,
                    created_at        TEXT NOT NULL,
                    updated_at        TEXT NOT NULL,
                    CHECK (reporter_id > 0),
                    CHECK (length(trim(draft_text)) > 0),
                    CHECK (category IN ({_sql_enum(PROBLEM_CATEGORIES)})),
                    CHECK (scope_kind IN ({_sql_enum(SCOPE_KINDS)})),
                    CHECK (status IN ('draft', 'submitted')),
                    CHECK (content_revision >= 0),
                    CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
                    CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
                    CHECK (
                        (scope_kind = 'citywide' AND length(trim(location_label)) = 0
                         AND latitude IS NULL AND longitude IS NULL)
                        OR
                        (scope_kind != 'citywide' AND length(trim(location_label)) > 0
                         AND latitude IS NOT NULL AND longitude IS NOT NULL
                         AND latitude BETWEEN {OLDENBURG_BOUNDS["south"]}
                                          AND {OLDENBURG_BOUNDS["north"]}
                         AND longitude BETWEEN {OLDENBURG_BOUNDS["west"]}
                                           AND {OLDENBURG_BOUNDS["east"]})
                    ),
                    CHECK (date(observed_at) IS NOT NULL AND date(observed_at) = observed_at),
                    CHECK (datetime(created_at) IS NOT NULL),
                    CHECK (datetime(updated_at) IS NOT NULL AND updated_at >= created_at),
                    CHECK (
                        (status = 'draft' AND confirmed_text IS NULL AND submitted_at IS NULL)
                        OR
                        (status = 'submitted' AND length(trim(confirmed_text)) > 0
                         AND datetime(submitted_at) IS NOT NULL
                         AND content_revision >= 1)
                    ),
                    FOREIGN KEY (reporter_id) REFERENCES web_users(id) ON DELETE CASCADE
                )""",
            """CREATE INDEX idx_civic_reports_owner
                   ON civic_reports(reporter_id, updated_at DESC)""",
        ),
    ),
    (
        2,
        (
            """CREATE TABLE civic_report_observations (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_id         INTEGER NOT NULL,
                    content_revision  INTEGER NOT NULL,
                    text              TEXT NOT NULL,
                    observed_at       TEXT NOT NULL,
                    created_at        TEXT NOT NULL,
                    CHECK (content_revision >= 1),
                    CHECK (length(trim(text)) > 0),
                    CHECK (date(observed_at) IS NOT NULL AND date(observed_at) = observed_at),
                    CHECK (datetime(created_at) IS NOT NULL),
                    UNIQUE (report_id, content_revision),
                    FOREIGN KEY (report_id) REFERENCES civic_reports(id) ON DELETE CASCADE
                )""",
            """CREATE INDEX idx_civic_report_observations_report
                   ON civic_report_observations(report_id, content_revision)""",
        ),
    ),
    (3, _INVARIANT_MIGRATION_STATEMENTS),
    # Version 4 baut ein bereits von der früheren Version 3 markiertes
    # Legacy-Schema auf dieselben Tabellen-Constraints wie eine frische DB um.
    (4, _INVARIANT_MIGRATION_STATEMENTS),
    (5, _IDEMPOTENCY_MIGRATION_STATEMENTS),
)


_REPORT_COLUMNS_V4 = (
    "id", "reporter_id", "draft_text", "confirmed_text", "category",
    "scope_kind", "location_label", "latitude", "longitude", "observed_at",
    "status", "content_revision", "submitted_at", "created_at", "updated_at",
)
_REPORT_COLUMNS = (*_REPORT_COLUMNS_V4, "idempotency_key", "creation_fingerprint")
_OBSERVATION_COLUMNS = (
    "id", "report_id", "content_revision", "text", "observed_at", "created_at",
)


def _private_schema_requires_rebuild(connection: sqlite3.Connection) -> bool:
    report_columns = tuple(
        str(row["name"])
        for row in connection.execute("PRAGMA table_info(civic_reports)")
    )
    observation_columns = tuple(
        str(row["name"])
        for row in connection.execute("PRAGMA table_info(civic_report_observations)")
    )
    report_foreign_keys = {
        (str(row["from"]), str(row["table"]), str(row["to"]), str(row["on_delete"]))
        for row in connection.execute("PRAGMA foreign_key_list(civic_reports)")
    }
    observation_foreign_keys = {
        (str(row["from"]), str(row["table"]), str(row["to"]), str(row["on_delete"]))
        for row in connection.execute("PRAGMA foreign_key_list(civic_report_observations)")
    }
    report_sql_row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'civic_reports'"
    ).fetchone()
    observation_sql_row = connection.execute(
        """SELECT sql FROM sqlite_master
           WHERE type = 'table' AND name = 'civic_report_observations'"""
    ).fetchone()
    report_sql = str(report_sql_row["sql"] if report_sql_row else "")
    observation_sql = str(observation_sql_row["sql"] if observation_sql_row else "")
    return (
        report_columns not in (_REPORT_COLUMNS_V4, _REPORT_COLUMNS)
        or observation_columns != _OBSERVATION_COLUMNS
        or ("reporter_id", "web_users", "id", "CASCADE") not in report_foreign_keys
        or (
            "report_id", "civic_reports", "id", "CASCADE"
        ) not in observation_foreign_keys
        or not all(
            fragment in report_sql
            for fragment in (
                "CHECK (category IN",
                "CHECK (scope_kind IN",
                "CHECK (status IN",
                "date(observed_at)",
                "datetime(created_at)",
                "datetime(updated_at)",
            )
        )
        or not all(
            fragment in observation_sql
            for fragment in (
                "CHECK (content_revision >= 1)",
                "date(observed_at)",
                "datetime(created_at)",
            )
        )
    )


def _migration_upgrade_statements(
    connection: sqlite3.Connection,
    version: int,
) -> tuple[str, ...]:
    if version == 5:
        report_columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(civic_reports)")
        }
        additions = []
        if "idempotency_key" not in report_columns:
            additions.append(
                """ALTER TABLE civic_reports ADD COLUMN idempotency_key TEXT
                       CHECK (
                           idempotency_key IS NULL OR (
                               length(idempotency_key) BETWEEN 8 AND 128
                               AND idempotency_key NOT GLOB '*[^A-Za-z0-9._:-]*'
                           )
                       )"""
            )
        if "creation_fingerprint" not in report_columns:
            additions.append(
                """ALTER TABLE civic_reports ADD COLUMN creation_fingerprint TEXT
                       CHECK (
                           creation_fingerprint IS NULL OR (
                               length(creation_fingerprint) = 64
                               AND creation_fingerprint NOT GLOB '*[^0-9a-f]*'
                           )
                       )"""
            )
        return tuple(additions)
    if version not in (3, 4) or not _private_schema_requires_rebuild(connection):
        return ()
    report_columns = {
        str(row["name"])
        for row in connection.execute("PRAGMA table_info(civic_reports)")
    }
    observation_columns = {
        str(row["name"])
        for row in connection.execute("PRAGMA table_info(civic_report_observations)")
    }
    report_revision = (
        "CASE WHEN status = 'submitted' THEN MAX(content_revision, 1) "
        "ELSE content_revision END"
        if "content_revision" in report_columns
        else "CASE WHEN status = 'submitted' THEN 1 ELSE 0 END"
    )
    observation_revision = (
        "content_revision"
        if "content_revision" in observation_columns
        else "ROW_NUMBER() OVER (PARTITION BY report_id ORDER BY id)"
    )
    create_reports = _MIGRATIONS[0][1][0]
    create_observations = _MIGRATIONS[1][1][0]
    return (
        "ALTER TABLE civic_report_observations "
        "RENAME TO civic_report_observations_before_v3",
        "ALTER TABLE civic_reports RENAME TO civic_reports_before_v3",
        create_reports,
        f"""INSERT INTO civic_reports (
                id, reporter_id, draft_text, confirmed_text, category, scope_kind,
                location_label, latitude, longitude, observed_at, status,
                content_revision, submitted_at, created_at, updated_at
            )
            SELECT id, reporter_id, draft_text, confirmed_text, category, scope_kind,
                   location_label, latitude, longitude, observed_at, status,
                   {report_revision}, submitted_at, created_at, updated_at
            FROM civic_reports_before_v3""",
        create_observations,
        f"""INSERT INTO civic_report_observations (
                id, report_id, content_revision, text, observed_at, created_at
            )
            SELECT id, report_id, {observation_revision}, text, observed_at, created_at
            FROM civic_report_observations_before_v3""",
        "DROP TABLE civic_report_observations_before_v3",
        "DROP TABLE civic_reports_before_v3",
    )


@dataclass(frozen=True)
class DraftContent:
    """Der private, von der meldenden Person kontrollierte Inhalt."""

    text: str
    category: str
    scope_kind: str
    observed_on: str
    location_label: str = ""
    latitude: float | None = None
    longitude: float | None = None


@dataclass(frozen=True)
class PrivateObservation:
    text: str
    observed_on: str
    content_revision: int
    created_at: str


@dataclass(frozen=True)
class PrivateReport:
    id: int
    draft_text: str
    confirmed_text: str | None
    category: str
    scope_kind: str
    observed_on: str
    location_label: str
    latitude: float | None
    longitude: float | None
    state: ReportState
    content_revision: int
    submitted_at: str | None
    created_at: str
    updated_at: str
    observations: tuple[PrivateObservation, ...]


class PrivateReportNotFound(ValueError):
    """Unbekannte oder nicht der meldenden Person gehörende Meldung."""


class InvalidReportTransition(ValueError):
    """Der aktuelle Lebenslauf erlaubt die gewünschte Änderung nicht."""


class IdempotencyConflict(InvalidReportTransition):
    """Ein Erstellungsschlüssel wurde bereits für andere Eingaben verwendet."""


class ReporterNotEligible(ValueError):
    """Das Konto darf keine private Meldung anlegen oder verändern."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _is_storage_id(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, int)
        and 1 <= value <= _SQLITE_INTEGER_MAX
    )


def _normalized_expected_revision(value: int | None) -> int | None:
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value < _SQLITE_INTEGER_MAX
    ):
        raise ValueError("Die erwartete Inhaltsrevision ist ungültig.")
    return value


def _normalized_idempotency_key(value: str) -> str:
    if not _IDEMPOTENCY_KEY.fullmatch(value):
        raise ValueError("Der Idempotenzschlüssel ist ungültig.")
    return value


def _creation_fingerprint(content: DraftContent) -> str:
    serialized = json.dumps(
        {
            "category": content.category,
            "latitude": content.latitude,
            "location_label": content.location_label,
            "longitude": content.longitude,
            "observed_on": content.observed_on,
            "scope_kind": content.scope_kind,
            "text": content.text,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _normalized_observed_on(value: str) -> str:
    try:
        observed_on = date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise ValueError("Das Beobachtungsdatum ist ungültig.") from error
    if (
        observed_on != value
        or date.fromisoformat(observed_on) > datetime.now(timezone.utc).date()
    ):
        raise ValueError("Das Beobachtungsdatum ist ungültig.")
    return observed_on


def _normalized_content(content: DraftContent) -> DraftContent:
    text = content.text.strip()
    location_label = content.location_label.strip()
    if not text:
        raise ValueError("Eine Meldung benötigt eine Beschreibung.")
    if content.category not in PROBLEM_CATEGORIES:
        raise ValueError("Unbekannte Problemkategorie.")
    if content.scope_kind not in SCOPE_KINDS:
        raise ValueError("Unbekannter geografischer Bezug.")
    observed_on = _normalized_observed_on(content.observed_on)

    latitude = content.latitude
    longitude = content.longitude
    coordinates = (latitude, longitude)
    if any(isinstance(value, bool) for value in coordinates if value is not None):
        raise ValueError("Ungültige Koordinaten.")
    if (
        latitude is not None
        and (not math.isfinite(latitude) or not -90 <= latitude <= 90)
    ) or (
        longitude is not None
        and (not math.isfinite(longitude) or not -180 <= longitude <= 180)
    ):
        raise ValueError("Ungültige Koordinaten.")
    if content.scope_kind == "citywide":
        if location_label or latitude is not None or longitude is not None:
            raise ValueError("Stadtweite Meldungen verwenden keinen genauen Ort.")
    elif not location_label or latitude is None or longitude is None:
        raise ValueError("Nicht stadtweite Meldungen benötigen Ort und Koordinaten.")
    elif not (
        OLDENBURG_BOUNDS["south"] <= latitude <= OLDENBURG_BOUNDS["north"]
        and OLDENBURG_BOUNDS["west"] <= longitude <= OLDENBURG_BOUNDS["east"]
    ):
        raise ValueError("Die markierte Lage liegt außerhalb von Oldenburg.")

    return DraftContent(
        text=text,
        category=content.category,
        scope_kind=content.scope_kind,
        observed_on=observed_on,
        location_label=location_label,
        latitude=latitude,
        longitude=longitude,
    )


class PrivateReportStore:
    """Persistiert private Meldungen hinter eigentümergebundenen Operationen."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, timeout=15, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA secure_delete=ON")
        try:
            self._migrate()
        except Exception:
            self._conn.close()
            raise

    def close(self) -> None:
        self._conn.close()

    def _migrate(self) -> None:
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS civic_report_schema_migrations (
                   version INTEGER PRIMARY KEY,
                   applied_at TEXT NOT NULL
               )"""
        )
        self._conn.commit()
        for version, statements in _MIGRATIONS:
            rebuild = version in (3, 4) and _private_schema_requires_rebuild(self._conn)
            if rebuild:
                # SQLite kann Fremdschlüssel nur außerhalb einer Transaktion
                # abschalten. Der Tabellenumbau selbst bleibt in BEGIN IMMEDIATE
                # atomar; vor dem Commit wird der neue Stand vollständig geprüft.
                self._conn.execute("PRAGMA foreign_keys=OFF")
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                applied = self._conn.execute(
                    "SELECT 1 FROM civic_report_schema_migrations WHERE version = ?",
                    (version,),
                ).fetchone()
                if applied:
                    self._conn.commit()
                    continue
                for statement in _migration_upgrade_statements(self._conn, version):
                    self._conn.execute(statement)
                for statement in statements:
                    self._conn.execute(statement)
                foreign_key_errors = self._conn.execute(
                    "PRAGMA foreign_key_check"
                ).fetchall()
                if foreign_key_errors:
                    raise sqlite3.IntegrityError(
                        "private report migration violates foreign keys"
                    )
                self._conn.execute(
                    """INSERT INTO civic_report_schema_migrations(version, applied_at)
                       VALUES (?, ?)""",
                    (version, _now()),
                )
                self._conn.commit()
            except Exception:
                if self._conn.in_transaction:
                    self._conn.rollback()
                raise
            finally:
                if rebuild:
                    self._conn.execute("PRAGMA foreign_keys=ON")

    def create_draft(self, *, reporter_id: int, content: DraftContent) -> int:
        if not _is_storage_id(reporter_id):
            raise ValueError("Eine Meldung benötigt ein gültiges Konto.")
        self._require_verified_reporter(reporter_id)
        normalized = _normalized_content(content)
        now = _now()
        with self._conn:
            cursor = self._conn.execute(
                """INSERT INTO civic_reports (
                       reporter_id, draft_text, category, scope_kind,
                       location_label, latitude, longitude, observed_at,
                       created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    reporter_id,
                    normalized.text,
                    normalized.category,
                    normalized.scope_kind,
                    normalized.location_label,
                    normalized.latitude,
                    normalized.longitude,
                    normalized.observed_on,
                    now,
                    now,
                ),
            )
        return int(cursor.lastrowid)

    def create_owned_draft_idempotent(
        self,
        *,
        reporter_id: int,
        idempotency_key: str,
        content: DraftContent,
    ) -> PrivateReport:
        """Legt den Entwurf je Konto und Schlüssel höchstens einmal an.

        Der Fingerabdruck hält die ursprüngliche, normalisierte Anfrage fest.
        Dadurch bleibt ein späterer Retry auch dann erkennbar, wenn der Entwurf
        inzwischen geändert wurde; derselbe Schlüssel mit anderem Inhalt
        scheitert dagegen geschlossen.
        """
        if not _is_storage_id(reporter_id):
            raise ValueError("Eine Meldung benötigt ein gültiges Konto.")
        self._require_verified_reporter(reporter_id)
        key = _normalized_idempotency_key(idempotency_key)
        normalized = _normalized_content(content)
        fingerprint = _creation_fingerprint(normalized)
        now = _now()
        with self._conn:
            self._conn.execute(
                """INSERT INTO civic_reports (
                       reporter_id, draft_text, category, scope_kind,
                       location_label, latitude, longitude, observed_at,
                       created_at, updated_at, idempotency_key,
                       creation_fingerprint
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(reporter_id, idempotency_key)
                   WHERE idempotency_key IS NOT NULL DO NOTHING""",
                (
                    reporter_id,
                    normalized.text,
                    normalized.category,
                    normalized.scope_kind,
                    normalized.location_label,
                    normalized.latitude,
                    normalized.longitude,
                    normalized.observed_on,
                    now,
                    now,
                    key,
                    fingerprint,
                ),
            )
            existing = self._conn.execute(
                """SELECT id, creation_fingerprint
                   FROM civic_reports
                   WHERE reporter_id = ? AND idempotency_key = ?""",
                (reporter_id, key),
            ).fetchone()
            if existing is None:
                raise RuntimeError("Idempotent angelegter Entwurf konnte nicht geladen werden.")
            if existing["creation_fingerprint"] != fingerprint:
                raise IdempotencyConflict(
                    "Der Idempotenzschlüssel gehört bereits zu einer anderen Anfrage."
                )
            report_id = int(existing["id"])
        draft = self.get_owned_report(report_id, reporter_id=reporter_id)
        if draft is None:  # Durch die konto-spezifische Abfrage garantiert.
            raise RuntimeError("Idempotent angelegter Entwurf konnte nicht geladen werden.")
        return draft

    def update_owned_draft(
        self,
        report_id: int,
        *,
        reporter_id: int,
        content: DraftContent,
        expected_revision: int | None = None,
    ) -> PrivateReport:
        if not _is_storage_id(report_id) or not _is_storage_id(reporter_id):
            raise PrivateReportNotFound("Meldung nicht gefunden.")
        self._require_verified_reporter(reporter_id)
        normalized = _normalized_content(content)
        expected_revision = _normalized_expected_revision(expected_revision)
        now = _now()
        parameters: tuple[object, ...] = (
            normalized.text,
            normalized.category,
            normalized.scope_kind,
            normalized.location_label,
            normalized.latitude,
            normalized.longitude,
            normalized.observed_on,
            now,
            report_id,
            reporter_id,
            expected_revision,
            expected_revision,
        )
        with self._conn:
            updated = self._conn.execute(
                """UPDATE civic_reports
                   SET draft_text = ?, category = ?, scope_kind = ?,
                       location_label = ?, latitude = ?, longitude = ?,
                       observed_at = ?, content_revision = content_revision + 1,
                       updated_at = ?
                   WHERE id = ? AND reporter_id = ? AND status = 'draft'
                     AND (? IS NULL OR content_revision = ?)""",
                parameters,
            )
            if updated.rowcount != 1:
                self._raise_missing_or_transition(report_id, reporter_id=reporter_id)
        draft = self.get_owned_report(report_id, reporter_id=reporter_id)
        if draft is None:  # Durch die eigentümergebundene Änderung garantiert.
            raise RuntimeError("Geänderter Meldeentwurf konnte nicht geladen werden.")
        return draft

    def submit_owned_draft(
        self,
        report_id: int,
        *,
        reporter_id: int,
        confirmed_text: str,
        expected_revision: int | None = None,
    ) -> PrivateReport:
        if not _is_storage_id(report_id) or not _is_storage_id(reporter_id):
            raise PrivateReportNotFound("Meldung nicht gefunden.")
        self._require_verified_reporter(reporter_id)
        confirmed_text = confirmed_text.strip()
        if not confirmed_text:
            raise ValueError("Vor dem Absenden muss der Meldetext bestätigt werden.")
        expected_revision = _normalized_expected_revision(expected_revision)
        now = _now()
        parameters: tuple[object, ...] = (
            confirmed_text,
            now,
            now,
            report_id,
            reporter_id,
            expected_revision,
            expected_revision,
        )
        with self._conn:
            updated = self._conn.execute(
                """UPDATE civic_reports
                   SET confirmed_text = ?, status = 'submitted',
                       content_revision = content_revision + 1,
                       submitted_at = ?, updated_at = ?
                   WHERE id = ? AND reporter_id = ? AND status = 'draft'
                     AND (? IS NULL OR content_revision = ?)""",
                parameters,
            )
            if updated.rowcount != 1:
                existing = self.get_owned_report(report_id, reporter_id=reporter_id)
                if existing is None:
                    raise PrivateReportNotFound("Meldung nicht gefunden.")
                if (
                    expected_revision is not None
                    and existing.state == "submitted"
                    and existing.content_revision == expected_revision + 1
                    and existing.confirmed_text == confirmed_text
                ):
                    return existing
                raise InvalidReportTransition(
                    "Dieser Meldeentwurf kann nicht mehr abgesendet werden."
                )
        submitted = self.get_owned_report(report_id, reporter_id=reporter_id)
        if submitted is None:  # Durch den eigentümergebundenen Übergang garantiert.
            raise RuntimeError("Abgesendete Meldung konnte nicht geladen werden.")
        return submitted

    def append_owned_observation(
        self,
        report_id: int,
        *,
        reporter_id: int,
        text: str,
        observed_on: str,
    ) -> PrivateReport:
        if not _is_storage_id(report_id) or not _is_storage_id(reporter_id):
            raise PrivateReportNotFound("Meldung nicht gefunden.")
        self._require_verified_reporter(reporter_id)
        text = text.strip()
        if not text:
            raise ValueError("Eine Beobachtung benötigt eine Beschreibung.")
        observed_on = _normalized_observed_on(observed_on)
        now = _now()
        with self._conn:
            inserted = self._conn.execute(
                """INSERT INTO civic_report_observations (
                       report_id, content_revision, text, observed_at, created_at
                   )
                   SELECT id, content_revision + 1, ?, ?, ?
                   FROM civic_reports
                   WHERE id = ? AND reporter_id = ? AND status = 'submitted'
                   RETURNING content_revision""",
                (text, observed_on, now, report_id, reporter_id),
            ).fetchone()
            if inserted is None:
                self._raise_missing_or_transition(report_id, reporter_id=reporter_id)
        updated = self.get_owned_report(report_id, reporter_id=reporter_id)
        if updated is None:  # Durch den eigentümergebundenen Nachtrag garantiert.
            raise RuntimeError("Ergänzte Meldung konnte nicht geladen werden.")
        return updated

    def erase_reporter_data(self, *, reporter_id: int) -> int:
        """Löscht alle privaten Meldungsdaten eines Kontos samt Beobachtungen."""
        if not _is_storage_id(reporter_id):
            raise ValueError("Ein gültiges Konto ist erforderlich.")
        with self._conn:
            deleted = self._conn.execute(
                "DELETE FROM civic_reports WHERE reporter_id = ?",
                (reporter_id,),
            )
        return deleted.rowcount

    def _require_verified_reporter(self, reporter_id: int) -> None:
        account_table = self._conn.execute(
            """SELECT 1 FROM sqlite_master
               WHERE type = 'table' AND name = 'web_users'"""
        ).fetchone()
        verified = None
        if account_table is not None:
            verified = self._conn.execute(
                """SELECT 1 FROM web_users
                   WHERE id = ? AND status = 'active' AND email_verified = 1""",
                (reporter_id,),
            ).fetchone()
        if verified is None:
            raise ReporterNotEligible(
                "Private Meldungen benötigen ein bestätigtes Konto."
            )

    def _raise_missing_or_transition(self, report_id: int, *, reporter_id: int) -> None:
        owned = self._conn.execute(
            "SELECT 1 FROM civic_reports WHERE id = ? AND reporter_id = ?",
            (report_id, reporter_id),
        ).fetchone()
        if owned is None:
            raise PrivateReportNotFound("Meldung nicht gefunden.")
        raise InvalidReportTransition("Dieser Meldeentwurf kann nicht mehr geändert werden.")

    def get_owned_report(
        self,
        report_id: int,
        *,
        reporter_id: int,
    ) -> PrivateReport | None:
        if not _is_storage_id(report_id) or not _is_storage_id(reporter_id):
            return None
        row = self._conn.execute(
            """SELECT id, draft_text, confirmed_text, category, scope_kind,
                      observed_at, location_label, latitude, longitude, status,
                      content_revision, submitted_at, created_at, updated_at
               FROM civic_reports
               WHERE id = ? AND reporter_id = ?""",
            (report_id, reporter_id),
        ).fetchone()
        if row is None:
            return None
        observations = self._conn.execute(
            """SELECT text, observed_at, content_revision, created_at
               FROM civic_report_observations
               WHERE report_id = ?
               ORDER BY content_revision""",
            (report_id,),
        ).fetchall()
        return PrivateReport(
            id=int(row["id"]),
            draft_text=str(row["draft_text"]),
            confirmed_text=row["confirmed_text"],
            category=str(row["category"]),
            scope_kind=str(row["scope_kind"]),
            observed_on=str(row["observed_at"]),
            location_label=str(row["location_label"]),
            latitude=row["latitude"],
            longitude=row["longitude"],
            state=cast(ReportState, row["status"]),
            content_revision=int(row["content_revision"]),
            submitted_at=row["submitted_at"],
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            observations=tuple(
                PrivateObservation(
                    text=str(observation["text"]),
                    observed_on=str(observation["observed_at"]),
                    content_revision=int(observation["content_revision"]),
                    created_at=str(observation["created_at"]),
                )
                for observation in observations
            ),
        )
