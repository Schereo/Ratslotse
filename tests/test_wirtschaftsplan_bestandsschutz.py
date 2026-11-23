"""Die Kernzahl allein überschreibt keine volle Zeile aus derselben Vorlage.

Anlass (11/2026): Die Bäder trugen am 24.09.2026 Erträge und Aufwendungen aus
der GuV-Übersicht ihrer Anlage. Nach dem Umzug des Ratsinfos scheiterte der
Abruf der Anlage, und der nächste Lauf schrieb die bloße Kernzahl (nur das
Ergebnis) über die Zeile — Erträge und Aufwendungen waren weg.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from council.wirtschaftsplan import Wirtschaftsplan, bestand_ist_reicher  # noqa: E402


def _kern(result: float = -10_128_335.0, vorlage: str = "25/0819") -> Wirtschaftsplan:
    return Wirtschaftsplan(
        enterprise="bbgo", enterprise_name="Bäderbetriebsgesellschaft", year=2026,
        template_number=vorlage, revenues=None, expenses=None, taxes=None,  # type: ignore[arg-type]
        result=result, capital_plan=None, commitments=None, draft_date=None)


VOLL = {"template_number": "25/0819", "revenues": 4_012_000.0,
        "expenses": -14_140_335.0, "result": -10_128_335.0}


def test_volle_zeile_aus_derselben_vorlage_bleibt():
    assert bestand_ist_reicher(VOLL, _kern())


def test_rundung_innerhalb_der_toleranz_bleibt():
    assert bestand_ist_reicher(VOLL, _kern(result=-10_128_336.0))


def test_anderes_ergebnis_ersetzt():
    """Trifft die Kernzahl das gespeicherte Ergebnis nicht, stimmt eins von
    beiden nicht — dann gilt der Beschlusstext, wie bisher."""
    assert not bestand_ist_reicher(VOLL, _kern(result=-9_000_000.0))


def test_andere_vorlage_ersetzt():
    """Eine Anpassung des Plans ist eine neue Vorlage: Ihre Erträge sind
    andere, die alten stehen zu lassen hieße zwei Pläne mischen."""
    assert not bestand_ist_reicher(VOLL, _kern(vorlage="26/0101"))


def test_ohne_gespeicherte_zeile_oder_ohne_ertraege_ersetzt():
    assert not bestand_ist_reicher(None, _kern())
    assert not bestand_ist_reicher({**VOLL, "revenues": None}, _kern())


def test_neue_volle_zeile_ersetzt_immer():
    voll_neu = Wirtschaftsplan(
        enterprise="bbgo", enterprise_name="Bäderbetriebsgesellschaft", year=2026,
        template_number="25/0819", revenues=4_100_000.0, expenses=-14_228_335.0,
        taxes=0.0, result=-10_128_335.0, capital_plan=None, commitments=None,
        draft_date=None)
    assert not bestand_ist_reicher(VOLL, voll_neu)
