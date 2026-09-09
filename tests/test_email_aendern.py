"""E-Mail-Adresse ändern — und die Fallen, die dabei aufgehen.

Der Wechsel ist zweistufig: Passwort jetzt, Link an die neue Adresse. Bis der
Link geklickt ist, ändert sich NICHTS. Diese Datei hält vor allem die Fälle
fest, in denen eine naheliegende Umsetzung ein Loch aufreißt:

* Ein DEAKTIVIERTES Konto darf sich über einen Wechsel-Link nicht selbst
  wieder freischalten (`status == pending` heißt beides — unbestätigt UND vom
  Admin abgeschaltet).
* Ein UNBESTÄTIGTES Konto muss wechseln dürfen: Der Tippfehler bei der
  Registrierung ist der häufigste echte Anlass, und genau dieses Konto sperrt
  `require_active` aus.
* Wird die Zieladresse zwischen Anstoßen und Klick vergeben, muss der Klick
  scheitern statt die UNIQUE-Bedingung zu verletzen.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

_BACKEND = Path(__file__).resolve().parents[1] / "web" / "backend"
sys.path.insert(0, str(_BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from kern.store import Store  # noqa: E402

RATSLOTSE_DB = os.environ["RATSLOTSE_DB"]
COUNCIL_DB = os.environ["COUNCIL_DB"]

ALT = "wechsel@example.org"
NEU = "neu@example.org"
PASSWORT = "password123"


@pytest.fixture(autouse=True)
def fresh_dbs():
    for base in (RATSLOTSE_DB, COUNCIL_DB):
        for suffix in ("", "-wal", "-shm"):
            Path(base + suffix).unlink(missing_ok=True)
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def postfach():
    """Sammelt die verschickten Mails als ``[(empfänger, text), …]``.

    Der Wechsel verschickt an ZWEI Adressen (Link an die neue, Warnung an die
    alte). Ein Fake, der nur die letzte behält, würde genau den Teil
    verschlucken, der die alte Adresse schützt.
    """
    return []


def _fake_settings():
    return SimpleNamespace(
        resend_api_key="x", app_base_url="https://ratslotse.de",
        email_from="Ratslotse <f@example.org>", feedback_email="",
        web_admin_email="", cookie_secure=False,
        access_token_expire_minutes=60, app_access_token_expire_minutes=60,
        ratslotse_db=str(RATSLOTSE_DB), apple_bundle_id="de.ratslotse.app",
    )


def _mit_mailversand(postfach):
    """Kontextmanager-Paar: Mailversand vortäuschen, Settings mit Key liefern.

    Beide Router patchen: `account.py` ruft die Mail-Funktionen, die in
    `auth.py` stehen — gepatcht werden muss deshalb `auth.send_email`, die
    Settings dagegen an beiden Stellen.
    """
    def fake_send(to, subject, html, **kw):
        postfach.append((to, kw.get("text", "")))
        return "id"

    einstellungen = _fake_settings()
    return (
        patch("app.routers.auth.send_email", side_effect=fake_send),
        patch("app.routers.auth.get_settings", return_value=einstellungen),
        patch("app.routers.account.get_settings", return_value=einstellungen),
    )


def _registrieren(client, email=ALT, passwort=PASSWORT):
    r = client.post("/api/auth/register", json={"email": email, "password": passwort})
    assert r.status_code == 201, r.text
    return r.json()


def _token_aus(text: str) -> str:
    treffer = re.search(r"token=([\w~.-]+)", text)
    assert treffer, f"kein Token im Mailtext: {text!r}"
    return treffer.group(1)


def _an(postfach, adresse: str) -> str:
    """Der Text der Mail an genau diese Adresse."""
    passend = [t for (to, t) in postfach if to == adresse]
    assert passend, f"keine Mail an {adresse} (nur an {[to for to, _ in postfach]})"
    return passend[-1]


def _wechsel_anstossen(client, postfach, neu=NEU, passwort=PASSWORT):
    versand, s_auth, s_account = _mit_mailversand(postfach)
    with versand, s_auth, s_account:
        return client.post("/api/account/change-email",
                           json={"new_email": neu, "current_password": passwort})


def _bestaetigen(client, postfach, token):
    versand, s_auth, s_account = _mit_mailversand(postfach)
    with versand, s_auth, s_account:
        return client.post("/api/auth/verify-email", json={"token": token})


# --- Sofort-Pfad: ohne Mailversand gilt der Wechsel direkt -------------------

def test_ohne_mailversand_gilt_der_wechsel_sofort(client):
    """Dieselbe Regel wie bei der Registrierung: Ohne ``RESEND_API_KEY`` gibt
    es keinen Bestätigungslink — dann wäre ein zweistufiger Wechsel eine
    Sackgasse. Genau dieser Pfad trägt dev, feature und die Browsertests."""
    _registrieren(client)
    r = client.post("/api/account/change-email",
                    json={"new_email": NEU, "current_password": PASSWORT})
    assert r.status_code == 200, r.text
    assert r.json()["email"] == NEU
    assert r.json()["pending_email"] is None

    client.post("/api/auth/logout")
    assert client.post("/api/auth/login",
                       json={"email": NEU, "password": PASSWORT}).status_code == 200
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login",
                       json={"email": ALT, "password": PASSWORT}).status_code == 401


# --- Token-Pfad: der eigentliche Ablauf -------------------------------------

def test_wechsel_gilt_erst_mit_dem_klick_und_meldet_sich_bei_beiden_adressen(client, postfach):
    # Ohne RESEND_API_KEY legt die Registrierung ein bereits bestätigtes,
    # aktives Konto an (`verified = not can_send_email` in `register`) — genau
    # die Ausgangslage, die dieser Test braucht. Der Mailversand wird erst für
    # den Wechsel selbst vorgetäuscht.
    _registrieren(client)

    r = _wechsel_anstossen(client, postfach)
    assert r.status_code == 200, r.text
    # Nichts geändert — nur angekündigt.
    assert r.json()["email"] == ALT
    assert r.json()["pending_email"] == NEU
    assert client.get("/api/auth/me").json()["pending_email"] == NEU

    # Beide Adressen wurden angeschrieben: Link an neu, Warnung an alt.
    assert {to for to, _ in postfach} == {ALT, NEU}
    assert "Passwort" in _an(postfach, ALT)
    assert NEU in _an(postfach, ALT)

    v = _bestaetigen(client, postfach, _token_aus(_an(postfach, NEU)))
    assert v.status_code == 200, v.text
    assert v.json()["email"] == NEU
    assert v.json()["pending_email"] is None
    # Quittung an die alte Adresse.
    assert "geändert" in _an(postfach, ALT).lower() or NEU in _an(postfach, ALT)

    client.post("/api/auth/logout")
    assert client.post("/api/auth/login",
                       json={"email": NEU, "password": PASSWORT}).status_code == 200


def test_die_sitzung_bleibt_nach_dem_wechsel_gueltig(client, postfach):
    """`token_version` wird bewusst NICHT erhöht: Der Wechsel wurde mit dem
    Passwort bestätigt, und wer den Link auf einem zweiten Gerät klickt,
    würde sonst beide Geräte abmelden."""
    _registrieren(client)
    _wechsel_anstossen(client, postfach)
    _bestaetigen(client, postfach, _token_aus(_an(postfach, NEU)))
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == NEU


# --- Re-Auth ----------------------------------------------------------------

def test_falsches_passwort_aendert_nichts(client):
    _registrieren(client)
    r = client.post("/api/account/change-email",
                    json={"new_email": NEU, "current_password": "falsch-falsch"})
    assert r.status_code == 400
    assert client.get("/api/auth/me").json()["email"] == ALT


def test_ohne_anmeldung_kein_wechsel(client):
    _registrieren(client)
    client.post("/api/auth/logout")
    r = client.post("/api/account/change-email",
                    json={"new_email": NEU, "current_password": PASSWORT})
    assert r.status_code == 401


# --- Zieladresse ------------------------------------------------------------

def test_die_eigene_adresse_ist_kein_wechsel(client):
    _registrieren(client)
    for variante in (ALT, ALT.upper(), f"  {ALT}  "):
        r = client.post("/api/account/change-email",
                        json={"new_email": variante, "current_password": PASSWORT})
        assert r.status_code == 400, f"{variante!r} hätte abgewiesen werden müssen"


def test_vergebene_adresse_wird_abgewiesen(client):
    _registrieren(client, "fremd@example.org")
    client.post("/api/auth/logout")
    _registrieren(client)
    r = client.post("/api/account/change-email",
                    json={"new_email": "fremd@example.org", "current_password": PASSWORT})
    assert r.status_code == 409


def test_local_adressen_sind_nicht_zulaessig(client):
    """`…@local` sind die synthetischen Adressen des Telegram-Altbestands —
    ein Konto dorthin zu wechseln hieße, es unerreichbar zu machen.

    Geprüft wird die WIRKUNG, nicht der Statuscode: Heute weist schon
    ``EmailStr`` die Domain ohne Punkt mit 422 ab, der Riegel im Router käme
    gar nicht zum Zug. Beides ist richtig; festhalten lässt sich sinnvoll nur,
    dass die Adresse nicht durchkommt.
    """
    _registrieren(client)
    r = client.post("/api/account/change-email",
                    json={"new_email": "tg-42@local", "current_password": PASSWORT})
    assert r.status_code in (400, 422), r.text
    assert client.get("/api/auth/me").json()["email"] == ALT


def test_adresse_wird_zwischen_anstossen_und_klick_vergeben(client, postfach):
    """Der Wettlauf: Der Klick muss scheitern, nicht die UNIQUE-Bedingung."""
    _registrieren(client)
    _wechsel_anstossen(client, postfach)
    token = _token_aus(_an(postfach, NEU))

    client.post("/api/auth/logout")
    _registrieren(client, NEU)          # jemand anders schnappt sich die Adresse
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email": ALT, "password": PASSWORT})

    v = _bestaetigen(client, postfach, token)
    assert v.status_code == 409
    assert client.get("/api/auth/me").json()["email"] == ALT
    # Token ist verbraucht — der Wechsel muss neu angestoßen werden.
    assert client.get("/api/auth/me").json()["pending_email"] is None


# --- Kontostände ------------------------------------------------------------

def test_unbestaetigtes_konto_darf_den_tippfehler_korrigieren(client, postfach):
    """Der häufigste echte Anlass — und genau das Konto, das `require_active`
    aussperrt. Der alte Registrierungs-Link muss dabei sterben."""
    versand, s_auth, s_account = _mit_mailversand(postfach)
    with versand, s_auth, s_account:
        r = client.post("/api/auth/register",
                        json={"email": ALT, "password": PASSWORT})
    assert r.status_code == 201
    assert r.json()["email_verified"] is False
    alter_link = _token_aus(_an(postfach, ALT))
    postfach.clear()

    w = _wechsel_anstossen(client, postfach)
    assert w.status_code == 200, w.text
    assert w.json()["pending_email"] == NEU

    # Der Link auf die Tippfehler-Adresse ist tot.
    assert _bestaetigen(client, postfach, alter_link).status_code == 400

    v = _bestaetigen(client, postfach, _token_aus(_an(postfach, NEU)))
    assert v.status_code == 200
    assert v.json()["email"] == NEU
    assert v.json()["email_verified"] is True
    assert v.json()["status"] == "active"


def test_deaktiviertes_konto_kann_sich_nicht_selbst_freischalten(client, postfach):
    """Das Loch, gegen das der `war_unbestaetigt`-Merker gebaut ist:
    `status == pending` heißt auch „von einem Admin abgeschaltet"."""
    _registrieren(client)
    _wechsel_anstossen(client, postfach)
    token = _token_aus(_an(postfach, NEU))

    store = Store(RATSLOTSE_DB)
    try:
        konto = store.get_web_user_by_email(ALT)
        store.set_email_verified(konto["id"], True)
        store.set_web_user_status(konto["id"], "pending")   # Admin schaltet ab
    finally:
        store.close()

    v = _bestaetigen(client, postfach, token)
    assert v.status_code == 200
    assert v.json()["email"] == NEU          # die Adresse wechselt
    assert v.json()["status"] == "pending"   # der Rauswurf bleibt


def test_deaktiviertes_konto_kann_keinen_wechsel_anstossen(client):
    _registrieren(client)
    store = Store(RATSLOTSE_DB)
    try:
        konto = store.get_web_user_by_email(ALT)
        store.set_email_verified(konto["id"], True)
        store.set_web_user_status(konto["id"], "pending")
    finally:
        store.close()
    r = client.post("/api/account/change-email",
                    json={"new_email": NEU, "current_password": PASSWORT})
    assert r.status_code == 403


# --- Abbrechen und erneut senden -------------------------------------------

def test_abbrechen_macht_den_link_ungueltig(client, postfach):
    _registrieren(client)
    _wechsel_anstossen(client, postfach)
    token = _token_aus(_an(postfach, NEU))

    r = client.delete("/api/account/change-email")
    assert r.status_code == 200
    assert r.json()["pending_email"] is None
    assert client.get("/api/auth/me").json()["pending_email"] is None
    assert _bestaetigen(client, postfach, token).status_code == 400


def test_erneut_senden_geht_an_die_neue_adresse(client, postfach):
    """Ohne diesen Pfad hätte „Erneut senden" den schwebenden Wechsel still
    gelöscht: `create_email_verification` verwirft alle älteren Tokens."""
    _registrieren(client)
    _wechsel_anstossen(client, postfach)
    erster = _token_aus(_an(postfach, NEU))
    postfach.clear()

    versand, s_auth, s_account = _mit_mailversand(postfach)
    with versand, s_auth, s_account:
        assert client.post("/api/auth/resend-verification").status_code == 200

    assert {to for to, _ in postfach} == {NEU}
    zweiter = _token_aus(_an(postfach, NEU))
    assert zweiter != erster
    assert _bestaetigen(client, postfach, erster).status_code == 400
    assert _bestaetigen(client, postfach, zweiter).status_code == 200
    assert client.get("/api/auth/me").json()["email"] == NEU


def test_zweiter_wechsel_ersetzt_den_ersten(client, postfach):
    _registrieren(client)
    _wechsel_anstossen(client, postfach)
    erster = _token_aus(_an(postfach, NEU))
    postfach.clear()

    zweite_adresse = "zweite@example.org"
    _wechsel_anstossen(client, postfach, neu=zweite_adresse)
    assert client.get("/api/auth/me").json()["pending_email"] == zweite_adresse
    assert _bestaetigen(client, postfach, erster).status_code == 400

    v = _bestaetigen(client, postfach, _token_aus(_an(postfach, zweite_adresse)))
    assert v.json()["email"] == zweite_adresse


def test_link_laesst_sich_nur_einmal_einloesen(client, postfach):
    _registrieren(client)
    _wechsel_anstossen(client, postfach)
    token = _token_aus(_an(postfach, NEU))
    assert _bestaetigen(client, postfach, token).status_code == 200
    assert _bestaetigen(client, postfach, token).status_code == 400


def test_abgelaufener_wechsel_zaehlt_nicht_mehr_als_schwebend(client, postfach):
    """Ein abgelaufener Token ist kein Wechsel mehr — sonst wartete die
    Oberfläche auf eine Bestätigung, die nicht mehr kommen kann."""
    _registrieren(client)
    _wechsel_anstossen(client, postfach)
    store = Store(RATSLOTSE_DB)
    try:
        konto = store.get_web_user_by_email(ALT)
        store._conn.execute("UPDATE email_verification_tokens SET expires_at = ?",
                            ("2000-01-01T00:00:00",))
        store._conn.commit()
        assert store.pending_email_change(konto["id"], "2026-09-09T12:00:00") is None
    finally:
        store.close()
    assert client.get("/api/auth/me").json()["pending_email"] is None


# --- Bremse -----------------------------------------------------------------

def test_der_wechsel_ist_pro_konto_gebremst(client, monkeypatch):
    """Der Aufruf verschickt eine Mail an eine FREMDE, frei gewählte Adresse —
    ungebremst wäre das ein Versandweg für Belästigung auf unsere Kosten."""
    monkeypatch.delenv("DISABLE_RATE_LIMIT", raising=False)
    from app.ratelimit import change_email_limiter
    change_email_limiter._calls.clear()
    _registrieren(client)
    codes = [
        client.post("/api/account/change-email",
                    json={"new_email": f"z{i}@example.org", "current_password": "falsch"}).status_code
        for i in range(6)
    ]
    change_email_limiter._calls.clear()
    assert codes[-1] == 429, codes
