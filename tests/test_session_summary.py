"""Lottis Satz zur Sitzung, vom Modell (``council/session_summary.py``): was
das Modell zu sehen bekommt. Den Satz selbst misst ``eval/run_sitzung_satz.py``
am echten Modell."""
from __future__ import annotations

import json
from types import SimpleNamespace

from council import session_summary


def p(t, typ, wichtig=False, **mehr):
    return {"type": typ, "type_label": {"decision": "Entscheidung", "motion": "Antrag"}.get(typ),
            "short_title": t, "important": wichtig, "postponed": 0, **mehr}


ITEMS = {"Ö 1": p("Genehmigung der Tagesordnung", "formality"),
         "Ö 4": p("Mitteilungen", "announcement"),
         "Ö 5": p("Geschäftsordnung", "decision", True, important_reason="gilt für alle Gremien"),
         "Ö 6.1": p("Radweg Nadorster Straße", "motion", applicant="SPD-Fraktion", postponed=1)}


def test_formalien_bleiben_draussen_wichtiges_mit_grund_und_kurzfassung():
    stoff = session_summary.material("Rat", "2026-11-02", ITEMS, {"Ö 5": "Neue Regeln für Sitzungen."}, {})
    assert "Genehmigung der Tagesordnung" not in stoff and "Mitteilungen" not in stoff
    assert "Stand: vor dem Protokoll" in stoff and "Sitzung am 02.11.2026" in stoff
    assert "- Geschäftsordnung [Entscheidung · wichtig (gilt für alle Gremien)] — Neue Regeln für Sitzungen." in stoff
    assert "Antrag von SPD-Fraktion · stand schon einmal hier und wurde vertagt" in stoff


def test_nach_dem_protokoll_steht_das_ergebnis_in_worten_dabei():
    stoff = session_summary.material("Rat", "2026-11-02", ITEMS, {}, {"Ö 5": "accepted", "Ö 6.1": "no_decision"})
    assert "Stand: nach dem Protokoll" in stoff
    assert "Ergebnis: angenommen" in stoff and "Ergebnis: ohne Entscheidung" in stoff


def test_kaputte_antwort_ergibt_keinen_satz(monkeypatch):
    def antwort(text):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])
    monkeypatch.setattr(session_summary.llm, "chat_complete", lambda **k: antwort("kein json"))
    assert session_summary.generate("…") is None
    monkeypatch.setattr(session_summary.llm, "chat_complete",
                        lambda **k: antwort(json.dumps({"satz": " Im Mittelpunkt steht die Geschäftsordnung. "})))
    assert session_summary.generate("…") == "Im Mittelpunkt steht die Geschäftsordnung."
