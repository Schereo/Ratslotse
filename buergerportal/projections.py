"""Human-confirmed bridge from approved private reports to public projections.

``ProjectionStore`` owns assignment evidence and projection writes. Public callers
continue to read only through :class:`buergerportal.store.ProblemStore`;
``PrivateReportStore`` never writes public rows.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from kern.store import Store

from .domain import ProblemCategory, ScopeKind
from .reports import ModerationObservation, PrivateReportStore, ReviewerNotEligible
from .store import ProblemStore

_SQLITE_INTEGER_MAX = 2**63 - 1
_MAX_PUBLIC_TITLE_LENGTH = 120
_MAX_PUBLIC_SUMMARY_LENGTH = 600
_PRIVATE_REPORT_PREVIEW_LENGTH = 160
_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class NewCitywideProjection:
    title: str
    summary: str


@dataclass(frozen=True)
class ExistingProjection:
    problem_id: int


ProjectionTarget = NewCitywideProjection | ExistingProjection


@dataclass(frozen=True)
class ProjectionCandidateSummary:
    report_id: int
    content_revision: int
    text_preview: str
    category: ProblemCategory
    scope_kind: ScopeKind
    observed_on: str


@dataclass(frozen=True)
class ProjectionCandidatePage:
    reports: tuple[ProjectionCandidateSummary, ...]
    total: int


@dataclass(frozen=True)
class ProjectionCandidate:
    report_id: int
    content_revision: int
    category: ProblemCategory
    scope_kind: ScopeKind
    observations: tuple[ModerationObservation, ...]


@dataclass(frozen=True)
class PublicProjectionTarget:
    problem_id: int
    title: str
    summary: str
    category: ProblemCategory
    scope_kind: ScopeKind
    status: str
    independent_reports: int


@dataclass(frozen=True)
class OwnerPublicAssignment:
    problem_id: int
    title: str


@dataclass(frozen=True)
class ProblemAssignment:
    id: int
    report_id: int
    content_revision: int
    problem_id: int
    problem_title: str
    reviewer_id: int
    assigned_at: str


class ProjectionConflict(ValueError):
    """The requested candidate/target no longer supports this confirmation."""


_SCHEMA = """
BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS civic_problem_projection_baselines (
    problem_id                    INTEGER PRIMARY KEY,
    baseline_independent_reports INTEGER NOT NULL CHECK (baseline_independent_reports >= 0),
    baseline_first_observed_at    TEXT,
    baseline_last_observed_at     TEXT,
    FOREIGN KEY (problem_id) REFERENCES civic_problems(id) ON DELETE RESTRICT
);
CREATE TRIGGER IF NOT EXISTS trg_civic_problem_projection_baselines_no_update
BEFORE UPDATE ON civic_problem_projection_baselines
BEGIN
    SELECT RAISE(ABORT, 'projection baselines are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_civic_problem_projection_baselines_no_delete
BEFORE DELETE ON civic_problem_projection_baselines
BEGIN
    SELECT RAISE(ABORT, 'projection baselines are immutable');
END;
CREATE TABLE IF NOT EXISTS civic_report_problem_assignments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id        INTEGER NOT NULL,
    content_revision INTEGER NOT NULL CHECK (content_revision >= 1),
    problem_id       INTEGER NOT NULL,
    reviewer_id      INTEGER NOT NULL CHECK (reviewer_id > 0),
    creates_problem  INTEGER NOT NULL CHECK (creates_problem IN (0, 1)),
    assigned_at      TEXT NOT NULL CHECK (datetime(assigned_at) IS NOT NULL),
    UNIQUE (report_id, content_revision),
    FOREIGN KEY (report_id, content_revision)
        REFERENCES civic_report_observations(report_id, content_revision)
        ON DELETE CASCADE,
    FOREIGN KEY (problem_id) REFERENCES civic_problems(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_civic_report_problem_assignments_problem
    ON civic_report_problem_assignments(problem_id);
CREATE VIEW IF NOT EXISTS civic_report_current_projectable AS
    SELECT report.id AS report_id,
           report.content_revision AS content_revision,
           decision.id AS moderation_decision_id
    FROM civic_reports AS report
    JOIN web_users AS owner ON owner.id = report.reporter_id
    JOIN civic_report_moderation_decisions AS decision
      ON decision.report_id = report.id
     AND decision.content_revision = report.content_revision
     AND decision.outcome = 'approved'
    WHERE report.status = 'submitted'
      AND owner.role = 'user' AND owner.status = 'active'
      AND owner.email_verified = 1
      AND NOT EXISTS (
          SELECT 1 FROM civic_report_problem_assignments AS assignment
          WHERE assignment.report_id = report.id
            AND assignment.content_revision = report.content_revision
      );
CREATE TRIGGER IF NOT EXISTS trg_civic_report_problem_assignments_eligible_insert
BEFORE INSERT ON civic_report_problem_assignments
WHEN NOT EXISTS (
    SELECT 1
    FROM civic_report_current_projectable AS candidate
    JOIN civic_reports AS candidate_report
      ON candidate_report.id = candidate.report_id
     AND candidate_report.content_revision = candidate.content_revision
    JOIN civic_report_eligible_reviewers AS reviewer
      ON reviewer.reviewer_id = NEW.reviewer_id
    JOIN civic_problem_projection_baselines AS baseline
      ON baseline.problem_id = NEW.problem_id
    JOIN civic_problems AS problem ON problem.id = baseline.problem_id
    WHERE candidate.report_id = NEW.report_id
      AND candidate.content_revision = NEW.content_revision
      AND (
          (NEW.creates_problem = 0
           AND problem.published_at IS NOT NULL
           AND problem.independent_reports >= 1
           AND problem.status != 'apparently_resolved')
          OR
          (NEW.creates_problem = 1
           AND baseline.baseline_independent_reports = 0
           AND problem.published_at IS NULL
           AND problem.independent_reports = 0
           AND problem.scope_kind = 'citywide'
           AND problem.category = candidate_report.category
           AND problem.status = 'new'
           AND problem.tags_json = '[]'
           AND length(trim(problem.title)) BETWEEN 1 AND 120
           AND length(trim(problem.summary)) BETWEEN 1 AND 600
           AND problem.location_label = ''
           AND problem.latitude IS NULL
           AND problem.longitude IS NULL
           AND problem.geometry_json IS NULL)
      )
)
BEGIN
    SELECT RAISE(ABORT, 'assignment requires current approval, reviewer, and target');
END;
CREATE TRIGGER IF NOT EXISTS trg_civic_report_problem_assignments_no_update
BEFORE UPDATE ON civic_report_problem_assignments
BEGIN
    SELECT RAISE(ABORT, 'problem assignments are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_civic_report_problem_assignments_no_direct_delete
BEFORE DELETE ON civic_report_problem_assignments
WHEN EXISTS (SELECT 1 FROM civic_reports WHERE id = OLD.report_id)
BEGIN
    SELECT RAISE(ABORT, 'problem assignments are append-only');
END;
CREATE VIEW IF NOT EXISTS civic_problem_projection_stats AS
SELECT baseline.problem_id,
       baseline.baseline_independent_reports
         + COUNT(DISTINCT CASE WHEN decision.id IS NOT NULL THEN owner.id END)
           AS independent_reports,
       baseline.baseline_first_observed_at,
       baseline.baseline_last_observed_at,
       MIN(CASE WHEN decision.id IS NOT NULL THEN observation.observed_at END)
           AS assigned_first_observed_at,
       MAX(CASE WHEN decision.id IS NOT NULL THEN observation.observed_at END)
           AS assigned_last_observed_at
FROM civic_problem_projection_baselines AS baseline
LEFT JOIN civic_report_problem_assignments AS assignment
  ON assignment.problem_id = baseline.problem_id
LEFT JOIN civic_reports AS report
  ON report.id = assignment.report_id
 AND report.content_revision = assignment.content_revision
 AND report.status = 'submitted'
LEFT JOIN web_users AS owner
  ON owner.id = report.reporter_id
 AND owner.role = 'user' AND owner.status = 'active' AND owner.email_verified = 1
LEFT JOIN civic_report_moderation_decisions AS decision
  ON decision.report_id = report.id
 AND decision.content_revision = report.content_revision
 AND decision.outcome = 'approved'
LEFT JOIN civic_report_observations AS observation
  ON observation.report_id = report.id
 AND observation.content_revision <= assignment.content_revision
GROUP BY baseline.problem_id;
CREATE TRIGGER IF NOT EXISTS trg_civic_report_problem_assignments_refresh_insert
AFTER INSERT ON civic_report_problem_assignments
BEGIN
    UPDATE civic_problems
    SET independent_reports = (
            SELECT independent_reports FROM civic_problem_projection_stats
            WHERE problem_id = NEW.problem_id
        ),
        first_observed_at = COALESCE(
            (SELECT CASE
                WHEN baseline_first_observed_at IS NULL THEN assigned_first_observed_at
                WHEN assigned_first_observed_at IS NULL THEN baseline_first_observed_at
                ELSE MIN(baseline_first_observed_at, assigned_first_observed_at)
             END FROM civic_problem_projection_stats WHERE problem_id = NEW.problem_id),
            first_observed_at
        ),
        last_observed_at = COALESCE(
            (SELECT CASE
                WHEN baseline_last_observed_at IS NULL THEN assigned_last_observed_at
                WHEN assigned_last_observed_at IS NULL THEN baseline_last_observed_at
                ELSE MAX(baseline_last_observed_at, assigned_last_observed_at)
             END FROM civic_problem_projection_stats WHERE problem_id = NEW.problem_id),
            last_observed_at
        ),
        published_at = CASE
            WHEN (SELECT independent_reports FROM civic_problem_projection_stats
                  WHERE problem_id = NEW.problem_id) >= 1
            THEN COALESCE(published_at, NEW.assigned_at)
            ELSE NULL
        END,
        updated_at = NEW.assigned_at
    WHERE id = NEW.problem_id;
END;
CREATE TRIGGER IF NOT EXISTS trg_civic_report_problem_assignments_refresh_delete
AFTER DELETE ON civic_report_problem_assignments
BEGIN
    UPDATE civic_problems
    SET independent_reports = (
            SELECT independent_reports FROM civic_problem_projection_stats
            WHERE problem_id = OLD.problem_id
        ),
        first_observed_at = COALESCE(
            (SELECT CASE
                WHEN baseline_first_observed_at IS NULL THEN assigned_first_observed_at
                WHEN assigned_first_observed_at IS NULL THEN baseline_first_observed_at
                ELSE MIN(baseline_first_observed_at, assigned_first_observed_at)
             END FROM civic_problem_projection_stats WHERE problem_id = OLD.problem_id),
            first_observed_at
        ),
        last_observed_at = COALESCE(
            (SELECT CASE
                WHEN baseline_last_observed_at IS NULL THEN assigned_last_observed_at
                WHEN assigned_last_observed_at IS NULL THEN baseline_last_observed_at
                ELSE MAX(baseline_last_observed_at, assigned_last_observed_at)
             END FROM civic_problem_projection_stats WHERE problem_id = OLD.problem_id),
            last_observed_at
        ),
        published_at = CASE
            WHEN (SELECT independent_reports FROM civic_problem_projection_stats
                  WHERE problem_id = OLD.problem_id) >= 1
            THEN published_at ELSE NULL END,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = OLD.problem_id;
END;
CREATE TRIGGER IF NOT EXISTS trg_civic_reports_refresh_projection
AFTER UPDATE OF content_revision, status, reporter_id ON civic_reports
BEGIN
    UPDATE civic_problems
    SET independent_reports = (
            SELECT independent_reports FROM civic_problem_projection_stats
            WHERE problem_id = civic_problems.id
        ),
        first_observed_at = COALESCE(
            (SELECT CASE
                WHEN baseline_first_observed_at IS NULL THEN assigned_first_observed_at
                WHEN assigned_first_observed_at IS NULL THEN baseline_first_observed_at
                ELSE MIN(baseline_first_observed_at, assigned_first_observed_at)
             END FROM civic_problem_projection_stats
             WHERE problem_id = civic_problems.id),
            first_observed_at
        ),
        last_observed_at = COALESCE(
            (SELECT CASE
                WHEN baseline_last_observed_at IS NULL THEN assigned_last_observed_at
                WHEN assigned_last_observed_at IS NULL THEN baseline_last_observed_at
                ELSE MAX(baseline_last_observed_at, assigned_last_observed_at)
             END FROM civic_problem_projection_stats
             WHERE problem_id = civic_problems.id),
            last_observed_at
        ),
        published_at = CASE
            WHEN (SELECT independent_reports FROM civic_problem_projection_stats
                  WHERE problem_id = civic_problems.id) >= 1
            THEN COALESCE(published_at, CURRENT_TIMESTAMP) ELSE NULL END,
        updated_at = CURRENT_TIMESTAMP
    WHERE id IN (
        SELECT problem_id FROM civic_report_problem_assignments
        WHERE report_id = NEW.id
    );
END;
CREATE TRIGGER IF NOT EXISTS trg_web_users_refresh_problem_projections
AFTER UPDATE OF role, status, email_verified ON web_users
BEGIN
    UPDATE civic_problems
    SET independent_reports = (
            SELECT independent_reports FROM civic_problem_projection_stats
            WHERE problem_id = civic_problems.id
        ),
        first_observed_at = COALESCE(
            (SELECT CASE
                WHEN baseline_first_observed_at IS NULL THEN assigned_first_observed_at
                WHEN assigned_first_observed_at IS NULL THEN baseline_first_observed_at
                ELSE MIN(baseline_first_observed_at, assigned_first_observed_at)
             END FROM civic_problem_projection_stats
             WHERE problem_id = civic_problems.id),
            first_observed_at
        ),
        last_observed_at = COALESCE(
            (SELECT CASE
                WHEN baseline_last_observed_at IS NULL THEN assigned_last_observed_at
                WHEN assigned_last_observed_at IS NULL THEN baseline_last_observed_at
                ELSE MAX(baseline_last_observed_at, assigned_last_observed_at)
             END FROM civic_problem_projection_stats
             WHERE problem_id = civic_problems.id),
            last_observed_at
        ),
        published_at = CASE
            WHEN (SELECT independent_reports FROM civic_problem_projection_stats
                  WHERE problem_id = civic_problems.id) >= 1
            THEN COALESCE(published_at, CURRENT_TIMESTAMP) ELSE NULL END,
        updated_at = CURRENT_TIMESTAMP
    WHERE id IN (
        SELECT assignment.problem_id
        FROM civic_report_problem_assignments AS assignment
        JOIN civic_reports AS report ON report.id = assignment.report_id
        WHERE report.reporter_id = NEW.id
    );
END;
INSERT INTO civic_projection_schema_migrations(version) VALUES (1);
COMMIT;
"""

_MIGRATION_TABLE = """
CREATE TABLE IF NOT EXISTS civic_projection_schema_migrations (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


def _is_storage_id(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= _SQLITE_INTEGER_MAX


def _bounded_public_text(value: str, *, label: str, maximum: int) -> str:
    normalized = " ".join((value or "").strip().split())
    if not 1 <= len(normalized) <= maximum:
        raise ValueError(f"{label} muss zwischen 1 und {maximum} Zeichen lang sein.")
    return normalized


class ProjectionStore:
    """Small write interface for private assignment and public projection."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        accounts = Store(self.path)
        accounts.close()
        reports = PrivateReportStore(self.path)
        reports.close()
        public = ProblemStore(self.path)
        public.close()
        self._conn = sqlite3.connect(self.path, timeout=15, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute(_MIGRATION_TABLE)
        self._conn.commit()
        row = self._conn.execute(
            "SELECT COALESCE(MAX(version), 0) AS version FROM civic_projection_schema_migrations"
        ).fetchone()
        version = int(row["version"])
        if version > _SCHEMA_VERSION:
            self._conn.close()
            raise RuntimeError(
                f"Projection schema version {version} is newer than supported {_SCHEMA_VERSION}"
            )
        if version < _SCHEMA_VERSION:
            try:
                self._conn.executescript(_SCHEMA)
            except Exception:
                self._conn.rollback()
                self._conn.close()
                raise

    def close(self) -> None:
        self._conn.close()

    def list_candidates(
        self,
        *,
        reviewer_id: int,
        limit: int,
        offset: int,
    ) -> ProjectionCandidatePage:
        if (
            type(limit) is not int
            or not 1 <= limit <= 50
            or type(offset) is not int
            or not 0 <= offset <= _SQLITE_INTEGER_MAX
        ):
            raise ValueError("Ungültige Seitenauswahl.")
        self._require_reviewer(reviewer_id)
        total = int(
            self._conn.execute(
                "SELECT COUNT(*) FROM civic_report_current_projectable"
            ).fetchone()[0]
        )
        rows = self._conn.execute(
            """SELECT report.id, report.content_revision, report.confirmed_text,
                      report.category, report.scope_kind, report.observed_at
               FROM civic_report_current_projectable AS candidate
               JOIN civic_reports AS report
                 ON report.id = candidate.report_id
                AND report.content_revision = candidate.content_revision
               ORDER BY report.submitted_at ASC, report.id ASC
               LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()
        return ProjectionCandidatePage(
            reports=tuple(
                ProjectionCandidateSummary(
                    report_id=int(row["id"]),
                    content_revision=int(row["content_revision"]),
                    text_preview=str(row["confirmed_text"])[
                        :_PRIVATE_REPORT_PREVIEW_LENGTH
                    ],
                    category=cast(ProblemCategory, row["category"]),
                    scope_kind=cast(ScopeKind, row["scope_kind"]),
                    observed_on=str(row["observed_at"]),
                )
                for row in rows
            ),
            total=total,
        )

    def list_owner_assignments(
        self,
        *,
        reporter_id: int,
        report_ids: list[int],
    ) -> dict[int, OwnerPublicAssignment]:
        if not _is_storage_id(reporter_id) or len(report_ids) > 50:
            return {}
        normalized_ids = [report_id for report_id in report_ids if _is_storage_id(report_id)]
        if not normalized_ids:
            return {}
        placeholders = ", ".join("?" for _ in normalized_ids)
        rows = self._conn.execute(
            f"""SELECT report.id AS report_id, problem.id AS problem_id,
                       problem.title
                FROM civic_reports AS report
                JOIN web_users AS owner ON owner.id = report.reporter_id
                JOIN civic_report_problem_assignments AS assignment
                  ON assignment.report_id = report.id
                 AND assignment.content_revision = report.content_revision
                JOIN civic_problems AS problem ON problem.id = assignment.problem_id
                WHERE report.reporter_id = ?
                  AND owner.role = 'user' AND owner.status = 'active'
                  AND owner.email_verified = 1
                  AND problem.published_at IS NOT NULL
                  AND problem.independent_reports >= 1
                  AND report.id IN ({placeholders})""",
            (reporter_id, *normalized_ids),
        ).fetchall()
        return {
            int(row["report_id"]): OwnerPublicAssignment(
                problem_id=int(row["problem_id"]),
                title=str(row["title"]),
            )
            for row in rows
        }

    def list_targets(
        self,
        *,
        reviewer_id: int,
        query: str,
        limit: int,
    ) -> tuple[PublicProjectionTarget, ...]:
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("Ungültige Seitenauswahl.")
        normalized_query = " ".join((query or "").strip().split())
        if len(normalized_query) > 100:
            raise ValueError("Die Suche darf höchstens 100 Zeichen lang sein.")
        self._require_reviewer(reviewer_id)
        escaped = (
            normalized_query.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        rows = self._conn.execute(
            """SELECT id, title, summary, category, scope_kind, status,
                      independent_reports
               FROM civic_problems
               WHERE published_at IS NOT NULL
                 AND independent_reports >= 1
                 AND status != 'apparently_resolved'
                 AND (? = '' OR title LIKE ? ESCAPE '\\')
               ORDER BY title COLLATE NOCASE ASC, id ASC
               LIMIT ?""",
            (normalized_query, f"%{escaped}%", limit),
        ).fetchall()
        return tuple(
            PublicProjectionTarget(
                problem_id=int(row["id"]),
                title=str(row["title"]),
                summary=str(row["summary"]),
                category=cast(ProblemCategory, row["category"]),
                scope_kind=cast(ScopeKind, row["scope_kind"]),
                status=str(row["status"]),
                independent_reports=int(row["independent_reports"]),
            )
            for row in rows
        )

    def get_candidate(self, report_id: int, *, reviewer_id: int) -> ProjectionCandidate | None:
        self._require_reviewer(reviewer_id)
        if not _is_storage_id(report_id):
            return None
        rows = self._conn.execute(
            """SELECT report.id, report.content_revision, report.category,
                      report.scope_kind, observation.text AS observation_text,
                      observation.observed_at AS observation_observed_at
               FROM civic_report_current_projectable AS candidate
               JOIN civic_reports AS report
                 ON report.id = candidate.report_id
                AND report.content_revision = candidate.content_revision
               JOIN civic_report_observations AS observation
                 ON observation.report_id = report.id
                AND observation.content_revision <= report.content_revision
               WHERE candidate.report_id = ?
               ORDER BY observation.content_revision""",
            (report_id,),
        ).fetchall()
        if not rows:
            return None
        first = rows[0]
        return ProjectionCandidate(
            report_id=int(first["id"]),
            content_revision=int(first["content_revision"]),
            category=cast(ProblemCategory, first["category"]),
            scope_kind=cast(ScopeKind, first["scope_kind"]),
            observations=tuple(
                ModerationObservation(
                    text=str(row["observation_text"]),
                    observed_on=str(row["observation_observed_at"]),
                )
                for row in rows
            ),
        )

    def confirm_assignment(
        self,
        report_id: int,
        *,
        reviewer_id: int,
        expected_revision: int,
        target: ProjectionTarget,
    ) -> ProblemAssignment:
        self._require_reviewer(reviewer_id)
        if not _is_storage_id(report_id) or not _is_storage_id(expected_revision):
            raise ProjectionConflict("Meldung ist nicht mehr für die Projektion verfügbar.")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            existing = self._conn.execute(
                """SELECT * FROM civic_report_problem_assignments
                   WHERE report_id = ? AND content_revision = ?""",
                (report_id, expected_revision),
            ).fetchone()
            if existing is not None:
                return self._exact_retry_or_conflict(existing, target)
            candidate = self._candidate_row(report_id, expected_revision)
            if candidate is None:
                raise ProjectionConflict("Meldung ist nicht mehr für die Projektion verfügbar.")
            if isinstance(target, NewCitywideProjection):
                if candidate["scope_kind"] != "citywide":
                    raise ProjectionConflict("Neue Projektionen sind derzeit nur stadtweit möglich.")
                problem_id = self._create_citywide_problem(candidate, target, now)
                creates_problem = 1
            else:
                problem_id = target.problem_id
                self._capture_existing_baseline(problem_id)
                creates_problem = 0
            inserted = self._conn.execute(
                """INSERT INTO civic_report_problem_assignments (
                       report_id, content_revision, problem_id, reviewer_id,
                       creates_problem, assigned_at
                   ) VALUES (?, ?, ?, ?, ?, ?)
                   RETURNING *""",
                (
                    report_id,
                    expected_revision,
                    problem_id,
                    reviewer_id,
                    creates_problem,
                    now,
                ),
            ).fetchone()
            self._refresh_problem(problem_id, published_at=now)
            self._conn.commit()
        except (sqlite3.IntegrityError, sqlite3.OperationalError) as error:
            self._conn.rollback()
            raise ProjectionConflict("Meldung ist nicht mehr für die Projektion verfügbar.") from error
        except Exception:
            self._conn.rollback()
            raise
        assert inserted is not None
        return self._assignment(inserted)

    def _candidate_row(self, report_id: int, revision: int) -> sqlite3.Row | None:
        return self._conn.execute(
            """SELECT report.id, report.category, report.scope_kind,
                      MIN(observation.observed_at) AS first_observed_at,
                      MAX(observation.observed_at) AS last_observed_at
               FROM civic_report_current_projectable AS candidate
               JOIN civic_reports AS report ON report.id = candidate.report_id
               JOIN civic_report_observations AS observation
                 ON observation.report_id = report.id
                AND observation.content_revision <= report.content_revision
               WHERE candidate.report_id = ? AND candidate.content_revision = ?
               GROUP BY report.id""",
            (report_id, revision),
        ).fetchone()

    def _create_citywide_problem(
        self,
        candidate: sqlite3.Row,
        target: NewCitywideProjection,
        now: str,
    ) -> int:
        title = _bounded_public_text(
            target.title,
            label="Öffentlicher Titel",
            maximum=_MAX_PUBLIC_TITLE_LENGTH,
        )
        summary = _bounded_public_text(
            target.summary,
            label="Öffentliche Zusammenfassung",
            maximum=_MAX_PUBLIC_SUMMARY_LENGTH,
        )
        cursor = self._conn.execute(
            """INSERT INTO civic_problems (
                   title, summary, category, tags_json, scope_kind,
                   location_label, latitude, longitude, geometry_json, status,
                   independent_reports, first_observed_at, last_observed_at,
                   published_at, updated_at
               ) VALUES (?, ?, ?, '[]', 'citywide', '', NULL, NULL, NULL, 'new',
                         0, ?, ?, NULL, ?)""",
            (
                title,
                summary,
                candidate["category"],
                candidate["first_observed_at"],
                candidate["last_observed_at"],
                now,
            ),
        )
        problem_id = int(cursor.lastrowid)
        self._conn.execute(
            """INSERT INTO civic_problem_projection_baselines (
                   problem_id, baseline_independent_reports,
                   baseline_first_observed_at, baseline_last_observed_at
               ) VALUES (?, 0, NULL, NULL)""",
            (problem_id,),
        )
        return problem_id

    def _capture_existing_baseline(self, problem_id: int) -> None:
        if not _is_storage_id(problem_id):
            raise ProjectionConflict("Öffentliches Problem ist nicht verfügbar.")
        self._conn.execute(
            """INSERT OR IGNORE INTO civic_problem_projection_baselines (
                   problem_id, baseline_independent_reports,
                   baseline_first_observed_at, baseline_last_observed_at
               )
               SELECT id, independent_reports, first_observed_at, last_observed_at
               FROM civic_problems
               WHERE id = ? AND published_at IS NOT NULL
                 AND independent_reports >= 1 AND status != 'apparently_resolved'""",
            (problem_id,),
        )

    def _refresh_problem(self, problem_id: int, *, published_at: str) -> None:
        row = self._conn.execute(
            """SELECT baseline.baseline_independent_reports,
                      baseline.baseline_first_observed_at,
                      baseline.baseline_last_observed_at,
                      COUNT(DISTINCT owner.id) AS assigned_reporters,
                      MIN(observation.observed_at) AS assigned_first,
                      MAX(observation.observed_at) AS assigned_last
               FROM civic_problem_projection_baselines AS baseline
               LEFT JOIN civic_report_problem_assignments AS assignment
                 ON assignment.problem_id = baseline.problem_id
               LEFT JOIN civic_reports AS report
                 ON report.id = assignment.report_id
                AND report.content_revision = assignment.content_revision
                AND report.status = 'submitted'
               LEFT JOIN web_users AS owner
                 ON owner.id = report.reporter_id
                AND owner.role = 'user' AND owner.status = 'active'
                AND owner.email_verified = 1
               LEFT JOIN civic_report_moderation_decisions AS decision
                 ON decision.report_id = report.id
                AND decision.content_revision = report.content_revision
                AND decision.outcome = 'approved'
               LEFT JOIN civic_report_observations AS observation
                 ON observation.report_id = report.id
                AND observation.content_revision <= assignment.content_revision
                AND owner.id IS NOT NULL AND decision.id IS NOT NULL
               WHERE baseline.problem_id = ?
               GROUP BY baseline.problem_id""",
            (problem_id,),
        ).fetchone()
        if row is None:
            raise ProjectionConflict("Öffentliches Problem ist nicht verfügbar.")
        count = int(row["baseline_independent_reports"]) + int(row["assigned_reporters"])
        first_values = [
            value for value in (row["baseline_first_observed_at"], row["assigned_first"])
            if value is not None
        ]
        last_values = [
            value for value in (row["baseline_last_observed_at"], row["assigned_last"])
            if value is not None
        ]
        self._conn.execute(
            """UPDATE civic_problems
               SET independent_reports = ?, first_observed_at = ?, last_observed_at = ?,
                   published_at = CASE WHEN ? >= 1 THEN COALESCE(published_at, ?) ELSE NULL END,
                   updated_at = ?
               WHERE id = ?""",
            (
                count,
                min(first_values),
                max(last_values),
                count,
                published_at,
                published_at,
                problem_id,
            ),
        )

    def _assignment(self, row: sqlite3.Row) -> ProblemAssignment:
        problem = self._conn.execute(
            "SELECT title FROM civic_problems WHERE id = ?",
            (row["problem_id"],),
        ).fetchone()
        if problem is None:
            raise ProjectionConflict("Öffentliches Problem ist nicht verfügbar.")
        return ProblemAssignment(
            id=int(row["id"]),
            report_id=int(row["report_id"]),
            content_revision=int(row["content_revision"]),
            problem_id=int(row["problem_id"]),
            problem_title=str(problem["title"]),
            reviewer_id=int(row["reviewer_id"]),
            assigned_at=str(row["assigned_at"]),
        )

    def _exact_retry_or_conflict(
        self,
        row: sqlite3.Row,
        target: ProjectionTarget,
    ) -> ProblemAssignment:
        same = (
            isinstance(target, ExistingProjection)
            and int(row["creates_problem"]) == 0
            and int(row["problem_id"]) == target.problem_id
        )
        if isinstance(target, NewCitywideProjection) and int(row["creates_problem"]) == 1:
            problem = self._conn.execute(
                "SELECT title, summary FROM civic_problems WHERE id = ?",
                (row["problem_id"],),
            ).fetchone()
            same = problem is not None and (
                str(problem["title"])
                == _bounded_public_text(
                    target.title,
                    label="Öffentlicher Titel",
                    maximum=_MAX_PUBLIC_TITLE_LENGTH,
                )
                and str(problem["summary"])
                == _bounded_public_text(
                    target.summary,
                    label="Öffentliche Zusammenfassung",
                    maximum=_MAX_PUBLIC_SUMMARY_LENGTH,
                )
            )
        if not same:
            raise ProjectionConflict("Für diese Meldungsrevision besteht bereits eine andere Zuordnung.")
        self._conn.commit()
        return self._assignment(row)

    def _require_reviewer(self, reviewer_id: int) -> None:
        if not _is_storage_id(reviewer_id):
            raise ReviewerNotEligible("Dieses Konto darf Projektionen nicht bestätigen.")
        row = self._conn.execute(
            "SELECT 1 FROM civic_report_eligible_reviewers WHERE reviewer_id = ?",
            (reviewer_id,),
        ).fetchone()
        if row is None:
            raise ReviewerNotEligible("Dieses Konto darf Projektionen nicht bestätigen.")
