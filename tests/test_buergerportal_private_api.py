"""Private Bürgerportal-API: Authentisierung, Eigentum und Retry-Sicherheit."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import sys
from threading import Barrier

import pytest

_BACKEND = Path(__file__).resolve().parents[1] / "web" / "backend"
sys.path.insert(0, str(_BACKEND))
os.environ.setdefault("WEB_JWT_SECRET", "test-secret")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("DISABLE_RATE_LIMIT", "1")

from fastapi.testclient import TestClient  # noqa: E402
from app import deps  # noqa: E402
from app.main import app  # noqa: E402
from app.security import create_access_token  # noqa: E402
from buergerportal.reports import PrivateReportStore  # noqa: E402
from buergerportal.store import ProblemStore  # noqa: E402
from kern.store import Store  # noqa: E402


@pytest.fixture
def private_api(tmp_path):
    """Ein FastAPI-Client und alle Stores gegen dieselbe temporäre SQLite."""
    database = tmp_path / "ratslotse.sqlite"

    def get_store():
        store = Store(database)
        try:
            yield store
        finally:
            store.close()

    def get_problem_store():
        store = ProblemStore(database)
        try:
            yield store
        finally:
            store.close()

    def get_private_report_store():
        store = PrivateReportStore(database)
        try:
            yield store
        finally:
            store.close()

    app.dependency_overrides[deps.get_store] = get_store
    app.dependency_overrides[deps.get_problem_store] = get_problem_store
    app.dependency_overrides[deps.get_private_report_store] = get_private_report_store
    try:
        yield TestClient(app), database
    finally:
        app.dependency_overrides.clear()


def _account(
    database: Path,
    *,
    email: str,
    role: str = "user",
    status: str = "active",
    email_verified: bool = True,
) -> tuple[int, dict[str, str]]:
    store = Store(database)
    user_id = store.create_web_user(
        email,
        "nur-ein-fiktiver-test-hash",
        role=role,
        status=status,
        email_verified=email_verified,
    )
    store.close()
    token = create_access_token(user_id)
    return user_id, {"Authorization": f"Bearer {token}"}


def _content(
    *, text: str = "Am fiktiven Kanal fehlt abends Licht."
) -> dict:
    return {
        "text": text,
        "category": "public_space",
        "scope_kind": "point",
        "location_label": "Fiktiver Kanalweg",
        "latitude": 53.143,
        "longitude": 8.214,
        "observed_on": "2026-09-01",
    }


def _draft(
    *,
    key: str = "fiktiver-request-0001",
    text: str = "Am fiktiven Kanal fehlt abends Licht.",
) -> dict:
    return {"idempotency_key": key, **_content(text=text)}


def _assert_no_account_identifier(value) -> None:
    if isinstance(value, dict):
        forbidden = {"reporter_id", "owner_id", "account_id", "user_id"}
        assert not (forbidden & value.keys())
        for nested in value.values():
            _assert_no_account_identifier(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_no_account_identifier(nested)


def test_private_routes_reject_missing_ineligible_and_admin_sessions(private_api):
    client, database = private_api
    _, active = _account(database, email="aktiv@example.org")
    _, pending = _account(
        database,
        email="offen@example.org",
        status="pending",
        email_verified=False,
    )
    _, blocked = _account(
        database,
        email="gesperrt@example.org",
        status="blocked",
        email_verified=True,
    )
    _, admin = _account(database, email="admin@example.org", role="admin")

    created = client.post("/api/meldungen/entwuerfe", json=_draft(), headers=active)
    assert created.status_code == 201
    report_id = created.json()["id"]
    calls = (
        ("post", "/api/meldungen/entwuerfe", _draft(key="fiktiver-request-0002")),
        ("get", f"/api/meldungen/{report_id}", None),
        (
            "put",
            f"/api/meldungen/{report_id}/entwurf",
            {**_content(), "expected_revision": 0},
        ),
        (
            "post",
            f"/api/meldungen/{report_id}/absenden",
            {"expected_revision": 0, "confirmed_text": "Bestätigte fiktive Beobachtung."},
        ),
    )
    for method, path, body in calls:
        kwargs = {} if body is None else {"json": {k: v for k, v in body.items() if v is not None}}
        assert client.request(method, path, **kwargs).status_code == 401, path
        for headers in (pending, blocked, admin):
            assert client.request(method, path, headers=headers, **kwargs).status_code == 403, path


def test_private_validation_errors_do_not_echo_raw_text_or_exact_places(private_api):
    client, database = private_api
    _, owner = _account(database, email="fehlerdetails@example.org")
    private_text = "Nur privat: fiktive Rohbeschreibung 7d14."
    private_place = "Nur privat: genauer Fantasieort 9a31."
    body = _draft(text=private_text)
    body["location_label"] = private_place
    del body["category"]

    response = client.post(
        "/api/meldungen/entwuerfe", json=body, headers=owner
    )

    assert response.status_code == 422
    assert private_text not in response.text
    assert private_place not in response.text
    assert "53.143" not in response.text
    assert "8.214" not in response.text


def test_owner_id_only_comes_from_the_authenticated_session(private_api):
    client, database = private_api
    owner_id, owner = _account(database, email="eigentuemer@example.org")
    other_id, _ = _account(database, email="fremd@example.org")

    attempted = client.post(
        "/api/meldungen/entwuerfe",
        json={**_draft(), "reporter_id": other_id},
        headers=owner,
    )
    assert attempted.status_code == 422

    created = client.post(
        "/api/meldungen/entwuerfe",
        json=_draft(key="fiktiver-request-0003"),
        headers=owner,
    )
    assert created.status_code == 201
    payload = created.json()
    _assert_no_account_identifier(payload)
    store = PrivateReportStore(database)
    assert store.get_owned_report(payload["id"], reporter_id=owner_id) is not None
    assert store.get_owned_report(payload["id"], reporter_id=other_id) is None
    store.close()


def test_foreign_and_unknown_ids_have_the_same_404_for_every_operation(private_api):
    client, database = private_api
    _, owner = _account(database, email="alpha@example.org")
    _, other = _account(database, email="beta@example.org")
    report_id = client.post(
        "/api/meldungen/entwuerfe", json=_draft(), headers=owner
    ).json()["id"]
    unknown_id = report_id + 9_000_000

    requests = (
        ("get", "/api/meldungen/{report_id}", None),
        (
            "put",
            "/api/meldungen/{report_id}/entwurf",
            {**_content(text="Geänderter fiktiver Entwurf."), "expected_revision": 0},
        ),
        (
            "post",
            "/api/meldungen/{report_id}/absenden",
            {"expected_revision": 0, "confirmed_text": "Bestätigte fiktive Beobachtung."},
        ),
    )
    for method, path, body in requests:
        kwargs = {} if body is None else {"json": body}
        foreign = client.request(method, path.format(report_id=report_id), headers=other, **kwargs)
        unknown = client.request(method, path.format(report_id=unknown_id), headers=other, **kwargs)
        assert (foreign.status_code, foreign.json()) == (404, {"detail": "Meldung nicht gefunden."})
        assert (unknown.status_code, unknown.json()) == (foreign.status_code, foreign.json())


def test_draft_creation_is_account_scoped_idempotent_and_conflict_closed(private_api):
    client, database = private_api
    owner_id, owner = _account(database, email="retry@example.org")
    _, other = _account(database, email="anderes-konto@example.org")
    body = _draft(key="fiktiver-request-retry")

    first = client.post("/api/meldungen/entwuerfe", json=body, headers=owner)
    retry = client.post("/api/meldungen/entwuerfe", json=body, headers=owner)
    other_account = client.post("/api/meldungen/entwuerfe", json=body, headers=other)
    conflict = client.post(
        "/api/meldungen/entwuerfe",
        json={**body, "text": "Anderer fiktiver Inhalt mit demselben Schlüssel."},
        headers=owner,
    )

    assert first.status_code == retry.status_code == other_account.status_code == 201
    assert retry.json() == first.json()
    assert other_account.json()["id"] != first.json()["id"]
    assert conflict.status_code == 409

    barrier = Barrier(2)
    concurrent_body = _draft(key="fiktiver-request-konkurrenz")

    def create_once() -> tuple[int, dict]:
        barrier.wait()
        response = TestClient(app).post(
            "/api/meldungen/entwuerfe", json=concurrent_body, headers=owner
        )
        return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=2) as executor:
        concurrent = list(executor.map(lambda _: create_once(), range(2)))

    assert [status for status, _ in concurrent] == [201, 201]
    assert concurrent[0][1] == concurrent[1][1]
    # Zwei Entwürfe des ersten Kontos: der erste Retry-Fall und der Konkurrenz-Fall.
    report_store = PrivateReportStore(database)
    assert report_store._conn.execute(
        "SELECT COUNT(*) FROM civic_reports WHERE reporter_id = ?", (owner_id,)
    ).fetchone()[0] == 2
    report_store.close()


def test_updates_are_revision_safe_and_submission_retries_are_exact(private_api):
    client, database = private_api
    owner_id, owner = _account(database, email="revision@example.org")
    created = client.post(
        "/api/meldungen/entwuerfe", json=_draft(), headers=owner
    ).json()
    report_id = created["id"]
    assert created["state"] == "draft"
    assert created["content_revision"] == 0

    update_body = {
        **_content(text="Korrigierte fiktive Beschreibung."),
        "expected_revision": 0,
    }
    updated = client.put(
        f"/api/meldungen/{report_id}/entwurf", json=update_body, headers=owner
    )
    stale = client.put(
        f"/api/meldungen/{report_id}/entwurf",
        json={**update_body, "text": "Diese veraltete Änderung darf nicht gewinnen."},
        headers=owner,
    )
    assert updated.status_code == 200
    assert updated.json()["content_revision"] == 1
    assert stale.status_code == 409
    assert client.get(f"/api/meldungen/{report_id}", headers=owner).json() == updated.json()

    submission = {
        "expected_revision": 1,
        "confirmed_text": "Bestätigte fiktive Beobachtung.",
    }
    first = client.post(
        f"/api/meldungen/{report_id}/absenden", json=submission, headers=owner
    )
    retry = client.post(
        f"/api/meldungen/{report_id}/absenden", json=submission, headers=owner
    )
    changed = client.post(
        f"/api/meldungen/{report_id}/absenden",
        json={**submission, "confirmed_text": "Abweichender Absendeversuch."},
        headers=owner,
    )
    wrong_revision = client.post(
        f"/api/meldungen/{report_id}/absenden",
        json={**submission, "expected_revision": 2},
        headers=owner,
    )
    after_submission_update = client.put(
        f"/api/meldungen/{report_id}/entwurf",
        json={**update_body, "expected_revision": 2},
        headers=owner,
    )

    assert first.status_code == retry.status_code == 200
    assert retry.json() == first.json()
    assert first.json()["state"] == "submitted"
    assert first.json()["content_revision"] == 2
    assert changed.status_code == wrong_revision.status_code == 409
    assert after_submission_update.status_code == 409
    _assert_no_account_identifier(first.json())
    store = PrivateReportStore(database)
    persisted = store.get_owned_report(report_id, reporter_id=owner_id)
    observations = store._conn.execute(
        "SELECT COUNT(*) FROM civic_report_observations WHERE report_id = ?", (report_id,)
    ).fetchone()[0]
    store.close()
    assert persisted is not None
    assert observations == 1


def test_concurrent_identical_submission_is_idempotent(private_api):
    client, database = private_api
    owner_id, owner = _account(database, email="absende-retry@example.org")
    report_id = client.post(
        "/api/meldungen/entwuerfe", json=_draft(), headers=owner
    ).json()["id"]
    submission = {
        "expected_revision": 0,
        "confirmed_text": "Bestätigte fiktive Beobachtung bei Konkurrenz.",
    }
    barrier = Barrier(2)

    def submit_once() -> tuple[int, dict]:
        barrier.wait()
        response = TestClient(app).post(
            f"/api/meldungen/{report_id}/absenden",
            json=submission,
            headers=owner,
        )
        return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=2) as executor:
        submissions = list(executor.map(lambda _: submit_once(), range(2)))

    assert [status for status, _ in submissions] == [200, 200]
    assert submissions[0][1] == submissions[1][1]
    store = PrivateReportStore(database)
    report = store.get_owned_report(report_id, reporter_id=owner_id)
    store.close()
    assert report is not None
    assert len(report.observations) == 1


def test_private_api_does_not_change_public_problem_projections(private_api):
    client, database = private_api
    _, owner = _account(database, email="projektion@example.org")
    public_store = ProblemStore(database)
    with public_store._conn:
        public_store._conn.execute(
            """INSERT INTO civic_problems (
                   title, summary, category, tags_json, scope_kind,
                   location_label, latitude, longitude, status,
                   independent_reports, first_observed_at, last_observed_at,
                   published_at, updated_at
               ) VALUES (
                   'Fiktives öffentliches Problem', 'Öffentliche Zusammenfassung',
                   'public_space', '[]', 'point', 'Fiktiver öffentlicher Ort',
                   53.143, 8.214, 'new', 2,
                   '2026-08-30T12:00:00+00:00', '2026-09-01T12:00:00+00:00',
                   '2026-09-01T12:00:00+00:00', '2026-09-01T12:00:00+00:00'
               )"""
        )
    public_store.close()
    before = client.get("/api/probleme").json()

    created = client.post(
        "/api/meldungen/entwuerfe", json=_draft(), headers=owner
    ).json()
    client.put(
        f"/api/meldungen/{created['id']}/entwurf",
        json={**_content(text="Geänderter privater Text."), "expected_revision": 0},
        headers=owner,
    )
    client.post(
        f"/api/meldungen/{created['id']}/absenden",
        json={"expected_revision": 1, "confirmed_text": "Bestätigter privater Text."},
        headers=owner,
    )

    assert client.get("/api/probleme").json() == before


def test_private_openapi_contract_is_explicit_and_contains_no_owner_id():
    operation_paths = {
        ("post", "/api/meldungen/entwuerfe"),
        ("get", "/api/meldungen/{report_id}"),
        ("put", "/api/meldungen/{report_id}/entwurf"),
        ("post", "/api/meldungen/{report_id}/absenden"),
    }
    schema = app.openapi()
    assert operation_paths <= {
        (method, path)
        for path, operations in schema["paths"].items()
        for method in operations
    }
    private_report = schema["components"]["schemas"]["PrivateReportOut"]
    assert set(private_report["required"]) == {
        "id",
        "draft_text",
        "confirmed_text",
        "category",
        "scope_kind",
        "observed_on",
        "location_label",
        "latitude",
        "longitude",
        "state",
        "content_revision",
        "submitted_at",
        "created_at",
        "updated_at",
    }
    serialized = str(private_report).lower()
    assert "reporter" not in serialized
    assert "owner" not in serialized
    assert "account" not in serialized
    assert "user_id" not in serialized
