"""Öffentliche Problemprojektion: Verhalten an der Lesegrenze."""
from __future__ import annotations

import json
import sqlite3

import pytest


def _projection(
    database,
    *,
    title: str,
    published: bool,
    scope_kind: str = "point",
    latitude: float | None = 53.143,
    longitude: float | None = 8.214,
    geometry: dict | None = None,
    category: str = "mobility",
    status: str = "new",
    reports: int = 1,
) -> None:
    connection = sqlite3.connect(database)
    connection.execute(
        """INSERT INTO civic_problems (
               title, summary, category, tags_json, scope_kind,
               location_label, latitude, longitude, geometry_json, status,
               independent_reports, first_observed_at, last_observed_at,
               published_at, updated_at
           ) VALUES (?, ?, ?, '[]', ?, 'Beispielort', ?, ?, ?, ?, ?,
                     '2026-08-20T08:00:00+00:00',
                     '2026-08-21T08:00:00+00:00', ?,
                     '2026-08-21T08:00:00+00:00')""",
        (
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
        ),
    )
    connection.commit()
    connection.close()


def test_public_projection_lists_only_published_rows_without_exact_counts(tmp_path):
    from buergerportal.store import ProblemStore

    database = tmp_path / "ratslotse.sqlite"
    store = ProblemStore(database)
    _projection(database, title="Freigegebenes Problem", published=True, reports=4)
    _projection(database, title="Noch in Moderation", published=False, reports=7)

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
    _projection(database, title="Punkt", published=True)
    _projection(
        database, title="Einrichtung", published=True,
        scope_kind="facility",
    )
    _projection(
        database, title="Route", published=True, scope_kind="route",
        latitude=None, longitude=None, geometry=route,
    )
    _projection(
        database, title="Gebiet", published=True, scope_kind="area",
        latitude=None, longitude=None, geometry=polygon,
    )
    _projection(
        database, title="Geteiltes Gebiet", published=True,
        scope_kind="area", latitude=None, longitude=None, geometry=multipolygon,
    )
    _projection(
        database, title="Stadtweit", published=True,
        scope_kind="citywide", latitude=53.143, longitude=8.214,
    )
    _projection(
        database, title="Kaputte Route", published=True,
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
        database, title="Fiktive Radweg-Lücke", published=True,
        category="mobility",
    )
    _projection(
        database, title="Fiktive Hitzeinsel", published=True,
        category="environment", status="persists",
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
            "fictional": False,
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

    # Jede aktuelle Spalte stimmt mit einer frischen DB überein; die frühere
    # `unique_reporters`-Spalte bleibt als bewusst additive Altlast erhalten.
    fresh_database = tmp_path / "fresh.sqlite"
    ProblemStore(fresh_database).close()

    def columns(path, table):
        connection = sqlite3.connect(path)
        try:
            return {
                row[1]: (row[2], row[3], row[4], row[5])
                for row in connection.execute(f"PRAGMA table_info({table})")
            }
        finally:
            connection.close()

    fresh_columns = columns(fresh_database, "civic_problems")
    migrated_columns = columns(database, "civic_problems")
    assert {
        name: (migrated_columns[name][0], migrated_columns[name][1], migrated_columns[name][3])
        for name in fresh_columns
    } == {
        name: (definition[0], definition[1], definition[3])
        for name, definition in fresh_columns.items()
    }
    default_differences = {
        name
        for name in fresh_columns
        if migrated_columns[name][2] != fresh_columns[name][2]
    }
    assert default_differences == {"location_label", "status", "tags_json"}
    assert set(migrated_columns) - set(fresh_columns) == {"unique_reporters"}
    assert columns(database, "civic_problem_feature_examples") == columns(
        fresh_database, "civic_problem_feature_examples"
    )


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


def test_feature_examples_do_not_bypass_legacy_publication_triggers(tmp_path, monkeypatch):
    from buergerportal.feature_examples import seed_feature_examples
    from buergerportal.store import ProblemStore

    feature_root = tmp_path / "app-feature"
    database = feature_root / "data" / "ratslotse.sqlite"
    database.parent.mkdir(parents=True)
    connection = sqlite3.connect(database)
    connection.executescript(
        """CREATE TABLE civic_problems (
               id INTEGER PRIMARY KEY,
               title TEXT NOT NULL, summary TEXT NOT NULL, category TEXT NOT NULL,
               tags_json TEXT NOT NULL, scope_kind TEXT NOT NULL,
               location_label TEXT NOT NULL, latitude REAL, longitude REAL,
               geometry_json TEXT, status TEXT NOT NULL,
               unique_reporters INTEGER NOT NULL, first_observed_at TEXT NOT NULL,
               last_observed_at TEXT NOT NULL, published_at TEXT, updated_at TEXT NOT NULL
           );
           CREATE TRIGGER trg_civic_problems_create_private
           BEFORE INSERT ON civic_problems
           WHEN NEW.published_at IS NOT NULL
           BEGIN
               SELECT RAISE(ABORT, 'problems must be created unpublished');
           END;"""
    )
    connection.close()
    monkeypatch.setenv("RATSLOTSE_FEATURE_SEED", "1")

    assert seed_feature_examples(database, deployment_root=feature_root) == 7
    store = ProblemStore(database)
    try:
        assert len(store.list_public_problems()) == 7
    finally:
        store.close()

    connection = sqlite3.connect(database)
    with pytest.raises(sqlite3.IntegrityError, match="created unpublished"):
        connection.execute(
            """INSERT INTO civic_problems (
                   title, summary, category, tags_json, scope_kind, location_label,
                   status, unique_reporters, independent_reports, first_observed_at,
                   last_observed_at, published_at, updated_at
               ) VALUES (
                   'Nicht freigegeben', 'Privat', 'other', '[]', 'citywide', '',
                   'new', 1, 1, '2026-09-02', '2026-09-02', '2026-09-02',
                   '2026-09-02'
               )"""
        )
    connection.close()


def test_application_registers_public_problem_endpoint(tmp_path):
    from fastapi.testclient import TestClient

    from buergerportal.store import ProblemStore
    from web.backend.app.deps import get_problem_store
    from web.backend.app.main import app

    database = tmp_path / "ratslotse.sqlite"
    store = ProblemStore(database)
    _projection(database, title="Öffentliche Projektion", published=True)
    app.dependency_overrides[get_problem_store] = lambda: store
    try:
        response = TestClient(app).get("/api/probleme")
        assert response.status_code == 200
        assert response.json()["problems"][0]["title"] == "Öffentliche Projektion"
    finally:
        app.dependency_overrides.pop(get_problem_store, None)
        store.close()
