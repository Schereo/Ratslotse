"""Die Facette `measures` — die einzelnen Vorhaben des Investitionsprogramms.

Drei Messungen: welche Fragen sie ziehen, was die Store-Methode aus einem
kleinen echten Bestand holt, und wie groß ihr Baustein an der Dev-Datenbank
wird. Kein LLM-Aufruf; alles deterministisch."""
import os
import sqlite3
from pathlib import Path

import pytest

from council import qa
from council.geld import measures
from council.store import CouncilStore

NAME = measures.NAME

#: Die echte Datenbank für die Zeichen-Messung, gefunden wie in den
#: Ingest-Skripten: ``COUNCIL_DB``, sonst ``data/council.sqlite``. In der CI
#: gibt es sie nicht — dort entfällt der Test, und das ist richtig so: Er misst
#: Zeichen an echten Zahlen, und die kann ein Fixture nicht ersetzen. Gemessen
#: wurde am dev-Stand vom 02.09.2026.
DEV_DB = Path(os.environ.get("COUNCIL_DB")
              or Path(__file__).resolve().parents[1] / "data" / "council.sqlite")


class _NurLesen(measures.Store):
    """Die Facette auf einer schreibgeschützten Datenbank.

    ``CouncilStore`` würde beim Öffnen migrieren, also schreiben — auf der
    Dev-Kopie ist das verboten. Gebraucht werden nur die drei Dinge, die der
    Vertrag der Facette zusichert: ``_conn``, ``_trifft`` und ``_beleg``."""
    _trifft = CouncilStore._trifft
    _beleg = CouncilStore._beleg

    def __init__(self, pfad: str):
        self._conn = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
        self._conn.row_factory = sqlite3.Row


# ---------------------------------------------------------------------------
# 1. Erkennung
# ---------------------------------------------------------------------------

ZIEHT = [
    "Was kostet der Ausbau der Nadorster Straße?",
    "Wird die Cäcilienbrücke saniert?",
    "Welche Vorhaben stehen im Investitionsprogramm?",
    "Wie viel kostet der Neubau der Feuerwache?",
    "Was wird an der Kreuzung Alexanderstraße gebaut?",
    "Wie viel investiert die Stadt?",          # angedockt an `investitionen`
]

#: Die drei Pflicht-Negativen aus dem Auftrag stehen vorn: Themenfragen ohne
#: Geld- und ohne Vorhaben-Anker. „Cäcilienbrücke" ist die härteste — sie
#: enthält „bruecke" als Wortende und darf trotzdem nichts ziehen.
ZIEHT_NICHT = [
    "Wie ist der Stand beim Stadion?",
    "Was hat der Rat zum Bebauungsplan Fliegerhorst beschlossen?",
    "Wann wurde die Cäcilienbrücke gesperrt?",
    "Wie hoch sind die Schulden der Stadt?",
    "Wie viele Stellen sind unbesetzt?",
    "Wie hoch waren die Steuereinnahmen 2024?",
]


@pytest.mark.parametrize("frage", ZIEHT)
def test_vorhaben_fragen_ziehen_die_facette(frage):
    gefunden = qa.geld_facetten(frage, "topic")
    assert NAME in gefunden, (frage, sorted(gefunden))


@pytest.mark.parametrize("frage", ZIEHT_NICHT)
def test_themenfragen_ziehen_sie_nicht(frage):
    assert NAME not in qa.geld_facetten(frage, "topic"), frage


def test_bauwerk_ohne_geld_anker_zieht_nichts():
    """Ein Bauwerk ist genauso gut ein Thema.

    Der Testkorpus (tests/test_qa_geldquellen.py) hält beide Radweg-Fragen
    ausdrücklich für Fragen OHNE Haushalts-Bezug: Die eine fragt nach einem
    Beschluss, die andere nach einem Antragsteller. Erst mit einem Geld-Wort
    wird daraus eine Frage an das Investitionsprogramm."""
    for frage in ("Was wurde zum Radweg an der Donnerschweer Straße beschlossen?",
                  "Wer stellte den Antrag zum Radweg?",
                  "Wie lange ist die Brücke gesperrt?"):
        assert NAME not in qa.geld_facetten(frage, "topic"), frage
    assert NAME in qa.geld_facetten(
        "Was kostet der Radweg an der Donnerschweer Straße?", "topic")


def test_positionsfrage_ohne_geld_zieht_nichts():
    """„Was sagte die SPD zum Stadionneubau?" trägt ein Bau-Wort und meint
    trotzdem eine Position. Dieselbe Bremse wie bei `investitionen`."""
    frage = "Was sagte die SPD zum Stadionneubau?"
    assert NAME not in qa.geld_facetten(frage, "party")
    # Mit Geld-Anker im Wortlaut kippt es — dann ist es eine Kostenfrage.
    assert NAME in qa.geld_facetten(
        "Was sagte die SPD zu den Kosten des Stadionneubaus?", "party")


@pytest.mark.parametrize("frage,alte", [
    # Seit #953 zieht eine Kosten-Frage auch den Ansatz (Posten-Ebene).
    ("Was kostet der Ausbau der Nadorster Straße?", {"plan", "produkte", "ansatz"}),
    ("Wie viel investiert die Stadt?", {"investitionen", "gebaut"}),
    ("Welche Vorhaben stehen im Investitionsprogramm?", {"investitionen", "gebaut"}),
    ("Wird die Cäcilienbrücke saniert?", set()),
])
def test_die_alten_facetten_bleiben_unverschoben(frage, alte):
    """Die neue Facette darf nur sich selbst hinzufügen."""
    assert qa.geld_facetten(frage, "topic") - {NAME} == alte


# ---------------------------------------------------------------------------
# 2. Inhalt
# ---------------------------------------------------------------------------

def _store(tmp_path) -> CouncilStore:
    """Zwei Jahrgänge Investitionsprogramm im Zuschnitt des echten Bestands."""
    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_provenance (id, key, kind, label, url, "
            " citation, probe, as_of, fetched_at) VALUES "
            "(1, 'k1', 'ris', 'Investitionsprogramm 2026', "
            " 'https://example.org/ip2026', 'Anlage 004, Spalte "
            " „Gesamtinvestitionssumme“', 'capital_programme_section_total', "
            " 'Stand der Einbringung', '2026-08-30')")
        for jahr, no, name in [(2025, 8, "Verkehr und Straßenbau"),
                               (2026, 8, "Verkehr und Straßenbau"),
                               (2026, 12, "Schule und Bildung")]:
            store._conn.execute(
                "INSERT INTO council_investment_measures (year, level, "
                " sub_budget_no, code, label, grand_total, fetched_at, "
                " herkunft_id) VALUES (?, 'sub_budget', ?, '', ?, 0, '', 1)",
                (jahr, no, name))
        for jahr, no, code, name, summe, details in [
                (2026, 8, "I10.180700", "SG Untere Nadorster Straße",
                 4_294_800.0, "SG Untere Nadorster Straße, Grundstücke"),
                (2025, 8, "I10.180700", "SG Untere Nadorster Straße",
                 1_200_000.0, None),
                (2026, 8, "I10.190326", "Erneuerung Straßenbeleuchtung",
                 800_000.0, None),
                (2026, 12, "I10.070426", "StartChancen-Programm",
                 300_000.0, "Schulausstattung")]:
            store._conn.execute(
                "INSERT INTO council_investment_measures (year, level, "
                " sub_budget_no, code, label, grand_total, details, "
                " fetched_at, herkunft_id) VALUES (?, 'measure', ?, ?, ?, ?, "
                " ?, '', 1)", (jahr, no, code, name, summe, details))
    return store


def test_liefert_das_vorhaben_zum_begriff(tmp_path):
    store = _store(tmp_path)
    daten = store.measures_context(["Nadorster"], None)
    assert daten["year"] == 2026
    assert [m["label"] for m in daten["measures"]] == ["SG Untere Nadorster Straße"]
    assert daten["measures"][0]["sub_budget"] == "Verkehr und Straßenbau"
    assert daten["measures"][0]["davor"]["year"] == 2025
    text = measures.block(daten)
    assert "4,3 Mio. €" in text and "im Programm 2025 noch 1,2 Mio. €" in text
    assert "SCHULGEBÄUDE FEHLEN HIER" in text
    assert "Beleg: Investitionsprogramm 2026" in text
    store.close()


def test_findet_ueber_die_detailzeilen(tmp_path):
    """Straßennamen stehen mal im Kurznamen, mal nur in den Sachkonto-Zeilen."""
    store = _store(tmp_path)
    daten = store.measures_context(["Schulausstattung"], None)
    assert [m["label"] for m in daten["measures"]] == ["StartChancen-Programm"]
    store.close()


def test_gefragtes_jahr_wird_geliefert(tmp_path):
    store = _store(tmp_path)
    daten = store.measures_context(["Nadorster"], 2025)
    assert daten["year"] == 2025 and daten["year_deviates"] is False
    assert daten["measures"][0]["grand_total"] == 1_200_000.0
    assert "Jahrgang" not in measures.block(daten)
    store.close()


def test_fehlendes_jahr_faellt_auf_das_juengste_und_sagt_es(tmp_path):
    store = _store(tmp_path)
    daten = store.measures_context(["Nadorster"], 2019)
    assert daten["year"] == 2026 and daten["year_deviates"] is True
    assert "Zum Haushaltsjahr 2019 liegt kein Investitionsprogramm vor" \
        in measures.block(daten)
    store.close()


def test_ohne_begriffstreffer_kommt_nichts(tmp_path):
    """Die Summen macht `investitionen` — fünf zufällige Zeilen sind keine
    Antwort auf eine Vorhaben-Frage."""
    store = _store(tmp_path)
    assert store.measures_context(["Schwimmbad", "Eishalle"], None) is None
    # Und Allerwelts-Begriffe der Query-Expansion zählen nicht als Treffer.
    assert store.measures_context(["Investition", "Stadt", "Bau"], None) is None
    assert measures.block(None) == ""
    store.close()


# ---------------------------------------------------------------------------
# 3. Größe
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("frage", [
    "Was kostet der Ausbau der Nadorster Straße?",
    "Wie viel kostet die Sanierung der Ammerländer Heerstraße?",
    "Welche Vorhaben stehen im Investitionsprogramm für den Stadthafen?",
])
def test_baustein_bleibt_unter_der_grenze(frage):
    if not DEV_DB.exists():
        pytest.skip("keine Dev-Datenbank zum Messen")
    store = _NurLesen(str(DEV_DB))
    daten = store.measures_context(frage.split(), qa.haushaltsjahr(frage))
    text = measures.block(daten)
    assert text, frage
    assert len(text) <= measures.FACETTE.grenze, (frage, len(text))
