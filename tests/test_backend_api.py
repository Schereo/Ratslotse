"""Integration tests for the FastAPI backend (web/backend)."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Make the backend importable and point it at throwaway databases BEFORE import.
_BACKEND = Path(__file__).resolve().parents[1] / "web" / "backend"
sys.path.insert(0, str(_BACKEND))
_TMP = tempfile.mkdtemp()
os.environ["NWZ_DB"] = str(Path(_TMP) / "nwz.sqlite")
os.environ["COUNCIL_DB"] = str(Path(_TMP) / "council.sqlite")
os.environ["WEB_JWT_SECRET"] = "test-secret"
os.environ["WEB_ADMIN_EMAIL"] = "admin@test.de"

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from nwz.store import Store  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from council.scraper import CouncilSession, AgendaItem  # noqa: E402

NWZ_DB = os.environ["NWZ_DB"]
COUNCIL_DB = os.environ["COUNCIL_DB"]


@pytest.fixture(autouse=True)
def fresh_dbs():
    for p in (NWZ_DB, COUNCIL_DB):
        Path(p).unlink(missing_ok=True)
    yield


@pytest.fixture
def client():
    return TestClient(app)


def _register(client, email="admin@test.de", password="password123"):
    return client.post("/api/auth/register", json={"email": email, "password": password})


def _link(email):
    """Simulate the bot redeeming a link code, returning the linked chat_id."""
    store = Store(NWZ_DB)
    uid = store.get_web_user_by_email(email)["id"]
    store.create_link_code(uid, "LINK01")
    store.redeem_link_code("LINK01", 555, "Tester")
    store.close()
    return 555


# ---- auth ----
def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_register_first_user_is_admin(client):
    r = _register(client)
    assert r.status_code == 201
    assert r.json()["role"] == "admin"
    assert r.json()["linked"] is False


def test_second_user_is_regular(client):
    _register(client)
    r = _register(client, email="bob@test.de")
    assert r.status_code == 201
    assert r.json()["role"] == "user"


def test_duplicate_email_conflicts(client):
    _register(client)
    assert _register(client).status_code == 409


def test_login_and_me(client):
    _register(client)
    fresh = TestClient(app)
    assert fresh.post("/api/auth/login", json={"email": "admin@test.de", "password": "wrong"}).status_code == 401
    r = fresh.post("/api/auth/login", json={"email": "admin@test.de", "password": "password123"})
    assert r.status_code == 200
    assert fresh.get("/api/auth/me").json()["email"] == "admin@test.de"


def test_logout_clears_session(client):
    _register(client)
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401


def test_me_requires_auth(client):
    assert client.get("/api/auth/me").status_code == 401


# ---- admin: prompts ----
def test_admin_prompts_crud(client):
    _register(client)
    r = client.get("/api/admin/prompts")
    assert r.status_code == 200 and len(r.json()) == 10
    key = "nwz_digest_system"
    upd = client.put(f"/api/admin/prompts/{key}", json={"content": "Custom {pub_date}"})
    assert upd.status_code == 200 and upd.json()["is_overridden"] is True
    rst = client.post(f"/api/admin/prompts/{key}/reset")
    assert rst.json()["is_overridden"] is False


def test_admin_endpoints_forbidden_for_regular_user(client):
    _register(client)  # admin
    bob = TestClient(app)
    bob.post("/api/auth/register", json={"email": "bob@test.de", "password": "password123"})
    assert bob.get("/api/admin/prompts").status_code == 403
    assert bob.get("/api/admin/users").status_code == 403


def test_admin_can_change_role(client):
    _register(client)  # `client` stays logged in as admin
    # Register bob on a separate client so the admin cookie on `client` is kept.
    TestClient(app).post("/api/auth/register", json={"email": "bob@test.de", "password": "password123"})
    users = client.get("/api/admin/users").json()
    bob = next(u for u in users if u["email"] == "bob@test.de")
    r = client.put(f"/api/admin/users/{bob['id']}/role", json={"role": "admin"})
    assert r.status_code == 200 and r.json()["role"] == "admin"


# ---- nwz search ----
def test_nwz_search_empty(client):
    _register(client)
    r = client.get("/api/nwz/search?q=test")
    assert r.status_code == 200 and r.json()["count"] == 0


def test_nwz_article_404(client):
    _register(client)
    assert client.get("/api/nwz/article/1/missing").status_code == 404


def test_nwz_requires_auth(client):
    assert client.get("/api/nwz/search?q=x").status_code == 401


# ---- council ----
def test_council_sessions_and_detail(client):
    _register(client)
    cs = CouncilStore(COUNCIL_DB)
    cs.save_session(
        CouncilSession(42, "Bauausschuss", "2026-06-10", "18:00", "Rathaus",
                       agenda_items=[AgendaItem("Ö 1", "Bebauungsplan Hafen")])
    )
    cs.close()
    r = client.get("/api/council/sessions?scope=all")
    assert r.status_code == 200 and r.json()["count"] == 1
    detail = client.get("/api/council/session/42").json()
    assert detail["committee"] == "Bauausschuss"
    assert detail["agenda_items"][0]["title"] == "Bebauungsplan Hafen"
    assert "ksinr=42" in detail["url"]


def test_council_session_404(client):
    _register(client)
    assert client.get("/api/council/session/999").status_code == 404


# ---- topics (need linking) ----
def test_topics_require_linked_account(client):
    _register(client)
    assert client.get("/api/topics").status_code == 409


def test_topics_and_subscriptions_flow(client):
    _register(client)
    _link("admin@test.de")
    # add topic
    r = client.post("/api/topics", json={"name": "Radwege", "description": "Ausbau in Oldenburg"})
    assert r.status_code == 201
    tid = r.json()["id"]
    assert len(client.get("/api/topics").json()) == 1
    assert client.get(f"/api/topics/{tid}/matches").json()["matches"] == []
    # subscriptions
    assert client.post("/api/subscriptions", json={"committee_name": "Bauausschuss"}).json()["subscribed"]
    assert "Bauausschuss" in client.get("/api/subscriptions").json()["subscriptions"]
    assert client.request("DELETE", "/api/subscriptions", json={"committee_name": "Bauausschuss"}).json()["unsubscribed"]
    # delete topic
    assert client.delete(f"/api/topics/{tid}").status_code == 204
    assert client.get("/api/topics").json() == []


def test_cannot_delete_foreign_topic(client):
    _register(client)
    _link("admin@test.de")
    assert client.delete("/api/topics/9999").status_code == 404


# ---- link endpoints ----
def test_link_request_and_status(client):
    _register(client)
    code = client.post("/api/link/request").json()
    assert len(code["code"]) == 6 and code["expires_in_minutes"] == 15
    assert client.get("/api/link/status").json()["linked"] is False
    _link("admin@test.de")
    assert client.get("/api/link/status").json()["linked"] is True
