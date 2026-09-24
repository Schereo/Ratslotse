"""Die geprüften Erklärtexte (kern/erklaerwissen.py) — wann sie greifen,
wann nicht, und dass jeder seine Quelle trägt.

Die Fragen sind die echten aus dem Laien-Befund vom 24.09.2026 (36 Fragen
durch Lottis Fenster), dazu die Gegenfälle, an denen ein zu weiter Auslöser
auffiele: Jede Regel im Prompt kostet die Fälle, für die sie nicht gilt.
"""
from __future__ import annotations

import re

import pytest

from kern import erklaerwissen


def _keys(frage: str) -> list[str]:
    return [e.key for e in erklaerwissen.finde(frage)]


@pytest.mark.parametrize(("frage", "key"), [
    # Die Befund-Fragen, Teil B
    ("warum macht die stadt überhaupt schulden", "kredite"),
    ("hat die stadt genug geld", "genug_geld"),
    ("warum ist die stadt pleite", "genug_geld"),
    ("stimmt es dass für kitas kein geld mehr da ist", "genug_geld"),
    ("was muss die stadt bezahlen und was nicht", "pflicht"),
    ("könnte man nicht einfach das theater streichen", "pflicht"),
    ("wo kann die stadt sparen", "pflicht"),
    ("kann ich mitbestimmen wofür das geld ausgegeben wird", "mitreden"),
    ("was bedeutet defizit", "defizit"),
    # Schreibvarianten und Nachbarn derselben Frage
    ("Wieso nimmt Oldenburg Kredite auf?", "kredite"),
    ("Darf die Stadt einfach Schulden machen?", "kredite"),
    ("Wie steht die Stadt finanziell da?", "genug_geld"),
    ("Ist Oldenburg überschuldet?", "genug_geld"),
    ("Ist das eine Pflichtaufgabe?", "pflicht"),
    ("Wie kann man sich als Bürger beteiligen?", "mitreden"),
    ("Gibt es einen Bürgerhaushalt?", "mitreden"),
    ("Hat die Stadt einen Überschuss?", "defizit"),
    ("Gibt die Stadt mehr aus als sie einnimmt?", "defizit"),
])
def test_die_grundfrage_zieht_ihren_text(frage, key):
    assert key in _keys(frage)


@pytest.mark.parametrize("frage", [
    # Fragen an die ZAHL — die hat der Geld-Baustein, ein Text über
    # Kreditrecht wäre dort Füllstoff.
    "wie viele schulden hat die stadt",
    "wann sind die schulden weg",
    "wer muss das alles zurückzahlen",
    "wie hoch sind die schulen pro einwohner",
    # Plan gegen Ist ist keine Defizit-Frage.
    "hat die stadt mehr ausgegeben als geplant",
    # „Beteiligungen" sind Gesellschaften, kein Mitreden.
    "Welche Beteiligungen hat die Stadt?",
    # „leisten" meint ein Vorhaben; die Antwort steht im Ratsarchiv.
    "kann sich die stadt das neue stadion leisten",
    # Nichts davon
    "was sind eigenbetriebe",
    "was kostet die feuerwehr",
    "was wird gebaut",
    "Was sehe ich hier?",
    "",
])
def test_andere_fragen_ziehen_nichts(frage):
    assert _keys(frage) == []


def test_hoechstens_zwei_je_frage():
    """Eine Mischfrage zieht mehrere — aber nie mehr als zwei: Jeder weitere
    Text schiebt die Oldenburger Zahlen nach hinten."""
    frage = ("Warum macht die Stadt Schulden, ist sie pleite, hat sie ein Defizit "
             "und kann ich mitbestimmen?")
    assert len(erklaerwissen.finde(frage)) == erklaerwissen.MAX_JE_FRAGE == 2


def test_jeder_text_traegt_eine_quelle_mit_paragraf_oder_unterlage():
    for e in erklaerwissen.ERKLAERUNGEN:
        assert re.search(r"§ \d+", e.quelle), e.key
        assert "NKomVG" in e.quelle or "KomHKVO" in e.quelle, e.key


def test_die_texte_sind_kurz_und_ohne_oldenburger_betraege():
    """Zwei bis vier Sätze sind die Vorgabe (Lottis Antwort hat selbst nur
    fünf); ein Betrag gehört in die Haushaltsdaten, wo er Jahr und Beleg hat,
    nicht in einen Erklärtext."""
    for e in erklaerwissen.ERKLAERUNGEN:
        saetze = [s for s in re.split(r"[.?!](?:\s|$)", e.text) if s.strip()]
        assert 2 <= len(saetze) <= 4, (e.key, len(saetze))
        assert not re.search(r"\d[\d.,]*\s*(?:€|Euro|Mio|Millionen)", e.text), e.key


def test_die_schluessel_sind_eindeutig():
    keys = [e.key for e in erklaerwissen.ERKLAERUNGEN]
    assert len(keys) == len(set(keys))
