"""Welche Features an sind — die eine Stelle, an der das steht.

**Wozu.** Ein Feature fährt heute in dem Moment nach Prod, in dem sein PR
gemergt wird. Wer etwas Größeres baut, hat drei Möglichkeiten, und alle drei
sind unangenehm: den Zweig wochenlang offen halten (und mit jedem Tag
schwerer mergen), auf `feature.ratslotse.de` ausweichen (wo niemand
mitliest), oder es einfach live schalten und hoffen.

Ein Schalter trennt **Ausliefern** von **Freischalten**. Der Code fährt
fertig nach `main`, bleibt aber dunkel, bis jemand ihn anschaltet — und lässt
sich in derselben Minute wieder ausschalten, ohne Revert und ohne Deploy.

**Warum über ``/api/app-config`` und nicht über ``NEXT_PUBLIC_``.** Eine
``NEXT_PUBLIC_``-Variable wird zur BAUZEIT einkompiliert; sie umzulegen heißt,
neu zu bauen und neu zu deployen — also genau das, was der Schalter ersparen
soll. Dieselbe Falle hat den CARTO-Kartenschlüssel erwischt (s. ``CLAUDE.md``).
``/api/app-config`` fragt jede Oberfläche ohnehin vor allem anderen ab, das
Web wie die native App; ein Neustart des Dienstes genügt.

**Was ein Schalter NICHT ist.** Er ist keine Rechteprüfung. Wer eine Fläche
vor bestimmten Konten schützen will, nimmt ein Recht (``kern/roles.py``) — das
Backend setzt es durch. Ein Feature-Schalter regelt, ob etwas **schon so
weit** ist, nicht, **wer** es sehen darf. Deshalb reicht es, wenn die
Oberfläche ihn liest: Was hinter ihm liegt, ist ohnehin unfertig und nicht
geheim. Braucht ein halbfertiges Feature zusätzlich Schutz, gehört ein Recht
davor, nicht ein zweiter Schalter.

**Eintragen, benutzen, wieder entfernen.** Ein Schalter ist eine Schuld wie
eine Ausnahme im Linter: Sobald das Feature steht, fliegt er raus und der Code
bleibt. ``tests/test_features.py`` hält beide Richtungen — kein Schalter ohne
Nutzung, keine Nutzung ohne Schalter.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Feature:
    key: str
    #: Ein Satz: Was schaltet dieser Schalter frei? Menschentext.
    description: str
    #: Woran man erkennt, dass er weg kann. Ohne das bleibt jeder Schalter für
    #: immer stehen — „vielleicht braucht ihn noch jemand".
    fertig_wenn: str


#: Alle Schalter, die es gibt. Ein Name, der hier nicht steht, ist ein
#: Tippfehler — und ein Tippfehler in einem Schalter schaltet lautlos NIE ein.
#:
#: **Absichtlich leer.** Die Mechanik steht bereit; der erste Schalter kommt
#: mit dem ersten Feature, das ihn braucht. Ein Beispiel-Eintrag „auf Vorrat"
#: wäre schon die Schuld, gegen die `fertig_wenn` geschrieben ist.
#:
#: So sieht ein Eintrag aus::
#:
#:     "neue-suche": Feature(
#:         key="neue-suche",
#:         description="Die überarbeitete Beschluss-Suche mit Facetten.",
#:         fertig_wenn="Die Stadion-Fragen liefern mindestens so gute Treffer "
#:                     "wie vorher (tests/…/eval).",
#:     ),
FEATURES: dict[str, Feature] = {}


def aktive(roh: str | None = None) -> list[str]:
    """Die eingeschalteten Schalter, aus ``FEATURE_FLAGS``.

    Kommagetrennt, Leerraum egal: ``FEATURE_FLAGS=haushalt-labor, neue-suche``.
    Ein Name, den ``FEATURES`` nicht kennt, wird **verworfen** und nicht
    durchgereicht — sonst schaltete ein Tippfehler in der ``.env`` etwas frei,
    das es nicht gibt, und niemand sähe den Unterschied zu „ist eben aus".

    Die Reihenfolge folgt der Registry, nicht der ``.env``: So ist die Antwort
    von ``/api/app-config`` stabil und taugt als Cache-Schlüssel.
    """
    wert = os.environ.get("FEATURE_FLAGS", "") if roh is None else roh
    gewuenscht = {t.strip() for t in wert.split(",") if t.strip()}
    return [k for k in FEATURES if k in gewuenscht]


def an(key: str, roh: str | None = None) -> bool:
    """Ist dieser Schalter an? Für den Gebrauch im Backend."""
    return key in aktive(roh)
