"""Der Anfang einer Arbeitsliste ist keine Stichprobe.

`fit.run` prüft mitten im Lauf, ob noch jeder Beleg-Arm etwas findet, und
bricht ab, wenn einer leer läuft — der Wächter aus #1238. Er hat funktioniert,
nur an der falschen Stelle gemessen: Er nahm die ERSTEN dreißig der
Arbeitsliste, und die kommt aus `annotations_missing`, also nach Kennung
sortiert. Dreißig aufeinanderfolgende Kennungen sind ein Block aus einem
Gremium, kein Querschnitt.

Gemessen am 17.09.2026 an 7.660 offenen Vorlagen, beides im selben frischen
Prozess: `offen[:30]` fand **nur** `recap` (alle vier anderen Arme null),
jede 255. Vorlage fand `fts 28, decision 17, chunk 15, neighbor 14`.

Der Lauf ist daran dreimal gestorben, jedes Mal nach Stunden, jedes Mal mit
der Diagnose „Der Unterbau ist unvollständig" — dabei war er vollständig.
"""
from __future__ import annotations

from council.cities import fit


def _liste(n: int) -> list[dict]:
    return [{"id": f"p/{i:05}"} for i in range(n)]


def test_die_stichprobe_greift_uebers_ganze_feld():
    """Vorn, hinten und in der Mitte — nicht nur vorn."""
    offen = _liste(7660)
    probe = fit.stichprobe(offen)
    assert len(probe) == fit.PROBE_BREITE
    # Der letzte Eintrag liegt im hinteren Drittel: Ein Block vom Anfang
    # käme nie dorthin.
    letzter = int(probe[-1]["id"].split("/")[1])
    assert letzter > len(offen) * 0.9, (
        f"Die Stichprobe endet bei {letzter} von {len(offen)} — sie greift "
        "wieder nur in den Anfang der Arbeitsliste.")


def test_keine_zwei_gleichen():
    offen = _liste(7660)
    probe = fit.stichprobe(offen)
    assert len({p["id"] for p in probe}) == len(probe)


def test_eine_kurze_liste_bleibt_ganz():
    """Weniger Vorlagen als Breite: alle nehmen, nicht jede n-te von zu wenigen."""
    for n in (0, 1, 7, 29, 30):
        assert len(fit.stichprobe(_liste(n))) == n


def test_dieselbe_liste_ergibt_dieselbe_probe():
    """Gestreut und nicht zufällig.

    Zwei Läufe über denselben Bestand müssen dieselbe Stichprobe ziehen,
    sonst ist ein Befund nicht nachstellbar — und ein Wächter, dessen Urteil
    vom Würfel abhängt, bricht irgendwann grundlos ab.
    """
    offen = _liste(5000)
    assert [p["id"] for p in fit.stichprobe(offen)] == \
           [p["id"] for p in fit.stichprobe(list(offen))]


def test_der_lauf_nimmt_nicht_mehr_den_anfang():
    """Der Wächter: `offen[:30]` darf nicht zurückkommen."""
    import inspect

    quelle = "\n".join(z for z in inspect.getsource(fit.run).splitlines()
                       if not z.lstrip().startswith("#"))
    assert "offen[:30]" not in quelle, (
        "Die Stichprobe im Lauf greift wieder in den Anfang der Arbeitsliste "
        "— dort fand sie am 17.09.2026 von fünf Armen nur einen, und der "
        "Lauf brach nach Stunden mit einer falschen Diagnose ab.")
    assert "stichprobe(offen)" in quelle
