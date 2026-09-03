"""Die Facette `donations` — Spenden an die Stadt in der KI-Frage.

Der wichtigste Wächter dieser Datei ist der letzte im Abschnitt „Inhalt": Der
Baustein muss sagen, dass die Gebenden NICHT im Bestand stehen. Die Tabelle
führt keine Namensspalte (``council/store.py`` über ``council_donations``),
und ohne den Satz füllt ein Sprachmodell die Lücke mit Plausiblem.
"""
from pathlib import Path

import pytest

from council import qa
from council.geld import donations
from council.store import CouncilStore

ECHTE_DB = Path(
    "/private/tmp/claude-501/-Users-tim-Documents-kommunalwahl-scraper--"
    "claude-worktrees-haushaltsseite-review-763d8c/"
    "1759b603-5a3e-439a-95af-ccd796425871/scratchpad/data/council.sqlite")


# --- 1. Erkennung ---------------------------------------------------------

@pytest.mark.parametrize("frage", [
    "Wie viel Geld hat die Stadt 2024 an Spenden angenommen?",
    "Wie viel wird der Stadt gespendet?",
    "Wer spendet an die Stadt Oldenburg?",
    "Gab es Sponsoring für die Stadt?",
    "Welche Schenkungen hat der Rat angenommen?",
    "Wie viele Zuwendungen hat die Stadt 2025 erhalten?",
])
def test_diese_fragen_ziehen_die_spenden(frage):
    assert "donations" in qa.geld_facetten(frage, "topic"), frage


@pytest.mark.parametrize("frage", [
    # „Zuwendung" ohne das Annehmen ist in der Kommunalfinanzierung das
    # ANDERE Wort — Landesmittel, nicht Spenden.
    "Wie hoch sind die Schlüsselzuweisungen?",
    "Welche Zuweisungen bekommt die Stadt vom Land?",
    "Welche Förderung gibt es für den Radweg?",
    "Wie hoch ist der Zuschuss für das Theater?",
    "Wie viel gibt Oldenburg für Soziales aus?",
    "Wie ist der Stand beim Stadion?",
])
def test_diese_fragen_ziehen_sie_nicht(frage):
    assert "donations" not in qa.geld_facetten(frage, "topic"), frage


def test_die_alten_facetten_verschieben_sich_nicht():
    assert qa.geld_facetten("Wie hoch waren die Steuereinnahmen?", "money") == {
        "plan", "ansatz", "taxes", "ausgleich"}
    assert qa.geld_facetten("Wie viel gibt Oldenburg für Soziales aus?",
                            "money") == {"plan", "produkte", "ansatz"}


# --- 2. Inhalt ------------------------------------------------------------

def _store(tmp_path) -> CouncilStore:
    """Drei Jahrgänge im Zuschnitt des Bestands — der jüngste angefangen."""
    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_provenance (id, key, kind, label, url, citation, "
            " probe, as_of, fetched_at) VALUES "
            "(1, 'k1', 'ris', 'Ratsvorlage „Annahme von Zuwendungen“ — Vorlage "
            "24/0419', 'https://example.org/v', 'Beschlussvorschlag und Abschnitt "
            "„Auswirkungen a) Finanzen“', 'donation_second_mention', "
            "'Sitzung vom 2024-08-26', '2026-08-30')")
        for nummer, jahr, datum, betrag, gremium in [
                ("23/0100", 2023, "2023-03-02", 12_000.0, "Verwaltungsausschuss"),
                ("23/0400", 2023, "2023-09-07", 140_783.48, "Rat"),
                ("24/0419", 2024, "2024-08-26", 303_757.40, "Rat"),
                ("24/0500", 2024, "2024-11-04", 51_000.0, "Rat"),
                ("24/0600", 2024, "2024-12-02", 1_800.0, "Verwaltungsausschuss"),
                ("25/0530", 2025, "2025-09-29", 263_074.0, "Rat")]:
            store._conn.execute(
                "INSERT INTO council_donations (template_number, year, "
                " session_date, amount, committee, layout, second_mention, "
                " probes, herkunft_id, fetched_at) "
                "VALUES (?,?,?,?,?,'new','split','donation_second_mention',1,'')",
                (nummer, jahr, datum, betrag, gremium))
        store._conn.execute(
            "INSERT INTO council_donations_rejected (template_number, "
            " session_date, reason, herkunft_id, fetched_at) VALUES "
            "('23/0265', '2023-05-03', 'Die Vorlage schlug 52.000,00 Euro vor, "
            "das Protokoll hält 51.500,00 Euro fest.', 1, '')")
    return store


def test_liefert_das_gefragte_jahr_mit_summe_und_groesster_vorlage(tmp_path):
    store = _store(tmp_path)
    d = store.donations_context(["Spenden"], 2024)
    assert d["year"] == 2024 and d["anzahl"] == 3
    assert d["summe"] == pytest.approx(356_557.40)
    assert d["groesste"]["template_number"] == "24/0419"
    assert [r["year"] for r in d["reihe"]] == [2023, 2024, 2025]
    assert not d["laufend"] and not d["anderer_jahrgang"]
    store.close()


def test_fehlendes_jahr_faellt_auf_das_juengste_zurueck(tmp_path):
    store = _store(tmp_path)
    d = store.donations_context(["Spenden"], 2019)
    assert d["year"] == 2025 and d["anderer_jahrgang"]
    text = donations.block(d)
    assert "Zum gefragten Jahr gibt es keine Beschlüsse im Bestand" in text
    # Der jüngste Jahrgang ist ein angefangenes Jahr und wird so bezeichnet.
    assert "LÄUFT NOCH" in text
    store.close()


def test_begriffe_schreiben_die_luecken_aus(tmp_path):
    store = _store(tmp_path)
    knapp = donations.block(store.donations_context(["Spenden", "Summe"], 2024))
    assert "NICHT in diesen Summen: 1 Beschlüsse" in knapp
    assert "51.500,00 Euro" not in knapp and "Summe je Jahr" in knapp
    breit = donations.block(
        store.donations_context(["Spenden", "abgelehnt"], 2024))
    assert "Vorlage 23/0265" in breit and "51.500,00 Euro" in breit
    # Statt der Reihe — beides zusammen sprengte das Zeichenbudget.
    assert "Summe je Jahr" not in breit
    store.close()


def test_der_baustein_verbietet_namen_und_nennt_keine(tmp_path):
    """Die härteste Zusicherung dieser Facette."""
    store = _store(tmp_path)
    text = donations.block(store.donations_context(["Spenden"], 2024))
    assert "WER GESPENDET HAT UND WOFÜR, WEISS DIESE QUELLE NICHT" in text
    assert "Zuwendungsliste" in text and "Nenne keine" in text
    # Und die Gegenprobe: In der Tabelle gibt es keine Spalte, aus der ein
    # Name in den Baustein geraten könnte.
    spalten = {r[1].lower() for r in
               store._conn.execute("PRAGMA table_info(council_donations)")}
    assert not (spalten & {"spender", "geber", "name", "zuwendungsgeber",
                           "person", "firma", "zweck"})
    assert "Beleg: Ratsvorlage" in text and "NIE mit [id]" in text
    store.close()


def test_betraege_in_euro_nicht_in_millionen(tmp_path):
    """`de_mio` machte aus jeder Jahressumme „0,4 Mio. €"."""
    store = _store(tmp_path)
    text = donations.block(store.donations_context(["Spenden"], 2024))
    assert "356.557 €" in text and "Mio." not in text
    store.close()


def test_leere_datenbank_liefert_nichts(tmp_path):
    store = CouncilStore(tmp_path / "leer.sqlite")
    assert store.donations_context(["Spenden"], 2024) is None
    assert donations.block(None) == ""
    store.close()


# --- 3. Größe -------------------------------------------------------------

@pytest.mark.parametrize("frage,begriffe", [
    ("Wie viel Geld hat die Stadt 2024 an Spenden angenommen?",
     "Spenden Zuwendungen Annahme"),
    ("Wie viel wird der Stadt gespendet?", "Spenden Zuwendungen Summe"),
    ("Welche Spenden wurden abgelehnt oder fehlen?",
     "Spenden abgelehnt verworfen Lücke"),
])
def test_bausteingroesse_an_echten_zahlen(frage, begriffe, tmp_path):
    if not ECHTE_DB.exists():
        pytest.skip("dev-Datenbank nicht vorhanden")
    kopie = tmp_path / "council.sqlite"
    kopie.write_bytes(ECHTE_DB.read_bytes())
    store = CouncilStore(kopie)
    daten = store.donations_context(begriffe.split(), qa.haushaltsjahr(frage))
    text = donations.block(daten)
    assert 700 < len(text) <= donations.FACETTE.grenze, (frage, len(text))
    store.close()
