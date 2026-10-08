"""Die zweite Sicherheitsprüfung vom 08.10.2026 — je Befund ein Test.

Die erste Runde steht in ``test_sicherheitspruefung_2026_10.py``. Was zum
Bestätigungs-, Reset- und Teilen-Ablauf gehört, steht bei seinen Geschwistern
in ``test_backend_api.py``, das Tippspiel in ``test_prediction_api.py``.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1] / "web" / "backend"
sys.path.insert(0, str(_BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from app import ratelimit  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas import name_zulaessig  # noqa: E402
from app.security import decode_rs256_token  # noqa: E402
from kern.store import Store  # noqa: E402
from scripts.grant_admin import grant_admin  # noqa: E402

RATSLOTSE_DB = os.environ["RATSLOTSE_DB"]
COUNCIL_DB = os.environ["COUNCIL_DB"]


@pytest.fixture(autouse=True)
def fresh_dbs():
    for base in (RATSLOTSE_DB, COUNCIL_DB):
        for suffix in ("", "-wal", "-shm"):
            Path(base + suffix).unlink(missing_ok=True)
    yield


def _konto(email: str = "konto@test.de", name: str = "Test") -> TestClient:
    c = TestClient(app)
    r = c.post("/api/auth/register", json={"display_name": name, "email": email,
                                           "password": "password123"})
    assert r.status_code == 201, r.text
    return c


# --- F1: Stopp während des Schreibens -------------------------------------------

def test_f1_ein_gestoppter_job_zaehlt_sobald_der_bericht_unterwegs_war():
    store = Store(RATSLOTSE_DB)
    try:
        uid = store.create_web_user("deep@test.de", "x", "user", "active", email_verified=True)
        frei = store.deep_job_anlegen(uid, "Frage eins")
        gezaehlt = store.deep_job_anlegen(uid, "Frage zwei")
        kaputt = store.deep_job_anlegen(uid, "Frage drei")
        for job in (frei, gezaehlt, kaputt):
            store.deep_job_update(job, "gestoppt")
        store.deep_job_mark_counted(gezaehlt)
        store.deep_job_mark_counted(kaputt)
        store.deep_job_update(kaputt, "fehler")
        # Nur der gestoppte Job, dessen Bericht schon rausging, zählt —
        # ein Fehler kostet weiterhin nichts.
        assert store.deep_jobs_heute(uid) == 1
    finally:
        store.close()


# --- F2: Länge der Frage --------------------------------------------------------

def test_f2_eine_ueberlange_frage_wird_abgewiesen():
    c = _konto()
    r = c.post("/api/council/ask", json={"question": "Stadion? " + "a " * 5000})
    assert r.status_code == 422


# --- F6/F7: 500er aus fremder Eingabe ------------------------------------------

@pytest.mark.parametrize("kopf", ["W10", "IjEi", "W" * 0 + "WzFd"])
def test_f6_ein_kopf_ohne_objekt_ist_kein_absturz(kopf):
    # `[]`, `"1"`, `[1]` — gültiges JSON, aber kein Objekt.
    assert decode_rs256_token(f"{kopf}.eyJ4IjoxfQ.AAAA", []) is None


def test_f6_tiefe_verschachtelung_ist_kein_absturz():
    import base64
    kopf = base64.urlsafe_b64encode(b"[" * 5000).rstrip(b"=").decode()
    assert decode_rs256_token(f"{kopf}.eyJ4IjoxfQ.AAAA", []) is None


def test_f6_apple_anmeldung_mit_kaputtem_token_ist_kein_500():
    r = TestClient(app, raise_server_exceptions=False).post(
        "/api/auth/apple", json={"identity_token": "W10.eyJ4IjoxfQ.AAAAAAAAAAAAAAAAAAAAAAAA"})
    assert r.status_code < 500


def test_f7_ein_nicht_ascii_token_ist_ein_404():
    r = TestClient(app, raise_server_exceptions=False).get(
        "/api/wahlabend/stichwahl/potenzial", params={"token": "ä"})
    assert r.status_code == 404


# --- F9/F10: siehe test_backend_api.py ------------------------------------------

def test_f10_ein_adresswechsel_macht_niemanden_zum_admin(monkeypatch):
    """Nach einem Wechsel auf WEB_ADMIN_EMAIL gibt es keine Beförderung."""
    import hashlib
    from datetime import timedelta
    c = _konto("wechsler@test.de")
    store = Store(RATSLOTSE_DB)
    try:
        uid = int(store.get_web_user_by_email("wechsler@test.de")["id"])
        exp = (datetime.utcnow() + timedelta(hours=1)).isoformat(timespec="seconds")
        store.create_email_verification(uid, hashlib.sha256(b"zum-admin").hexdigest(), exp,
                                        new_email=os.environ["WEB_ADMIN_EMAIL"])
    finally:
        store.close()
    r = c.post("/api/auth/verify-email", json={"token": "zum-admin"})
    assert r.status_code == 200
    assert "admin" not in r.json()["roles"]


# --- F12: kein Cookie für die App ----------------------------------------------

def test_f12_die_app_bekommt_kein_sitzungs_cookie():
    r = TestClient(app).post("/api/auth/register", headers={"X-Client": "ios"}, json={
        "display_name": "App", "email": "app@test.de", "password": "password123"})
    assert r.status_code == 201
    assert r.json()["access_token"]
    assert "access_token" not in r.cookies
    # Der Browser bekommt es weiter.
    r = TestClient(app).post("/api/auth/register", json={
        "display_name": "Web", "email": "web@test.de", "password": "password123"})
    assert "access_token" in r.cookies


# --- F13: Fehlversuche je Konto --------------------------------------------------

def test_f13_fehlversuche_je_konto_sperren_die_anmeldung(monkeypatch):
    monkeypatch.delenv("DISABLE_RATE_LIMIT", raising=False)
    monkeypatch.setattr(ratelimit.login_limiter, "max_calls", 10_000)
    begrenzer = ratelimit.RateLimiter(max_calls=3, window_seconds=900)
    monkeypatch.setattr("app.routers.auth.login_fail_limiter", begrenzer)
    _konto("ziel@test.de")
    c = TestClient(app)
    for _ in range(3):
        assert c.post("/api/auth/login", json={"email": "ziel@test.de",
                                               "password": "falsch123"}).status_code == 401
    # Jetzt auch mit dem RICHTIGEN Passwort: gesperrt, egal von welcher Adresse.
    r = c.post("/api/auth/login", json={"email": "ziel@test.de", "password": "password123"})
    assert r.status_code == 429


def test_f13_ipv6_zaehlt_je_64er_netz():
    from types import SimpleNamespace
    b = ratelimit.RateLimiter(max_calls=1, window_seconds=60)
    req = lambda host: SimpleNamespace(client=SimpleNamespace(host=host))  # noqa: E731
    assert b._key(req("2001:db8:1:2::1")) == b._key(req("2001:db8:1:2:ffff::9"))
    assert b._key(req("192.0.2.1")) == "192.0.2.1"


# --- F14: Live-Probe nicht von fremder Seite -------------------------------------

def test_f14_live_probe_nicht_von_fremder_seite():
    c = _konto("admin@test.de")
    grant_admin("admin@test.de", RATSLOTSE_DB)
    r = c.get("/api/admin/live-probe", params={"seconds": 10},
              headers={"Sec-Fetch-Site": "cross-site"})
    assert r.status_code == 403


# --- F15: keine Adressen im Namen, keine Anrede an Fremde ----------------------

@pytest.mark.parametrize("name", ["Konto gesperrt: https://evil.example/x", "www.evil.de",
                                  "Anna evil.de", "a@b", "<b>Anna</b>"])
def test_f15_ein_name_mit_adresse_wird_abgewiesen(name):
    assert not name_zulaessig(name)
    r = TestClient(app).post("/api/auth/register", json={
        "display_name": name, "email": "name@test.de", "password": "password123"})
    assert r.status_code == 422


@pytest.mark.parametrize("name", ["Anna", "Dr. Anna-Lena O'Brien", "Jörg M.", "St. Martin"])
def test_f15_echte_namen_bleiben_erlaubt(name):
    assert name_zulaessig(name)


def test_f15_die_bestaetigungsmail_gruesst_ohne_namen(monkeypatch):
    from app.routers import auth as auth_mod
    gesendet = {}
    monkeypatch.setattr(auth_mod, "send_email",
                        lambda an, betreff, html, **k: gesendet.update(html=html))
    monkeypatch.setattr(auth_mod, "protokolliere", lambda *a, **k: None)
    monkeypatch.setattr(auth_mod, "get_settings", lambda: type("S", (), {
        "resend_api_key": "x", "app_base_url": "https://ratslotse.example", "email_from": "x"})())
    auth_mod._send_verification_email("a@example.org", "tok", "Fremder Text", 1, "123456")
    assert "Fremder Text" not in gesendet["html"]


# --- F16: Hinweis an die Besitzerin ---------------------------------------------

def test_f16_doppelte_registrierung_benachrichtigt_die_adresse(monkeypatch):
    from app.routers import auth as auth_mod
    gesendet = []
    monkeypatch.setattr(auth_mod, "_send_duplicate_notice",
                        lambda email, owner_id: gesendet.append(email))
    monkeypatch.setattr(auth_mod, "register_notice_limiter",
                        ratelimit.RateLimiter(max_calls=1, window_seconds=3600))
    monkeypatch.setattr(auth_mod, "register_duplicate_limiter",
                        ratelimit.RateLimiter(max_calls=100, window_seconds=3600))
    _konto("doppelt@test.de")
    monkeypatch.delenv("DISABLE_RATE_LIMIT", raising=False)
    for _ in range(2):
        r = TestClient(app).post("/api/auth/register", json={
            "display_name": "X", "email": "doppelt@test.de", "password": "password123"})
        assert r.status_code == 409
    # Höchstens ein Hinweis je Stunde — sonst ließe sich die Adresse zumüllen.
    assert gesendet == ["doppelt@test.de"]


def test_f16_der_neue_mail_anlass_ist_bekannt():
    from kern.store import MAIL_ANLAESSE
    assert "duplicate_signup" in MAIL_ANLAESSE
