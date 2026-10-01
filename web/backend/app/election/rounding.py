"""Kaufmännisch runden — genau EINMAL, und über den Dezimaltext.

**Nur einmal.** Die API liefert Anteile auf sechs Stellen (``exact_pct``),
gerundet wird erst bei der Anzeige. Bis 09/2026 rundete das Backend auf zwei
Stellen und die Seite danach auf eine — doppelt gerundet. Nach der Stichwahl
zeigte sich das: Rohr hat 30.792 von 59.734 Stimmen, 51,5485 %. Die Stadt
schreibt 51,55 %, und wer das noch einmal rundet, landet bei 51,6 — richtig
ist 51,5. Ebenso BSW in der Ratswahl: 4.162 von 252.400 sind 1,6490 %, zwei
Stellen machten 1,65 daraus und eine dann 1,7.

**Über den Dezimaltext.**

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


#: Nachkommastellen, mit denen die API Anteile ausliefert — genug, dass die
#: Rundung bei der Anzeige nie an einem schon gerundeten Wert hängt.
EXACT_DIGITS = 6


def exact_pct(part: float, whole: float | None) -> float | None:
    """Anteil in Prozent auf sechs Stellen — ``None`` ohne Nenner."""
    if not whole:
        return None
    return round(100 * part / whole, EXACT_DIGITS)
