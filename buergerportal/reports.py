"""Private Meldeentwürfe, Meldungen und Beobachtungen des Bürgerportals.

Dieses Modul besitzt ausschließlich das private Schreibmodell. Öffentliche
Problemprojektionen werden nur über :mod:`buergerportal.store` gelesen.
"""
from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal, cast

from .domain import OLDENBURG_BOUNDS, PROBLEM_CATEGORIES, SCOPE_KINDS


ReportState = Literal["draft", "submitted"]
_SQLITE_INTEGER_MAX = 2**63 - 1


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
    (
        3,
        (
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
            """CREATE UNIQUE INDEX IF NOT EXISTS
                   uq_civic_report_observations_revision
                   ON civic_report_observations(report_id, content_revision)""",
            *_INVARIANT_TRIGGERS,
        ),
    ),
)


def _migration_upgrade_statements(
    connection: sqlite3.Connection,
    version: int,
) -> tuple[str, ...]:
    if version != 3:
        return ()
    report_columns = {
        str(row["name"])
        for row in connection.execute("PRAGMA table_info(civic_reports)")
    }
    observation_columns = {
        str(row["name"])
        for row in connection.execute("PRAGMA table_info(civic_report_observations)")
    }
    statements: list[str] = []
    if "content_revision" not in report_columns:
        statements.append(
            """ALTER TABLE civic_reports
               ADD COLUMN content_revision INTEGER NOT NULL DEFAULT 0
               CHECK (content_revision >= 0)"""
        )
    if "content_revision" not in observation_columns:
        statements.append(
            """ALTER TABLE civic_report_observations
               ADD COLUMN content_revision INTEGER NOT NULL DEFAULT 0
               CHECK (content_revision >= 0)"""
        )
    return tuple(statements)


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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _is_storage_id(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, int)
        and 1 <= value <= _SQLITE_INTEGER_MAX
    )


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

    def update_owned_draft(
        self,
        report_id: int,
        *,
        reporter_id: int,
        content: DraftContent,
    ) -> PrivateReport:
        if not _is_storage_id(report_id) or not _is_storage_id(reporter_id):
            raise PrivateReportNotFound("Meldung nicht gefunden.")
        self._require_verified_reporter(reporter_id)
        normalized = _normalized_content(content)
        now = _now()
        with self._conn:
            updated = self._conn.execute(
                """UPDATE civic_reports
                   SET draft_text = ?, category = ?, scope_kind = ?,
                       location_label = ?, latitude = ?, longitude = ?,
                       observed_at = ?, content_revision = content_revision + 1,
                       updated_at = ?
                   WHERE id = ? AND reporter_id = ? AND status = 'draft'""",
                (
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
                ),
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
    ) -> PrivateReport:
        if not _is_storage_id(report_id) or not _is_storage_id(reporter_id):
            raise PrivateReportNotFound("Meldung nicht gefunden.")
        self._require_verified_reporter(reporter_id)
        confirmed_text = confirmed_text.strip()
        if not confirmed_text:
            raise ValueError("Vor dem Absenden muss der Meldetext bestätigt werden.")
        now = _now()
        with self._conn:
            updated = self._conn.execute(
                """UPDATE civic_reports
                   SET confirmed_text = ?, status = 'submitted',
                       content_revision = content_revision + 1,
                       submitted_at = ?, updated_at = ?
                   WHERE id = ? AND reporter_id = ? AND status = 'draft'""",
                (confirmed_text, now, now, report_id, reporter_id),
            )
            if updated.rowcount != 1:
                self._raise_missing_or_transition(report_id, reporter_id=reporter_id)
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
            raise ValueError("Private Meldungen benötigen ein bestätigtes Konto.")

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
