"""Die Facette `tax_plan` — Steuern: geplant und eingenommen (Tabelle 1103).

Sie feuert nur, wenn BEIDES im Wortlaut steht: ein Steuer-Anker und ein
Plan-Wort. Genau dort verläuft die Grenze zu ihren beiden Nachbarn — `taxes`
(nur Ist) und `plan` (Haushaltsplan ohne Steuerbezug)."""
import os
import sqlite3
from pathlib import Path

import pytest

from council import qa
from council.geld import tax_plan
from council.store import CouncilStore

NAME = tax_plan.NAME

#: Die echte Datenbank für die Zeichen-Messung, gefunden wie in den
#: Ingest-Skripten: ``COUNCIL_DB``, sonst ``data/council.sqlite``. In der CI
#: gibt es sie nicht — dort entfällt der Test, und das ist richtig so: Er misst
#: Zeichen an echten Zahlen, und die kann ein Fixture nicht ersetzen. Gemessen
#: wurde am dev-Stand vom 02.09.2026.
DEV_DB = Path(os.environ.get("COUNCIL_DB")
              or Path(__file__).resolve().parents[1] / "data" / "council.sqlite")


class _NurLesen(tax_plan.Store):
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
    "Kam bei der Gewerbesteuer mehr rein als geplant?",
    "Wie viel Grundsteuer war 2024 veranschlagt?",
    "Weichen die Steuereinnahmen vom Ansatz ab?",
    "Wurde die Gewerbesteuer zu vorsichtig kalkuliert?",
    "Wie viel Steuern hatte die Stadt eingeplant?",
]

#: Die beiden Pflicht-Negativen aus dem Auftrag stehen vorn — je einer der
#: beiden Anker fehlt, und ohne beide ist es nicht diese Frage.
ZIEHT_NICHT = [
    "Wie hoch waren die Steuereinnahmen 2024?",
    "Was ist im Haushalt für Schulen geplant?",
    "Wie hoch ist der Hebesatz für die Grundsteuer B?",
    "Wie viel gibt die Stadt für Soziales aus?",
    "Wie ist der Stand beim Stadion?",
]


@pytest.mark.parametrize("frage", ZIEHT)
def test_plan_ist_fragen_ziehen_die_facette(frage):
    gefunden = qa.geld_facetten(frage, "topic")
    assert NAME in gefunden, (frage, sorted(gefunden))


@pytest.mark.parametrize("frage", ZIEHT_NICHT)
def test_nachbarfragen_ziehen_sie_nicht(frage):
    assert NAME not in qa.geld_facetten(frage, "topic"), frage


@pytest.mark.parametrize("frage,alte", [
    ("Kam bei der Gewerbesteuer mehr rein als geplant?", {"taxes", "ausgleich"}),
    ("Wie viel Grundsteuer war 2024 veranschlagt?", {"taxes", "ausgleich"}),
])
def test_die_alten_facetten_bleiben_unverschoben(frage, alte):
    assert qa.geld_facetten(frage, "topic") - {NAME} == alte


# ---------------------------------------------------------------------------
# 2. Inhalt
# ---------------------------------------------------------------------------

def _store(tmp_path) -> CouncilStore:
    """Drei Jahrgänge Tabelle 1103 — mehr führt eine Ausgabe der Tabelle nie."""
    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_provenance (id, key, kind, label, url, "
            " citation, probe, as_of, fetched_at) VALUES "
            "(1, 'k1', 'city', 'Statistisches Jahrbuch, Tabelle 1103', "
            " 'https://example.org/1103', 'Ansatz und Rechnungsergebnis je "
            " Steuerart', 'ist_abgleich', 'Haushaltsjahre 2023-2025', "
            " '2026-08-30')")
        for jahr, art, plan, ist, vorlaeufig in [
                (2023, "Gewerbesteuer (-umlage)", 124_234_000.0, 176_840_000.0, 0),
                (2023, "Grundsteuer A+B", 33_770_000.0, 33_879_000.0, 0),
                (2024, "Gewerbesteuer (-umlage)", 133_440_000.0, 202_918_000.0, 0),
                (2024, "Grundsteuer A+B", 34_120_000.0, 34_171_000.0, 0),
                (2025, "Gewerbesteuer (-umlage)", 155_526_000.0, 222_117_000.0, 1),
                (2025, "Grundsteuer A+B", 34_120_000.0, 32_585_000.0, 1)]:
            store._conn.execute(
                "INSERT INTO council_tax_plan (year, kind, plan, actual, "
                " provisional, fetched_at, herkunft_id) VALUES "
                "(?, ?, ?, ?, ?, '', 1)", (jahr, art, plan, ist, vorlaeufig))
    return store


def test_juengster_jahrgang_mit_abstand_und_vorlaeufigkeit(tmp_path):
    store = _store(tmp_path)
    daten = store.tax_plan_context(["Steuern"], None)
    assert daten["year"] == 2025
    gewerbe = next(r for r in daten["kinds"] if r["kind"].startswith("Gewerbe"))
    assert gewerbe["deviation"] == pytest.approx(66_591_000.0)
    assert gewerbe["deviation_pct"] == pytest.approx(42.8, abs=0.1)
    text = tax_plan.block(daten)
    assert "Ansatz 155,5 Mio. €, Ergebnis 222,1 Mio. €" in text
    assert "+42,8 %" in text                       # deutsches Dezimalkomma
    assert "VORLÄUFIG" in text
    assert "ER IST KEINE NOTE" in text
    assert "Beleg: Statistisches Jahrbuch, Tabelle 1103" in text
    store.close()


def test_gefragtes_jahr_wird_geliefert(tmp_path):
    store = _store(tmp_path)
    daten = store.tax_plan_context(["Grundsteuer"], 2024)
    assert daten["year"] == 2024 and daten["year_deviates"] is False
    assert "STEUERN 2024:" in tax_plan.block(daten)
    assert "VORLÄUFIG" not in tax_plan.block(daten)   # 2024 ist endgültig
    store.close()


def test_fehlendes_jahr_faellt_auf_das_juengste_und_sagt_es(tmp_path):
    store = _store(tmp_path)
    daten = store.tax_plan_context(["Steuern"], 2018)
    assert daten["year"] == 2025 and daten["year_deviates"] is True
    assert "Zu 2018 führt diese Quelle keine Zeile" in tax_plan.block(daten)
    store.close()


def test_kurzreihe_nur_fuer_die_gefragte_art(tmp_path):
    store = _store(tmp_path)
    daten = store.tax_plan_context(["Gewerbesteuer"], None)
    assert [r["year"] for r in daten["series"]] == [2023, 2024, 2025]
    assert all(r["kind"] == "Gewerbesteuer (-umlage)" for r in daten["series"])
    assert "über alle vorliegenden Jahre" in tax_plan.block(daten)
    # Passt keine Art, bleibt es beim einen Jahrgang.
    ohne = store.tax_plan_context(["Hundesteuer"], None)
    assert ohne["series"] == []
    assert "über alle vorliegenden Jahre" not in tax_plan.block(ohne)
    store.close()


def test_leerer_bestand_bleibt_still(tmp_path):
    store = CouncilStore(tmp_path / "leer.sqlite")
    assert store.tax_plan_context(["Steuern"], None) is None
    assert tax_plan.block(None) == ""
    store.close()


# ---------------------------------------------------------------------------
# 3. Größe
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("frage", [
    "Kam bei der Gewerbesteuer mehr rein als geplant?",
    "Wie viel Grundsteuer war 2024 veranschlagt?",
    "Weichen die Steuereinnahmen vom Ansatz ab?",
])
def test_baustein_bleibt_unter_der_grenze(frage):
    if not DEV_DB.exists():
        pytest.skip("keine Dev-Datenbank zum Messen")
    store = _NurLesen(str(DEV_DB))
    daten = store.tax_plan_context(frage.split(), qa.haushaltsjahr(frage))
    text = tax_plan.block(daten)
    assert text, frage
    assert len(text) <= tax_plan.FACETTE.grenze, (frage, len(text))
