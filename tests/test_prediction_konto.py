"""Eine Tipprunde je Wahl — und was „nur für Angemeldete" wirklich heißt.

Tims Wunsch vom 14.09.2026: „wollen wir auch immer direkt ein öffentliches
Tippspiel verlinken? erstmal nur für registrierte Nutzer mit der Option für
den Admin es für alle freizuschalten."

Drei Zusagen stehen hier, und die erste ist die wichtigste:

1. **Am Bestand ändert sich nichts.** Die Runden zur Ratswahl sind
   kontenlos — der QR-Code hing an einer Leinwand, und wer dort mitgetippt
   hat, hat kein Konto. Eine Migration, die daraus Konto-Zwang macht, nähme
   Leuten ihren laufenden Tipp weg.
2. **Der Riegel sitzt im Router**, nicht im Link. Ein Link, den man nicht
   sieht, ist keine Beschränkung.
3. **Ein Tipp je Konto**, auf jedem Gerät derselbe. Das ist der Unterschied
   zum Cookie — und der Grund, warum es überhaupt eine zweite Art gibt.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from kern.store import Store  # noqa: E402

from app.deps import get_store, optional_user  # noqa: E402
from app.election import mayor as mayor_module  # noqa: E402
from app.election import service as election_service  # noqa: E402
from app.main import app  # noqa: E402
from app.prediction import rounds, service  # noqa: E402

TIPP = "ob-stichwahl-2026"  # eine Runde, die von selbst zu einer Wahl gehört
#: Die API heißt den Parameter ``round``, die SEITE ``runde`` — eine Adresse,
#: die Menschen bekommen, ist deutsch (``rounds.public_path``). Wer das
#: verwechselt, bekommt still die Hauptrunde statt eines 404.


@pytest.fixture(autouse=True)
def ohne_eintrag_von_hand(monkeypatch):
    """Diese Tests prüfen die Runde, die eine Wahl VON SELBST mitbringt (Konto-
    Zwang, Admin schaltet frei). Seit 19.09.2026 hat die Stichwahl einen
    Eintrag von Hand in ``ROUNDS`` (öffentlich, Slug ``stichwahl``) — der
    ginge hier vor. Für den Mechanismus wird er ausgeblendet; dass er
    existiert und öffentlich ist, prüft ``test_prediction_stichwahl.py``."""
    monkeypatch.delitem(rounds.ROUNDS, "stichwahl", raising=False)


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "tippspiel,wahlabend")
    monkeypatch.setattr(election_service, "live", lambda: election_service.probe(0))
    monkeypatch.setattr(mayor_module, "fetch", lambda force=False, w=None: mayor_module.probe(0, w))
    st = Store(tmp_path / "tipp.sqlite")
    app.dependency_overrides[get_store] = lambda: st
    service.reset()
    yield st
    app.dependency_overrides.clear()
    st.close()
    service.reset()


@pytest.fixture
def client(store):
    return TestClient(app)


def _als(user: dict | None):
    """Anmeldung vortäuschen — ``None`` heißt anonym."""
    app.dependency_overrides[optional_user] = lambda: user


ANNA = {"id": 7, "email": "anna@example.org", "display_name": "Anna K."}
BEN = {"id": 8, "email": "ben@example.org", "display_name": "Ben"}


# ------------------------------------------------------------------ (1) Bestand

def test_die_runden_zur_ratswahl_bleiben_kontenlos(client, store):
    """Die Hauptrunde und Vallys Runde stehen in ``ROUNDS`` und sind offen."""
    for runde in ("", "?round=vally"):
        _als(None)
        antwort = client.get(f"/api/tipp/setup{runde}")
        assert antwort.status_code == 200, runde
        assert antwort.json()["public"] is True


def test_eine_alte_spielzeile_wird_oeffentlich(store):
    """Der Bestand hatte die Spalte nicht — und war für jede*n offen."""
    with store._conn:  # noqa: SLF001
        store._conn.execute(  # noqa: SLF001
            "INSERT INTO prediction_game (slug, title, phase, late_scored, created_at) "
            "VALUES ('alt', 'Alte Runde', 'open', 0, '2026-01-01T00:00:00')")
    store._migrate_tippspiel_konto()  # noqa: SLF001
    assert store.prediction_spiel_zeile("alt")["visibility"] == "oeffentlich"


# ------------------------------------------------------------------ (2) Der Riegel

def test_jede_wahl_bringt_ihre_runde_mit():
    runde = rounds.get(TIPP)
    assert runde is not None
    assert runde.election == TIPP and runde.visibility == "konto" and runde.listed


def test_ohne_anmeldung_kommt_man_nicht_hinein(client):
    _als(None)
    for pfad in (f"/api/tipp/setup?round={TIPP}", f"/api/tipp/me?round={TIPP}"):
        assert client.get(pfad).status_code == 401, pfad
    assert client.post(f"/api/tipp?round={TIPP}", json={"name": "Fremd"}).status_code == 401


def test_mit_anmeldung_steht_sie_offen(client):
    _als(ANNA)
    antwort = client.get(f"/api/tipp/setup?round={TIPP}")
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["public"] is False
    assert daten["tip_kind"] == "pct"


def test_die_uebersicht_verlinkt_nur_was_man_benutzen_kann(client):
    """Ein Link, den man sieht und nicht benutzen kann, ist schlechter als
    keiner — also entscheidet das Backend, nicht die Seite."""
    _als(None)
    ohne = {z["slug"]: z["tipp_path"] for z in client.get("/api/wahlen").json()["elections"]}
    assert ohne[TIPP] == ""

    _als(ANNA)
    mit = {z["slug"]: z["tipp_path"] for z in client.get("/api/wahlen").json()["elections"]}
    assert mit[TIPP] == f"/tipp?runde={TIPP}"


def test_die_uebersicht_legt_keine_runde_an(client, store):
    """Vier Wahlen ansehen darf nicht vier Spielzeilen erzeugen."""
    _als(ANNA)
    client.get("/api/wahlen")
    assert store.prediction_spiel_zeile(TIPP) is None


# ------------------------------------------------------------------ (3) Ein Tipp je Konto

def _tipp(client, wer: dict, prozente: dict[str, float]):
    _als(wer)
    return client.post(f"/api/tipp?round={TIPP}", json={"seats": None, "mayor": prozente})


def test_ein_konto_tippt_einmal_und_ueberall(client, store):
    assert _tipp(client, ANNA, {"prange": 52.0, "rohr": 48.0}).status_code == 200
    # Zweiter Aufruf OHNE Cookie (anderes Gerät): dieselbe Person, kein Zweitname.
    client.cookies.clear()
    assert _tipp(client, ANNA, {"prange": 51.0, "rohr": 49.0}).status_code == 200

    game_id = store.prediction_spiel_zeile(TIPP)["id"]
    spieler = store.prediction_players(game_id, include_hidden=True)
    assert len(spieler) == 1, "ein Konto, eine Zeile — auch nach einem Gerätewechsel"
    assert spieler[0]["name"] == "Anna K.", "der Name kommt aus dem Profil"
    assert spieler[0]["owner_id"] == ANNA["id"]

    _als(ANNA)
    meins = client.get(f"/api/tipp/me?round={TIPP}").json()
    assert meins["has_mayor_tip"] is True


def test_zwei_konten_sind_zwei_personen(client, store):
    _tipp(client, ANNA, {"prange": 52.0, "rohr": 48.0})
    client.cookies.clear()
    _tipp(client, BEN, {"prange": 40.0, "rohr": 60.0})
    game_id = store.prediction_spiel_zeile(TIPP)["id"]
    assert {p["name"] for p in store.prediction_players(game_id)} == {"Anna K.", "Ben"}


def test_meins_haengt_am_konto_nicht_am_browser(client):
    _tipp(client, ANNA, {"prange": 52.0, "rohr": 48.0})
    client.cookies.clear()
    _als(BEN)
    assert client.get(f"/api/tipp/me?round={TIPP}").status_code == 401, (
        "Bens Anmeldung darf Annas Tipp nicht zeigen — auch nicht auf demselben Rechner.")


def test_konto_loeschen_nimmt_den_tipp_mit(client, store):
    """DSGVO: Wer sein Konto löscht, hinterlässt keine Waise."""
    uid = store.create_web_user("anna@example.org", "hash", status="active", email_verified=True)
    _tipp(client, {"id": uid, "email": "anna@example.org", "display_name": "Anna K."},
          {"prange": 52.0, "rohr": 48.0})
    game_id = store.prediction_spiel_zeile(TIPP)["id"]
    assert len(store.prediction_players(game_id, include_hidden=True)) == 1

    store.delete_web_user(uid)
    assert store.prediction_players(game_id, include_hidden=True) == []
    rest = store._conn.execute("SELECT COUNT(*) FROM prediction_tips").fetchone()[0]  # noqa: SLF001
    assert rest == 0, "der Tipp hängt am Spieler, nicht am Konto — er muss trotzdem weg"


# ------------------------------------------------------------------ Der Schalter

def test_der_admin_schaltet_frei(client, store, monkeypatch):
    from app.deps import require_admin

    app.dependency_overrides[require_admin] = lambda: {"id": 1, "role": "admin"}
    _als(ANNA)
    client.get(f"/api/tipp/setup?round={TIPP}")  # legt die Zeile an

    antwort = client.put(f"/api/tipp/admin/einstellungen?round={TIPP}", json={"public": True})
    assert antwort.status_code == 200
    assert store.prediction_spiel_zeile(TIPP)["visibility"] == "oeffentlich"

    _als(None)
    assert client.get(f"/api/tipp/setup?round={TIPP}").status_code == 200, (
        "freigeschaltet heißt: auch ohne Konto")
    assert any("freigeschaltet" in e["text"] for e in store.prediction_log(
        store.prediction_spiel_zeile(TIPP)["id"])), "und es steht im Protokoll"
