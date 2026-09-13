"""Die Spaltenprobe (``crosscheck.check_columns``) vergleicht nach Namen.

Am Wahlabend 2026 führte die Ergebnistabelle des Votemanagers den
Einzelwahlvorschlag (D11) nicht — 15 Zeilen statt 16. Positionsweise
verglichen galt ab D11 jede Spalte als verrutscht, obwohl die CSV stimmte.
"""
from __future__ import annotations

from web.backend.app.election import crosscheck
from web.backend.app.election.register import load

REG = load()

#: So stand es am 13.09.2026 um 20:08 Uhr in der Tabelle — ohne M. Stille.
TABELLE_2026 = ["GRÜNE", "SPD", "CDU", "Die Linke", "FDP", "AfD Niedersachsen", "Volt", "PIRATEN",
                "BSW Niedersachsen", "DAVA-Niedersachsen", "Die PARTEI", "PGM NDS", "BB-OL",
                "Echt Oldenburg", "WFO"]


def test_fehlender_einzelwahlvorschlag_ist_kein_befund():
    assert crosscheck.check_columns(TABELLE_2026, REG) == []


def test_fehlende_liste_wird_gemeldet():
    ohne_fdp = [n for n in TABELLE_2026 if n != "FDP"]
    hinweise = crosscheck.check_columns(ohne_fdp, REG)
    assert len(hinweise) == 1 and "FDP" in hinweise[0] and "D5" in hinweise[0]


def test_vertauschte_reihenfolge_wird_gemeldet():
    vertauscht = list(TABELLE_2026)
    vertauscht[0], vertauscht[1] = vertauscht[1], vertauscht[0]
    hinweise = crosscheck.check_columns(vertauscht, REG)
    assert len(hinweise) == 2
    assert any("D1" in h and "SPD" in h and "Grüne" in h for h in hinweise), hinweise


def test_unbekannter_name_wird_gemeldet():
    hinweise = crosscheck.check_columns(TABELLE_2026 + ["Tierschutzpartei"], REG)
    assert len(hinweise) == 1 and "Tierschutzpartei" in hinweise[0]


def test_leere_tabelle_schweigt():
    assert crosscheck.check_columns([], REG) == []
