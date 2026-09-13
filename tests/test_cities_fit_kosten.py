"""Was eine Vorlage gekostet hat — ihre eigenen Aufrufe, nicht die der Nachbarn.

`fit` fragt drei Stimmen je Vorlage, und zwar in vielen Arbeitern gleichzeitig.
Die Kosten wurden bis zum 13.09.2026 als Differenz auf einem GEMEINSAMEN
Zähler gemessen — und damit stand an jeder Vorlage, was in ihrer Zeitspanne
alle anderen Arbeiter verbraucht hatten:

    Lauf            Arbeiter   gespeichert   wirklich   Verhältnis
    09.09. (v3)         96      $1611.90      $15.57       104x
    13.09. Hannover     48      $  30.29      $ 0.64        47x

**Der Faktor ist die Arbeiterzahl.** Der Lauf-Gesamtwert war immer richtig —
nur die Zahl an der einzelnen Vorlage war es nie. Wer sie liest, um zu
entscheiden, ob ein Bestandslauf bezahlbar ist, verrechnet sich um zwei
Größenordnungen.
"""
from __future__ import annotations

import inspect

from council.cities import fit


def test_die_kosten_kommen_nicht_aus_dem_gemeinsamen_zaehler():
    """Der Wächter: eine Differenz auf `stand["cost_usd"]` ist der Fehler.

    Er liest den Quelltext, weil der Fehler nur unter NEBENLÄUFIGKEIT
    auftritt — ein Test mit einem Arbeiter wäre grün geblieben, und genau
    deshalb ist er ein halbes Jahr nicht aufgefallen.
    """
    quelle = inspect.getsource(fit.run)
    assert 'vorher = stand["cost_usd"]' not in quelle, (
        "Die Kosten je Vorlage werden wieder als Differenz auf dem "
        "gemeinsamen Zähler gemessen. Mit N Arbeitern steht dann das "
        "N-Fache an jeder Vorlage. Stattdessen: eigener Korb je Vorlage.")
    assert "sum(korb)" in quelle, (
        "Die Kosten je Vorlage sollen aus dem eigenen Korb kommen.")


def test_der_korb_sammelt_nur_die_eigenen_aufrufe():
    """Drei Stimmen, drei Beträge — und nichts von den Nachbarn."""
    quelle = inspect.getsource(fit.run)
    # `eine_stimme` legt ihren Betrag in den Korb, den der Aufrufer mitgibt.
    assert "korb.append(kosten)" in quelle
    assert "eine_stimme(p, belege, klasse, korb)" in quelle
