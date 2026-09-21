"""Bei Widerspruch zwischen Beschlusstext und belegtem Ortsbezug gewinnt die
Fundstelle.

Gemessen am 21.09.2026 an einer echten Antwort. Der Kontext zu Beschluss 15159
sah so aus:

    [15159] Straßenbenennung nach Rosa Lazarus (Rat · 28.09.2020 · accepted):
    Die Benennung einer Straße nach Rosa Lazarus im zukünftigen Wohnbereich des
    ehemaligen Fliegerhorstes wird beschlossen. — Ortsbezug: Neu-Donnerschwee;
    Fundstelle: Gelände in Neu-Donnerschwee

Die Zusammenfassung sagt Fliegerhorst, der belegte Ortsbezug sagt
Neu-Donnerschwee. Beide stimmen — die Vorlage benennt mehrere Straßen —, aber
das Modell nahm die Zusammenfassung und schrieb den Fliegerhorst in eine
Neu-Donnerschwee-Antwort.

Der Plan dahinter: `docs/plan-ki-frage-zeitbezug.md`, PR 4.
"""
from __future__ import annotations

import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from council import qa  # noqa: E402

#: Der Beschluss aus dem Anlassfall, mit beiden Hälften.
WIDERSPRUCH = {
    "id": 15159, "title": "Straßenbenennung nach Rosa Lazarus",
    "committee": "Rat", "session_date": "2020-09-28", "outcome": "accepted",
    "summary": ("Die Benennung einer Straße nach Rosa Lazarus im zukünftigen "
                "Wohnbereich des ehemaligen Fliegerhorstes wird beschlossen."),
    "location_matches": [{"name": "Neu-Donnerschwee",
                          "evidence": "Gelände in Neu-Donnerschwee"}],
}


def test_der_kontext_traegt_beide_haelften():
    """Erst die Voraussetzung: Die richtige Information steht längst da — es
    fehlte nur die Ansage, welche Hälfte für den Ort zählt."""
    kontext = qa._build_context([WIDERSPRUCH])
    assert "Fliegerhorstes" in kontext                     # der Text
    assert "Ortsbezug: Neu-Donnerschwee" in kontext        # der Beleg
    assert "Fundstelle: Gelände in Neu-Donnerschwee" in kontext


def test_die_ortsregel_sagt_welche_haelfte_zaehlt():
    messages, _ = qa._answer_messages(
        "Was wurde in Neu-Donnerschwee beschlossen?", [WIDERSPRUCH], typ="place")
    prompt = messages[0]["content"]
    assert "Fundstelle" in prompt
    assert "nicht als Ort des Vorhabens" in prompt


def test_nur_bei_ortsfragen():
    """Die Regel hängt am Fragetyp `place` — eine Themenfrage bekommt sie
    nicht, sonst stünde in jedem Prompt eine Anweisung ohne Gegenstand."""
    messages, _ = qa._answer_messages("Was wurde zum Radverkehr beschlossen?",
                                      [WIDERSPRUCH], typ="topic")
    assert "nicht als Ort des Vorhabens" not in messages[0]["content"]
