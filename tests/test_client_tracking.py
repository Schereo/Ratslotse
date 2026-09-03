"""Womit greift jemand zu — Browser oder App? (Admin-Auswertung 09/2026)

Geprüft wird die ganze Kette: Header → Normalisierung → ``user_activity`` →
Admin-Antworten. Und der eine Nebeneffekt, an dem hier am meisten hängt: Die
Anmeldung muss die native App weiterhin als solche erkennen, obwohl sie sich
jetzt ``ios`` statt ``app`` nennt.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web" / "backend"))

# `fresh_dbs` MUSS mit: Die autouse-Fixture wirkt nur in dem Modul, in dem sie
# steht. Ohne sie teilen sich die Tests hier eine Datenbank — die zweite
# Registrierung liefe in 409, es käme kein Cookie, und alles Weitere wäre 401.
# Die `client`-Fixture wird dagegen hier neu definiert statt importiert: Ein
# importierter Fixture-Name kollidiert mit dem gleichnamigen Testparameter
# (ruff F811), und sie ist ohnehin nur ein Einzeiler.
from tests.test_backend_api import _register, app, fresh_dbs  # noqa: E402,F401


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------- Header ---

@pytest.mark.parametrize("header,erwartet", [
    (None, "web"),
    ("", "web"),
    ("ios", "ios"),
    ("IOS", "ios"),          # Groß-/Kleinschreibung darf nicht zählen
    ("  android  ", "android"),
    ("app", "app"),          # Altwert bleibt gültig
    ("kaputt", "web"),       # Fremdwerte werden nicht durchgereicht …
    ("'; DROP TABLE", "web"),  # … erst recht keine, die nach Angriff aussehen
])
def test_client_kind_bildet_streng_ab(header, erwartet):
    from starlette.datastructures import Headers
    from starlette.requests import Request

    from app.clients import client_kind

    roh = [(b"x-client", header.encode())] if header is not None else []
    request = Request({"type": "http", "headers": Headers(raw=roh).raw})
    assert client_kind(request) == erwartet


def test_native_app_bekommt_weiter_ein_token(client):
    """Der Regressionstest, an dem hier am meisten hängt.

    ``_is_app_client`` prüfte auf ``== "app"``. Seit die iOS-App ``ios``
    schickt, hätte diese Prüfung sie für einen Browser gehalten — die Anmeldung
    hätte nur noch ein Cookie gesetzt, und die App stünde nach dem nächsten
    Start abgemeldet da (Cookies überleben dort nicht).
    """
    _register(client)
    for marke in ("app", "ios", "android"):
        r = client.post("/api/auth/login",
                        json={"email": "admin@test.de", "password": "password123"},
                        headers={"X-Client": marke})
        assert r.status_code == 200, marke
        assert r.json().get("access_token"), f"{marke} bekam kein Bearer-Token"
    # Der Browser dagegen bekommt es weiterhin NICHT in den Rumpf gelegt.
    r = client.post("/api/auth/login",
                    json={"email": "admin@test.de", "password": "password123"})
    assert r.status_code == 200 and not r.json().get("access_token")


# ------------------------------------------------------------- Statistik ---

def test_zugriffe_werden_je_client_getrennt_gezaehlt(client):
    """Dieselbe Person, derselbe Tag, zwei Geräte → zwei Zeilen.

    Genau dafür steht ``client`` im Primärschlüssel. Stünde er nicht dort,
    gewänne der Client, der zufällig zuerst kam, und die Aufteilung wäre
    strukturell nicht messbar.
    """
    _register(client)
    client.get("/api/auth/me")                                  # web
    client.get("/api/auth/me", headers={"X-Client": "ios"})     # App
    client.get("/api/auth/me", headers={"X-Client": "ios"})     # App, nochmal

    admin = client.get("/api/auth/me").json()
    detail = client.get(f"/api/admin/users/{admin['id']}").json()
    assert detail["clients"]["ios"] >= 2
    assert detail["clients"]["web"] >= 1

    zeile = next(u for u in client.get("/api/admin/users").json() if u["id"] == admin["id"])
    assert zeile["clients"]["ios"] >= 2 and zeile["clients"]["web"] >= 1


def test_registrierung_haelt_den_client_fest(client):
    """Womit jemand HERKOMMT ist eine andere Frage als was er DANN benutzt."""
    TestClient(app).post("/api/auth/register",
                         json={"email": "appler@example.org", "password": "password123"},
                         headers={"X-Client": "ios"})
    _register(client)  # der Admin selbst registriert sich im Browser

    users = client.get("/api/admin/users").json()
    assert next(u for u in users if u["email"] == "appler@example.org")["signup_client"] == "ios"
    assert next(u for u in users if u["email"] == "admin@test.de")["signup_client"] == "web"


def test_wachstum_zeigt_beide_aufteilungen(client):
    _register(client)
    client.get("/api/auth/me", headers={"X-Client": "ios"})
    b = client.get("/api/admin/stats/growth?range=30d").json()

    assert {"clients", "clients_both", "signup_clients"} <= set(b)
    nutzung = {c["client"]: c for c in b["clients"]}
    assert nutzung["ios"]["n"] >= 1
    # `users` zählt Konten, nicht Zugriffe — die ehrlichere Zahl.
    assert nutzung["ios"]["users"] == 1
    assert {c["client"] for c in b["signup_clients"]} >= {"web"}


def test_jedes_konto_zaehlt_in_der_aufteilung_genau_einmal(tmp_path):
    """Die Falle, in die die erste Fassung gelaufen ist.

    Zählte man je Client die verschiedenen Konten, stünde ein Konto, das App
    UND Web benutzt, in beiden Zahlen: Die Summe wäre größer als der Bestand,
    und der Anteilsbalken darüber behauptete eine Aufteilung, die keine ist.
    Deshalb entscheidet je Konto der meistgenutzte Client — und wie viele
    überhaupt wechseln, steht getrennt daneben.
    """
    from kern.store import Store

    store = Store(str(tmp_path / "s.sqlite"))
    try:
        for _ in range(9):
            store.record_activity(1, "session", "ios")
        for _ in range(2):
            store.record_activity(1, "session", "web")   # dasselbe Konto, auch im Browser
        store.record_activity(2, "session", "web")
        store.record_activity(3, "session", "android")
        # Altbestand darf an der Kür nicht teilnehmen: ungemessen ist keine Plattform.
        store.record_activity(4, "session", "unknown")

        ergebnis = store.client_split(30)
        konten = {c["client"]: c["users"] for c in ergebnis["clients"]}
        assert konten == {"ios": 1, "web": 1, "android": 1}
        assert sum(konten.values()) == 3          # 3 gemessene Konten, nicht 4
        assert ergebnis["both"] == 1            # Konto 1 nutzt beides
        assert "unknown" not in konten

        # Die Zugriffszahl bleibt die Zugriffszahl — sie darf sich nicht ändern.
        zugriffe = {c["client"]: c["n"] for c in ergebnis["clients"]}
        assert zugriffe["ios"] == 9 and zugriffe["web"] == 3
    finally:
        store.close()


# ------------------------------------------------------------- Migration ---

def test_migration_baut_user_activity_um(tmp_path):
    """Bestandsdaten überleben den PK-Umbau — und behaupten nicht „web".

    Eine Altzeile stammt aus der Zeit vor der Messung. Sie als ``web`` zu
    übernehmen wäre in der Statistik nicht von einer echten Messung zu
    unterscheiden; deshalb ``unknown``.
    """
    import sqlite3

    from kern.store import Store

    db = tmp_path / "alt.sqlite"
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE user_activity (
            owner_id INTEGER NOT NULL, day TEXT NOT NULL, feature TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 1, PRIMARY KEY (owner_id, day, feature));
        INSERT INTO user_activity VALUES (7, '2026-08-01', 'session', 42);
    """)
    con.commit()
    con.close()

    store = Store(str(db))
    try:
        zeilen = store._conn.execute(
            "SELECT owner_id, client, count FROM user_activity").fetchall()
        assert [tuple(r) for r in zeilen] == [(7, "unknown", 42)]
        # Und der neue Schlüssel greift: derselbe Tag, anderer Client → eigene Zeile.
        store.record_activity(7, "session", "ios")
        store.record_activity(7, "session", "web")
        store.record_activity(7, "session", "web")
        assert store.client_usage(7) == {"unknown": 42, "ios": 1, "web": 2}
    finally:
        store.close()


def test_migrierte_und_frische_form_sind_gleich(tmp_path):
    """Der Fehler, den keine gewöhnliche Testsuite sieht (vgl. #897).

    ``CREATE TABLE`` und die Migration sind zwei getrennt geschriebene DDLs für
    dieselbe Tabelle. Driften sie auseinander, läuft alles grün: Tests und CI
    arbeiten auf einer FRISCHEN Datenbank, dev und Prod auf einer GEWACHSENEN.
    Der Widerspruch zeigt sich erst im Betrieb — hier deshalb beide Formen
    nebeneinander.
    """
    import sqlite3

    from kern.store import Store

    def form(pfad) -> tuple:
        con = sqlite3.connect(pfad)
        try:
            spalten = [(r[1], r[2], r[5]) for r in con.execute("PRAGMA table_info(user_activity)")]
        finally:
            con.close()
        return tuple(spalten)   # Name, Typ, Stellung im Primärschlüssel

    frisch = tmp_path / "frisch.sqlite"
    Store(str(frisch)).close()

    gewachsen = tmp_path / "gewachsen.sqlite"
    con = sqlite3.connect(gewachsen)
    con.executescript("""
        CREATE TABLE user_activity (
            owner_id INTEGER NOT NULL, day TEXT NOT NULL, feature TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 1, PRIMARY KEY (owner_id, day, feature));
    """)
    con.commit()
    con.close()
    Store(str(gewachsen)).close()

    assert form(frisch) == form(gewachsen), (
        "CREATE TABLE und Migration bauen user_activity verschieden — "
        "auf dev/Prod hätte die Tabelle eine andere Form als in jedem Test."
    )
