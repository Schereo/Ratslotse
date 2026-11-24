"""Die Facette `holding_forecasts` — die Quartalsberichte der Beteiligungen.

Drei Messungen, wie für jede Modul-Facette (council/geld/): welche Fragen sie
zieht, was die Store-Methode liefert, wie groß ihr Baustein wird. Dazu die
Abgrenzung, derentwegen sie existiert: „Hochrechnung Klinikum 2025“ gehört
nicht mehr dem Haushaltsvollzug der Kernverwaltung. Kein LLM-Aufruf."""
import os
from pathlib import Path

import pytest

from council import holding_quarterly as hq, qa
from council.geld import holding_forecasts
from council.store import CouncilStore

FIX = Path(__file__).resolve().parent / "fixtures"
ECHTE_DB = Path(os.environ.get("RATSLOTSE_MESS_DB")
                or Path(__file__).resolve().parents[1] / "data" / "council.sqlite")

ZIEHT = [
    "Hält das Klinikum dieses Jahr seinen Plan laut Quartalsbericht?",
    "Wie lautet die Hochrechnung des Klinikums für 2025?",
    "Was sagt der Quartalsbericht zur VWG?",
    "Wie läuft die BBGO im laufenden Jahr gegen ihren Plan?",
    "Mit welchem Ergebnis rechnet die Weser-Ems-Halle dieses Jahr?",
    "Hochrechnung Klinikum 2025",
]

#: Ohne Unternehmen bleibt es beim Haushaltsvollzug; ein Unternehmen ohne
#: Hochrechnungs-Wort ist ein Fall für `companies`.
ZIEHT_NICHT = [
    "Wie läuft der Haushalt im laufenden Jahr?",
    "Was steht im Quartalsbericht zur Stadt?",
    "Wem gehört das Klinikum?",
    "Wie ist der Stand beim Stadion?",
    "Wie lief das Klinikum 2022?",
]


@pytest.mark.parametrize("frage", ZIEHT)
def test_erkennung_zieht(frage):
    assert "holding_forecasts" in qa.geld_facetten(frage, "topic"), frage


@pytest.mark.parametrize("frage", ZIEHT_NICHT)
def test_erkennung_zieht_nicht(frage):
    assert "holding_forecasts" not in qa.geld_facetten(frage, "topic"), frage


def test_hochrechnung_eines_unternehmens_geht_nicht_mehr_an_den_vollzug():
    """Der Anlass (Befund 23.11.2026): „Hochrechnung Klinikum 2025“ landete im
    Haushaltsvollzug der Kernverwaltung."""
    assert "execution" not in qa.geld_facetten("Hochrechnung Klinikum 2025", "topic")
    assert "execution" not in qa.geld_facetten(
        "Was sagt der Quartalsbericht zur Hochrechnung der VWG?", "topic")


def test_der_vollzug_behaelt_seine_fragen():
    for frage in ("Wie läuft der Haushalt im laufenden Jahr?",
                  "Was steht im Finanz- und Leistungsbericht?",
                  "Was steht im Quartalsbericht zur Stadt?",
                  # Nennt die Frage ausdrücklich den Bericht der Kernverwaltung,
                  # antwortet er auch neben einem Unternehmen.
                  "Wie steht der Haushaltsvollzug und wie das Klinikum?"):
        assert "execution" in qa.geld_facetten(frage, "topic"), frage


# --- Inhalt -------------------------------------------------------------------

def _store(tmp_path) -> CouncilStore:
    """Zwei Stände desselben Jahres plus ein Unternehmen mit Zuschussbedarf."""
    store = CouncilStore(tmp_path / "c.sqlite")
    titel = "Bericht zum {q}. Quartal 2025 der städtischen Beteiligungsunternehmen und Eigenbetriebe"
    q4 = hq.lies_bericht((FIX / "quartalsbericht_26_0124.txt").read_text(encoding="utf-8"),
                         titel.format(q=4), "26/0124", 7)
    store.save_holding_forecasts(q4, hq.herkunft_fuer(
        q4, document_id=7, label="Quartalsbericht 31.12.2025", url="https://example.org/q4"))
    return store


def test_store_liefert_stationen_je_unternehmen(tmp_path):
    store = _store(tmp_path)
    try:
        daten = store.holding_forecasts_context(["Hochrechnung", "Klinikum", "VWG"], 2025)
        assert [c["company"] for c in daten["companies"]] == ["klinikum", "vwg"]
        kol = daten["companies"][0]
        assert kol["year"] == 2025 and len(kol["stations"]) == 1
        assert kol["stations"][0]["forecast"] == -23_865_033
        assert "year_asked" not in daten
        # Ein Jahr ohne Bericht: das jüngste, und die Abweichung ist ausgesprochen.
        anders = store.holding_forecasts_context(["Klinikum"], 2019)
        assert anders["year_asked"] == 2019 and anders["companies"][0]["year"] == 2025
        assert store.holding_forecasts_context(["Haushalt"], 2025) is None
    finally:
        store.close()


def test_baustein_haelt_die_grenzen_ein(tmp_path):
    store = _store(tmp_path)
    try:
        text = holding_forecasts.block(
            store.holding_forecasts_context(["Hochrechnung", "Klinikum", "VWG"], 2025))
    finally:
        store.close()
    # Hochrechnung ist kein Ist; Plan und Hochrechnung nie verrechnet.
    assert "KEIN IST" in text and "NIE verrechnet" in text
    assert "keine „Fehlprognose“" in text
    # Plan heißt zweierlei: Die Art steht an jedem Wert.
    assert "geänderter Plan 2025 -14.972.040 €" in text
    assert "Plan 2025 -25.429.193 €" in text
    # Widerspruch Tabelle/Text: beide Werte stehen da.
    assert "-25.429.270 €" in text
    assert "Gesamtzuschussbedarf" in text and "Vorlage 26/0124" in text
    assert len(text) <= holding_forecasts.FACETTE.grenze


@pytest.mark.skipif(not ECHTE_DB.exists(), reason="kein lokaler Abzug (scripts/lokale_daten.py)")
def test_groesse_am_echten_bestand():
    store = CouncilStore(ECHTE_DB)
    try:
        if not store.holding_forecasts():
            pytest.skip("Bestand ohne Quartalsberichte (scripts/ingest_holding_quarterly.py)")
        for terme in (["Klinikum", "VWG"], ["BBGO", "WEH"], ["AWB"], ["TGO", "OTM"]):
            text = holding_forecasts.block(store.holding_forecasts_context(terme, None))
            assert 0 < len(text) <= holding_forecasts.FACETTE.grenze, (terme, len(text))
    finally:
        store.close()
