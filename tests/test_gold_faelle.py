"""Die Gold-Fälle (eval/cases_deep_gold.json) und ihre beiden Runner.

Die Fälle messen „Frag den Rat“ (scripts/eval_ask_gold.py) und die
Gründliche Recherche (scripts/eval_deep_gold.py) gegen handgeprüfte
Faktenlisten. Ein Tippfehler in einer Fakt-id oder ein Material-Eintrag, der
auf einen Fakt zeigt, den es nicht gibt, fiele erst im Lauf auf — als stilles
„nicht erfüllt“. Dieser Test hält das Format fest.
"""
import json
import re
from pathlib import Path

import pytest

FAELLE = Path(__file__).resolve().parents[1] / "eval" / "cases_deep_gold.json"


def _faelle():
    return json.loads(FAELLE.read_text(encoding="utf-8"))


def test_gold_faelle_sind_wohlgeformt():
    faelle = _faelle()
    assert len(faelle) >= 7
    ids = [f["id"] for f in faelle]
    assert len(ids) == len(set(ids))
    for f in faelle:
        fakten = {p["id"] for p in f["pflicht"]}
        assert len(fakten) == len(f["pflicht"]), f["id"]
        assert all(p["gewicht"] in (1, 2, 3) and p["beleg"].strip() for p in f["pflicht"]), f["id"]
        assert any(p["gewicht"] == 3 for p in f["pflicht"]), f"{f['id']}: kein Kernfakt (Gewicht 3)"
        assert f["verboten"], f"{f['id']}: keine verbotene Behauptung"
        for m in f.get("material", []):
            assert set(m["fuer"]) <= fakten, f"{f['id']}/{m['id']}: zeigt auf unbekannte Fakten"
            assert m["art"] in ("beschluss", "debatte", "presse", "vorlage", "beratung"), m
            if m["art"] == "debatte":
                assert m["text_enthaelt_eins"], m
            if m["art"] == "vorlage":
                assert re.fullmatch(r"\d{2}/\d{4}(?:/\d+)?", m["template_number"]), m
            if m["art"] == "beratung":
                assert m["session_date"] and m["titel_enthaelt"], m


def test_ask_runner_liest_die_debatten_im_web_vertrag():
    """Das Quellen-Ereignis trägt Debatten als date/excerpt, die Material-
    prüfung liest session_date/text — die Umrechnung darf nichts verlieren."""
    from scripts import eval_ask_gold as ask
    from scripts import eval_deep_gold as deep

    fall = next(f for f in _faelle() if f["id"] == "trinkwasserspender-draussen")
    quellen = {"sources": [{"id": 1, "title": "Prüfung … Trinkwasserspender …",
                            "session_date": "2026-04-16",
                            "committee": "Ausschuss für Stadtgrün, Umwelt und Klima"}],
               "debates": [], "press_releases": []}
    ohne = {m["id"]: m["vorhanden"] for m in deep._material_pruefen(fall, ask.material_form(quellen))}
    assert ohne == {"M1": False, "M2": True}
    nachgeladen = [{"date": "2026-04-16", "speaker": "Verwaltung (Protokollnotiz)",
                    "excerpt": "Klärung 2027 mit Abschluss des KLAK, danach Bau."}]
    mit = {m["id"]: m["vorhanden"] for m in deep._material_pruefen(
        fall, ask.material_form(quellen, nachgeladen))}
    assert mit == {"M1": True, "M2": True}


@pytest.mark.parametrize("urteil,bestanden", [
    ({"pflicht": {"F1": {"ok": True}, "F2": {"ok": True}}, "verboten": {}}, True),
    ({"pflicht": {"F1": {"ok": True}, "F2": {"ok": True}}, "verboten": {"X1": {"verstoss": True}}}, False),
    ({"pflicht": {"F2": {"ok": True}, "F3": {"ok": True}, "F4": {"ok": True}}, "verboten": {}}, False),
])
def test_bewertung_verlangt_kernfakt_und_keinen_verstoss(urteil, bestanden):
    # Eigener Mini-Fall: Die Probe hing an den Gewichten des Trinkwasser-
    # Falls und wurde rot, als die Gold-Recherche vom 02.10.2026 ihn um
    # Fakten ergänzte. Hier geht es um die Regel, nicht um einen Fall.
    from scripts import eval_deep_gold as deep
    fall = {"pflicht": [{"id": "F1", "gewicht": 3}, {"id": "F2", "gewicht": 1},
                        {"id": "F3", "gewicht": 1}, {"id": "F4", "gewicht": 1}],
            "verboten": [{"id": "X1"}]}
    assert deep._bewerten(fall, urteil)["bestanden"] is bestanden


def test_vorlage_und_beratung_werden_erkannt():
    """Die beiden Belegarten aus Plan „Akte“, Schritt 0.2."""
    from scripts import eval_deep_gold as deep
    fall = {"material": [
        {"id": "V", "fuer": ["F1"], "art": "vorlage", "template_number": "26/0261"},
        {"id": "B", "fuer": ["F1"], "art": "beratung", "session_date": "2026-09-28",
         "committee": "Rat", "titel_enthaelt": "Liquiditätskredit"}]}
    leer = {m["id"]: m["vorhanden"] for m in deep._material_pruefen(fall, {})}
    assert leer == {"V": False, "B": False}
    voll = {"attachments": [{"template_number": "26/0261/1"}],
            "agenda": [{"session_date": "2026-09-28", "committee": "Rat",
                        "title": "Verlängerung des Liquiditätskreditvertrages"}]}
    assert {m["id"]: m["vorhanden"] for m in deep._material_pruefen(fall, voll)} == {"V": True, "B": True}
