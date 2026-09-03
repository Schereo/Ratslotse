"""Öffentliche Problemprojektion: Verhalten an der Lesegrenze."""
from __future__ import annotations

import json
import sqlite3

import pytest


def _projection(
    database,
    *,
    key: str,
    title: str,
    published: bool,
    scope_kind: str = "point",
    latitude: float | None = 53.143,
    longitude: float | None = 8.214,
    geometry: dict | None = None,
    category: str = "mobility",
    status: str = "new",
    reports: int = 1,
    fictional: bool = False,
) -> None:
    connection = sqlite3.connect(database)
    connection.execute(
        """INSERT INTO civic_problems (
               example_key, title, summary, category, tags_json, scope_kind,
               location_label, latitude, longitude, geometry_json, status,
               independent_reports, first_observed_at, last_observed_at,
               published_at, updated_at, is_fictional
           ) VALUES (?, ?, ?, ?, '[]', ?, 'Beispielort', ?, ?, ?, ?, ?,
                     '2026-08-20T08:00:00+00:00',
                     '2026-08-21T08:00:00+00:00', ?,
                     '2026-08-21T08:00:00+00:00', ?)""",
        (
            key,
            title,
            "Eine moderierte öffentliche Zusammenfassung.",
            category,
            scope_kind,
            latitude,
            longitude,
            json.dumps(geometry) if geometry else None,
            status,
            reports,
            "2026-08-21T08:00:00+00:00" if published else None,
            int(fictional),
        ),
    )
    connection.commit()
    connection.close()


def test_public_projection_lists_only_published_rows_without_exact_counts(tmp_path):
    from buergerportal.store import ProblemStore

    database = tmp_path / "ratslotse.sqlite"
    store = ProblemStore(database)
    _projection(database, key="visible", title="Freigegebenes Problem", published=True, reports=4)
    _projection(database, key="private", title="Noch in Moderation", published=False, reports=7)

    result = store.list_public_problems()

    assert [problem["title"] for problem in result] == ["Freigegebenes Problem"]
    assert result[0]["frequency"] == "several"
    assert "independent_reports" not in result[0]
    assert "summary" not in result[0]
    assert "tags" not in result[0]
    store.close()


def test_public_projection_keeps_only_truthful_map_geometry(tmp_path):
    from buergerportal.store import ProblemStore

    database = tmp_path / "ratslotse.sqlite"
    store = ProblemStore(database)
    route = {"type": "LineString", "coordinates": [[8.19, 53.14], [8.22, 53.15]]}
    polygon = {
        "type": "Polygon",
        "coordinates": [[[8.19, 53.14], [8.22, 53.14], [8.22, 53.15], [8.19, 53.14]]],
    }
    multipolygon = {"type": "MultiPolygon", "coordinates": [polygon["coordinates"]]}
    _projection(database, key="point", title="Punkt", published=True)
    _projection(
        database, key="facility", title="Einrichtung", published=True,
        scope_kind="facility",
    )
    _projection(
        database, key="route", title="Route", published=True, scope_kind="route",
        latitude=None, longitude=None, geometry=route,
    )
    _projection(
        database, key="polygon", title="Gebiet", published=True, scope_kind="area",
        latitude=None, longitude=None, geometry=polygon,
    )
    _projection(
        database, key="multipolygon", title="Geteiltes Gebiet", published=True,
        scope_kind="area", latitude=None, longitude=None, geometry=multipolygon,
    )
    _projection(
        database, key="citywide", title="Stadtweit", published=True,
        scope_kind="citywide", latitude=53.143, longitude=8.214,
    )
    _projection(
        database, key="malformed", title="Kaputte Route", published=True,
        scope_kind="route", latitude=None, longitude=None,
        geometry={"type": "LineString", "coordinates": [[8.19, 53.14]]},
    )

    projected = {problem["title"]: problem for problem in store.list_public_problems()}

    assert projected["Punkt"]["latitude"] == 53.143
    assert projected["Einrichtung"]["longitude"] == 8.214
    assert projected["Route"]["geometry"] == route
    assert projected["Gebiet"]["geometry"] == polygon
    assert projected["Geteiltes Gebiet"]["geometry"] == multipolygon
    assert projected["Stadtweit"]["latitude"] is None
    assert projected["Stadtweit"]["longitude"] is None
    assert projected["Stadtweit"]["geometry"] is None
    assert projected["Kaputte Route"]["geometry"] is None
    store.close()


def test_public_api_is_open_filtered_and_uses_the_sparse_response_contract(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from buergerportal.store import ProblemStore
    from web.backend.app.deps import get_problem_store
    from web.backend.app.routers.problems import router

    database = tmp_path / "ratslotse.sqlite"
    store = ProblemStore(database)
    _projection(
        database, key="mobility", title="Fiktive Radweg-Lücke", published=True,
        category="mobility", fictional=True,
    )
    _projection(
        database, key="environment", title="Fiktive Hitzeinsel", published=True,
        category="environment", status="persists", fictional=True,
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_problem_store] = lambda: store
    client = TestClient(app)

    response = client.get("/api/probleme?category=environment&status=persists")

    assert response.status_code == 200
    assert response.json() == {
        "problems": [{
            "id": 2,
            "title": "Fiktive Hitzeinsel",
            "category": "environment",
            "scope_kind": "point",
            "location_label": "Beispielort",
            "latitude": 53.143,
            "longitude": 8.214,
            "geometry": None,
            "status": "persists",
            "frequency": "once",
            "fictional": True,
        }],
        "total": 1,
    }
    assert "independent_reports" not in response.text
    assert client.get("/api/probleme?category=personenkritik").status_code == 422
    assert client.get("/api/probleme?status=amtlich_in_bearbeitung").status_code == 422
    store.close()


def test_projection_migration_preserves_legacy_public_rows_and_is_idempotent(tmp_path):
    from buergerportal.store import ProblemStore

    database = tmp_path / "legacy.sqlite"
    connection = sqlite3.connect(database)
    connection.executescript(
        """CREATE TABLE civic_problems (
               id INTEGER PRIMARY KEY,
               title TEXT NOT NULL,
               summary TEXT NOT NULL,
               category TEXT NOT NULL,
               tags_json TEXT NOT NULL,
               scope_kind TEXT NOT NULL,
               location_label TEXT NOT NULL,
               latitude REAL,
               longitude REAL,
               geometry_json TEXT,
               status TEXT NOT NULL,
               unique_reporters INTEGER NOT NULL,
               first_observed_at TEXT NOT NULL,
               last_observed_at TEXT NOT NULL,
               published_at TEXT,
               updated_at TEXT NOT NULL
           );
           INSERT INTO civic_problems VALUES (
               41, 'Bestehende Projektion', 'Öffentliche Zusammenfassung',
               'public_space', '[]', 'citywide', 'Gesamtes Stadtgebiet',
               NULL, NULL, NULL, 'multiple_reports', 3,
               '2026-08-01T08:00:00+00:00', '2026-08-20T08:00:00+00:00',
               '2026-08-21T08:00:00+00:00', '2026-08-21T08:00:00+00:00'
           );
           INSERT INTO civic_problems VALUES (
               42, 'Ungültiger Alt-Punkt', 'Öffentliche Zusammenfassung',
               'public_space', '[]', 'point', 'Alter Datenbestand',
               200, 8.21, NULL, 'new', 1,
               '2026-08-01T08:00:00+00:00', '2026-08-22T08:00:00+00:00',
               '2026-08-22T08:00:00+00:00', '2026-08-22T08:00:00+00:00'
           );"""
    )
    connection.close()

    first = ProblemStore(database)
    first.close()
    migrated = ProblemStore(database)

    projected = {problem["title"]: problem for problem in migrated.list_public_problems()}
    assert projected["Bestehende Projektion"] == {
        "id": 41,
        "title": "Bestehende Projektion",
        "category": "public_space",
        "scope_kind": "citywide",
        "location_label": "Gesamtes Stadtgebiet",
        "latitude": None,
        "longitude": None,
        "geometry": None,
        "status": "multiple_reports",
        "frequency": "several",
        "fictional": False,
    }
    assert projected["Ungültiger Alt-Punkt"]["latitude"] is None
    assert projected["Ungültiger Alt-Punkt"]["longitude"] is None
    migrated.close()


def test_feature_examples_are_guarded_fictional_and_idempotent(tmp_path, monkeypatch):
    from buergerportal.feature_examples import seed_feature_examples
    from buergerportal.store import ProblemStore

    feature_root = tmp_path / "app-feature"
    database = feature_root / "data" / "ratslotse.sqlite"
    with pytest.raises(RuntimeError, match="freigeschaltet"):
        seed_feature_examples(database, deployment_root=feature_root)
    assert not database.exists()

    forbidden_root = tmp_path / "app-dev"
    forbidden_database = forbidden_root / "data" / "ratslotse.sqlite"
    monkeypatch.setenv("RATSLOTSE_FEATURE_SEED", "1")
    try:
        seed_feature_examples(forbidden_database, deployment_root=forbidden_root)
    except RuntimeError as error:
        assert "app-feature" in str(error)
    else:
        raise AssertionError("Beispiele durften außerhalb der Feature-Instanz schreiben")
    assert not forbidden_database.exists()

    first_count = seed_feature_examples(database, deployment_root=feature_root)
    first = ProblemStore(database).list_public_problems()
    second_count = seed_feature_examples(database, deployment_root=feature_root)
    second_store = ProblemStore(database)
    second = second_store.list_public_problems()

    assert first_count == second_count == 7
    assert [problem["id"] for problem in second] == [problem["id"] for problem in first]
    assert all(problem["fictional"] for problem in second)
    assert all(problem["title"].startswith("Beispiel:") for problem in second)
    assert {problem["scope_kind"] for problem in second} == {
        "point", "facility", "route", "area", "citywide",
    }
    second_store.close()


def test_application_registers_public_problem_endpoint(tmp_path):
    from fastapi.testclient import TestClient

    from buergerportal.store import ProblemStore
    from web.backend.app.deps import get_problem_store
    from web.backend.app.main import app

    database = tmp_path / "ratslotse.sqlite"
    store = ProblemStore(database)
    _projection(database, key="visible", title="Öffentliche Projektion", published=True)
    app.dependency_overrides[get_problem_store] = lambda: store
    try:
        response = TestClient(app).get("/api/probleme")
        assert response.status_code == 200
        assert response.json()["problems"][0]["title"] == "Öffentliche Projektion"
    finally:
        app.dependency_overrides.pop(get_problem_store, None)
        store.close()
