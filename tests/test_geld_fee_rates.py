"""Die Facette `fee_rates` — die Gebührensätze aus der Anlage 4.

Prüfstein: „Was kostet die Tonne?" zieht die Sätze, „Warum sind die Gebühren
so hoch?" darf sie mitziehen (die alte `fees` liefert die Bedarfsberechnung
dazu), und Fragen ohne Abfall oder Straßenreinigung ziehen nichts."""
import pytest

from council import qa
from council.geld import fee_rates
from council.store import CouncilStore

NAME = fee_rates.NAME

ZIEHT = [
    "Was kostet eine Restmülltonne in Oldenburg?",
    "Wie hoch ist die Grundgebühr für Müll 2025?",
    "Was kostet die Sperrmüllkarte?",
    "Wie teuer ist die Straßenreinigungsgebühr je Meter?",
    "Wird der Müll 2026 teurer?",
]
ZIEHT_NICHT = [
    "Wie hoch sind die Schulden der Stadt?",
    "Was kostet die Feuerwehr?",
    "Wie hoch ist der Hebesatz für die Grundsteuer B?",
    "Was kostet der Neubau der Schule?",
]


@pytest.mark.parametrize("frage", ZIEHT)
def test_gebuehrenfragen_ziehen_die_facette(frage):
    assert NAME in qa.geld_facetten(frage, "topic"), frage


@pytest.mark.parametrize("frage", ZIEHT_NICHT)
def test_andere_kostenfragen_ziehen_sie_nicht(frage):
    assert NAME not in qa.geld_facetten(frage, "topic"), frage


def _store(tmp_path) -> CouncilStore:
    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_provenance (id, key, kind, label, url, citation, probe, "
            "as_of, fetched_at) VALUES (1, 'k1', 'ris', 'Gebührenbedarfsberechnung 2026', "
            "'https://example.org/g', 'Anlage 4', 'fee_rate_count', 'Vorschlag 2026', '2026-08-30')")
        for year, key, area, label, amount, unit, prior, pct in (
                (2026, "per_litre_fee", "waste_collection", "Allgemeine Litergebühr", 0.0323,
                 "Liter Behältervolumen", 0.0301, 7.3),
                (2026, "base_fee", "waste_collection", "Grundgebühr", 52.0, "Grundgebühr", 50.0, 4.0),
                (2026, "street_cleaning_per_metre", "street_cleaning",
                 "Gebühr je Meter Quadratwurzel bei wöchentlicher Reinigung", 4.039,
                 "Meter Quadratwurzel", 3.66, 10.4),
                (2025, "base_fee", "waste_collection", "Grundgebühr", 50.0, "Grundgebühr", 48.0, 4.2)):
            store._conn.execute(
                "INSERT INTO council_fee_rates (year, key, area, label, amount, unit, prior_year, "
                "change_pct, template_number, probes, herkunft_id, fetched_at) VALUES "
                "(?,?,?,?,?,?,?,?,'25/0644','fee_rate_count',1,'2026-08-30')",
                (year, key, area, label, amount, unit, prior, pct))
    return store


def test_saetze_mit_einheit_vorjahr_und_beleg(tmp_path):
    store = _store(tmp_path)
    try:
        d = store.fee_rates_context(["restmuelltonne"], None)
        assert d["year"] == 2026 and len(d["rates"]) == 3
        b = fee_rates.block(d)
        assert "0,0323 € je Liter Behältervolumen" in b
        assert "Grundgebühr (Abfallsammlung): 52,00 €" in b
        assert "(Vorjahr 3,66 €, 10,4 %)" in b
        assert "Beleg: Gebührenbedarfsberechnung 2026, Anlage 4" in b
        # Die Abfallsammlung steht vor der Straßenreinigung.
        assert b.index("Grundgebühr") < b.index("Quadratwurzel")
    finally:
        store.close()


def test_gefragtes_jahr_und_abweichung(tmp_path):
    store = _store(tmp_path)
    try:
        d = store.fee_rates_context([], 2025)
        assert d["year"] == 2025 and not d["year_deviates"]
        d = store.fee_rates_context([], 2021)
        assert d["year"] == 2026 and d["year_deviates"]
        assert "keine Gebührensätze im Bestand (Reihe 2025–2026)" in fee_rates.block(d)
    finally:
        store.close()
