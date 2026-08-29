"""Private Meldungen des Bürgerportals.

Dieses Modul besitzt die private Schreibseite. Öffentliche Problemprojektionen
werden ausschließlich über :mod:`buergerportal.store` gelesen.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .domain import (
    AI_ASSESSMENT_VERDICTS,
    MODERATION_OUTCOMES,
    PROBLEM_CATEGORIES,
    REPORT_STATUSES,
    SCOPE_KINDS,
)
from .schema import sql_enum


_PRIVATE_MIGRATIONS = (
    (
        1,
        f"""
        CREATE TABLE civic_reports (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            reporter_id       INTEGER NOT NULL,
            problem_id        INTEGER,
            draft_text        TEXT NOT NULL,
            confirmed_text    TEXT,
            category          TEXT NOT NULL,
            scope_kind        TEXT NOT NULL,
            location_label    TEXT NOT NULL DEFAULT '',
            latitude          REAL,
            longitude         REAL,
            observed_at       TEXT NOT NULL,
            status            TEXT NOT NULL DEFAULT 'draft',
            submitted_at      TEXT,
            withdrawn_at      TEXT,
            created_at        TEXT NOT NULL,
            updated_at        TEXT NOT NULL,
            CHECK (reporter_id > 0),
            CHECK (length(trim(draft_text)) > 0),
            CHECK (category IN ({sql_enum(PROBLEM_CATEGORIES)})),
            CHECK (scope_kind IN ({sql_enum(SCOPE_KINDS)})),
            CHECK (status IN ({sql_enum(REPORT_STATUSES)})),
            CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
            CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
            CHECK (
                scope_kind NOT IN ('point', 'facility')
                OR (latitude IS NOT NULL AND longitude IS NOT NULL)
            ),
            UNIQUE (reporter_id, problem_id)
        );
        CREATE INDEX idx_civic_reports_owner
            ON civic_reports(reporter_id, updated_at DESC);
        CREATE INDEX idx_civic_reports_moderation
            ON civic_reports(status, submitted_at);
        """,
    ),
    (
        2,
        """
        CREATE TABLE civic_report_observations (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id      INTEGER NOT NULL,
            text           TEXT NOT NULL,
            observed_at    TEXT NOT NULL,
            withdrawn_at   TEXT,
            created_at     TEXT NOT NULL,
            CHECK (length(trim(text)) > 0),
            FOREIGN KEY (report_id) REFERENCES civic_reports(id) ON DELETE CASCADE
        );
        CREATE INDEX idx_civic_report_observations_report
            ON civic_report_observations(report_id, observed_at, id);
        """,
    ),
    (
        3,
        f"""
        CREATE TABLE civic_moderation_decisions (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id      INTEGER NOT NULL,
            moderator_id   INTEGER NOT NULL,
            outcome        TEXT NOT NULL,
            reason_code    TEXT NOT NULL,
            reporter_message TEXT NOT NULL DEFAULT '',
            private_note      TEXT NOT NULL DEFAULT '',
            problem_id        INTEGER,
            previous_category TEXT,
            new_category      TEXT,
            previous_scope_kind TEXT,
            new_scope_kind    TEXT,
            previous_location_label TEXT,
            new_location_label TEXT,
            previous_latitude REAL,
            new_latitude      REAL,
            previous_longitude REAL,
            new_longitude     REAL,
            created_at        TEXT NOT NULL,
            CHECK (moderator_id > 0),
            CHECK (length(trim(reason_code)) > 0),
            CHECK (outcome IN ({sql_enum(MODERATION_OUTCOMES)})),
            CHECK (previous_category IS NULL OR previous_category IN ({sql_enum(PROBLEM_CATEGORIES)})),
            CHECK (new_category IS NULL OR new_category IN ({sql_enum(PROBLEM_CATEGORIES)})),
            CHECK (previous_scope_kind IS NULL OR previous_scope_kind IN ({sql_enum(SCOPE_KINDS)})),
            CHECK (new_scope_kind IS NULL OR new_scope_kind IN ({sql_enum(SCOPE_KINDS)})),
            CHECK (previous_latitude IS NULL OR previous_latitude BETWEEN -90 AND 90),
            CHECK (new_latitude IS NULL OR new_latitude BETWEEN -90 AND 90),
            CHECK (previous_longitude IS NULL OR previous_longitude BETWEEN -180 AND 180),
            CHECK (new_longitude IS NULL OR new_longitude BETWEEN -180 AND 180),
            CHECK (outcome != 'corrected_category' OR (previous_category IS NOT NULL AND new_category IS NOT NULL)),
            CHECK (outcome != 'corrected_geography' OR (previous_scope_kind IS NOT NULL AND new_scope_kind IS NOT NULL)),
            CHECK (outcome NOT IN ('assigned_existing_problem', 'published_as_new_problem') OR problem_id IS NOT NULL),
            UNIQUE (id, report_id),
            FOREIGN KEY (report_id) REFERENCES civic_reports(id) ON DELETE CASCADE
        );
        CREATE INDEX idx_civic_moderation_decisions_report
            ON civic_moderation_decisions(report_id, created_at, id);
        """,
    ),
    (
        4,
        """
        CREATE TABLE civic_moderation_review_requests (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id       INTEGER NOT NULL,
            decision_id     INTEGER NOT NULL UNIQUE,
            reporter_reason TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'pending',
            created_at      TEXT NOT NULL,
            resolved_at     TEXT,
            CHECK (length(trim(reporter_reason)) > 0),
            CHECK (status IN ('pending', 'accepted', 'rejected')),
            FOREIGN KEY (report_id) REFERENCES civic_reports(id) ON DELETE CASCADE,
            FOREIGN KEY (decision_id, report_id)
                REFERENCES civic_moderation_decisions(id, report_id)
        );
        """,
    ),
    (
        5,
        f"""
        CREATE TABLE civic_ai_assessments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id   INTEGER NOT NULL,
            verdict     TEXT NOT NULL,
            reason_code TEXT NOT NULL,
            model       TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            CHECK (verdict IN ({sql_enum(AI_ASSESSMENT_VERDICTS)})),
            CHECK (length(trim(reason_code)) > 0),
            CHECK (length(trim(model)) > 0),
            FOREIGN KEY (report_id) REFERENCES civic_reports(id) ON DELETE CASCADE
        );
        CREATE INDEX idx_civic_ai_assessments_report
            ON civic_ai_assessments(report_id, created_at, id);
        ALTER TABLE civic_moderation_decisions
            ADD COLUMN ai_assessment_id INTEGER
            REFERENCES civic_ai_assessments(id);
        """,
    ),
)

_AI_PUBLICATION_GATE = """
CREATE TRIGGER IF NOT EXISTS trg_civic_moderation_ai_publication_gate
BEFORE INSERT ON civic_moderation_decisions
WHEN NEW.outcome IN ('assigned_existing_problem', 'published_as_new_problem')
     AND NOT EXISTS (
         SELECT 1
         FROM civic_ai_assessments
         WHERE id = NEW.ai_assessment_id
           AND report_id = NEW.report_id
           AND verdict = 'suitable'
     )
BEGIN
    SELECT RAISE(ABORT, 'publication requires suitable AI assessment');
END;
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ReportStore:
    """Owns private report persistence behind owner-scoped read methods."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, timeout=15, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._migrate()

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
        for version, sql in _PRIVATE_MIGRATIONS:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                applied = self._conn.execute(
                    "SELECT 1 FROM civic_report_schema_migrations WHERE version = ?",
                    (version,),
                ).fetchone()
                if applied:
                    self._conn.commit()
                    continue
                for statement in sql.split(";"):
                    if statement.strip():
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
        self._conn.executescript(_AI_PUBLICATION_GATE)

    def create_draft(
        self,
        *,
        reporter_id: int,
        text: str,
        category: str,
        scope_kind: str,
        observed_at: str,
        location_label: str = "",
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> int:
        if reporter_id < 1:
            raise ValueError("Eine Meldung benötigt ein gültiges Konto.")
        if not text.strip():
            raise ValueError("Eine Meldung benötigt eine Beschreibung.")
        if category not in PROBLEM_CATEGORIES:
            raise ValueError("Unbekannte Problemkategorie.")
        if scope_kind not in SCOPE_KINDS:
            raise ValueError("Unbekannter geografischer Bezug.")
        if scope_kind in {"point", "facility"} and (latitude is None or longitude is None):
            raise ValueError("Punkt und Einrichtung benötigen Koordinaten.")
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
                    text.strip(),
                    category,
                    scope_kind,
                    location_label.strip(),
                    latitude,
                    longitude,
                    observed_at,
                    now,
                    now,
                ),
            )
        return int(cursor.lastrowid)

    def get_owned_report(self, report_id: int, *, reporter_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            """SELECT id, problem_id, draft_text AS text, confirmed_text,
                      category, scope_kind, location_label, latitude, longitude,
                      observed_at, status, submitted_at, withdrawn_at,
                      created_at, updated_at
               FROM civic_reports
               WHERE id = ? AND reporter_id = ?""",
            (report_id, reporter_id),
        ).fetchone()
        if not row:
            return None
        report = dict(row)
        observations = self._conn.execute(
            """SELECT text, observed_at, withdrawn_at
               FROM civic_report_observations
               WHERE report_id = ?
               ORDER BY observed_at, id""",
            (report_id,),
        ).fetchall()
        report["observations"] = [dict(observation) for observation in observations]
        return report

    def submit_owned_report(
        self,
        report_id: int,
        *,
        reporter_id: int,
        confirmed_text: str,
    ) -> dict[str, Any]:
        """Submit an owned draft and record its first observation atomically."""
        text = confirmed_text.strip()
        if not text:
            raise ValueError("Vor dem Absenden muss der deutsche Meldetext bestätigt werden.")
        now = _now()
        with self._conn:
            updated = self._conn.execute(
                """UPDATE civic_reports
                   SET confirmed_text = ?, status = 'submitted',
                       submitted_at = ?, updated_at = ?
                   WHERE id = ? AND reporter_id = ? AND status = 'draft'""",
                (text, now, now, report_id, reporter_id),
            )
            if updated.rowcount != 1:
                owned = self._conn.execute(
                    "SELECT 1 FROM civic_reports WHERE id = ? AND reporter_id = ?",
                    (report_id, reporter_id),
                ).fetchone()
                if not owned:
                    raise ValueError("Meldung nicht gefunden.")
                raise ValueError("Diese Meldung wurde bereits abgesendet.")
            row = self._conn.execute(
                "SELECT observed_at FROM civic_reports WHERE id = ?",
                (report_id,),
            ).fetchone()
            self._conn.execute(
                """INSERT INTO civic_report_observations (
                       report_id, text, observed_at, created_at
                   ) VALUES (?, ?, ?, ?)""",
                (report_id, text, row["observed_at"], now),
            )
        submitted = self.get_owned_report(report_id, reporter_id=reporter_id)
        if submitted is None:  # Protected by the transaction above.
            raise RuntimeError("Abgesendete Meldung konnte nicht geladen werden.")
        return submitted

    def record_ai_assessment(
        self,
        report_id: int,
        *,
        verdict: str,
        reason_code: str,
        model: str,
    ) -> dict[str, Any]:
        """Record an immutable private AI judgement without publishing anything."""
        if verdict not in AI_ASSESSMENT_VERDICTS:
            raise ValueError("Unbekanntes Ergebnis der KI-Vorprüfung.")
        if not reason_code.strip() or not model.strip():
            raise ValueError("Die KI-Vorprüfung benötigt Grund und Modell.")
        now = _now()
        with self._conn:
            report = self._conn.execute(
                "SELECT status FROM civic_reports WHERE id = ?",
                (report_id,),
            ).fetchone()
            if not report:
                raise ValueError("Meldung nicht gefunden.")
            if report["status"] not in {"submitted", "in_review", "needs_information"}:
                raise ValueError("Diese Meldung kann nicht durch die KI vorgeprüft werden.")
            cursor = self._conn.execute(
                """INSERT INTO civic_ai_assessments (
                       report_id, verdict, reason_code, model, created_at
                   ) VALUES (?, ?, ?, ?, ?)""",
                (report_id, verdict, reason_code.strip(), model.strip(), now),
            )
            self._conn.execute(
                "UPDATE civic_reports SET status = 'in_review', updated_at = ? WHERE id = ?",
                (now, report_id),
            )
        return {
            "id": int(cursor.lastrowid),
            "report_id": report_id,
            "verdict": verdict,
            "reason_code": reason_code.strip(),
            "model": model.strip(),
            "created_at": now,
        }

    def approve_report_for_projection(
        self,
        report_id: int,
        *,
        moderator_id: int,
        assessment_id: int,
        problem_id: int,
        reason_code: str,
        publish_as_new_problem: bool = False,
    ) -> dict[str, Any]:
        """Record final human approval after a suitable AI assessment.

        Approval only marks the private report as eligible. It never writes to
        the public problem projection by itself.
        """
        if moderator_id < 1 or problem_id < 1:
            raise ValueError("Freigabe benötigt gültige Moderation und Problemzuordnung.")
        if not reason_code.strip():
            raise ValueError("Freigabe benötigt einen Begründungscode.")
        now = _now()
        outcome = "published_as_new_problem" if publish_as_new_problem else "assigned_existing_problem"
        with self._conn:
            assessment = self._conn.execute(
                """SELECT verdict
                   FROM civic_ai_assessments
                   WHERE id = ? AND report_id = ?""",
                (assessment_id, report_id),
            ).fetchone()
            if not assessment:
                raise ValueError("Vor der Freigabe ist eine KI-Vorprüfung erforderlich.")
            if assessment["verdict"] != "suitable":
                raise ValueError("Nur eine als geeignet beurteilte Meldung kann freigegeben werden.")
            report = self._conn.execute(
                "SELECT status FROM civic_reports WHERE id = ?",
                (report_id,),
            ).fetchone()
            if not report or report["status"] not in {"submitted", "in_review", "needs_information"}:
                raise ValueError("Diese Meldung kann nicht freigegeben werden.")
            cursor = self._conn.execute(
                """INSERT INTO civic_moderation_decisions (
                       report_id, moderator_id, outcome, reason_code,
                       problem_id, created_at, ai_assessment_id
                   ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    report_id,
                    moderator_id,
                    outcome,
                    reason_code.strip(),
                    problem_id,
                    now,
                    assessment_id,
                ),
            )
            self._conn.execute(
                """UPDATE civic_reports
                   SET problem_id = ?, status = 'accepted', updated_at = ?
                   WHERE id = ?""",
                (problem_id, now, report_id),
            )
        return {
            "id": int(cursor.lastrowid),
            "report_id": report_id,
            "outcome": outcome,
            "problem_id": problem_id,
            "ai_assessment_id": assessment_id,
            "created_at": now,
        }

    def add_owned_observation(
        self,
        report_id: int,
        *,
        reporter_id: int,
        text: str,
        observed_at: str,
    ) -> dict[str, Any]:
        """Append an observation to an owned, active report."""
        observation = text.strip()
        if not observation:
            raise ValueError("Eine Beobachtung benötigt eine Beschreibung.")
        now = _now()
        with self._conn:
            report = self._conn.execute(
                """SELECT status FROM civic_reports
                   WHERE id = ? AND reporter_id = ?""",
                (report_id, reporter_id),
            ).fetchone()
            if not report:
                raise ValueError("Meldung nicht gefunden.")
            if report["status"] not in {
                "submitted",
                "in_review",
                "needs_information",
                "accepted",
            }:
                raise ValueError("Diese Meldung kann nicht aktualisiert werden.")
            self._conn.execute(
                """INSERT INTO civic_report_observations (
                       report_id, text, observed_at, created_at
                   ) VALUES (?, ?, ?, ?)""",
                (report_id, observation, observed_at, now),
            )
            self._conn.execute(
                "UPDATE civic_reports SET updated_at = ? WHERE id = ?",
                (now, report_id),
            )
        updated = self.get_owned_report(report_id, reporter_id=reporter_id)
        if updated is None:  # Protected by the transaction above.
            raise RuntimeError("Aktualisierte Meldung konnte nicht geladen werden.")
        return updated
