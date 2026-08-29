"""Problemtracker: öffentliche Projektion und API-Grenze."""
from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from buergerportal.reports import ReportStore
from buergerportal.store import ProblemStore
from web.backend.app.deps import get_problem_store
from web.backend.app.routers.problems import router


def _approve_and_publish(
    store: ProblemStore,
    database,
    problem_id: int,
    *,
    independent_reports: int = 1,
) -> None:
    reports = ReportStore(database)
    for index in range(independent_reports):
        owner_id = 10_000 + problem_id * 10 + index
        report_id = reports.create_draft(
            reporter_id=owner_id,
            text="Die Beobachtung wurde unabhängig gemeldet.",
            category="other",
            category_detail="Das kommunale Problem betrifft das gesamte Stadtgebiet.",
            scope_kind="citywide",
            observed_at=f"2026-08-{20 + index:02d}T08:00:00+00:00",
        )
        reports.submit_owned_report(
            report_id,
            reporter_id=owner_id,
            confirmed_text="Die Beobachtung wurde unabhängig gemeldet.",
        )
        assessment = reports.record_ai_assessment(
            report_id,
            verdict="suitable",
            reason_code="municipal_problem",
            model_identifier="test-review-v1",
        )
        approve = (
            reports.approve_report_for_new_problem
            if index == 0
            else reports.approve_report_for_existing_problem
        )
        approve(
            report_id,
            moderator_id=7,
            assessment_id=assessment["id"],
            problem_id=problem_id,
            reason_code="suitable",
            reporter_message="Die Meldung wurde freigegeben.",
            private_note="Testfreigabe.",
        )
    reports.close()
    store.publish_problem(problem_id)


def test_problem_store_exposes_only_published_problems(tmp_path):
    database = tmp_path / "problems.sqlite"
    store = ProblemStore(database)
    visible = store.create_problem(
        title="Dunkler Weg",
        summary="Der Weg ist abends nicht durchgängig beleuchtet.",
        category="public_space",
        scope_kind="point",
        location_label="Innenstadt",
        latitude=53.14,
        longitude=8.21,
    )
    store.create_problem(
        title="Noch in Moderation",
        summary="Dieser Rohstand darf nicht öffentlich werden.",
        category="other",
        scope_kind="citywide",
    )
    store.add_public_event(
        visible,
        kind="published",
        title="Problem veröffentlicht",
        detail="Von Ratslotse geprüft.",
        source_kind="Ratslotse-Prüfung",
    )
    _approve_and_publish(store, database, visible, independent_reports=3)

    listed = store.list_public_problems()
    assert [problem["id"] for problem in listed] == [visible]
    assert listed[0]["frequency"] == "several"
    assert "events" not in listed[0]
    assert "unique_reporters" not in listed[0]
    assert "current_observations" not in listed[0]
    assert store.get_public_problem(visible)["events"][0]["title"] == "Problem veröffentlicht"
    assert store.get_public_problem(visible)["independent_reports"] == 3
    store.close()


def test_public_api_hides_unpublished_problem_and_exposes_detail(tmp_path):
    database = tmp_path / "problems.sqlite"
    store = ProblemStore(database)
    visible = store.create_problem(
        title="Überfüllte Fahrradständer",
        summary="Zu Pendelzeiten reichen die Plätze nicht aus.",
        category="mobility",
        scope_kind="facility",
        location_label="Bahnhof",
        latitude=53.143,
        longitude=8.223,
    )
    store.add_public_event(
        visible,
        kind="response",
        title="Öffentliche Rückmeldung",
        source_kind="Stadtverwaltung",
        source_url="https://www.oldenburg.de/quelle",
    )
    _approve_and_publish(store, database, visible)
    hidden = store.create_problem(
        title="Private Moderationsfassung",
        summary="Nicht freigegeben.",
        category="other",
        scope_kind="citywide",
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_problem_store] = lambda: store
    client = TestClient(app)

    response = client.get("/api/probleme")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["problems"][0]["id"] == visible
    assert "unique_reporters" not in response.json()["problems"][0]
    detail = client.get(f"/api/probleme/{visible}")
    assert detail.status_code == 200
    assert detail.json()["independent_reports"] == 1
    assert "unique_reporters" not in detail.json()
    assert "current_observations" not in detail.json()
    assert "total_observations" not in detail.json()
    assert detail.json()["events"][0]["source_kind"] == "Stadtverwaltung"
    assert detail.json()["events"][0]["source_url"] == "https://www.oldenburg.de/quelle"
    assert client.get(f"/api/probleme/{hidden}").status_code == 404
    assert client.get("/api/probleme?status=amtlich_in_bearbeitung").status_code == 422
    assert client.get("/api/probleme?category=personenkritik").status_code == 422
    store.close()


def test_external_public_event_requires_role_and_http_source(tmp_path):
    store = ProblemStore(tmp_path / "problems.sqlite")
    problem_id = store.create_problem(
        title="Fehlende Absenkung",
        summary="Die Querung ist nicht stufenlos nutzbar.",
        category="accessibility",
        scope_kind="point",
        latitude=53.141,
        longitude=8.207,
    )

    with pytest.raises(ValueError, match="Rollenlabel"):
        store.add_public_event(problem_id, kind="reply", title="Rückmeldung", source_kind="Behörde")
    with pytest.raises(ValueError, match="überprüfbare Quelle"):
        store.add_public_event(
            problem_id,
            kind="reply",
            title="Rückmeldung",
            source_kind="Stadtverwaltung",
        )
    for invalid_url in ("javascript:alert(1)", "https:// x", "https://%zz"):
        with pytest.raises(ValueError, match="HTTP-Adresse"):
            store.add_public_event(
                problem_id,
                kind="check",
                title="Prüfung",
                source_kind="Ratslotse-Prüfung",
                source_url=invalid_url,
            )
    with pytest.raises(sqlite3.IntegrityError, match="invalid public event source"):
        store._conn.execute(
            """INSERT INTO civic_problem_events (
                   problem_id, kind, title, source_kind, source_url,
                   event_at, published_at
               ) VALUES (?, 'reply', 'Direkter Eintrag', 'Stadtverwaltung',
                         'http:///kein-host', ?, ?)""",
            (problem_id, "2026-08-29T08:00:00+00:00", "2026-08-29T08:00:00+00:00"),
        )
    store._conn.rollback()
    event_id = store.add_public_event(
        problem_id,
        kind="reply",
        title="Rückmeldung",
        source_kind="Stadtverwaltung",
        source_url="https://www.oldenburg.de/quelle",
    )

    assert event_id > 0
    store.close()


def test_migration_hides_legacy_public_event_without_source(tmp_path):
    database = tmp_path / "problems.sqlite"
    store = ProblemStore(database)
    problem_id = store.create_problem(
        title="Fehlende Absenkung",
        summary="Die Querung ist nicht stufenlos nutzbar.",
        category="accessibility",
        scope_kind="point",
        latitude=53.141,
        longitude=8.207,
    )
    _approve_and_publish(store, database, problem_id)
    store.close()

    connection = sqlite3.connect(database)
    connection.execute("DROP TRIGGER trg_civic_problem_events_public_source_insert")
    connection.execute("DROP TRIGGER trg_civic_problem_events_public_source_update")
    connection.execute(
        """INSERT INTO civic_problem_events (
               problem_id, kind, title, event_at, published_at
           ) VALUES (?, 'legacy', 'Altes Ereignis', ?, ?)""",
        (problem_id, "2026-08-29T08:00:00+00:00", "2026-08-29T08:00:00+00:00"),
    )
    connection.commit()
    connection.close()

    migrated = ProblemStore(database)
    assert migrated.get_public_problem(problem_id)["events"] == []
    migrated.close()


def test_problem_store_rejects_uncontrolled_category(tmp_path):
    store = ProblemStore(tmp_path / "problems.sqlite")
    try:
        store.create_problem(
            title="Ungeeignet",
            summary="Personenbezogene Kategorie.",
            category="personenkritik",
            scope_kind="citywide",
        )
    except ValueError as error:
        assert "Problemkategorie" in str(error)
    else:
        raise AssertionError("Unkontrollierte Kategorie wurde gespeichert")
    finally:
        store.close()


def test_published_problem_requires_ai_review_and_human_approval(tmp_path):
    database = tmp_path / "problems.sqlite"
    store = ProblemStore(database)
    ReportStore(database).close()
    problem_id = store.create_problem(
        title="Ohne Meldung",
        summary="Darf nicht öffentlich werden.",
        category="other",
        scope_kind="citywide",
    )

    with pytest.raises(sqlite3.IntegrityError, match="AI assessment and human approval"):
        store._conn.execute(
            "UPDATE civic_problems SET published_at = ? WHERE id = ?",
            ("2026-08-29T10:00:00+00:00", problem_id),
        )
    store._conn.rollback()
    with pytest.raises(ValueError, match="KI-Vorprüfung"):
        store.publish_problem(problem_id)
    assert store.get_public_problem(problem_id) is None
    store.close()


def test_route_and_area_require_matching_geojson_and_are_public(tmp_path):
    database = tmp_path / "problems.sqlite"
    store = ProblemStore(database)
    route_geometry = {
        "type": "LineString",
        "coordinates": [[8.198, 53.142], [8.205, 53.143], [8.212, 53.141]],
    }
    area_geometry = {
        "type": "Polygon",
        "coordinates": [[
            [8.204, 53.135],
            [8.214, 53.135],
            [8.214, 53.141],
            [8.204, 53.135],
        ]],
    }
    route = store.create_problem(
        title="Lücke im Radweg",
        summary="Der Radweg ist nicht durchgängig.",
        category="mobility",
        scope_kind="route",
        geometry={**route_geometry, "private_note": "Darf nicht öffentlich werden."},
    )
    area = store.create_problem(
        title="Hitze im Quartier",
        summary="Mehrere Straßen sind im Sommer stark aufgeheizt.",
        category="environment",
        scope_kind="area",
        geometry=area_geometry,
    )
    _approve_and_publish(store, database, route)
    _approve_and_publish(store, database, area)
    store._conn.execute(
        "UPDATE civic_problems SET geometry_json = ? WHERE id = ?",
        (json.dumps({**route_geometry, "private_note": "Alte interne Notiz"}), route),
    )
    store._conn.commit()

    projected = {problem["id"]: problem for problem in store.list_public_problems()}
    assert projected[route]["geometry"] == route_geometry
    assert projected[area]["geometry"] == area_geometry
    with pytest.raises(ValueError, match="LineString"):
        store.create_problem(
            title="Falsche Route",
            summary="Eine Fläche ist keine Route.",
            category="mobility",
            scope_kind="route",
            geometry=area_geometry,
        )
    with pytest.raises(ValueError, match="geschlossen"):
        store.create_problem(
            title="Offene Fläche",
            summary="Der Ring ist nicht geschlossen.",
            category="environment",
            scope_kind="area",
            geometry={
                "type": "Polygon",
                "coordinates": [[[8.2, 53.1], [8.3, 53.1], [8.3, 53.2], [8.2, 53.2]]],
            },
        )
    with pytest.raises(ValueError, match="keine Punktkoordinaten"):
        store.create_problem(
            title="Stadtweiter Punkt",
            summary="Stadtweit hat keinen künstlichen Mittelpunkt.",
            category="other",
            scope_kind="citywide",
            latitude=53.14,
            longitude=8.21,
        )
    store._conn.execute(
        "UPDATE civic_problems SET geometry_json = ? WHERE id = ?",
        (json.dumps({"type": "Polygon", "private_note": "Nicht öffentlich"}), area),
    )
    store._conn.commit()
    assert store.get_public_problem(area)["geometry"] is None
    store.close()


def test_point_problem_requires_valid_coordinates(tmp_path):
    store = ProblemStore(tmp_path / "problems.sqlite")
    for latitude, longitude in ((None, None), (float("nan"), 8.2), (91, 8.2)):
        with pytest.raises(ValueError, match="Koordinaten"):
            store.create_problem(
                title="Ohne Ort",
                summary="Ein Punkt ohne gültige Koordinaten ist nicht kartierbar.",
                category="other",
                scope_kind="point",
                latitude=latitude,
                longitude=longitude,
            )
    store.close()
