"""Integration tests for the FastAPI backend (web/backend)."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Make the backend importable and point it at throwaway databases BEFORE import.
_BACKEND = Path(__file__).resolve().parents[1] / "web" / "backend"
sys.path.insert(0, str(_BACKEND))
_TMP = tempfile.mkdtemp()
os.environ["NWZ_DB"] = str(Path(_TMP) / "nwz.sqlite")
os.environ["COUNCIL_DB"] = str(Path(_TMP) / "council.sqlite")
os.environ["WEB_JWT_SECRET"] = "test-secret"
os.environ["WEB_ADMIN_EMAIL"] = "admin@test.de"
os.environ["COOKIE_SECURE"] = "false"  # TestClient uses http://testserver
os.environ["DISABLE_RATE_LIMIT"] = "1"  # avoid state bleeding across tests

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from nwz.store import Store  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from council.scraper import CouncilSession, AgendaItem  # noqa: E402

NWZ_DB = os.environ["NWZ_DB"]
COUNCIL_DB = os.environ["COUNCIL_DB"]


@pytest.fixture(autouse=True)
def fresh_dbs():
    for base in (NWZ_DB, COUNCIL_DB):
        for suffix in ("", "-wal", "-shm"):
            Path(base + suffix).unlink(missing_ok=True)
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
    assert r.json()["status"] == "active"
    assert r.json()["linked"] is False


def test_second_user_is_pending(client):
    _register(client)
    r = _register(client, email="bob@test.de")
    assert r.status_code == 201
    assert r.json()["role"] == "user"
    assert r.json()["status"] == "pending"


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


def test_activation_emails_user_on_approve(client):
    from types import SimpleNamespace
    _register(client)  # admin
    TestClient(app).post("/api/auth/register", json={"email": "bob@test.de", "password": "password123"})  # pending
    bob = next(u for u in client.get("/api/admin/users").json() if u["email"] == "bob@test.de")
    assert bob["status"] == "pending"

    sent = {}
    fake_settings = SimpleNamespace(resend_api_key="x", app_base_url="https://ratslotse.de",
                                    email_from="F <f@x.de>", feedback_email="", web_admin_email="admin@test.de")

    def fake_send(to, subject, html, **kw):
        sent.update(to=to, subject=subject)
        return "id"

    with patch("app.routers.admin.send_email", side_effect=fake_send), \
         patch("app.routers.admin.get_settings", return_value=fake_settings):
        r = client.put(f"/api/admin/users/{bob['id']}/status", json={"status": "active"})
    assert r.status_code == 200 and r.json()["status"] == "active"
    assert sent.get("to") == "bob@test.de"
    assert "freigeschaltet" in sent.get("subject", "").lower()

    # Re-saving 'active' (no transition) must NOT send a second mail.
    sent.clear()
    with patch("app.routers.admin.send_email", side_effect=fake_send), \
         patch("app.routers.admin.get_settings", return_value=fake_settings):
        client.put(f"/api/admin/users/{bob['id']}/status", json={"status": "active"})
    assert sent == {}


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


# ---- password reset + account deletion ----
def test_forgot_password_no_enumeration(client):
    _register(client)  # admin@test.de
    assert client.post("/api/auth/forgot-password", json={"email": "admin@test.de"}).status_code == 200
    # An unknown address gets the same 200 — no account enumeration.
    assert client.post("/api/auth/forgot-password", json={"email": "nobody@test.de"}).status_code == 200


def test_password_reset_flow(client):
    _register(client)
    with patch("app.routers.auth.secrets.token_urlsafe", return_value="known-token"):
        assert client.post("/api/auth/forgot-password", json={"email": "admin@test.de"}).status_code == 200
    assert client.post("/api/auth/reset-password",
                       json={"token": "known-token", "new_password": "newpass12345"}).status_code == 200
    fresh = TestClient(app)
    assert fresh.post("/api/auth/login", json={"email": "admin@test.de", "password": "newpass12345"}).status_code == 200
    assert fresh.post("/api/auth/login", json={"email": "admin@test.de", "password": "password123"}).status_code == 401


def test_reset_password_invalid_token(client):
    _register(client)
    assert client.post("/api/auth/reset-password",
                       json={"token": "bogus", "new_password": "whatever12345"}).status_code == 400


def test_reset_token_single_use(client):
    _register(client)
    with patch("app.routers.auth.secrets.token_urlsafe", return_value="once-token"):
        client.post("/api/auth/forgot-password", json={"email": "admin@test.de"})
    assert client.post("/api/auth/reset-password",
                       json={"token": "once-token", "new_password": "newpass12345"}).status_code == 200
    assert client.post("/api/auth/reset-password",
                       json={"token": "once-token", "new_password": "another12345"}).status_code == 400


def test_delete_account(client):
    _register(client)  # admin@test.de
    client.post("/api/topics", json={"name": "X", "description": "Testthema zum Mitlöschen."})
    assert client.delete("/api/account").status_code == 204
    # Account + data are gone — a fresh login fails.
    fresh = TestClient(app)
    assert fresh.post("/api/auth/login", json={"email": "admin@test.de", "password": "password123"}).status_code == 401


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


def test_field_recaps_endpoint(client):
    """Field recaps surface via /council/field-recaps with the German label resolved."""
    _register(client)
    cs = CouncilStore(COUNCIL_DB)
    cs.save_field_recap("verkehr", "Der Rat hat zuletzt mehrere Radwege beschlossen.", 12,
                        "2026-01-10", "2026-06-01", "2026-06-26T00:00:00")
    cs.close()
    data = client.get("/api/council/field-recaps").json()["recaps"]
    assert len(data) == 1
    assert data[0]["policy_field"] == "verkehr"
    assert data[0]["field_label"] == "Verkehr & Mobilität"
    assert data[0]["n_decisions"] == 12 and "Radwege" in data[0]["summary"]


def test_recaps_render_items_falls_back_to_beschluss():
    """_render_items uses summary when present, else the raw beschluss, and keeps the outcome."""
    from council.recaps import _render_items
    out = _render_items([
        {"session_date": "2026-06-01", "title": "Radweg Haarenufer", "summary": "Ausbau beschlossen", "outcome": "angenommen"},
        {"session_date": "2026-05-01", "title": "Brücke Y", "beschluss": "Sanierung wird beauftragt", "outcome": "abgelehnt"},
    ])
    assert "Radweg Haarenufer — Ausbau beschlossen" in out
    assert "Brücke Y — Sanierung wird beauftragt" in out  # falls back to beschluss
    assert "[abgelehnt]" in out


# ---- topics (owned by the web account, no Telegram link required) ----
def test_topics_work_without_telegram_link(client):
    _register(client)
    assert client.get("/api/topics").status_code == 200
    assert client.get("/api/topics").json() == []
    r = client.post("/api/topics", json={"name": "Radwege", "description": "Ausbau in Oldenburg"})
    assert r.status_code == 201
    assert len(client.get("/api/topics").json()) == 1


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


def test_topic_decision_matching(client):
    """A topic surfaces its semantically matched council decisions (decision_count + /decisions)."""
    owner_id = _register(client).json()["id"]
    tid = client.post("/api/topics", json={"name": "Radverkehr", "description": "Radwege in Oldenburg"}).json()["id"]

    # Seed a council decision (session + decision) — the offline matcher would store the link below.
    cs = CouncilStore(COUNCIL_DB)
    cs.save_session(CouncilSession(77, "Verkehrsausschuss", "2026-03-01", "18:00", "Rathaus",
                                   agenda_items=[AgendaItem("Ö 1", "Radweg Haarenufer")]))
    cs._insert_decision(77, 0, "decision", None, "1", "Radweg Haarenufer ausbauen",
                        "Beschluss", "angenommen", None, None, None, [], None, None, None)
    cs._conn.commit()
    did = cs._conn.execute("SELECT id FROM council_decisions WHERE ksinr = 77").fetchone()[0]
    cs.close()

    st = Store(NWZ_DB)
    assert st.save_topic_decision_matches(tid, owner_id, [(did, 0.81)]) == 1
    assert st.topic_decision_counts(owner_id) == {tid: 1}
    st.close()

    # decision_count surfaces in the topic list…
    topic = next(t for t in client.get("/api/topics").json() if t["id"] == tid)
    assert topic["decision_count"] == 1
    # …and the decisions endpoint joins to the council store (title, committee, score).
    decisions = client.get(f"/api/topics/{tid}/decisions").json()["decisions"]
    assert len(decisions) == 1
    assert decisions[0]["title"] == "Radweg Haarenufer ausbauen"
    assert decisions[0]["committee"] == "Verkehrsausschuss"
    assert round(decisions[0]["score"], 2) == 0.81


def test_topic_decisions_replace_on_rerun(client):
    """Re-running the matcher replaces a topic's matches (no stale duplicates)."""
    owner_id = _register(client).json()["id"]
    tid = client.post("/api/topics", json={"name": "X", "description": "y"}).json()["id"]
    st = Store(NWZ_DB)
    st.save_topic_decision_matches(tid, owner_id, [(1, 0.7), (2, 0.6)])
    st.save_topic_decision_matches(tid, owner_id, [(2, 0.9)])  # rerun → replaces
    assert [m["decision_id"] for m in st.get_topic_decision_matches(tid)] == [2]
    assert st.topic_decision_counts(owner_id) == {tid: 1}
    st.close()


def test_cannot_delete_foreign_topic(client):
    _register(client)
    _link("admin@test.de")
    assert client.delete("/api/topics/9999").status_code == 404


# ---- admin approval flow ----
def test_pending_user_blocked_until_approved(client):
    _register(client)  # admin
    bob = TestClient(app)
    bob.post("/api/auth/register", json={"email": "bob@test.de", "password": "password123"})
    # pending bob cannot use active-gated endpoints
    assert bob.get("/api/council/sessions").status_code == 403
    assert bob.get("/api/link/status").status_code == 403
    # admin approves
    users = client.get("/api/admin/users").json()
    bob_id = next(u["id"] for u in users if u["email"] == "bob@test.de")
    r = client.put(f"/api/admin/users/{bob_id}/status", json={"status": "active"})
    assert r.status_code == 200 and r.json()["status"] == "active"
    # now bob has access
    assert bob.get("/api/council/sessions").status_code == 200


def test_admin_cannot_suspend_self(client):
    _register(client)
    me = client.get("/api/auth/me").json()
    r = client.put(f"/api/admin/users/{me['id']}/status", json={"status": "pending"})
    assert r.status_code == 400


def test_admin_users_list_includes_status(client):
    _register(client)
    users = client.get("/api/admin/users").json()
    assert users[0]["status"] == "active"
    assert "nwz_fulltext_allowed" in users[0]


# ---- account: change password ----
def test_change_password_success(client):
    _register(client)
    r = client.post(
        "/api/account/change-password",
        json={"current_password": "password123", "new_password": "newpassword456"},
    )
    assert r.status_code == 200
    # Old cookie still valid in this request (re-issued), but old password should fail login
    fresh = TestClient(app)
    assert fresh.post("/api/auth/login", json={"email": "admin@test.de", "password": "password123"}).status_code == 401
    assert fresh.post("/api/auth/login", json={"email": "admin@test.de", "password": "newpassword456"}).status_code == 200


def test_change_password_wrong_current(client):
    _register(client)
    r = client.post(
        "/api/account/change-password",
        json={"current_password": "wrong", "new_password": "newpassword456"},
    )
    assert r.status_code == 400


# ---- link endpoints ----
def test_link_request_and_status(client):
    _register(client)
    code = client.post("/api/link/request").json()
    assert len(code["code"]) == 6 and code["expires_in_minutes"] == 15
    assert client.get("/api/link/status").json()["linked"] is False
    _link("admin@test.de")
    assert client.get("/api/link/status").json()["linked"] is True


# ---- feedback ----
def test_feedback_sends_email(client):
    from types import SimpleNamespace
    _register(client)  # admin@test.de
    sent = {}

    def fake_send(to, subject, html, **kw):
        sent.update(to=to, subject=subject, reply_to=kw.get("reply_to"), text=kw.get("text"))
        return "msg-id"

    fake_settings = SimpleNamespace(
        resend_api_key="x", feedback_email="ops@test.de",
        web_admin_email="admin@test.de", email_from="Ratslotse <f@x.de>")
    with patch("app.routers.feedback.send_email", side_effect=fake_send), \
         patch("app.routers.feedback.get_settings", return_value=fake_settings):
        r = client.post("/api/feedback", json={"kind": "feature", "message": "Bitte Dark Mode für die Karte"})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert sent["to"] == "ops@test.de"
    assert sent["reply_to"] == "admin@test.de"          # operator can reply straight to the user
    assert "Feature-Vorschlag" in sent["subject"]
    assert "Dark Mode" in sent["text"]


def test_feedback_validation(client):
    _register(client)
    assert client.post("/api/feedback", json={"kind": "nope", "message": "hallo welt"}).status_code == 422
    assert client.post("/api/feedback", json={"kind": "bug", "message": "x"}).status_code == 422  # too short


def test_feedback_ok_without_email_config(client):
    """No Resend key / recipient → still returns ok (best-effort), no error to the user."""
    from types import SimpleNamespace
    _register(client)
    fake = SimpleNamespace(resend_api_key="", feedback_email="", web_admin_email="", email_from="")
    with patch("app.routers.feedback.get_settings", return_value=fake):
        r = client.post("/api/feedback", json={"kind": "other", "message": "Test ohne Mail-Config"})
    assert r.status_code == 200 and r.json()["ok"] is True


# ---- email verification ----
import hashlib  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402


def test_register_marks_verified_without_email_config(client):
    """With no Resend key configured we can't send a link, so accounts are created
    already-verified — otherwise they could never be confirmed."""
    _register(client)  # admin
    r = _register(client, email="bob@test.de")
    assert r.status_code == 201
    assert r.json()["email_verified"] is True


def test_verify_email_endpoint(client):
    _register(client)  # admin
    _register(client, email="bob@test.de")
    store = Store(NWZ_DB)
    uid = store.get_web_user_by_email("bob@test.de")["id"]
    store.set_email_verified(uid, False)  # pretend the link was sent, not yet clicked
    raw = "verify-token-123"
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    exp = (datetime.utcnow() + timedelta(hours=1)).isoformat(timespec="seconds")
    store.create_email_verification(uid, token_hash, exp)
    store.close()

    # bad token rejected
    assert client.post("/api/auth/verify-email", json={"token": "nope"}).status_code == 400
    # valid token verifies the address
    r = client.post("/api/auth/verify-email", json={"token": raw})
    assert r.status_code == 200 and r.json()["email_verified"] is True
    store = Store(NWZ_DB)
    assert store.get_web_user_by_email("bob@test.de")["email_verified"] == 1
    store.close()
    # single-use: replaying the same token fails
    assert client.post("/api/auth/verify-email", json={"token": raw}).status_code == 400


def test_email_verification_token_expiry():
    store = Store(NWZ_DB)
    uid = store.create_web_user("exp@test.de", "h", "user", "pending", email_verified=False)
    token_hash = hashlib.sha256(b"expired").hexdigest()
    past = (datetime.utcnow() - timedelta(hours=1)).isoformat(timespec="seconds")
    store.create_email_verification(uid, token_hash, past)
    now = datetime.utcnow().isoformat(timespec="seconds")
    assert store.consume_email_verification(token_hash, now) is None
    store.close()


# ---- native app: bearer token + push notifications ----
def test_web_register_has_null_access_token(client):
    """Browser clients authenticate via the cookie — no token in the body."""
    r = _register(client)
    assert r.status_code == 201 and r.json()["access_token"] is None


def test_app_register_returns_bearer_token(client):
    """`X-Client: app` gets a JWT in the body that authenticates without a cookie."""
    r = _register(client, email="admin@test.de")
    assert r.status_code == 201  # ensure the account exists first
    # A fresh app client registers a *new* account and receives a token.
    app_client = TestClient(app)
    r2 = app_client.post(
        "/api/auth/register",
        json={"email": "appuser@test.de", "password": "password123"},
        headers={"X-Client": "app"},
    )
    token = r2.json()["access_token"]
    assert isinstance(token, str) and token
    # The token alone (no cookies) authenticates /me.
    bare = TestClient(app)
    me = bare.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200 and me.json()["email"] == "appuser@test.de"


def test_app_login_returns_bearer_token(client):
    _register(client)
    fresh = TestClient(app)
    withhdr = fresh.post("/api/auth/login",
                         json={"email": "admin@test.de", "password": "password123"},
                         headers={"X-Client": "app"})
    assert isinstance(withhdr.json()["access_token"], str) and withhdr.json()["access_token"]
    plain = fresh.post("/api/auth/login", json={"email": "admin@test.de", "password": "password123"})
    assert plain.json()["access_token"] is None


def test_app_flow_bearer_registers_push_device(client):
    """End-to-end app path: register (app) → bearer token → register a device token."""
    r = client.post("/api/auth/register",
                    json={"email": "admin@test.de", "password": "password123"},
                    headers={"X-Client": "app"})
    token = r.json()["access_token"]
    bearer = {"Authorization": f"Bearer {token}"}
    only_bearer = TestClient(app)  # no cookies

    assert only_bearer.post("/api/push/register",
                            json={"token": "dev-tok-1", "platform": "ios"},
                            headers=bearer).status_code == 204
    store = Store(NWZ_DB)
    uid = store.get_web_user_by_email("admin@test.de")["id"]
    assert [t["token"] for t in store.get_push_tokens_for_owner(uid)] == ["dev-tok-1"]
    store.close()

    assert only_bearer.post("/api/push/unregister",
                            json={"token": "dev-tok-1"}, headers=bearer).status_code == 204
    store = Store(NWZ_DB)
    assert store.get_push_tokens_for_owner(uid) == []
    store.close()


def test_push_register_requires_auth():
    assert TestClient(app).post(
        "/api/push/register", json={"token": "x", "platform": "ios"}
    ).status_code == 401


def test_push_register_validates_platform(client):
    _register(client)  # admin is active; client keeps the session cookie
    assert client.post("/api/push/register",
                       json={"token": "x", "platform": "windows"}).status_code == 422


def test_push_unregister_is_scoped_to_owner(client):
    """One account can't drop another's device token."""
    _register(client)  # admin (active), cookie on `client`
    assert client.post("/api/push/register",
                       json={"token": "adm-dev", "platform": "ios"}).status_code == 204
    # Register bob on a separate client so `client` keeps the admin session cookie
    # (TestClient persists Set-Cookie, so registering bob here would clobber it).
    bob = TestClient(app).post("/api/auth/register",
                               json={"email": "bob@test.de", "password": "password123"}).json()
    assert client.put(f"/api/admin/users/{bob['id']}/status",
                      json={"status": "active"}).status_code == 200
    bob_client = TestClient(app)
    bob_client.post("/api/auth/login", json={"email": "bob@test.de", "password": "password123"})
    # Bob's unregister of the admin's token is a no-op (still 204), token survives.
    assert bob_client.post("/api/push/unregister", json={"token": "adm-dev"}).status_code == 204
    store = Store(NWZ_DB)
    admin_uid = store.get_web_user_by_email("admin@test.de")["id"]
    assert [t["token"] for t in store.get_push_tokens_for_owner(admin_uid)] == ["adm-dev"]
    store.close()
