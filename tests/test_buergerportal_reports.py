"""Private Meldungen: Eigentums- und Projektionsgrenzen."""
from __future__ import annotations

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
        published=True,
    )
    public.close()

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

    migrated_public = ProblemStore(database)
    assert migrated_public.get_public_problem(problem_id)["title"] == "Fehlende Absenkung"
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


def test_reporter_can_contribute_only_once_to_a_problem(tmp_path):
    database = tmp_path / "problems.sqlite"
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
    reports = ReportStore(database)

    first = reports.create_draft(
        reporter_id=101,
        text="Erste Beobachtung",
        category="accessibility",
        scope_kind="point",
        latitude=53.141,
        longitude=8.207,
        observed_at="2026-08-28T08:00:00+00:00",
    )
    second = reports.create_draft(
        reporter_id=101,
        text="Zweite Beobachtung",
        category="accessibility",
        scope_kind="point",
        latitude=53.141,
        longitude=8.207,
        observed_at="2026-08-29T08:00:00+00:00",
    )
    reports.submit_owned_report(first, reporter_id=101, confirmed_text="Erste Beobachtung")
    reports.submit_owned_report(second, reporter_id=101, confirmed_text="Zweite Beobachtung")
    reports.record_moderation_decision(
        first,
        moderator_id=900,
        outcome="assigned_existing_problem",
        reason_code="same_place_and_issue",
        note="Dem bestehenden Problem zugeordnet.",
        problem_id=problem_id,
    )

    with pytest.raises(ValueError, match="bereits eine Meldung"):
        reports.record_moderation_decision(
            second,
            moderator_id=900,
            outcome="assigned_existing_problem",
            reason_code="same_place_and_issue",
            note="Dem bestehenden Problem zugeordnet.",
            problem_id=problem_id,
        )

    assert reports.get_owned_report(first, reporter_id=101)["problem_id"] == problem_id
    reports.close()


def test_route_geography_round_trips_in_private_draft(tmp_path):
    reports = ReportStore(tmp_path / "problems.sqlite")
    geometry = {
        "type": "LineString",
        "coordinates": [[8.20, 53.14], [8.21, 53.15]],
    }

    report_id = reports.create_draft(
        reporter_id=101,
        text="Auf diesem Abschnitt fehlt ein sicherer Radweg.",
        category="mobility",
        scope_kind="route",
        location_label="Theaterwall bis Pferdemarkt",
        geometry=geometry,
        observed_at="2026-08-29T08:00:00+00:00",
    )

    assert reports.get_owned_report(report_id, reporter_id=101)["geometry"] == geometry
    reports.close()
