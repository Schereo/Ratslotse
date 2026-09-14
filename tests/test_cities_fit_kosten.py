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


def test_stance_laeuft_nicht_in_der_ueblichen_schleife():
    """Er braucht das Label SEINER Gruppe — das kennt nur `stance_all`.

    Am 13.09.2026 meldete der Bestandslauf **9.289 „Fehler"** ohne einen
    einzigen Modellaufruf: `annotate.run` rendert den stance-Prompt ohne
    `{gruppe}` und läuft je Vorlage in ein `KeyError`. Es kostete nichts und
    tat nichts — aber eine Fehlerzahl, die nichts bedeutet, ist schlimmer
    als keine: Der Wochen-Cron zählt sie in `job_runs`, und die nächste
    Person sucht einen Fehler, den es nicht gibt.
    """
    from council.cities.annotators import active_annotators, get

    assert get("stance").own_stage == "cluster"
    ueblich = [a.key for a in active_annotators("paper")]
    assert "stance" not in ueblich, (
        "`stance` läuft wieder in der üblichen Schleife und scheitert dort "
        "an jedem einzelnen Objekt.")
    assert "stance" in [a.key for a in active_annotators("paper", own_stage="cluster")]


def test_der_stance_prompt_verlangt_seine_gruppe():
    """Der Grund, warum er eine eigene Stufe hat — nicht bloß eine Konvention."""
    import re

    from kern import prompts

    from council.cities.annotators import get

    platzhalter = set(re.findall(r"\{(\w+)\}", prompts.get(get("stance").prompt_user)))
    assert "gruppe" in platzhalter, (
        "Braucht der Prompt seine Gruppe nicht mehr, kann `stance` zurück in "
        "die übliche Schleife — dann gehört `own_stage` weg.")
