"""Der Rechenkern des Potenzial-Berichts (``scripts/stichwahl_potenzial.py``)
hält die Zahlen, auf denen ``docs/plan-stichwahl-potenzial.md`` steht.

Fällt einer dieser Tests, stimmt der Plan nicht mehr — dann ist der Plan zu
korrigieren, nicht der Test.
"""
from __future__ import annotations

import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from scripts import stichwahl_potenzial as sp  # noqa: E402


def test_die_ausgangslage_2026():
    zeilen = sp.potenzial(sp.VORGABE, sp.VORGABE_CDU)
    assert len(zeilen) == 133
    assert sum(z["rohr"] for z in zeilen) == 25850
    assert sum(z["prange"] for z in zeilen) == 28075
    assert sum(z["prange"] - z["rohr"] for z in zeilen) == 2225
    # Die Ausgeschiedenen laut Bezirksdatei (Castur/Stille stecken in „Sonstige").
    assert sum(z["pool"] for z in zeilen) == 10198 + 4945 + 6211 + 4025 + 3843
    # Jeder Urnenbezirk kennt seine Wahlberechtigten; die Briefwahl nicht.
    assert all(z["eligible"] > 0 for z in zeilen if not z["postal"])
    assert all(z["non_voters"] == 0 for z in zeilen if z["postal"])


def test_die_briefwahl_ist_rohrs_bessere_haelfte():
    zeilen = sp.potenzial(sp.VORGABE, sp.VORGABE_CDU)
    def anteil(rows):
        return 100 * sum(z["rohr"] for z in rows) / sum(z["rohr"] + z["prange"] for z in rows)
    urne = anteil([z for z in zeilen if not z["postal"]])
    brief = anteil([z for z in zeilen if z["postal"]])
    assert brief > urne + 4, (urne, brief)


def test_die_annahmen_wirken_linear_und_null_heisst_null():
    null = sp.potenzial({s: (0, 0) for s in sp.AUSGESCHIEDEN}, (0, 0))
    assert sum(z["net_total"] for z in null) == 0
    nur_linke = sp.potenzial({**{s: (0, 0) for s in sp.AUSGESCHIEDEN}, "boldt": (100, 0)}, (0, 0))
    assert round(sum(z["net_total"] for z in nur_linke)) == 10198


def test_jeder_urnenbezirk_hat_einen_ort():
    zeilen = sp.potenzial(sp.VORGABE, sp.VORGABE_CDU)
    ohne = [z["number"] for z in zeilen if not z["postal"] and z["district_name"] == "Briefwahl"]
    assert ohne == [], ohne
