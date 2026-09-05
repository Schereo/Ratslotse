"""Wächter für den Fehler-Sammler des Web-Backends.

**Die Lücke, die er schließt.** Ein Cron-Absturz meldet sich per Mail
(``run_guarded``) und steht in ``job_runs``. Ein 500er im Web-Request ging bis
09/2026 ins ``journalctl`` und sonst nirgendwohin — wer nicht zufällig auf dem
Server nachsah, erfuhr nie davon.

**Was hier geprüft wird, ist vor allem, was NICHT passiert:** Der Sammler darf
nichts Persönliches aufheben, darf nicht fluten und darf die Antwort nie mit
umbringen. Ein Sammler, der einen 500er in einen Absturz verwandelt, ist
schlimmer als gar keiner.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from kern.fehler import (aufbereiten, browser_aufbereiten, fingerabdruck,
                         route_vorlage, saeubern, spur)
from kern.store import Store

WURZEL = Path(__file__).resolve().parents[1]


def _wirf(f):
    try:
        f()
    except Exception as e:   # noqa: BLE001 — genau darum geht es hier
        return e
    raise AssertionError("die Probe hat nicht geworfen")


# ---------------------------------------------------------------------------
# Was NICHT aufgehoben wird
# ---------------------------------------------------------------------------

def test_adressen_werden_maskiert():
    """Eine echte Adresse in der Datenbank wäre genau das, was
    `lint_adressen.py` im Quelltext verbietet — nur schlechter, weil sie
    niemand im Diff sieht."""
    assert "@" not in saeubern("Konto person@example.org unbekannt")
    assert "<adresse>" in saeubern("Konto person@example.org unbekannt")


def test_lange_kennungen_und_token_werden_maskiert():
    assert saeubern("owner_id=1234567") == "owner_id=<zahl>"
    assert "<token>" in saeubern("Bearer eyJhbGciOiJIUzI1NiJ9abcdefghijkl")


def test_kurze_zahlen_bleiben_stehen():
    """Ein Jahrgang und ein Betrag sind keine Kennung — ohne sie wäre die
    Meldung unlesbar."""
    assert saeubern("Jahr 2026 fehlt") == "Jahr 2026 fehlt"


def test_der_rohe_pfad_wird_zur_vorlage():
    """Sonst führte die Fehlerliste eine Spur davon, wer was gelesen hat."""
    assert route_vorlage(None, "/api/council/decision/8525") == "/api/council/decision/{n}"


def test_die_route_aus_dem_code_gewinnt():
    assert route_vorlage("/api/x/{id}", "/api/x/7") == "/api/x/{id}"


def test_die_spur_traegt_keine_werte():
    """Aufgehoben werden Datei, Zeile und Funktionsname — nicht, was in den
    Variablen stand."""
    geheim = "streng-geheimes-passwort"

    def innen():
        raise ValueError("kaputt")

    text = spur(_wirf(innen))
    assert "in innen" in text
    assert geheim not in text


# ---------------------------------------------------------------------------
# Gruppierung — sonst flutet ein Ausfall die Liste
# ---------------------------------------------------------------------------

def test_gleiche_stelle_ergibt_denselben_fingerabdruck():
    def kaputt():
        raise KeyError("provenance")

    a = fingerabdruck(_wirf(kaputt), "/api/x")
    b = fingerabdruck(_wirf(kaputt), "/api/x")
    assert a == b


def test_andere_meldung_derselben_stelle_faellt_zusammen():
    """Zwei Aufrufe derselben kaputten Stelle sind derselbe Fehler, auch wenn
    die Meldung andere Zahlen trägt."""
    def kaputt(w):
        raise KeyError(w)

    assert (fingerabdruck(_wirf(lambda: kaputt("a")), "/api/x")
            == fingerabdruck(_wirf(lambda: kaputt("b")), "/api/x"))


def test_andere_route_ist_ein_anderer_fehler():
    def kaputt():
        raise KeyError("x")

    assert (fingerabdruck(_wirf(kaputt), "/api/a")
            != fingerabdruck(_wirf(kaputt), "/api/b"))


def test_anderer_ausnahmetyp_ist_ein_anderer_fehler():
    assert (fingerabdruck(_wirf(lambda: 1 / 0), "/api/x")
            != fingerabdruck(_wirf(lambda: {}["x"]), "/api/x"))


# ---------------------------------------------------------------------------
# Der Store
# ---------------------------------------------------------------------------

@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "r.sqlite")
    yield s
    s.close()


def _daten(fingerprint="abc", route="/api/x"):
    return {"fingerprint": fingerprint, "exc_type": "ValueError", "message": "m",
            "route": route, "method": "GET", "trace": "t"}


def test_erst_neu_dann_nur_gezaehlt(store):
    """Gemeldet wird nur die ERSTE Begegnung. Sonst flutete ein Ausfall mit
    tausend Anfragen das Postfach mit tausend Mails, und die eine wichtige
    ginge darin unter."""
    assert store.merke_request_fehler(_daten()) is True
    assert store.merke_request_fehler(_daten()) is False
    assert store.merke_request_fehler(_daten()) is False
    zeilen = store.request_fehler()
    assert len(zeilen) == 1
    assert zeilen[0]["count"] == 3


def test_abhaken_und_wiederauftauchen(store):
    """Ein Haken auf etwas, das weiter passiert, wäre eine Lüge."""
    store.merke_request_fehler(_daten())
    zeile = store.request_fehler()[0]
    assert store.request_fehler_abhaken(zeile["id"]) is True
    assert store.request_fehler_offen() == 0
    # Wieder da → wieder offen UND wieder gemeldet.
    assert store.merke_request_fehler(_daten()) is True
    assert store.request_fehler_offen() == 1


def test_nur_offen_filtert(store):
    store.merke_request_fehler(_daten("a", "/api/a"))
    store.merke_request_fehler(_daten("b", "/api/b"))
    store.request_fehler_abhaken(store.request_fehler()[0]["id"])
    assert len(store.request_fehler(nur_offen=True)) == 1
    assert len(store.request_fehler()) == 2


def test_abhaken_einer_unbekannten_id_meldet_das(store):
    assert store.request_fehler_abhaken(9999) is False


def test_der_sammler_wirft_nie(store):
    """Die wichtigste Eigenschaft: Ein Sammler, der die Antwort mit umbringt,
    ist schlimmer als kein Sammler.

    Nachgestellt wird der Fall, der ihn wirklich trifft: Die Platte ist voll
    oder die Datei nur lesbar — dann scheitert schon das ``execute``.
    """
    class VolleP1atte:
        def execute(self, *a, **k):
            raise sqlite3.OperationalError("attempt to write a readonly database")

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def close(self):
            """Die Fixture räumt am Ende auf — auch dieser Ersatz muss das können."""

    store._conn = VolleP1atte()          # type: ignore[assignment]
    assert store.merke_request_fehler(_daten()) is False


# ---------------------------------------------------------------------------
# Der Weg durch die API
# ---------------------------------------------------------------------------

def test_aufbereiten_liefert_genau_die_erlaubten_felder():
    """Kommt ein Feld dazu, gehört es hier UND in `AdminRequestFehler` — und
    dann ist die Frage zu beantworten, ob es etwas Persönliches tragen kann."""
    def kaputt():
        raise ValueError("x")

    d = aufbereiten(_wirf(kaputt), "get", None, "/api/x/7")
    assert set(d) == {"fingerprint", "exc_type", "message", "route", "method", "trace"}
    assert d["method"] == "GET"
    assert d["route"] == "/api/x/{n}"


# ---------------------------------------------------------------------------
# Der Weg durch die laufende API
# ---------------------------------------------------------------------------

def _api(tmp_path, monkeypatch):
    """Die App mit einer EIGENEN, leeren Datenbank — der Sammler schreibt echt.

    Die eigene Datei ist Pflicht, nicht Kosmetik: Ohne sie schreibt der Test in
    ``data/ratslotse.sqlite`` des Arbeitsbaums, die Zeile überlebt den Lauf,
    und beim zweiten Mal ist der Fehler nicht mehr neu — die Alarm-Prüfung
    ginge dann still von grün nach rot, ohne dass sich am Code etwas geändert
    hätte.
    """
    import sys

    sys.path.insert(0, str(WURZEL / "web" / "backend"))
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import app

    db = str(tmp_path / "ratslotse.sqlite")
    Store(db).close()                    # Schema anlegen
    monkeypatch.setattr(get_settings(), "ratslotse_db", db)
    return app, TestClient(app, raise_server_exceptions=False), db


def test_ein_500er_landet_in_der_tabelle_und_meldet_sich_einmal(tmp_path, monkeypatch):
    """Drei kaputte Aufrufe, EINE Zeile — und genau EINE Meldung."""
    app, client, db = _api(tmp_path, monkeypatch)
    gemeldet: list[str] = []
    import kern.alerts

    monkeypatch.setattr(kern.alerts, "notify_admin",
                        lambda text, **k: gemeldet.append(text))

    @app.get("/api/_probe_fehlersammler")
    def _kaputt():                      # pragma: no cover — wirft immer
        return {"a": 1}["provenance"]

    for _ in range(3):
        antwort = client.get("/api/_probe_fehlersammler")
        assert antwort.status_code == 500
        # Der Nutzer bekommt einen Satz, keinen Traceback.
        assert "schiefgegangen" in antwort.json()["detail"]

    store = Store(db)
    try:
        zeilen = [z for z in store.request_fehler()
                  if z["route"] == "/api/_probe_fehlersammler"]
        assert len(zeilen) == 1, "gleiche Fehler müssen zusammenfallen"
        assert zeilen[0]["count"] == 3
        assert zeilen[0]["exc_type"] == "KeyError"
        assert zeilen[0]["method"] == "GET"
    finally:
        store.close()

    assert len(gemeldet) == 1, (
        "Gemeldet wird nur die ERSTE Begegnung — sonst flutet ein Ausfall das "
        "Postfach, und die eine wichtige Mail geht darin unter.")


def test_der_traceback_bleibt_im_log(caplog, tmp_path, monkeypatch):
    """Bisher schrieb ihn Starlettes Standard-Handler. Den ersetzen wir —
    ohne das `logger.exception` wäre er weg, und das Server-Log bliebe stumm."""
    app, client, _ = _api(tmp_path, monkeypatch)

    @app.get("/api/_probe_log")
    def _kaputt():                      # pragma: no cover — wirft immer
        raise RuntimeError("etwas ging schief")

    with caplog.at_level("ERROR"):
        client.get("/api/_probe_log")
    assert any("Unbehandelter Fehler" in r.message or "etwas ging schief" in str(r.exc_info)
               for r in caplog.records)


# ---------------------------------------------------------------------------
# Meldungen aus dem Browser — FREMDE Eingabe
# ---------------------------------------------------------------------------

def test_eine_browser_meldung_wird_gesaeubert():
    """Der Endpunkt ist offen; jeder kann hineinschreiben, was er will."""
    d = browser_aufbereiten({
        "name": "TypeError", "message": "Konto person@example.org, id 987654321",
        "stack": "at h (/_next/static/chunks/abc.js:1:23)",
        "route": "/haushalt/schulden"}, "/haushalt/schulden")
    assert "@" not in d["message"]
    assert "<zahl>" in d["message"]
    assert d["quelle"] == "browser"
    assert d["method"] == "BROWSER"


def test_eine_leere_meldung_wird_nicht_abgelehnt():
    """Eine Fehlermeldung, die selbst an einer Formalie scheitert, hilft
    niemandem — ersetzen statt ablehnen."""
    d = browser_aufbereiten({}, "/x")
    assert d["exc_type"] == "Error"
    assert d["route"] == "/x"
    assert d["fingerprint"]


def test_browser_und_server_vermischen_sich_nicht():
    """Sonst könnte jemand mit einer erfundenen Meldung eine echte Zeile
    überschreiben."""
    def kaputt():
        raise TypeError("x")

    server = aufbereiten(_wirf(kaputt), "GET", "/api/x", "/api/x")
    browser = browser_aufbereiten({"name": "TypeError", "message": "x", "route": "/api/x"},
                                  "/api/x")
    assert server["fingerprint"] != browser["fingerprint"]


def test_der_stapel_wird_gekappt():
    lang = "\n".join(f"at f{i} (/a.js:{i}:1)" for i in range(40))
    d = browser_aufbereiten({"name": "E", "stack": lang, "route": "/x"}, "/x")
    assert len(d["trace"].splitlines()) <= 8


# ---------------------------------------------------------------------------
# Der Tagesverlauf
# ---------------------------------------------------------------------------

def test_der_verlauf_zaehlt_je_tag(store):
    for _ in range(4):
        store.merke_request_fehler(_daten())
    verlauf = store.request_fehler()[0]["daily"]
    assert len(verlauf) == 1
    assert verlauf[0]["n"] == 4


def test_der_verlauf_bleibt_begrenzt():
    """Ein eigener Ereignis-Tisch liefe bei einem Ausfall in Minuten voll;
    dies hier bleibt klein."""
    import json

    from kern.store import VERLAUF_TAGE, _verlauf_plus

    voll = json.dumps({f"2026-01-{i:02d}": 1 for i in range(1, 32)})
    assert len(_verlauf_plus(voll, "2026-02-01")) == VERLAUF_TAGE


def test_ein_kaputter_verlauf_gilt_als_leer():
    from kern.store import _verlauf_lesen

    for roh in (None, "", "{kein json", "[]", "3"):
        assert _verlauf_lesen(roh) == {}


def test_der_browser_endpunkt_speichert_und_antwortet_immer_200(tmp_path, monkeypatch):
    app, client, db = _api(tmp_path, monkeypatch)
    antwort = client.post("/api/client-errors", json={
        "name": "TypeError", "message": "kaputt",
        "stack": "at h (/x.js:1:1)", "route": "/haushalt"})
    assert antwort.status_code == 200

    store = Store(db)
    try:
        zeilen = [z for z in store.request_fehler() if z["quelle"] == "browser"]
        assert zeilen and zeilen[0]["route"] == "/haushalt"
    finally:
        store.close()

    # Auch krumme Nutzlast bekommt 200: Wer einen Fehler meldet, hat schon
    # einen — ein zweiter hilft niemandem.
    assert client.post("/api/client-errors", json={}).status_code == 200
