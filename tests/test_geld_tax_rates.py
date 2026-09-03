"""Die Facette `tax_rates` — Hebesätze und Gewerbesteuerstatistik.

Der Prüfstein dieser Facette ist die Trennung von Satz und Aufkommen: „Wie
hoch waren die Steuereinnahmen 2024?" beantwortet `taxes` vollständig und darf
die Treppe nicht mitziehen; „Wie hoch ist der Hebesatz?" beantwortet nur sie."""
import os
import sqlite3
from pathlib import Path

import pytest

from council import qa
from council.geld import tax_rates
from council.store import CouncilStore

NAME = tax_rates.NAME

#: Die echte Datenbank für die Zeichen-Messung, gefunden wie in den
#: Ingest-Skripten: ``COUNCIL_DB``, sonst ``data/council.sqlite``. In der CI
#: gibt es sie nicht — dort entfällt der Test, und das ist richtig so: Er misst
#: Zeichen an echten Zahlen, und die kann ein Fixture nicht ersetzen. Gemessen
#: wurde am dev-Stand vom 02.09.2026.
DEV_DB = Path(os.environ.get("COUNCIL_DB")
              or Path(__file__).resolve().parents[1] / "data" / "council.sqlite")


class _NurLesen(tax_rates.Store):
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
    "Wie hoch ist der Hebesatz für die Grundsteuer B?",
    "Wann wurden die Hebesätze zuletzt erhöht?",
    "Wie viel Prozent beträgt die Gewerbesteuer in Oldenburg?",
    "Warum ist die Grundsteuer gestiegen?",
    "Wie viele Betriebe zahlen in Oldenburg Gewerbesteuer?",
    "Wie hoch war der Steuermessbetrag?",
]

ZIEHT_NICHT = [
    "Wie hoch waren die Steuereinnahmen 2024?",
    "Wie viel Geld nimmt die Stadt mit der Gewerbesteuer ein?",
    "Wie viele Betriebe gibt es auf dem Fliegerhorst?",
    "Wie ist der Stand beim Stadion?",
    "Wie hoch sind die Schulden der Stadt?",
    "Was kostet die Feuerwehr?",
]


@pytest.mark.parametrize("frage", ZIEHT)
def test_hebesatz_fragen_ziehen_die_facette(frage):
    gefunden = qa.geld_facetten(frage, "topic")
    assert NAME in gefunden, (frage, sorted(gefunden))


@pytest.mark.parametrize("frage", ZIEHT_NICHT)
def test_aufkommens_fragen_ziehen_sie_nicht(frage):
    assert NAME not in qa.geld_facetten(frage, "topic"), frage


def test_grundsteuerreform_ohne_satzfrage_zieht_nichts():
    """Bewusste Entscheidung: Die Reform änderte die MESSBETRÄGE, nicht den
    Hebesatz. „Was ist die Grundsteuerreform?" bekommt deshalb keine Treppe;
    sobald jemand nach dem Satz oder nach einer Erhöhung fragt, kommt sie."""
    assert NAME not in qa.geld_facetten("Was ist die Grundsteuerreform?", "topic")
    assert NAME in qa.geld_facetten(
        "Hat die Grundsteuerreform den Hebesatz verändert?", "topic")


@pytest.mark.parametrize("frage,alte", [
    ("Wie hoch ist der Hebesatz für die Grundsteuer B?", {"taxes", "ausgleich"}),
    ("Wie hoch war der Steuermessbetrag?", {"taxes", "ausgleich"}),
])
def test_die_alten_facetten_bleiben_unverschoben(frage, alte):
    """`ausgleich` bei „hebesatz" ist gewollt — es ist der NFAG-Dämpfer, die
    zweite Hälfte derselben Antwort."""
    assert qa.geld_facetten(frage, "topic") - {NAME} == alte


# ---------------------------------------------------------------------------
# 2. Inhalt
# ---------------------------------------------------------------------------

def _store(tmp_path) -> CouncilStore:
    """Die Hebesatz-Treppe im Zuschnitt von Tabelle 1105 — samt der Zeile, in
    der sich nur ZWEI der drei Sätze geändert haben (2025)."""
    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_provenance (id, key, kind, label, url, "
            " citation, probe, as_of, fetched_at) VALUES "
            "(1, 'k1', 'city', 'Statistisches Jahrbuch, Tabelle 1105', "
            " 'https://example.org/1105', 'Realsteuer-Hebesätze seit 1980', "
            " 'rate_jump_check', 'Änderungsjahre 1980-2025', '2026-08-30')")
        store._conn.execute(
            "INSERT INTO council_provenance (id, key, kind, label, url, "
            " citation, probe, as_of, fetched_at) VALUES "
            "(2, 'k2', 'lsn', 'Gewerbesteuerstatistik 2021', "
            " 'https://example.org/lsn', 'Blatt 6.1', 'sheet_check', "
            " 'Erschienen 2026', '2026-08-26')")
        for jahr, art, satz, davor in [
                (1980, "Grundsteuer A", 200, None),
                (2015, "Grundsteuer A", 390, 360),
                (2025, "Grundsteuer A", 500, 390),
                (1980, "Grundsteuer B", 300, None),
                (2015, "Grundsteuer B", 445, 430),
                (2025, "Grundsteuer B", 539, 445),
                (1980, "Gewerbesteuer", 370, None),
                (2015, "Gewerbesteuer", 439, 430),
                (2025, "Gewerbesteuer", 439, 439)]:
            store._conn.execute(
                "INSERT INTO council_tax_rates (year, kind, rate, prior_rate, "
                " fetched_at, herkunft_id) VALUES (?, ?, ?, ?, '', 1)",
                (jahr, art, satz, davor))
        # Acht kreisfreie Städte stehen in dieser Tabelle; Osnabrück ist der
        # Prüfstein dafür, dass nur die Oldenburger Zeile herauskommt.
        for jahr, schluessel, stadt, faelle, positiv, mess in [
                (2019, "403000", "Oldenburg", 8_100, 3_500, 31_000_000),
                (2021, "403000", "Oldenburg", 8_421, 3_642, 30_015_356),
                (2021, "404000", "Osnabrück", 9_172, 3_733, 28_888_109)]:
            store._conn.execute(
                "INSERT INTO council_trade_tax_statistics (year, key, city, "
                " cases, cases_positive, tax_base_eur, apportionments, "
                " apportionments_positive, apportioned_assessment_eur, "
                " fetched_at, herkunft_id) VALUES (?, ?, ?, ?, ?, ?, "
                " 1425, 879, 15911807, '', 2)",
                (jahr, schluessel, stadt, faelle, positiv, mess))
    return store


def test_aktueller_satz_und_treppe(tmp_path):
    store = _store(tmp_path)
    daten = store.tax_rates_context(["Hebesatz"], None)
    nach_art = {k["kind"]: k for k in daten["kinds"]}
    assert nach_art["Grundsteuer B"]["rate"] == 539
    assert nach_art["Grundsteuer B"]["since"] == 2025
    # Die 2025er Zeile der Gewerbesteuer ist KEINE Änderung (439 → 439):
    # „seit" ist deshalb 2015 und nicht das Jahr der jüngsten Zeile.
    assert nach_art["Gewerbesteuer"]["since"] == 2015
    assert nach_art["Gewerbesteuer"]["stufen"] == [(1980, 370), (2015, 439)]
    text = tax_rates.block(daten)
    assert "aktuell 539 %, unverändert seit 2025" in text
    assert "EIN HEBESATZ IST KEIN AUFKOMMEN" in text
    assert "Beleg: Statistisches Jahrbuch, Tabelle 1105" in text
    assert "statistics" not in daten
    store.close()


def test_gefragtes_jahr_nennt_den_damals_geltenden_satz(tmp_path):
    """Zwischen zwei Stufen gilt der Satz weiter — 2018 gibt es keine Zeile,
    aber sehr wohl einen Satz."""
    store = _store(tmp_path)
    daten = store.tax_rates_context(["Hebesatz"], 2018)
    nach_art = {k["kind"]: k for k in daten["kinds"]}
    assert nach_art["Grundsteuer B"]["asked_rate"] == 445
    assert nach_art["Grundsteuer B"]["asked_since"] == 2015
    assert "Im Jahr 2018 galten:" in tax_rates.block(daten)
    store.close()


def test_jahr_vor_der_reihe_wird_benannt(tmp_path):
    store = _store(tmp_path)
    daten = store.tax_rates_context(["Hebesatz"], 1975)
    assert all(k["asked_rate"] is None for k in daten["kinds"])
    assert "Die Reihe beginnt 1980" in tax_rates.block(daten)
    store.close()


def test_statistik_nur_bei_betriebs_begriffen(tmp_path):
    store = _store(tmp_path)
    assert "statistics" not in store.tax_rates_context(["Hebesatz"], None)
    daten = store.tax_rates_context(["Betriebe", "Gewerbesteuer"], None)
    s = daten["statistics"]
    assert s["year"] == 2021 and s["city"] == "Oldenburg"   # nicht Osnabrück
    text = tax_rates.block(daten)
    assert "8.421" in text and "3.642" in text and "30,0 Mio. €" in text
    assert "STEUERMESSBETRAG IST NICHT AUFKOMMEN" in text
    store.close()


def test_statistik_gefragtes_und_fehlendes_jahr(tmp_path):
    store = _store(tmp_path)
    daten = store.tax_rates_context(["Betriebe"], 2019)
    assert daten["statistics"]["year"] == 2019
    assert daten["statistics"]["year_deviates"] is False
    # 2024 gibt es nicht: jüngster Jahrgang, und der Baustein sagt es.
    daten = store.tax_rates_context(["Betriebe"], 2024)
    assert daten["statistics"]["year"] == 2021
    assert daten["statistics"]["year_deviates"] is True
    assert "Zu 2024 gibt es sie nicht" in tax_rates.block(daten)
    store.close()


def test_leerer_bestand_bleibt_still(tmp_path):
    store = CouncilStore(tmp_path / "leer.sqlite")
    assert store.tax_rates_context(["Hebesatz"], None) is None
    assert tax_rates.block(None) == ""
    store.close()


# ---------------------------------------------------------------------------
# 3. Größe
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("frage", [
    "Wie hoch ist der Hebesatz für die Grundsteuer B?",
    "Wie hat sich der Gewerbesteuer-Hebesatz entwickelt?",
    "Wie viele Betriebe zahlen in Oldenburg Gewerbesteuer?",
])
def test_baustein_bleibt_unter_der_grenze(frage):
    if not DEV_DB.exists():
        pytest.skip("keine Dev-Datenbank zum Messen")
    store = _NurLesen(str(DEV_DB))
    daten = store.tax_rates_context(frage.split(), qa.haushaltsjahr(frage))
    text = tax_rates.block(daten)
    assert text, frage
    assert len(text) <= tax_rates.FACETTE.grenze, (frage, len(text))
