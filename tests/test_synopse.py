"""Spaltenleser für Synopsen (council/synopse.py) — gegen ein selbst gebautes PDF."""
from __future__ import annotations

import pymupdf

from council import synopse


def _synopse_pdf() -> bytes:
    doc = pymupdf.open()
    seite = doc.new_page(width=842, height=595)
    for x in (60, 351, 641, 769):   # senkrechte Tabellenlinien wie im Ratsinfo
        seite.draw_line((x, 140), (x, 560))
    seite.insert_text((150, 160), "Ursprungsfassung", fontsize=10)
    seite.insert_text((450, 160), "Änderungen", fontsize=10)
    seite.insert_text((660, 160), "Begründung", fontsize=10)
    seite.insert_text((70, 200), "§ 2 Aufwandsentschädigung", fontsize=9)
    seite.insert_text((360, 200), "§ 2 Aufwandsentschädigung", fontsize=9)
    seite.insert_text((70, 214), "erhalten monatlich 335 Euro.", fontsize=9)
    seite.insert_text((360, 214), "erhalten monatlich 400 Euro.", fontsize=9)
    seite.insert_text((650, 214), "Empfehlung der Kommission", fontsize=9)
    return doc.tobytes()


def test_spalten_aus_den_tabellenlinien():
    regeln = synopse.read(_synopse_pdf())
    assert len(regeln) == 1
    r = regeln[0]
    assert r["ref"] == "§ 2" and r["page"] == 1
    assert "335" in r["before"] and "400" not in r["before"]
    assert "400" in r["after"] and "335" not in r["after"]
    assert r["reason"] and "Kommission" in r["reason"]


def test_geaenderte_stellen_mit_umfeld():
    c = synopse.changes(synopse.read(_synopse_pdf()))
    assert c == [{"ref": "§ 2", "page": 1, "before": "§ 2 Aufwandsentschädigung erhalten monatlich 335 Euro.",
                  "after": "§ 2 Aufwandsentschädigung erhalten monatlich 400 Euro."}]   # fünf Wörter Umfeld


def test_ohne_spaltenkopf_nichts():
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Ein Fließtext ohne Synopse.")
    assert synopse.read(doc.tobytes()) == []
