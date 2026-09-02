"""Die Facette `execution` — der Haushaltsvollzug in der KI-Frage.

Drei Messungen, wie es der Vertrag in ``council/geld/__init__.py`` vorsieht:
welche Fragen sie ziehen, was die Store-Methode liefert und wie groß ihr
Baustein an echten Zahlen wird. Kein LLM-Aufruf.
"""
from datetime import date
from pathlib import Path

import pytest

from council import qa
from council.geld import execution
from council.store import CouncilStore

#: Die dev-Kopie für die Größen-Messung. Nur lesen — sie wird kopiert.
ECHTE_DB = Path(
    "/private/tmp/claude-501/-Users-tim-Documents-kommunalwahl-scraper--"
    "claude-worktrees-haushaltsseite-review-763d8c/"
    "1759b603-5a3e-439a-95af-ccd796425871/scratchpad/data/council.sqlite")


# --- 1. Erkennung ---------------------------------------------------------

@pytest.mark.parametrize("frage", [
    "Wie läuft der Haushalt im laufenden Jahr?",
    "Was steht im Finanz- und Leistungsbericht?",
    "Wie ist der Zwischenstand beim Haushalt?",
    "Was erwartet die Verwaltung für den Etat zum Jahresende?",
    "Liegt der Haushalt nach Plan?",
    "Wie viel hat die Stadt 2026 ausgegeben?",
])
def test_diese_fragen_ziehen_den_vollzug(frage):
    assert "execution" in qa.geld_facetten(frage, "topic"), frage


@pytest.mark.parametrize("frage", [
    # Die Nachbarn, bei denen ein zu weites Muster zuerst fehlfeuert:
    # „Prognose" ohne Geld, „Stand" als Sachstand einer Sache, „laufend" als
    # laufendes Verfahren, „Stand" als Verb der Vergangenheit.
    "Wie ist die Bevölkerungsprognose für Oldenburg?",
    "Wie ist der Stand beim Stadion?",
    "Was wird im laufenden Verfahren zur Cäcilienbrücke beraten?",
    "Was stand in der Haushaltssatzung 2020?",
    "Was ist am Fliegerhorst geplant?",
    "Hat die Stadt 2024 mehr ausgegeben als geplant?",
])
def test_diese_fragen_ziehen_ihn_nicht(frage):
    assert "execution" not in qa.geld_facetten(frage, "topic"), frage


def test_die_alten_facetten_verschieben_sich_nicht():
    """Die Nachbarfragen behalten genau die Quellen, die sie vorher hatten."""
    assert qa.geld_facetten("Welche Änderungslisten gab es zum Haushalt 2026?",
                            "topic") == {"plan", "ansatz", "antraege", "amendments"}
    assert qa.geld_facetten("Hat die Stadt 2024 mehr ausgegeben als geplant?",
                            "money") == {"plan", "ist", "kassensicht"}
    assert qa.geld_facetten("Wie ist der Stand beim Stadion?", "history") == set()


def test_das_jahr_ohne_abschluss_zieht_ihn_mit():
    """Zweite Regel: Für Jahre ohne Jahresabschluss ist der Vollzug die
    einzige Quelle zum „was wurde daraus". Das Jahr wird gerechnet, damit der
    Test nicht am 1. Januar rot wird."""
    ohne_abschluss = date.today().year
    mit_abschluss = date.today().year - 3
    assert "execution" in qa.geld_facetten(
        f"Wie viel hat die Stadt {ohne_abschluss} ausgegeben?", "money")
    assert "execution" not in qa.geld_facetten(
        f"Wie viel hat die Stadt {mit_abschluss} ausgegeben?", "money")


# --- 2. Inhalt ------------------------------------------------------------

def _store(tmp_path) -> CouncilStore:
    """Zwei Jahrgänge im Zuschnitt des Bestands: 2019 mit zwei Stichtagen und
    der alten Ansatz-Basis, 2026 mit einem und der neuen."""
    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_provenance (id, key, kind, label, url, citation, "
            " probe, as_of, fetched_at) VALUES "
            "(1, 'k1', 'ris', 'Finanz- und Leistungsbericht zum 30. Juni 2026', "
            " 'https://example.org/flb', 'Auswertung der Berichte zum 30.06.2026, "
            "1. Ergebnishaushalt', 'execution_row', "
            "'Finanz- und Leistungsbericht zum 30.06.2026', '2026-09-02')")
        zeilen = [
            # (jahr, stichtag, haushalt, teil, art, label, ansatz, prognose,
            #  abweichung, basis, summe?)
            (2019, "2019-06-30", "result", 0, "result", "Summen",
             -20_000_000.0, -25_000_000.0, -5_000_000.0, "budget_plus_carryover", 1),
            (2019, "2019-09-30", "result", 0, "result", "Summen",
             -20_000_000.0, -18_000_000.0, 2_000_000.0, "budget_plus_carryover", 1),
            (2026, "2026-06-30", "result", 0, "result", "Summen",
             -68_679_446.0, -66_033_353.0, 2_646_093.0, "budget", 1),
            (2026, "2026-06-30", "result", 0, "revenue", "Summen",
             816_700_942.0, 835_207_715.0, 18_506_773.0, "budget", 1),
            (2026, "2026-06-30", "result", 0, "expense", "Summen",
             885_380_387.0, 901_241_068.0, 15_860_681.0, "budget", 1),
            (2026, "2026-06-30", "result", 10, "result", "Soziales und Gesundheit",
             -113_195_538.0, -116_616_049.0, -3_420_511.0, "budget", 0),
            (2026, "2026-06-30", "result", 12, "result", "Schule und Bildung",
             -65_102_693.0, -66_419_113.0, -1_316_420.0, "budget", 0),
            (2026, "2026-06-30", "cash", 0, "result", "Summen",
             -52_960_632.0, -51_160_788.0, 1_799_844.0, "budget", 1),
        ]
        for z in zeilen:
            store._conn.execute(
                "INSERT INTO council_budget_execution (budget_year, as_of, budget, "
                " sub_budget, kind, label, budgeted, forecast, deviation, "
                " plan_basis, is_total, probes, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,'execution_row',1,'')", z)
    return store


def test_liefert_den_juengsten_stichtag_des_jahrgangs(tmp_path):
    store = _store(tmp_path)
    d = store.execution_context(["Haushalt", "Ergebnis"], 2019)
    assert d["year"] == 2019 and d["as_of"] == "2019-09-30"
    assert d["ergebnis"]["forecast"] == -18_000_000.0
    # Beide Stichtage stehen als Verlauf daneben.
    assert [v["as_of"] for v in d["verlauf"]] == ["2019-06-30", "2019-09-30"]
    assert not d["anderer_jahrgang"]
    store.close()


def test_fehlendes_jahr_faellt_auf_das_juengste_zurueck(tmp_path):
    store = _store(tmp_path)
    d = store.execution_context(["Haushalt"], 2021)
    assert d["year"] == 2026 and d["anderer_jahrgang"]
    assert "Für das gefragte Jahr liegt kein Bericht vor" in execution.block(d)
    store.close()


def test_begriffe_waehlen_die_teilhaushalte(tmp_path):
    store = _store(tmp_path)
    d = store.execution_context(["Soziales", "Gesundheit"], 2026)
    assert [r["label"] for r in d["bereiche"]] == ["Soziales und Gesundheit"]
    # Ohne Treffer kommt KEIN Teilhaushalt — dreizehn wären der halbe Prompt.
    assert store.execution_context(["Stadion"], 2026)["bereiche"] == []
    store.close()


def test_finanzhaushalt_nur_bei_investitions_begriffen(tmp_path):
    store = _store(tmp_path)
    assert store.execution_context(["Haushalt", "Ergebnis"],
                                   2026)["finanzhaushalt"] is None
    d = store.execution_context(["Investitionen", "Auszahlungen"], 2026)
    assert d["finanzhaushalt"]["forecast"] == -51_160_788.0
    assert "Saldo aus Investitionen" in execution.block(d)
    store.close()


def test_der_baustein_sagt_prognose_und_nie_tatsaechlich(tmp_path):
    store = _store(tmp_path)
    text = execution.block(store.execution_context(["Haushalt"], 2026))
    assert "erwartet" in text and "tatsächlich" not in text.split("NIE")[-1]
    assert "Beleg: Finanz- und Leistungsbericht zum 30. Juni 2026" in text
    assert "NIE mit [id]" in text
    # Die alte Ansatz-Basis wird nur dort angeschrieben, wo sie gilt.
    assert "Ermächtigungsübertragungen" not in text
    assert "Ermächtigungsübertragungen" in execution.block(
        store.execution_context(["Haushalt"], 2019))
    store.close()


def test_leere_datenbank_liefert_nichts(tmp_path):
    store = CouncilStore(tmp_path / "leer.sqlite")
    assert store.execution_context(["Haushalt"], 2026) is None
    assert execution.block(None) == ""
    store.close()


# --- 3. Größe -------------------------------------------------------------

@pytest.mark.parametrize("frage,begriffe", [
    ("Wie läuft der Haushalt im laufenden Jahr?", "Haushalt Ergebnis Prognose"),
    ("Wie steht der Haushalt bei Soziales und Jugend im Zwischenbericht?",
     "Soziales Jugend Familie Gesundheit Haushalt"),
    ("Wie lief der Haushalt 2019?", "Haushalt Ergebnis Investitionen Auszahlungen"),
])
def test_bausteingroesse_an_echten_zahlen(frage, begriffe, tmp_path):
    if not ECHTE_DB.exists():
        pytest.skip("dev-Datenbank nicht vorhanden")
    kopie = tmp_path / "council.sqlite"
    kopie.write_bytes(ECHTE_DB.read_bytes())
    store = CouncilStore(kopie)
    daten = store.execution_context(begriffe.split(), qa.haushaltsjahr(frage))
    text = execution.block(daten)
    assert 700 < len(text) <= execution.FACETTE.grenze, (frage, len(text))
    store.close()
