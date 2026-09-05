"""Human-confirmed assignment at the private/public projection seam."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest


def _approved_report(
    database,
    *,
    reporter_email: str,
    reviewer_email: str,
    text: str,
    scope_kind: str = "citywide",
    observed_on: str = "2026-09-01",
):
    from kern.store import Store

    accounts = Store(database)
    reporter_id = accounts.create_web_user(
        reporter_email,
        "x",
        role="user",
        status="active",
        email_verified=True,
    )
    reviewer_id = accounts.create_web_user(
        reviewer_email,
        "x",
        role="moderator",
        status="active",
        email_verified=True,
    )
    accounts.close()
    submitted = _approve_for_accounts(
        database,
        reporter_id=reporter_id,
        reviewer_id=reviewer_id,
        text=text,
        scope_kind=scope_kind,
        observed_on=observed_on,
    )
    return reporter_id, reviewer_id, submitted


def _approve_for_accounts(
    database,
    *,
    reporter_id: int,
    reviewer_id: int,
    text: str,
    scope_kind: str = "citywide",
    observed_on: str = "2026-09-01",
):
    from buergerportal.reports import DraftContent, PrivateReportStore

    reports = PrivateReportStore(database)
    report_id = reports.create_draft(
        reporter_id=reporter_id,
        content=DraftContent(
            text="Ausdrücklich fiktiver Projektionsentwurf.",
            category="public_space",
            scope_kind=scope_kind,
            observed_on=observed_on,
            location_label="" if scope_kind == "citywide" else "Fiktiver Testpunkt",
            latitude=None if scope_kind == "citywide" else 53.14,
            longitude=None if scope_kind == "citywide" else 8.21,
        ),
    )
    submitted = reports.submit_owned_draft(
        report_id,
        reporter_id=reporter_id,
        confirmed_text=text,
        expected_revision=0,
    )
    reports.decide_report(
        report_id,
        reviewer_id=reviewer_id,
        expected_revision=submitted.content_revision,
        outcome="approved",
        rejection_explanation=None,
    )
    reports.close()
    return submitted


def test_human_confirmation_creates_one_minimized_citywide_projection(tmp_path):
    from buergerportal.projections import NewCitywideProjection, ProjectionStore
    from buergerportal.store import ProblemStore

    database = tmp_path / "ratslotse.sqlite"
    owner_id, reviewer_id, approved = _approved_report(
        database,
        reporter_email="fiktive-projektionsmeldung@test.de",
        reviewer_email="fiktive-projektionspruefung@test.de",
        text="Fiktive Beobachtung zu fehlenden Sitzmöglichkeiten im Stadtgebiet.",
    )
    public_before = ProblemStore(database)
    assert public_before.list_public_problems() == []
    public_before.close()
    projections = ProjectionStore(database)

    candidate = projections.get_candidate(
        approved.id,
        reviewer_id=reviewer_id,
    )
    assignment = projections.confirm_assignment(
        approved.id,
        reviewer_id=reviewer_id,
        expected_revision=approved.content_revision,
        target=NewCitywideProjection(
            title="Mehr fiktive Sitzmöglichkeiten",
            summary="Eine ausdrücklich fiktive Projektion für den Abnahmetest.",
        ),
    )

    assert candidate is not None
    assert candidate.report_id == approved.id
    assert candidate.content_revision == approved.content_revision
    assert candidate.category == "public_space"
    assert candidate.scope_kind == "citywide"
    assert [item.text for item in candidate.observations] == [
        "Fiktive Beobachtung zu fehlenden Sitzmöglichkeiten im Stadtgebiet."
    ]
    assert assignment.report_id == approved.id
    assert assignment.content_revision == approved.content_revision
    assert projections.get_candidate(approved.id, reviewer_id=reviewer_id) is None
    assert projections.list_owner_assignments(
        reporter_id=assignment.report_id + 10_000,
        report_ids=[approved.id],
    ) == {}
    owner_assignments = projections.list_owner_assignments(
        reporter_id=owner_id,
        report_ids=[approved.id],
    )
    assert owner_assignments[approved.id].problem_id == assignment.problem_id
    assert owner_assignments[approved.id].title == "Mehr fiktive Sitzmöglichkeiten"
    projections.close()

    public_after = ProblemStore(database)
    assert public_after.list_public_problems() == [
        {
            "id": assignment.problem_id,
            "title": "Mehr fiktive Sitzmöglichkeiten",
            "summary": "Eine ausdrücklich fiktive Projektion für den Abnahmetest.",
            "category": "public_space",
            "scope_kind": "citywide",
            "location_label": "",
            "latitude": None,
            "longitude": None,
            "geometry": None,
            "status": "new",
            "independent_reports": 1,
            "frequency": "once",
            "fictional": False,
        }
    ]
    public_after.close()


def test_owner_link_disappears_when_public_target_is_resolved(tmp_path):
    import sqlite3

    from buergerportal.projections import NewCitywideProjection, ProjectionStore
    from buergerportal.store import ProblemStore

    database = tmp_path / "ratslotse.sqlite"
    owner_id, reviewer_id, approved = _approved_report(
        database,
        reporter_email="fiktive-geloeste-projektion@test.de",
        reviewer_email="fiktive-geloeste-pruefung@test.de",
        text="Fiktive Beobachtung für eine später gelöste Projektion.",
    )
    projections = ProjectionStore(database)
    assignment = projections.confirm_assignment(
        approved.id,
        reviewer_id=reviewer_id,
        expected_revision=1,
        target=NewCitywideProjection(
            title="Fiktive später gelöste Projektion",
            summary="Nach der Lösung darf kein Owner-Link auf ein unsichtbares Ziel zeigen.",
        ),
    )
    connection = sqlite3.connect(database)
    connection.execute(
        "UPDATE civic_problems SET status = 'apparently_resolved' WHERE id = ?",
        (assignment.problem_id,),
    )
    connection.commit()
    connection.close()

    assert projections.list_owner_assignments(
        reporter_id=owner_id,
        report_ids=[approved.id],
    ) == {}
    public = ProblemStore(database)
    assert public.get_public_problem(assignment.problem_id) is None
    public.close()
    projections.close()


def test_projection_candidates_are_oldest_first_bounded_and_minimized(tmp_path):
    from dataclasses import asdict

    from buergerportal.projections import ProjectionStore

    database = tmp_path / "ratslotse.sqlite"
    _, reviewer_id, first = _approved_report(
        database,
        reporter_email="fiktive-erste-projektion@test.de",
        reviewer_email="fiktive-erste-pruefung@test.de",
        text="Fiktive erste freigegebene Beobachtung.",
    )
    _, _, second = _approved_report(
        database,
        reporter_email="fiktive-zweite-projektion@test.de",
        reviewer_email="fiktive-zweite-pruefung@test.de",
        text="Fiktive zweite freigegebene Beobachtung.",
    )
    projections = ProjectionStore(database)

    page = projections.list_candidates(
        reviewer_id=reviewer_id,
        limit=1,
        offset=0,
    )
    next_page = projections.list_candidates(
        reviewer_id=reviewer_id,
        limit=1,
        offset=1,
    )

    assert page.total == 2
    assert [report.report_id for report in page.reports] == [first.id]
    assert [report.report_id for report in next_page.reports] == [second.id]
    assert asdict(page.reports[0]) == {
        "report_id": first.id,
        "content_revision": 1,
        "text_preview": "Fiktive erste freigegebene Beobachtung.",
        "category": "public_space",
        "scope_kind": "citywide",
        "observed_on": "2026-09-01",
    }
    projections.close()


def test_existing_projection_counts_distinct_owners_and_exact_retry(tmp_path):
    from dataclasses import asdict

    from buergerportal.projections import (
        ExistingProjection,
        NewCitywideProjection,
        ProjectionStore,
    )
    from buergerportal.store import ProblemStore
    from kern.store import Store

    database = tmp_path / "ratslotse.sqlite"
    first_owner, reviewer_id, first = _approved_report(
        database,
        reporter_email="fiktive-zaehlung-eins@test.de",
        reviewer_email="fiktive-zaehlungspruefung@test.de",
        text="Fiktive erste Beobachtung für dieselbe Projektion.",
    )
    projections = ProjectionStore(database)
    initial = projections.confirm_assignment(
        first.id,
        reviewer_id=reviewer_id,
        expected_revision=1,
        target=NewCitywideProjection(
            title="Fiktive gemeinsame Projektion",
            summary="Öffentliche fiktive Zusammenfassung ohne private Rohdaten.",
        ),
    )
    second = _approve_for_accounts(
        database,
        reporter_id=first_owner,
        reviewer_id=reviewer_id,
        text="Fiktive zweite Beobachtung derselben Person.",
    )
    accounts = Store(database)
    other_owner = accounts.create_web_user(
        "fiktive-zaehlung-zwei@test.de",
        "x",
        role="user",
        status="active",
        email_verified=True,
    )
    accounts.close()
    third = _approve_for_accounts(
        database,
        reporter_id=other_owner,
        reviewer_id=reviewer_id,
        text="Fiktive Beobachtung einer anderen Person.",
    )

    targets = projections.list_targets(
        reviewer_id=reviewer_id,
        query="gemeinsame",
        limit=10,
    )
    second_assignment = projections.confirm_assignment(
        second.id,
        reviewer_id=reviewer_id,
        expected_revision=1,
        target=ExistingProjection(initial.problem_id),
    )
    retry = projections.confirm_assignment(
        second.id,
        reviewer_id=reviewer_id,
        expected_revision=1,
        target=ExistingProjection(initial.problem_id),
    )
    projections.confirm_assignment(
        third.id,
        reviewer_id=reviewer_id,
        expected_revision=1,
        target=ExistingProjection(initial.problem_id),
    )
    projections.close()

    assert [asdict(target) for target in targets] == [{
        "problem_id": initial.problem_id,
        "title": "Fiktive gemeinsame Projektion",
        "summary": "Öffentliche fiktive Zusammenfassung ohne private Rohdaten.",
        "category": "public_space",
        "scope_kind": "citywide",
        "status": "new",
        "independent_reports": 1,
    }]
    assert retry == second_assignment
    public = ProblemStore(database)
    assert public.get_public_problem(initial.problem_id)["independent_reports"] == 2
    public.close()


def test_projection_fails_closed_when_owner_changes_and_erasure_removes_contribution(tmp_path):
    from buergerportal.projections import NewCitywideProjection, ProjectionStore
    from buergerportal.store import ProblemStore
    from kern.store import Store

    database = tmp_path / "ratslotse.sqlite"
    owner_id, reviewer_id, approved = _approved_report(
        database,
        reporter_email="fiktive-loeschprojektion@test.de",
        reviewer_email="fiktive-loeschpruefung@test.de",
        text="Fiktive Beobachtung für die Löschgrenze.",
    )
    projections = ProjectionStore(database)
    assignment = projections.confirm_assignment(
        approved.id,
        reviewer_id=reviewer_id,
        expected_revision=1,
        target=NewCitywideProjection(
            title="Fiktive Projektion an der Löschgrenze",
            summary="Fiktive öffentliche Zusammenfassung für den Erasure-Test.",
        ),
    )
    accounts = Store(database)

    accounts.set_web_user_role(owner_id, "moderator")
    hidden = ProblemStore(database)
    assert hidden.get_public_problem(assignment.problem_id) is None
    hidden.close()
    accounts.set_web_user_role(owner_id, "user")
    restored = ProblemStore(database)
    assert restored.get_public_problem(assignment.problem_id)["independent_reports"] == 1
    restored.close()

    accounts.set_web_user_status(owner_id, "blocked")
    status_hidden = ProblemStore(database)
    assert status_hidden.get_public_problem(assignment.problem_id) is None
    status_hidden.close()
    accounts.set_web_user_status(owner_id, "active")
    accounts.set_email_verified(owner_id, False)
    verification_hidden = ProblemStore(database)
    assert verification_hidden.get_public_problem(assignment.problem_id) is None
    verification_hidden.close()
    accounts.set_email_verified(owner_id, True)

    accounts.delete_web_user(owner_id)
    assert accounts.get_web_user_by_id(owner_id) is None
    erased = ProblemStore(database)
    assert erased.get_public_problem(assignment.problem_id) is None
    erased.close()
    accounts.close()
    projections.close()


def test_reporter_erasure_recomputes_dates_from_remaining_evidence(tmp_path):
    import sqlite3

    from buergerportal.projections import ExistingProjection, NewCitywideProjection, ProjectionStore
    from buergerportal.store import ProblemStore
    from kern.store import Store

    database = tmp_path / "ratslotse.sqlite"
    first_owner, reviewer_id, first = _approved_report(
        database,
        reporter_email="fiktive-fruehe-datumsprojektion@test.de",
        reviewer_email="fiktive-datumspruefung@test.de",
        text="Fiktive frühe Beobachtung für die Datumsspanne.",
        observed_on="2026-09-01",
    )
    accounts = Store(database)
    second_owner = accounts.create_web_user(
        "fiktive-spaete-datumsprojektion@test.de",
        "x",
        role="user",
        status="active",
        email_verified=True,
    )
    second = _approve_for_accounts(
        database,
        reporter_id=second_owner,
        reviewer_id=reviewer_id,
        text="Fiktive spätere Beobachtung für die Datumsspanne.",
        observed_on="2026-09-03",
    )
    projections = ProjectionStore(database)
    created = projections.confirm_assignment(
        first.id,
        reviewer_id=reviewer_id,
        expected_revision=1,
        target=NewCitywideProjection(
            title="Fiktive Projektion mit Datumsspanne",
            summary="Die öffentliche Datumsspanne folgt nur verbleibender Evidenz.",
        ),
    )
    projections.confirm_assignment(
        second.id,
        reviewer_id=reviewer_id,
        expected_revision=1,
        target=ExistingProjection(created.problem_id),
    )

    accounts.delete_web_user(first_owner)

    public = ProblemStore(database)
    assert public.get_public_problem(created.problem_id)["independent_reports"] == 1
    public.close()
    connection = sqlite3.connect(database)
    assert connection.execute(
        "SELECT first_observed_at, last_observed_at FROM civic_problems WHERE id = ?",
        (created.problem_id,),
    ).fetchone() == ("2026-09-03", "2026-09-03")
    connection.close()
    projections.close()
    accounts.close()


def test_later_report_revision_hides_stale_projection_without_rewriting_assignment(tmp_path):
    from buergerportal.projections import NewCitywideProjection, ProjectionStore
    from buergerportal.reports import PrivateReportStore
    from buergerportal.store import ProblemStore

    database = tmp_path / "ratslotse.sqlite"
    owner_id, reviewer_id, approved = _approved_report(
        database,
        reporter_email="fiktive-revisionsprojektion@test.de",
        reviewer_email="fiktive-revisionspruefung@test.de",
        text="Fiktive erste Beobachtung für die Revisionsgrenze.",
    )
    projections = ProjectionStore(database)
    assignment = projections.confirm_assignment(
        approved.id,
        reviewer_id=reviewer_id,
        expected_revision=1,
        target=NewCitywideProjection(
            title="Fiktive revisionsgebundene Projektion",
            summary="Eine spätere private Revision macht diese Evidenz unbrauchbar.",
        ),
    )
    reports = PrivateReportStore(database)

    updated = reports.append_owned_observation(
        approved.id,
        reporter_id=owner_id,
        text="Fiktive neuere Beobachtung, die eine neue Prüfung braucht.",
        observed_on="2026-09-03",
    )

    assert updated.content_revision == 2
    assert projections.list_candidates(reviewer_id=reviewer_id, limit=20, offset=0).total == 0
    public = ProblemStore(database)
    assert public.get_public_problem(assignment.problem_id) is None
    public.close()
    exact_retry = projections.confirm_assignment(
        approved.id,
        reviewer_id=reviewer_id,
        expected_revision=1,
        target=NewCitywideProjection(
            title="Fiktive revisionsgebundene Projektion",
            summary="Eine spätere private Revision macht diese Evidenz unbrauchbar.",
        ),
    )
    assert exact_retry == assignment
    reports.close()
    projections.close()


def test_reviewer_deletion_preserves_assignment_actor_without_identity(tmp_path):
    from buergerportal.projections import NewCitywideProjection, ProjectionStore
    from kern.store import Store

    database = tmp_path / "ratslotse.sqlite"
    _, reviewer_id, approved = _approved_report(
        database,
        reporter_email="fiktive-auditprojektion@test.de",
        reviewer_email="fiktive-geloeschte-pruefung@test.de",
        text="Fiktive Beobachtung für unveränderliche Audit-Evidenz.",
    )
    accounts = Store(database)
    admin_id = accounts.create_web_user(
        "fiktive-projektionsaufsicht@test.de",
        "x",
        role="admin",
        status="active",
        email_verified=False,
    )
    projections = ProjectionStore(database)
    target = NewCitywideProjection(
        title="Fiktive Audit-Projektion",
        summary="Fiktive öffentliche Zusammenfassung für erhaltene Evidenz.",
    )
    assignment = projections.confirm_assignment(
        approved.id,
        reviewer_id=reviewer_id,
        expected_revision=1,
        target=target,
    )

    accounts.delete_web_user(reviewer_id)
    exact_retry = projections.confirm_assignment(
        approved.id,
        reviewer_id=admin_id,
        expected_revision=1,
        target=target,
    )

    assert exact_retry == assignment
    assert exact_retry.reviewer_id == reviewer_id
    assert accounts.get_web_user_by_id(reviewer_id) is None
    projections.close()
    accounts.close()


def test_concurrent_projection_confirmation_is_exactly_once(tmp_path):
    from buergerportal.projections import NewCitywideProjection, ProjectionStore
    from buergerportal.store import ProblemStore

    database = tmp_path / "ratslotse.sqlite"
    _, reviewer_id, approved = _approved_report(
        database,
        reporter_email="fiktive-parallelprojektion@test.de",
        reviewer_email="fiktive-parallelpruefung@test.de",
        text="Fiktive Beobachtung für zwei gleichzeitige Bestätigungen.",
    )
    target = NewCitywideProjection(
        title="Fiktive parallele Projektion",
        summary="Eine fiktive Projektion darf trotz Parallelität nur einmal entstehen.",
    )

    def confirm():
        store = ProjectionStore(database)
        try:
            return store.confirm_assignment(
                approved.id,
                reviewer_id=reviewer_id,
                expected_revision=1,
                target=target,
            )
        finally:
            store.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        assignments = list(executor.map(lambda _: confirm(), range(2)))

    assert assignments[0] == assignments[1]
    public = ProblemStore(database)
    assert len(public.list_public_problems()) == 1
    public.close()


def test_conflicting_projection_retry_cannot_replace_public_copy(tmp_path):
    from buergerportal.projections import (
        NewCitywideProjection,
        ProjectionConflict,
        ProjectionStore,
    )
    from buergerportal.store import ProblemStore

    database = tmp_path / "ratslotse.sqlite"
    _, reviewer_id, approved = _approved_report(
        database,
        reporter_email="fiktive-konfliktprojektion@test.de",
        reviewer_email="fiktive-konfliktpruefung@test.de",
        text="Fiktive Beobachtung für einen Konflikttest.",
    )
    projections = ProjectionStore(database)
    original = NewCitywideProjection(
        title="Fiktiver unveränderlicher Titel",
        summary="Fiktive zuerst bestätigte öffentliche Zusammenfassung.",
    )
    projections.confirm_assignment(
        approved.id,
        reviewer_id=reviewer_id,
        expected_revision=1,
        target=original,
    )

    with pytest.raises(ProjectionConflict, match="andere Zuordnung"):
        projections.confirm_assignment(
            approved.id,
            reviewer_id=reviewer_id,
            expected_revision=1,
            target=NewCitywideProjection(
                title="Abweichender fiktiver Titel",
                summary="Eine abweichende Zusammenfassung darf nichts ersetzen.",
            ),
        )

    public = ProblemStore(database)
    assert public.list_public_problems()[0]["title"] == original.title
    public.close()
    projections.close()


def test_new_projection_rejects_non_citywide_private_reports(tmp_path):
    from buergerportal.projections import (
        NewCitywideProjection,
        ProjectionConflict,
        ProjectionStore,
    )
    from buergerportal.store import ProblemStore

    database = tmp_path / "ratslotse.sqlite"
    _, reviewer_id, approved = _approved_report(
        database,
        reporter_email="fiktive-punktprojektion@test.de",
        reviewer_email="fiktive-punktpruefung@test.de",
        text="Fiktive punktbezogene Beobachtung für die Projektionsgrenze.",
        scope_kind="point",
    )
    projections = ProjectionStore(database)

    with pytest.raises(ProjectionConflict, match="nur stadtweit"):
        projections.confirm_assignment(
            approved.id,
            reviewer_id=reviewer_id,
            expected_revision=1,
            target=NewCitywideProjection(
                title="Unzulässige fiktive Punktprojektion",
                summary="Diese Projektion darf nicht öffentlich entstehen.",
            ),
        )

    public = ProblemStore(database)
    assert public.list_public_problems() == []
    public.close()
    projections.close()


def test_projection_migration_matches_fresh_schema_and_is_repeatable(tmp_path):
    import sqlite3

    from buergerportal.projections import ExistingProjection, ProjectionStore
    from buergerportal.store import ProblemStore
    from kern.store import Store

    def projection_columns(path):
        connection = sqlite3.connect(path)
        result = {
            table: connection.execute(f"PRAGMA table_info({table})").fetchall()
            for table in (
                "civic_projection_schema_migrations",
                "civic_problem_projection_baselines",
                "civic_report_problem_assignments",
            )
        }
        connection.close()
        return result

    upgraded_database = tmp_path / "upgraded.sqlite"
    accounts = Store(upgraded_database)
    accounts.close()
    public = ProblemStore(upgraded_database)
    public.close()
    connection = sqlite3.connect(upgraded_database)
    inserted = connection.execute(
        """INSERT INTO civic_problems (
               title, summary, category, tags_json, scope_kind, location_label,
               latitude, longitude, geometry_json, status, independent_reports,
               first_observed_at, last_observed_at, published_at, updated_at
           ) VALUES (?, ?, 'public_space', '[]', 'citywide', '', NULL, NULL, NULL,
                     'new', 3, ?, ?, ?, ?)""",
        (
            "Bestehende fiktive öffentliche Projektion",
            "Diese öffentliche Projektion muss die neue Migration unverändert überstehen.",
            "2026-08-01T00:00:00+00:00",
            "2026-08-02T00:00:00+00:00",
            "2026-08-03T00:00:00+00:00",
            "2026-08-03T00:00:00+00:00",
        ),
    )
    existing_problem_id = int(inserted.lastrowid)
    connection.commit()
    connection.close()
    before_store = ProblemStore(upgraded_database)
    before = before_store.list_public_problems()
    before_store.close()

    migrated = ProjectionStore(upgraded_database)
    migrated.close()
    migrated_again = ProjectionStore(upgraded_database)
    migrated_again.close()
    fresh_database = tmp_path / "fresh.sqlite"
    fresh = ProjectionStore(fresh_database)
    fresh.close()

    assert projection_columns(upgraded_database) == projection_columns(fresh_database)
    after_store = ProblemStore(upgraded_database)
    assert after_store.list_public_problems() == before
    after_store.close()
    connection = sqlite3.connect(upgraded_database)
    assert connection.execute(
        "SELECT version FROM civic_projection_schema_migrations ORDER BY version"
    ).fetchall() == [(1,)]
    connection.close()

    _, reviewer_id, approved = _approved_report(
        upgraded_database,
        reporter_email="fiktive-migrationsmeldung@test.de",
        reviewer_email="fiktive-migrationspruefung@test.de",
        text="Fiktive Beobachtung nach einer Bestandsmigration.",
    )
    projections = ProjectionStore(upgraded_database)
    projections.confirm_assignment(
        approved.id,
        reviewer_id=reviewer_id,
        expected_revision=1,
        target=ExistingProjection(existing_problem_id),
    )
    projections.close()
    exercised = ProblemStore(upgraded_database)
    assert exercised.get_public_problem(existing_problem_id)["independent_reports"] == 4
    exercised.close()


def test_projection_database_evidence_is_immutable(tmp_path):
    import sqlite3

    from buergerportal.projections import NewCitywideProjection, ProjectionStore

    database = tmp_path / "ratslotse.sqlite"
    owner_id, reviewer_id, approved = _approved_report(
        database,
        reporter_email="fiktive-db-evidenz@test.de",
        reviewer_email="fiktive-db-pruefung@test.de",
        text="Fiktive Beobachtung für unveränderliche Projektionsevidenz.",
    )
    projections = ProjectionStore(database)
    assignment = projections.confirm_assignment(
        approved.id,
        reviewer_id=reviewer_id,
        expected_revision=1,
        target=NewCitywideProjection(
            title="Fiktive unveränderliche Projektion",
            summary="Öffentliche fiktive Zusammenfassung für Datenbankwächter.",
        ),
    )
    second = _approve_for_accounts(
        database,
        reporter_id=owner_id,
        reviewer_id=reviewer_id,
        text="Fiktive zweite Beobachtung für Datenbankwächter.",
        scope_kind="point",
    )
    projections.close()
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA foreign_keys=ON")

    with pytest.raises(sqlite3.IntegrityError, match="current approval, reviewer, and target"):
        connection.execute(
            """INSERT INTO civic_report_problem_assignments (
                   report_id, content_revision, problem_id, reviewer_id,
                   creates_problem, assigned_at
               ) VALUES (?, 1, ?, ?, 0, '2026-09-05T00:00:00+00:00')""",
            (second.id, assignment.problem_id, owner_id),
        )

    fake = connection.execute(
        """INSERT INTO civic_problems (
               title, summary, category, tags_json, scope_kind, location_label,
               latitude, longitude, geometry_json, status, independent_reports,
               first_observed_at, last_observed_at, published_at, updated_at
           ) VALUES ('Fiktives falsches Ziel', 'Fiktive falsche Zusammenfassung',
                     'public_space', '[]', 'citywide', '', NULL, NULL, NULL, 'new',
                     0, '2026-09-01', '2026-09-01', NULL, '2026-09-05')"""
    )
    fake_problem_id = int(fake.lastrowid)
    connection.execute(
        """INSERT INTO civic_problem_projection_baselines (
               problem_id, baseline_independent_reports,
               baseline_first_observed_at, baseline_last_observed_at
           ) VALUES (?, 0, NULL, NULL)""",
        (fake_problem_id,),
    )
    connection.commit()
    with pytest.raises(sqlite3.IntegrityError, match="current approval, reviewer, and target"):
        connection.execute(
            """INSERT INTO civic_report_problem_assignments (
                   report_id, content_revision, problem_id, reviewer_id,
                   creates_problem, assigned_at
               ) VALUES (?, 1, ?, ?, 1, '2026-09-05T00:00:00+00:00')""",
            (second.id, fake_problem_id, reviewer_id),
        )

    with pytest.raises(sqlite3.IntegrityError, match="assignments are immutable"):
        connection.execute(
            "UPDATE civic_report_problem_assignments SET reviewer_id = reviewer_id + 1"
        )
    with pytest.raises(sqlite3.IntegrityError, match="baselines are immutable"):
        connection.execute(
            "UPDATE civic_problem_projection_baselines SET baseline_independent_reports = 9 WHERE problem_id = ?",
            (assignment.problem_id,),
        )

    connection.close()


def test_projection_migration_rejects_newer_schema_versions(tmp_path):
    import sqlite3

    from buergerportal.projections import ProjectionStore

    database = tmp_path / "ratslotse.sqlite"
    initialized = ProjectionStore(database)
    initialized.close()
    connection = sqlite3.connect(database)
    connection.execute("INSERT INTO civic_projection_schema_migrations(version) VALUES (99)")
    connection.commit()
    connection.close()

    with pytest.raises(RuntimeError, match="newer than supported"):
        ProjectionStore(database)
