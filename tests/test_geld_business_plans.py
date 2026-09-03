"""Die Facette `business_plans` — die Wirtschaftspläne der Eigenbetriebe.

Drei Messungen, wie für jede Modul-Facette (council/geld/): welche Fragen sie
zieht, was die Store-Methode liefert, wie groß ihr Baustein an echten Zahlen
wird."""
import sqlite3
from pathlib import Path

import pytest

from council import qa
from council.geld import business_plans
from council.store import CouncilStore

ECHTE_DB = Path(
    "/private/tmp/claude-501/-Users-tim-Documents-kommunalwahl-scraper--claude-"
    "worktrees-haushaltsseite-review-763d8c/1759b603-5a3e-439a-95af-ccd796425871/"
    "scratchpad/data/council.sqlite")


# ---------------------------------------------------------------------------
# 1. Erkennung
# ---------------------------------------------------------------------------

ZIEHT = [
    "Was planen die Eigenbetriebe?",
    "Was steht im Wirtschaftsplan des Abfallwirtschaftsbetriebs?",
    "Wie viel plant der Bäderbetrieb für 2026?",
    "Was steht im Erfolgsplan des Eigenbetriebs Gebäudewirtschaft?",
    "Wie hoch ist der Vermögensplan der Gebäudewirtschaft?",
    "Wie viel Geld bekommt der AWB?",
]

#: Die Nachbarfragen: „Wirtschaft" ohne Plan, „Betrieb" ohne Eigen-, das
#: Staatstheater (Sache des Landes) und das Klinikum (eine AöR — ihre Zahlen
#: stehen im Beteiligungsbericht, nicht in einem Wirtschaftsplan).
ZIEHT_NICHT = [
    "Was gibt die Stadt für Wirtschaftsförderung aus?",
    "Wie hoch sind die Betriebskosten der Schulen?",
    "Was zahlt die Stadt für das Staatstheater?",
    "Wie hoch ist der Verlust des Klinikums?",
    "Wie ist der Stand beim Stadion?",
    "Was hat der Rat zur Baumschutzsatzung beschlossen?",
]


@pytest.mark.parametrize("frage", ZIEHT)
def test_erkennung_zieht(frage):
    assert "business_plans" in qa.geld_facetten(frage, "topic"), frage


@pytest.mark.parametrize("frage", ZIEHT_NICHT)
def test_erkennung_zieht_nicht(frage):
    assert "business_plans" not in qa.geld_facetten(frage, "topic"), frage


def test_die_alten_facetten_bleiben_stehen():
    """Die neue Facette nimmt keiner alten etwas weg und legt keiner etwas
    dazu — „eigenbetrieb" zog den Konzern schon vorher, und das bleibt."""
    assert qa.geld_facetten("Wie viel Schulden hat Oldenburg?", "topic") == {"schulden"}
    assert qa.geld_facetten("Was planen die Eigenbetriebe?",
                            "topic") == {"konzern", "business_plans"}


# ---------------------------------------------------------------------------
# 2. Inhalt
# ---------------------------------------------------------------------------

#: (Betrieb, Name, Jahr, Erträge, Aufwendungen, Ergebnis, Vermögensplan,
#:  Investitionen, VE) — im Zuschnitt des echten Bestands: ein Betrieb mit
#: vollem Erfolgsplan, einer mit nur der Kernzahl, einer, dessen Reihe endet.
ZEILEN = [
    ("gebaeude", "Eigenbetrieb Gebäudewirtschaft", 2026, 82_815_150.0,
     82_824_771.0, -15_621.0, 51_134_100.0, None, 104_980_000.0),
    ("gebaeude", "Eigenbetrieb Gebäudewirtschaft", 2025, 70_497_300.0,
     75_894_925.0, -5_401_285.0, 59_631_400.0, None, None),
    ("abfall", "Abfallwirtschaftsbetrieb", 2026, 26_747_250.0, 26_036_000.0,
     711_250.0, None, None, None),
    ("abfall", "Abfallwirtschaftsbetrieb", 2025, 25_197_796.0, 24_570_285.0,
     627_511.0, None, None, None),
    ("baeder", "Bäderbetrieb der Stadt", 2026, None, None, 0.0, None,
     10_752_000.0, None),
    ("hafen", "Eigenbetrieb Hafen", 2020, None, None, -400_000.0, None, None, None),
    ("hafen", "Eigenbetrieb Hafen", 2019, None, None, -300_000.0, None, None, None),
]


def _store(tmp_path) -> CouncilStore:
    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_provenance (id, key, kind, label, url, citation, "
            " probe, as_of, fetched_at) VALUES "
            "(1, 'w1', 'ris', 'Abfallwirtschaftsbetrieb: Wirtschaftsplan 2026', "
            " 'https://example.org/vo', 'Erfolgsplan der Anlage', "
            " 'business_plan_columns', 'Wirtschaftsplan 2026', '2026-09-02')")
        for (kuerzel, name, jahr, ertrag, aufwand, ergebnis,
             vermoegen, invest, ve) in ZEILEN:
            store._conn.execute(
                "INSERT INTO council_business_plans (enterprise, year, enterprise_name, "
                " template_number, revenues, expenses, taxes, result, capital_plan, "
                " investments, commitments, probes, herkunft_id, fetched_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, 'business_plan_columns', 1, "
                " '2026-09-02')",
                (kuerzel, jahr, name, f"25/{jahr}", ertrag, aufwand, ergebnis,
                 vermoegen, invest, ve))
    return store


def test_begriffe_waehlen_den_betrieb(tmp_path):
    store = _store(tmp_path)
    daten = store.business_plans_context(["Müll", "Abfall", "Tonne"])
    assert daten["detail"] is True and daten["year"] == 2026
    assert [p["enterprise"] for p in daten["plans"]] == ["abfall"]
    p = daten["plans"][0]
    assert (p["year"], p["result"]) == (2026, 711_250.0)
    assert p["prior"] == {"year": 2025, "result": 627_511.0}
    text = business_plans.block(daten)
    assert "Ergebnis 711.250 €" in text
    assert "im Plan 2025 waren es 627.511 €" in text
    assert "Erfolgsplan: Erträge 26,7 Mio. €, Aufwendungen 26,0 Mio. €" in text
    store.close()


def test_ohne_treffer_kommt_der_jahrgang(tmp_path):
    """Der Überblick zeigt den JAHRGANG, nicht den Bestand: Der aufgelöste
    Hafenbetrieb gehört nicht neben lauter aktuelle Pläne."""
    store = _store(tmp_path)
    daten = store.business_plans_context(["Was", "planen", "die", "Eigenbetriebe"])
    assert daten["detail"] is False
    # Nach dem Ausschlag sortiert — nicht nach der Größe des Betriebs: Der
    # Eigenbetrieb Gebäudewirtschaft plant 82 Mio. € Erträge und landet mit
    # seinem ausgeglichenen Ergebnis (−15.621 €) trotzdem hinten. Und ohne den
    # Betrieb, den es 2026 nicht mehr gibt.
    assert [p["enterprise"] for p in daten["plans"]] == ["abfall", "gebaeude", "baeder"]
    text = business_plans.block(daten)
    assert "Eigenbetrieb Hafen" not in text
    assert "NIE addieren" in text
    store.close()


def test_ausgeglichener_plan_sagt_was_die_null_heisst(tmp_path):
    store = _store(tmp_path)
    text = business_plans.block(store.business_plans_context(["Bäder", "Schwimmbad"]))
    assert "Ergebnis 0 € (ausgeglichener Plan" in text
    assert "Erträge und Aufwendungen nennt diese Quelle nicht" in text
    assert "davon Investitionen 10,8 Mio. €" in text
    store.close()


def test_gefragtes_jahr_wird_geliefert(tmp_path):
    store = _store(tmp_path)
    daten = store.business_plans_context(["Gebäude", "Schulen"], 2025)
    assert daten["year"] == 2025 and "year_asked" not in daten
    p = daten["plans"][0]
    assert (p["year"], p["result"]) == (2025, -5_401_285.0)
    text = business_plans.block(daten)
    assert "Vermögensplan 59,6 Mio. €" in text
    store.close()


def test_beendete_reihe_sagt_dass_sie_endet(tmp_path):
    store = _store(tmp_path)
    text = business_plans.block(store.business_plans_context(["Hafen", "Liegeplätze"]))
    assert "Wirtschaftsplan 2020" in text
    assert "keinen Wirtschaftsplan mehr vor" in text
    store.close()


def test_fehlendes_jahr_faellt_auf_das_juengste_und_sagt_es(tmp_path):
    store = _store(tmp_path)
    daten = store.business_plans_context(["Müll", "Abfall"], 2005)
    assert daten["year"] == 2026 and daten["year_asked"] == 2005
    assert ("ACHTUNG: Einen Wirtschaftsplan-Jahrgang 2005 gibt es nicht"
            in business_plans.block(daten))
    store.close()


def test_leere_datenbank_liefert_nichts(tmp_path):
    store = CouncilStore(tmp_path / "leer.sqlite")
    assert store.business_plans_context(["Abfall"]) is None
    assert business_plans.block(None) == ""
    store.close()


# ---------------------------------------------------------------------------
# 3. Größe an echten Zahlen
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("frage,begriffe", [
    ("Was planen die Eigenbetriebe?", "Eigenbetriebe Wirtschaftsplan"),
    ("Was steht im Wirtschaftsplan des Abfallwirtschaftsbetriebs?",
     "Abfallwirtschaftsbetrieb Müll Gebühren"),
    ("Was stand im Wirtschaftsplan 2005 des Bäderbetriebs?", "Bäder Schwimmbad"),
])
def test_bausteingroesse_am_echten_bestand(frage, begriffe, tmp_path):
    if not ECHTE_DB.exists():
        pytest.skip("dev-Datenbank nicht vorhanden")
    kopie = tmp_path / "c.sqlite"
    kopie.write_bytes(ECHTE_DB.read_bytes())
    store = CouncilStore(kopie)
    try:
        daten = store.business_plans_context(begriffe.split(), qa.haushaltsjahr(frage))
        text = business_plans.block(daten)
        assert text, frage
        assert len(text) <= business_plans.FACETTE.grenze, (frage, len(text))
    except sqlite3.OperationalError as e:      # veralteter Dump
        pytest.skip(str(e))
    finally:
        store.close()


def _mit_abschluss(store: CouncilStore, enterprise: str, year: int, **werte) -> CouncilStore:
    """Die Kennzahlen eines Jahresabschlusses dazu (Schicht seit #981)."""
    with store._conn:
        for metric, value in werte.items():
            store._conn.execute(
                "INSERT INTO council_enterprise_accounts (enterprise, year, metric, value, unit, "
                "report_year, confirmations, conflicts, document_id, probes, herkunft_id, fetched_at) "
                "VALUES (?, ?, ?, ?, 'TEUR', ?, 2, 0, 1, 'enterprise_accounts_overlap', 1, '2026-09-02')",
                (enterprise, year, metric, value, year + 1))
    return store


def test_ist_laut_jahresabschluss_steht_beim_plan(tmp_path):
    """Plan ist nicht Abschluss — aber wo der Abschluss vorliegt, steht er als
    eigene Zeile daneben. Gleiches Jahr: Vergleich mit dem Plan-Ergebnis;
    sonst der jüngste Abschluss mit dem Vermerk, dass der des Planjahrs fehlt."""
    store = _mit_abschluss(_store(tmp_path), "abfall", 2025,
                           revenues=23_824_000, result=294_000, balance_total=25_500_000)
    try:
        d = store.business_plans_context(["abfallwirtschaftsbetrieb"], 2025)
        text = business_plans.block(d)
        assert "IST laut geprüftem Jahresabschluss 2025: Umsatzerlöse 23,8 Mio. €, Jahresergebnis 294.000 €, Bilanzsumme 25,5 Mio. €" in text
        assert "gegenüber dem Plan-Ergebnis 627.511 €" in text and "2 Berichte nennen dieselbe Zahl" in text
        d = store.business_plans_context(["abfallwirtschaftsbetrieb"], 2026)
        text = business_plans.block(d)
        assert "jüngster Abschluss; für 2026 liegt noch keiner vor" in text
    finally:
        store.close()
