"""Kontaktdaten kommen nicht in die Suche — der Text bleibt trotzdem ganz.

Tims Entscheidung vom 20.08.2026: **alles in die Datenbank, aber Namen,
Anschriften und Kontodaten nicht über „Frag den Rat" zurückgeben.** Die erste
Umsetzung hielt dafür den ganzen OCR-Text aus der Suche — das war falsch, weil
es die HERKUNFT des Textes traf statt dessen, was darin steht, und den
AWB-Wirtschaftsplan gleich mit aussperrte.

Richtig ist: Maskieren an der Index-Grenze. Diese Datei hält beide Hälften
fest — was maskiert wird, und was auf keinen Fall.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from council.kontaktdaten import (  # noqa: E402
    PLATZHALTER,
    enthaelt_kontaktdaten,
    entfernen,
    maskieren,
    zaehlen,
)
from council.store import CouncilStore  # noqa: E402

# Echt, aus dem Briefkopf von Anlage 194496 (Förderantrag Wildwasser 2019) —
# gekürzt und mit erfundenen Ziffern, aber in der Form des Originals.
BRIEFKOPF = """Wildwasser Oldenburg e.V.
Lindenallee 23 · 26122 Oldenburg
Tel. (0441) 16656
Fax (0441) 248 9553
info@example.org
Geschäftskonto: IBAN: DE20 2805 0100 0014 4046 77 · BIC: SLZODE22
"""


# --------------------------------------------------------------------------
# (a) Was verschwindet
# --------------------------------------------------------------------------

@pytest.mark.parametrize("text, was", [
    ("IBAN: DE20 2805 0100 0014 4046 77", "Kontonummer"),
    ("IBAN DE49290500003011146005", "Kontonummer ohne Leerzeichen"),
    ("BIC: SLZODE22", "Bankleitzahl"),
    ("info@example.org", "E-Mail"),
    ("Tel. (0441) 16656", "Telefon in Klammern"),
    ("Telefon 0441-235-2778", "Telefon mit Bindestrichen"),
    ("Fax: 0441 / 248 95 53", "Fax"),
    ("Mobil +49 170 1234567", "Mobilnummer"),
    ("Lindenallee 23 · 26122 Oldenburg", "ganze Anschrift"),
    ("Bergstr. 25, 26105 Oldenburg", "Anschrift mit Abkürzung"),
    ("Am Markt 1\n26129 Bad Zwischenahn\n", "Postleitzahl auf eigener Zeile"),
])
def test_wird_maskiert(text, was):
    assert PLATZHALTER in maskieren(text), f"{was} steht noch im Text"
    assert enthaelt_kontaktdaten(text)


def test_der_ganze_briefkopf():
    aus = maskieren(BRIEFKOPF)
    for rest in ("2805", "16656", "example.org", "SLZODE22", "26122"):
        assert rest not in aus, f"„{rest}“ steht noch im maskierten Text"
    # Der Vereinsname bleibt — er IST die Auskunft.
    assert "Wildwasser Oldenburg e.V." in aus


# --------------------------------------------------------------------------
# (b) Was bleiben MUSS — die gefährlichere Hälfte
# --------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    # Der halbe Investitionsbereich besteht aus Straßennamen. Wer eine
    # Anschrift am Muster „Straße + Hausnummer" erkennt, löscht ihn.
    "Ausbau Bümmersteder Tredde, 2. Bauabschnitt",
    "Radweg Alexanderstraße 12 bis Donnerschweer Straße",
    "Sanierung Grundschule Ohmstede, Butjadinger Straße 61",
    "Erweiterung Kita Am Alexanderhaus, Wilhelmstraße 4",
    # Fünfstellige Zahlen sind im Haushalt Beträge und Produktschlüssel.
    "Produkt 11101 Verwaltungssteuerung",
    "Gesamtertrag 21.011.173 €",
    "Kostenträger 0951/1 · Produkt 0844",
    # Namen bleiben: Der Bestand nennt 1.271 Ratsmitglieder.
    "Oberbürgermeister Krogmann begründet die Vorlage.",
])
def test_bleibt_unveraendert(text):
    assert maskieren(text) == text
    assert not enthaelt_kontaktdaten(text)


def test_strasse_faellt_nur_mit_postleitzahl_dahinter():
    """Der Unterschied zwischen Briefkopf und Baumaßnahme steht nicht in der
    Straße, sondern DAHINTER."""
    briefkopf = maskieren("Lindenallee 23, 26122 Oldenburg")
    vorhaben = maskieren("Sanierung Lindenallee 23")
    assert "Lindenallee" not in briefkopf
    assert vorhaben == "Sanierung Lindenallee 23"


# --------------------------------------------------------------------------
# (c) Die Grenze: gespeichert wird alles, indexiert wird maskiert
# --------------------------------------------------------------------------

def _store_mit_text(tmp_path: Path, text: str) -> CouncilStore:
    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_anlagen (document_id, kvonr, label, url, raw_text, "
            "n_pages, fetched_at, status, is_antrag) "
            "VALUES (4711, 99, 'Antrag auf Förderung', 'https://x/1', ?, 11, "
            "datetime('now'), 'ok', 1)", (text,))
    return store


def test_der_bestand_behaelt_alles(tmp_path):
    """Die Parser brauchen den vollen Text, und ein Beleg, der auf ein PDF
    zeigt, muss auch wiederfinden, was darin steht."""
    store = _store_mit_text(tmp_path, BRIEFKOPF)
    try:
        gespeichert = store._conn.execute(
            "SELECT raw_text FROM council_anlagen WHERE document_id=4711").fetchone()[0]
        assert gespeichert == BRIEFKOPF
        assert "SLZODE22" in gespeichert
    finally:
        store.close()


def test_die_chunk_vektoren_bekommen_maskierten_text(tmp_path):
    """Der Weg in die Gründliche Recherche und damit in Nutzerantworten."""
    store = _store_mit_text(tmp_path, BRIEFKOPF + "Antrag auf Förderung 2019. " * 20)
    try:
        offen = store.anlagen_missing_embeddings()
        assert len(offen) == 1
        text = offen[0]["raw_text"]
        assert PLATZHALTER in text
        for rest in ("SLZODE22", "example.org", "16656", "26122"):
            assert rest not in text
        # Der Inhalt, um den es geht, ist noch da.
        assert "Antrag auf Förderung" in text
    finally:
        store.close()


def test_der_volltextindex_bekommt_maskierten_text(tmp_path):
    """Der zweite Weg: `rebuild_fts()` zieht Antrags-Anlagen mit hinein.

    Geprüft über die SQLite-Funktion, die die Abfrage benutzt — sie ist die
    Stelle, an der maskiert wird."""
    store = _store_mit_text(tmp_path, BRIEFKOPF)
    try:
        aus = store._conn.execute(
            "SELECT ohne_kontaktdaten(raw_text) FROM council_anlagen "
            "WHERE document_id = 4711").fetchone()[0]
        assert PLATZHALTER in aus and "SLZODE22" not in aus
    finally:
        store.close()


def test_der_hash_haengt_am_maskierten_text(tmp_path):
    """Sonst gälte jede Anlage als geändert, sobald sich an der Maskierung
    etwas dreht — und der nächste Lauf rechnete den halben Bestand neu."""
    import hashlib

    store = _store_mit_text(tmp_path, BRIEFKOPF + "x" * 300)
    try:
        offen = store.anlagen_missing_embeddings()[0]
        erwartet = hashlib.sha256(
            maskieren(BRIEFKOPF + "x" * 300).encode("utf-8")).hexdigest()[:16]
        assert offen["text_hash"] == erwartet
    finally:
        store.close()


def test_zaehlen_meldet_die_arten():
    z = zaehlen(BRIEFKOPF)
    assert z["iban"] == 1 and z["bic"] == 1 and z["email"] == 1
    assert z["telefon"] == 2 and z["anschrift"] == 1


# --------------------------------------------------------------------------
# (d) Zwei Sätze: was gar nicht gespeichert wird, was nur den Index meidet
# --------------------------------------------------------------------------

def test_entfernen_nimmt_konto_und_anschrift_aus_dem_bestand():
    """Tims Entscheidung: „IBANs und Adresse kannst du auch komplett
    rausnehmen." Beides braucht kein Parser — eine Kontonummer ist nie eine
    Haushaltszahl, und der Straßenname allein bleibt ja stehen."""
    aus = entfernen(BRIEFKOPF)
    for weg in ("2805", "SLZODE22", "26122", "Lindenallee"):
        assert weg not in aus, f"„{weg}“ steht noch im gespeicherten Text"


def test_entfernen_laesst_telefon_und_mail_stehen():
    """Sie bleiben im Bestand und werden erst am Index maskiert.

    Der Grund ist nicht Bequemlichkeit: Eine Rufnummer der Verwaltung kann der
    Anker sein, an dem jemand eine Fundstelle im PDF wiederfindet. Eine
    Kontonummer ist das nie — und der Eingriff hier ist ohne erneutes Laden
    des PDF unumkehrbar."""
    aus = entfernen(BRIEFKOPF)
    assert "16656" in aus and "example.org" in aus


def test_maskieren_nimmt_beides():
    """Am Index fällt alles — auch das, was im Bestand bleiben darf."""
    aus = maskieren(BRIEFKOPF)
    for weg in ("2805", "SLZODE22", "26122", "16656", "example.org"):
        assert weg not in aus


def test_entfernen_faellt_nicht_ueber_strassennamen():
    """Dieselbe Grenze wie beim Maskieren — und hier wiegt sie schwerer, weil
    der Eingriff nicht rückgängig zu machen ist."""
    for text in ("Ausbau Bümmersteder Tredde, 2. Bauabschnitt",
                 "Sanierung Grundschule Ohmstede, Butjadinger Straße 61",
                 "Produkt 11101 Verwaltungssteuerung"):
        assert entfernen(text) == text


def test_die_beiden_saetze_ueberschneiden_sich_wie_erwartet():
    """`HART` ist eine echte Teilmenge dessen, was am Index fällt — sonst
    stünde im Index etwas, das im Bestand längst weg ist."""
    from council.kontaktdaten import HART, NUR_INDEX

    assert set(HART).isdisjoint(NUR_INDEX)
    assert len(HART) + len(NUR_INDEX) == 6
