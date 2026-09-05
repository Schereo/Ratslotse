"""Authenticated HTTP contract for human-confirmed public projections."""
from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest

_BACKEND = Path(__file__).resolve().parents[1] / "web" / "backend"
sys.path.insert(0, str(_BACKEND))
os.environ.setdefault("WEB_JWT_SECRET", "test-secret")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("DISABLE_RATE_LIMIT", "1")
os.environ.setdefault("RATSLOTSE_BUERGERPORTAL", "1")

from fastapi.testclient import TestClient  # noqa: E402
from app import deps  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from app.security import create_access_token  # noqa: E402
from buergerportal.projections import ProjectionStore  # noqa: E402
from buergerportal.reports import DraftContent, PrivateReportStore  # noqa: E402
from buergerportal.store import ProblemStore  # noqa: E402
from kern.store import Store  # noqa: E402


@pytest.fixture
def projection_api(tmp_path):
    database = tmp_path / "ratslotse.sqlite"

    def account_store():
        store = Store(database)
        try:
            yield store
        finally:
            store.close()

    def public_store():
        store = ProblemStore(database)
        try:
            yield store
        finally:
            store.close()

    def private_store():
        store = PrivateReportStore(database)
        try:
            yield store
        finally:
            store.close()

    def projection_store():
        store = ProjectionStore(database)
        try:
            yield store
        finally:
            store.close()

    app.dependency_overrides[deps.get_store] = account_store
    app.dependency_overrides[deps.get_problem_store] = public_store
    app.dependency_overrides[deps.get_private_report_store] = private_store
    app.dependency_overrides[deps.get_projection_store] = projection_store
    app.dependency_overrides[deps.get_owner_projection_store] = projection_store
    try:
        yield TestClient(app), database
    finally:
        app.dependency_overrides.clear()


def _account(
    database,
    email: str,
    *,
    role: str,
    status: str = "active",
    email_verified: bool = True,
) -> tuple[int, dict[str, str]]:
    store = Store(database)
    account_id = store.create_web_user(
        email,
        "x",
        role=role,
        status=status,
        email_verified=email_verified,
    )
    store.close()
    return account_id, {"Authorization": f"Bearer {create_access_token(account_id)}"}


def _approved_report(database, *, reporter_id: int, reviewer_id: int):
    reports = PrivateReportStore(database)
    report_id = reports.create_draft(
        reporter_id=reporter_id,
        content=DraftContent(
            text="Ausdrücklich fiktiver HTTP-Projektionsentwurf.",
            category="public_space",
            scope_kind="citywide",
            observed_on="2026-09-02",
        ),
    )
    submitted = reports.submit_owned_draft(
        report_id,
        reporter_id=reporter_id,
        confirmed_text="Fiktive freigegebene Beobachtung für den HTTP-Vertrag.",
        expected_revision=0,
    )
    reports.decide_report(
        report_id,
        reviewer_id=reviewer_id,
        expected_revision=1,
        outcome="approved",
        rejection_explanation=None,
    )
    reports.close()
    return submitted


def test_disabled_projection_dependencies_do_not_provision_storage(tmp_path, monkeypatch):
    from fastapi import HTTPException

    database = tmp_path / "disabled.sqlite"
    settings = get_settings()
    monkeypatch.setattr(settings, "ratslotse_buergerportal", False)
    monkeypatch.setattr(settings, "ratslotse_db", str(database))

    owner_dependency = deps.get_owner_projection_store()
    assert next(owner_dependency) is None
    with pytest.raises(StopIteration):
        next(owner_dependency)
    with pytest.raises(HTTPException) as blocked:
        next(deps.get_projection_store())

    assert blocked.value.status_code == 404
    assert not database.exists()


def test_projection_http_entrypoint_is_hidden_when_feature_gate_is_closed(
    projection_api,
    monkeypatch,
):
    client, _ = projection_api
    monkeypatch.setattr(get_settings(), "ratslotse_buergerportal", False)

    response = client.get("/api/moderation/projektionen")

    assert response.status_code == 404


def test_projection_http_is_authorized_minimized_and_explicit(projection_api):
    client, database = projection_api
    reporter_id, reporter = _account(database, "fiktive-http-meldung@test.de", role="user")
    reviewer_id, moderator = _account(
        database,
        "fiktive-http-projektionspruefung@test.de",
        role="moderator",
    )
    _, admin = _account(
        database,
        "fiktive-http-projektionsaufsicht@test.de",
        role="admin",
        email_verified=False,
    )
    _, unverified_moderator = _account(
        database,
        "fiktive-unbestaetigte-projektion@test.de",
        role="moderator",
        email_verified=False,
    )
    _, blocked_admin = _account(
        database,
        "fiktive-gesperrte-projektionsaufsicht@test.de",
        role="admin",
        status="blocked",
    )
    approved = _approved_report(
        database,
        reporter_id=reporter_id,
        reviewer_id=reviewer_id,
    )

    assert client.get("/api/moderation/projektionen", headers=reporter).status_code == 403
    assert client.get(
        "/api/moderation/projektionen",
        headers=unverified_moderator,
    ).status_code == 403
    assert client.get(
        "/api/moderation/projektionen",
        headers=blocked_admin,
    ).status_code == 403
    assert client.get("/api/moderation/projektionen", headers=admin).status_code == 200
    listing = client.get(
        "/api/moderation/projektionen?limit=20&offset=0",
        headers=moderator,
    )
    detail = client.get(
        f"/api/moderation/projektionen/{approved.id}",
        headers=moderator,
    )

    assert listing.status_code == 200
    assert listing.json() == {
        "reports": [{
            "id": approved.id,
            "content_revision": 1,
            "text_preview": "Fiktive freigegebene Beobachtung für den HTTP-Vertrag.",
            "category": "public_space",
            "scope_kind": "citywide",
            "observed_on": "2026-09-02",
        }],
        "total": 1,
        "limit": 20,
        "offset": 0,
    }
    assert detail.status_code == 200
    assert detail.json() == {
        "id": approved.id,
        "content_revision": 1,
        "category": "public_space",
        "scope_kind": "citywide",
        "observations": [{
            "text": "Fiktive freigegebene Beobachtung für den HTTP-Vertrag.",
            "observed_on": "2026-09-02",
        }],
    }
    assert client.get(
        f"/api/moderation/projektionen/{approved.id}/ziele?q=fiktiv&limit=20",
        headers=moderator,
    ).json() == []

    confirmed = client.post(
        f"/api/moderation/projektionen/{approved.id}/neue-stadtweite-projektion",
        headers=moderator,
        json={
            "expected_revision": 1,
            "title": "Fiktive öffentliche HTTP-Projektion",
            "summary": "Bewusst öffentliche, fiktive und datensparsame Zusammenfassung.",
        },
    )

    assert confirmed.status_code == 201
    assert confirmed.json() == {
        "report_id": approved.id,
        "content_revision": 1,
        "problem_id": confirmed.json()["problem_id"],
        "problem_title": "Fiktive öffentliche HTTP-Projektion",
    }
    unavailable = client.get(
        f"/api/moderation/projektionen/{approved.id}",
        headers=moderator,
    )
    assert unavailable.status_code == 404
    public = client.get(f"/api/probleme/{confirmed.json()['problem_id']}")
    owner_list = client.get("/api/meldungen?limit=20&offset=0", headers=reporter)
    owner_detail = client.get(f"/api/meldungen/{approved.id}", headers=reporter)
    assert public.status_code == 200
    expected_public_link = {
        "id": confirmed.json()["problem_id"],
        "title": "Fiktive öffentliche HTTP-Projektion",
    }
    assert owner_list.json()["reports"][0]["public_projection"] == expected_public_link
    assert owner_detail.json()["public_projection"] == expected_public_link
    assert public.json()["location_label"] == ""
    assert public.json()["latitude"] is None
    assert public.json()["longitude"] is None
    encoded = str(confirmed.json()) + str(public.json())
    assert "Fiktive freigegebene Beobachtung" not in str(public.json())
    for forbidden in (
        "reporter_id", "reviewer_id", "email", "ai_verdict",
        "model_identifier", "claim_token",
    ):
        assert forbidden not in encoded

    second = _approved_report(
        database,
        reporter_id=reporter_id,
        reviewer_id=reviewer_id,
    )
    targets = client.get(
        f"/api/moderation/projektionen/{second.id}/ziele?q=HTTP&limit=20",
        headers=moderator,
    )
    assert targets.status_code == 200
    assert targets.json() == [{
        "problem_id": confirmed.json()["problem_id"],
        "title": "Fiktive öffentliche HTTP-Projektion",
        "summary": "Bewusst öffentliche, fiktive und datensparsame Zusammenfassung.",
        "category": "public_space",
        "scope_kind": "citywide",
        "status": "new",
        "independent_reports": 1,
    }]
    existing = client.post(
        f"/api/moderation/projektionen/{second.id}/bestehendes-problem",
        headers=moderator,
        json={
            "expected_revision": 1,
            "problem_id": confirmed.json()["problem_id"],
        },
    )
    retry = client.post(
        f"/api/moderation/projektionen/{second.id}/bestehendes-problem",
        headers=moderator,
        json={
            "expected_revision": 1,
            "problem_id": confirmed.json()["problem_id"],
        },
    )
    conflict = client.post(
        f"/api/moderation/projektionen/{second.id}/bestehendes-problem",
        headers=moderator,
        json={"expected_revision": 1, "problem_id": 999_999},
    )
    assert existing.status_code == 201
    assert retry.status_code == 201
    assert retry.json() == existing.json()
    assert conflict.status_code == 409
    same_owner_public = client.get(f"/api/probleme/{confirmed.json()['problem_id']}")
    assert same_owner_public.json()["independent_reports"] == 1
    assert client.get(
        "/api/moderation/projektionen/999999",
        headers=moderator,
    ).status_code == 404
