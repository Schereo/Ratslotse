"""Private reports and revision-bound local and external screening evidence.

This module exclusively owns the private write model. Public problem
projections are read only through :mod:`buergerportal.store`.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, cast
from zoneinfo import ZoneInfo

from .domain import (
    OLDENBURG_BOUNDS,
    PROBLEM_CATEGORIES,
    SCOPE_KINDS,
    ProblemCategory,
    ScopeKind,
)


ReportState = Literal["draft", "submitted"]
LocalScreeningOutcome = Literal[
    "external_review_candidate",
    "manual_review_only",
]
LocalScreeningReason = Literal[
    "potential_emergency",
    "direct_contact_data",
    "unsupported_text_format",
]
LOCAL_SCREENING_OUTCOMES: tuple[LocalScreeningOutcome, ...] = (
    "external_review_candidate",
    "manual_review_only",
)
LOCAL_SCREENING_REASONS: tuple[LocalScreeningReason, ...] = (
    "potential_emergency",
    "direct_contact_data",
    "unsupported_text_format",
)
ExternalAiScreeningVerdict = Literal[
    "suitable",
    "needs_human_review",
    "unsuitable",
]
ExternalAiScreeningReason = Literal[
    "municipal_problem",
    "insufficient_information",
    "non_municipal_matter",
    "personal_or_identifying_content",
    "abusive_or_discriminatory_content",
    "commercial_or_spam",
    "possible_safety_context",
    "model_uncertain",
]
EXTERNAL_AI_SCREENING_VERDICTS: tuple[ExternalAiScreeningVerdict, ...] = (
    "suitable",
    "needs_human_review",
    "unsuitable",
)
EXTERNAL_AI_SCREENING_REASONS: tuple[ExternalAiScreeningReason, ...] = (
    "municipal_problem",
    "insufficient_information",
    "non_municipal_matter",
    "personal_or_identifying_content",
    "abusive_or_discriminatory_content",
    "commercial_or_spam",
    "possible_safety_context",
    "model_uncertain",
)
_EXTERNAL_AI_REASON_VERDICTS: dict[
    ExternalAiScreeningVerdict,
    tuple[ExternalAiScreeningReason, ...],
] = {
    "suitable": ("municipal_problem",),
    "needs_human_review": (
        "insufficient_information",
        "personal_or_identifying_content",
        "possible_safety_context",
        "model_uncertain",
    ),
    "unsuitable": (
        "non_municipal_matter",
        "abusive_or_discriminatory_content",
        "commercial_or_spam",
    ),
}
LOCAL_SCREENING_RULESET_VERSION = 1
EXTERNAL_AI_SCREENING_ASSESSMENT_VERSION = 1
_PRIVATE_REPORT_PREVIEW_LENGTH = 160
_SQLITE_INTEGER_MAX = 2**63 - 1
_IDEMPOTENCY_KEY = re.compile(r"[A-Za-z0-9._:-]{8,128}")
_AI_CLAIM_TOKEN = re.compile(r"[A-Za-z0-9._:-]{8,128}")
_AI_MODEL_IDENTIFIER = re.compile(r"[A-Za-z0-9._:/-]{1,200}")
_POTENTIAL_EMERGENCY = re.compile(
    r"\b(?:112|notruf|notfall|lebensgefahr|akute\s+gefahr|bewusstlos|"
    r"gasgeruch|explosionsgefahr|schwer\s+verletzt|feuer|brand|brennt)\b",
    re.IGNORECASE,
)
_EMAIL_ADDRESS = re.compile(
    r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[a-z]{2,}(?!\w)",
    re.IGNORECASE,
)
_WRITTEN_DATE = re.compile(
    r"(?<![\d/.-])\b(?:\d{4}-\d{2}-\d{2}|"
    r"\d{1,2}\s*(?P<date_separator>[./-])\s*\d{1,2}\s*"
    r"(?P=date_separator)\s*\d{2,4})\b(?!\d)"
)
_PHONE_NUMBER = re.compile(
    r"(?<!\w)(?:(?:\+\d{1,3}|00\d{1,3}|0)[\d\s()/.-]{5,}\d)(?!\w)"
)
_PHONE_CONTEXT_NUMBER = re.compile(
    r"\b(?:telefon(?:nummer)?|tel|mobil(?:telefon|nummer)?|handy(?:nummer)?|"
    r"rückruf(?:nummer)?|rufnummer|anruf|durchwahl|kontakt|erreichbar|erreichen|"
    r"zurückrufen|zurückruft|anrufen|anruft|rufen|ruft|nummer)\b\.?"
    r"[^\n]{0,40}?(?<!\w)(?:\+\d{1,3}[\s()/.-]*)?"
    r"\d[\d\s()/.-]{3,}\d(?!\w)",
    re.IGNORECASE,
)
_UNSUPPORTED_TEXT_FORMAT = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_OLDENBURG_TIMEZONE = ZoneInfo("Europe/Berlin")
_LOGGER = logging.getLogger(__name__)


def _sql_enum(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


_OWNER_TRIGGERS = (
    """CREATE TRIGGER trg_civic_reports_owner_insert
           BEFORE INSERT ON civic_reports
           WHEN NOT EXISTS (
               SELECT 1 FROM web_users
               WHERE id = NEW.reporter_id AND role = 'user'
                 AND status = 'active' AND email_verified = 1
           )
           BEGIN
               SELECT RAISE(ABORT, 'report owner must be an eligible account');
           END""",
    """CREATE TRIGGER trg_civic_reports_owner_update
           BEFORE UPDATE OF reporter_id ON civic_reports
           WHEN NOT EXISTS (
               SELECT 1 FROM web_users
               WHERE id = NEW.reporter_id AND role = 'user'
                 AND status = 'active' AND email_verified = 1
           )
           BEGIN
               SELECT RAISE(ABORT, 'report owner must be an eligible account');
           END""",
)

_INVARIANT_TRIGGERS = (
    *_OWNER_TRIGGERS,
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

_REPORTER_ELIGIBILITY_MIGRATION_STATEMENTS = (
    "DROP TRIGGER IF EXISTS trg_civic_reports_owner_insert",
    "DROP TRIGGER IF EXISTS trg_civic_reports_owner_update",
    *_OWNER_TRIGGERS,
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
    (6, _REPORTER_ELIGIBILITY_MIGRATION_STATEMENTS),
    (
        7,
        (
            f"""CREATE TABLE civic_report_local_screenings (
                    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_id          INTEGER NOT NULL,
                    content_revision   INTEGER NOT NULL,
                    ruleset_version    INTEGER NOT NULL,
                    outcome            TEXT NOT NULL,
                    reason_codes_json  TEXT NOT NULL,
                    created_at         TEXT NOT NULL,
                    CHECK (content_revision >= 1),
                    CHECK (ruleset_version >= 1),
                    CHECK (outcome IN ({_sql_enum(LOCAL_SCREENING_OUTCOMES)})),
                    CHECK (
                        json_valid(reason_codes_json)
                        AND json_type(reason_codes_json) = 'array'
                    ),
                    CHECK (datetime(created_at) IS NOT NULL),
                    UNIQUE (report_id, content_revision, ruleset_version),
                    FOREIGN KEY (report_id, content_revision)
                        REFERENCES civic_report_observations(
                            report_id, content_revision
                        ) ON DELETE CASCADE
                )""",
            f"""CREATE TRIGGER trg_civic_report_local_screenings_controlled_result
                   BEFORE INSERT ON civic_report_local_screenings
                   WHEN CASE
                       WHEN json_valid(NEW.reason_codes_json) = 0 THEN 1
                       WHEN json_type(NEW.reason_codes_json) != 'array' THEN 1
                       WHEN NEW.outcome = 'external_review_candidate'
                         AND json_array_length(NEW.reason_codes_json) != 0 THEN 1
                       WHEN NEW.outcome = 'manual_review_only'
                         AND json_array_length(NEW.reason_codes_json) = 0 THEN 1
                       WHEN EXISTS (
                           SELECT 1 FROM json_each(NEW.reason_codes_json)
                           WHERE type != 'text'
                              OR value NOT IN ({_sql_enum(LOCAL_SCREENING_REASONS)})
                       ) THEN 1
                       WHEN (
                           SELECT COUNT(*) FROM json_each(NEW.reason_codes_json)
                       ) != (
                           SELECT COUNT(DISTINCT value)
                           FROM json_each(NEW.reason_codes_json)
                       ) THEN 1
                       ELSE 0
                   END
                   BEGIN
                       SELECT RAISE(ABORT, 'local screening requires controlled screening result');
                   END""",
            """CREATE TRIGGER trg_civic_report_local_screenings_current_revision
                   BEFORE INSERT ON civic_report_local_screenings
                   WHEN NOT EXISTS (
                       SELECT 1 FROM civic_reports AS report
                       JOIN web_users AS owner ON owner.id = report.reporter_id
                       WHERE report.id = NEW.report_id
                         AND report.status = 'submitted'
                         AND report.content_revision = NEW.content_revision
                         AND owner.role = 'user'
                         AND owner.status = 'active'
                         AND owner.email_verified = 1
                   )
                   BEGIN
                       SELECT RAISE(ABORT, 'screening requires current submitted revision and eligible owner');
                   END""",
            """CREATE TRIGGER trg_civic_report_local_screenings_no_update
                   BEFORE UPDATE ON civic_report_local_screenings
                   BEGIN
                       SELECT RAISE(ABORT, 'local screenings are immutable');
                   END""",
            """CREATE TRIGGER trg_civic_report_local_screenings_no_direct_delete
                   BEFORE DELETE ON civic_report_local_screenings
                   WHEN EXISTS (
                       SELECT 1 FROM civic_reports WHERE id = OLD.report_id
                   )
                   BEGIN
                       SELECT RAISE(ABORT, 'local screenings are append-only');
                   END""",
        ),
    ),
    (
        8,
        (
            """CREATE UNIQUE INDEX uq_civic_report_local_screening_identity
                   ON civic_report_local_screenings(
                       id, report_id, content_revision
                   )""",
            """CREATE TABLE civic_report_ai_screening_claims (
                    report_id          INTEGER NOT NULL,
                    content_revision   INTEGER NOT NULL,
                    local_screening_id INTEGER NOT NULL,
                    assessment_version INTEGER NOT NULL,
                    claim_token        TEXT NOT NULL,
                    lease_until        TEXT NOT NULL,
                    attempt_started_at TEXT,
                    PRIMARY KEY (
                        report_id, content_revision, assessment_version
                    ),
                    UNIQUE (
                        report_id, content_revision, assessment_version,
                        claim_token
                    ),
                    CHECK (content_revision >= 1),
                    CHECK (assessment_version >= 1),
                    CHECK (
                        length(claim_token) BETWEEN 8 AND 128
                        AND claim_token NOT GLOB '*[^A-Za-z0-9._:-]*'
                    ),
                    CHECK (datetime(lease_until) IS NOT NULL),
                    CHECK (
                        attempt_started_at IS NULL
                        OR datetime(attempt_started_at) IS NOT NULL
                    ),
                    FOREIGN KEY (report_id, content_revision)
                        REFERENCES civic_report_observations(
                            report_id, content_revision
                        ) ON DELETE CASCADE,
                    FOREIGN KEY (
                        local_screening_id, report_id, content_revision
                    ) REFERENCES civic_report_local_screenings(
                        id, report_id, content_revision
                    ) ON DELETE CASCADE
                )""",
            """CREATE TABLE civic_report_ai_screenings (
                    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_id          INTEGER NOT NULL,
                    content_revision   INTEGER NOT NULL,
                    local_screening_id INTEGER NOT NULL,
                    assessment_version INTEGER NOT NULL,
                    verdict            TEXT NOT NULL,
                    reason_code        TEXT NOT NULL,
                    model_identifier   TEXT NOT NULL,
                    created_at         TEXT NOT NULL,
                    CHECK (content_revision >= 1),
                    CHECK (assessment_version >= 1),
                    CHECK (
                        length(model_identifier) BETWEEN 1 AND 200
                        AND model_identifier NOT GLOB '*[^A-Za-z0-9._:/-]*'
                    ),
                    CHECK (datetime(created_at) IS NOT NULL),
                    UNIQUE (report_id, content_revision, assessment_version),
                    FOREIGN KEY (report_id, content_revision)
                        REFERENCES civic_report_observations(
                            report_id, content_revision
                        ) ON DELETE CASCADE,
                    FOREIGN KEY (
                        local_screening_id, report_id, content_revision
                    ) REFERENCES civic_report_local_screenings(
                        id, report_id, content_revision
                    ) ON DELETE CASCADE,
                    FOREIGN KEY (
                        report_id, content_revision, assessment_version
                    ) REFERENCES civic_report_ai_screening_claims(
                        report_id, content_revision, assessment_version
                    ) ON DELETE CASCADE
                )""",
            f"""CREATE TRIGGER trg_civic_report_ai_claims_current_candidate_insert
                   BEFORE INSERT ON civic_report_ai_screening_claims
                   WHEN NEW.assessment_version != {EXTERNAL_AI_SCREENING_ASSESSMENT_VERSION}
                     OR NOT EXISTS (
                       SELECT 1
                       FROM civic_reports AS report
                       JOIN web_users AS owner ON owner.id = report.reporter_id
                       JOIN civic_report_local_screenings AS screening
                         ON screening.report_id = report.id
                        AND screening.content_revision = report.content_revision
                       WHERE report.id = NEW.report_id
                         AND report.status = 'submitted'
                         AND report.content_revision = NEW.content_revision
                         AND screening.id = NEW.local_screening_id
                         AND screening.ruleset_version = {LOCAL_SCREENING_RULESET_VERSION}
                         AND screening.outcome = 'external_review_candidate'
                         AND owner.role = 'user' AND owner.status = 'active'
                         AND owner.email_verified = 1
                     )
                   BEGIN
                       SELECT RAISE(ABORT, 'AI claim requires current local candidate');
                   END""",
            f"""CREATE TRIGGER trg_civic_report_ai_claims_current_candidate_update
                   BEFORE UPDATE ON civic_report_ai_screening_claims
                   WHEN NEW.assessment_version != {EXTERNAL_AI_SCREENING_ASSESSMENT_VERSION}
                     OR NOT EXISTS (
                       SELECT 1
                       FROM civic_reports AS report
                       JOIN web_users AS owner ON owner.id = report.reporter_id
                       JOIN civic_report_local_screenings AS screening
                         ON screening.report_id = report.id
                        AND screening.content_revision = report.content_revision
                       WHERE report.id = NEW.report_id
                         AND report.status = 'submitted'
                         AND report.content_revision = NEW.content_revision
                         AND screening.id = NEW.local_screening_id
                         AND screening.ruleset_version = {LOCAL_SCREENING_RULESET_VERSION}
                         AND screening.outcome = 'external_review_candidate'
                         AND owner.role = 'user' AND owner.status = 'active'
                         AND owner.email_verified = 1
                     )
                   BEGIN
                       SELECT RAISE(ABORT, 'AI claim requires current local candidate');
                   END""",
            """CREATE TRIGGER trg_civic_report_ai_claims_expired_update_only
                   BEFORE UPDATE ON civic_report_ai_screening_claims
                   WHEN OLD.report_id != NEW.report_id
                     OR OLD.content_revision != NEW.content_revision
                     OR OLD.local_screening_id != NEW.local_screening_id
                     OR OLD.assessment_version != NEW.assessment_version
                     OR (
                       OLD.lease_until > strftime(
                           '%Y-%m-%dT%H:%M:%f+00:00', 'now'
                       )
                       AND NOT (
                           OLD.attempt_started_at IS NULL
                           AND NEW.attempt_started_at IS NOT NULL
                           AND NEW.attempt_started_at <= NEW.lease_until
                           AND OLD.claim_token = NEW.claim_token
                           AND OLD.lease_until = NEW.lease_until
                       )
                     )
                   BEGIN
                       SELECT RAISE(ABORT, 'active AI claims are immutable');
                   END""",
            f"""CREATE TRIGGER trg_civic_report_ai_screenings_controlled_result
                   BEFORE INSERT ON civic_report_ai_screenings
                   WHEN NEW.verdict NOT IN ({_sql_enum(EXTERNAL_AI_SCREENING_VERDICTS)})
                     OR NEW.reason_code NOT IN ({_sql_enum(EXTERNAL_AI_SCREENING_REASONS)})
                     OR (NEW.verdict = 'suitable'
                         AND NEW.reason_code NOT IN ({_sql_enum(_EXTERNAL_AI_REASON_VERDICTS['suitable'])}))
                     OR (NEW.verdict = 'needs_human_review'
                         AND NEW.reason_code NOT IN ({_sql_enum(_EXTERNAL_AI_REASON_VERDICTS['needs_human_review'])}))
                     OR (NEW.verdict = 'unsuitable'
                         AND NEW.reason_code NOT IN ({_sql_enum(_EXTERNAL_AI_REASON_VERDICTS['unsuitable'])}))
                   BEGIN
                       SELECT RAISE(ABORT, 'AI screening requires controlled result');
                   END""",
            f"""CREATE TRIGGER trg_civic_report_ai_screenings_current_candidate
                   BEFORE INSERT ON civic_report_ai_screenings
                   WHEN NEW.assessment_version != {EXTERNAL_AI_SCREENING_ASSESSMENT_VERSION}
                     OR NOT EXISTS (
                       SELECT 1
                       FROM civic_reports AS report
                       JOIN web_users AS owner ON owner.id = report.reporter_id
                       JOIN civic_report_local_screenings AS screening
                         ON screening.report_id = report.id
                        AND screening.content_revision = report.content_revision
                       JOIN civic_report_ai_screening_claims AS claim
                         ON claim.report_id = report.id
                        AND claim.content_revision = report.content_revision
                        AND claim.assessment_version = NEW.assessment_version
                       WHERE report.id = NEW.report_id
                         AND report.status = 'submitted'
                         AND report.content_revision = NEW.content_revision
                         AND screening.id = NEW.local_screening_id
                         AND screening.ruleset_version = {LOCAL_SCREENING_RULESET_VERSION}
                         AND screening.outcome = 'external_review_candidate'
                         AND claim.local_screening_id = screening.id
                         AND claim.attempt_started_at IS NOT NULL
                         AND claim.attempt_started_at <= NEW.created_at
                         AND claim.lease_until > NEW.created_at
                         AND owner.role = 'user' AND owner.status = 'active'
                         AND owner.email_verified = 1
                     )
                   BEGIN
                       SELECT RAISE(ABORT, 'AI screening requires current claimed candidate');
                   END""",
            """CREATE TRIGGER trg_civic_report_ai_claims_keep_completed
                   BEFORE DELETE ON civic_report_ai_screening_claims
                   WHEN EXISTS (
                       SELECT 1 FROM civic_report_ai_screenings AS completed
                       WHERE completed.report_id = OLD.report_id
                         AND completed.content_revision = OLD.content_revision
                         AND completed.assessment_version = OLD.assessment_version
                   )
                     AND EXISTS (
                       SELECT 1 FROM civic_reports WHERE id = OLD.report_id
                   )
                   BEGIN
                       SELECT RAISE(ABORT, 'completed AI claims are immutable');
                   END""",
            """CREATE TRIGGER trg_civic_report_ai_screenings_no_update
                   BEFORE UPDATE ON civic_report_ai_screenings
                   BEGIN
                       SELECT RAISE(ABORT, 'AI screenings are immutable');
                   END""",
            """CREATE TRIGGER trg_civic_report_ai_screenings_no_direct_delete
                   BEFORE DELETE ON civic_report_ai_screenings
                   WHEN EXISTS (
                       SELECT 1 FROM civic_reports WHERE id = OLD.report_id
                   )
                   BEGIN
                       SELECT RAISE(ABORT, 'AI screenings are append-only');
                   END""",
        ),
    ),
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
    category: ProblemCategory
    scope_kind: ScopeKind
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
class LocalReportScreening:
    """Private, revisionsgebundene Sperre vor einer möglichen externen Prüfung."""

    report_id: int
    content_revision: int
    ruleset_version: int
    outcome: LocalScreeningOutcome
    reason_codes: tuple[LocalScreeningReason, ...]
    created_at: str


@dataclass(frozen=True)
class ExternalAiScreeningInput:
    """The only private report fields allowed to reach the AI adapter."""

    observation_texts: tuple[str, ...]
    category: ProblemCategory
    scope_kind: ScopeKind


@dataclass(frozen=True)
class ClaimedExternalAiScreening:
    report_id: int
    content_revision: int
    local_screening_id: int
    assessment_version: int
    claim_token: str = field(repr=False)


@dataclass(frozen=True)
class ExternalAiScreening:
    """Private immutable AI evidence; never an automatic decision."""

    report_id: int
    content_revision: int
    local_screening_id: int
    assessment_version: int
    verdict: ExternalAiScreeningVerdict
    reason_code: ExternalAiScreeningReason
    model_identifier: str
    created_at: str


@dataclass(frozen=True)
class PrivateReportSummary:
    id: int
    text_preview: str
    category: ProblemCategory
    scope_kind: ScopeKind
    observed_on: str
    state: ReportState
    content_revision: int
    submitted_at: str | None
    updated_at: str


@dataclass(frozen=True)
class PrivateReportPage:
    reports: tuple[PrivateReportSummary, ...]
    total: int


@dataclass(frozen=True)
class PrivateReport:
    id: int
    draft_text: str
    confirmed_text: str | None
    category: ProblemCategory
    scope_kind: ScopeKind
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


def _local_screening_reasons(texts: tuple[str, ...]) -> tuple[LocalScreeningReason, ...]:
    combined = "\n".join(texts)
    reasons: list[LocalScreeningReason] = []
    if _POTENTIAL_EMERGENCY.search(combined):
        reasons.append("potential_emergency")
    contact_text = _WRITTEN_DATE.sub("", combined)
    if (
        _EMAIL_ADDRESS.search(contact_text)
        or _PHONE_NUMBER.search(contact_text)
        or _PHONE_CONTEXT_NUMBER.search(contact_text)
    ):
        reasons.append("direct_contact_data")
    if _UNSUPPORTED_TEXT_FORMAT.search(combined):
        reasons.append("unsupported_text_format")
    return tuple(reasons)


def _local_screening_from_row(row: sqlite3.Row) -> LocalReportScreening:
    return LocalReportScreening(
        report_id=int(row["report_id"]),
        content_revision=int(row["content_revision"]),
        ruleset_version=int(row["ruleset_version"]),
        outcome=cast(LocalScreeningOutcome, row["outcome"]),
        reason_codes=tuple(
            cast(LocalScreeningReason, reason)
            for reason in json.loads(row["reason_codes_json"])
        ),
        created_at=str(row["created_at"]),
    )


def _external_ai_screening_from_row(row: sqlite3.Row) -> ExternalAiScreening:
    return ExternalAiScreening(
        report_id=int(row["report_id"]),
        content_revision=int(row["content_revision"]),
        local_screening_id=int(row["local_screening_id"]),
        assessment_version=int(row["assessment_version"]),
        verdict=cast(ExternalAiScreeningVerdict, row["verdict"]),
        reason_code=cast(ExternalAiScreeningReason, row["reason_code"]),
        model_identifier=str(row["model_identifier"]),
        created_at=str(row["created_at"]),
    )


def validate_external_ai_screening_result(
    verdict: str,
    reason_code: str,
) -> tuple[ExternalAiScreeningVerdict, ExternalAiScreeningReason]:
    if verdict not in EXTERNAL_AI_SCREENING_VERDICTS:
        raise ValueError("Unbekanntes Ergebnis der externen KI-Vorprüfung.")
    controlled_verdict = cast(ExternalAiScreeningVerdict, verdict)
    if reason_code not in _EXTERNAL_AI_REASON_VERDICTS[controlled_verdict]:
        raise ValueError("Ungültiger Grund der externen KI-Vorprüfung.")
    return controlled_verdict, cast(ExternalAiScreeningReason, reason_code)


def normalize_external_ai_model_identifier(model_identifier: str) -> str:
    controlled_model = (
        model_identifier.strip() if isinstance(model_identifier, str) else ""
    )
    if not _AI_MODEL_IDENTIFIER.fullmatch(controlled_model):
        raise ValueError("Ungültige Modellkennung der externen KI-Vorprüfung.")
    return controlled_model


def _oldenburg_today(now: datetime | None = None) -> date:
    """Kalendertag am Ort der gemeldeten Beobachtung, unabhängig vom Server-TZ."""
    instant = now or datetime.now(timezone.utc)
    return instant.astimezone(_OLDENBURG_TIMEZONE).date()


def _normalized_observed_on(value: str) -> str:
    try:
        observed_on = date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise ValueError("Das Beobachtungsdatum ist ungültig.") from error
    if (
        observed_on != value
        or date.fromisoformat(observed_on) > _oldenburg_today()
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
        self._require_eligible_reporter(reporter_id)
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
        self._require_eligible_reporter(reporter_id)
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
        self._require_eligible_reporter(reporter_id)
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
        self._require_eligible_reporter(reporter_id)
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
        exact_retry: PrivateReport | None = None
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
                    exact_retry = existing
                else:
                    raise InvalidReportTransition(
                        "Dieser Meldeentwurf kann nicht mehr abgesendet werden."
                    )
        submitted = exact_retry or self.get_owned_report(
            report_id,
            reporter_id=reporter_id,
        )
        if submitted is None:  # Durch den eigentümergebundenen Übergang garantiert.
            raise RuntimeError("Abgesendete Meldung konnte nicht geladen werden.")
        try:
            self.assess_owned_submission(
                report_id,
                reporter_id=reporter_id,
                expected_revision=submitted.content_revision,
            )
        except Exception:  # noqa: BLE001 — Meldeeingang bleibt, Weitergabe bleibt gesperrt.
            _LOGGER.exception(
                "Lokale Weitergabeprüfung nach privatem Meldeeingang fehlgeschlagen"
            )
        return submitted

    def assess_owned_submission(
        self,
        report_id: int,
        *,
        reporter_id: int,
        expected_revision: int,
    ) -> LocalReportScreening:
        """Prüft die aktuelle eingereichte Revision ohne externe Weitergabe."""
        if not _is_storage_id(report_id) or not _is_storage_id(reporter_id):
            raise PrivateReportNotFound("Meldung nicht gefunden.")
        self._require_eligible_reporter(reporter_id)
        revision = _normalized_expected_revision(expected_revision)
        if revision is None:
            raise ValueError("Die erwartete Inhaltsrevision ist erforderlich.")
        now = _now()
        with self._conn:
            report = self._conn.execute(
                """SELECT 1 FROM civic_reports
                   WHERE id = ? AND reporter_id = ? AND status = 'submitted'
                     AND content_revision = ?""",
                (report_id, reporter_id, revision),
            ).fetchone()
            if report is None:
                self._raise_missing_or_transition(report_id, reporter_id=reporter_id)
            texts = tuple(
                str(row["text"])
                for row in self._conn.execute(
                    """SELECT text FROM civic_report_observations
                       WHERE report_id = ? AND content_revision <= ?
                       ORDER BY content_revision""",
                    (report_id, revision),
                )
            )
            reasons = _local_screening_reasons(texts)
            outcome = (
                "manual_review_only" if reasons else "external_review_candidate"
            )
            self._conn.execute(
                """INSERT INTO civic_report_local_screenings (
                       report_id, content_revision, ruleset_version,
                       outcome, reason_codes_json, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(report_id, content_revision, ruleset_version)
                   DO NOTHING""",
                (
                    report_id,
                    revision,
                    LOCAL_SCREENING_RULESET_VERSION,
                    outcome,
                    json.dumps(reasons, separators=(",", ":")),
                    now,
                ),
            )
        screening = self.get_current_owned_screening(
            report_id,
            reporter_id=reporter_id,
        )
        if screening is None:
            raise RuntimeError("Lokale Weitergabeprüfung konnte nicht geladen werden.")
        return screening

    def get_current_owned_screening(
        self,
        report_id: int,
        *,
        reporter_id: int,
    ) -> LocalReportScreening | None:
        """Liest nur die Prüfung der aktuellen Revision und Regelversion."""
        if not _is_storage_id(report_id) or not _is_storage_id(reporter_id):
            return None
        row = self._conn.execute(
            """SELECT screening.report_id, screening.content_revision,
                      screening.ruleset_version, screening.outcome,
                      screening.reason_codes_json, screening.created_at
               FROM civic_report_local_screenings AS screening
               JOIN civic_reports AS report ON report.id = screening.report_id
               WHERE report.id = ? AND report.reporter_id = ?
                 AND report.status = 'submitted'
                 AND report.content_revision = screening.content_revision
                 AND screening.ruleset_version = ?""",
            (report_id, reporter_id, LOCAL_SCREENING_RULESET_VERSION),
        ).fetchone()
        if row is None:
            return None
        return _local_screening_from_row(row)

    def get_owned_external_review_candidate(
        self,
        report_id: int,
        *,
        reporter_id: int,
        expected_revision: int,
    ) -> LocalReportScreening | None:
        """Gibt nur eine aktuelle lokal freigehaltene Kandidatin zurück."""
        if not _is_storage_id(report_id) or not _is_storage_id(reporter_id):
            return None
        try:
            revision = _normalized_expected_revision(expected_revision)
        except ValueError:
            return None
        if revision is None:
            return None
        row = self._conn.execute(
            """SELECT screening.report_id, screening.content_revision,
                      screening.ruleset_version, screening.outcome,
                      screening.reason_codes_json, screening.created_at
               FROM civic_report_local_screenings AS screening
               JOIN civic_reports AS report ON report.id = screening.report_id
               JOIN web_users AS owner ON owner.id = report.reporter_id
               WHERE report.id = ? AND report.reporter_id = ?
                 AND report.status = 'submitted'
                 AND report.content_revision = ?
                 AND screening.content_revision = report.content_revision
                 AND screening.ruleset_version = ?
                 AND screening.outcome = 'external_review_candidate'
                 AND owner.role = 'user' AND owner.status = 'active'
                 AND owner.email_verified = 1""",
            (
                report_id,
                reporter_id,
                revision,
                LOCAL_SCREENING_RULESET_VERSION,
            ),
        ).fetchone()
        if row is None:
            return None
        return _local_screening_from_row(row)

    def claim_external_ai_screening(
        self,
        report_id: int,
        *,
        expected_revision: int,
        assessment_version: int,
        claim_token: str,
        lease_seconds: int = 600,
    ) -> ClaimedExternalAiScreening | None:
        """Durably claim a current locally eligible revision for one AI call."""
        if not _is_storage_id(report_id):
            return None
        try:
            revision = _normalized_expected_revision(expected_revision)
        except ValueError:
            return None
        if revision is None:
            return None
        if (
            type(assessment_version) is not int
            or assessment_version != EXTERNAL_AI_SCREENING_ASSESSMENT_VERSION
        ):
            raise ValueError("Unbekannte Version der externen KI-Vorprüfung.")
        if not isinstance(claim_token, str) or not _AI_CLAIM_TOKEN.fullmatch(
            claim_token
        ):
            raise ValueError("Ungültige Claim-ID der externen KI-Vorprüfung.")
        if (
            isinstance(lease_seconds, bool)
            or not isinstance(lease_seconds, int)
            or not 1 <= lease_seconds <= 3600
        ):
            raise ValueError("Ungültige Laufzeit des KI-Claims.")

        claimed_at = datetime.now(timezone.utc)
        claimed_at_text = claimed_at.isoformat(timespec="microseconds")
        lease_until = (claimed_at + timedelta(seconds=lease_seconds)).isoformat(
            timespec="microseconds"
        )
        with self._conn:
            claim = self._conn.execute(
                """INSERT INTO civic_report_ai_screening_claims (
                       report_id, content_revision, local_screening_id,
                       assessment_version, claim_token, lease_until
                   )
                   SELECT report.id, report.content_revision, screening.id,
                          ?, ?, ?
                   FROM civic_reports AS report
                   JOIN web_users AS owner ON owner.id = report.reporter_id
                   JOIN civic_report_local_screenings AS screening
                     ON screening.report_id = report.id
                    AND screening.content_revision = report.content_revision
                   WHERE report.id = ?
                     AND report.status = 'submitted'
                     AND report.content_revision = ?
                     AND screening.ruleset_version = ?
                     AND screening.outcome = 'external_review_candidate'
                     AND owner.role = 'user' AND owner.status = 'active'
                     AND owner.email_verified = 1
                     AND NOT EXISTS (
                         SELECT 1 FROM civic_report_ai_screenings AS completed
                         WHERE completed.report_id = report.id
                           AND completed.content_revision = report.content_revision
                           AND completed.assessment_version = ?
                     )
                   ON CONFLICT (
                       report_id, content_revision, assessment_version
                   ) DO UPDATE SET
                       local_screening_id = excluded.local_screening_id,
                       claim_token = excluded.claim_token,
                       lease_until = excluded.lease_until,
                       attempt_started_at = NULL
                   WHERE civic_report_ai_screening_claims.lease_until <= ?
                   RETURNING local_screening_id""",
                (
                    assessment_version,
                    claim_token,
                    lease_until,
                    report_id,
                    revision,
                    LOCAL_SCREENING_RULESET_VERSION,
                    assessment_version,
                    claimed_at_text,
                ),
            ).fetchone()
            if claim is None:
                return None
        return ClaimedExternalAiScreening(
            report_id=report_id,
            content_revision=revision,
            local_screening_id=int(claim["local_screening_id"]),
            assessment_version=assessment_version,
            claim_token=claim_token,
        )

    def start_claimed_external_ai_screening(
        self,
        candidate: ClaimedExternalAiScreening,
    ) -> ExternalAiScreeningInput | None:
        """Linearize provider dispatch and return freshly revalidated input."""
        started_at = _now()
        with self._conn:
            started = self._conn.execute(
                """UPDATE civic_report_ai_screening_claims AS claim
                   SET attempt_started_at = ?
                   WHERE claim.report_id = ?
                     AND claim.content_revision = ?
                     AND claim.local_screening_id = ?
                     AND claim.assessment_version = ?
                     AND claim.claim_token = ?
                     AND claim.attempt_started_at IS NULL
                     AND claim.lease_until > ?
                     AND EXISTS (
                         SELECT 1
                         FROM civic_reports AS report
                         JOIN web_users AS owner ON owner.id = report.reporter_id
                         JOIN civic_report_local_screenings AS screening
                           ON screening.id = claim.local_screening_id
                          AND screening.report_id = report.id
                          AND screening.content_revision = report.content_revision
                         WHERE report.id = claim.report_id
                           AND report.status = 'submitted'
                           AND report.content_revision = claim.content_revision
                           AND screening.ruleset_version = ?
                           AND screening.outcome = 'external_review_candidate'
                           AND owner.role = 'user' AND owner.status = 'active'
                           AND owner.email_verified = 1
                     )
                   RETURNING local_screening_id""",
                (
                    started_at,
                    candidate.report_id,
                    candidate.content_revision,
                    candidate.local_screening_id,
                    candidate.assessment_version,
                    candidate.claim_token,
                    started_at,
                    LOCAL_SCREENING_RULESET_VERSION,
                ),
            ).fetchone()
            if started is None:
                return None
            report = self._conn.execute(
                """SELECT category, scope_kind
                   FROM civic_reports
                   WHERE id = ? AND content_revision = ?""",
                (candidate.report_id, candidate.content_revision),
            ).fetchone()
            observations = self._conn.execute(
                """SELECT text FROM civic_report_observations
                   WHERE report_id = ? AND content_revision <= ?
                   ORDER BY content_revision""",
                (candidate.report_id, candidate.content_revision),
            ).fetchall()
            if report is None or not observations:
                raise InvalidReportTransition(
                    "Gestarteter KI-Claim hat keine aktuelle private Meldung."
                )
        return ExternalAiScreeningInput(
            observation_texts=tuple(str(row["text"]) for row in observations),
            category=cast(ProblemCategory, report["category"]),
            scope_kind=cast(ScopeKind, report["scope_kind"]),
        )

    def complete_external_ai_screening(
        self,
        candidate: ClaimedExternalAiScreening,
        *,
        verdict: str,
        reason_code: str,
        model_identifier: str,
    ) -> ExternalAiScreening:
        """Persist a controlled result only while the candidate claim is valid."""
        controlled_verdict, controlled_reason = validate_external_ai_screening_result(
            verdict,
            reason_code,
        )
        controlled_model = normalize_external_ai_model_identifier(model_identifier)
        created_at = _now()
        with self._conn:
            inserted = self._conn.execute(
                """INSERT INTO civic_report_ai_screenings (
                       report_id, content_revision, local_screening_id,
                       assessment_version, verdict, reason_code,
                       model_identifier, created_at
                   )
                   SELECT claim.report_id, claim.content_revision,
                          claim.local_screening_id, claim.assessment_version,
                          ?, ?, ?, ?
                   FROM civic_report_ai_screening_claims AS claim
                   WHERE claim.report_id = ?
                     AND claim.content_revision = ?
                     AND claim.local_screening_id = ?
                     AND claim.assessment_version = ?
                     AND claim.claim_token = ?
                     AND claim.attempt_started_at IS NOT NULL
                     AND claim.attempt_started_at <= ?
                     AND claim.lease_until > ?
                   ON CONFLICT (
                       report_id, content_revision, assessment_version
                   ) DO NOTHING
                   RETURNING id""",
                (
                    controlled_verdict,
                    controlled_reason,
                    controlled_model,
                    created_at,
                    candidate.report_id,
                    candidate.content_revision,
                    candidate.local_screening_id,
                    candidate.assessment_version,
                    candidate.claim_token,
                    created_at,
                    created_at,
                ),
            ).fetchone()
            if inserted is None:
                existing = self._conn.execute(
                    """SELECT * FROM civic_report_ai_screenings
                       WHERE report_id = ? AND content_revision = ?
                         AND assessment_version = ?""",
                    (
                        candidate.report_id,
                        candidate.content_revision,
                        candidate.assessment_version,
                    ),
                ).fetchone()
                if existing is not None:
                    return _external_ai_screening_from_row(existing)
                raise InvalidReportTransition(
                    "Der Claim für die externe KI-Vorprüfung ist nicht mehr gültig."
                )
            row = self._conn.execute(
                "SELECT * FROM civic_report_ai_screenings WHERE id = ?",
                (int(inserted["id"]),),
            ).fetchone()
        if row is None:
            raise RuntimeError("Gespeicherte KI-Vorprüfung fehlt.")
        return _external_ai_screening_from_row(row)

    def release_external_ai_screening(
        self,
        candidate: ClaimedExternalAiScreening,
    ) -> bool:
        """Release an unfinished claim after a local/provider failure."""
        with self._conn:
            deleted = self._conn.execute(
                """DELETE FROM civic_report_ai_screening_claims
                   WHERE report_id = ? AND content_revision = ?
                     AND assessment_version = ? AND claim_token = ?
                     AND NOT EXISTS (
                         SELECT 1 FROM civic_report_ai_screenings AS completed
                         WHERE completed.report_id = ?
                           AND completed.content_revision = ?
                           AND completed.assessment_version = ?
                     )""",
                (
                    candidate.report_id,
                    candidate.content_revision,
                    candidate.assessment_version,
                    candidate.claim_token,
                    candidate.report_id,
                    candidate.content_revision,
                    candidate.assessment_version,
                ),
            )
        return deleted.rowcount == 1

    def get_current_external_ai_screening(
        self,
        report_id: int,
    ) -> ExternalAiScreening | None:
        """Return only evidence for the report's current eligible revision."""
        if not _is_storage_id(report_id):
            return None
        row = self._conn.execute(
            """SELECT completed.*
               FROM civic_report_ai_screenings AS completed
               JOIN civic_reports AS report ON report.id = completed.report_id
               JOIN web_users AS owner ON owner.id = report.reporter_id
               JOIN civic_report_local_screenings AS local
                 ON local.id = completed.local_screening_id
                AND local.report_id = completed.report_id
                AND local.content_revision = completed.content_revision
               WHERE completed.report_id = ?
                 AND completed.content_revision = report.content_revision
                 AND completed.assessment_version = ?
                 AND report.status = 'submitted'
                 AND local.ruleset_version = ?
                 AND local.outcome = 'external_review_candidate'
                 AND owner.role = 'user' AND owner.status = 'active'
                 AND owner.email_verified = 1""",
            (
                report_id,
                EXTERNAL_AI_SCREENING_ASSESSMENT_VERSION,
                LOCAL_SCREENING_RULESET_VERSION,
            ),
        ).fetchone()
        return _external_ai_screening_from_row(row) if row is not None else None

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
        self._require_eligible_reporter(reporter_id)
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

    def _require_eligible_reporter(self, reporter_id: int) -> None:
        account_table = self._conn.execute(
            """SELECT 1 FROM sqlite_master
               WHERE type = 'table' AND name = 'web_users'"""
        ).fetchone()
        verified = None
        if account_table is not None:
            verified = self._conn.execute(
                """SELECT 1 FROM web_users
                   WHERE id = ? AND role = 'user'
                     AND status = 'active' AND email_verified = 1""",
                (reporter_id,),
            ).fetchone()
        if verified is None:
            raise ReporterNotEligible(
                "Private Meldungen benötigen ein zugelassenes Konto."
            )

    def _raise_missing_or_transition(self, report_id: int, *, reporter_id: int) -> None:
        owned = self._conn.execute(
            "SELECT 1 FROM civic_reports WHERE id = ? AND reporter_id = ?",
            (report_id, reporter_id),
        ).fetchone()
        if owned is None:
            raise PrivateReportNotFound("Meldung nicht gefunden.")
        raise InvalidReportTransition("Dieser Meldeentwurf kann nicht mehr geändert werden.")

    def list_owned_reports(
        self,
        *,
        reporter_id: int,
        limit: int,
        offset: int,
    ) -> PrivateReportPage:
        """Return a bounded, newest-first page of the owner's private reports."""
        if (
            type(limit) is not int
            or limit < 1
            or limit > 50
            or type(offset) is not int
            or offset < 0
            or offset > _SQLITE_INTEGER_MAX
        ):
            raise ValueError("Ungültige Seitenauswahl.")
        if not _is_storage_id(reporter_id):
            raise ReporterNotEligible(
                "Private Meldungen benötigen ein zugelassenes Konto."
            )
        self._require_eligible_reporter(reporter_id)
        total = int(
            self._conn.execute(
                "SELECT COUNT(*) FROM civic_reports WHERE reporter_id = ?",
                (reporter_id,),
            ).fetchone()[0]
        )
        rows = self._conn.execute(
            """SELECT id,
                      CASE WHEN status = 'submitted'
                           THEN confirmed_text ELSE draft_text END AS text_preview,
                      category, scope_kind, observed_at, status,
                      content_revision, submitted_at, updated_at
               FROM civic_reports
               WHERE reporter_id = ?
               ORDER BY updated_at DESC, id DESC
               LIMIT ? OFFSET ?""",
            (reporter_id, limit, offset),
        ).fetchall()
        return PrivateReportPage(
            reports=tuple(
                PrivateReportSummary(
                    id=int(row["id"]),
                    text_preview=str(row["text_preview"])[
                        :_PRIVATE_REPORT_PREVIEW_LENGTH
                    ],
                    category=cast(ProblemCategory, row["category"]),
                    scope_kind=cast(ScopeKind, row["scope_kind"]),
                    observed_on=str(row["observed_at"]),
                    state=cast(ReportState, row["status"]),
                    content_revision=int(row["content_revision"]),
                    submitted_at=row["submitted_at"],
                    updated_at=str(row["updated_at"]),
                )
                for row in rows
            ),
            total=total,
        )

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
            category=cast(ProblemCategory, row["category"]),
            scope_kind=cast(ScopeKind, row["scope_kind"]),
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
