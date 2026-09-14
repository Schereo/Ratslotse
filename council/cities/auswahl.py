"""Welche Vorlagen einer Stadt am Vergleich teilnehmen — und welche nicht.

**Warum das eine eigene Datei ist.** Drei Stufen wählen Kandidaten:
``annotate`` (Einordnung und Aufwand), ``fit`` (das Urteil) und über deren
Ergebnisse mittelbar ``cluster``. Stünde die Regel dreimal da, liefe sie
auseinander — genau das steht schon als Warnung in ``annotate.run`` über dem
``transfer in USABLE``-Filter.

**Zwei Einschränkungen, beide je Stadt in der Registry.**

1. **Das Zeitfenster.** ``since`` in der Registry regelt, was GEERNTET wird;
   für die Auswertung war das bisher unbegrenzt. Gemessen am 13.09.2026:
   Hannover trägt 24.654 Kandidaten seit 2017, die fünf OParl-Städte
   beginnen 2023. Ungefenstert kostete Hannover allein rund $75 statt $35 —
   und verglich acht Jahre gegen drei.
2. **Die Vorlagenarten.** ``IDEA_KINDS`` sagt projektweit, was eine Idee
   tragen kann. Eine Stadt kann davon weniger brauchen: Hannovers 6.483
   Anfragen tragen in **1 %** der Fälle ein Ergebnis, weil Anfragen dort
   beantwortet und nicht beschlossen werden. Sie einzuordnen kostet rund $7
   und liefert nichts, was der Vergleich lesen könnte (Tims Entscheidung
   13.09.2026).

**Oldenburg bleibt ungefenstert.** Es ist die Bezugsstadt: ``fit`` fragt,
ob Oldenburg eine Sache schon hat, und ein Beschluss von 2019 beantwortet
das genauso wie einer von 2024.
"""
from __future__ import annotations

from typing import NamedTuple

from council.cities.registry import BODIES
from council.cities.store import CitiesStore


class Fenster(NamedTuple):
    """Was von einer Stadt in den Vergleich geht."""

    since: str | None
    kinds: tuple[str, ...]


def fenster(body_id: str | None) -> Fenster:
    """Das Fenster einer Stadt — oder das offene, wenn sie unbekannt ist.

    Ohne ``body_id`` läuft eine Stufe über alle Städte; dann kann es kein
    gemeinsames Fenster geben, und jede Stadt bringt ihr eigenes mit
    (``papiere`` macht das). Eine Stadt, die nicht in der Registry steht,
    bekommt das offene Fenster: Der Speicher ist die Wahrheit über den
    Bestand, nicht die Registry.
    """
    spec = BODIES.get(body_id or "")
    if spec is None:
        return Fenster(None, ())
    return Fenster(spec.compare_since, tuple(spec.compare_kinds))


def papiere(main: CitiesStore, body_id: str | None = None) -> list[dict]:
    """Die Vorlagen, die am Vergleich teilnehmen.

    Über alle Städte hinweg gilt je Stadt ihr eigenes Fenster — deshalb wird
    dann Stadt für Stadt gefragt und nicht einmal über alles.
    """
    if body_id:
        f = fenster(body_id)
        return main.papers(body_id=body_id, since=f.since, kinds=f.kinds)
    raus: list[dict] = []
    for stadt in main.paper_body_ids():
        f = fenster(stadt)
        raus += main.papers(body_id=stadt, since=f.since, kinds=f.kinds)
    return raus
