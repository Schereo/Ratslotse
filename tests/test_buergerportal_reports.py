"""Private Meldungs-Domäne: Verhalten an der Store- und Migrationsseam."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import sqlite3

import pytest


def _insert_public_projection(database) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute(
            """INSERT INTO civic_problems (
                   title, summary, category, tags_json, scope_kind,
                   location_label, latitude, longitude, status,
                   independent_reports, first_observed_at, last_observed_at,
                   published_at, updated_at
               ) VALUES (
                   'Fiktives öffentliches Problem', 'Öffentliche Zusammenfassung',
                   'public_space', '[]', 'point', 'Fiktiver Ort', 53.143, 8.214,
                   'new', 2, '2026-08-30T12:00:00+00:00',
                   '2026-09-01T12:00:00+00:00', '2026-09-01T12:00:00+00:00',
                   '2026-09-01T12:00:00+00:00'
               )"""
        )
        connection.execute(
            """INSERT INTO civic_problem_feature_examples (
                   id, example_key, title, summary, category, scope_kind,
                   location_label, latitude, longitude, status,
                   independent_reports, last_observed_at
               ) VALUES (
                   -1071001, 'issue-1071-isolation', 'Fiktives Feature-Problem',
                   'Fiktive Feature-Zusammenfassung', 'mobility', 'point',
                   'Fiktiver Feature-Ort', 53.144, 8.215, 'new', 3,
                   '2026-09-01T12:00:00+00:00'
               )"""
        )


def _insert_verified_accounts(database, *reporter_ids: int) -> None:
    from kern.store import Store

    store = Store(database)
    with store._conn:
        for reporter_id in reporter_ids:
            store._conn.execute(
                """INSERT OR IGNORE INTO web_users (
                       id, email, password_hash, role, status, email_verified, created_at
                   ) VALUES (?, ?, 'x', 'user', 'active', 1, '2026-09-01')""",
                (reporter_id, f"meldung-{reporter_id}@test.de"),
            )
    store.close()


def _create_submitted_citywide_report(
    database,
    confirmed_text: str,
    *,
    reporter_id: int = 17,
    reject_screening: bool = False,
):
    from buergerportal.reports import DraftContent, PrivateReportStore

    _insert_verified_accounts(database, reporter_id)
    store = PrivateReportStore(database)
    report_id = store.create_draft(
        reporter_id=reporter_id,
        content=DraftContent(
            text="Fiktiver Entwurf",
            category="other",
            scope_kind="citywide",
            observed_on="2026-09-01",
        ),
    )
    if reject_screening:
        with sqlite3.connect(database) as connection:
            connection.execute(
                """CREATE TRIGGER test_reject_local_screening
                       BEFORE INSERT ON civic_report_local_screenings
                       BEGIN
                           SELECT RAISE(ABORT, 'simulated local screening failure');
                       END"""
            )
    submitted = store.submit_owned_draft(
        report_id,
        reporter_id=reporter_id,
        confirmed_text=confirmed_text,
        expected_revision=0,
    )
    return store, submitted


def _private_schema_signature(database) -> list[tuple[str, str, str | None]]:
    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            """SELECT type, name, sql
               FROM sqlite_master
               WHERE tbl_name IN (
                   'civic_reports', 'civic_report_observations',
                   'civic_report_local_screenings',
                   'civic_report_schema_migrations'
               )
               ORDER BY type, name"""
        ).fetchall()
    return [
        (object_type, name, " ".join(sql.split()) if sql else None)
        for object_type, name, sql in rows
    ]


def _private_data_schema_signature(database) -> list[tuple[str, str, str | None]]:
    return [
        row
        for row in _private_schema_signature(database)
        if row[1] != "civic_report_schema_migrations"
    ]


def _drop_local_screening_schema(connection: sqlite3.Connection) -> None:
    connection.execute("DROP TABLE IF EXISTS civic_report_local_screenings")


def _drop_private_triggers(connection: sqlite3.Connection) -> None:
    triggers = connection.execute(
        """SELECT name FROM sqlite_master
           WHERE type = 'trigger' AND name LIKE 'trg_civic_report%'"""
    ).fetchall()
    for (trigger,) in triggers:
        connection.execute(f'DROP TRIGGER "{trigger}"')


def _downgrade_private_schema_to_version_two(database) -> None:
    with sqlite3.connect(database) as connection:
        _drop_local_screening_schema(connection)
        _drop_private_triggers(connection)
        # Repräsentative Triggernamen aus dem Stand vor der Folgemigration:
        # Version 3 muss bestehende Definitionen ersetzen, nicht nur ergänzen.
        connection.executescript(
            """CREATE TRIGGER trg_civic_reports_submitted_content_no_update
                   BEFORE UPDATE OF draft_text ON civic_reports
                   WHEN OLD.status = 'submitted'
                   BEGIN
                       SELECT RAISE(ABORT, 'pre-fix submitted trigger');
                   END;
               CREATE TRIGGER trg_civic_reports_revision_requires_observation
                   BEFORE UPDATE OF content_revision ON civic_reports
                   BEGIN
                       SELECT RAISE(ABORT, 'pre-fix revision trigger');
                   END;
               CREATE TRIGGER trg_civic_report_observations_match_revision
                   BEFORE INSERT ON civic_report_observations
                   BEGIN
                       SELECT RAISE(ABORT, 'pre-fix observation trigger');
                   END;
               DROP INDEX IF EXISTS uq_civic_report_observations_revision;
               DELETE FROM civic_report_schema_migrations WHERE version >= 3;"""
        )


def _downgrade_private_schema_to_version_one(database) -> None:
    _downgrade_private_schema_to_version_two(database)
    with sqlite3.connect(database) as connection:
        _drop_private_triggers(connection)
        connection.executescript(
            """DROP TABLE civic_report_observations;
               DELETE FROM civic_report_schema_migrations WHERE version >= 2;"""
        )


def _install_pre_v6_owner_triggers(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """DROP TRIGGER trg_civic_reports_owner_insert;
           DROP TRIGGER trg_civic_reports_owner_update;
           CREATE TRIGGER trg_civic_reports_owner_insert
               BEFORE INSERT ON civic_reports
               WHEN NOT EXISTS (
                   SELECT 1 FROM web_users
                   WHERE id = NEW.reporter_id AND status = 'active'
                     AND email_verified = 1
               )
               BEGIN
                   SELECT RAISE(ABORT, 'pre-v6 owner trigger');
               END;
           CREATE TRIGGER trg_civic_reports_owner_update
               BEFORE UPDATE OF reporter_id ON civic_reports
               WHEN NOT EXISTS (
                   SELECT 1 FROM web_users
                   WHERE id = NEW.reporter_id AND status = 'active'
                     AND email_verified = 1
               )
               BEGIN
                   SELECT RAISE(ABORT, 'pre-v6 owner trigger');
               END;"""
    )


def _downgrade_private_schema_to_version_four(database) -> None:
    with sqlite3.connect(database) as connection:
        _drop_local_screening_schema(connection)
        connection.executescript(
            """DROP TRIGGER trg_civic_reports_idempotency_pair_insert;
               DROP TRIGGER trg_civic_reports_idempotency_pair_update;
               DROP TRIGGER trg_civic_reports_idempotency_no_update;
               DROP INDEX uq_civic_reports_owner_idempotency;
               ALTER TABLE civic_reports DROP COLUMN creation_fingerprint;
               ALTER TABLE civic_reports DROP COLUMN idempotency_key;
               DELETE FROM civic_report_schema_migrations WHERE version >= 5;"""
        )
        _install_pre_v6_owner_triggers(connection)


def _downgrade_private_schema_to_version_five(database) -> None:
    with sqlite3.connect(database) as connection:
        _drop_local_screening_schema(connection)
        _install_pre_v6_owner_triggers(connection)
        connection.execute(
            "DELETE FROM civic_report_schema_migrations WHERE version >= 6"
        )


def test_controlled_domain_types_match_their_runtime_values():
    from typing import get_args

    from buergerportal.domain import (
        PROBLEM_CATEGORIES,
        SCOPE_KINDS,
        ProblemCategory,
        ScopeKind,
    )

    from buergerportal.reports import (
        LOCAL_SCREENING_OUTCOMES,
        LOCAL_SCREENING_REASONS,
        LocalScreeningOutcome,
        LocalScreeningReason,
    )

    assert get_args(ProblemCategory) == PROBLEM_CATEGORIES
    assert get_args(ScopeKind) == SCOPE_KINDS
    assert get_args(LocalScreeningOutcome) == LOCAL_SCREENING_OUTCOMES
    assert get_args(LocalScreeningReason) == LOCAL_SCREENING_REASONS


def test_observation_date_uses_oldenburg_civil_day(monkeypatch, tmp_path):
    from datetime import date, datetime, timezone

    import buergerportal.reports as reports

    assert reports._oldenburg_today(
        datetime(2026, 3, 28, 23, 30, tzinfo=timezone.utc)
    ) == date(2026, 3, 29)
    assert reports._oldenburg_today(
        datetime(2026, 10, 24, 22, 30, tzinfo=timezone.utc)
    ) == date(2026, 10, 25)

    database = tmp_path / "ratslotse.sqlite"
    _insert_verified_accounts(database, 16)
    monkeypatch.setattr(reports, "_oldenburg_today", lambda: date(2026, 9, 5))
    store = reports.PrivateReportStore(database)

    draft_id = store.create_draft(
        reporter_id=16,
        content=reports.DraftContent(
            text="Fiktive Beobachtung kurz nach Mitternacht in Oldenburg.",
            category="other",
            scope_kind="citywide",
            observed_on="2026-09-05",
        ),
    )

    assert store.get_owned_report(draft_id, reporter_id=16) is not None
    with pytest.raises(ValueError, match="Beobachtungsdatum"):
        store.create_draft(
            reporter_id=16,
            content=reports.DraftContent(
                text="Fiktive Beobachtung vom Folgetag.",
                category="other",
                scope_kind="citywide",
                observed_on="2026-09-06",
            ),
        )
    store.close()


def test_drafts_require_an_eligible_reporter_account(tmp_path):
    from buergerportal.reports import DraftContent, PrivateReportStore
    from kern.store import Store

    database = tmp_path / "ratslotse.sqlite"
    account_store = Store(database)
    pending_id = account_store.create_web_user(
        "offen@test.de",
        "x",
        status="pending",
        email_verified=False,
    )
    verified_id = account_store.create_web_user(
        "bestaetigt@test.de",
        "x",
        status="active",
        email_verified=True,
    )
    admin_id = account_store.create_web_user(
        "meldung-admin@test.de",
        "x",
        role="admin",
        status="active",
        email_verified=True,
    )
    account_store.close()
    private_store = PrivateReportStore(database)
    content = DraftContent(
        text="Fiktiver Entwurf",
        category="public_space",
        scope_kind="citywide",
        observed_on="2026-09-01",
    )

    with pytest.raises(ValueError, match="zugelassenes Konto"):
        private_store.create_draft(reporter_id=999_999, content=content)
    with pytest.raises(ValueError, match="zugelassenes Konto"):
        private_store.create_draft(reporter_id=pending_id, content=content)
    with pytest.raises(ValueError, match="zugelassenes Konto"):
        private_store.create_draft(reporter_id=admin_id, content=content)
    draft_id = private_store.create_draft(reporter_id=verified_id, content=content)
    account_store = Store(database)
    account_store.set_web_user_role(verified_id, "admin")
    account_store.close()
    with pytest.raises(ValueError, match="zugelassenes Konto"):
        private_store.submit_owned_draft(
            draft_id,
            reporter_id=verified_id,
            confirmed_text="Bestätigte fiktive Beobachtung",
        )
    account_store = Store(database)
    account_store.set_web_user_role(verified_id, "user")
    account_store.set_web_user_status(verified_id, "suspended")
    account_store.close()

    with pytest.raises(ValueError, match="zugelassenes Konto"):
        private_store.submit_owned_draft(
            draft_id,
            reporter_id=verified_id,
            confirmed_text="Bestätigte fiktive Beobachtung",
        )
    assert private_store.get_owned_report(draft_id, reporter_id=verified_id) is not None
    private_store.close()


def test_owner_can_create_and_read_a_private_draft(tmp_path):
    from buergerportal.reports import DraftContent, PrivateReportStore

    database = tmp_path / "ratslotse.sqlite"
    _insert_verified_accounts(database, 17, 18)
    store = PrivateReportStore(database)
    draft_id = store.create_draft(
        reporter_id=17,
        content=DraftContent(
            text="  Am fiktiven Kanal ist der Weg abends nicht beleuchtet.  ",
            category="public_space",
            scope_kind="point",
            location_label="  Fiktiver Kanalweg  ",
            latitude=53.143,
            longitude=8.214,
            observed_on="2026-09-01",
        ),
    )

    draft = store.get_owned_report(draft_id, reporter_id=17)

    assert draft is not None
    assert draft.id == draft_id
    assert draft.draft_text == "Am fiktiven Kanal ist der Weg abends nicht beleuchtet."
    assert draft.confirmed_text is None
    assert draft.category == "public_space"
    assert draft.scope_kind == "point"
    assert draft.location_label == "Fiktiver Kanalweg"
    assert draft.latitude == 53.143
    assert draft.longitude == 8.214
    assert draft.observed_on == "2026-09-01"
    assert draft.state == "draft"
    assert draft.content_revision == 0
    assert draft.submitted_at is None
    assert draft.observations == ()
    assert store.get_owned_report(draft_id, reporter_id=18) is None
    store.close()


def test_drafts_enforce_controlled_private_content_and_geography(tmp_path):
    from buergerportal.domain import SCOPE_KINDS
    from buergerportal.reports import DraftContent, PrivateReportStore

    database = tmp_path / "ratslotse.sqlite"
    _insert_verified_accounts(database, 17)
    store = PrivateReportStore(database)
    invalid_contents = (
        DraftContent("", "public_space", "citywide", "2026-09-01"),
        DraftContent("Text", "unknown", "citywide", "2026-09-01"),
        DraftContent("Text", "public_space", "unknown", "2026-09-01"),
        DraftContent("Text", "public_space", "point", "2026-09-01"),
        DraftContent(
            "Text", "public_space", "citywide", "2026-09-01",
            location_label="Unzulässig genauer Ort",
        ),
        DraftContent(
            "Text", "public_space", "citywide", "2026-09-01",
            latitude=53.143, longitude=8.214,
        ),
        DraftContent(
            "Text", "public_space", "point", "2026-09-01",
            location_label="Fiktiver Ort", latitude=52.52, longitude=13.405,
        ),
        DraftContent("Text", "public_space", "citywide", "2999-01-01"),
    )
    for content in invalid_contents:
        with pytest.raises(ValueError):
            store.create_draft(reporter_id=17, content=content)

    for index, scope_kind in enumerate(SCOPE_KINDS):
        is_citywide = scope_kind == "citywide"
        store.create_draft(
            reporter_id=17,
            content=DraftContent(
                text=f"Fiktiver Entwurf {index}",
                category="public_space",
                scope_kind=scope_kind,
                observed_on="2026-09-01",
                location_label="" if is_citywide else "Fiktiver Ort",
                latitude=None if is_citywide else 53.143,
                longitude=None if is_citywide else 8.214,
            ),
        )
    assert store.erase_reporter_data(reporter_id=17) == len(SCOPE_KINDS)
    store.close()


def test_database_enforces_private_report_invariants(tmp_path):
    from buergerportal.reports import DraftContent, PrivateReportStore
    from kern.store import Store

    database = tmp_path / "ratslotse.sqlite"
    _insert_verified_accounts(database, 17)
    account_store = Store(database)
    admin_id = account_store.create_web_user(
        "invarianten-admin@test.de",
        "x",
        role="admin",
        status="active",
        email_verified=True,
    )
    account_store.close()
    store = PrivateReportStore(database)
    draft_id = store.create_draft(
        reporter_id=17,
        content=DraftContent(
            text="Fiktiver Entwurf",
            category="public_space",
            scope_kind="point",
            observed_on="2026-09-01",
            location_label="Fiktiver Ort",
            latitude=53.143,
            longitude=8.214,
        ),
    )
    store.close()

    invalid_assignments = (
        "reporter_id = 0",
        f"reporter_id = {admin_id}",
        "category = 'unknown'",
        "scope_kind = 'citywide'",
        "content_revision = -1",
        "observed_at = 'kein-datum'",
        "draft_text = 'Änderung ohne neue Revision'",
        "status = 'submitted'",
    )
    with sqlite3.connect(database) as connection:
        for assignment in invalid_assignments:
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    f"UPDATE civic_reports SET {assignment} WHERE id = ?",
                    (draft_id,),
                )
            connection.rollback()
        with pytest.raises(sqlite3.IntegrityError, match="submission requires new revision"):
            connection.execute(
                """UPDATE civic_reports
                   SET status = 'submitted', confirmed_text = 'Bestätigt',
                       submitted_at = updated_at
                   WHERE id = ?""",
                (draft_id,),
            )


def test_only_owner_can_change_a_draft(tmp_path):
    from buergerportal.reports import (
        DraftContent,
        PrivateReportNotFound,
        PrivateReportStore,
    )

    database = tmp_path / "ratslotse.sqlite"
    _insert_verified_accounts(database, 17, 18)
    store = PrivateReportStore(database)
    draft_id = store.create_draft(
        reporter_id=17,
        content=DraftContent(
            text="Erste fiktive Beschreibung",
            category="public_space",
            scope_kind="point",
            location_label="Fiktiver Kanalweg",
            latitude=53.143,
            longitude=8.214,
            observed_on="2026-09-01",
        ),
    )
    changed = DraftContent(
        text="Korrigierte fiktive Beschreibung",
        category="accessibility",
        scope_kind="facility",
        location_label="Fiktive Musterhalle",
        latitude=53.144,
        longitude=8.215,
        observed_on="2026-09-02",
    )

    with pytest.raises(PrivateReportNotFound):
        store.update_owned_draft(draft_id, reporter_id=18, content=changed)
    draft = store.update_owned_draft(draft_id, reporter_id=17, content=changed)

    assert draft.draft_text == "Korrigierte fiktive Beschreibung"
    assert draft.category == "accessibility"
    assert draft.scope_kind == "facility"
    assert draft.location_label == "Fiktive Musterhalle"
    assert draft.latitude == 53.144
    assert draft.longitude == 8.215
    assert draft.observed_on == "2026-09-02"
    assert draft.content_revision == 1
    store.close()


def test_submission_is_owner_bound_once_and_records_the_first_observation(tmp_path):
    from buergerportal.reports import (
        DraftContent,
        InvalidReportTransition,
        PrivateReportNotFound,
        PrivateReportStore,
    )

    database = tmp_path / "ratslotse.sqlite"
    _insert_verified_accounts(database, 17, 18)
    store = PrivateReportStore(database)
    draft_id = store.create_draft(
        reporter_id=17,
        content=DraftContent(
            text="Fiktiver Entwurf",
            category="public_space",
            scope_kind="point",
            location_label="Fiktiver Kanalweg",
            latitude=53.143,
            longitude=8.214,
            observed_on="2026-09-01",
        ),
    )

    with pytest.raises(PrivateReportNotFound):
        store.submit_owned_draft(
            draft_id,
            reporter_id=18,
            confirmed_text="Fremder Absendeversuch",
        )
    submitted = store.submit_owned_draft(
        draft_id,
        reporter_id=17,
        confirmed_text="  Bestätigte fiktive Beobachtung.  ",
    )

    assert submitted.state == "submitted"
    assert submitted.confirmed_text == "Bestätigte fiktive Beobachtung."
    assert submitted.content_revision == 1
    assert submitted.submitted_at is not None
    assert [
        (observation.text, observation.observed_on, observation.content_revision)
        for observation in submitted.observations
    ] == [("Bestätigte fiktive Beobachtung.", "2026-09-01", 1)]
    with pytest.raises(InvalidReportTransition):
        store.submit_owned_draft(
            draft_id,
            reporter_id=17,
            confirmed_text="Doppeltes Absenden",
        )
    with pytest.raises(InvalidReportTransition):
        store.update_owned_draft(
            draft_id,
            reporter_id=17,
            content=DraftContent(
                text="Nachträgliche Entwurfsänderung",
                category="public_space",
                scope_kind="point",
                location_label="Fiktiver Kanalweg",
                latitude=53.143,
                longitude=8.214,
                observed_on="2026-09-01",
            ),
        )
    current = store.get_owned_report(draft_id, reporter_id=17)
    assert current is not None
    assert len(current.observations) == 1
    store.close()


def test_owner_can_locally_screen_a_submitted_report_for_external_review(tmp_path):
    database = tmp_path / "ratslotse.sqlite"
    store, submitted = _create_submitted_citywide_report(
        database,
        "Am fiktiven Platz ist eine Leuchte ausgefallen.",
    )

    screening = store.assess_owned_submission(
        submitted.id,
        reporter_id=17,
        expected_revision=submitted.content_revision,
    )

    assert screening.report_id == submitted.id
    assert screening.content_revision == submitted.content_revision
    assert screening.ruleset_version == 1
    assert screening.outcome == "external_review_candidate"
    assert screening.reason_codes == ()
    assert screening.created_at
    assert store.get_current_owned_screening(
        submitted.id,
        reporter_id=17,
    ) == screening
    assert store.get_owned_external_review_candidate(
        submitted.id,
        reporter_id=17,
        expected_revision=submitted.content_revision,
    ) == screening
    store.close()


def test_local_screening_storage_does_not_copy_identity_or_report_content(tmp_path):
    database = tmp_path / "ratslotse.sqlite"
    store, _submitted = _create_submitted_citywide_report(
        database,
        "Fiktive private Beobachtung.",
    )
    store.close()

    with sqlite3.connect(database) as connection:
        columns = tuple(
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(civic_report_local_screenings)"
            )
        )

    assert columns == (
        "id",
        "report_id",
        "content_revision",
        "ruleset_version",
        "outcome",
        "reason_codes_json",
        "created_at",
    )


def test_submission_runs_the_local_screening_without_external_processing(tmp_path):
    database = tmp_path / "ratslotse.sqlite"
    store, submitted = _create_submitted_citywide_report(
        database,
        "Am fiktiven Ort besteht Lebensgefahr, bitte sofort 112 rufen.",
    )

    screening = store.get_current_owned_screening(submitted.id, reporter_id=17)

    assert submitted.state == "submitted"
    assert screening is not None
    assert screening.content_revision == submitted.content_revision
    assert screening.outcome == "manual_review_only"
    assert screening.reason_codes == ("potential_emergency",)
    assert store.get_owned_external_review_candidate(
        submitted.id,
        reporter_id=17,
        expected_revision=submitted.content_revision,
    ) is None
    store.close()


@pytest.mark.parametrize(
    "confirmed_text",
    (
        "Das ist am fiktiven Ort ein Notfall.",
        "Hier brennt ein fiktives Haus.",
        "Eine Person ist schwer verletzt.",
        "An der fiktiven Leitung besteht Explosionsgefahr.",
    ),
)
def test_obvious_emergency_language_requires_manual_review(
    tmp_path,
    confirmed_text,
):
    database = tmp_path / "ratslotse.sqlite"
    store, submitted = _create_submitted_citywide_report(database, confirmed_text)

    screening = store.get_current_owned_screening(submitted.id, reporter_id=17)

    assert screening is not None
    assert screening.outcome == "manual_review_only"
    assert screening.reason_codes == ("potential_emergency",)
    store.close()


def test_local_screening_failure_never_loses_the_private_submission(
    caplog,
    tmp_path,
):
    database = tmp_path / "ratslotse.sqlite"
    store, submitted = _create_submitted_citywide_report(
        database,
        "Fiktive Beobachtung bleibt sicher privat gespeichert.",
        reject_screening=True,
    )
    retry = store.submit_owned_draft(
        submitted.id,
        reporter_id=17,
        confirmed_text="Fiktive Beobachtung bleibt sicher privat gespeichert.",
        expected_revision=0,
    )

    assert retry == submitted
    assert len(submitted.observations) == 1
    assert store.get_current_owned_screening(submitted.id, reporter_id=17) is None
    assert store.get_owned_external_review_candidate(
        submitted.id,
        reporter_id=17,
        expected_revision=submitted.content_revision,
    ) is None
    assert "Weitergabeprüfung" in caplog.text
    store.close()


def test_local_screening_requires_current_submitted_owned_report(tmp_path):
    from buergerportal.reports import (
        DraftContent,
        InvalidReportTransition,
        PrivateReportNotFound,
        PrivateReportStore,
    )

    database = tmp_path / "ratslotse.sqlite"
    _insert_verified_accounts(database, 17, 18)
    store = PrivateReportStore(database)
    report_id = store.create_draft(
        reporter_id=17,
        content=DraftContent(
            text="Fiktiver Entwurf",
            category="other",
            scope_kind="citywide",
            observed_on="2026-09-01",
        ),
    )

    with pytest.raises(InvalidReportTransition):
        store.assess_owned_submission(
            report_id,
            reporter_id=17,
            expected_revision=0,
        )
    submitted = store.submit_owned_draft(
        report_id,
        reporter_id=17,
        confirmed_text="Fiktive eingereichte Beobachtung.",
    )
    with pytest.raises(PrivateReportNotFound):
        store.assess_owned_submission(
            report_id,
            reporter_id=18,
            expected_revision=submitted.content_revision,
        )
    with pytest.raises(InvalidReportTransition):
        store.assess_owned_submission(
            report_id,
            reporter_id=17,
            expected_revision=submitted.content_revision - 1,
        )
    with pytest.raises(PrivateReportNotFound):
        store.assess_owned_submission(
            999_999,
            reporter_id=17,
            expected_revision=submitted.content_revision,
        )
    assert store.get_owned_external_review_candidate(
        report_id,
        reporter_id=18,
        expected_revision=submitted.content_revision,
    ) is None
    assert store.get_owned_external_review_candidate(
        999_999,
        reporter_id=17,
        expected_revision=submitted.content_revision,
    ) is None
    assert store.get_owned_external_review_candidate(
        report_id,
        reporter_id=17,
        expected_revision=submitted.content_revision - 1,
    ) is None
    store.close()


@pytest.mark.parametrize(
    "confirmed_text",
    (
        "Seit 2026-09-01 (01.09.2026) sind die fiktiven Laternen 12 und 14 ausgefallen.",
        "Die fiktive Beobachtung stammt vom 01.09.2026.",
        "Der fiktive Termin ist am 01/09/2026.",
        "Der fiktive Rückruf war am 01/09/2026.",
    ),
)
def test_dates_and_civic_numbers_are_not_mistaken_for_contact_data(
    tmp_path,
    confirmed_text,
):
    database = tmp_path / "ratslotse.sqlite"
    store, submitted = _create_submitted_citywide_report(
        database,
        confirmed_text,
    )

    screening = store.get_current_owned_screening(submitted.id, reporter_id=17)

    assert screening is not None
    assert screening.outcome == "external_review_candidate"
    assert screening.reason_codes == ()
    store.close()


def test_unsupported_text_format_requires_manual_review(tmp_path):
    database = tmp_path / "ratslotse.sqlite"
    store, submitted = _create_submitted_citywide_report(
        database,
        "Fiktive Beobachtung mit" + chr(0) + "Steuerzeichen.",
    )

    screening = store.get_current_owned_screening(submitted.id, reporter_id=17)

    assert screening is not None
    assert screening.outcome == "manual_review_only"
    assert screening.reason_codes == ("unsupported_text_format",)
    store.close()


@pytest.mark.parametrize(
    "confirmed_text",
    (
        "Rückfrage bitte an person@example.org senden.",
        "Rückruf zur fiktiven Meldung bitte unter 0441 123456.",
        "Rückruf zur fiktiven Meldung: 0441/12.34.56.",
        "Telefon: 12345678.",
        "Meine Telefonnummer lautet 12345678.",
        "Meine Rückrufnummer ist 12345678.",
        "Meine Nummer ist 12345678.",
        "Bitte zurückrufen: 12345678.",
        "Meine Nummer ist +1 212 555 0199.",
    ),
)
def test_direct_contact_data_requires_manual_review(tmp_path, confirmed_text):
    database = tmp_path / "ratslotse.sqlite"
    store, submitted = _create_submitted_citywide_report(database, confirmed_text)

    screening = store.get_current_owned_screening(submitted.id, reporter_id=17)

    assert screening is not None
    assert screening.outcome == "manual_review_only"
    assert screening.reason_codes == ("direct_contact_data",)
    store.close()


def test_later_observation_requires_a_new_local_screening(tmp_path):
    database = tmp_path / "ratslotse.sqlite"
    store, submitted = _create_submitted_citywide_report(
        database,
        "Erste fiktive Beobachtung ohne Sperrgrund.",
    )
    first_screening = store.get_current_owned_screening(submitted.id, reporter_id=17)
    assert first_screening is not None
    assert first_screening.outcome == "external_review_candidate"

    updated = store.append_owned_observation(
        submitted.id,
        reporter_id=17,
        text="Jetzt besteht am fiktiven Ort Lebensgefahr.",
        observed_on="2026-09-02",
    )

    assert store.get_current_owned_screening(submitted.id, reporter_id=17) is None
    assert store.get_owned_external_review_candidate(
        submitted.id,
        reporter_id=17,
        expected_revision=first_screening.content_revision,
    ) is None
    second_screening = store.assess_owned_submission(
        submitted.id,
        reporter_id=17,
        expected_revision=updated.content_revision,
    )
    assert second_screening.outcome == "manual_review_only"
    assert second_screening.reason_codes == ("potential_emergency",)
    store.close()


def test_local_screening_is_idempotent_under_concurrent_retries(tmp_path):
    from buergerportal.reports import PrivateReportStore

    database = tmp_path / "ratslotse.sqlite"
    first_store, submitted = _create_submitted_citywide_report(
        database,
        "Fiktive Beobachtung für nebenläufige Prüfversuche.",
        reject_screening=True,
    )
    assert first_store.get_current_owned_screening(
        submitted.id,
        reporter_id=17,
    ) is None
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TRIGGER test_reject_local_screening")
    second_store = PrivateReportStore(database)
    barrier = Barrier(2)

    def assess(store):
        barrier.wait()
        return store.assess_owned_submission(
            submitted.id,
            reporter_id=17,
            expected_revision=submitted.content_revision,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        screenings = list(executor.map(assess, (first_store, second_store)))

    assert screenings[0] == screenings[1]
    assert first_store.get_current_owned_screening(
        submitted.id,
        reporter_id=17,
    ) == screenings[0]
    first_store.close()
    second_store.close()


def test_database_keeps_local_screenings_immutable(tmp_path):
    database = tmp_path / "ratslotse.sqlite"
    store, submitted = _create_submitted_citywide_report(
        database,
        "Fiktive Beobachtung für unveränderliche Prüfevidenz.",
    )
    store.close()

    with sqlite3.connect(database) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="screenings are immutable"):
            connection.execute(
                """UPDATE civic_report_local_screenings
                   SET outcome = 'manual_review_only'
                   WHERE report_id = ?""",
                (submitted.id,),
            )
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError, match="screenings are append-only"):
            connection.execute(
                "DELETE FROM civic_report_local_screenings WHERE report_id = ?",
                (submitted.id,),
            )


def test_database_rejects_screening_for_a_stale_report_revision(tmp_path):
    database = tmp_path / "ratslotse.sqlite"
    store, submitted = _create_submitted_citywide_report(
        database,
        "Erste fiktive Beobachtung.",
    )
    store.append_owned_observation(
        submitted.id,
        reporter_id=17,
        text="Spätere fiktive Beobachtung.",
        observed_on="2026-09-02",
    )
    store.close()

    with sqlite3.connect(database) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="current submitted revision"):
            connection.execute(
                """INSERT INTO civic_report_local_screenings (
                       report_id, content_revision, ruleset_version,
                       outcome, reason_codes_json, created_at
                   ) VALUES (?, ?, 1, 'external_review_candidate', '[]', ?)""",
                (submitted.id, submitted.content_revision, submitted.submitted_at),
            )


def test_database_rejects_screening_for_an_ineligible_owner(tmp_path):
    from buergerportal.reports import PrivateReportStore
    from kern.store import Store

    database = tmp_path / "ratslotse.sqlite"
    private_store, submitted = _create_submitted_citywide_report(
        database,
        "Fiktive Beobachtung vor der Kontosperre.",
    )
    private_store.close()
    account_store = Store(database)
    account_store.set_web_user_status(17, "suspended")
    account_store.close()
    ineligible_store = PrivateReportStore(database)
    assert ineligible_store.get_owned_external_review_candidate(
        submitted.id,
        reporter_id=17,
        expected_revision=submitted.content_revision,
    ) is None
    ineligible_store.close()

    with sqlite3.connect(database) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="eligible owner"):
            connection.execute(
                """INSERT INTO civic_report_local_screenings (
                       report_id, content_revision, ruleset_version,
                       outcome, reason_codes_json, created_at
                   ) VALUES (?, ?, 2, 'external_review_candidate', '[]', ?)""",
                (submitted.id, submitted.content_revision, submitted.submitted_at),
            )


def test_database_rejects_uncontrolled_local_screening_results(tmp_path):
    database = tmp_path / "ratslotse.sqlite"
    store, submitted = _create_submitted_citywide_report(
        database,
        "Fiktive Beobachtung für kontrollierte Prüfergebnisse.",
    )
    store.close()

    invalid_results = (
        ("external_review_candidate", '["potential_emergency"]'),
        ("manual_review_only", "[]"),
        ("manual_review_only", "not-json"),
        ("manual_review_only", "{}"),
        ("manual_review_only", '["unknown_reason"]'),
        (
            "manual_review_only",
            '["potential_emergency","potential_emergency"]',
        ),
    )
    with sqlite3.connect(database) as connection:
        for outcome, reason_codes in invalid_results:
            with pytest.raises(sqlite3.IntegrityError, match="controlled screening result"):
                connection.execute(
                    """INSERT INTO civic_report_local_screenings (
                           report_id, content_revision, ruleset_version,
                           outcome, reason_codes_json, created_at
                       ) VALUES (?, ?, 1, ?, ?, ?)""",
                    (
                        submitted.id,
                        submitted.content_revision,
                        outcome,
                        reason_codes,
                        submitted.submitted_at,
                    ),
                )
            connection.rollback()


def test_later_observations_append_without_replacing_the_first(tmp_path):
    from buergerportal.reports import (
        DraftContent,
        InvalidReportTransition,
        PrivateReportNotFound,
        PrivateReportStore,
    )

    database = tmp_path / "ratslotse.sqlite"
    _insert_verified_accounts(database, 17, 18)
    store = PrivateReportStore(database)
    draft_id = store.create_draft(
        reporter_id=17,
        content=DraftContent(
            text="Fiktiver Entwurf",
            category="public_space",
            scope_kind="point",
            location_label="Fiktiver Kanalweg",
            latitude=53.143,
            longitude=8.214,
            observed_on="2026-08-30",
        ),
    )
    with pytest.raises(InvalidReportTransition):
        store.append_owned_observation(
            draft_id,
            reporter_id=17,
            text="Zu früher Nachtrag",
            observed_on="2026-09-01",
        )
    submitted = store.submit_owned_draft(
        draft_id,
        reporter_id=17,
        confirmed_text="Erste bestätigte Beobachtung",
    )
    first_observation = submitted.observations[0]

    with pytest.raises(PrivateReportNotFound):
        store.append_owned_observation(
            draft_id,
            reporter_id=18,
            text="Fremder Nachtrag",
            observed_on="2026-09-01",
        )
    with pytest.raises(PrivateReportNotFound):
        store.append_owned_observation(
            999_999,
            reporter_id=17,
            text="Nachtrag zu unbekannter Meldung",
            observed_on="2026-09-01",
        )
    updated = store.append_owned_observation(
        draft_id,
        reporter_id=17,
        text="  Das fiktive Problem besteht weiterhin.  ",
        observed_on="2026-09-02",
    )

    assert updated.confirmed_text == "Erste bestätigte Beobachtung"
    assert updated.content_revision == 2
    assert updated.observations[0] == first_observation
    assert [
        (observation.text, observation.observed_on, observation.content_revision)
        for observation in updated.observations
    ] == [
        ("Erste bestätigte Beobachtung", "2026-08-30", 1),
        ("Das fiktive Problem besteht weiterhin.", "2026-09-02", 2),
    ]
    store.close()


def test_database_keeps_observations_immutable_and_revision_bound(tmp_path):
    from buergerportal.reports import DraftContent, PrivateReportStore

    database = tmp_path / "ratslotse.sqlite"
    _insert_verified_accounts(database, 17)
    store = PrivateReportStore(database)
    draft_id = store.create_draft(
        reporter_id=17,
        content=DraftContent(
            text="Fiktiver Entwurf",
            category="public_space",
            scope_kind="citywide",
            observed_on="2026-09-01",
        ),
    )
    submitted = store.submit_owned_draft(
        draft_id,
        reporter_id=17,
        confirmed_text="Bestätigte fiktive Beobachtung",
    )
    observation = submitted.observations[0]
    store.close()

    with sqlite3.connect(database) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="submitted reports are immutable"):
            connection.execute(
                "UPDATE civic_reports SET draft_text = 'ersetzt' WHERE id = ?",
                (draft_id,),
            )
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError, match="report revision requires observation"):
            connection.execute(
                "UPDATE civic_reports SET content_revision = 99 WHERE id = ?",
                (draft_id,),
            )
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError, match="report observations are immutable"):
            connection.execute(
                "UPDATE civic_report_observations SET text = 'ersetzt' WHERE report_id = ?",
                (draft_id,),
            )
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "DELETE FROM civic_report_observations WHERE report_id = ?",
                (draft_id,),
            )
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError, match="must match"):
            connection.execute(
                """INSERT INTO civic_report_observations (
                       report_id, content_revision, text, observed_at, created_at
                   ) VALUES (?, 99, 'unzulässig', '2026-09-02', ?)""",
                (draft_id, observation.created_at),
            )


def test_concurrent_submission_creates_exactly_one_first_observation(tmp_path):
    from buergerportal.reports import (
        DraftContent,
        InvalidReportTransition,
        PrivateReportStore,
    )

    database = tmp_path / "ratslotse.sqlite"
    _insert_verified_accounts(database, 17)
    first_store = PrivateReportStore(database)
    draft_id = first_store.create_draft(
        reporter_id=17,
        content=DraftContent(
            text="Fiktiver Entwurf",
            category="public_space",
            scope_kind="point",
            location_label="Fiktiver Kanalweg",
            latitude=53.143,
            longitude=8.214,
            observed_on="2026-09-01",
        ),
    )
    second_store = PrivateReportStore(database)
    barrier = Barrier(2)

    def submit(store, text):
        barrier.wait()
        try:
            store.submit_owned_draft(
                draft_id,
                reporter_id=17,
                confirmed_text=text,
            )
        except InvalidReportTransition:
            return "rejected"
        return "submitted"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                submit,
                (first_store, second_store),
                ("Erster Absendeversuch", "Zweiter Absendeversuch"),
            )
        )

    assert sorted(results) == ["rejected", "submitted"]
    report = first_store.get_owned_report(draft_id, reporter_id=17)
    assert report is not None
    assert len(report.observations) == 1
    assert report.observations[0].text == report.confirmed_text
    first_store.close()
    second_store.close()


def test_erasing_reporter_data_removes_only_private_owned_content(tmp_path):
    from buergerportal.reports import DraftContent, PrivateReportStore
    from buergerportal.store import ProblemStore

    database = tmp_path / "ratslotse.sqlite"
    public_store = ProblemStore(database)
    _insert_public_projection(database)
    public_before = public_store.list_public_problems()
    _insert_verified_accounts(database, 17, 18)
    private_store = PrivateReportStore(database)

    first_id = private_store.create_draft(
        reporter_id=17,
        content=DraftContent(
            text="Nur privat: Entwurf Alpha",
            category="public_space",
            scope_kind="citywide",
            observed_on="2026-09-01",
        ),
    )
    second_id = private_store.create_draft(
        reporter_id=17,
        content=DraftContent(
            text="Nur privat: Entwurf Beta",
            category="mobility",
            scope_kind="point",
            location_label="Nur privat: genauer Fantasieort",
            latitude=53.143,
            longitude=8.214,
            observed_on="2026-09-01",
        ),
    )
    private_store.submit_owned_draft(
        second_id,
        reporter_id=17,
        confirmed_text="Nur privat: bestätigter Inhalt",
    )
    updated = private_store.append_owned_observation(
        second_id,
        reporter_id=17,
        text="Nur privat: wiederholte Beobachtung",
        observed_on="2026-09-02",
    )
    private_store.assess_owned_submission(
        second_id,
        reporter_id=17,
        expected_revision=updated.content_revision,
    )
    other_id = private_store.create_draft(
        reporter_id=18,
        content=DraftContent(
            text="Fremder privater Entwurf bleibt erhalten",
            category="housing",
            scope_kind="citywide",
            observed_on="2026-09-02",
        ),
    )

    assert public_store.list_public_problems() == public_before
    with sqlite3.connect(database) as connection:
        screening_columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(civic_report_local_screenings)"
            )
        }
    assert screening_columns == {
        "id", "report_id", "content_revision", "ruleset_version",
        "outcome", "reason_codes_json", "created_at",
    }
    assert private_store.erase_reporter_data(reporter_id=17) == 2

    assert private_store.get_owned_report(first_id, reporter_id=17) is None
    assert private_store.get_owned_report(second_id, reporter_id=17) is None
    assert private_store.get_owned_report(other_id, reporter_id=18) is not None
    assert public_store.list_public_problems() == public_before
    private_store.close()
    public_store.close()
    with sqlite3.connect(database) as connection:
        dump = "\n".join(connection.iterdump())
    assert "Entwurf Alpha" not in dump
    assert "Entwurf Beta" not in dump
    assert "genauer Fantasieort" not in dump
    assert "bestätigter Inhalt" not in dump
    assert "wiederholte Beobachtung" not in dump


def test_private_migration_adds_idempotency_to_a_grown_version_four_schema(tmp_path):
    from buergerportal.reports import DraftContent, PrivateReportStore

    database = tmp_path / "ratslotse.sqlite"
    _insert_verified_accounts(database, 17)
    old_store = PrivateReportStore(database)
    old_draft_id = old_store.create_draft(
        reporter_id=17,
        content=DraftContent(
            text="Fiktiver Entwurf vor der Idempotenzmigration",
            category="public_space",
            scope_kind="citywide",
            observed_on="2026-09-01",
        ),
    )
    old_store.close()
    _downgrade_private_schema_to_version_four(database)

    migrated_store = PrivateReportStore(database)
    content = DraftContent(
        text="Fiktiver idempotenter Entwurf nach der Migration",
        category="mobility",
        scope_kind="citywide",
        observed_on="2026-09-02",
    )
    first = migrated_store.create_owned_draft_idempotent(
        reporter_id=17,
        idempotency_key="fiktiver-migrations-request",
        content=content,
    )
    retry = migrated_store.create_owned_draft_idempotent(
        reporter_id=17,
        idempotency_key="fiktiver-migrations-request",
        content=content,
    )
    preserved = migrated_store.get_owned_report(old_draft_id, reporter_id=17)
    migrated_store.close()
    migrated_schema = _private_schema_signature(database)
    reopened_store = PrivateReportStore(database)
    reopened_store.close()
    fresh_database = tmp_path / "fresh.sqlite"
    fresh_store = PrivateReportStore(fresh_database)
    fresh_store.close()

    assert preserved is not None
    assert preserved.draft_text == "Fiktiver Entwurf vor der Idempotenzmigration"
    assert retry == first
    assert _private_schema_signature(database) == migrated_schema
    assert _private_data_schema_signature(database) == _private_data_schema_signature(
        fresh_database
    )
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT version FROM civic_report_schema_migrations ORDER BY version"
        ).fetchall() == [(1,), (2,), (3,), (4,), (5,), (6,), (7,)]


def test_private_migration_refreshes_owner_triggers_after_applied_version_five(
    tmp_path,
):
    from buergerportal.reports import PrivateReportStore
    from kern.store import Store

    database = tmp_path / "ratslotse.sqlite"
    account_store = Store(database)
    admin_id = account_store.create_web_user(
        "migration-admin@test.de",
        "x",
        role="admin",
        status="active",
        email_verified=True,
    )
    account_store.close()
    old_store = PrivateReportStore(database)
    old_store.close()
    _downgrade_private_schema_to_version_five(database)

    with sqlite3.connect(database) as connection:
        old_trigger = connection.execute(
            """SELECT sql FROM sqlite_master
               WHERE type = 'trigger' AND name = 'trg_civic_reports_owner_insert'"""
        ).fetchone()[0]
    assert "role = 'user'" not in old_trigger

    migrated_store = PrivateReportStore(database)
    migrated_store.close()
    reopened_store = PrivateReportStore(database)
    reopened_store.close()
    fresh_database = tmp_path / "fresh.sqlite"
    fresh_store = PrivateReportStore(fresh_database)
    fresh_store.close()

    with sqlite3.connect(database) as connection:
        migrated_trigger = connection.execute(
            """SELECT sql FROM sqlite_master
               WHERE type = 'trigger' AND name = 'trg_civic_reports_owner_insert'"""
        ).fetchone()[0]
        versions = connection.execute(
            "SELECT version FROM civic_report_schema_migrations ORDER BY version"
        ).fetchall()
        with pytest.raises(sqlite3.IntegrityError, match="eligible account"):
            connection.execute(
                """INSERT INTO civic_reports (
                       reporter_id, draft_text, category, scope_kind,
                       observed_at, created_at, updated_at
                   ) VALUES (
                       ?, 'Unzulässiger Admin-Entwurf', 'other', 'citywide',
                       '2026-09-01', '2026-09-01T12:00:00+00:00',
                       '2026-09-01T12:00:00+00:00'
                   )""",
                (admin_id,),
            )
    assert "role = 'user'" in migrated_trigger
    assert versions == [(1,), (2,), (3,), (4,), (5,), (6,), (7,)]
    assert _private_data_schema_signature(database) == _private_data_schema_signature(
        fresh_database
    )


def test_private_migration_upgrades_the_pre_fix_version_two_schema(tmp_path):
    from buergerportal.reports import DraftContent, PrivateReportStore

    database = tmp_path / "ratslotse.sqlite"
    _insert_verified_accounts(database, 17)
    old_store = PrivateReportStore(database)
    draft_id = old_store.create_draft(
        reporter_id=17,
        content=DraftContent(
            text="Fiktiver Entwurf aus Schema-Version 2",
            category="public_space",
            scope_kind="citywide",
            observed_on="2026-09-01",
        ),
    )
    old_store.close()
    _downgrade_private_schema_to_version_two(database)

    migrated_store = PrivateReportStore(database)
    submitted = migrated_store.submit_owned_draft(
        draft_id,
        reporter_id=17,
        confirmed_text="Bestätigte fiktive Beobachtung nach Migration",
    )
    migrated_store.close()
    fresh_database = tmp_path / "fresh.sqlite"
    fresh_store = PrivateReportStore(fresh_database)
    fresh_store.close()

    assert submitted.content_revision == 1
    assert [observation.text for observation in submitted.observations] == [
        "Bestätigte fiktive Beobachtung nach Migration"
    ]
    with sqlite3.connect(database) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="revision requires observation"):
            connection.execute(
                "UPDATE civic_reports SET content_revision = 99 WHERE id = ?",
                (draft_id,),
            )
        versions = connection.execute(
            "SELECT version FROM civic_report_schema_migrations ORDER BY version"
        ).fetchall()
    assert versions == [(1,), (2,), (3,), (4,), (5,), (6,), (7,)]
    assert _private_data_schema_signature(database) == _private_data_schema_signature(
        fresh_database
    )


def test_private_migration_preserves_legacy_reports_without_revision_columns(tmp_path):
    from buergerportal.reports import PrivateReportStore

    database = tmp_path / "ratslotse.sqlite"
    _insert_verified_accounts(database, 17)
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """CREATE TABLE civic_report_schema_migrations (
                   version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL
               );
               INSERT INTO civic_report_schema_migrations VALUES (1, '2026-08-01');
               INSERT INTO civic_report_schema_migrations VALUES (2, '2026-08-01');
               INSERT INTO civic_report_schema_migrations VALUES (3, '2026-08-01');
               CREATE TABLE civic_reports (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   reporter_id INTEGER NOT NULL,
                   draft_text TEXT NOT NULL,
                   confirmed_text TEXT,
                   category TEXT NOT NULL,
                   scope_kind TEXT NOT NULL,
                   location_label TEXT NOT NULL DEFAULT '',
                   latitude REAL,
                   longitude REAL,
                   observed_at TEXT NOT NULL,
                   status TEXT NOT NULL DEFAULT 'draft',
                   submitted_at TEXT,
                   created_at TEXT NOT NULL,
                   updated_at TEXT NOT NULL
               );
               CREATE TABLE civic_report_observations (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   report_id INTEGER NOT NULL,
                   text TEXT NOT NULL,
                   observed_at TEXT NOT NULL,
                   created_at TEXT NOT NULL,
                   FOREIGN KEY (report_id) REFERENCES civic_reports(id) ON DELETE CASCADE
               );
               INSERT INTO civic_reports (
                   id, reporter_id, draft_text, confirmed_text, category, scope_kind,
                   observed_at, status, submitted_at, created_at, updated_at
               ) VALUES (
                   41, 17, 'Alter fiktiver Entwurf', 'Alte bestätigte Beobachtung',
                   'other', 'citywide', '2026-08-01', 'submitted',
                   '2026-08-01T12:00:00+00:00', '2026-08-01T11:00:00+00:00',
                   '2026-08-01T12:00:00+00:00'
               );
               INSERT INTO civic_report_observations (
                   report_id, text, observed_at, created_at
               ) VALUES (
                   41, 'Alte bestätigte Beobachtung', '2026-08-01',
                   '2026-08-01T12:00:00+00:00'
               );"""
        )

    store = PrivateReportStore(database)
    migrated = store.get_owned_report(41, reporter_id=17)
    updated = store.append_owned_observation(
        41,
        reporter_id=17,
        text="Fiktive Beobachtung nach der Migration",
        observed_on="2026-09-01",
    )
    store.close()
    fresh_database = tmp_path / "fresh.sqlite"
    fresh_store = PrivateReportStore(fresh_database)
    fresh_store.close()

    assert migrated is not None
    assert migrated.content_revision == 1
    assert [observation.content_revision for observation in migrated.observations] == [1]
    assert updated.content_revision == 2
    assert [observation.content_revision for observation in updated.observations] == [1, 2]
    assert _private_data_schema_signature(database) == _private_data_schema_signature(
        fresh_database
    )
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_private_migration_grows_repeatably_without_replacing_public_data(tmp_path):
    from buergerportal.reports import DraftContent, PrivateReportStore
    from buergerportal.store import ProblemStore

    fresh_database = tmp_path / "fresh.sqlite"
    fresh_store = PrivateReportStore(fresh_database)
    fresh_store.close()
    fresh_schema = _private_schema_signature(fresh_database)

    grown_database = tmp_path / "grown.sqlite"
    public_store = ProblemStore(grown_database)
    _insert_public_projection(grown_database)
    public_before = public_store.list_public_problems()
    public_store.close()
    _insert_verified_accounts(grown_database, 17)
    old_store = PrivateReportStore(grown_database)
    old_draft_id = old_store.create_draft(
        reporter_id=17,
        content=DraftContent(
            text="Fiktiver Entwurf aus Schema-Version 1",
            category="public_space",
            scope_kind="citywide",
            observed_on="2026-09-01",
        ),
    )
    old_store.close()
    _downgrade_private_schema_to_version_one(grown_database)

    migrated_store = PrivateReportStore(grown_database)
    migrated_draft = migrated_store.get_owned_report(old_draft_id, reporter_id=17)
    migrated_store.close()
    schema_after_migration = _private_schema_signature(grown_database)
    reopened_store = PrivateReportStore(grown_database)
    reopened_store.close()

    assert migrated_draft is not None
    assert migrated_draft.draft_text == "Fiktiver Entwurf aus Schema-Version 1"
    assert schema_after_migration == fresh_schema
    assert _private_schema_signature(grown_database) == schema_after_migration
    with sqlite3.connect(grown_database) as connection:
        versions = connection.execute(
            "SELECT version FROM civic_report_schema_migrations ORDER BY version"
        ).fetchall()
    assert versions == [(1,), (2,), (3,), (4,), (5,), (6,), (7,)]
    public_store = ProblemStore(grown_database)
    assert public_store.list_public_problems() == public_before
    public_store.close()


def test_failed_private_migration_rolls_back_the_whole_version(tmp_path):
    from buergerportal.reports import PrivateReportStore

    database = tmp_path / "ratslotse.sqlite"
    store = PrivateReportStore(database)
    store.close()
    _downgrade_private_schema_to_version_one(database)
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """CREATE TABLE migration_conflict (id INTEGER PRIMARY KEY);
               CREATE INDEX idx_civic_report_observations_report
                   ON migration_conflict(id);"""
        )

    with pytest.raises(sqlite3.OperationalError, match="already exists"):
        PrivateReportStore(database)

    with sqlite3.connect(database) as connection:
        observation_table = connection.execute(
            """SELECT 1 FROM sqlite_master
               WHERE type = 'table' AND name = 'civic_report_observations'"""
        ).fetchone()
        versions = connection.execute(
            "SELECT version FROM civic_report_schema_migrations ORDER BY version"
        ).fetchall()
        connection.executescript(
            """DROP INDEX idx_civic_report_observations_report;
               DROP TABLE migration_conflict;"""
        )
    assert observation_table is None
    assert versions == [(1,)]

    recovered_store = PrivateReportStore(database)
    recovered_store.close()
    with sqlite3.connect(database) as connection:
        versions = connection.execute(
            "SELECT version FROM civic_report_schema_migrations ORDER BY version"
        ).fetchall()
    assert versions == [(1,), (2,), (3,), (4,), (5,), (6,), (7,)]
