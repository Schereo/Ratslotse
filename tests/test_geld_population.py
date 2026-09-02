"""Die Facette `population` — die Einwohnerzahl.

Prüfstein: „Wie viele Einwohner?" bekommt die Reihe; Fragen nach dem Vermögen
je Einwohner ziehen sie als Nenner mit."""
import pytest

from council import qa
from council.geld import population
from council.store import CouncilStore

NAME = population.NAME

ZIEHT = [
    "Wie viele Einwohner hat Oldenburg?",
    "Wie viele Menschen lebten 2020 in Oldenburg?",
    "Wie hat sich die Bevölkerung entwickelt?",
]
ZIEHT_NICHT = [
    # „pro Kopf" rechnen `schulden` und `bilanz` selbst — der Korpus pinnt
    # die Schulden je Kopf auf `schulden` allein.
    "Wie viele Schulden hat die Stadt pro Kopf?",
    "Wie hoch sind die Schulden der Stadt?",
    "Was kostet die Feuerwehr?",
    "Wie ist der Stand beim Stadion?",
]


@pytest.mark.parametrize("frage", ZIEHT)
def test_einwohnerfragen_ziehen_die_facette(frage):
    assert NAME in qa.geld_facetten(frage, "topic"), frage


@pytest.mark.parametrize("frage", ZIEHT_NICHT)
def test_andere_fragen_ziehen_sie_nicht(frage):
    assert NAME not in qa.geld_facetten(frage, "topic"), frage


def _store(tmp_path) -> CouncilStore:
    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_provenance (id, key, kind, label, url, citation, probe, "
            "as_of, fetched_at) VALUES (1, 'k1', 'city', 'Datensatz 1102', "
            "'https://example.org/1102', 'Einwohner-Spalte', 'column_check', "
            "'2010–2025', '2026-08-30')")
        for year, n in ((2019, 168_210), (2020, 169_077), (2021, 169_605), (2022, 170_389),
                        (2023, 174_445), (2024, 176_242), (2025, 176_614)):
            store._conn.execute(
                "INSERT INTO council_einwohner (year, population, source_url, fetched_at, "
                "herkunft_id) VALUES (?, ?, 'https://example.org/1102', '2026-08-30', 1)", (year, n))
    return store


def test_juengstes_jahr_mit_fuenfjahresvergleich(tmp_path):
    store = _store(tmp_path)
    try:
        d = store.population_context([], None)
        assert d["latest"]["year"] == 2025 and d["five_years_ago"]["year"] == 2020
        b = population.block(d)
        assert "Einwohner*innen Ende 2025: 176.614" in b
        assert "Fünf Jahre zuvor (2020): 169.077 — plus 7.537 (4,5 %)" in b
        assert "Beleg: Datensatz 1102, Einwohner-Spalte" in b
    finally:
        store.close()


def test_gefragtes_jahr_und_fehlendes_jahr(tmp_path):
    store = _store(tmp_path)
    try:
        b = population.block(store.population_context([], 2020))
        assert "Für das gefragte Jahr 2020: 169.077" in b
        b = population.block(store.population_context([], 2005))
        assert "Für 2005 gibt es keinen Wert in der Reihe (2019–2025)" in b
    finally:
        store.close()
