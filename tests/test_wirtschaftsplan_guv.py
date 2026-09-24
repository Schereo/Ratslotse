"""Die GuV-Übersichten der Wirtschaftspläne von BBGO, BBO und Hafen
(council/wirtschaftsplan_guv.py).

Die Fixtures sind die Tabellenzeilen echter Anlagen mit Wortkanten: BBGO 2026
(Dokument 300203, Rechenfehler der Vorlage in der Spalte 2027), BBGO 2021
(225393, leere Zellen), BBO 2020 (213985, mittig gesetzter Kopf), Hafen 2019
(194665, HGB-Gliederung mit positiven Aufwendungen) und BBGO 2023 (255530,
senkrecht gesetzt)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from council import wirtschaftsplan_guv as g

FX = json.loads((Path(__file__).parent / "fixtures" / "wirtschaftsplan_guv_zeilen.json").read_text())


def _lies(key: str, jahr: int, soll: float | None = None) -> g.GuvLesung:
    return g.lies_guv([[tuple(w) for w in z] for z in FX[key]], jahr, soll)


def test_bbgo_2026_planspalte_und_vermerkter_rechenfehler():
    l = _lies("bbgo_2026", 2026)
    assert l.result == -10_128_335.0          # = Kernzahl im Beschlusstext
    assert (l.revenues, l.expenses) == (10_119_804.0, 20_248_140.0)
    # In der Vorausschau 2027 verrechnet sich die Vorlage — vermerkt, nicht verworfen.
    assert any(a.startswith("Spalte 2027") for a in l.abweichend)


def test_leere_zellen_finden_ihre_spalte():
    """„Bestandsveränderungen 0 0,0 5.000 0,1 …" — vier Zellen von acht."""
    l = _lies("bbgo_2021", 2021)
    assert l.result == -5_447_575.0 and l.proben == len(l.jahre) == 8
    assert l.jahre[l.spalte] == 2021 and l.spalte == 4


def test_bbo_ausgeglichen_mit_umsatz():
    l = _lies("bbo_2020", 2020)
    assert l.result == 0.0
    assert l.revenues == pytest.approx(4_543_531.0)
    assert abs(l.revenues - l.expenses) <= 1


def test_hafen_hgb_vorzeichen():
    l = _lies("hafen_2019", 2019)
    assert (l.revenues, l.expenses, l.result) == (141_700.0, 415_650.0, -273_950.0)


def test_senkrecht_gesetzte_seite():
    l = _lies("bbgo_2023", 2023)
    assert l.result == -5_298_647.0


def test_planspalte_nach_beschlusstext():
    """Steht das Planjahr mehrfach im Kopf, gilt die Spalte mit der Kernzahl —
    und ohne Treffer die erste."""
    ohne = _lies("bbgo_2021", 2021)
    mit = _lies("bbgo_2021", 2021, ohne.result)
    assert mit.spalte == ohne.spalte


def test_falsches_jahr_wirft():
    with pytest.raises(g.GuvFehler):
        _lies("hafen_2019", 2031)
