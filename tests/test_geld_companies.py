"""Die Facette `companies` — der Beteiligungsbericht in der KI-Frage.

Drei Messungen, wie für jede Modul-Facette (council/geld/): welche Fragen sie
zieht, was die Store-Methode liefert, wie groß ihr Baustein an echten Zahlen
wird."""
import sqlite3
from pathlib import Path

import pytest

from council import qa
from council.geld import companies
from council.store import CouncilStore

#: Der dev-Bestand als Kopie — nur die Größenmessung braucht ihn.
ECHTE_DB = Path(
    "/private/tmp/claude-501/-Users-tim-Documents-kommunalwahl-scraper--claude-"
    "worktrees-haushaltsseite-review-763d8c/1759b603-5a3e-439a-95af-ccd796425871/"
    "scratchpad/data/council.sqlite")


# ---------------------------------------------------------------------------
# 1. Erkennung
# ---------------------------------------------------------------------------

ZIEHT = [
    "Welche Beteiligungen hat die Stadt Oldenburg?",
    "Wem gehört die GSG?",
    "An welchen Gesellschaften ist die Stadt beteiligt?",
    "Wer sitzt im Aufsichtsrat der VWG?",
    "Was steht im Beteiligungsbericht?",
    "Wie viel Verlust macht das Klinikum?",
    "Welche Anteile hält die Stadt an der Weser-Ems Halle?",
]

#: Die Nachbarfragen, bei denen das Muster am ehesten fehlfeuert: „Beteiligung"
#: als Bürgerbeteiligung, „Gesellschaft" als Öffentlichkeit, „beteiligt sich"
#: als Kostenanteil — und das Stadion, das in Oldenburg ein Thema ist und keine
#: Gesellschaft.
ZIEHT_NICHT = [
    "Gibt es eine Bürgerbeteiligung zum Bebauungsplan Donnerschwee?",
    "Wie lief die Öffentlichkeitsbeteiligung zum Verkehrsentwicklungsplan?",
    "Was tut die Stadt für gesellschaftliche Teilhabe?",
    "Wie steht die Stadtgesellschaft zum Klimaschutz?",
    "Wie ist der Stand beim Stadion?",
    "Wer ist Oberbürgermeister von Oldenburg?",
]


@pytest.mark.parametrize("frage", ZIEHT)
def test_erkennung_zieht(frage):
    assert "companies" in qa.geld_facetten(frage, "topic"), frage


@pytest.mark.parametrize("frage", ZIEHT_NICHT)
def test_erkennung_zieht_nicht(frage):
    assert "companies" not in qa.geld_facetten(frage, "topic"), frage


def test_die_alten_facetten_bleiben_stehen():
    """Die neue Facette darf keine bestehende verschieben — weder wegnehmen
    noch hinzufügen. Gemessen an je einer Frage der engsten alten Quellen."""
    assert qa.geld_facetten("Wie viel Schulden hat Oldenburg?", "topic") == {"schulden"}
    assert qa.geld_facetten("Wie viele Stellen sind unbesetzt?", "topic") == {"stellenplan"}
    # „Klinikum" zieht den Konzern seit jeher mit — das bleibt so, die neue
    # Facette kommt DANEBEN: der Gesamtabschluss ist die Summe, sie die
    # einzelne Gesellschaft.
    assert qa.geld_facetten("Wie hoch ist der Verlust des Klinikums?",
                            "topic") == {"konzern", "companies"}


# ---------------------------------------------------------------------------
# 2. Inhalt
# ---------------------------------------------------------------------------

def _store(tmp_path) -> CouncilStore:
    """Zwei Gesellschaften im Zuschnitt des echten Bestands: eine mit
    Mitgesellschaftern und Gewinn, eine im Alleinbesitz mit Null-Ergebnis
    (Ergebnisabführung) — der Fall, der ohne Erklärsatz falsch gelesen wird."""
    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_provenance (id, key, kind, label, url, citation, "
            " page, probe, as_of, fetched_at) VALUES "
            "(1, 'b1', 'ris', 'Beteiligungsbericht 2024', 'https://example.org/bb', "
            " 'Abschnitt 2.4.9 — Wohnbau', 190, 'anteilsprobe', "
            " 'Beteiligungsbericht 2024', '2026-09-02')")
        for company, name, classification, page in [
                ("wohnbau", "Wohnbau Oldenburg mbH", "2.4.9", 190),
                ("verkehr", "Verkehr Oldenburg GmbH", "2.4.8", 178)]:
            store._conn.execute(
                "INSERT INTO council_companies (report_year, company, name, "
                " classification, page, herkunft_id, fetched_at) "
                "VALUES (2024, ?, ?, ?, ?, 1, '2026-09-02')",
                (company, name, classification, page))
            store._conn.execute(
                "INSERT INTO council_company_texts (report_year, company, section, "
                " text, herkunft_id, fetched_at) VALUES (2024, ?, 'business_purpose', "
                " ?, 1, '2026-09-02')",
                (company, "Zweck der Gesellschaft ist die Wohnungsversor-\ngung."
                 if company == "wohnbau" else "Gegenstand sind Wasser und Busse."))
        store._conn.execute(
            "INSERT INTO council_company_texts (report_year, company, section, text, "
            " herkunft_id, fetched_at) VALUES (2024, 'verkehr', 'budget_impact', "
            " 'Die Stadt zahlte 13.344.252,11 Euro Ausgleichsleistung.', 1, '2026-09-02')")
        for company, sort_order, owner, pct in [
                ("wohnbau", 0, "Stadt Oldenburg", 34.5),
                ("wohnbau", 1, "Landesbank", 65.5),
                ("verkehr", 0, "Stadt Oldenburg", 100.0)]:
            store._conn.execute(
                "INSERT INTO council_company_owners (report_year, company, sort_order, "
                " name, share_pct, herkunft_id, fetched_at) "
                "VALUES (2024, ?, ?, ?, ?, 1, '2026-09-02')",
                (company, sort_order, owner, pct))
        for company, sort_order, name, position, chair in [
                ("verkehr", 0, "Erika Mustermann", "Ratsmitglied", "chair"),
                ("verkehr", 1, "Max Mustermann", "Ratsmitglied", None),
                ("verkehr", 2, "Pia Beispiel", "Vertreterin Mitgesellschafter", None)]:
            store._conn.execute(
                "INSERT INTO council_company_people (report_year, company, sort_order, "
                " committee, name, position, chair_role, roles_assignable, herkunft_id, "
                " fetched_at) VALUES (2024, ?, ?, 'Aufsichtsrat', ?, ?, ?, 1, 1, "
                " '2026-09-02')",
                (company, sort_order, name, position, chair))
        for company, kind, year, value, unit in [
                ("wohnbau", "jahresergebnis", 2024, 8_236_483.57, "eur"),
                ("wohnbau", "jahresergebnis", 2022, 5_000_000.0, "eur"),
                ("wohnbau", "bilanzsumme", 2024, 363_583_688.69, "eur"),
                ("wohnbau", "eigenkapitalquote", 2024, 36.7, "percent"),
                ("verkehr", "jahresergebnis", 2024, 0.0, "eur"),
                ("verkehr", "bilanzsumme", 2024, 69_000_000.0, "eur")]:
            store._conn.execute(
                "INSERT INTO council_company_indicators (company, indicator, year, "
                " value, unit, report_year, n_reports, herkunft_id, fetched_at) "
                "VALUES (?, ?, ?, ?, ?, 2024, 1, 1, '2026-09-02')",
                (company, kind, year, value, unit))
    return store


def test_begriffe_waehlen_die_gesellschaft(tmp_path):
    store = _store(tmp_path)
    daten = store.companies_context(["Wohnungen", "Miete"])
    assert [g["name"] for g in daten["companies"]] == ["Wohnbau Oldenburg mbH"]
    g = daten["companies"][0]
    assert g["legal_form"] == "GmbH / Co. KG"
    assert [(k["kind"], k["year"], k["value"]) for k in g["indicators"]] == [
        ("jahresergebnis", 2024, 8_236_483.57),
        ("bilanzsumme", 2024, 363_583_688.69),
        ("eigenkapitalquote", 2024, 36.7)]
    assert [(e["name"], e["share_pct"]) for e in g["owners"]] == [
        ("Stadt Oldenburg", 34.5), ("Landesbank", 65.5)]
    text = companies.block(daten)
    assert "Stadt Oldenburg 34,5 %" in text
    assert "8,2 Mio. €" in text
    # Der Trennstrich des zweispaltigen PDF-Satzes ist zusammengefügt.
    assert "Wohnungsversorgung" in text and "versor-" not in text
    store.close()


def test_ohne_treffer_kommt_der_ueberblick(tmp_path):
    """Die Auslöse-Wörter der Facette sind keine Suchbegriffe: Sonst träfe
    „Welche Beteiligungen hat die Stadt?" die erstbeste Gesellschaft."""
    store = _store(tmp_path)
    daten = store.companies_context(["Welche", "Beteiligungen", "hat", "die", "Stadt"])
    assert daten["companies"] == []
    u = daten["overview"]
    assert u["count"] == 2 and u["forms"] == [("GmbH / Co. KG", 2)]
    assert [g["name"] for g in u["largest"]] == ["Wohnbau Oldenburg mbH",
                                                 "Verkehr Oldenburg GmbH"]
    assert u["results_sum"] == 8_236_483.57 and u["results_n"] == 2
    text = companies.block(daten)
    assert "NICHT das Konzernergebnis" in text
    store.close()


def test_null_ergebnis_bekommt_seinen_erklaersatz(tmp_path):
    """Die gefährlichste Zeile des Bausteins: „Jahresergebnis 0 €" heißt
    Ergebnisabführung, nicht „macht keinen Verlust"."""
    store = _store(tmp_path)
    text = companies.block(store.companies_context(["Busse", "Wasser"]))
    assert "Jahresergebnis 2024: 0 €" in text
    assert "Die Null ist Vertragslage" in text
    assert "13.344.252,11 Euro" in text
    assert "Aufsichtsrat: 3 Mitglieder, Vorsitz Erika Mustermann (Ratsmitglied)" in text
    assert "davon 2 Ratsmitglieder" in text
    store.close()


def test_gefragtes_jahr_wird_geliefert(tmp_path):
    store = _store(tmp_path)
    daten = store.companies_context(["Wohnungen"], 2022)
    assert daten["year"] == 2022 and "year_asked" not in daten
    ergebnis = next(k for k in daten["companies"][0]["indicators"]
                    if k["kind"] == "jahresergebnis")
    assert (ergebnis["year"], ergebnis["value"]) == (2022, 5_000_000.0)
    store.close()


def test_fehlendes_jahr_faellt_auf_das_juengste_und_sagt_es(tmp_path):
    store = _store(tmp_path)
    daten = store.companies_context(["Wohnungen"], 2005)
    assert daten["year"] == 2024 and daten["year_asked"] == 2005
    text = companies.block(daten)
    assert "ACHTUNG: Für 2005 führt der Bericht keine Kennzahlen" in text
    store.close()


def test_leere_datenbank_liefert_nichts(tmp_path):
    store = CouncilStore(tmp_path / "leer.sqlite")
    assert store.companies_context(["Wohnungen"]) is None
    assert companies.block(None) == ""
    store.close()


# ---------------------------------------------------------------------------
# 3. Größe an echten Zahlen
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("frage,begriffe", [
    ("Wem gehört die GSG Oldenburg?", "GSG Wohnungen Anteile"),
    ("Wie viel Verlust machte die VWG 2005?", "VWG Verkehr Wasser Busse Verlust"),
    ("Welche Beteiligungen hat die Stadt Oldenburg?", "Beteiligungen Gesellschaften"),
])
def test_bausteingroesse_am_echten_bestand(frage, begriffe, tmp_path):
    if not ECHTE_DB.exists():
        pytest.skip("dev-Datenbank nicht vorhanden")
    kopie = tmp_path / "c.sqlite"
    kopie.write_bytes(ECHTE_DB.read_bytes())
    store = CouncilStore(kopie)
    try:
        daten = store.companies_context(begriffe.split(), qa.haushaltsjahr(frage))
        text = companies.block(daten)
        assert text, frage
        assert len(text) <= companies.FACETTE.grenze, (frage, len(text))
    except sqlite3.OperationalError as e:      # veralteter Dump
        pytest.skip(str(e))
    finally:
        store.close()
