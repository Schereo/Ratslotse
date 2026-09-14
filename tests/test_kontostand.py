"""Der Kontostand trennt seit 09/2026 zwei Wartezustände.

``pending`` heißt „E-Mail noch nicht bestätigt" — das Konto wartet auf sich
selbst. ``disabled`` heißt „von einem Admin abgeschaltet" — es wartet auf
jemand anderen. Vorher trugen beide denselben Wert, und das war nicht nur
unscharf:

* Der Apple-Verknüpfungspfad las ``pending`` als „unbestätigt" und schaltete
  frei — ein gesperrtes Konto hob damit seine Sperre selbst auf (#1240).
* Die iOS-App zeigte einer gesperrten Person „Bestätige deine E-Mail-Adresse",
  was sie längst getan hatte.

Diese Datei hält die Trennung fest: die Migration des Bestands, die
Kompatibilität mit der ausgelieferten App und dass die Fälle nicht wieder
zusammenfallen.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1] / "web" / "backend"
sys.path.insert(0, str(_BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from kern.store import Store  # noqa: E402

RATSLOTSE_DB = os.environ["RATSLOTSE_DB"]
COUNCIL_DB = os.environ["COUNCIL_DB"]
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


def _registrieren(client, email, passwort=PASSWORT):
    r = client.post("/api/auth/register", json={"display_name": "Testkonto", "email": email, "password": passwort})
    assert r.status_code == 201, r.text
    return r.json()


def _stand(email: str) -> str:
    store = Store(RATSLOTSE_DB)
    try:
        return store.get_web_user_by_email(email)["status"]
    finally:
        store.close()


# --- Migration des Bestands -------------------------------------------------

def test_migration_hebt_abgeschaltete_konten_auf_disabled(tmp_path):
    """Rückwirkend unterscheidbar sind die beiden nur an einem Merkmal: Wer
    bestätigt hat und trotzdem nicht aktiv ist, wurde abgeschaltet."""
    pfad = tmp_path / "alt.sqlite"
    store = Store(pfad)
    try:
        abgeschaltet = store.create_web_user("weg@example.org", "x", "user", "active",
                                             email_verified=True)
        wartet = store.create_web_user("neu@example.org", "x", "user", "pending",
                                       email_verified=False)
        # Den Altzustand herstellen: abgeschaltet == bestätigt + pending.
        store._conn.execute("UPDATE web_users SET status = 'pending' WHERE id = ?",
                            (abgeschaltet,))
        # Und eine Zeile mit dem Phantom-Wert aus dem Vertrag.
        blockiert = store.create_web_user("alt@example.org", "x", "user", "active",
                                          email_verified=True)
        store._conn.execute("UPDATE web_users SET status = 'blocked' WHERE id = ?",
                            (blockiert,))
        store._conn.execute("DELETE FROM migration_marks WHERE marke = ?",
                            ("kontostand_disabled_2026_09",))
        store._conn.commit()
    finally:
        store.close()

    store = Store(pfad)          # zweites Öffnen: die Migration läuft
    try:
        assert store.get_web_user_by_id(abgeschaltet)["status"] == "disabled"
        assert store.get_web_user_by_id(blockiert)["status"] == "disabled"
        # Wer WIRKLICH auf die eigene Bestätigung wartet, bleibt pending.
        assert store.get_web_user_by_id(wartet)["status"] == "pending"
    finally:
        store.close()


def test_migration_laeuft_genau_einmal(tmp_path):
    """Mit Marke, nicht bei jedem Start — und das ist kein Geschmack:
    ``verify_email`` setzt erst ``email_verified``, dann den Status. Dazwischen
    sieht eine ganz normale Bestätigung wie ein abgeschaltetes Konto aus. Liefe
    der Schritt bei jedem Öffnen, könnte er genau dort zuschlagen."""
    pfad = tmp_path / "einmal.sqlite"
    store = Store(pfad)
    try:
        uid = store.create_web_user("x@example.org", "x", "user", "active",
                                    email_verified=True)
    finally:
        store.close()

    store = Store(pfad)
    try:
        # Den Schwebezustand aus der Mitte von verify_email nachstellen.
        store._conn.execute("UPDATE web_users SET status = 'pending' WHERE id = ?", (uid,))
        store._conn.commit()
    finally:
        store.close()

    store = Store(pfad)          # Migration ist schon abgehakt → rührt nichts an
    try:
        assert store.get_web_user_by_id(uid)["status"] == "pending"
    finally:
        store.close()


# --- Admin ------------------------------------------------------------------

def test_admin_schaltet_auf_disabled(client):
    _registrieren(client, "admin@test.de")
    from scripts.grant_admin import grant_admin
    grant_admin("admin@test.de", RATSLOTSE_DB)
    _registrieren(TestClient(app), "opfer@example.org")
    opfer = next(u for u in client.get("/api/admin/users").json()
                 if u["email"] == "opfer@example.org")

    r = client.put(f"/api/admin/users/{opfer['id']}/status", json={"status": "disabled"})
    assert r.status_code == 200 and r.json()["status"] == "disabled"
    assert _stand("opfer@example.org") == "disabled"

    r = client.put(f"/api/admin/users/{opfer['id']}/status", json={"status": "active"})
    assert r.status_code == 200 and r.json()["status"] == "active"


def test_die_ausgelieferte_app_darf_weiter_pending_schicken(client):
    """Die Admin-Ansicht im App Store sendet beim „Sperren" den alten Wert.
    Ein 400 hieße: Sperren geht aus der App nicht mehr. Gespeichert wird
    trotzdem der neue Wert — sonst entstünde die Doppelbedeutung neu."""
    _registrieren(client, "admin@test.de")
    from scripts.grant_admin import grant_admin
    grant_admin("admin@test.de", RATSLOTSE_DB)
    _registrieren(TestClient(app), "opfer@example.org")
    opfer = next(u for u in client.get("/api/admin/users").json()
                 if u["email"] == "opfer@example.org")

    r = client.put(f"/api/admin/users/{opfer['id']}/status", json={"status": "pending"})
    assert r.status_code == 200
    assert r.json()["status"] == "disabled"
    assert _stand("opfer@example.org") == "disabled"


def test_unbekannter_status_wird_abgewiesen(client):
    _registrieren(client, "admin@test.de")
    from scripts.grant_admin import grant_admin
    grant_admin("admin@test.de", RATSLOTSE_DB)
    _registrieren(TestClient(app), "opfer@example.org")
    opfer = next(u for u in client.get("/api/admin/users").json()
                 if u["email"] == "opfer@example.org")
    r = client.put(f"/api/admin/users/{opfer['id']}/status", json={"status": "geloescht"})
    assert r.status_code == 400


# --- Was das Konto danach zu sehen bekommt ---------------------------------

def test_ein_abgeschaltetes_konto_hoert_nicht_es_solle_die_mail_bestaetigen(client):
    """Der Satz war der sichtbare Teil des Fehlers: Die Person HAT bestätigt."""
    _registrieren(client, "admin@test.de")
    from scripts.grant_admin import grant_admin
    grant_admin("admin@test.de", RATSLOTSE_DB)
    opfer_client = TestClient(app)
    _registrieren(opfer_client, "opfer@example.org")
    opfer = next(u for u in client.get("/api/admin/users").json()
                 if u["email"] == "opfer@example.org")
    client.put(f"/api/admin/users/{opfer['id']}/status", json={"status": "disabled"})

    r = opfer_client.get("/api/topics")
    assert r.status_code == 403
    assert "deaktiviert" in r.json()["detail"]
    assert "bestätige" not in r.json()["detail"].lower()

    # Und das Konto trägt den Stand auch nach außen, damit die Oberflächen
    # den richtigen Bildschirm wählen können.
    me = opfer_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["status"] == "disabled" and me.json()["email_verified"] is True


def test_ein_unbestaetigtes_konto_hoert_weiterhin_es_solle_bestaetigen(client, monkeypatch):
    """Die Gegenprobe — der andere Wartezustand behält seinen Satz."""
    store = Store(RATSLOTSE_DB)
    try:
        store.create_web_user("wartet@example.org", "x", "user", "pending",
                              email_verified=False)
    finally:
        store.close()
    from app.security import create_access_token
    store = Store(RATSLOTSE_DB)
    try:
        uid = store.get_web_user_by_email("wartet@example.org")["id"]
    finally:
        store.close()
    c = TestClient(app)
    c.headers["Authorization"] = f"Bearer {create_access_token(uid, 0)}"
    r = c.get("/api/topics")
    assert r.status_code == 403
    assert "bestätige" in r.json()["detail"].lower()


def test_apple_anmeldung_laesst_ein_disabled_konto_gesperrt(client):
    """Das Loch aus #1240, jetzt am Modell statt an einer Zusatzprüfung:
    `disabled` ist kein `pending`, der Verknüpfungspfad greift gar nicht."""
    _registrieren(client, "admin@test.de")
    from scripts.grant_admin import grant_admin
    grant_admin("admin@test.de", RATSLOTSE_DB)
    _registrieren(TestClient(app), "gesperrt@example.org")
    ziel = next(u for u in client.get("/api/admin/users").json()
                if u["email"] == "gesperrt@example.org")
    client.put(f"/api/admin/users/{ziel['id']}/status", json={"status": "disabled"})

    store = Store(RATSLOTSE_DB)
    try:
        konto = store.get_web_user_by_id(ziel["id"])
        # Genau der Zustand, den der Apple-Pfad früher freigeschaltet hätte.
        assert konto["status"] == "disabled" and konto["email_verified"] == 1
    finally:
        store.close()
