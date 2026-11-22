"""Ratsaufträge (`council/open_mandates.py`, Plan „Pläne“ § 3.5, Art 2).

Die Liste „Ratsauftrag ohne Folge“ ist NICHT ausgeliefert: Zwei Messungen
haben das Ziel von 90 % verfehlt (docs/plan-ziele-plaene.md, Phase 4b). Was
hier fest steht, ist der Teil ohne Modell, auf dem die Messung steht —
Aufträge erkennen, Kandidaten für die Folge suchen — und dass es weder einen
Endpunkt noch einen Schalter dafür gibt.
"""
from __future__ import annotations

import json
from pathlib import Path

from council import open_mandates
from kern import features

ROOT = Path(__file__).resolve().parents[1]


def _decision(number, date, outcome, text, title="Titel", committee="Rat", id_=1):
    return {"id": id_, "template_number": number, "session_date": date, "outcome": outcome,
            "official_text": text, "title": title, "committee": committee}


def test_auftrag_ist_der_angenommene_beschluss_ab_der_letzten_beratung():
    found = open_mandates.mandates([
        _decision("21/0037", "2021-06-10", "accepted", "Die Verwaltung wird beauftragt, eine Leitlinie zu entwickeln.", id_=1,
                  committee="Ausschuss"),
        _decision("21/0037/1", "2021-06-28", "accepted", "Die  Verwaltung wird\nbeauftragt, eine Leitlinie zu entwickeln.", id_=2),
        _decision("22/0001", "2022-01-10", "rejected", "Die Verwaltung wird beauftragt, etwas vorzulegen."),   # abgelehnt
        _decision("22/0002", "2022-01-10", "accepted", "Der Rat nimmt den Bericht zur Kenntnis."),            # kein Auftrag
    ])
    assert [(m["stem"], m["decision_id"], m["since"]) for m in found] == [("21/0037", 2, "2021-06-28")]
    assert found[0]["quote"].startswith("Verwaltung wird beauftragt, eine Leitlinie")
    assert open_mandates.old_enough(found[0], "2022-01-01") and not open_mandates.old_enough(found[0], "2021-09-01")


def test_kandidaten_fuer_die_folge():
    mandate = {"stem": "18/0420", "since": "2018-06-25", "title": "Schulentwicklungsplan für die allgemeinbildenden Schulen - Beschluss"}
    agenda = [
        {"title": "Umsetzung der Empfehlungen des Gutachtens zur Schulentwicklung - Bericht", "date": "2019-12-03",
         "committee": "Schulausschuss", "template_number": "19/0942"},
        {"title": "Schulentwicklungsplan - Beschluss", "date": "2018-07-01", "committee": "Rat", "template_number": "18/0420/1"},  # eigene Vorlage
        {"title": "Schulentwicklung: früher Bericht", "date": "2018-01-10", "committee": "Schulausschuss", "template_number": "18/0001"},  # davor
        {"title": "Bebauungsplan 845 (Nadorster Straße)", "date": "2020-01-01", "committee": "Rat", "template_number": "20/0001"},
    ]
    got = open_mandates.follow_up_candidates(mandate, ["Schulentwicklungsplan"], agenda)
    assert [c["template_number"] for c in got] == ["19/0942"]   # „Schulentwicklungsplan“ findet „Schulentwicklung“
    assert open_mandates.title_words("Park-and-Ride-Konzept für Oldenburg (CDU-Fraktion vom 18.10.2019) - Beschluss") == [
        "Park-and-Ride-Konzept"]


def test_nicht_ausgeliefert():
    """Solange das Messziel verfehlt ist, gibt es weder Schalter noch Endpunkt noch eine eingecheckte Liste."""
    assert "offene-auftraege" not in features.FEATURES
    assert "/council/open-mandates" not in json.loads((ROOT / "api" / "openapi.json").read_text())["paths"]
    assert not (ROOT / "council" / "open_mandates.json").exists()
