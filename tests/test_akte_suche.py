"""Suche über Akten (council/akte_suche.py, Plan „Akte“ Phase 3).

Hier steht die Auswahlregel; ob sie die Antworten besser macht, misst der
Gold-Lauf (scripts/eval_ask_gold.py) mit Schalter an und aus.
"""
import pytest

from council import akte_suche
from tests.akten_testdaten import store_bauen, themen_bauen


@pytest.fixture
def themen(tmp_path):
    return themen_bauen(store_bauen(tmp_path))


def test_leer_ohne_treffer(themen, monkeypatch):
    assert akte_suche.material(themen, "Frage?", [])["decisions"] == []


def test_beschluesse_neueste_zuerst_ohne_teilabstimmung(themen, monkeypatch):
    m = akte_suche.material(themen, "Spielleitplanung?", [{"id": 10}])
    ids = [d["id"] for d in m["decisions"]]
    assert ids[0] == 11 and 10 in ids          # Rat (Mai) vor Ausschuss (April)
    assert 12 not in ids                        # Teilabstimmung


def test_verwaltung_kommt_auch_ohne_naehe(themen, monkeypatch):
    # Nach Vektor-Nähe wird nichts gewählt — die Verwaltung kommt trotzdem.
    monkeypatch.setattr(akte_suche, "_naechste", lambda store, frage, beitraege: [])
    m = akte_suche.material(themen, "Trinkwasserspender?", [{"id": 13}])
    assert [w["id"] for w in m["speeches"]] == [801]   # Protokollnotiz (pledge)


def test_presse_der_akte_neueste_zuerst(themen, monkeypatch):
    m = akte_suche.material(themen, "Spielplatz Schlossplatz?", [{"id": 20}])
    assert [p["id"] for p in m["press"]] == [30]


def test_ohne_grundakten_bleibt_alles_beim_alten(themen, monkeypatch):
    themen._conn.execute("DROP TABLE council_matter_items")
    assert akte_suche.material(themen, "Frage?", [{"id": 10}]) == {
        "decisions": [], "speeches": [], "press": [], "akte": {}}
