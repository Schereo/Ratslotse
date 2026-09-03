"""Der Bericht zum 31. März: die Tabelle im Vorlagentext (council/budget_execution.py).

Die Fixtures sind die echten Vorlagentexte, auf die Tabelle gekürzt."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from council import budget_execution as be

Q1 = json.loads((Path(__file__).parent / "fixtures" / "vollzug_q1.json").read_text())


def _lies(nr):
    return be.lies_q1_vorlage(Q1[nr]["raw_text"], Q1[nr]["title"])


@pytest.mark.parametrize(("nr", "plan", "prognose", "abweichung"), [
    ("26/0155", -68_679_445, -73_164_412, -4_485_000),
    ("25/0308", -91_474_677, -48_766_677, 42_708_000),
    ("24/0310", -31_930_657, -26_878_986, 5_051_671),
    ("22/0267", 11_873_605, 2_025_817, -9_847_788),
])
def test_summenzeile_und_dreizehn_teilhaushalte(nr, plan, prognose, abweichung):
    b = _lies(nr)
    assert b is not None
    assert (b.budget_year, b.as_of, b.budget) == (int("20" + nr[:2]), f"20{nr[:2]}-03-31", be.ERGEBNISHAUSHALT)
    zeilen = [p for p in b.positionen if not p.is_total]
    assert [p.sub_budget for p in zeilen] == list(range(1, 14))
    total = b.summe["result"]
    assert (total.budgeted, total.forecast, total.deviation) == (plan, prognose, abweichung)
    assert be.PROBE_Q1_SUMMEN in b.probes


def test_minus_mit_leerzeichen_und_strich_als_null():
    """2025 schreibt „- 8.964.051", 2026 „- 4.000.000" neben einem einsamen
    Strich für „keine Abweichung" — beides muss auseinandergehalten werden."""
    b26 = {p.sub_budget: p for p in _lies("26/0155").positionen}
    assert (b26[1].budgeted, b26[1].deviation) == (-8_844_512, 0.0)
    assert (b26[2].forecast, b26[2].deviation) == (-48_517_854, -4_000_000)
    # Zeile 10 druckt eine Prognose, die die Abweichung nicht trägt — es gilt
    # Plan plus Abweichung (die Summenzeile bestätigt die Abweichungen).
    assert (b26[10].budgeted, b26[10].deviation, b26[10].forecast) == (
        -113_195_538, -6_622_000, -119_817_538)
    assert b26[11].forecast == -129_875_120 + 6_137_000
    assert b26[13].label.startswith("Nicht rechtsfähige")
    b25 = {p.sub_budget: p for p in _lies("25/0308").positionen}
    assert (b25[1].budgeted, b25[4].deviation) == (-8_964_051, 48_800_000)


def test_ohne_tabelle_kein_bericht():
    """2018 berichtet zum ersten Quartal nur in Prosa."""
    assert _lies("18/0316") is None


def test_verfehlte_summenzeile_reisst():
    text = Q1["26/0155"]["raw_text"].replace("-68.679.445", "-68.000.000")
    with pytest.raises(be.VollzugFehler, match="Plan der Teilhaushalte"):
        be.lies_q1_vorlage(text, Q1["26/0155"]["title"])
