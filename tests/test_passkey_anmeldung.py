"""Mit Passkey registrieren und anmelden (``web/backend/app/passkeys.py``,
``routers/auth_passkey.py``).

Geprüft wird gegen ein **Software-Gerät** mit festem Schlüssel (``Geraet``):
Es baut ``attestationObject``, ``authenticatorData`` und die Signatur so, wie
ein echter Authenticator sie liefert — die Prüfung läuft also durch
``py_webauthn`` und nicht an ihm vorbei. Der Browsertest mit dem virtuellen
Authenticator von Chrome deckt den Weg durch die Oberfläche ab
(``web/frontend/tests/e2e/34-passkey.spec.ts``).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import cbor2
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))

from fastapi.testclient import TestClient  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from kern.store import USER_OWNED_TABLES, Store  # noqa: E402

RATSLOTSE_DB = os.environ["RATSLOTSE_DB"]
ORIGIN = "{0.scheme}://{0.netloc}".format(urlsplit(get_settings().app_base_url))
RP_ID = urlsplit(ORIGIN).hostname or ""


def b64url(roh: bytes) -> str:
    return base64.urlsafe_b64encode(roh).rstrip(b"=").decode()


def von_b64url(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class Geraet:
    """Ein Authenticator mit festem P-256-Schlüssel (Testvektor: Skalar
    ``nummer``) und fester Kennung — reproduzierbar von Lauf zu Lauf."""

    def __init__(self, nummer: int = 1, *, uv: bool = True, rp_id: str = RP_ID, origin: str = ORIGIN):
        self.schluessel = ec.derive_private_key(0x5EC0DE + nummer, ec.SECP256R1())
        self.kennung = hashlib.sha256(f"geraet-{nummer}".encode()).digest()
        self.zaehler = 0
        self.uv = uv
        self.rp_id = rp_id
        self.origin = origin
        self.handle: str | None = None

    def _flags(self, extra: int = 0) -> bytes:
        return bytes([0x01 | (0x04 if self.uv else 0) | 0x08 | 0x10 | extra])  # UP, UV, BE, BS

    def _client(self, typ: str, challenge: str) -> bytes:
        return json.dumps({"type": typ, "challenge": challenge, "origin": self.origin,
                           "crossOrigin": False}).encode()

    def anlegen(self, optionen: dict) -> dict:
        pk = optionen["public_key"]
        self.handle = pk["user"]["id"]
        zahlen = self.schluessel.public_key().public_numbers()
        cose = cbor2.dumps({1: 2, 3: -7, -1: 1, -2: zahlen.x.to_bytes(32, "big"), -3: zahlen.y.to_bytes(32, "big")})
        auth = (hashlib.sha256(self.rp_id.encode()).digest() + self._flags(0x40) + self.zaehler.to_bytes(4, "big")
                + bytes(16) + len(self.kennung).to_bytes(2, "big") + self.kennung + cose)
        att = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth})
        return {
            "id": b64url(self.kennung), "rawId": b64url(self.kennung), "type": "public-key",
            "response": {"clientDataJSON": b64url(self._client("webauthn.create", pk["challenge"])),
                         "attestationObject": b64url(att), "transports": ["internal", "hybrid"]},
            # Was der Browser aus PRF liefert, darf den Server nie erreichen —
            # die Formen verwerfen es (s. test_prf_geheimnis_wird_verworfen).
            "clientExtensionResults": {"prf": {"enabled": True, "results": {"first": "R0VIRUlNLVBSRi1HRUhFSU0"}}},
        }

    def bestaetigen(self, optionen: dict, *, zaehler: int | None = None, handle: str | None = None) -> dict:
        self.zaehler = self.zaehler + 1 if zaehler is None else zaehler
        auth = hashlib.sha256(self.rp_id.encode()).digest() + self._flags() + self.zaehler.to_bytes(4, "big")
        client = self._client("webauthn.get", optionen["public_key"]["challenge"])
        sig = self.schluessel.sign(auth + hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256()))
        return {
            "id": b64url(self.kennung), "rawId": b64url(self.kennung), "type": "public-key",
            "response": {"clientDataJSON": b64url(client), "authenticatorData": b64url(auth),
                         "signature": b64url(sig), "userHandle": handle if handle is not None else self.handle},
        }


@pytest.fixture(autouse=True)
def frisch(monkeypatch):
    for suffix in ("", "-wal", "-shm"):
        Path(RATSLOTSE_DB + suffix).unlink(missing_ok=True)
    monkeypatch.setenv("FEATURE_FLAGS", "passkey-anmeldung,notizen")
    yield


def _registrieren(geraet: Geraet, email: str = "passkey@example.org", name: str = "Pia") -> tuple[TestClient, dict]:
    c = TestClient(app)
    opt = c.post("/api/auth/passkey/signup/options", json={"email": email, "display_name": name})
    assert opt.status_code == 200, opt.text
    r = c.post("/api/auth/passkey/signup", json={"credential": geraet.anlegen(opt.json()), "label": "Mac"})
    assert r.status_code == 201, r.text
    return c, r.json()


def _anmelden(geraet: Geraet, c: TestClient | None = None, **kw) -> tuple[TestClient, object]:
    c = c or TestClient(app)
    opt = c.post("/api/auth/passkey/login/options").json()
    return c, c.post("/api/auth/passkey/login", json={"credential": geraet.bestaetigen(opt, **kw)})


def _passwortkonto(email: str = "pw@example.org") -> TestClient:
    c = TestClient(app)
    assert c.post("/api/auth/register", json={"display_name": "Paul", "email": email,
                                              "password": "password123"}).status_code == 201
    return c


# ---- Schalter und Grundfluss ---------------------------------------------------------

def test_ohne_schalter_gibt_es_die_endpunkte_nicht(monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "")
    c = TestClient(app)
    assert c.post("/api/auth/passkey/login/options").status_code == 404
    assert c.post("/api/auth/passkey/signup/options",
                  json={"email": "a@example.org", "display_name": "A"}).status_code == 404


def test_registrieren_legt_passwortloses_konto_mit_passkey_an():
    g = Geraet()
    c, user = _registrieren(g)
    assert user["has_password"] is False
    assert user["display_name"] == "Pia"
    me = c.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["email"] == "passkey@example.org"
    liste = c.get("/api/account/passkeys").json()["passkeys"]
    assert [(p["label"], p["credential_id"]) for p in liste] == [("Mac", b64url(g.kennung))]


def test_optionen_tragen_rp_id_und_verlangen_nutzerverifikation():
    pk = TestClient(app).post("/api/auth/passkey/signup/options",
                              json={"email": "o@example.org", "display_name": "O"}).json()["public_key"]
    assert pk["rp"]["id"] == RP_ID
    assert pk["authenticatorSelection"]["userVerification"] == "required"
    assert pk["authenticatorSelection"]["residentKey"] == "required"
    assert pk["attestation"] == "none"


def test_anmelden_mit_dem_passkey():
    g = Geraet()
    _registrieren(g)
    c, r = _anmelden(g)
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "passkey@example.org"
    assert c.get("/api/auth/me").status_code == 200


def test_anmelde_optionen_ohne_kennungen():
    """Kein ``allowCredentials``: Wer anmeldet, muss vorher nichts tippen."""
    pk = TestClient(app).post("/api/auth/passkey/login/options").json()["public_key"]
    assert pk.get("allowCredentials", []) == []
    assert pk["rpId"] == RP_ID


def test_vergebene_adresse_vor_der_abfrage_am_geraet():
    _passwortkonto("vergeben@example.org")
    r = TestClient(app).post("/api/auth/passkey/signup/options",
                             json={"email": "vergeben@example.org", "display_name": "X"})
    assert r.status_code == 409


def test_name_ist_pflicht():
    r = TestClient(app).post("/api/auth/passkey/signup/options", json={"email": "n@example.org", "display_name": " "})
    assert r.status_code == 422


# ---- Was die Prüfung abweisen muss ----------------------------------------------------

def test_challenge_gilt_genau_einmal():
    g = Geraet()
    c = TestClient(app)
    opt = c.post("/api/auth/passkey/signup/options", json={"email": "e@example.org", "display_name": "E"}).json()
    cred = g.anlegen(opt)
    assert c.post("/api/auth/passkey/signup", json={"credential": cred}).status_code == 201
    assert c.post("/api/auth/passkey/signup", json={"credential": cred}).status_code == 400


def test_anmelde_challenge_gilt_genau_einmal():
    g = Geraet()
    _registrieren(g)
    c = TestClient(app)
    opt = c.post("/api/auth/passkey/login/options").json()
    cred = g.bestaetigen(opt)
    assert c.post("/api/auth/passkey/login", json={"credential": cred}).status_code == 200
    assert c.post("/api/auth/passkey/login", json={"credential": cred}).status_code == 400


def test_challenge_fuer_einen_anderen_zweck_taugt_nicht():
    """Eine Anmelde-Challenge registriert nichts."""
    g = Geraet()
    c = TestClient(app)
    opt = c.post("/api/auth/passkey/login/options").json()
    opt["public_key"]["user"] = {"id": b64url(b"x" * 16)}
    assert c.post("/api/auth/passkey/signup", json={"credential": g.anlegen(opt)}).status_code == 400


def test_abgelaufene_challenge(monkeypatch):
    g = Geraet()
    c = TestClient(app)
    opt = c.post("/api/auth/passkey/signup/options", json={"email": "alt@example.org", "display_name": "A"}).json()
    s = Store(RATSLOTSE_DB)
    s._conn.execute("UPDATE webauthn_challenges SET expires_at = ?",
                    ((datetime.utcnow() - timedelta(minutes=1)).isoformat(timespec="seconds"),))
    s._conn.commit()
    s.close()
    assert c.post("/api/auth/passkey/signup", json={"credential": g.anlegen(opt)}).status_code == 400


def test_fremde_herkunft():
    g = Geraet(origin="https://ratslotse.example.org")
    c = TestClient(app)
    opt = c.post("/api/auth/passkey/signup/options", json={"email": "f@example.org", "display_name": "F"}).json()
    assert c.post("/api/auth/passkey/signup", json={"credential": g.anlegen(opt)}).status_code == 400


def test_fremde_rp_id():
    """Ein Passkey für eine andere Seite — die RP-ID steckt gehasht in den
    Gerätedaten, die Herkunft im Browser-Teil wäre gefälscht passend."""
    g = Geraet(rp_id="example.org")
    c = TestClient(app)
    opt = c.post("/api/auth/passkey/signup/options", json={"email": "r@example.org", "display_name": "R"}).json()
    assert c.post("/api/auth/passkey/signup", json={"credential": g.anlegen(opt)}).status_code == 400


def test_ohne_nutzerverifikation_keine_anmeldung():
    g = Geraet()
    _registrieren(g)
    g.uv = False
    _, r = _anmelden(g)
    assert r.status_code == 401


def test_ohne_nutzerverifikation_keine_registrierung():
    g = Geraet(uv=False)
    c = TestClient(app)
    opt = c.post("/api/auth/passkey/signup/options", json={"email": "u@example.org", "display_name": "U"}).json()
    assert c.post("/api/auth/passkey/signup", json={"credential": g.anlegen(opt)}).status_code == 400


def test_falsche_signatur():
    g = Geraet()
    _registrieren(g)
    anderer = Geraet(2)
    anderer.kennung, anderer.handle = g.kennung, g.handle  # gleiche Kennung, anderer Schlüssel
    _, r = _anmelden(anderer)
    assert r.status_code == 401


def test_zaehler_darf_nicht_zuruecklaufen():
    """Ein Zähler, der zurückläuft, heißt: Der Schlüssel wurde kopiert."""
    g = Geraet()
    _registrieren(g)
    assert _anmelden(g, zaehler=5)[1].status_code == 200
    assert _anmelden(g, zaehler=3)[1].status_code == 401


def test_nutzerkennung_muss_passen():
    g = Geraet()
    _registrieren(g)
    _, r = _anmelden(g, handle=b64url(b"jemand-anderes!!"))
    assert r.status_code == 401


def test_unbekannter_passkey():
    _, r = _anmelden(Geraet(3))
    assert r.status_code == 401
    assert "kennt Ratslotse nicht" in r.json()["detail"]


def test_prf_geheimnis_wird_verworfen():
    """Das PRF-Ergebnis schließt die Notizen auf und bleibt auf dem Gerät.
    Schickt ein Browser es doch mit, steht es danach nirgends."""
    _registrieren(Geraet())
    for suffix in ("", "-wal"):
        datei = Path(RATSLOTSE_DB + suffix)
        if datei.exists():
            assert b"R0VIRUlNLVBSRi1HRUhFSU0" not in datei.read_bytes()


# ---- Im Konto -------------------------------------------------------------------------

def _hinzufuegen(c: TestClient, g: Geraet, label: str = "iPhone"):
    opt = c.post("/api/account/passkeys/options")
    assert opt.status_code == 200, opt.text
    return c.post("/api/account/passkeys", json={"credential": g.anlegen(opt.json()), "label": label})


def test_passwortkonto_fuegt_passkey_hinzu_und_meldet_sich_damit_an():
    c = _passwortkonto()
    g = Geraet()
    r = _hinzufuegen(c, g)
    assert r.status_code == 200, r.text
    assert [p["label"] for p in r.json()["passkeys"]] == ["iPhone"]
    _, r = _anmelden(g)
    assert r.status_code == 200 and r.json()["email"] == "pw@example.org"


def test_kennung_je_konto_gleich_und_wie_bei_den_notizen():
    """Dieselbe Kennung wie ``nutzerKennung`` in ``lib/notiz-passkey.ts`` —
    sonst legte ein Gerät zwei Ratslotse-Passkeys für ein Konto an."""
    c = _passwortkonto()
    uid = c.get("/api/auth/me").json()["id"]
    pk = c.post("/api/account/passkeys/options").json()["public_key"]
    erwartet = b64url(hashlib.sha256(f"ratslotse-notizen|{uid}".encode()).digest()[:16])
    assert pk["user"]["id"] == erwartet


def test_optionen_schliessen_vorhandene_und_notiz_passkeys_aus():
    c = _passwortkonto()
    g = Geraet()
    _hinzufuegen(c, g)
    notiz = {"key_version": 1, "kdf": "pbkdf2-sha256", "iterations": 600_000,
             "salt": base64.b64encode(bytes(16)).decode(),
             "passkey": {"credential_id": "Tm90aXotUGFzc2tleS0xMjM0", "prf_salt": base64.b64encode(bytes(32)).decode(),
                         "wrapped_key": base64.b64encode(bytes(40)).decode(), "label": "Mac"}}
    assert c.put("/api/notes/keys", json=notiz).status_code == 200
    pk = c.post("/api/account/passkeys/options").json()["public_key"]
    assert {e["id"] for e in pk["excludeCredentials"]} == {b64url(g.kennung), "Tm90aXotUGFzc2tleS0xMjM0"}
    # Der Notiz-Passkey taucht in der Liste als „auch für Notizen“ auf, sobald
    # er dieselbe Kennung trägt.
    assert c.get("/api/account/passkeys").json()["passkeys"][0]["notes"] is False


def test_hinzufuegen_braucht_ein_konto():
    c = TestClient(app)
    assert c.post("/api/account/passkeys/options").status_code == 401
    assert c.get("/api/account/passkeys").status_code == 401


def test_challenge_eines_anderen_kontos():
    a, b = _passwortkonto("a@example.org"), _passwortkonto("b@example.org")
    opt = a.post("/api/account/passkeys/options").json()
    r = b.post("/api/account/passkeys", json={"credential": Geraet().anlegen(opt), "label": "x"})
    assert r.status_code == 400


def test_derselbe_passkey_nicht_zweimal():
    c = _passwortkonto()
    g = Geraet()
    assert _hinzufuegen(c, g).status_code == 200
    assert _hinzufuegen(c, g).status_code == 409


def test_letzter_weg_ins_konto_bleibt():
    g = Geraet()
    c, _ = _registrieren(g)
    pid = c.get("/api/account/passkeys").json()["passkeys"][0]["id"]
    assert c.delete(f"/api/account/passkeys/{pid}").status_code == 409
    assert _hinzufuegen(c, Geraet(2)).status_code == 200
    r = c.delete(f"/api/account/passkeys/{pid}")
    assert r.status_code == 200
    assert len(r.json()["passkeys"]) == 1
    assert _anmelden(g)[1].status_code == 401


def test_passwortkonto_darf_den_einzigen_passkey_entfernen():
    c = _passwortkonto()
    _hinzufuegen(c, Geraet())
    pid = c.get("/api/account/passkeys").json()["passkeys"][0]["id"]
    assert c.delete(f"/api/account/passkeys/{pid}").status_code == 200


def test_fremden_passkey_nicht_entfernen():
    a = _passwortkonto("a@example.org")
    _hinzufuegen(a, Geraet())
    pid = a.get("/api/account/passkeys").json()["passkeys"][0]["id"]
    b = _passwortkonto("b@example.org")
    assert b.delete(f"/api/account/passkeys/{pid}").status_code == 404


# ---- Bestätigen, Löschen, Zurückholen ---------------------------------------------------

def test_passkey_konto_loescht_sich_mit_passkey():
    g = Geraet()
    c, _ = _registrieren(g)
    uid = c.get("/api/auth/me").json()["id"]
    ohne = c.request("DELETE", "/api/account", json={"current_password": ""})
    assert ohne.status_code == 400
    assert "Passkey" in ohne.json()["detail"]
    opt = c.post("/api/auth/passkey/login/options").json()
    r = c.request("DELETE", "/api/account", json={"passkey": g.bestaetigen(opt)})
    assert r.status_code == 204, r.text
    s = Store(RATSLOTSE_DB)
    for tabelle, spalte in USER_OWNED_TABLES:
        n = s._conn.execute(f"SELECT COUNT(*) FROM {tabelle} WHERE {spalte} = ?", (uid,)).fetchone()[0]
        assert n == 0, tabelle
    s.close()


def test_loeschen_nicht_mit_dem_passkey_eines_anderen_kontos():
    fremd = Geraet(2)
    _registrieren(fremd, "fremd@example.org")
    c, _ = _registrieren(Geraet(), "eigen@example.org")
    opt = c.post("/api/auth/passkey/login/options").json()
    r = c.request("DELETE", "/api/account", json={"passkey": fremd.bestaetigen(opt)})
    assert r.status_code == 400
    assert c.get("/api/auth/me").status_code == 200


def test_mit_mailversand_bleibt_das_konto_unbestaetigt(monkeypatch):
    """Tim 11.11.2026: Auch mit Passkey erst die Adresse bestätigen."""
    from app.routers import auth as auth_mod

    monkeypatch.setattr(get_settings(), "resend_api_key", "re_test")
    monkeypatch.setattr(auth_mod, "send_email", lambda *a, **k: "mid")
    c, user = _registrieren(Geraet())
    assert user["status"] == "pending" and user["email_verified"] is False
    assert c.get("/api/account/passkeys").status_code == 403


def test_zurueckholen_per_passwort_link_entfernt_fremde_passkeys():
    """Wer ein Konto auf eine fremde Adresse anlegt, kommt nicht weiter als
    bis zur Bestätigung — holt die Besitzerin es sich über „Passwort
    vergessen" zurück, ist sein Passkey kein Weg mehr hinein."""
    g = Geraet()
    _, user = _registrieren(g, "opfer@example.org")
    s = Store(RATSLOTSE_DB)
    s.set_email_verified(user["id"], False)
    roh = "reset-token-fuer-den-test"
    s.create_password_reset(user["id"], hashlib.sha256(roh.encode()).hexdigest(),
                            (datetime.utcnow() + timedelta(hours=1)).isoformat(timespec="seconds"))
    s.close()
    r = TestClient(app).post("/api/auth/reset-password", json={"token": roh, "new_password": "neues-passwort-1"})
    assert r.status_code == 200, r.text
    assert _anmelden(g)[1].status_code == 401
