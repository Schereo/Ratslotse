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
        "decisions": [], "speeches": [], "press": [], "announced": [], "akte": {}}


# --------------------------------------------------------------------------- #
# Phase 4: Zeitleiste, letzte Station, „Zuletzt“
# --------------------------------------------------------------------------- #

BESCHLUSS_ALT = {"id": 1, "title": "Spielleitplanung", "committee": "Ausschuss",
                 "session_date": "2026-04-16", "outcome": "accepted"}
BESCHLUSS_NEU = {"id": 2, "title": "Spielleitplanung", "committee": "Rat",
                 "session_date": "2026-06-01", "outcome": "accepted"}
BEITRAG = {"id": 9, "session_date": "2026-04-16", "committee": "Ausschuss",
           "speaker": "Verwaltung (Protokollnotiz)", "kind": "pledge",
           "text": "Auf dem Schlossplatz ist kein Platz für einen Spielplatz."}
PM = {"id": 5, "date": "2026-08-12", "title": "EU gibt grünes Licht", "auszug": "…"}
TERMIN = {"id": 7, "date": "2026-09-28", "committee": "Rat", "result": "Entscheidung",
          "title": "Ausfallbürgschaft Klinikum"}


def test_zeitleiste_aelteste_zuerst_und_markiert():
    text = akte_suche.zeitleiste([BESCHLUSS_NEU, BESCHLUSS_ALT], [BEITRAG], [PM], [TERMIN])
    text = text[text.index("\n- "):]            # ohne die Kopfzeile des Blocks
    reihe = [text.index(s) for s in ("[1]", "Protokollnotiz der Verwaltung", "[2]",
                                     "Pressemitteilung", "ANGEKÜNDIGT (Entscheidung)")]
    assert reihe == sorted(reihe)
    assert "noch nicht protokolliert" in text


def test_letzte_station_ist_der_juengste_termin():
    st = akte_suche.letzte_station([BESCHLUSS_ALT, BESCHLUSS_NEU], [PM], [TERMIN])
    assert st["art"] == "angekuendigt"
    assert akte_suche.letzte_station([BESCHLUSS_ALT], [], [])["c"]["id"] == 1


def test_nennt_erkennt_id_monat_und_ziffern():
    beschluss = {"art": "beschluss", "datum": "2026-06-01", "c": BESCHLUSS_NEU}
    termin = {"art": "angekuendigt", "datum": "2026-09-28", "c": TERMIN}
    assert akte_suche.nennt("Der Rat stimmte zu [2].", beschluss)
    assert akte_suche.nennt("Im September 2026 berät der Rat.", termin)
    assert akte_suche.nennt("Termin: 28.09.2026.", termin)
    assert not akte_suche.nennt("Der Ausschuss empfahl es im April.", termin)


def test_zuletzt_satz_fuer_termin():
    satz = akte_suche.zuletzt_satz({"art": "angekuendigt", "datum": "2026-09-28", "c": TERMIN})
    assert "Ausfallbürgschaft Klinikum" in satz and "noch nicht" in satz


def test_akte_steht_einmal_im_prompt():
    """Was zum Vorgang gehört, steht nur in der AKTE, nicht doppelt."""
    from council import qa
    andere = {"id": 3, "title": "Etwas anderes", "committee": "Rat",
              "session_date": "2025-01-01", "outcome": "accepted"}
    messages, _ = qa._answer_messages(
        "Wie ist der Stand?", [BESCHLUSS_ALT, BESCHLUSS_NEU, andere], debatten=[BEITRAG],
        presse=[PM], akte={"decision_ids": {1, 2}, "speech_ids": {9}, "press_ids": {5},
                           "announced": [TERMIN]})
    prompt = messages[0]["content"]
    akte_teil = prompt[prompt.index("AKTE DES VORGANGS"):]
    assert prompt.count("[1]") == 1 and "[1]" in akte_teil
    assert "[3]" in prompt[:prompt.index("AKTE DES VORGANGS")]   # Rest bleibt bei den Beschlüssen
    assert prompt.count("kein Platz für einen Spielplatz") == 1
    assert "ZUM VORGANG IN DER AKTE" in prompt


def test_ohne_akte_bleibt_der_prompt_wie_er_war():
    from council import qa
    mit, _ = qa._answer_messages("Frage?", [BESCHLUSS_ALT], akte=None)
    assert "AKTE DES VORGANGS" not in mit[0]["content"]
