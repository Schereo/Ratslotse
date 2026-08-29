"""Private Meldungen: Eigentums- und Projektionsgrenzen."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import sqlite3
from threading import Barrier

import pytest

from buergerportal.reports import ReportStore
from buergerportal.store import ProblemStore


def test_private_draft_is_visible_only_to_its_reporter(tmp_path):
    database = tmp_path / "problems.sqlite"
    reports = ReportStore(database)
    report_id = reports.create_draft(
        reporter_id=101,
        text="An der Querung ist die Bordsteinkante zu hoch.",
        category="accessibility",
        scope_kind="point",
        location_label="Theaterwall",
        latitude=53.141,
        longitude=8.207,
        observed_at="2026-08-28T08:00:00+00:00",
    )

    own_report = reports.get_owned_report(report_id, reporter_id=101)

    assert own_report is not None
    assert own_report["text"] == "An der Querung ist die Bordsteinkante zu hoch."
    assert reports.get_owned_report(report_id, reporter_id=202) is None
    reports.close()

    public = ProblemStore(database)
    assert public.list_public_problems() == []
    public.close()


def test_private_schema_migration_preserves_existing_public_projection(tmp_path):
    database = tmp_path / "existing.sqlite"
    public = ProblemStore(database)
    problem_id = public.create_problem(
        title="Fehlende Absenkung",
        summary="Die Querung ist nicht stufenlos nutzbar.",
        category="accessibility",
        scope_kind="point",
        location_label="Theaterwall",
        latitude=53.141,
        longitude=8.207,
    )
    public.add_public_event(
        problem_id,
        kind="published",
        title="Problem veröffentlicht",
        detail="Von Ratslotse geprüft.",
        source_kind="Ratslotse-Prüfung",
    )
    public.create_problem(
        title="Noch in Moderation",
        summary="Darf nicht veröffentlicht werden.",
        category="other",
        scope_kind="citywide",
    )
    public.close()

    legacy = sqlite3.connect(database)
    legacy.execute("DROP TRIGGER trg_civic_problems_human_publication_gate")
    legacy.execute(
        """UPDATE civic_problems
           SET unique_reporters = 1, current_observations = 1,
               total_observations = 1, published_at = ?
           WHERE id = ?""",
        ("2026-08-28T09:00:00+00:00", problem_id),
    )
    legacy.commit()
    legacy.close()

    reports = ReportStore(database)
    reports.create_draft(
        reporter_id=101,
        text="Die Bordsteinkante ist weiterhin zu hoch.",
        category="accessibility",
        scope_kind="point",
        location_label="Theaterwall",
        latitude=53.141,
        longitude=8.207,
        observed_at="2026-08-29T08:00:00+00:00",
    )
    reports.close()
    ReportStore(database).close()  # Migrationen bleiben beim erneuten Öffnen idempotent.

    migrated_public = ProblemStore(database)
    assert [problem["id"] for problem in migrated_public.list_public_problems()] == [problem_id]
    detail = migrated_public.get_public_problem(problem_id)
    assert detail["title"] == "Fehlende Absenkung"
    assert detail["summary"] == "Die Querung ist nicht stufenlos nutzbar."
    assert detail["events"][0]["title"] == "Problem veröffentlicht"
    migrated_public.close()


def test_draft_can_be_submitted_exactly_once(tmp_path):
    reports = ReportStore(tmp_path / "problems.sqlite")
    report_id = reports.create_draft(
        reporter_id=101,
        text="The curb is too high.",
        category="accessibility",
        scope_kind="point",
        location_label="Theaterwall",
        latitude=53.141,
        longitude=8.207,
        observed_at="2026-08-28T08:00:00+00:00",
    )

    submitted = reports.submit_owned_report(
        report_id,
        reporter_id=101,
        confirmed_text="Die Bordsteinkante ist zu hoch.",
    )

    assert submitted["status"] == "submitted"
    assert submitted["confirmed_text"] == "Die Bordsteinkante ist zu hoch."
    assert submitted["observations"] == [
        {
            "text": "Die Bordsteinkante ist zu hoch.",
            "observed_at": "2026-08-28T08:00:00+00:00",
            "withdrawn_at": None,
        }
    ]
    with pytest.raises(ValueError, match="bereits abgesendet"):
        reports.submit_owned_report(
            report_id,
            reporter_id=101,
            confirmed_text="Noch einmal absenden.",
        )
    reports.close()


def test_concurrent_submission_creates_only_one_first_observation(tmp_path):
    database = tmp_path / "problems.sqlite"
    reports = ReportStore(database)
    report_id = reports.create_draft(
        reporter_id=101,
        text="Die Bordsteinkante ist zu hoch.",
        category="accessibility",
        scope_kind="point",
        latitude=53.141,
        longitude=8.207,
        observed_at="2026-08-28T08:00:00+00:00",
    )
    barrier = Barrier(2)

    def submit() -> str:
        connection = ReportStore(database)
        barrier.wait()
        try:
            connection.submit_owned_report(
                report_id,
                reporter_id=101,
                confirmed_text="Die Bordsteinkante ist zu hoch.",
            )
        except ValueError:
            return "rejected"
        finally:
            connection.close()
        return "submitted"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: submit(), range(2)))

    assert sorted(results) == ["rejected", "submitted"]
    assert len(reports.get_owned_report(report_id, reporter_id=101)["observations"]) == 1
    reports.close()


def test_report_needs_current_ai_assessment_and_human_approval_before_projection(tmp_path):
    database = tmp_path / "problems.sqlite"
    reports = ReportStore(database)
    report_id = reports.create_draft(
        reporter_id=101,
        text="Die Bordsteinkante ist zu hoch.",
        category="accessibility",
        scope_kind="point",
        latitude=53.141,
        longitude=8.207,
        observed_at="2026-08-28T08:00:00+00:00",
    )
    reports.submit_owned_report(
        report_id,
        reporter_id=101,
        confirmed_text="Die Bordsteinkante ist zu hoch.",
    )
    public = ProblemStore(database)
    problem_id = public.create_problem(
        title="Fehlende Absenkung",
        summary="Die Querung ist nicht stufenlos nutzbar.",
        category="accessibility",
        scope_kind="point",
        latitude=53.141,
        longitude=8.207,
    )
    with pytest.raises(ValueError, match="KI-Vorprüfung"):
        public.publish_problem(problem_id)
    public.close()

    with pytest.raises(ValueError, match="KI-Vorprüfung"):
        reports.approve_report_for_existing_problem(
            report_id,
            moderator_id=7,
            assessment_id=999,
            problem_id=problem_id,
            reason_code="suitable",
            reporter_message="Die Meldung wird veröffentlicht.",
            private_note="Geprüft.",
        )

    unsuitable = reports.record_ai_assessment(
        report_id,
        verdict="unsuitable",
        reason_code="personal_claim",
        model_identifier="independent-review-v1",
    )
    with pytest.raises(ValueError, match="geeignet"):
        reports.approve_report_for_existing_problem(
            report_id,
            moderator_id=7,
            assessment_id=unsuitable["id"],
            problem_id=problem_id,
            reason_code="suitable",
            reporter_message="Die Meldung wird veröffentlicht.",
            private_note="Geprüft.",
        )

    stale = reports.record_ai_assessment(
        report_id,
        verdict="suitable",
        reason_code="municipal_problem",
        model_identifier="independent-review-v1",
    )
    reports.add_owned_observation(
        report_id,
        reporter_id=101,
        text="Die Bordsteinkante ist weiterhin zu hoch.",
        observed_at="2026-08-29T08:00:00+00:00",
    )
    with pytest.raises(ValueError, match="erneute KI-Vorprüfung"):
        reports.approve_report_for_existing_problem(
            report_id,
            moderator_id=7,
            assessment_id=stale["id"],
            problem_id=problem_id,
            reason_code="suitable",
            reporter_message="Die Meldung wird veröffentlicht.",
            private_note="Geprüft.",
        )

    suitable = reports.record_ai_assessment(
        report_id,
        verdict="suitable",
        reason_code="municipal_problem",
        model_identifier="independent-review-v1",
    )
    approval = reports.approve_report_for_existing_problem(
        report_id,
        moderator_id=7,
        assessment_id=suitable["id"],
        problem_id=problem_id,
        reason_code="suitable",
        reporter_message="Die Meldung wird veröffentlicht.",
        private_note="Geprüft.",
    )

    assert approval["outcome"] == "assigned_existing_problem"
    assert reports.get_owned_report(report_id, reporter_id=101)["status"] == "accepted"
    reports.close()

    public = ProblemStore(database)
    assert public.list_public_problems() == []
    public.publish_problem(problem_id)
    assert public.get_public_problem(problem_id)["independent_reports"] == 1
    public.close()


def test_human_approval_is_recorded_exactly_once_under_concurrency(tmp_path):
    database = tmp_path / "problems.sqlite"
    reports = ReportStore(database)
    report_id = reports.create_draft(
        reporter_id=101,
        text="Die Bordsteinkante ist zu hoch.",
        category="accessibility",
        scope_kind="point",
        latitude=53.141,
        longitude=8.207,
        observed_at="2026-08-28T08:00:00+00:00",
    )
    reports.submit_owned_report(
        report_id,
        reporter_id=101,
        confirmed_text="Die Bordsteinkante ist zu hoch.",
    )
    assessment = reports.record_ai_assessment(
        report_id,
        verdict="suitable",
        reason_code="municipal_problem",
        model_identifier="independent-review-v1",
    )
    public = ProblemStore(database)
    problem_id = public.create_problem(
        title="Fehlende Absenkung",
        summary="Die Querung ist nicht stufenlos nutzbar.",
        category="accessibility",
        scope_kind="point",
        latitude=53.141,
        longitude=8.207,
    )
    public.close()
    barrier = Barrier(2)

    def approve() -> str:
        connection = ReportStore(database)
        barrier.wait()
        try:
            connection.approve_report_for_existing_problem(
                report_id,
                moderator_id=7,
                assessment_id=assessment["id"],
                problem_id=problem_id,
                reason_code="suitable",
                reporter_message="Die Meldung wird veröffentlicht.",
                private_note="Geprüft.",
            )
        except ValueError:
            return "rejected"
        finally:
            connection.close()
        return "approved"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: approve(), range(2)))

    assert sorted(results) == ["approved", "rejected"]
    assert reports.get_owned_report(report_id, reporter_id=101)["status"] == "accepted"
    reports.close()


def test_owner_can_add_an_observation_without_creating_another_report(tmp_path):
    reports = ReportStore(tmp_path / "problems.sqlite")
    report_id = reports.create_draft(
        reporter_id=101,
        text="Die Bordsteinkante ist zu hoch.",
        category="accessibility",
        scope_kind="point",
        latitude=53.141,
        longitude=8.207,
        observed_at="2026-08-28T08:00:00+00:00",
    )
    reports.submit_owned_report(
        report_id,
        reporter_id=101,
        confirmed_text="Die Bordsteinkante ist zu hoch.",
    )

    with pytest.raises(ValueError, match="nicht gefunden"):
        reports.add_owned_observation(
            report_id,
            reporter_id=202,
            text="Fremde Aktualisierung",
            observed_at="2026-08-29T08:00:00+00:00",
        )
    updated = reports.add_owned_observation(
        report_id,
        reporter_id=101,
        text="Die Bordsteinkante ist weiterhin zu hoch.",
        observed_at="2026-08-29T08:00:00+00:00",
    )

    assert [item["text"] for item in updated["observations"]] == [
        "Die Bordsteinkante ist zu hoch.",
        "Die Bordsteinkante ist weiterhin zu hoch.",
    ]
    assert updated["id"] == report_id
    reports.close()
