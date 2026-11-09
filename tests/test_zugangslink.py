"""Anmeldelinks aus Mails (``kern/zugangslink.py``, ``POST /api/auth/magic``).

Was hier hält, ist vor allem die **Grenze**: Ein Link meldet an, ist aber nie
selbst eine Sitzung, gilt zehn Tage, stirbt mit ``token_version`` — und die
Sitzung daraus darf das Konto nicht übernehmen.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))

from fastapi.testclient import TestClient  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from app import security  # noqa: E402
from kern import zugangslink  # noqa: E402
from kern.store import Store  # noqa: E402

RATSLOTSE_DB = os.environ["RATSLOTSE_DB"]


@pytest.fixture(autouse=True)
def frische_db():
    for suffix in ("", "-wal", "-shm"):
        Path(RATSLOTSE_DB + suffix).unlink(missing_ok=True)
    yield


@pytest.fixture
def client():
    return TestClient(app)


def _konto(client, email="leserin@example.org") -> int:
    r = client.post("/api/auth/register", json={"display_name": "Leserin", "email": email,
                                                 "password": "password123"})
    assert r.status_code == 201, r.text
    client.cookies.clear()
    store = Store(RATSLOTSE_DB)
    try:
        return store.get_web_user_by_email(email)["id"]
    finally:
        store.close()


def _link(uid: int, ver: int = 0, **kw) -> str:
    tok = zugangslink.token(uid, ver, geheimnis=get_settings().web_jwt_secret, **kw)
    assert tok
    return tok


# ---- Das Token --------------------------------------------------------------

def test_das_backend_nimmt_den_link_aus_kern_an_aber_nie_als_sitzung():
    tok = _link(7, 3)
    assert security.decode_magic_token(tok) == ("7", 3)
    assert security.decode_access_token(tok) is None


def test_ein_sitzungs_token_ist_kein_anmeldelink():
    assert security.decode_magic_token(security.create_access_token(7, 0)) is None


def test_nach_zehn_tagen_ist_er_wertlos():
    alt = _link(7, 0, jetzt=time.time() - zugangslink.TAGE * 86400 - 5)
    assert security.decode_magic_token(alt) is None
    assert zugangslink.TAGE == security.MAGIC_TAGE


def test_die_sitzung_aus_dem_link_bleibt_markiert():
    tok = security.create_access_token(7, 0, via=security.VIA_LINK)
    assert security.token_via(tok) == security.VIA_LINK
    assert security.decode_access_token(tok) == ("7", 0)
    assert security.token_via(security.create_access_token(7, 0)) is None


# ---- Einlösen ----------------------------------------------------------------

def test_ein_klick_meldet_an_und_die_sitzung_darf_lesen(client):
    uid = _konto(client)
    r = client.post("/api/auth/magic", json={"token": _link(uid)})
    assert r.status_code == 200, r.text
    assert client.get("/api/auth/me").status_code == 200


def test_abgelaufen_widerrufen_oder_falsch_gibt_401(client):
    uid = _konto(client)
    alt = _link(uid, jetzt=time.time() - 11 * 86400)
    assert client.post("/api/auth/magic", json={"token": alt}).status_code == 401
    # Abmelden überall hebt token_version — der Link stirbt mit.
    assert client.post("/api/auth/magic", json={"token": _link(uid, ver=1)}).status_code == 401
    assert client.post("/api/auth/magic", json={"token": "x" * 40}).status_code == 401
    # Ein Sitzungs-Token ist kein Anmeldelink.
    sitzung = security.create_access_token(uid, 0)
    assert client.post("/api/auth/magic", json={"token": sitzung}).status_code == 401


def test_die_app_loest_keine_links_ein(client):
    uid = _konto(client)
    r = client.post("/api/auth/magic", json={"token": _link(uid)}, headers={"X-Client": "ios"})
    assert r.status_code == 400


def test_mit_der_link_sitzung_kein_passwort_keine_adresse_kein_loeschen(client):
    uid = _konto(client)
    client.post("/api/auth/magic", json={"token": _link(uid)})
    gesperrt = [
        client.post("/api/account/change-password",
                    json={"current_password": "password123", "new_password": "password456"}),
        client.post("/api/account/change-email", json={"email": "neu@example.org", "password": "password123"}),
        client.request("DELETE", "/api/account", json={"password": "password123"}),
    ]
    for r in gesperrt:
        assert r.status_code == 403, r.text
        assert "Passwort" in r.json()["detail"]
    # Einstellen darf sie.
    assert client.put("/api/account/notifications", json={"prefs": {"n7_news": False}}).status_code == 200


def test_die_verlaengerung_vergisst_die_herkunft_nicht(monkeypatch):
    from app import session
    from starlette.requests import Request as _R
    tok = security.create_access_token(7, 0, expires_minutes=1, via=security.VIA_LINK)
    monkeypatch.setattr(session, "Request", lambda scope: type("R", (), {"cookies": {session.COOKIE_NAME: tok}})())
    kopf = session._erneuertes_cookie({})
    assert kopf, "eine fast abgelaufene Sitzung wird verlängert"
    neu = kopf[0][1].decode().split(";")[0].split("=", 1)[1]
    assert security.token_via(neu) == security.VIA_LINK
    del _R


# ---- In der Mail -------------------------------------------------------------

def test_nur_eigene_links_bekommen_das_token():
    html = ("<a href='https://ratslotse.de/karte?von=n7_news'>a</a>"
            "<a href=\"https://ratsinfo.oldenburg.de/x\">b</a><a href='mailto:x@example.org'>c</a>")
    neu = zugangslink.einsetzen(html, "TOKEN", "https://ratslotse.de")
    assert "https://ratslotse.de/karte?von=n7_news&ml=TOKEN" in neu
    assert "ratsinfo.oldenburg.de/x\"" in neu and "mailto:x@example.org'" in neu


def test_ohne_schalter_oder_fuer_andere_anlaesse_bleibt_die_mail_wie_sie_ist(monkeypatch):
    class _Store:
        class _conn:  # noqa: N801
            @staticmethod
            def execute(sql, args):
                return type("C", (), {"fetchone": staticmethod(lambda: (0,))})()
    html = "<a href='https://ratslotse.de/karte'>a</a>"
    monkeypatch.setenv("WEB_JWT_SECRET", "geheim")
    monkeypatch.setenv("FEATURE_FLAGS", "")
    assert zugangslink.fuer_mail(_Store, 1, "n7_news", html, "https://ratslotse.de") == html
    monkeypatch.setenv("FEATURE_FLAGS", "zugangslinks")
    assert "ml=" in zugangslink.fuer_mail(_Store, 1, "n7_news", html, "https://ratslotse.de")
    assert zugangslink.fuer_mail(_Store, 1, "n2_thema", html, "https://ratslotse.de") == html
