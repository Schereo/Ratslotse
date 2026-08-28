"""Problemtracker: öffentliche Projektion und API-Grenze."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from buergerportal.store import ProblemStore
from web.backend.app.deps import get_problem_store
from web.backend.app.routers.problems import router


def test_problem_store_exposes_only_published_problems(tmp_path):
    store = ProblemStore(tmp_path / "problems.sqlite")
    visible = store.create_problem(
        title="Dunkler Weg",
        summary="Der Weg ist abends nicht durchgängig beleuchtet.",
        category="public_space",
        scope_kind="point",
        location_label="Innenstadt",
        latitude=53.14,
        longitude=8.21,
        unique_reporters=3,
        current_observations=2,
        total_observations=4,
        published=True,
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

    listed = store.list_public_problems()
    assert [problem["id"] for problem in listed] == [visible]
    assert "events" not in listed[0]
    assert store.get_public_problem(visible)["events"][0]["title"] == "Problem veröffentlicht"
    assert store.get_public_problem(visible)["unique_reporters"] == 3
    store.close()


def test_public_api_hides_unpublished_problem_and_exposes_detail(tmp_path):
    store = ProblemStore(tmp_path / "problems.sqlite")
    visible = store.create_problem(
        title="Überfüllte Fahrradständer",
        summary="Zu Pendelzeiten reichen die Plätze nicht aus.",
        category="mobility",
        scope_kind="facility",
        location_label="Bahnhof",
        latitude=53.143,
        longitude=8.223,
        published=True,
    )
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
    assert client.get(f"/api/probleme/{visible}").status_code == 200
    assert client.get(f"/api/probleme/{hidden}").status_code == 404
    assert client.get("/api/probleme?status=amtlich_in_bearbeitung").status_code == 422
    store.close()


def test_point_problem_requires_coordinates(tmp_path):
    store = ProblemStore(tmp_path / "problems.sqlite")
    try:
        store.create_problem(
            title="Ohne Ort",
            summary="Ein Punkt ohne Koordinaten ist nicht kartierbar.",
            category="other",
            scope_kind="point",
        )
    except ValueError as error:
        assert "Koordinaten" in str(error)
    else:
        raise AssertionError("Punktproblem ohne Koordinaten wurde gespeichert")
    finally:
        store.close()
