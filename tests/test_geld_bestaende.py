"""Die sechs Facetten der Bestände, die bis 10/2026 nur auf den Haushaltsseiten
standen: Finanzhaushalt, Vorbericht, Schuldenübersicht des Plans,
Verpflichtungsermächtigungen nach Fälligkeit, Abschlüsse der Gesellschaften,
Bilanz-Erläuterungen.

Gemessen am 21.10.2026 gegen die Haushalts-Gold-Fälle (Kontext-Recall ohne
Modell, prod-Abzug 11.10.): Die acht neuen Fälle zu diesen Beständen fanden
ihren Sollwert vorher 1-mal, nachher 8-mal im Kontext; bei den 232 alten
Fällen keine Verschlechterung, die Kontextlänge stieg im Schnitt um 12
Zeichen. Damit das so bleibt, lösen die Facetten ENG aus — die Liste der
Nicht-Fragen unten ist der wichtigere Teil.
"""
import json
from pathlib import Path

import pytest

from council import qa
from council.geld import (bilanz_erlaeuterung, finanzhaushalt, gesellschaft_abschluss,
                          schuldenplan, ve, vorbericht)

MODULE = (finanzhaushalt, vorbericht, schuldenplan, ve, gesellschaft_abschluss,
          bilanz_erlaeuterung)
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "geld_kontext_echt.json"


@pytest.mark.parametrize("modul,frage", [
    (finanzhaushalt, "Wie hoch ist der Finanzmittelfehlbetrag im Finanzhaushalt 2026?"),
    (finanzhaushalt, "Welchen Saldo aus laufender Verwaltungstätigkeit sieht die "
                     "Finanzplanung für 2027 vor?"),
    (vorbericht, "Mit wie viel Gewerbesteuer rechnet die Stadt laut Prognose für 2025?"),
    (vorbericht, "Was steht im Vorbericht zum Haushaltsplan?"),
    (schuldenplan, "Mit welchen Schulden geht der Eigenbetrieb Gebäudewirtschaft "
                   "voraussichtlich ins Jahr 2026?"),
    (schuldenplan, "Was steht in der Schuldenübersicht des Haushaltsplans?"),
    (ve, "Wie viel aus den Verpflichtungsermächtigungen wird 2027 fällig?"),
    (gesellschaft_abschluss, "Welches Jahresergebnis hatte die Bäderbetriebsgesellschaft 2025?"),
    (gesellschaft_abschluss, "Wie hoch war die Bilanzsumme der Verkehr und Wasser GmbH 2024?"),
    (bilanz_erlaeuterung, "Was steckt hinter den Rückstellungen in der Bilanz der Stadt?"),
])
def test_zieht(modul, frage):
    assert modul.NAME in qa.geld_facetten(frage, "topic"), frage


@pytest.mark.parametrize("frage", [
    # Die Allerweltsfragen der alten Facetten sollen bleiben, wie sie waren.
    "Wie hoch sind die Schulden der Stadt?",
    "Wie viel investiert die Stadt 2026?",
    "Wie hoch ist die Gewerbesteuer 2024?",
    "Wie hoch ist das Anlagevermögen der Stadt Oldenburg?",
    "Wem gehört die GSG Oldenburg?",
    "Was steht im Wirtschaftsplan des Abfallwirtschaftsbetriebs?",
    "Was kostet die Feuerwehr?",
    "Wie hoch ist der Hebesatz für die Grundsteuer B?",
])
def test_zieht_nicht(frage):
    neu = {m.NAME for m in MODULE}
    assert not neu & qa.geld_facetten(frage, "topic"), frage


@pytest.mark.parametrize("modul", MODULE, ids=lambda m: m.NAME)
def test_baustein_an_echten_zahlen(modul):
    """Jeder Baustein aus dem Abzug: nicht leer, unter seiner Grenze, mit Beleg
    und mit dem Satz, der sagt, WAS die Zahl ist."""
    daten = json.loads(FIXTURE.read_text())[modul.NAME]
    assert daten, f"{modul.NAME}: keine Frage im Abzug (tests/test_geld_gliederung.py)"
    for d in daten:
        text = modul.block(d)
        assert text and len(text) <= modul.FACETTE.grenze, (modul.NAME, len(text))
        assert "Beleg:" in text and "NIE mit [id]" in text
    erwartet = {
        "finanzhaushalt": "Finanzmittelüberschuss/-fehlbetrag 2026 (Ansatz)",
        "vorbericht": "PROGNOSE",
        "schuldenplan": "VORAUSSICHTLICH 31.12.2025",
        "ve": "fällig 2027",
        "gesellschaft_abschluss": "(Ist, Jahresabschluss)",
        "bilanz_erlaeuterung": "Rückstellungen (Erläuterung zur Bilanz 2025)",
    }[modul.NAME]
    assert any(erwartet in modul.block(d) for d in daten), (modul.NAME, erwartet)


def test_leer_heisst_kein_baustein():
    for modul in MODULE:
        assert modul.block(None) == "" and modul.block({}) == ""
