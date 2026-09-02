"""Die Posten-Ebene des Jahresabschlusses und des Ansatzes in der KI-Frage.

„Was kostet das Personal der Stadt?" bekam bis 09/2026 die Summen 12/20 der
Ergebnisrechnung und den Teilhaushalt „Personal, Organisation" — nicht die
Personalaufwendungen (Posten 13), obwohl sie in beiden Quellen stehen. Und
„Wie war das Jahresergebnis 2024?" zog gar nichts. Ohne LLM-Aufruf."""
import pytest

from council import qa
from council.store import CouncilStore


@pytest.fixture
def store(tmp_path) -> CouncilStore:
    st = CouncilStore(tmp_path / "c.sqlite")
    with st._conn:
        st._conn.execute(
            "INSERT INTO council_provenance (id, key, kind, label, url, citation, probe, "
            " as_of, fetched_at) VALUES (1, 'k1', 'ris', 'Jahresabschluss 2024', "
            " 'https://example.org/ja', 'Abschnitt 6.2', 'p', '2024', '2026-09-02')")
        posten = [(1, "Steuern und ähnliche Abgaben", 302.7, 377.9, 75.1, 0),
                  (12, "Summe ordentliche Erträge", 693.6, 799.1, 105.4, 1),
                  (13, "Personalaufwendungen", 183.3, 184.8, 1.4, 0),
                  (17, "Zinsen und ähnliche Aufwendungen", 3.4, 4.2, 0.8, 0),
                  (18, "Transferaufwendungen", 297.7, 323.7, 26.0, 0),
                  (20, "Summe ordentliche Aufwendungen", 727.9, 764.4, 36.5, 1),
                  (21, "ordentliches Ergebnis", -34.3, 34.6, 68.9, 1),
                  (24, "außerordentliches Ergebnis", 2.3, -28.5, -30.8, 1)]
        for nr, label, plan, ist, abw, total in posten:
            st._conn.execute(
                "INSERT INTO council_income_statement (year, sub_budget_no, sub_budget_name, "
                " nr, label, budgeted, plan, plan_kind, result, deviation, is_total, "
                " fetched_at, herkunft_id) VALUES (2024,NULL,NULL,?,?,?,?,'ansatz',?,?,?,'',1)",
                (nr, label, plan * 1e6, plan * 1e6, ist * 1e6, abw * 1e6, total))
        for nr, label, plan, ist in ((12, "Summe ordentliche Erträge", 30.0, 31.0),
                                     (20, "Summe ordentliche Aufwendungen", 44.0, 48.7)):
            st._conn.execute(
                "INSERT INTO council_income_statement (year, sub_budget_no, sub_budget_name, "
                " nr, label, budgeted, plan, plan_kind, result, deviation, is_total, "
                " fetched_at, herkunft_id) VALUES (2024,2,'Personal- u. Verwaltungsmanagement',"
                " ?,?,?,?,'ansatz',?,0,1,'',1)", (nr, label, plan * 1e6, plan * 1e6, ist * 1e6))
        st._conn.executemany(
            "INSERT INTO council_income_budget (plan_budget_year, year, kind, nr, label, "
            " amount, is_total, fetched_at, herkunft_id) VALUES (2026,2026,'budget',?,?,?,?,'',1)",
            [(1, "Steuern und ähnliche Abgaben", 388.4e6, 0),
             (12, "Summe ordentliche Erträge", 788.6e6, 1),
             (13, "Personalaufwendungen", 209.4e6, 0),
             (20, "Summe ordentliche Aufwendungen", 880.8e6, 1)])
        st._conn.execute(
            "INSERT INTO council_budget (year, area, revenues, expenses, result, is_total, "
            " fetched_at) VALUES (2026, 'Personal, Organisation, Digitalisierung', "
            " 2e6, 47.2e6, -45.2e6, 0, '')")
    yield st
    st.close()


def test_ist_traegt_die_getroffenen_posten_und_das_ergebnis(store):
    ist = store.result_actual_for_terms(["Personal"], year=2024)
    assert [p["nr"] for p in ist["posten"]] == [13]
    assert ist["posten"][0]["actual"] == pytest.approx(184.8e6)
    assert ist["ergebnis"]["ordentlich"] == (pytest.approx(-34.3e6), pytest.approx(34.6e6))
    text = qa._ist_block(ist)
    assert "Posten 13 Personalaufwendungen 2024" in text
    assert "Ordentliches Ergebnis 2024" in text and "außerordentliches Ergebnis" in text
    # Der Teilhaushalt kommt weiter wie bisher dazu.
    assert ist["bereiche"][0]["name"].startswith("Personal")


def test_ohne_treffer_keine_posten_aber_das_ergebnis(store):
    ist = store.result_actual_for_terms(["Feuerwehr"], year=2024)
    assert ist["posten"] == [] and ist["bereiche"] == []
    assert "ordentlich" in ist["ergebnis"]


def test_ansatz_meldet_ob_die_begriffe_einen_posten_trafen(store):
    a = store.ansatz_fuer_begriffe(["Personal"], year=2026)
    assert a["treffer"] and [p["nr"] for p in a["posten"]] == [13]
    a = store.ansatz_fuer_begriffe(["Feuerwehr"], year=2026)
    assert not a["treffer"] and all(p["is_total"] for p in a["posten"])


def test_geld_kontext_laedt_den_ansatz_bei_postentreffer_trotz_teilhaushalt(store):
    k = qa.geld_kontext(store, "Was kostet das Personal der Stadt?", "Personal", "money")
    assert k["haushalt"], "der Teilhaushalt fehlt — Fixture verrutscht?"
    assert k["ansatz"]["treffer"] and k["ansatz"]["posten"][0]["nr"] == 13
    k = qa.geld_kontext(store, "Was steht im Haushalt für Organisation und Digitalisierung?",
                        "Organisation Digitalisierung", "money")
    assert k["haushalt"] and "ansatz" not in k


@pytest.mark.parametrize("frage", [
    "Wie war das Jahresergebnis 2024?",
    "Wie hoch war das ordentliche Ergebnis der Stadt 2023?",
])
def test_jahresergebnis_zieht_den_abschluss(frage):
    assert "ist" in qa.geld_facetten(frage, "topic")
