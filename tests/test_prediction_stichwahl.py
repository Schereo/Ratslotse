"""Das Tippspiel zur OB-Stichwahl am 27.09.2026 (Tims Auftrag 19.09.2026).

Drei Dinge, die vorher nicht gingen — gemessen vor dem Umbau:

* Eine Runde auf die Stichwahl verglich gegen den ERSTEN Wahlgang
  (``mayor.fetch()`` ohne Wahl) und zeigte in „meins" neun Kandidaturen.
* Ein Prozent-Tipp ohne Sitze galt als „kein Tipp" (``has_tip False``,
  ``tip_count 0``) — die Seite zeigte nach dem Abgeben wieder das Formular.
* Der Tipp-Schluss fiel für eine Stichwahl-Runde nie automatisch.

Dazu die beiden neuen Felder: Wahlbeteiligung (``turnout``, Punkte) und die
freiwillige Parteizugehörigkeit (``party``, Menü ohne AfD).
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from kern.store import Store  # noqa: E402

from app.deps import get_store, require_admin  # noqa: E402
from app.election import elections  # noqa: E402
from app.election import mayor as mayor_module  # noqa: E402
from app.election import service as election_service  # noqa: E402
from app.main import app  # noqa: E402
from app.prediction import rounds, service  # noqa: E402

RUNDE = "?round=stichwahl"
ADMIN = {"id": 1, "role": "admin", "roles": ["admin"], "status": "active"}


def _stichwahl_stand(counted: int):
    """``mayor.fetch`` so, dass NUR die Stichwahl ``counted`` Bezirke zeigt —
    der erste Wahlgang bleibt bei „nichts ausgezählt". Wer gegen den ersten
    Wahlgang verglicht, sieht hier also keine Zahl."""
    def fetch(force=False, w=None):
        w = w or elections.mayor_of()
        return mayor_module.probe(counted if w.first_round else 0, w)
    return fetch


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "tippspiel,wahlabend")
    monkeypatch.setattr(election_service, "live", lambda: election_service.probe(0))
    monkeypatch.setattr(mayor_module, "fetch", _stichwahl_stand(0))
    # Die Uhr steht VOR der Schließung der Wahllokale (13.09.2026, 18 Uhr):
    # Seit 19.09.2026 sperrt sich eine Runde um 18 Uhr am Wahltag von selbst —
    # mit der echten Uhr wäre die Ratswahl-Runde hier sofort zu.
    monkeypatch.setattr(service, "_jetzt",
                        lambda: datetime(2026, 9, 13, 10, 0, tzinfo=timezone.utc))
    store = Store(tmp_path / "stichwahl.sqlite")
    app.dependency_overrides[get_store] = lambda: store
    service.reset_all()
    yield TestClient(app)
    app.dependency_overrides.clear()
    store.close()
    service.reset_all()


@pytest.fixture
def store(client) -> Store:
    return app.dependency_overrides[get_store]()


def tippen(client: TestClient, name: str, prange: float, rohr: float, turnout: float | None = None,
           party: str | None = None, **extra):
    client.cookies.clear()
    r = client.post(f"/api/tipp{RUNDE}", json={"name": name, "party": party})
    assert r.status_code == 200, r.text
    r = client.post(f"/api/tipp{RUNDE}", json={"seats": None, "mayor": {"prange": prange, "rohr": rohr},
                                               "turnout": turnout, **extra})
    return r


# ------------------------------------------------------------------ Die Runde

def test_die_stichwahl_runde_ist_oeffentlich_und_gelistet():
    """Tims Auftrag: freischalten — Name statt Konto, wie bei der Ratswahl."""
    runde = rounds.get("stichwahl")
    assert runde is not None
    assert runde.election == "ob-stichwahl-2026" and runde.visibility == "oeffentlich" and runde.listed
    # Die automatische Runde der Wahl UND der kurze Slug meinen dieselbe Runde.
    assert rounds.get("ob-stichwahl-2026") is runde
    assert rounds.public_path(runde) == "/tipp?runde=stichwahl"


def test_setup_nennt_die_beiden_kandidaturen_und_das_parteien_menue(client):
    daten = client.get(f"/api/tipp/setup{RUNDE}").json()
    assert daten["public"] is True and daten["tip_kind"] == "pct" and daten["parties"] == []
    assert [c["slug"] for c in daten["mayor_candidates"]] == ["rohr", "prange"]
    slugs = [o["slug"] for o in daten["party_options"]]
    assert "afd" not in slugs, "Tims Entscheidung 19.09.2026: ohne AfD"
    assert "stille" not in slugs, "ein Einzelwahlvorschlag ist keine Partei"
    assert {"gruene", "spd", "cdu", "volt", "fuer-oldenburg"} <= set(slugs)
    assert daten["turnout_previous"] == pytest.approx(63.46) and daten["turnout_previous_label"] == "1. Wahlgang"
    assert "Schließung der Wahllokale" in daten["deadline_hint"]


def test_die_uebersicht_verlinkt_die_stichwahl_ohne_konto(client):
    zeilen = {z["slug"]: z for z in client.get("/api/wahlen").json()["elections"]}
    assert zeilen["ob-stichwahl-2026"]["tipp_path"] == "/tipp?runde=stichwahl"
    assert zeilen["ob-stichwahl-2026"]["tipp_locked"] is False


# ------------------------------------------------------------------ Tippen

def test_ein_prozent_tipp_ist_ein_tipp(client):
    """Vorher: ``has_tip False`` — die Seite zeigte nach dem Abgeben wieder das Formular."""
    meins = tippen(client, "Anna", 52.0, 48.0, turnout=45.0, party="volt").json()
    assert meins["has_tip"] is True and meins["has_mayor_tip"] is True
    assert [m["slug"] for m in meins["mayor"]] == ["rohr", "prange"], "die ZWEI der Stichwahl, nicht neun"
    assert meins["seats"] == []
    assert meins["turnout"] == {"tip": 45.0, "actual_pct": None, "avg_tip": 45.0, "points": 0}
    assert meins["party"]["slug"] == "volt" and meins["party"]["short"] == "Volt"
    assert meins["score"] is None, "vor der ersten Zahl gibt es keine Punkte"

    stand = client.get(f"/api/tipp/stand{RUNDE}").json()
    assert stand["tip_kind"] == "pct" and stand["tip_count"] == 1 and stand["seats_total"] == 0
    assert stand["rows"][0]["has_tip"] is True and stand["rows"][0]["party"]["short"] == "Volt"
    assert stand["turnout"] == {"actual_pct": None, "avg_tip": 45.0, "tip_count": 1}
    assert stand["compare"] == []


def test_ohne_partei_und_ohne_wahlbeteiligung_geht_es_auch(client):
    meins = tippen(client, "Ben", 50.0, 50.0).json()
    assert meins["party"] is None and meins["turnout"] is None and meins["has_tip"] is True


@pytest.mark.parametrize("partei", ["afd", "stille", "gibtsnicht"])
def test_parteien_ausserhalb_des_menues_sind_422(client, partei):
    r = client.post(f"/api/tipp{RUNDE}", json={"name": "Fremd", "party": partei})
    assert r.status_code == 422
    assert "nicht zur Auswahl" in r.json()["detail"]


def test_wahlbeteiligung_ausserhalb_von_0_bis_100_ist_422(client):
    r = tippen(client, "Cem", 50.0, 50.0, turnout=101.0)
    assert r.status_code == 422 and "Wahlbeteiligung" in r.json()["detail"]


def test_sitze_bei_der_stichwahl_sind_422(client):
    client.post(f"/api/tipp{RUNDE}", json={"name": "Dana"})
    r = client.post(f"/api/tipp{RUNDE}", json={"seats": {"spd": 52}, "mayor": {"prange": 50.0}})
    assert r.status_code == 422 and "keine Sitze" in r.json()["detail"]


# ------------------------------------------------------------------ Der Vergleich gilt der STICHWAHL

def test_punkte_zaehlen_gegen_die_stichwahl_nicht_gegen_den_ersten_wahlgang(client, monkeypatch):
    """Generalprobe der Stichwahl bei 133/133: Prange 52,06, Rohr 47,94,
    Beteiligung 63,46 (der eingefrorene erste Wahlgang auf zwei Namen)."""
    tippen(client, "Anna", 52.0, 48.0, turnout=63.0)
    tippen(client, "Ben", 45.0, 55.0, turnout=40.0)
    monkeypatch.setattr(mayor_module, "fetch", _stichwahl_stand(133))
    service.reset_all()

    stand = client.get(f"/api/tipp/stand{RUNDE}").json()
    ist = {m["slug"]: m["actual_pct"] for m in stand["mayor"]}
    assert ist == {"prange": pytest.approx(52.06), "rohr": pytest.approx(47.94)}
    assert stand["turnout"]["actual_pct"] == pytest.approx(63.46)
    assert stand["mayor_status"] == "complete" and stand["source_label"] == "votemanager"
    assert stand["area_label"] == "133/133 Wahlbezirke"

    zeilen = {r["name"]: r for r in stand["rows"]}
    assert zeilen["Anna"]["rank"] == 1 and zeilen["Anna"]["score"]["total"] == 6 + 6 + 6
    assert zeilen["Anna"]["score"]["turnout_points"] == 6 and zeilen["Anna"]["score"]["seat_points"] == 0
    assert zeilen["Ben"]["rank"] == 2 and zeilen["Ben"]["score"]["total"] == 0
    assert "Prozentpunkte" in stand["compare_sentence"]


def test_der_erste_auszaehlungsstand_der_stichwahl_setzt_den_tipp_schluss(client, store, monkeypatch):
    tippen(client, "Anna", 52.0, 48.0)
    game_id = store.prediction_spiel_zeile("stichwahl")["id"]
    assert store.prediction_game(game_id)["phase"] == "open"

    monkeypatch.setattr(mayor_module, "fetch", _stichwahl_stand(40))
    service.reset_all()
    client.get(f"/api/tipp/stand{RUNDE}")
    game = store.prediction_game(game_id)
    assert game["phase"] == "locked" and game["locked_reason"] == "projection"
    assert any("Auszählungsstand" in e["text"] for e in store.prediction_log(game_id))


def test_die_ratswahl_hochrechnung_schliesst_die_stichwahl_nicht(client, store, monkeypatch):
    """Und umgekehrt: Zahlen der Ratswahl (die längst da sind) gehen die
    Stichwahl-Runde nichts an."""
    tippen(client, "Anna", 52.0, 48.0)
    monkeypatch.setattr(election_service, "live", lambda: election_service.probe(133))
    service.reset_all()
    client.get(f"/api/tipp/stand{RUNDE}")
    assert store.prediction_game(store.prediction_spiel_zeile("stichwahl")["id"])["phase"] == "open"


def test_handeingabe_der_wahlbeteiligung_schlaegt_den_abruf(client, monkeypatch):
    app.dependency_overrides[require_admin] = lambda: ADMIN
    tippen(client, "Anna", 52.0, 48.0, turnout=50.0)
    monkeypatch.setattr(mayor_module, "fetch", _stichwahl_stand(133))
    service.reset_all()
    client.put(f"/api/tipp/admin/ergebnis{RUNDE}", json=[{"slug": "turnout", "pct": 50.4}])
    assert client.get(f"/api/tipp/stand{RUNDE}").json()["turnout"]["actual_pct"] == pytest.approx(63.46), (
        "der Entwurf ändert die Tafel nicht")
    client.post(f"/api/tipp/admin/veroeffentlichen{RUNDE}")
    stand = client.get(f"/api/tipp/stand{RUNDE}").json()
    assert stand["turnout"]["actual_pct"] == 50.4 and stand["source_label"] == "gemischt"
    assert stand["rows"][0]["score"]["turnout_points"] == 6


# ------------------------------------------------------------------ Admin

def test_admin_stand_zeigt_zwei_kandidaturen_und_die_wahlbeteiligung(client):
    app.dependency_overrides[require_admin] = lambda: ADMIN
    tippen(client, "Anna", 52.0, 48.0, turnout=45.0, party="spd")
    daten = client.get(f"/api/tipp/admin/stand{RUNDE}").json()
    assert [r["slug"] for r in daten["results"]] == ["ob:rohr", "ob:prange", "turnout"], "keine Listen-Zeilen"
    turnout = daten["results"][-1]
    assert turnout["avg_tip"] == 45.0 and turnout["pct"] is None
    spieler = daten["players"][0]
    assert spieler["party"] == "spd" and spieler["has_tip"] is True and spieler["has_turnout_tip"] is True
    assert "stichwahl" in {r["slug"] for r in daten["rounds"]}


def test_jetzt_abfragen_holt_die_stichwahl_samt_wahlbeteiligung(client, monkeypatch):
    app.dependency_overrides[require_admin] = lambda: ADMIN
    monkeypatch.setattr(mayor_module, "fetch", _stichwahl_stand(133))
    daten = client.post(f"/api/tipp/admin/abfragen{RUNDE}").json()
    entwurf = {r["slug"]: r["pct"] for r in daten["results"]}
    assert entwurf["ob:prange"] == pytest.approx(52.06) and entwurf["ob:rohr"] == pytest.approx(47.94)
    assert entwurf["turnout"] == pytest.approx(63.46)
    assert any("Wahlbeteiligung" in zeile for zeile in daten["log"])


def test_admin_korrigiert_die_partei(client, store):
    app.dependency_overrides[require_admin] = lambda: ADMIN
    meins = tippen(client, "Anna", 52.0, 48.0, party="spd").json()
    pid = meins["player_id"]
    client.put(f"/api/tipp/admin/spieler/{pid}{RUNDE}", json={"party": "gruene"})
    assert store.prediction_player_by_token(
        store.prediction_players(store.prediction_spiel_zeile("stichwahl")["id"])[0]["token_hash"],
        store.prediction_spiel_zeile("stichwahl")["id"])["party"] == "gruene"
    client.put(f"/api/tipp/admin/spieler/{pid}{RUNDE}", json={"party": ""})
    assert client.get(f"/api/tipp/admin/stand{RUNDE}").json()["players"][0]["party"] is None
    assert client.put(f"/api/tipp/admin/spieler/{pid}{RUNDE}", json={"party": "afd"}).status_code == 422


# ------------------------------------------------------------------ Von der Ratswahl zur Stichwahl

def test_die_hauptrunde_schickt_neue_zur_stichwahl(client, store):
    """``/tipp`` steht auf alten QR-Codes und Sharepics — wer heute dort
    landet, soll zum laufenden Spiel, nicht zu „Tippfrist vorbei, trotzdem
    tippen" der Ratswahl. Solange die Ratswahl-Runde offen ist, gibt es
    keinen Nachfolger."""
    assert client.get("/api/tipp/setup").json()["successor_path"] == ""
    game_id = store.prediction_spiel_zeile("ratswahl")["id"]
    store.prediction_game_set(game_id, phase="locked")
    assert client.get("/api/tipp/setup").json()["successor_path"] == "/tipp?runde=stichwahl"
    # Die Stichwahl-Runde selbst hat keinen Nachfolger — auch nicht, wenn sie zu ist.
    client.get(f"/api/tipp/setup{RUNDE}")
    store.prediction_game_set(store.prediction_spiel_zeile("stichwahl")["id"], phase="locked")
    assert client.get(f"/api/tipp/setup{RUNDE}").json()["successor_path"] == ""


def test_die_ratswahl_runde_bekommt_auch_das_menue_und_die_beteiligung(client):
    """Die neuen Felder gelten für jede Wahlart — die Ratswahl-Runde ist
    zwar zu, aber ihre Antwort darf nicht anders geformt sein."""
    daten = client.get("/api/tipp/setup").json()
    assert daten["tip_kind"] == "seats" and daten["party_options"] and daten["turnout_previous"] is None
    stand = client.get("/api/tipp/stand").json()
    assert stand["tip_kind"] == "seats" and stand["turnout"]["actual_pct"] is None


# ------------------------------------------------------------------ Bestand

def test_eine_alte_datenbank_bekommt_die_neuen_spalten(tmp_path):
    """Prod trägt ``prediction_players`` und ``prediction_tips`` noch ohne
    ``party``/``turnout_pct`` (gemessen 19.09.2026) — die Migration zieht
    beide nach, ohne Tipps anzufassen."""
    pfad = tmp_path / "alt.sqlite"
    con = sqlite3.connect(pfad)
    con.executescript("""
        CREATE TABLE prediction_game (id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL, phase TEXT NOT NULL, locked_at TEXT, locked_reason TEXT,
            late_scored INTEGER NOT NULL DEFAULT 0, shared_device INTEGER NOT NULL DEFAULT 0,
            election_slug TEXT, visibility TEXT NOT NULL DEFAULT 'oeffentlich', created_at TEXT NOT NULL);
        CREATE TABLE prediction_players (id INTEGER PRIMARY KEY AUTOINCREMENT, game_id INTEGER NOT NULL DEFAULT 1,
            name TEXT NOT NULL, owner_id INTEGER, token_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
            late_at TEXT, hidden_at TEXT);
        CREATE TABLE prediction_tips (player_id INTEGER PRIMARY KEY, seats_json TEXT NOT NULL,
            mayor_json TEXT, updated_at TEXT NOT NULL);
        INSERT INTO prediction_game (slug, title, phase, created_at) VALUES ('ratswahl', 'T', 'locked', '2026-09-11');
        INSERT INTO prediction_players (game_id, name, token_hash, created_at) VALUES (1, 'Alt', 'h', '2026-09-11');
        INSERT INTO prediction_tips VALUES (1, '{"spd": 52}', NULL, '2026-09-11');
    """)
    con.commit(); con.close()
    st = Store(pfad)
    try:
        zeile = st.prediction_player_by_token("h", 1)
        assert zeile is not None
        assert zeile["party"] is None and zeile["turnout_pct"] is None and zeile["seats_json"] == '{"spd": 52}'
    finally:
        st.close()


# ------------------------------------------------------------------ 18 Uhr ist Schluss (Tims Regel 19.09.2026)

def test_um_18_uhr_am_wahltag_ist_tipp_schluss_auch_ohne_zahl(client, store, monkeypatch):
    """Die Wahllokale schließen um 18 Uhr — ab dann wird nicht mehr getippt,
    egal ob der Votemanager schon etwas meldet. ``locked_at`` ist die
    Schließung selbst, nicht der Moment des ersten Aufrufs danach."""
    tippen(client, "Anna", 52.0, 48.0)
    game_id = store.prediction_spiel_zeile("stichwahl")["id"]
    monkeypatch.setattr(service, "_jetzt", lambda: datetime(2026, 9, 27, 15, 59, 59, tzinfo=timezone.utc))
    service.reset_all()
    client.get(f"/api/tipp/stand{RUNDE}")
    assert store.prediction_game(game_id)["phase"] == "open", "um 17:59:59 deutscher Zeit noch offen"

    monkeypatch.setattr(service, "_jetzt", lambda: datetime(2026, 9, 27, 16, 7, tzinfo=timezone.utc))  # 18:07 Berlin
    service.reset_all()
    client.get(f"/api/tipp/stand{RUNDE}")
    game = store.prediction_game(game_id)
    assert game["phase"] == "locked" and game["locked_reason"] == "polls_close"
    assert game["locked_at"] == "2026-09-27T16:00:00+00:00", "die Schließung, nicht 18:07"
    setup = client.get(f"/api/tipp/setup{RUNDE}").json()
    assert setup["deadline_hint"] == "Die Tippfrist endete um 18:00 Uhr."
    assert any("Wahllokale geschlossen" in e["text"] for e in store.prediction_log(game_id))
    # Ein Tipp danach ist 409 für Rechtzeitige …
    assert client.post(f"/api/tipp{RUNDE}", json={"seats": None, "mayor": {"prange": 50.0, "rohr": 50.0}}).status_code == 409
    # … und wer jetzt erst kommt, tippt nach.
    client.cookies.clear()
    spaet = client.post(f"/api/tipp{RUNDE}", json={"name": "Spät", "seats": None, "mayor": {"prange": 50.0, "rohr": 50.0}}).json()
    assert spaet["late_at"] is not None


def test_die_frist_steht_im_setup(client):
    setup = client.get(f"/api/tipp/setup{RUNDE}").json()
    assert setup["deadline_hint"] == "bis Sonntag, 27.09., 18:00 Uhr (Schließung der Wahllokale)"
    assert setup["polls_close"] == "2026-09-27T18:00:00+02:00"
