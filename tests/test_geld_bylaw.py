"""Die Facette `bylaw` — die Haushaltssatzung in der KI-Frage.

Der schärfste Wächter steht unten: Die Satzungen im Bestand sind
Verwaltungsentwürfe, und der Baustein muss das sagen. Ohne diesen Satz
machte eine Antwort aus einem Vorschlag einen Ratsbeschluss.
"""
from pathlib import Path

import pytest

from council import qa
from council.geld import bylaw
from council.store import CouncilStore

ECHTE_DB = Path(
    "/private/tmp/claude-501/-Users-tim-Documents-kommunalwahl-scraper--"
    "claude-worktrees-haushaltsseite-review-763d8c/"
    "1759b603-5a3e-439a-95af-ccd796425871/scratchpad/data/council.sqlite")


# --- 1. Erkennung ---------------------------------------------------------

@pytest.mark.parametrize("frage", [
    "Was steht in der Haushaltssatzung?",
    "Wie hoch ist die Kreditermächtigung?",
    "Wie viel Kassenkredit darf die Stadt aufnehmen?",
    "Wie hoch sind die Verpflichtungsermächtigungen?",
    "Welchen Höchstbetrag für Liquiditätskredite nennt die Satzung?",
    "Welche Ermächtigungen stecken im Haushalt 2026?",
])
def test_diese_fragen_ziehen_die_satzung(frage):
    assert "bylaw" in qa.geld_facetten(frage, "topic"), frage


@pytest.mark.parametrize("frage", [
    # „Satzung" allein ist in Oldenburg fast immer eine andere.
    "Was hat der Rat zur Baumschutzsatzung beschlossen?",
    "Wie werden die Müllgebühren berechnet?",
    # Der Hebesatz gehört den Steuer-Facetten, nicht dieser hier — auch
    # wenn § 5 der Satzung ihn ebenfalls nennt.
    "Wie hoch ist der Hebesatz der Grundsteuer?",
    "Wie viel Schulden hat Oldenburg?",
    "Wie viel investiert die Stadt?",
    "Wie ist der Stand beim Stadion?",
])
def test_diese_fragen_ziehen_sie_nicht(frage):
    assert "bylaw" not in qa.geld_facetten(frage, "topic"), frage


def test_die_alten_facetten_verschieben_sich_nicht():
    assert qa.geld_facetten("Wie hoch ist der Hebesatz der Grundsteuer?",
                            "money") == {"taxes", "ausgleich", "tax_rates"}
    assert qa.geld_facetten("Wie viel Schulden hat Oldenburg?",
                            "money") == {"schulden"}


# --- 2. Inhalt ------------------------------------------------------------

def _store(tmp_path) -> CouncilStore:
    """Zwei Jahrgänge mit einer Lücke dazwischen — wie im echten Bestand, dem
    der Jahrgang 2022 fehlt."""
    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_provenance (id, key, kind, label, url, citation, "
            " probe, as_of, fetched_at) VALUES "
            "(1, 'k1', 'ris', 'Haushaltssatzung 2026', 'https://example.org/hs', "
            " 'Haushaltssatzung 2026, §§ 1–5', 'bylaw_cash_budget', "
            " 'Haushaltssatzung 2026, Verwaltungsentwurf', '2026-08-30')")
        for jahr, erw, aufw, kredit, liqui, verpf, grund_b in [
                (2024, 695_625_370.0, 723_467_364.0, 0.0, 100_000_000.0,
                 28_202_400.0, 445),
                (2026, 788_574_714.0, 880_775_058.0, 0.0, 100_000_000.0,
                 41_489_000.0, None)]:
            store._conn.execute(
                "INSERT INTO council_budget_bylaw (year, supplement, version, "
                " ordinary_revenues, ordinary_expenses, extraordinary_revenues, "
                " extraordinary_expenses, in_operating, out_operating, in_capital, "
                " out_capital, in_financing, out_financing, in_total, out_total, "
                " investment_loans, commitment_authorizations, liquidity_loans, "
                " property_tax_a_rate, property_tax_b_rate, trade_tax_rate, "
                " probes, herkunft_id, fetched_at) "
                "VALUES (?,0,'draft',?,?,0,0,0,0,0,0,0,0,?,?,?,?,?,?,?,439,"
                " 'bylaw_cash_budget',1,'')",
                (jahr, erw, aufw, erw, aufw, kredit, verpf, liqui,
                 390 if grund_b else None, grund_b))
    return store


def test_liefert_den_gefragten_jahrgang(tmp_path):
    store = _store(tmp_path)
    d = store.bylaw_context(["Haushaltssatzung"], 2024)
    assert d["year"] == 2024 and not d["anderer_jahrgang"]
    assert d["zeile"]["commitment_authorizations"] == 28_202_400.0
    assert d["fehlend"] == [2025]
    store.close()


def test_fehlendes_jahr_faellt_auf_das_juengste_zurueck(tmp_path):
    store = _store(tmp_path)
    d = store.bylaw_context(["Haushaltssatzung"], 2019)
    assert d["year"] == 2026 and d["anderer_jahrgang"]
    assert "Zum gefragten Jahr liegt keine Satzung" in bylaw.block(d)
    store.close()


def test_begriffe_waehlen_die_reihe(tmp_path):
    store = _store(tmp_path)
    d = store.bylaw_context(["Kassenkredit", "Liquiditätskredit"], 2026)
    assert d["reihe"]["name"].startswith("Höchstbetrag für Liquiditätskredite")
    d = store.bylaw_context(["Verpflichtungsermächtigung"], 2026)
    assert d["reihe"]["name"].startswith("Verpflichtungsermächtigungen")
    # Ohne Treffer bleibt es beim gefragten Jahrgang.
    assert store.bylaw_context(["Stadion"], 2026)["reihe"] is None
    store.close()


def test_der_baustein_nennt_den_entwurf_und_die_leere_ermaechtigung(tmp_path):
    store = _store(tmp_path)
    text = bylaw.block(store.bylaw_context(["Kreditermächtigung"], 2026))
    assert "VERWALTUNGSENTWURF, KEIN RATSBESCHLUSS" in text
    # NICHT „0,0 Mio. €": Die Satzung schreibt dort einen Satz.
    assert "nicht veranschlagt" in text and "(§ 2): 0,0 Mio. €" not in text
    # Gleiche Werte über alle Jahrgänge werden zusammengefasst statt gelistet.
    assert "in allen 2 Jahrgängen 2024–2026: nicht veranschlagt" in text
    assert "NICHT im Bestand: 2025" in text
    assert "Beleg: Haushaltssatzung 2026" in text and "NIE mit [id]" in text
    store.close()


def test_hebesaetze_kommen_mit_dem_vorschlags_vermerk(tmp_path):
    store = _store(tmp_path)
    alt = bylaw.block(store.bylaw_context(["Haushaltssatzung"], 2024))
    assert "Grundsteuer B 445 %" in alt and "VORGESCHLAGEN" in alt
    # Ab 2025 nennt § 5 nur noch die Gewerbesteuer — das ist die Auskunft,
    # keine Lücke im Einlesen.
    neu = bylaw.block(store.bylaw_context(["Haushaltssatzung"], 2026))
    assert "Gewerbesteuer 439 %" in neu and "Grundsteuer" not in neu
    store.close()


def test_leere_datenbank_liefert_nichts(tmp_path):
    store = CouncilStore(tmp_path / "leer.sqlite")
    assert store.bylaw_context(["Haushaltssatzung"], 2026) is None
    assert bylaw.block(None) == ""
    store.close()


# --- 3. Größe -------------------------------------------------------------

@pytest.mark.parametrize("frage,begriffe", [
    ("Was steht in der Haushaltssatzung?", "Haushaltssatzung Gesamtbetrag"),
    ("Wie hoch ist die Kreditermächtigung?", "Kreditermächtigung Kredite"),
    ("Wie viel Kassenkredit darf die Stadt aufnehmen?",
     "Liquiditätskredit Kassenkredit Höchstbetrag"),
])
def test_bausteingroesse_an_echten_zahlen(frage, begriffe, tmp_path):
    if not ECHTE_DB.exists():
        pytest.skip("dev-Datenbank nicht vorhanden")
    kopie = tmp_path / "council.sqlite"
    kopie.write_bytes(ECHTE_DB.read_bytes())
    store = CouncilStore(kopie)
    daten = store.bylaw_context(begriffe.split(), qa.haushaltsjahr(frage))
    text = bylaw.block(daten)
    assert 700 < len(text) <= bylaw.FACETTE.grenze, (frage, len(text))
    store.close()
