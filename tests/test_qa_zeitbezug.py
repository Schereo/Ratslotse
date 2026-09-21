"""Der Zeitbezug der KI-Frage: Wie alt ist das, was die Antwort erzählt?

Anlass ist eine echte Nutzerfrage vom 21.09.2026. „Was ist für
Neu-Donnerschwee geplant?" bekam eine belegtechnisch saubere Antwort im
Präsens — über einen Satzungsbeschluss vom Oktober 2018. Das Quartier steht
längst, der jüngste Beleg der ganzen Antwort war von Februar 2023, und kein
Satz sagte das.

Das Modell hat dabei nichts falsch gemacht: Das Datum steht zwar an jedem
Beschluss im Kontext, aber der Antwort-Prompt kennt das HEUTIGE Datum nicht.
Ohne Bezugspunkt liest sich ein alter Beschluss wie ein aktueller Plan.
`qa.aktenstand` rechnet den Bezug deterministisch aus; `qa.aktenstand_regel`
sagt dem Modell, was daraus folgt.

Der Plan dahinter: `docs/plan-ki-frage-zeitbezug.md`. Der Weg durch den Endpunkt steht in
`test_backend_api.py` — dort wohnt die `client`-Fixture.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from council import qa  # noqa: E402

HEUTE = date(2026, 9, 21)


class _StoreStub:
    """Nur die zwei Kalender-Fragen, die `aktenstand` stellt."""

    def __init__(self, letzte: str | None = "2026-06-29",
                 naechste: str | None = "2026-09-21"):
        self._letzte, self._naechste = letzte, naechste

    def letzte_beschluss_sitzung(self) -> str | None:
        return self._letzte

    def upcoming_sessions(self, limit: int = 20) -> list[dict]:
        return [{"session_date": self._naechste}] if self._naechste else []


def _kandidaten(*daten: str) -> list[dict]:
    return [{"id": i, "session_date": d} for i, d in enumerate(daten, start=1)]


# ---- Das Alter ------------------------------------------------------------

def test_alter_stand_wird_als_alt_erkannt():
    """Der Anlassfall, mit seinen echten Daten."""
    stand = qa.aktenstand(_StoreStub(), _kandidaten("2018-10-22", "2023-02-09"),
                          heute=HEUTE)
    assert stand["latest"] == "2023-02-09"
    # Februar 2023 → September 2026 sind 43 Monate, nicht 31: Beim Schreiben
    # des Plans war das einmal falsch von Hand gerechnet.
    assert stand["months"] == 43
    assert stand["level"] == "old"
    assert stand["last_session"] == "2026-06-29"
    assert stand["next_session"] == "2026-09-21"


def test_frische_frage_bleibt_unberuehrt():
    """Die wichtigste Gegenrichtung: Eine aktuelle Antwort darf von diesem
    ganzen Umbau nichts merken — sonst wird jede Antwort vorsichtiger, und die
    Vorsicht verliert ihren Wert."""
    stand = qa.aktenstand(_StoreStub(), _kandidaten("2026-06-29"), heute=HEUTE)
    assert stand["level"] == "fresh"
    assert qa.aktenstand_regel(stand).count("ALTER Stand") == 0


def test_ruhig_liegt_zwischen_den_beiden():
    stand = qa.aktenstand(_StoreStub(), _kandidaten("2025-06-05"), heute=HEUTE)
    assert stand["months"] == 15 and stand["level"] == "quiet"


def test_monate_zaehlt_angefangene_nicht_mit():
    """Am Monatstag selbst ist der Monat voll, einen Tag davor nicht."""
    assert qa._monate_her("2026-03-21", HEUTE) == 6
    assert qa._monate_her("2026-03-22", HEUTE) == 5
    # Ein Datum aus der Zukunft (terminierte Sitzung) ist nicht negativ alt.
    assert qa._monate_her("2026-12-01", HEUTE) == 0


# ---- Die Ausfälle: Zusatz, nie Blocker ------------------------------------

def test_ohne_datierte_kandidaten_bleibt_es_leer():
    assert qa.aktenstand(_StoreStub(), [], heute=HEUTE) == {}
    assert qa.aktenstand(_StoreStub(), [{"id": 1}], heute=HEUTE) == {}
    assert qa.aktenstand_regel({}) == ""
    assert qa.aktenstand_regel(None) == ""


def test_ein_kaputter_store_kostet_nur_den_kalender():
    """Das Alter ist die Pflicht, der Sitzungskalender die Kür: Wenn der Store
    stolpert, bleibt die Altersangabe trotzdem stehen."""
    class _Kaputt:
        def letzte_beschluss_sitzung(self):
            raise RuntimeError("keine Datenbank")

        def upcoming_sessions(self, limit: int = 20):
            raise RuntimeError("keine Datenbank")

    stand = qa.aktenstand(_Kaputt(), _kandidaten("2023-02-09"), heute=HEUTE)
    assert stand["level"] == "old" and stand["last_session"] is None
    assert "43 Monate her" in qa.aktenstand_regel(stand)


# ---- Die Regel, die im Prompt landet --------------------------------------

def test_die_regel_nennt_die_tatsachen_und_verbietet_das_praesens():
    regel = qa.aktenstand_regel(
        qa.aktenstand(_StoreStub(), _kandidaten("2023-02-09"), heute=HEUTE))
    assert "STAND DER AKTEN" in regel
    assert "09.02.2023" in regel          # deutsches Datum, wie im Kontext
    assert "29.06.2026" in regel          # zuletzt überhaupt getagt
    assert "21.09.2026" in regel          # nächste Sitzung
    assert "Präsens" in regel and "ERSTEN Satz" in regel


def test_ruhige_lage_nennt_die_sitzungen_dazwischen():
    """Kein Alarm, aber die ehrliche Zusatzinfo: Der Rat hat getagt und nichts
    dazu entschieden."""
    regel = qa.aktenstand_regel(
        qa.aktenstand(_StoreStub(), _kandidaten("2025-06-05"), heute=HEUTE))
    assert "ALTER Stand" not in regel
    assert "nichts zu dieser Sache entschieden" in regel


def test_die_regel_steht_wirklich_im_antwort_prompt():
    """Ohne diesen Durchstich nützt die schönste Regel nichts — sie muss durch
    `_answer_messages` bis in den Prompt kommen."""
    stand = qa.aktenstand(_StoreStub(), _kandidaten("2023-02-09"), heute=HEUTE)
    messages, _ = qa._answer_messages(
        "Was ist für Neu-Donnerschwee geplant?",
        [{"id": 7, "title": "Bebauungsplan 58", "session_date": "2018-10-22",
          "summary": "Satzungsbeschluss", "outcome": "accepted"}],
        stand=stand)
    prompt = messages[0]["content"]
    assert "STAND DER AKTEN" in prompt
    # Und ohne Stand steht nichts davon drin.
    ohne, _ = qa._answer_messages("Was ist geplant?", [{"id": 7}])
    assert "STAND DER AKTEN" not in ohne[0]["content"]
