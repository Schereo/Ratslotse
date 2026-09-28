"""Kaufmännisch runden — über den Dezimaltext, nicht über die Gleitkommazahl.

Die Stadt meldet Anteile mit zwei Stellen („51,55 %"), wir zeigen eine. Als
Gleitkommazahl ist 51,55 aber 51,5499…, und ``f"{x:.1f}"`` macht daraus
51,5 — auf dem Teilbild der Stichwahl stand am 27.09.2026 „Rohr 51,5 %",
amtlich waren es 51,55 %. ``Decimal(str(x))`` nimmt die kürzeste Schreibweise,
also genau die Ziffern, die aus der Ergebnisdarstellung kamen.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def half_up(value: float, digits: int = 1) -> float:
    """``half_up(51.55) == 51.6``; ``half_up(48.45) == 48.5``.

    Vorher auf zehn Stellen geglättet: Eine Differenz trägt eigenes Rauschen
    (13,45 − 10,3 ist 3,1499…986), und das soll nicht über die Stufe
    entscheiden — dieselbe Regel wie ``fixed()`` im Frontend."""
    step = Decimal(1).scaleb(-digits)
    return float(Decimal(repr(round(value, 10))).quantize(step, rounding=ROUND_HALF_UP))


def pct_text(value: float | None, digits: int = 1) -> str:
    """„51,6 %" — oder „–" ohne Wert."""
    if value is None:
        return "–"
    return f"{half_up(value, digits):.{digits}f}".replace(".", ",") + " %"
