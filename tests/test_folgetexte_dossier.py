"""Stufe 4 (Plan Vorlagen § 7.4): Kartentext und Tragweite lesen das Dossier,
wenn eins da ist — und sonst wie bisher den Rohtext."""
from __future__ import annotations

from council import impact, social_text

PUNKT = {"committee": "Rat", "session_date": "2026-11-30", "title": "Entschädigungssatzung",
         "office": "Amt 10", "proposed_decision": "Die Satzung wird beschlossen.", "raw_text": "Sachverhalt: lang …"}
ZEILEN = ["Was es kostet: Die Mehraufwendungen betragen 89.000 Euro pro Jahr. (Vorlage 26/0743, S. 1)"]


def test_kartentext_kontext_aus_dossier():
    ktx, source = social_text.kontext_aus_dossier(PUNKT, ZEILEN)
    assert source == "dossier"
    assert "89.000 Euro" in ktx and "Beschlussvorschlag (ein VORSCHLAG" in ktx
    assert "Sachverhalt" not in ktx


def test_ohne_dossier_der_alte_kontext():
    assert social_text.kontext_aus_dossier(PUNKT, []) == social_text.kontext(PUNKT, [])


def test_text_fuer_nimmt_die_dossierzeilen(monkeypatch):
    gesehen = []
    monkeypatch.setattr(social_text, "_antwort", lambda system, user: gesehen.append(user) or
                        '{"text": "Die Mehraufwendungen betragen 89.000 Euro pro Jahr.", "headline": "Mehr Geld für den Rat"}')
    monkeypatch.setattr(social_text.kritiker, "pruefe_llm", lambda text, ktx: (True, ""), raising=False)
    out = social_text.text_fuer({**PUNKT, "dossier_lines": ZEILEN}, [])
    assert out is not None and out[1] == "dossier"
    assert "Aus den Unterlagen" in gesehen[0]


def test_tragweite_bekommt_die_zeilen():
    text = impact._batch_text([{"id": 1, "title": "T", "official_text": "Beschlossen.", "dossier_lines": ZEILEN}])
    assert "Aus der Vorlage: Was es kostet" in text
    assert "Aus der Vorlage" not in impact._batch_text([{"id": 1, "title": "T", "official_text": "Beschlossen."}])
