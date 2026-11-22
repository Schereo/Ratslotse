"""Verschlüsselte Notizen (``web/backend/app/routers/notes.py``,
``docs/plan-notizen-verschluesselt.md``): Der Server speichert und liefert
nur Blobs — er prüft Form, Größe, Version und Besitz, nie den Inhalt.

Das Ver- und Entschlüsseln selbst prüft ``web/frontend/lib/notiz-krypto.test.ts``
mit festen Testvektoren.
"""
from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from kern.store import USER_OWNED_TABLES, Store  # noqa: E402

RATSLOTSE_DB = os.environ["RATSLOTSE_DB"]


def b64(n: int, fill: int = 7) -> str:
    return base64.b64encode(bytes([fill]) * n).decode()


KEYS = {"key_version": 1, "kdf": "pbkdf2-sha256", "iterations": 600_000, "salt": b64(16),
        "wrapped_passphrase": b64(40, 1), "wrapped_recovery": b64(40, 2)}
NOTE = {"iv": b64(12), "ciphertext": b64(200, 9), "key_version": 1, "version": 0}
ZIEL = "/api/notes/agenda_item/4654|Ö 11.1/note"


@pytest.fixture(autouse=True)
def frisch(monkeypatch):
    for suffix in ("", "-wal", "-shm"):
        Path(RATSLOTSE_DB + suffix).unlink(missing_ok=True)
    monkeypatch.setenv("FEATURE_FLAGS", "notizen")
    yield


def _konto(email: str = "notiz@example.org") -> TestClient:
    c = TestClient(app)
    r = c.post("/api/auth/register", json={"display_name": "Notiz", "email": email, "password": "password123"})
    assert r.status_code == 201, r.text
    c.post("/api/auth/login", json={"email": email, "password": "password123"})
    return c


def test_ohne_schalter_gibt_es_die_endpunkte_nicht(monkeypatch):
    c = _konto()
    monkeypatch.setenv("FEATURE_FLAGS", "")
    assert c.get("/api/notes/keys").status_code == 404


def test_ohne_konto_kein_zugang():
    assert TestClient(app).get("/api/notes/keys").status_code == 401


def test_einrichten_einmal_dann_nur_neu_verpacken():
    c = _konto()
    assert c.get("/api/notes/keys").json() == {"configured": False, "keys": None, "passkeys": []}
    r = c.put("/api/notes/keys", json=KEYS)
    assert r.status_code == 200 and r.json()["keys"]["wrapped_recovery"] == KEYS["wrapped_recovery"]
    # Zweites Einrichten überschreibt nichts.
    assert c.put("/api/notes/keys", json={**KEYS, "wrapped_recovery": b64(40, 3)}).status_code == 409
    # Passphrase wechseln: nur die eine Verpackung, der Code bleibt.
    neu = {k: v for k, v in KEYS.items() if k != "wrapped_recovery"} | {"wrapped_passphrase": b64(40, 4), "salt": b64(16, 5)}
    r = c.put("/api/notes/keys", json=neu)
    assert r.status_code == 200
    k = r.json()["keys"]
    assert (k["wrapped_passphrase"], k["salt"], k["wrapped_recovery"]) == (b64(40, 4), b64(16, 5), KEYS["wrapped_recovery"])
    assert c.put("/api/notes/keys", json={**neu, "key_version": 2}).status_code == 409


@pytest.mark.parametrize("feld,wert,code", [
    ("iterations", 1000, 422),          # zu billig für die Passphrase
    ("salt", b64(8), 422),
    ("wrapped_passphrase", "kein base64!", 422),
])
def test_schluessel_form_wird_geprueft(feld, wert, code):
    assert _konto().put("/api/notes/keys", json={**KEYS, feld: wert}).status_code == code


def test_notiz_mit_version_statt_stillem_ueberschreiben():
    c = _konto()
    c.put("/api/notes/keys", json=KEYS)
    r = c.put(ZIEL, json=NOTE)
    assert r.status_code == 200 and r.json()["version"] == 1
    # Ein zweites Gerät mit altem Stand bekommt 409 und den aktuellen Stand.
    r = c.put(ZIEL, json={**NOTE, "ciphertext": b64(10, 1)})
    assert r.status_code == 409 and r.json()["detail"]["current"]["version"] == 1
    r = c.put(ZIEL, json={**NOTE, "ciphertext": b64(10, 1), "version": 1})
    assert r.status_code == 200 and r.json()["version"] == 2
    liste = c.get("/api/notes", params={"target_kind": "agenda_item", "target_key": "4654|Ö 11.1"}).json()["notes"]
    assert [(n["kind"], n["version"], n["ciphertext"]) for n in liste] == [("note", 2, b64(10, 1))]
    assert c.delete(ZIEL).status_code == 204
    assert c.get("/api/notes").json()["notes"] == []


def test_ohne_schluessel_oder_mit_alter_schluesselversion_keine_notiz():
    c = _konto()
    assert c.put(ZIEL, json=NOTE).status_code == 409
    c.put("/api/notes/keys", json=KEYS)
    assert c.put(ZIEL, json={**NOTE, "key_version": 2}).status_code == 409


@pytest.mark.parametrize("pfad,body,code", [
    ("/api/notes/agenda_item/4654/note", NOTE, 422),                 # Punkt ohne Nummer
    ("/api/notes/decision/abc/note", NOTE, 422),
    ("/api/notes/session/4654/note", NOTE, 422),                     # unbekannte Zielart
    (ZIEL, {**NOTE, "iv": b64(16)}, 422),                            # IV muss 12 Byte haben
    (ZIEL, {**NOTE, "ciphertext": "{\"text\": \"Klartext\"}"}, 422),  # Klartext ist kein Base64
    (ZIEL, {**NOTE, "ciphertext": b64(16 * 1024 + 1)}, 413),
])
def test_form_und_groesse(pfad, body, code):
    c = _konto()
    c.put("/api/notes/keys", json=KEYS)
    assert c.put(pfad, json=body).status_code == code


def test_fremde_notizen_bleiben_fremd():
    a = _konto("a@example.org")
    a.put("/api/notes/keys", json=KEYS)
    a.put(ZIEL, json=NOTE)
    b = _konto("b@example.org")
    assert b.get("/api/notes/keys").json()["configured"] is False
    assert b.get("/api/notes").json()["notes"] == []
    b.put("/api/notes/keys", json=KEYS)
    assert b.put(ZIEL, json=NOTE).json()["version"] == 1      # eigene Notiz, eigene Version


def test_neu_anfangen_loescht_schluessel_und_notizen():
    c = _konto()
    c.put("/api/notes/keys", json=KEYS)
    c.put(ZIEL, json=NOTE)
    c.put("/api/notes/decision/8525/note", json=NOTE)
    assert c.delete("/api/notes/keys").json() == {"deleted": 2}
    assert c.get("/api/notes/keys").json()["configured"] is False


def test_konto_loeschung_raeumt_alle_drei_tabellen_ab():
    for tabelle in ("note_keys", "note_passkeys", "user_notes"):
        assert (tabelle, "owner_id") in USER_OWNED_TABLES
    c = _konto()
    c.put("/api/notes/keys", json=NUR_PASSKEY)
    c.put(ZIEL, json=NOTE)
    store = Store(RATSLOTSE_DB)
    uid = store._conn.execute("SELECT id FROM web_users WHERE email = 'notiz@example.org'").fetchone()[0]
    store.delete_web_user(uid)
    assert store.get_note_keys(uid) is None and store.get_notes(uid) == [] and store.get_note_passkeys(uid) == []


# ---- Passkeys (seit 11/2026: einrichten ohne Passphrase und ohne Code) ----------

def passkey(n: int = 1) -> dict:
    return {"credential_id": f"Q3JlZGVudGlhbC0{n}xxxxxxxx", "prf_salt": b64(32, n), "wrapped_key": b64(40, 10 + n),
            "label": f"Gerät {n}"}


NUR_PASSKEY = {k: KEYS[k] for k in ("key_version", "kdf", "iterations", "salt")} | {"passkey": passkey(1)}


def test_einrichten_nur_mit_passkey():
    c = _konto()
    r = c.put("/api/notes/keys", json=NUR_PASSKEY)
    assert r.status_code == 200, r.text
    z = r.json()
    assert z["configured"] is True
    assert z["keys"]["wrapped_passphrase"] is None and z["keys"]["wrapped_recovery"] is None
    assert [(p["credential_id"], p["wrapped_key"], p["label"]) for p in z["passkeys"]] == \
        [(passkey(1)["credential_id"], passkey(1)["wrapped_key"], "Gerät 1")]
    assert c.get("/api/notes/keys").json() == z
    # Ohne Passphrase und ohne Passkey gibt es nichts zu verpacken.
    leer = _konto("leer@example.org")
    assert leer.put("/api/notes/keys", json={k: KEYS[k] for k in ("key_version", "kdf", "iterations", "salt")}).status_code == 422
    # Notizen gehen mit einem Passkey genauso.
    assert c.put(ZIEL, json=NOTE).json()["version"] == 1


def test_die_app_richtet_weiter_mit_passphrase_und_code_ein():
    """Die ausgelieferte iOS-App kennt keine Passkeys — ihr Weg muss bleiben."""
    z = _konto().put("/api/notes/keys", json=KEYS).json()
    assert z["keys"]["wrapped_passphrase"] == KEYS["wrapped_passphrase"] and z["passkeys"] == []


def test_weitere_passkeys_code_und_passphrase_nachtraeglich():
    c = _konto()
    c.put("/api/notes/keys", json=NUR_PASSKEY)
    z = c.post("/api/notes/passkeys", json={**passkey(2), "key_version": 1}).json()
    assert [p["label"] for p in z["passkeys"]] == ["Gerät 1", "Gerät 2"]
    # Derselbe Passkey noch einmal ersetzt seine Verpackung, statt einen zweiten anzulegen.
    z = c.post("/api/notes/passkeys", json={**passkey(2), "wrapped_key": b64(40, 99), "key_version": 1}).json()
    assert len(z["passkeys"]) == 2 and z["passkeys"][1]["wrapped_key"] == b64(40, 99)
    assert c.post("/api/notes/passkeys", json={**passkey(3), "key_version": 2}).status_code == 409
    # Notfall-Code und Passphrase lassen sich später dazunehmen.
    z = c.put("/api/notes/keys/recovery", json={"key_version": 1, "wrapped_recovery": b64(40, 7)}).json()
    assert z["keys"]["wrapped_recovery"] == b64(40, 7)
    neu = {k: KEYS[k] for k in ("key_version", "kdf", "iterations", "salt")} | {"wrapped_passphrase": b64(40, 8)}
    z = c.put("/api/notes/keys", json=neu).json()
    assert z["keys"]["wrapped_passphrase"] == b64(40, 8) and len(z["passkeys"]) == 2
    # Ein zweites Einrichten mit Passkey überschreibt nichts.
    assert c.put("/api/notes/keys", json=NUR_PASSKEY).status_code == 409


def test_der_letzte_weg_zu_den_notizen_bleibt():
    c = _konto()
    z = c.put("/api/notes/keys", json=NUR_PASSKEY).json()
    erster = z["passkeys"][0]["id"]
    r = c.delete(f"/api/notes/passkeys/{erster}")
    assert r.status_code == 409 and "letzte" in r.json()["detail"]
    zweiter = c.post("/api/notes/passkeys", json={**passkey(2), "key_version": 1}).json()["passkeys"][1]["id"]
    assert [p["id"] for p in c.delete(f"/api/notes/passkeys/{erster}").json()["passkeys"]] == [zweiter]
    assert c.delete(f"/api/notes/passkeys/{zweiter}").status_code == 409
    # Mit Notfall-Code darf auch der letzte Passkey gehen.
    c.put("/api/notes/keys/recovery", json={"key_version": 1, "wrapped_recovery": b64(40, 7)})
    assert c.delete(f"/api/notes/passkeys/{zweiter}").json()["passkeys"] == []
    assert c.delete("/api/notes/passkeys/999999").status_code == 404


def test_fremde_passkeys_bleiben_fremd():
    a = _konto("a@example.org")
    pid = a.put("/api/notes/keys", json=NUR_PASSKEY).json()["passkeys"][0]["id"]
    b = _konto("b@example.org")
    b.put("/api/notes/keys", json=KEYS)
    assert b.delete(f"/api/notes/passkeys/{pid}").status_code == 404
    assert b.get("/api/notes/keys").json()["passkeys"] == []


@pytest.mark.parametrize("feld,wert", [
    ("credential_id", "kurz"),
    ("credential_id", "kein base64url!!!!!!!"),
    ("prf_salt", b64(16)),
    ("wrapped_key", b64(32)),
    ("label", "x" * 61),
])
def test_passkey_form_wird_geprueft(feld, wert):
    body = NUR_PASSKEY | {"passkey": {**passkey(1), feld: wert}}
    assert _konto().put("/api/notes/keys", json=body).status_code == 422


def test_neu_anfangen_loescht_auch_die_passkeys():
    c = _konto()
    c.put("/api/notes/keys", json=NUR_PASSKEY)
    c.delete("/api/notes/keys")
    assert c.get("/api/notes/keys").json() == {"configured": False, "keys": None, "passkeys": []}
    assert c.put("/api/notes/keys", json=NUR_PASSKEY).status_code == 200
