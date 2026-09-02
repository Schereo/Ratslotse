"""Anreden und Rollen vor einem Namen — zwei Listen, zwei Zwecke.

**Der Fehler.** ``CouncilStore`` trug bis 02.09.2026 **zweimal** ein
Klassenattribut ``_ANREDEN``: oben eine lange Liste, die auch Rollen kennt
(„Ausschussvorsitzender Behrens"), unten eine kurze für die Anzeige. Zwei
Attribute mit demselben Namen — das zweite gewinnt, das erste war tot. Ein
Kommentar über der langen Liste erklärt ausführlich, warum sie Rollen
mitnimmt; wirksam war sie nie.

**Gemessen am echten Bestand**, bevor es geändert wurde: zehn Sprecher-Formen
mit 39 Wortbeiträgen waren keiner Person zugeordnet. Nichts ging dabei
verloren — die lange Liste ordnet zehn Formen mehr zu und keine weniger, und
``namensteile()`` liefert für alle 51 Personen unverändert dasselbe.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from council.store import CouncilStore  # noqa: E402


def test_die_beiden_listen_heissen_verschieden():
    """Sonst gewinnt wieder die zuletzt definierte, und die andere ist tot."""
    assert CouncilStore._ANREDEN is not CouncilStore._ANREDEN_ANZEIGE
    assert len(CouncilStore._ANREDEN) > len(CouncilStore._ANREDEN_ANZEIGE)


@pytest.mark.parametrize("sprecher, vorname, nachname", [
    ("Ausschussvorsitzender Behrens", "Paul", "Behrens"),
    ("Ausschussvorsitzende Kruse", "Ingrid", "Kruse"),
    ("Ratsvorsitzender Harms", "Tim Ebbeke", "Harms"),
    ("Oberbürgermeister Krogmann", "Jürgen", "Krogmann"),
    ("Stadtrat Bembennek", "Dagmar", "Bembennek"),
])
def test_eine_rolle_vor_dem_namen_zaehlt_als_anrede(sprecher, vorname, nachname):
    """Genau die Formen, die vorher durchfielen — mit den echten Namen aus dem
    Bestand."""
    assert CouncilStore._spricht_diese_person(sprecher, vorname, nachname)


@pytest.mark.parametrize("eingabe, erwartet", [
    ("Herr Jens Freymuth", "Jens Freymuth"),
    ("Frau Esther Niewerth-Baumann", "Esther Niewerth-Baumann"),
    ("Ratsherr Ellberg", "Ellberg"),
    # Ein Titel gehört zum Namen und bleibt stehen.
    ("Dr. Esther Niewerth-Baumann", "Dr. Esther Niewerth-Baumann"),
    # Eine ROLLE ist keine Anrede im Anzeige-Sinn: „Oberbürgermeister
    # Krogmann" soll auf der Seite auch so dastehen.
    ("Oberbürgermeister Krogmann", "Oberbürgermeister Krogmann"),
])
def test_die_anzeige_streicht_nur_die_vier_anreden(eingabe, erwartet):
    assert CouncilStore._person_anzeige(eingabe) == erwartet
