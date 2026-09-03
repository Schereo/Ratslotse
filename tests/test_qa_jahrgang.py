"""Der Jahrgang aus der Frage — bekommt „2022“ auch die Zahlen von 2022?

Bis 09/2026 lieferte jede Geld-Facette das jüngste Jahr, egal was in der
Frage stand: „Was stand 2022 im Haushalt für die Feuerwehr?" bekam den Plan
2026. Seit dieser Runde nimmt jede Quelle das Jahr aus der Frage, wenn sie es
führt — und sagt es im Baustein, wenn nicht. Ohne LLM-Aufruf."""
import pytest

from council import qa
from council.store import CouncilStore


@pytest.fixture
def store(tmp_path) -> CouncilStore:
    """Zwei Jahrgänge je Quelle — genug, um „gefragt" von „jüngst" zu trennen."""
    st = CouncilStore(tmp_path / "c.sqlite")
    with st._conn:
        st._conn.execute(
            "INSERT INTO council_provenance (id, key, kind, label, url, citation, probe, "
            " as_of, fetched_at) VALUES (1, 'k1', 'ris', 'Jahresabschluss', "
            " 'https://example.org/ja', 'Abschnitt 6.2', 'p', '2024', '2026-09-02')")
        st._conn.executemany(
            "INSERT INTO council_budget (year, area, revenues, expenses, result, is_total, "
            " fetched_at) VALUES (?,?,?,?,?,0,'')",
            [(2022, "Brandschutz und Rettungsdienst", 1_500_000, 26_000_000, -24_500_000),
             (2026, "Brandschutz und Rettungsdienst", 2_000_000, 31_000_000, -29_000_000)])
        for year, e_ist, a_ist in ((2022, 700_000_000.0, 720_000_000.0),
                                   (2024, 781_400_000.0, 812_300_000.0)):
            for nr, label, ist in ((12, "Summe ordentliche Erträge", e_ist),
                                   (20, "Summe ordentliche Aufwendungen", a_ist)):
                st._conn.execute(
                    "INSERT INTO council_income_statement (year, sub_budget_no, sub_budget_name, "
                    " nr, label, budgeted, plan, plan_kind, result, deviation, is_total, "
                    " fetched_at, herkunft_id) VALUES (?,NULL,NULL,?,?,?,?,'ansatz',?,0,1,'',1)",
                    (year, nr, label, ist - 10_000_000, ist - 10_000_000, ist))
        st._conn.executemany(
            "INSERT INTO council_products (year, product_no, product_name, office, revenues, "
            " expenses, result, legal_basis, controllability, fetched_at, herkunft_id) "
            "VALUES (?,'P12.126001','Brandschutz und Feuerwehr','Feuerwehr',1,?,?,'§ 2 NBrandSchG',"
            " 'niedrig','',1)",
            [(2021, 20_000_000, -19_999_999), (2023, 23_400_000, -23_399_999)])
        st._conn.executemany(
            "INSERT INTO council_debt (year, total, per_capita, revised, herkunft_id, fetched_at) "
            "VALUES (?,?,?,0,1,'')",
            [(2013, 512_400_000.0, 3_180.0), (2024, 332_800_000.0, 1_910.0),
             (2025, 337_400_000.0, 1_932.0)])
        st._conn.executemany(
            "INSERT INTO council_staff_plan (budget_year, part, row_no, kind, label, "
            " positions_planned, positions_prior_year, filled, vacant, as_of_date, "
            " herkunft_id, fetched_at) VALUES (?,'A',0,'total','Gesamt Teil A',?,?,?,?,?,1,'')",
            [(2025, 800.0, 790.0, 750.0, 40.0, "30.06.2024"),
             (2026, 815.5, 802.0, 761.25, 40.75, "30.06.2025")])
        st._conn.executemany(
            "INSERT INTO council_audit_reports (year, seq, mark, mark_name, text_number, "
            " section, page, text, fetched_at, herkunft_id) VALUES (?,1,'B','Beanstandung',"
            " '3.1',?,10,?,'',1)",
            [(2022, "Vergabewesen", "Vergaben 2022 unvollständig dokumentiert."),
             (2023, "Vergabewesen", "Vergaben 2023 unvollständig dokumentiert.")])
    yield st
    st.close()


# --- Das Jahr aus dem Wortlaut ------------------------------------------------

@pytest.mark.parametrize("frage,erwartet", [
    ("Was stand 2022 im Haushalt für die Feuerwehr?", 2022),
    ("Wer wollte den Haushalt 2024 ändern?", 2024),
    ("Wie hoch waren die Schulden Ende 2013?", 2013),
    # Zeitraum, kein Jahrgang:
    ("Wie haben sich die Ausgaben seit 2020 entwickelt?", None),
    ("Wie liefen die Haushalte von 2019 bis 2024?", None),
    ("Was änderte sich ab 2021 an den Gebühren?", None),
    ("Was kostet die Feuerwehr?", None),
])
def test_haushaltsjahr_liest_den_punkt_und_nicht_den_zeitraum(frage, erwartet):
    assert qa.haushaltsjahr(frage) == erwartet


# --- Die Quellen liefern das gefragte Jahr -------------------------------------

def test_plan_liefert_das_gefragte_jahr(store):
    zeilen = store.haushalt_fuer_begriffe(["Brandschutz"], year=2022)
    assert [z["year"] for z in zeilen] == [2022]
    assert "year_asked" not in zeilen[0]
    assert "2019" not in qa._haushalt_block(zeilen)


def test_plan_faellt_mit_vermerk_auf_das_juengste_jahr(store):
    zeilen = store.haushalt_fuer_begriffe(["Brandschutz"], year=2019)
    assert [z["year"] for z in zeilen] == [2026]
    assert zeilen[0]["year_asked"] == 2019
    text = qa._haushalt_block(zeilen)
    assert "Für 2019 liegt diese Quelle nicht vor" in text and "2026" in text


def test_ist_kennt_2022_und_sagt_bei_2026_dass_es_2024_ist(store):
    assert store.result_actual_for_terms([], year=2022)["year"] == 2022
    ist = store.result_actual_for_terms([], year=2026)
    assert ist["year"] == 2024 and ist["year_asked"] == 2026
    assert "Für 2026 liegt diese Quelle nicht vor" in qa._ist_block(ist)


def test_produkte_stellenplan_pruefung_schulden_folgen_dem_jahr(store):
    assert store.produkte_fuer_begriffe(["Feuerwehr"], year=2021)["year"] == 2021
    assert store.stellenplan_kontext(budget_year=2025)["budget_year"] == 2025
    sp = store.stellenplan_kontext(budget_year=2019)
    assert sp["budget_year"] == 2026 and sp["year_asked"] == 2019
    assert "Für 2019" in qa._stellenplan_block(sp)
    assert store.pruefberichte_fuer_begriffe([], year=2022)["year"] == 2022
    schulden = store.schulden_kontext(year=2024)
    assert schulden["year"] == 2024 and schulden["davor"]["year"] == 2013
    assert schulden["hoch"]["year"] == 2013


def test_ohne_jahr_bleibt_alles_wie_vorher(store):
    """Kein Jahr in der Frage: das jüngste, ohne Vermerk — das Verhalten von
    vor dieser Runde, unverändert."""
    zeilen = store.haushalt_fuer_begriffe(["Brandschutz"])
    assert [z["year"] for z in zeilen] == [2026] and "year_asked" not in zeilen[0]
    assert store.schulden_kontext()["year"] == 2025
    assert "ACHTUNG" not in qa._schulden_block(store.schulden_kontext())


# --- Der ganze Weg: Frage → Kontext ---------------------------------------------

def test_geld_kontext_reicht_das_jahr_an_die_quellen(store):
    k = qa.geld_kontext(store, "Was hat die Stadt 2022 tatsächlich für die Feuerwehr "
                               "ausgegeben, und was stand im Haushalt?", "Feuerwehr Brandschutz", "money")
    assert k["ist"]["year"] == 2022
    assert [z["year"] for z in k["haushalt"]] == [2022]
    k = qa.geld_kontext(store, "Wie hoch waren die Schulden 2013?", "Schulden", "money")
    assert k["schulden"]["year"] == 2013
    # Zeitraum: die Quellen liefern das jüngste Jahr, ohne Vermerk.
    k = qa.geld_kontext(store, "Wie haben sich die Schulden seit 2013 entwickelt?", "Schulden", "money")
    assert k["schulden"]["year"] == 2025 and "year_asked" not in k["schulden"]
