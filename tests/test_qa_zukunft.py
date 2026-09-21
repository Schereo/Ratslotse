"""Eine Zukunftsfrage ohne Zukunft sagt das — statt Altes ins Futur zu setzen.

„Was ist für Neu-Donnerschwee geplant?" (echte Nutzerfrage, 21.09.2026) bekam
eine Antwort im Futur über einen Bebauungsplan, dessen Satzungsbeschluss von
2018 ist. Gemessen auf Prod lieferten dabei BEIDE Ausblick-Wege des Routers
leere Listen: `store.geplante_beratungen_fuer([…16 kvonr…])` und
`store.kommende_beratungen(["Neu-Donnerschwee", "Donnerschwee", "Kaserne"])`.

Der Plan dahinter: `docs/plan-ki-frage-zeitbezug.md`, PR 3.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from council import qa  # noqa: E402


@pytest.mark.parametrize("frage", [
    "Was ist für Neu-Donnerschwee geplant?",
    "Was soll am Fliegerhorst entstehen?",
    "Wie geht es weiter mit der Cäcilienbrücke?",
    "Welche Planung gibt es für den Stadthafen?",
    "Was passiert als nächstes beim Stadion?",
    "Wird dort ein Radweg gebaut?",
    "Soll die Sporthalle saniert werden?",
])
def test_zukunftsfragen_werden_erkannt(frage):
    assert qa.zukunftsfrage(frage)


@pytest.mark.parametrize("frage", [
    # Die Vergangenheitsform ist der wichtigste Gegenfall: „war geplant" fragt
    # danach, was einmal vorgesehen war — da wäre der Hinweis schlicht falsch.
    "Was war ursprünglich geplant?",
    "Was war für das Gelände vorgesehen?",
    "Was wurde 2018 beschlossen?",
    "Was hat der Rat zuletzt beschlossen?",
    "Wer stimmte dagegen?",
    "Wie viel kostet die Sporthalle?",
    # „soll … kosten" ist kein Bauvorhaben, sondern eine Geldfrage.
    "Wie viel soll die Halle kosten?",
    "Was ist die GSG?",
])
def test_keine_zukunftsfragen(frage):
    assert not qa.zukunftsfrage(frage)


def test_die_regel_steht_nur_im_leeren_fall_im_prompt():
    kandidaten = [{"id": 7, "title": "Bebauungsplan 58", "session_date": "2018-10-22"}]
    mit, _ = qa._answer_messages("Was ist geplant?", kandidaten, zukunft_leer=True)
    assert "KEINE ZUKUNFT IM KONTEXT" in mit[0]["content"]
    assert "VERGANGENHEIT" in mit[0]["content"]
    ohne, _ = qa._answer_messages("Was ist geplant?", kandidaten)
    assert "KEINE ZUKUNFT IM KONTEXT" not in ohne[0]["content"]
