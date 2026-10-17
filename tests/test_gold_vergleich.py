"""Messwerkzeug der Gold-Läufe: Ursachen, Kontext-Recall, Vergleich mit Streuung.

Grundlage für jede Entscheidung über „Frag den Rat“ seit 17.10.2026 — ein
Fehler hier ließe eine Verbesserung wie Rauschen aussehen oder umgekehrt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import eval_ask_gold as gold  # noqa: E402
import gold_vergleich as vergleich  # noqa: E402

MATERIAL = [
    {"id": "M1", "fuer": ["F1"], "art": "beschluss", "vorhanden": True},
    {"id": "M2", "fuer": ["F2"], "art": "debatte", "vorhanden": False},
    {"id": "M3", "fuer": ["F3"], "art": "presse", "vorhanden": True},
    {"id": "M4", "fuer": ["F3"], "art": "debatte", "vorhanden": False},
]


def test_ursachen_trennen_suche_und_antwort():
    assert gold.ursache("F1", MATERIAL) == "weggelassen"      # lag vor
    assert gold.ursache("F2", MATERIAL) == "nicht_gefunden"   # fehlte
    assert gold.ursache("F3", MATERIAL) == "teilweise"
    assert gold.ursache("F9", MATERIAL) == "ohne_material"
    assert gold.kontext_recall(MATERIAL) == (2, 4)
    # Bei den Kandidaten gefunden, im Prompt nicht: der Schnitt nach Rang 20.
    gefunden = [dict(m, vorhanden=True) for m in MATERIAL]
    assert gold.ursache("F2", MATERIAL, gefunden) == "abgeschnitten"


def test_material_form_zaehlt_nur_was_im_prompt_stand():
    quellen = {"sources": [{"id": 1, "title": "A"}, {"id": 2, "title": "B"}]}
    assert [c["id"] for c in gold.material_form(quellen)["candidates"]] == [1, 2]
    assert [c["id"] for c in gold.material_form(quellen, kontext_ids=[2])["candidates"]] == [2]
    quellen["debates"] = [{"id": 7, "date": "2026-06-01", "excerpt": "a"},
                          {"id": 8, "date": "2026-06-01", "excerpt": "b"}]
    assert len(gold.material_form(quellen, debatten_ids=[8])["debates"]) == 1


def _lauf(tmp_path, label, abdeckung):
    faelle = [{"id": "fall-a", "material": MATERIAL,
               "wertung": {"abdeckung": abdeckung, "bestanden": abdeckung >= 0.7,
                           "verfehlt": ["F1", "F2"]}}]
    (tmp_path / f"ask-{label}.json").write_text(json.dumps({"cases": faelle}))


def test_vergleich_nennt_mittel_spanne_und_recall(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(vergleich, "ZIEL", tmp_path)
    _lauf(tmp_path, "v1", 0.3)
    _lauf(tmp_path, "v2", 0.4)
    _lauf(tmp_path, "n1", 0.8)
    _lauf(tmp_path, "n2", 0.9)
    monkeypatch.setattr(sys, "argv", ["x", "--vorher", "v1,v2", "--nachher", "n1,n2"])
    vergleich.main()
    aus = capsys.readouterr().out
    assert "Abdeckung 35% (30%–40%)" in aus and "Abdeckung 85% (80%–90%)" in aus
    assert "Kontext-Recall 50%" in aus
    # +50 Punkte bei 10 Punkten Spannweite je Seite: als echter Unterschied markiert.
    assert "★ fall-a" in aus
