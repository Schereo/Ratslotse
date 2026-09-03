"""Die Facette `expense_series` — die lange Ausgabenreihe seit 1972.

Zwei Dinge misst diese Datei besonders: dass die Facette einen Geld-Anker
verlangt (sonst hinge sie an jeder Entwicklungs-Frage) und dass der Baustein
die Naht 2009/2010 immer anschreibt (sonst wird aus zwei Rechnungswesen eine
Entwicklung)."""
import os
import sqlite3
from pathlib import Path

import pytest

from council import qa
from council.geld import expense_series
from council.store import CouncilStore

NAME = expense_series.NAME

#: Die echte Datenbank für die Zeichen-Messung, gefunden wie in den
#: Ingest-Skripten: ``COUNCIL_DB``, sonst ``data/council.sqlite``. In der CI
#: gibt es sie nicht — dort entfällt der Test, und das ist richtig so: Er misst
#: Zeichen an echten Zahlen, und die kann ein Fixture nicht ersetzen. Gemessen
#: wurde am dev-Stand vom 02.09.2026.
DEV_DB = Path(os.environ.get("COUNCIL_DB")
              or Path(__file__).resolve().parents[1] / "data" / "council.sqlite")


class _NurLesen(expense_series.Store):
    """Die Facette auf einer schreibgeschützten Datenbank (s. Vertrag in
    ``council/geld/__init__.py``: ``_conn``, ``_trifft``, ``_beleg``)."""
    _trifft = CouncilStore._trifft
    _beleg = CouncilStore._beleg

    def __init__(self, pfad: str):
        self._conn = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
        self._conn.row_factory = sqlite3.Row


# ---------------------------------------------------------------------------
# 1. Erkennung
# ---------------------------------------------------------------------------

ZIEHT = [
    "Wie haben sich die Ausgaben der Stadt seit 1972 entwickelt?",
    "Sind die Ausgaben über die Jahrzehnte gestiegen?",
    "Wie viel gab die Stadt 2005 aus?",
    "Wie hoch war der Haushalt 2015?",
    "Wie hat sich der Etat langfristig entwickelt?",
]

#: Vorn die beiden Pflicht-Negativen: einmal fehlt der Geld-Anker, einmal das
#: Langzeit-Wort.
ZIEHT_NICHT = [
    "Wie haben sich die Fahrgastzahlen entwickelt?",
    "Was kostet die Feuerwehr?",
    "Warum ist die Grundsteuer gestiegen?",
    "Wie ist der Stand beim Stadion?",
    "Wie viele Stellen sind unbesetzt?",
]


@pytest.mark.parametrize("frage", ZIEHT)
def test_langzeit_fragen_ziehen_die_facette(frage):
    gefunden = qa.geld_facetten(frage, "topic")
    assert NAME in gefunden, (frage, sorted(gefunden))


@pytest.mark.parametrize("frage", ZIEHT_NICHT)
def test_fragen_ohne_geld_oder_ohne_langzeit_ziehen_sie_nicht(frage):
    assert NAME not in qa.geld_facetten(frage, "topic"), frage


def test_warum_frage_setzt_ist_und_ist_trotzdem_kein_anker():
    """`ist` wird in qa.py auch von der Warum-Regel gesetzt, ohne dass im
    Wortlaut Geld vorkäme — deshalb zählt nur `plan` als Anker."""
    gefunden = qa.geld_facetten("Warum ist die Grundsteuer gestiegen?", "topic")
    assert "ist" in gefunden and NAME not in gefunden


@pytest.mark.parametrize("frage,alte", [
    ("Wie viel gab die Stadt 2005 aus?", set()),
    ("Sind die Ausgaben über die Jahrzehnte gestiegen?", {"plan"}),
])
def test_die_alten_facetten_bleiben_unverschoben(frage, alte):
    assert qa.geld_facetten(frage, "topic") - {NAME} == alte


# ---------------------------------------------------------------------------
# 2. Inhalt
# ---------------------------------------------------------------------------

#: Jahr, Regelwerk, Betrag, Widerspruch — der Zuschnitt der echten Reihe im
#: Kleinen, samt der Naht 2009/2010 und dem einen Konfliktjahr.
REIHE = [
    (1972, "kameral", 76_493_000.0, None),
    (1980, "kameral", 142_655_000.0, None),
    (1990, "kameral", 216_056_000.0, None),
    (2000, "kameral", 360_760_000.0, None),
    (2005, "kameral", 348_015_000.0, None),
    (2009, "kameral", 380_913_000.0, None),
    (2010, "doppik", 358_800_000.0, None),
    (2020, "doppik", 588_167_000.0, None),
    (2021, "doppik", 608_910_000.0, 613_572_000.0),
    (2025, "doppik", 850_170_000.0, None),
]


def _store(tmp_path) -> CouncilStore:
    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_provenance (id, key, kind, label, url, "
            " citation, probe, as_of, fetched_at) VALUES "
            "(1, 'k1', 'city', 'Statistisches Jahrbuch, Tabelle 1102', "
            " 'https://example.org/1102', 'Ausgaben je Haushaltsjahr', "
            " 'expense_series_per_capita', 'Haushaltsjahre 1972-2025', "
            " '2026-08-30')")
        for jahr, regel, betrag, konflikt in REIHE:
            store._conn.execute(
                "INSERT INTO council_expense_series (year, accounting_system, "
                " amount, source, probes, conflict_amount, conflict_source, "
                " fetched_at, herkunft_id) VALUES (?, ?, ?, 'pdf', "
                " 'expense_series_per_capita', ?, ?, '', 1)",
                (jahr, regel, betrag, konflikt, "csv" if konflikt else None))
    return store


def test_endpunkte_stuetzstellen_und_naht(tmp_path):
    store = _store(tmp_path)
    daten = store.expense_series_context([], None)
    assert daten["first"]["year"] == 1972 and daten["last"]["year"] == 2025
    assert [r["year"] for r in daten["supports"]] == [1980, 1990, 2000, 2010, 2020]
    assert daten["break_from"] == 2010
    text = expense_series.block(daten)
    assert "1972: 76,5 Mio. € · 2025: 850,2 Mio. €" in text
    assert "DIE NAHT 2009/2010" in text
    assert "NICHT direkt vergleichbar" in text
    assert "NICHT INFLATIONSBEREINIGT" in text
    assert "Beleg: Statistisches Jahrbuch, Tabelle 1102" in text
    # Ohne gefragtes Jahr keine Nachbarzeile — der Anker wäre sonst das
    # jüngste Jahr, das schon in der ersten Zeile steht.
    assert "Um das gefragte Jahr herum" not in text
    store.close()


def test_gefragtes_jahr_kommt_mit_seinen_nachbarn(tmp_path):
    store = _store(tmp_path)
    daten = store.expense_series_context([], 2005)
    assert daten["anchor"]["year"] == 2005 and daten["year_deviates"] is False
    text = expense_series.block(daten)
    assert "Um das gefragte Jahr herum: 2005: 348,0 Mio. €" in text
    store.close()


def test_fehlendes_jahr_faellt_auf_das_juengste_und_sagt_es(tmp_path):
    store = _store(tmp_path)
    daten = store.expense_series_context([], 1960)
    assert daten["anchor"]["year"] == 2025 and daten["year_deviates"] is True
    assert "Zu 1960 führt die Reihe keine Zeile" in expense_series.block(daten)
    store.close()


def test_widerspruch_steht_nur_an_seiner_eigenen_zahl(tmp_path):
    """Der Konflikt 2021 gehört zu SEINEM Wert. Steht das Jahr nicht im
    Baustein, wäre die Warnung 240 Zeichen über eine Zahl, die niemand sieht."""
    store = _store(tmp_path)
    ohne = expense_series.block(store.expense_series_context([], 2005))
    assert "widersprechen sich" not in ohne
    mit = expense_series.block(store.expense_series_context([], 2021))
    assert "Für 2021 widersprechen sich zwei amtliche Veröffentlichungen" in mit
    assert "608,9 Mio. € gegen 613,6 Mio. €" in mit
    store.close()


def test_leerer_bestand_bleibt_still(tmp_path):
    store = CouncilStore(tmp_path / "leer.sqlite")
    assert store.expense_series_context([], None) is None
    assert expense_series.block(None) == ""
    store.close()


# ---------------------------------------------------------------------------
# 3. Größe
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("frage", [
    "Wie haben sich die Ausgaben der Stadt seit 1972 entwickelt?",
    "Wie viel gab die Stadt 2005 aus?",
    "Sind die Ausgaben über die Jahrzehnte gestiegen?",
])
def test_baustein_bleibt_unter_der_grenze(frage):
    if not DEV_DB.exists():
        pytest.skip("keine Dev-Datenbank zum Messen")
    store = _NurLesen(str(DEV_DB))
    daten = store.expense_series_context(frage.split(), qa.haushaltsjahr(frage))
    text = expense_series.block(daten)
    assert text, frage
    assert len(text) <= expense_series.FACETTE.grenze, (frage, len(text))
