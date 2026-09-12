"""Mehrere Tipprunden (``web/backend/app/prediction/rounds.py``, 12.09.2026).

Eine Runde ist ein eigener Kreis: Spieler*innen, Tipps, Ergebnisse, Ränge,
Protokoll und der Cookie gehören ihr allein. Geteilt sind der Wahlabend, die
Listen und die Regeln. Die Hauptrunde (``ratswahl``) läuft OHNE Parameter —
jede Adresse von vorher bleibt gültig; jede andere Runde hängt an
``?round=<slug>``.

Dazu die Migration: Prod lief zwei Tage als EIN Spiel (``CHECK (id = 1)``,
keine ``game_id``-Spalten). Der Bestand muss nach dem Öffnen zur Hauptrunde
gehören, nicht verschwinden.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.deps import get_store, require_active  # noqa: E402
from app.election import mayor as mayor_module  # noqa: E402
from app.election import register  # noqa: E402
from app.election import service as election_service  # noqa: E402
from app.main import app  # noqa: E402
from app.prediction import rounds, service  # noqa: E402
from kern import features  # noqa: E402
from kern.store import Store  # noqa: E402

_TIPPSPIEL_FEATURE = features.Feature(
    key="tippspiel", description="Test-Registrierung.", fertig_wenn="s. tests/test_prediction_api.py")
ADMIN = {"id": 1, "role": "admin", "roles": ["admin"], "status": "active"}


@pytest.fixture(autouse=True)
def netzfrei(monkeypatch):
    monkeypatch.setattr(election_service, "live", lambda: election_service.probe(0))
    monkeypatch.setattr(mayor_module, "fetch", lambda force=False: mayor_module.probe(0))


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "tippspiel,wahlabend")
    monkeypatch.setitem(features.FEATURES, "tippspiel", _TIPPSPIEL_FEATURE)
    st = Store(tmp_path / "runden.sqlite")
    app.dependency_overrides[get_store] = lambda: st
    service.reset_all()
    yield st
    app.dependency_overrides.pop(get_store, None)
    app.dependency_overrides.pop(require_active, None)
    st.close()
    service.reset_all()


@pytest.fixture
def client(store):
    return TestClient(app)


def _voller_tipp() -> dict[str, int]:
    reg = register.load()
    tipp = {p.slug: 0 for p in reg.parties}
    tipp[max(reg.parties, key=lambda p: p.candidates_total).slug] = reg.seats
    return tipp


# ------------------------------------------------------------------ Registry

def test_die_hauptrunde_ist_ohne_parameter_und_die_einzige_gelistete():
    assert rounds.get(None) is rounds.ROUNDS[rounds.DEFAULT]
    assert rounds.get("ratswahl").is_default
    assert [r.slug for r in rounds.ROUNDS.values() if r.listed] == ["ratswahl"]
    assert rounds.get("gibt-es-nicht") is None
    assert rounds.public_path(rounds.get(None)) == "/tipp"
    assert rounds.public_path(rounds.get("vally")) == "/tipp?runde=vally"


# ------------------------------------------------------------------ Trennung

def test_runden_sehen_einander_nicht(client):
    haupt = TestClient(app)
    haupt.post("/api/tipp", json={"name": "Ismail", "seats": _voller_tipp()})
    vally = TestClient(app)
    r = vally.post("/api/tipp?round=vally", json={"name": "Nele", "seats": _voller_tipp()})
    assert r.status_code == 200
    assert r.json()["name"] == "Nele"

    haupt_stand = client.get("/api/tipp/stand").json()
    vally_stand = client.get("/api/tipp/stand?round=vally").json()
    assert [z["name"] for z in haupt_stand["rows"]] == ["Ismail"]
    assert [z["name"] for z in vally_stand["rows"]] == ["Nele"]
    assert client.get("/api/tipp/setup").json()["round"] == "ratswahl"
    vally_setup = client.get("/api/tipp/setup?round=vally").json()
    assert (vally_setup["round"], vally_setup["listed"], vally_setup["title"]) == ("vally", False, "Vallys Tippspiel")


def test_der_cookie_gehoert_zur_runde(client):
    """Wer in Vallys Runde beitritt, ist in der Hauptrunde niemand — und
    umgekehrt. Sonst hinge eine Person mit EINEM Cookie in beiden Kreisen."""
    c = TestClient(app)
    c.post("/api/tipp?round=vally", json={"name": "Nele"})
    assert "tipp_token_vally" in c.cookies
    assert "tipp_token" not in c.cookies
    assert c.get("/api/tipp/me?round=vally").status_code == 200
    assert c.get("/api/tipp/me").status_code == 401, "der Vally-Cookie gilt nicht in der Hauptrunde"

    # Dieselbe Person tritt zusätzlich der Hauptrunde bei — zwei Cookies, zwei Personen.
    c.post("/api/tipp", json={"name": "Nele"})
    assert "tipp_token" in c.cookies
    assert c.get("/api/tipp/me").json()["name"] == "Nele"
    assert c.get("/api/tipp/me?round=vally").json()["name"] == "Nele"


def test_gleicher_name_in_zwei_runden_bleibt_ungezaehlt(client):
    TestClient(app).post("/api/tipp", json={"name": "Merle"})
    r = TestClient(app).post("/api/tipp?round=vally", json={"name": "Merle"})
    assert r.json()["name"] == "Merle", "Doppelte zählen nur innerhalb einer Runde"
    r2 = TestClient(app).post("/api/tipp?round=vally", json={"name": "Merle"})
    assert r2.json()["name"] == "Merle (2)"


def test_unbekannte_runde_ist_404(client):
    assert client.get("/api/tipp/setup?round=gibt-es-nicht").status_code == 404
    assert client.post("/api/tipp?round=gibt-es-nicht", json={"name": "Xaver"}).status_code == 404
    assert client.get("/api/tipp/qr.png?round=gibt-es-nicht").status_code == 404


def test_qr_der_nebenrunde_ist_ein_bild_und_zeigt_auf_ihren_link(client):
    r = client.get("/api/tipp/qr.png?round=vally")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.content[1:4] == b"PNG"
    # Der Link steckt im Bild — statt zu dekodieren prüfen wir die eine
    # Stelle, die ihn baut: `rounds.public_path`.
    assert rounds.public_path(rounds.get("vally")) == "/tipp?runde=vally"


# ------------------------------------------------------------------ Admin je Runde

def test_admin_verwaltet_beide_runden_getrennt(client):
    TestClient(app).post("/api/tipp", json={"name": "Ismail", "seats": _voller_tipp()})
    TestClient(app).post("/api/tipp?round=vally", json={"name": "Nele", "seats": _voller_tipp()})
    reg = register.load()
    slug = reg.parties[0].slug

    app.dependency_overrides[require_active] = lambda: ADMIN
    try:
        stand = client.get("/api/tipp/admin/stand").json()
        assert [r["slug"] for r in stand["rounds"]] == ["ratswahl", "vally"]
        assert {r["slug"]: r["player_count"] for r in stand["rounds"]} == {"ratswahl": 1, "vally": 1}
        assert [p["name"] for p in stand["players"]] == ["Ismail"]
        vally = client.get("/api/tipp/admin/stand?round=vally").json()
        assert [p["name"] for p in vally["players"]] == ["Nele"]

        # Ein Ergebnis NUR für Vallys Runde eintragen und veröffentlichen …
        client.put("/api/tipp/admin/ergebnis?round=vally", json=[{"slug": slug, "seats": 7}])
        client.post("/api/tipp/admin/veroeffentlichen?round=vally")
        # … und die Tippfrist nur dort beenden.
        client.put("/api/tipp/admin/phase?round=vally", json={"phase": "locked"})
    finally:
        app.dependency_overrides.pop(require_active, None)

    service.reset()
    haupt = client.get("/api/tipp/stand").json()
    vally_stand = client.get("/api/tipp/stand?round=vally").json()
    assert next(c for c in vally_stand["compare"] if c["slug"] == slug)["actual"] == 7
    assert next(c for c in haupt["compare"] if c["slug"] == slug)["actual"] is None, "das Ergebnis gehört Vallys Runde"
    assert vally_stand["phase"] == "locked" and haupt["phase"] == "open"
    assert client.get("/api/tipp/setup").json()["locked"] is False


# ------------------------------------------------------------------ Migration

ALTES_SCHEMA = """
CREATE TABLE prediction_game (id INTEGER PRIMARY KEY CHECK (id = 1), title TEXT NOT NULL, phase TEXT NOT NULL,
  locked_at TEXT, locked_reason TEXT, late_scored INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE prediction_players (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL, late_at TEXT, hidden_at TEXT);
CREATE TABLE prediction_tips (player_id INTEGER PRIMARY KEY REFERENCES prediction_players(id), seats_json TEXT NOT NULL,
  mayor_json TEXT, updated_at TEXT NOT NULL);
CREATE TABLE prediction_result (slug TEXT PRIMARY KEY, seats INTEGER, pct REAL, source TEXT NOT NULL DEFAULT 'manuell',
  updated_at TEXT NOT NULL, published_seats INTEGER, published_pct REAL, published_source TEXT, published_at TEXT);
CREATE TABLE prediction_standings (stand_at TEXT NOT NULL, player_id INTEGER NOT NULL, rank INTEGER NOT NULL,
  points INTEGER NOT NULL, PRIMARY KEY (stand_at, player_id));
CREATE TABLE prediction_log (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, text TEXT NOT NULL);
INSERT INTO prediction_game VALUES (1, 'Tippspiel zur Ratswahl', 'locked', '2026-09-13T18:05:00+00:00', 'projection', 0, 'x');
INSERT INTO prediction_players (name, token_hash, created_at) VALUES ('Ismail', 'a', 'x'), ('Waltraud', 'b', 'x');
INSERT INTO prediction_tips VALUES (2, '{"spd": 52}', NULL, 'x');
INSERT INTO prediction_result (slug, seats, source, updated_at, published_seats, published_source, published_at)
  VALUES ('spd', 13, 'manuell', 'x', 13, 'manuell', 'y');
INSERT INTO prediction_standings VALUES ('2026-09-13T18:10:00', 2, 1, 45);
INSERT INTO prediction_log (at, text) VALUES ('x', 'Test');
"""


def test_der_bestand_eines_einzelnen_spiels_wird_zur_hauptrunde(tmp_path):
    pfad = tmp_path / "alt.sqlite"
    c = sqlite3.connect(pfad)
    c.executescript(ALTES_SCHEMA)
    c.commit()
    c.close()

    st = Store(pfad)
    try:
        assert [(g["id"], g["slug"], g["phase"]) for g in st.prediction_games()] == [(1, "ratswahl", "locked")]
        assert [(p["game_id"], p["name"]) for p in st.prediction_players(1, include_hidden=True)] == [(1, "Ismail"), (1, "Waltraud")]
        assert st.prediction_player_by_token("b", 1)["seats_json"] == '{"spd": 52}'
        assert [(r["game_id"], r["slug"], r["published_seats"]) for r in st.prediction_result(1)] == [(1, "spd", 13)]
        assert st.prediction_standings_previous(1, "9999") == {2: 1}
        assert [e["text"] for e in st.prediction_log(1)] == ["Test"]
        # Wiederholbar — und eine zweite Runde passt danach neben die erste.
        st._migrate_tippspiel_runden()  # noqa: SLF001
        assert st.prediction_game_by_slug("vally", "Vallys Tippspiel")["id"] == 2
        assert st.prediction_players(2) == []
    finally:
        st.close()
