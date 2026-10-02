"""Jeder Gold-Beleg trifft eine echte Zeile (eval/run_akten.py).

Ein Material-Eintrag, der keine Zeile trifft, zählt im Gold-Lauf still als
„fehlt“ — die Suche sähe schlechter aus, als sie ist. Die Fälle sind gegen
den Prod-Abzug vom 01.10.2026 recherchiert; der dev-Abzug kennt manche
jüngere Zeile nicht. Deshalb läuft der Test nur, wenn ``RATSLOTSE_MESS_DB``
ausdrücklich auf einen Prod-Abzug zeigt (``scripts/lokale_daten.py hol --von
prod``), nie gegen ``COUNCIL_DB`` (tests/CLAUDE.md).
"""
import json
import os
import sqlite3
from pathlib import Path

import pytest

from eval import run_akten

MESS_DB = os.environ.get("RATSLOTSE_MESS_DB")


@pytest.mark.skipif(not MESS_DB, reason="RATSLOTSE_MESS_DB nicht gesetzt (Prod-Abzug)")
def test_jeder_gold_beleg_trifft_eine_zeile():
    conn = sqlite3.connect(f"file:{MESS_DB}?mode=ro", uri=True)
    faelle = json.loads(Path(run_akten.CASES).read_text(encoding="utf-8"))
    leer = [(f["id"], m["id"]) for f in faelle for m in f.get("material", [])
            if not run_akten.belege_aufloesen(conn, m)]
    assert not leer, (f"{leer} treffen keine Zeile — Material-Eintrag gegen den Abzug "
                      "prüfen: python eval/run_akten.py --zeigen")


def test_einstieg_nimmt_die_kernbelege():
    fall = {"pflicht": [{"id": "F1", "gewicht": 3}, {"id": "F2", "gewicht": 1}],
            "material": [{"id": "M1", "art": "beschluss", "fuer": ["F1"]},
                         {"id": "M2", "art": "beschluss", "fuer": ["F2"]}]}
    aufgeloest = {"M1": {("beschluss", 10)}, "M2": {("beschluss", 20)}}
    assert run_akten.einstieg(fall, aufgeloest) == {10}
    aufgeloest["M1"] = set()  # ohne Kernbeleg: alle Beschluss-Belege
    assert run_akten.einstieg(fall, aufgeloest) == {20}


def test_vorlagenbasis():
    assert run_akten._vorlage_basis("26/0396/1") == "26/0396"
    assert run_akten._vorlage_basis(None) == ""
