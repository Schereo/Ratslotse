"""Integration tests for the FastAPI backend (web/backend)."""
from __future__ import annotations

import json
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


# ---- auth ----
def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_register_first_user_is_admin(client):
    r = _register(client)
    assert r.status_code == 201
    assert r.json()["role"] == "admin"
    assert r.json()["status"] == "active"


def test_second_user_active_without_email_config(client):
    # Ohne RESEND_API_KEY kann kein Bestätigungslink verschickt werden — das
    # Konto ist sofort aktiv (statt unbestätigbar zu hängen). Mit E-Mail-Versand
    # startet es 'pending' bis zur Bestätigung (siehe Verify-Flow-Test).
    _register(client)
    r = _register(client, email="bob@test.de")
    assert r.status_code == 201
    assert r.json()["role"] == "user"
    assert r.json()["status"] == "active"


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
    assert r.status_code == 200 and len(r.json()) == 16
    key = "council_watcher_system"
    upd = client.put(f"/api/admin/prompts/{key}", json={"content": "Angepasster Watcher-Systemprompt."})
    assert upd.status_code == 200 and upd.json()["is_overridden"] is True
    # Design 21a: „geändert von … · wann“ wird mitgeführt.
    assert upd.json()["updated_by"] == "admin@test.de" and upd.json()["updated_at"]
    rst = client.post(f"/api/admin/prompts/{key}/reset")
    assert rst.json()["is_overridden"] is False


def test_admin_quiz_stats(client):
    """Design 21a: Quiz-Kennzahlen + Gebiets-Warnung (leere DB → Nullen)."""
    _register(client)
    r = client.get("/api/admin/quiz/stats")
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"fragen_aktiv", "avg_accuracy", "gemeldet", "gebiete_niedrig"}
    assert body["fragen_aktiv"] == 0 and body["gebiete_niedrig"] == []


def test_admin_stats_growth(client):
    """Design 20a: Wachstums-Verläufe + WAU (record_activity via Login) + Import."""
    _register(client)  # Admin-Registrierung + folgende Requests schreiben Aktivität
    client.get("/api/auth/me")
    r = client.get("/api/admin/stats/growth?range=90d")
    assert r.status_code == 200
    b = r.json()
    assert b["users"]["total"] >= 1
    assert isinstance(b["users"]["series"], list) and b["users"]["series"][-1] >= 1
    # Admin war in dieser Woche aktiv → letzter WAU-Balken ≥ 1.
    assert b["wau"][-1] >= 1
    assert "decisions_with_ki" in b["council"] and "last_fetch" in b["council"]
    # Scraper-Puls und neueste Tagesordnung sind getrennte Angaben: in der
    # sitzungsfreien Zeit läuft der Scraper weiter, ohne Sitzungen zu schreiben.
    assert {"last_session_import", "next_session"} <= set(b["council"])
    # x-Achse: ein Datum je Punkt, jüngster Punkt = heute (Serverdatum).
    from datetime import date
    heute = date.today().isoformat()
    assert len(b["users"]["days"]) == len(b["users"]["series"]) == 90
    assert b["users"]["days"][-1] == heute
    assert len(b["topics"]["days"]) == len(b["topics"]["series"])
    assert len(b["wau_days"]) == len(b["wau"]) == 8
    assert b["wau_days"][-1] == heute


def test_admin_jobs_listet_registry_auch_ohne_laeufe(client):
    """Die Cron-Übersicht zeigt jeden Job der Registry — ein Job, der noch nie
    lief (oder gar nicht mehr startet), muss sichtbar sein und nicht fehlen."""
    _register(client)
    b = client.get("/api/admin/jobs").json()
    assert {j["key"] for j in b} == {
        "check_council", "check_committees", "check_protocols", "weekly_enrich", "backup_db",
    }
    job = next(j for j in b if j["key"] == "check_council")
    assert job["state"] == "unknown" and job["last"] is None and job["history"] == []
    assert job["schedule"] and job["label"]


def test_admin_jobs_zeigt_letzten_lauf(client):
    """Kennzahlen und Alter des letzten Laufs landen in der Übersicht; ein
    frischer Lauf steht auf „ok“, ein zu alter auf „stale“ (Backup: 30 h)."""
    from datetime import datetime, timedelta

    _register(client)
    store = Store(NWZ_DB)
    frisch = datetime.utcnow() - timedelta(hours=2)
    store.record_job_run(
        "backup_db", frisch.isoformat(timespec="seconds"),
        (frisch + timedelta(seconds=12)).isoformat(timespec="seconds"),
        "ok", 12.0, {"Datenbanken gesichert": 2}, None)
    alt = datetime.utcnow() - timedelta(days=5)
    store.record_job_run(
        "weekly_enrich", alt.isoformat(timespec="seconds"),
        alt.isoformat(timespec="seconds"), "error", 3.0, None, "RuntimeError: Schritt fehlgeschlagen")
    store.close()

    b = client.get("/api/admin/jobs").json()
    backup = next(j for j in b if j["key"] == "backup_db")
    assert backup["state"] == "ok"
    assert backup["last"]["stats"] == {"Datenbanken gesichert": 2}
    assert backup["last"]["duration_s"] == 12.0
    assert 1.5 < backup["age_h"] < 2.5
    assert len(backup["history"]) == 1

    # Fehlerlauf schlägt auf den Zustand durch, auch wenn er im Takt liegt.
    weekly = next(j for j in b if j["key"] == "weekly_enrich")
    assert weekly["state"] == "error"
    assert "Schritt fehlgeschlagen" in weekly["last"]["error"]


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


def test_admin_user_rows_and_detail(client):
    """Design 20a: Nutzer-Liste mit Signalen + Detail (Features, 30-T-Verlauf)."""
    _register(client)  # admin; folgender /me-Request schreibt Aktivität
    admin = client.get("/api/auth/me").json()
    rows = client.get("/api/admin/users").json()
    me = next(u for u in rows if u["id"] == admin["id"])
    assert {"n_topics", "n_ki", "n_quiz", "last_seen"} <= set(me)
    assert me["last_seen"] is not None  # via record_activity beim Login
    detail = client.get(f"/api/admin/users/{admin['id']}").json()
    assert detail["email"] == admin["email"]
    assert set(detail["features"]) == {"ki_frage", "suche", "quiz", "analyse", "karte"}
    assert isinstance(detail["verlauf"], list) and len(detail["verlauf"]) == 30
    # 30-Tage-Achse passt zu den Balken und endet heute.
    from datetime import date
    assert len(detail["verlauf_days"]) == 30
    assert detail["verlauf_days"][-1] == date.today().isoformat()
    assert client.get("/api/admin/users/999999").status_code == 404


def test_activation_emails_user_on_approve(client):
    """Entsperren (pending→active) durch den Admin verschickt die Freischalt-Mail —
    der letzte verbliebene manuelle Übergang, seit Konten sich per E-Mail-
    Bestätigung selbst aktivieren."""
    from types import SimpleNamespace
    _register(client)  # admin
    TestClient(app).post("/api/auth/register", json={"email": "bob@test.de", "password": "password123"})  # aktiv (kein Mail-Versand konfiguriert)
    bob = next(u for u in client.get("/api/admin/users").json() if u["email"] == "bob@test.de")
    assert bob["status"] == "active"
    # Admin sperrt bob — damit es wieder einen pending→active-Übergang gibt.
    r = client.put(f"/api/admin/users/{bob['id']}/status", json={"status": "pending"})
    assert r.status_code == 200 and r.json()["status"] == "pending"

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


def test_delete_account_requires_password(client):
    _register(client)  # admin@test.de
    client.post("/api/topics", json={"name": "X", "description": "Testthema zum Mitlöschen."})
    # Ohne bzw. mit falschem Passwort bleibt das Konto bestehen.
    assert client.request("DELETE", "/api/account").status_code == 422
    r = client.request("DELETE", "/api/account", json={"current_password": "falsches-passwort"})
    assert r.status_code == 400
    assert client.get("/api/auth/me").status_code == 200
    # Mit korrektem Passwort: weg.
    assert client.request(
        "DELETE", "/api/account", json={"current_password": "password123"}
    ).status_code == 204
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


def test_sessions_carry_my_topic_items(client):
    """RL-902: Tagesordnungs-Treffer der eigenen Themen hängen an der Sitzung —
    und nur an der eigenen (fremde Owner-Treffer bleiben unsichtbar)."""
    from datetime import date, timedelta

    _register(client)  # admin, owner_id 1
    future = (date.today() + timedelta(days=3)).isoformat()
    cs = CouncilStore(COUNCIL_DB)
    cs.save_session(CouncilSession(800, "Verkehrsausschuss", future, "17:00", "Fleiwa",
                                   agenda_items=[AgendaItem("Ö 2", "Radweg Hauptstraße")]))
    cs.save_session(CouncilSession(801, "Kulturausschuss", future, "17:00", "PFL",
                                   agenda_items=[AgendaItem("Ö 1", "Museumskonzept")]))
    cs.close()

    store = Store(NWZ_DB)
    topic = store.add_topic(1, "Radwege", "Ausbau von Radwegen")
    store.replace_agenda_matches(1, 800, "h", {topic.id: ["Ö 2"]})
    # Treffer eines anderen Owners auf derselben Sitzung: darf nicht auftauchen.
    other = store.add_topic(2, "Museen", "Kultur")
    store.replace_agenda_matches(2, 801, "h", {other.id: ["Ö 1"]})
    store.close()

    rows = client.get("/api/council/sessions?scope=upcoming").json()["sessions"]
    by_id = {r["ksinr"]: r for r in rows}
    assert by_id[800]["my_topic_items"] == [{"item_number": "Ö 2", "topic_name": "Radwege"}]
    assert "my_topic_items" not in by_id[801]


def test_decision_detail_includes_vorlage(client):
    """Der Beschluss liefert den eingelesenen Vorlagen-Auszug mit — und die
    vorlage_url wird über unsere Tabelle aufgelöst (Protokolle kennen kein kvonr)."""
    _register(client)
    cs = CouncilStore(COUNCIL_DB)
    cs.save_session(CouncilSession(88, "Rat der Stadt", "2026-02-01", "18:00", "Rathaus",
                                   agenda_items=[AgendaItem("Ö 2", "Radweg", vorlage_nr="26/0400", kvonr=901)]))
    cs._insert_decision(88, 0, "decision", None, "Ö 2", "Radweg bauen", "Wird gebaut.",
                        "angenommen", None, None, None, [], "26/0400", None, None)
    cs._conn.commit()
    did = cs._conn.execute("SELECT id FROM council_decisions WHERE ksinr = 88").fetchone()[0]
    cs.save_vorlage({"kvonr": 901, "vorlage_nr": "26/0400", "title": "Radweg", "art": "Beschlussvorlage",
                     "document_id": 12, "document_url": "https://buergerinfo.oldenburg.de/getfile.php?id=12",
                     "raw_text": "Sachverhalt:\nDie Stadt plant einen Radweg entlang der Haaren.",
                     "n_pages": 3, "status": "ok"})
    cs.close()
    data = client.get(f"/api/council/decision/{did}").json()
    assert data["vorlage"]["art"] == "Beschlussvorlage"
    assert "Radweg entlang der Haaren" in data["vorlage"]["excerpt"]
    assert "kvonr=901" in data["vorlage_url"]
    assert data["anlagen"] == []  # keine Anlagen geseedet → leere Liste, kein Fehlen


def test_decision_detail_lists_anlagen_and_analysis_has_antrag_stats(client):
    _register(client)
    cs = CouncilStore(COUNCIL_DB)
    cs.save_session(CouncilSession(89, "Rat der Stadt", "2026-03-01", "18:00", "Rathaus",
                                   agenda_items=[AgendaItem("Ö 3", "Lastenräder", vorlage_nr="26/0500", kvonr=902)]))
    cs._insert_decision(89, 0, "decision", None, "Ö 3", "Lastenräder fördern", "Wird gefördert.",
                        "angenommen", None, None, None, [], "26/0500", None, None)
    cs._conn.commit()
    did = cs._conn.execute("SELECT id FROM council_decisions WHERE ksinr = 89").fetchone()[0]
    cs.save_vorlage({"kvonr": 902, "vorlage_nr": "26/0500", "title": "Lastenräder", "art": "Beschlussvorlage",
                     "raw_text": "Sachverhalt: Förderung.", "n_pages": 2, "status": "ok"})
    cs.save_anlagen(902, [
        {"document_id": 77, "url": "https://x/77", "label": "Antrag der SPD-Fraktion vom 01.02.2026",
         "is_antrag": 1, "antragsteller": ["SPD"], "raw_text": "Wir beantragen…", "status": "ok"},
        {"document_id": 78, "url": "https://x/78", "label": "Anlage - Standortkarte", "status": "listed"},
    ])
    cs.close()
    data = client.get(f"/api/council/decision/{did}").json()
    assert [a["document_id"] for a in data["anlagen"]] == [77, 78]  # Antrag zuerst
    assert data["anlagen"][0]["antragsteller"] == ["SPD"]
    stats = client.get("/api/council/analysis").json()["antrag_stats"]
    assert {"party": "SPD", "n": 1, "angenommen": 1, "abgelehnt": 0} in stats["parties"]


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


# ---- topics (owned by the web account) ----
def test_topics_work_for_active_user(client):
    _register(client)
    assert client.get("/api/topics").status_code == 200
    assert client.get("/api/topics").json() == []
    r = client.post("/api/topics", json={"name": "Radwege", "description": "Ausbau in Oldenburg"})
    assert r.status_code == 201
    assert len(client.get("/api/topics").json()) == 1


def test_topics_and_subscriptions_flow(client):
    _register(client)
    # add topic
    r = client.post("/api/topics", json={"name": "Radwege", "description": "Ausbau in Oldenburg"})
    assert r.status_code == 201
    tid = r.json()["id"]
    assert len(client.get("/api/topics").json()) == 1
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
    assert client.delete("/api/topics/9999").status_code == 404


# ---- Aktivierung durch E-Mail-Bestätigung (keine Admin-Freischaltung) ----
def test_unverified_user_blocked_until_email_confirmed(client):
    """Mit konfiguriertem E-Mail-Versand: Registrieren → pending + gesperrt;
    der Klick auf den Bestätigungslink aktiviert das Konto automatisch."""
    import re
    from types import SimpleNamespace

    _register(client)  # admin belegt den Admin-Slot
    sent = {}
    fake_settings = SimpleNamespace(
        resend_api_key="x", app_base_url="https://ratslotse.de",
        email_from="F <f@x.de>", feedback_email="", web_admin_email="admin@test.de",
        cookie_secure=False, access_token_expire_minutes=60, nwz_db=str(NWZ_DB),
    )

    def fake_send(to, subject, html, **kw):
        sent.update(to=to, subject=subject, text=kw.get("text", ""))
        return "id"

    bob = TestClient(app)
    with patch("app.routers.auth.send_email", side_effect=fake_send), \
         patch("app.routers.auth.get_settings", return_value=fake_settings):
        r = bob.post("/api/auth/register", json={"email": "bob@test.de", "password": "password123"})
    assert r.status_code == 201 and r.json()["status"] == "pending"
    assert sent.get("to") == "bob@test.de"  # Bestätigungs-Mail ging raus

    # Unbestätigt = kein Zugriff auf aktive Endpunkte
    assert bob.get("/api/council/sessions").status_code == 403

    # Link aus der Mail einlösen → Konto ist aktiv, Admins bekommen eine FYI-Mail
    token = re.search(r"token=([\w~.-]+)", sent["text"]).group(1)
    sent.clear()
    with patch("app.routers.auth.send_email", side_effect=fake_send), \
         patch("app.routers.auth.get_settings", return_value=fake_settings):
        v = bob.post("/api/auth/verify-email", json={"token": token})
    assert v.status_code == 200
    assert v.json()["status"] == "active" and v.json()["email_verified"] is True
    assert sent.get("to") == "admin@test.de"  # FYI an Admin, kein To-do

    # Jetzt hat bob Zugriff — ganz ohne Admin-Freischaltung
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


# ---- onboarding (serverseitiger Kurs-Fortschritt) ----
def test_onboarding_requires_auth():
    assert TestClient(app).get("/api/onboarding").status_code == 401


def test_onboarding_starts_empty(client):
    _register(client)
    assert client.get("/api/onboarding").json() == {"steps": [], "celebrated": False}


def test_onboarding_merges_steps_idempotently(client):
    _register(client)
    r = client.post("/api/onboarding", json={"steps": ["frag", "analyse"]})
    assert r.status_code == 200 and set(r.json()["steps"]) == {"frag", "analyse"}
    # Doppelt melden ändert nichts, neue Schritte kommen dazu.
    r = client.post("/api/onboarding", json={"steps": ["frag", "karten"]})
    assert set(r.json()["steps"]) == {"frag", "analyse", "karten"}
    assert r.json()["celebrated"] is False


def test_onboarding_filters_unknown_steps(client):
    _register(client)
    r = client.post("/api/onboarding", json={"steps": ["frag", "hacken", "<script>"]})
    assert r.json()["steps"] == ["frag"]


def test_onboarding_celebrated_persists(client):
    _register(client)
    client.post("/api/onboarding", json={"steps": ["frag"], "celebrated": True})
    got = client.get("/api/onboarding").json()
    assert got["celebrated"] is True and got["steps"] == ["frag"]


def test_onboarding_is_per_account(client):
    _register(client)
    client.post("/api/onboarding", json={"steps": ["frag"]})
    other = TestClient(app)
    _register(other, email="bob@test.de")
    assert other.get("/api/onboarding").json() == {"steps": [], "celebrated": False}


# ---- quiz ----
def _seed_quiz(area_key="Osternburg", area_type="stadtteil", n=3, category="geschichte",
               difficulty="mittel"):
    """Seed n Quizfragen für ein Gebiet in die (throwaway) council.sqlite."""
    from council import quiz as quizmod
    store = CouncilStore(COUNCIL_DB)
    rows = []
    for i in range(n):
        text = f"Testfrage {category} {i} zu {area_key}?"  # je Kategorie eindeutig (Dedup)
        rows.append({
            "area_type": area_type, "area_key": area_key, "category": category,
            "difficulty": difficulty, "question": text,
            "options": ["A", "B", "C", "D"], "correct_index": 1,
            "explanation": "weil B", "source_type": "wikipedia", "source_ref": "http://w",
            "content_hash": quizmod._content_hash(area_type, area_key, text),
        })
    store.save_quiz_questions(rows)
    store.close()


def _seed_estimate(area_key="Osternburg", value=12000.0, unit="Einwohner",
                   lo=2000.0, hi=30000.0, difficulty="mittel"):
    """Seed eine Schätzfrage (qtype=estimate) in die throwaway council.sqlite."""
    from council import quiz as quizmod
    store = CouncilStore(COUNCIL_DB)
    text = f"Schätzfrage {area_key} {value}?"
    store.save_quiz_questions([{
        "area_type": "stadtteil", "area_key": area_key, "category": "schaetzen",
        "difficulty": difficulty, "question": text, "qtype": "estimate",
        "options": [], "correct_index": 0,
        "answer_value": value, "answer_unit": unit, "range_min": lo, "range_max": hi,
        "explanation": "…", "source_type": "wikipedia", "source_ref": "http://w",
        "content_hash": quizmod._content_hash("stadtteil", area_key, text),
    }])
    store.close()


def test_quiz_requires_auth():
    assert TestClient(app).get("/api/quiz/areas").status_code == 401


def test_quiz_areas_lists_seeded(client):
    _register(client)
    _seed_quiz("Osternburg", n=3)  # Osternburg → Wahlbereich 5
    data = client.get("/api/quiz/areas").json()
    st = {a["key"]: a for a in data["stadtteile"]}
    assert st["Osternburg"]["questions"] == 3 and st["Osternburg"]["wahlbereiche"] == [5, 2]
    wb = {a["key"]: a for a in data["wahlbereiche"]}
    # Grenzstadtteil Osternburg wird in BEIDEN Wahlbereichen (5 und 2) gelistet
    for b in ("5", "2"):
        assert wb[b]["questions"] == 3 and "Osternburg" in wb[b]["stadtteile"]


def test_own_quiz_crud_round_and_practice(client):
    """RL-U14: Eigene Fragen — CRUD, Übungsrunde ohne Lösung, Antwort schreibt
    Zähler fort, aber KEINE Punkte/Statistik (Selbstbedienung ausgeschlossen)."""
    _register(client)
    body = {"question": "Wie viele Wahlbereiche hat Oldenburg?",
            "options": ["Vier", "Sechs", "Acht"], "correct_index": 1,
            "stadtteil": None, "category": "ratspolitik", "explanation": "Es sind sechs."}
    qid = client.post("/api/quiz/own", json=body).json()["id"]
    # Runde: geformt wie normale Fragen, ohne Lösung
    r = client.get("/api/quiz/own/round?n=5").json()["questions"]
    assert len(r) == 1 and r[0]["id"] == qid and "correct_index" not in r[0]
    assert r[0]["area_type"] == "eigene" and r[0]["area_key"] == "Stadtweit"
    # Richtig antworten: 0 Punkte, Zähler steigen, Statistik bleibt leer
    res = client.post("/api/quiz/own/answer", json={"question_id": qid, "selected_index": 1}).json()
    assert res["correct"] is True and res["points"] == 0 and res["correct_index"] == 1
    assert res["explanation"] == "Es sind sechs."
    mine = client.get("/api/quiz/own").json()["questions"][0]
    assert mine["practiced"] == 1 and mine["correct_count"] == 1
    assert client.get("/api/quiz/stats").json()["total"]["answered"] == 0
    # Bearbeiten setzt die Übungs-Zähler zurück
    client.put(f"/api/quiz/own/{qid}", json={**body, "question": "Wie viele Wahlbereiche hat die Stadt?"})
    mine = client.get("/api/quiz/own").json()["questions"][0]
    assert mine["practiced"] == 0 and mine["question"].endswith("die Stadt?")
    # Löschen
    assert client.delete(f"/api/quiz/own/{qid}").json()["ok"] is True
    assert client.get("/api/quiz/own").json()["questions"] == []


def test_own_quiz_is_per_account_and_validated(client):
    """Fremde Fragen sind unsichtbar/unantastbar; kaputte Eingaben werden abgelehnt."""
    _register(client)
    qid = client.post("/api/quiz/own", json={
        "question": "Nur meine Frage?", "options": ["Ja", "Nein"], "correct_index": 0,
        "category": "geschichte"}).json()["id"]
    other = TestClient(app)
    _register(other, email="other@test.de")
    assert other.get("/api/quiz/own").json()["questions"] == []
    assert other.put(f"/api/quiz/own/{qid}", json={
        "question": "Gekapert?", "options": ["A", "B"], "correct_index": 0,
        "category": "geschichte"}).status_code == 404
    assert other.delete(f"/api/quiz/own/{qid}").status_code == 404
    assert other.post("/api/quiz/own/answer",
                      json={"question_id": qid, "selected_index": 0}).status_code == 404
    # Validierung: richtige Antwort muss existieren, Kategorie/Stadtteil bekannt sein
    bad = {"question": "Kaputt genug?", "options": ["A", "B"], "correct_index": 3,
           "category": "geschichte"}
    assert client.post("/api/quiz/own", json=bad).status_code == 400
    assert client.post("/api/quiz/own", json={**bad, "correct_index": 0,
                                              "category": "quatsch"}).status_code == 400
    assert client.post("/api/quiz/own", json={**bad, "correct_index": 0,
                                              "stadtteil": "Atlantis"}).status_code == 400


def test_own_quiz_estimate(client):
    """RL-U14-Erweiterung: eigene Schätzfrage (category schaetzen) — Zahl statt
    Optionen, Auto-Slider-Bereich, Nähe-Wertung ohne Punkte."""
    _register(client)
    r = client.post("/api/quiz/own", json={
        "question": "Wie viele Einwohner hat Oldenburg?", "category": "schaetzen",
        "answer_value": 172000, "unit": "Einwohner"})
    assert r.status_code == 200
    qid = r.json()["id"]
    mine = client.get("/api/quiz/own").json()["questions"][0]
    assert mine["qtype"] == "estimate" and mine["answer_value"] == 172000
    assert mine["unit"] == "Einwohner"
    assert mine["range_min"] == 0 and mine["range_max"] == 340000  # 0 bis ~2×, gerundet
    # Runde: estimate-Felder da, aber die Lösung fehlt
    q = client.get("/api/quiz/own/round?n=5").json()["questions"][0]
    assert q["qtype"] == "estimate" and q["range_max"] == 340000 and "answer_value" not in q
    # nahe Schätzung (≤15 %) = richtig, 0 Punkte; die Lösung kommt jetzt zurück
    res = client.post("/api/quiz/own/answer", json={"question_id": qid, "value": 180000}).json()
    assert res["correct"] is True and res["points"] == 0 and res["answer_value"] == 172000
    assert client.post("/api/quiz/own/answer",
                       json={"question_id": qid, "value": 50000}).json()["correct"] is False
    # Zahl fehlt → 400; manueller Bereich, der die Zahl nicht umschließt → 400
    assert client.post("/api/quiz/own", json={
        "question": "Ohne Zahl?", "category": "schaetzen"}).status_code == 400
    assert client.post("/api/quiz/own", json={
        "question": "Bereich zu klein?", "category": "schaetzen", "answer_value": 100,
        "range_min": 0, "range_max": 50}).status_code == 400
    # Jahreszahl (Einheit Jahr) → enges, zentriertes ±50-Fenster statt 0..2×
    yid = client.post("/api/quiz/own", json={
        "question": "Wann wurde die Cäcilienbrücke gebaut?", "category": "schaetzen",
        "answer_value": 1927, "unit": "Jahr"}).json()["id"]
    yq = next(q for q in client.get("/api/quiz/own").json()["questions"] if q["id"] == yid)
    assert yq["range_min"] == 1877 and yq["range_max"] == 1977
    # Kleine „Jahre"-Dauer bleibt beim Standard-Bereich (0..2×)
    did = client.post("/api/quiz/own", json={
        "question": "Seit wie vielen Jahren gesperrt?", "category": "schaetzen",
        "answer_value": 6, "unit": "Jahre"}).json()["id"]
    dq = next(q for q in client.get("/api/quiz/own").json()["questions"] if q["id"] == did)
    assert dq["range_min"] == 0 and dq["range_max"] == 12


def test_quiz_theme_stadtteil_binding(client):
    """RL-U13: Themen mit Entity-Geo tragen ihren Stadtteil im Katalog
    (Punkt-in-Polygon); Themen ohne Geo gelten als stadtweit (null)."""
    _register(client)
    _seed_quiz("fliegerhorst", area_type="thema", n=1)
    _seed_quiz("haushalt", area_type="thema", n=1, category="ratspolitik")
    store = CouncilStore(COUNCIL_DB)
    store.save_entities([("fliegerhorst", "Fliegerhorst", "projekt", 5)], [])
    store.set_entity_geo("fliegerhorst", 53.1720, 8.1850, None)  # liegt im Stadtteil Fliegerhorst
    store.close()
    themen = {t["key"]: t for t in client.get("/api/quiz/areas").json()["themen"]}
    assert themen["fliegerhorst"]["stadtteil"] == "Fliegerhorst"
    assert themen["haushalt"]["stadtteil"] is None


def test_quiz_round_hides_answer(client):
    _register(client)
    _seed_quiz("Osternburg", n=3)
    q = client.get("/api/quiz/round?areas=stadtteil:Osternburg&n=2").json()["questions"]
    assert len(q) == 2
    for item in q:
        assert "correct_index" not in item and "explanation" not in item
        assert len(item["options"]) == 4


def test_quiz_wahlbereich_expands(client):
    _register(client)
    _seed_quiz("Osternburg", n=2)
    q = client.get("/api/quiz/round?areas=wahlbereich:5&n=10").json()["questions"]
    assert len(q) == 2  # Osternburg ist in Wahlbereich 5


def test_quiz_answer_scores_and_reveals(client):
    _register(client)
    _seed_quiz("Osternburg", n=1, difficulty="schwer")
    qid = client.get("/api/quiz/round?areas=stadtteil:Osternburg").json()["questions"][0]["id"]
    r = client.post("/api/quiz/answer", json={"question_id": qid, "selected_index": 1}).json()
    assert r["correct"] is True and r["points"] == 3 and r["correct_index"] == 1
    assert r["explanation"] == "weil B" and r["source_ref"] == "http://w"
    # zweite Frage falsch → 0 Punkte
    _seed_quiz("Osternburg", n=1, category="orte")
    qid2 = [x["id"] for x in client.get("/api/quiz/round?areas=stadtteil:Osternburg&n=10").json()["questions"]
            if x["id"] != qid][0]
    r2 = client.post("/api/quiz/answer", json={"question_id": qid2, "selected_index": 0}).json()
    assert r2["correct"] is False and r2["points"] == 0


def test_quiz_stats_aggregate_per_area(client):
    _register(client)
    _seed_quiz("Osternburg", n=2)
    for item in client.get("/api/quiz/round?areas=stadtteil:Osternburg&n=10").json()["questions"]:
        client.post("/api/quiz/answer", json={"question_id": item["id"], "selected_index": 1})
    stats = client.get("/api/quiz/stats").json()
    assert stats["total"]["answered"] == 2 and stats["total"]["correct"] == 2
    area = next(a for a in stats["by_area"] if a["area_key"] == "Osternburg")
    assert area["points"] == 4  # 2× mittel


def test_quiz_rating_and_admin_flag(client):
    _register(client)  # erster Nutzer = admin
    _seed_quiz("Osternburg", n=1)
    qid = client.get("/api/quiz/round?areas=stadtteil:Osternburg").json()["questions"][0]["id"]
    assert client.post("/api/quiz/rate", json={"question_id": qid, "verdict": "schlecht",
                                               "comment": "unklar"}).json()["ok"] is True
    flagged = client.get("/api/admin/quiz/flagged").json()["flagged"]
    entry = next(f for f in flagged if f["question_id"] == qid)
    assert entry["bad"] == 1 and entry["comments"] == "unklar"  # optionaler Grund kommt durch
    # ausmustern → fliegt aus den Runden UND aus der Bewertungs-Liste
    client.post(f"/api/admin/quiz/{qid}/retire")
    assert client.get("/api/quiz/round?areas=stadtteil:Osternburg&n=10").json()["questions"] == []
    flagged_after = client.get("/api/admin/quiz/flagged").json()["flagged"]
    assert all(f["question_id"] != qid for f in flagged_after)


def test_quiz_scores_per_account(client):
    _register(client)
    _seed_quiz("Osternburg", n=1)
    qid = client.get("/api/quiz/round?areas=stadtteil:Osternburg").json()["questions"][0]["id"]
    client.post("/api/quiz/answer", json={"question_id": qid, "selected_index": 1})
    bob = TestClient(app)
    _register(bob, email="bob@test.de")
    assert bob.get("/api/quiz/stats").json()["total"]["answered"] == 0


def test_quiz_review_collects_wrong_and_clears_on_correct(client):
    _register(client)
    _seed_quiz("Osternburg", n=2)
    qs = client.get("/api/quiz/round?areas=stadtteil:Osternburg&n=10").json()["questions"]
    client.post("/api/quiz/answer", json={"question_id": qs[0]["id"], "selected_index": 0})  # falsch
    client.post("/api/quiz/answer", json={"question_id": qs[1]["id"], "selected_index": 1})  # richtig
    review = client.get("/api/quiz/review").json()["questions"]
    ids = {q["id"] for q in review}
    assert qs[0]["id"] in ids and qs[1]["id"] not in ids
    for q in review:  # Wiederhol-Fragen kommen ohne Lösung
        assert "correct_index" not in q
    # später richtig → fliegt aus dem „Meine Fehler"-Stapel
    client.post("/api/quiz/answer", json={"question_id": qs[0]["id"], "selected_index": 1})
    assert client.get("/api/quiz/review").json()["questions"] == []


def test_quiz_daily_deterministic_and_completable(client):
    _register(client)
    _seed_quiz("Osternburg", n=8)
    d1 = client.get("/api/quiz/daily").json()
    assert d1["done"] is None and len(d1["questions"]) == 5
    d2 = client.get("/api/quiz/daily").json()  # gleicher Tag → gleicher Fragensatz
    assert {q["id"] for q in d1["questions"]} == {q["id"] for q in d2["questions"]}
    for q in d1["questions"]:
        client.post("/api/quiz/answer", json={"question_id": q["id"], "selected_index": 1})
    r = client.post("/api/quiz/daily/complete", json={"correct": 5, "total": 5, "points": 10}).json()
    assert r["ok"] is True and r["streak"] == 1
    after = client.get("/api/quiz/daily").json()
    assert after["done"]["correct"] == 5 and after["questions"] == []


def test_quiz_stats_streak_wrong_and_badges(client):
    _register(client)
    _seed_quiz("Osternburg", n=6)
    for q in client.get("/api/quiz/round?areas=stadtteil:Osternburg&n=10").json()["questions"]:
        client.post("/api/quiz/answer", json={"question_id": q["id"], "selected_index": 1})
    s = client.get("/api/quiz/stats").json()
    assert s["streak"] == 1 and s["wrong"] == 0 and s["daily_done"] is False
    assert "Osternburg-Kenner" in {b["label"] for b in s["badges"]}  # 6× richtig, 100 %


def test_quiz_estimate_slider_scores_by_proximity(client):
    _register(client)
    _seed_estimate("Osternburg", value=12000.0, difficulty="schwer")  # schwer = 3 Punkte
    q = client.get("/api/quiz/round?areas=stadtteil:Osternburg&n=5").json()["questions"][0]
    assert q["qtype"] == "estimate" and q["unit"] == "Einwohner"
    assert "answer_value" not in q and q["range_min"] == 2000 and q["range_max"] == 30000
    # exakt → volle Punkte
    r = client.post("/api/quiz/answer", json={"question_id": q["id"], "value": 12000}).json()
    assert r["correct"] is True and r["points"] == 3 and r["answer_value"] == 12000
    # ~8 % daneben → „nah dran", Teilpunkte, gilt als richtig (≤15 %)
    r2 = client.post("/api/quiz/answer", json={"question_id": q["id"], "value": 13000}).json()
    assert r2["correct"] is True and r2["points"] == 2
    # weit daneben → 0 Punkte, nicht richtig
    r3 = client.post("/api/quiz/answer", json={"question_id": q["id"], "value": 29000}).json()
    assert r3["correct"] is False and r3["points"] == 0


def test_quiz_map_round_and_answer(client):
    _register(client)
    r = client.get("/api/quiz/map-round?n=5").json()
    assert len(r["questions"]) == 5
    assert all(q["question"].startswith("Wo liegt") and q["target"] for q in r["questions"])
    # richtig verorten → 2 Punkte
    res = client.post("/api/quiz/map-answer", json={"target": "Osternburg", "clicked": "Osternburg"}).json()
    assert res["correct"] is True and res["points"] == 2 and res["target"] == "Osternburg"
    # daneben → 0 Punkte
    res2 = client.post("/api/quiz/map-answer", json={"target": "Eversten", "clicked": "Nadorst"}).json()
    assert res2["correct"] is False and res2["points"] == 0
    # unbekannter Stadtteil → 400
    assert client.post("/api/quiz/map-answer", json={"target": "Nirgendwo", "clicked": "X"}).status_code == 400
    # zählt auf den Stadtteil-Fortschritt, aber NICHT in den „Meine Fehler"-Stapel
    stats = client.get("/api/quiz/stats").json()
    assert stats["total"]["answered"] == 2 and stats["total"]["points"] == 2 and stats["wrong"] == 0
    assert client.get("/api/quiz/review").json()["questions"] == []


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


def test_app_verify_email_returns_bearer_token(client):
    """Verification opened via the app deep link should land logged-in: an
    `X-Client: app` verify-email gets a bearer token in the body."""
    _register(client)  # admin (active)
    store = Store(NWZ_DB)
    uid = store.get_web_user_by_email("admin@test.de")["id"]
    raw = "app-verify-token"
    exp = (datetime.utcnow() + timedelta(hours=1)).isoformat(timespec="seconds")
    store.create_email_verification(uid, hashlib.sha256(raw.encode()).hexdigest(), exp)
    store.close()

    r = TestClient(app).post("/api/auth/verify-email", json={"token": raw},
                             headers={"X-Client": "app"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert isinstance(token, str) and token
    me = TestClient(app).get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200 and me.json()["email_verified"] is True


def test_cors_preflight_allows_app_webview_origin():
    """The Capacitor WebView origins are allowed by default (no .env needed):
    the app's cross-origin fetches must pass the browser-engine CORS preflight."""
    r = TestClient(app).options(
        "/api/auth/login",
        headers={
            "Origin": "capacitor://localhost",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-client,authorization",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "capacitor://localhost"
    assert r.headers.get("access-control-allow-credentials") == "true"


# ---- Sign in with Apple (RL-1002) ----
# Fester 2048-Bit-Testschlüssel (einmalig generiert): Tests signieren offline
# mit d (rohes RSA + EMSA-PKCS1-v1_5) und verifizieren den echten Server-Pfad.
_APPLE_N = 23292286828442764542923602884886102634630497020832090681415031917426634371549872951421751307795427778020033652931020993785405435375266637207273733185696842723723840048137832838787830710633262144703248819350993993779228227453743549376464448895752816351732669088600171771119929681241653844721217855925336951865225156196245188319224141205571780669141197871229169819690144412769760049364020327712810906003818442349824989657315952737445834675548869097844110780042087383813509900808819964181099303049532117389667796862500006668640019356333002353762096910159235120646666152212943426307862094829091638720316652902437398576279
_APPLE_D = 8396304838160826570399906256831892391959170802274253113555539947407502993891694364112839522270062461538280437518789469577235923341364216712746056573317287348011258666359952880051621322662854594161189888654615829318360273730579130601710245707580640094931236414294745838332892545500914769589947834617210473767990321986882809738325610990822923049798951381050642443016109010102515956779964727875353799774535343954005978135626311423156307033222819749230405134914161061433073643877196888646681175713907414015748006720763829431077994615230357666001882914881594149582209038126726745498176910258773099475330879258754175280753
_APPLE_E = 65537


def _apple_token(sub="apple-sub-1", email="anna@example.com", aud="de.ratslotse.app",
                 exp_offset=3600, kid="testkid"):
    import hashlib
    import json
    import time as _time
    from app.security import _SHA256_DIGEST_INFO, _b64url_encode

    header = _b64url_encode(json.dumps({"alg": "RS256", "kid": kid}).encode())
    claims = {"iss": "https://appleid.apple.com", "aud": aud, "sub": sub,
              "exp": int(_time.time()) + exp_offset}
    if email:
        claims["email"] = email
    payload = _b64url_encode(json.dumps(claims).encode())
    msg = f"{header}.{payload}".encode()
    k = (_APPLE_N.bit_length() + 7) // 8
    em = (b"\x00\x01" + b"\xff" * (k - 3 - len(_SHA256_DIGEST_INFO) - 32) + b"\x00"
          + _SHA256_DIGEST_INFO + hashlib.sha256(msg).digest())
    sig = pow(int.from_bytes(em, "big"), _APPLE_D, _APPLE_N).to_bytes(k, "big")
    return f"{header}.{payload}." + _b64url_encode(sig)


@pytest.fixture
def apple_jwks(monkeypatch):
    from app.routers import auth_apple
    from app.security import _b64url_encode

    n_bytes = _APPLE_N.to_bytes((_APPLE_N.bit_length() + 7) // 8, "big")
    jwk = {"kty": "RSA", "kid": "testkid", "alg": "RS256",
           "n": _b64url_encode(n_bytes), "e": _b64url_encode(_APPLE_E.to_bytes(3, "big"))}
    monkeypatch.setattr(auth_apple, "_fetch_jwks", lambda: [jwk])
    auth_apple._JWKS_CACHE.update(at=0.0, keys=[])
    yield


def test_apple_login_creates_active_account(client, apple_jwks):
    _register(client)  # Admin existiert → Apple-Konto wird normale:r Nutzer:in
    anna = TestClient(app)
    r = anna.post("/api/auth/apple", json={"identity_token": _apple_token()})
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "anna@example.com"
    assert body["status"] == "active" and body["email_verified"] is True
    assert body["apple_linked"] is True and body["has_password"] is False
    # Wiederholte Anmeldung (gleiche sub, diesmal ohne email-Claim) → gleiches Konto.
    r2 = anna.post("/api/auth/apple", json={"identity_token": _apple_token(email=None)})
    assert r2.status_code == 200 and r2.json()["id"] == body["id"]


def test_apple_login_links_existing_account_by_email(client, apple_jwks):
    _register(client)  # admin@test.de
    r = client.post("/api/auth/apple",
                    json={"identity_token": _apple_token(sub="sub-admin", email="admin@test.de")})
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "admin@test.de"
    assert body["apple_linked"] is True and body["has_password"] is True


def test_apple_login_rejects_foreign_audience_and_bad_signature(client, apple_jwks):
    bad_aud = _apple_token(aud="com.evil.app")
    assert client.post("/api/auth/apple", json={"identity_token": bad_aud}).status_code == 401
    tampered = _apple_token() + "x"
    assert client.post("/api/auth/apple", json={"identity_token": tampered}).status_code == 401
    expired = _apple_token(exp_offset=-60)
    assert client.post("/api/auth/apple", json={"identity_token": expired}).status_code == 401


def test_apple_only_account_deletes_via_apple_reauth(client, apple_jwks):
    _register(client)
    anna = TestClient(app)
    anna.post("/api/auth/apple", json={"identity_token": _apple_token(sub="sub-del", email="del@example.com")})
    # Ohne Passwort und ohne Apple-Token: klare Fehlermeldung.
    r = anna.request("DELETE", "/api/account", json={"current_password": ""})
    assert r.status_code == 400 and "Apple" in r.json()["detail"]
    # Fremde sub im Re-Auth-Token wird abgelehnt.
    r = anna.request("DELETE", "/api/account",
                     json={"apple_identity_token": _apple_token(sub="other-sub", email=None)})
    assert r.status_code == 400
    # Frisches Token derselben sub löscht das Konto.
    r = anna.request("DELETE", "/api/account",
                     json={"apple_identity_token": _apple_token(sub="sub-del", email=None)})
    assert r.status_code == 204
    store = Store(NWZ_DB)
    assert store.get_web_user_by_email("del@example.com") is None
    store.close()


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


# ---- Lotsen-Abzeichen (RL-U12) ----
def test_badges_events_and_newly_earned_once(client):
    _register(client)
    data = client.get("/api/badges").json()
    assert data["total"] == 8 and data["earned_count"] == 0 and data["newly_earned"] == []
    assert data["next"]["id"] == "erste-frage"

    client.post("/api/badges/event", json={"type": "sitzung"})
    data = client.get("/api/badges").json()
    assert {b["id"]: b["earned"] for b in data["badges"]}["sitzungsgast"] is True
    assert [n["id"] for n in data["newly_earned"]] == ["sitzungsgast"]
    # newly_earned kommt genau einmal — danach ist es persistiert.
    assert client.get("/api/badges").json()["newly_earned"] == []
    # Unbekannte Events werden still verworfen.
    assert client.post("/api/badges/event", json={"type": "quatsch"}).status_code == 200


def test_badges_kartograf_distinct_and_derived(client):
    _register(client)
    for key in ["fliegerhorst", "fliegerhorst", "bahnhof"]:
        client.post("/api/badges/event", json={"type": "map_place", "key": key})
    karto = next(b for b in client.get("/api/badges").json()["badges"] if b["id"] == "kartograf")
    assert karto["earned"] is False and karto["progress"] == {"current": 2, "target": 3}

    client.post("/api/badges/event", json={"type": "map_place", "key": "hafen"})
    data = client.get("/api/badges").json()
    karto = next(b for b in data["badges"] if b["id"] == "kartograf")
    assert karto["earned"] is True

    # Server-abgeleitet (Frühwarner): Push-Gerät registriert → verdient beim
    # nächsten GET — und bleibt verdient, auch wenn das Gerät wieder geht.
    store = Store(Path(NWZ_DB))
    store.add_push_token(1, "tok-1", "ios")
    assert {b["id"]: b["earned"] for b in client.get("/api/badges").json()["badges"]}["fruehwarner"] is True
    store.remove_push_token("tok-1")
    assert {b["id"]: b["earned"] for b in client.get("/api/badges").json()["badges"]}["fruehwarner"] is True


def test_badges_are_per_account(client):
    _register(client)
    client.post("/api/badges/event", json={"type": "sitzung"})
    client.get("/api/badges")
    client.post("/api/auth/logout")
    _register(client, email="zweite@test.de")
    data = client.get("/api/badges").json()
    assert data["earned_count"] == 0


# ---- Anzeigename ----
def test_display_name_register_change_and_greeting(client):
    r = client.post("/api/auth/register",
                    json={"email": "tim@test.de", "password": "password123", "display_name": "  Tim  "})
    assert r.status_code == 201 and r.json()["display_name"] == "Tim"

    client.post("/api/account/display-name", json={"display_name": "Timo"})
    assert client.get("/api/auth/me").json()["display_name"] == "Timo"
    # Leeren = Ansprache wieder neutral.
    client.post("/api/account/display-name", json={"display_name": "  "})
    assert client.get("/api/auth/me").json()["display_name"] is None

    from nwz.digest_email import render_html_email
    assert "Moin Timo," in render_html_email("Betreff", "Inhalt", greeting_name="Timo")
    assert "Moin" not in render_html_email("Betreff", "Inhalt").split("Ratslotse")[1][:40]


def test_topic_suggestions_dedupe_similar(client):
    """Vorschläge: „Stadion …", „Stadionneubau …" und „Maastrichter Straße"
    sind EIN Interesse — nur der aktivste erscheint; ein angelegtes Thema
    blockt alle Varianten."""
    from datetime import date, timedelta
    _register(client)
    council = CouncilStore(Path(COUNCIL_DB))
    recent = (date.today() - timedelta(days=20)).isoformat()
    council.save_session(CouncilSession(1, "Rat", recent, "17:00", "Ratssaal"))
    with council._conn:
        for i in range(3):
            council._insert_decision(1, i, "decision", None, f"Ö {i}", f"D{i}", "B",
                                     "angenommen", None, None, None, [], None, None, None)
        ids = [r[0] for r in council._conn.execute(
            "SELECT id FROM council_decisions ORDER BY id").fetchall()]
        ents = [(1, "stadion-maastrichter", "Stadion Maastrichter Straße", "ort"),
                (2, "stadionneubau", "Stadionneubau Maastrichter Straße", "projekt"),
                (3, "maastrichter-strasse", "Maastrichter Straße", "ort"),
                (4, "stadtmuseum", "Stadtmuseum", "ort")]
        for eid, slug, name, kind in ents:
            council._conn.execute(
                "INSERT INTO council_entities (id, slug, name, kind, n) VALUES (?,?,?,?,3)",
                (eid, slug, name, kind))
        for eid, dids in [(1, ids[:3]), (2, ids[:2]), (3, ids[:2]), (4, ids[:2])]:
            for did in dids:
                council._conn.execute("INSERT INTO council_entity_links VALUES (?, ?)", (eid, did))
    council.close()

    names = [s["name"] for s in client.get("/api/topics/suggestions").json()["suggestions"]]
    assert names == ["Stadion Maastrichter Straße", "Stadtmuseum"]

    # Angelegtes Thema blockt auch alle ähnlichen Varianten.
    client.post("/api/topics", json={"name": "Stadionneubau Maastrichter Straße",
                                     "description": "Bau des Fußballstadions in Eversten."})
    names = [s["name"] for s in client.get("/api/topics/suggestions").json()["suggestions"]]
    assert names == ["Stadtmuseum"]


# ---- KI-Frage: Folgefragen im Stream (Design 24a) ----
def test_ask_stream_haelt_marker_zurueck_und_liefert_suggestions(client, monkeypatch):
    """Der Marker der Folgefragen darf NIE im Antworttext auftauchen — auch dann
    nicht, wenn er über mehrere Stream-Deltas verteilt ankommt. Stattdessen
    kommen die Vorschläge als eigenes suggestions-Event."""
    from app.routers import council as council_router
    from council import qa as qa_mod

    _register(client)
    cand = [{"id": 5, "title": "Radverkehrsplan 2026", "summary": "Ausbau",
             "policy_field": "verkehr", "outcome": "angenommen", "session_date": "2026-07-02",
             "committee": "Verkehrsausschuss", "score": 1.0, "gegenstimmen": 2}]
    monkeypatch.setattr(council_router, "_qa_retrieve", lambda *a, **k: (cand, "semantisch"))
    monkeypatch.setattr(qa_mod, "expand_query", lambda q, **k: q)
    # Marker bewusst über Delta-Grenzen zerschnitten ("FOLGE" | "FRAGEN:").
    deltas = ["Die Veloroute 4 ", "wird ausgebaut [5].\n", "FOLGE", "FRAGEN:",
              ' ["Wer stimmte dagegen?", "Was kostet der Ausbau?"]']
    monkeypatch.setattr(qa_mod, "answer_stream", lambda *a, **k: iter(deltas))

    with client.stream("POST", "/api/council/ask", json={"question": "Was ist mit Radwegen?"}) as r:
        assert r.status_code == 200
        body = "".join(r.iter_text())

    events = [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]
    answer = "".join(e["text"] for e in events if e["type"] == "token")
    assert "FOLGEFRAGEN" not in answer and "FOLGE" not in answer
    assert answer.strip() == "Die Veloroute 4 wird ausgebaut [5]."
    sugg = [e for e in events if e["type"] == "suggestions"]
    assert sugg and sugg[0]["questions"] == ["Wer stimmte dagegen?", "Was kostet der Ausbau?"]
    assert [e for e in events if e["type"] == "done"]


def test_ask_stream_faellt_auf_abgeleitete_fragen_zurueck(client, monkeypatch):
    """Liefert das Modell keine Vorschläge, leitet der Server sie deterministisch
    aus den gefundenen Beschlüssen ab (Variante B) — nie eine leere Leiste."""
    from app.routers import council as council_router
    from council import qa as qa_mod

    _register(client)
    cand = [{"id": 9, "title": "Sanierung Cäcilienbrücke — Kosten", "summary": "",
             "policy_field": "verkehr", "outcome": "angenommen", "session_date": "2026-06-01",
             "committee": "Verkehrsausschuss", "score": 1.0, "gegenstimmen": 4,
             "amount_eur": 1_000_000}]
    monkeypatch.setattr(council_router, "_qa_retrieve", lambda *a, **k: (cand, "semantisch"))
    monkeypatch.setattr(qa_mod, "expand_query", lambda q, **k: q)
    monkeypatch.setattr(qa_mod, "answer_stream", lambda *a, **k: iter(["Antwort ohne Vorschläge [9]."]))

    with client.stream("POST", "/api/council/ask", json={"question": "Was ist mit der Brücke?"}) as r:
        body = "".join(r.iter_text())
    events = [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]
    answer = "".join(e["text"] for e in events if e["type"] == "token")
    assert answer.strip() == "Antwort ohne Vorschläge [9]."
    sugg = [e for e in events if e["type"] == "suggestions"]
    assert sugg and sugg[0]["questions"][0] == "Wer stimmte gegen Sanierung Cäcilienbrücke?"


# ---- Themen-Seite: verwandte Themen ----
def test_entity_detail_liefert_verwandte_themen(client):
    _register(client)
    store = CouncilStore(COUNCIL_DB)
    store._conn.executemany(
        "INSERT INTO council_entities(id, slug, name, kind, n) VALUES (?,?,?,?,?)",
        [(1, "fliegerhorst", "Fliegerhorst", "ort", 158),
         (2, "entlastungsstrasse", "Entlastungsstraße", "ort", 40),
         (3, "brookweg", "Brookweg", "ort", 5)])
    store._conn.commit()
    store.save_entity_relations([
        ("fliegerhorst", "entlastungsstrasse", "belegt", 0, 0.13, 22),
        ("fliegerhorst", "brookweg", "aehnlich", 1, 0.72, 0)])
    store.close()

    r = client.get("/api/council/entity/fliegerhorst")
    assert r.status_code == 200
    related = r.json()["related"]
    assert [x["name"] for x in related] == ["Entlastungsstraße", "Brookweg"]
    # Belegte zuerst, mit Belegzahl — die UI trennt danach die beiden Zeilen.
    assert related[0]["rel_type"] == "belegt" and related[0]["evidence"] == 22
    assert related[1]["rel_type"] == "aehnlich" and related[1]["evidence"] == 0


def test_entity_ohne_verwandte_liefert_leere_liste(client):
    """Vor dem ersten Backfill ist die Tabelle leer — die Seite darf trotzdem laden."""
    _register(client)
    store = CouncilStore(COUNCIL_DB)
    store._conn.execute(
        "INSERT INTO council_entities(id, slug, name, kind, n) VALUES (1,'solo','Solo','ort',3)")
    store._conn.commit()
    store.close()
    r = client.get("/api/council/entity/solo")
    assert r.status_code == 200 and r.json()["related"] == []
