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


def _private_schema_signature(database) -> list[tuple[str, str, str | None]]:
    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            """SELECT type, name, sql
               FROM sqlite_master
               WHERE tbl_name IN (
                   'civic_reports', 'civic_report_observations',
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


def _drop_private_triggers(connection: sqlite3.Connection) -> None:
    triggers = connection.execute(
        """SELECT name FROM sqlite_master
           WHERE type = 'trigger' AND name LIKE 'trg_civic_report%'"""
    ).fetchall()
    for (trigger,) in triggers:
        connection.execute(f'DROP TRIGGER "{trigger}"')


def _downgrade_private_schema_to_version_two(database) -> None:
    with sqlite3.connect(database) as connection:
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


def test_drafts_require_an_existing_verified_account(tmp_path):
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
    account_store.close()
    private_store = PrivateReportStore(database)
    content = DraftContent(
        text="Fiktiver Entwurf",
        category="public_space",
        scope_kind="citywide",
        observed_on="2026-09-01",
    )

    with pytest.raises(ValueError, match="bestätigtes Konto"):
        private_store.create_draft(reporter_id=999_999, content=content)
    with pytest.raises(ValueError, match="bestätigtes Konto"):
        private_store.create_draft(reporter_id=pending_id, content=content)
    draft_id = private_store.create_draft(reporter_id=verified_id, content=content)
    account_store = Store(database)
    account_store.set_web_user_status(verified_id, "suspended")
    account_store.close()

    with pytest.raises(ValueError, match="bestätigtes Konto"):
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

    database = tmp_path / "ratslotse.sqlite"
    _insert_verified_accounts(database, 17)
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
    private_store.append_owned_observation(
        second_id,
        reporter_id=17,
        text="Nur privat: wiederholte Beobachtung",
        observed_on="2026-09-02",
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
    assert versions == [(1,), (2,), (3,), (4,)]
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
    assert versions == [(1,), (2,), (3,), (4,)]
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
    assert versions == [(1,), (2,), (3,), (4,)]
