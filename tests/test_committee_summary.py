"""Tests für die Ausschuss-Zusammenfassung (LLM gemockt, kein Netz).

Kernfall: Das LLM liefert trotz response_format=json_object gelegentlich kein
valides JSON — das crashte den kompletten check_committees-Cron-Lauf (11× im
Juli 2026). summarize_agenda muss dann nach einem Retry ``None`` liefern
(Benachrichtigung ohne Zusammenfassung, KEIN Cache-Eintrag), nicht raisen.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from council import committee_summary
from council.scraper import AgendaItem


def _item(title: str = "Bebauungsplan 555: Aufstellung") -> AgendaItem:
    return AgendaItem(item_number="Ö 5", title=title, vorlage_nr="26/0123", is_public=True)


def _llm_returning(*contents: str | None):
    """Fake-chat_complete, das je Aufruf den nächsten content liefert (letzter wiederholt)."""
    calls = {"n": 0}

    def chat_complete(**kwargs):
        content = contents[min(calls["n"], len(contents) - 1)]
        calls["n"] += 1
        msg = SimpleNamespace(content=content)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=None)

    chat_complete.calls = calls
    return chat_complete


def _summarize():
    return committee_summary.summarize_agenda(
        committee="Bauausschuss", session_date="2026-09-10", agenda_items=[_item()],
    )


def test_valid_json_builds_summary(monkeypatch):
    payload = json.dumps({"has_content": True, "items": [{"number": "Ö 5", "summary": "Neuer B-Plan."}]})
    monkeypatch.setattr(committee_summary.llm, "chat_complete", _llm_returning(payload))
    out = _summarize()
    assert out == "• <b>Ö 5</b>: Neuer B-Plan."


def test_summary_traegt_keinen_kopf(monkeypatch):
    """Der Kopf gehört zur Sitzung, nicht in den Tagesordnungs-Cache: Sonst
    konserviert ein Cache-Treffer den Ort von damals — und war er leer, stand
    in der Mail eine Ortsmarke ohne Ort (Tims Befund 11.08.)."""
    payload = json.dumps({"has_content": True, "items": [{"number": "Ö 5", "summary": "Neuer B-Plan."}]})
    monkeypatch.setattr(committee_summary.llm, "chat_complete", _llm_returning(payload))
    out = _summarize()
    assert "📍" not in out and "📅" not in out and "Bauausschuss" not in out


def test_sitzungskopf_mit_und_ohne_ort():
    mit = committee_summary.sitzungskopf("Kulturausschuss", "2026-08-18", "17:00",
                                         "GLOBE Oldenburg, Beverbäker Wiesen 4")
    assert "<b>Kulturausschuss</b>" in mit
    assert "📅 18.08.2026  17:00 Uhr" in mit
    assert "📍 GLOBE Oldenburg, Beverbäker Wiesen 4" in mit
    # Ohne bekannten Ort bleibt die Ortsmarke weg statt leer dazustehen.
    ohne = committee_summary.sitzungskopf("Kulturausschuss", "2026-08-18", "17:00", "")
    assert "📍" not in ohne


def test_markdown_fenced_json_is_parsed(monkeypatch):
    payload = "```json\n" + json.dumps({"has_content": True, "items": [{"number": "Ö 5", "summary": "S."}]}) + "\n```"
    monkeypatch.setattr(committee_summary.llm, "chat_complete", _llm_returning(payload))
    out = _summarize()
    assert out and "S." in out


def test_garbage_retries_once_then_none(monkeypatch):
    fake = _llm_returning("Hier ist die Zusammenfassung: …", "immer noch kein JSON")
    monkeypatch.setattr(committee_summary.llm, "chat_complete", fake)
    assert _summarize() is None
    assert fake.calls["n"] == 2  # genau ein frischer Versuch


def test_none_content_does_not_crash(monkeypatch):
    monkeypatch.setattr(committee_summary.llm, "chat_complete", _llm_returning(None))
    assert _summarize() is None


def test_second_attempt_recovers(monkeypatch):
    good = json.dumps({"has_content": True, "items": [{"number": "Ö 5", "summary": "Doch noch."}]})
    fake = _llm_returning("kein json", good)
    monkeypatch.setattr(committee_summary.llm, "chat_complete", fake)
    out = _summarize()
    assert out and "Doch noch." in out
    assert fake.calls["n"] == 2


def test_json_list_counts_as_invalid(monkeypatch):
    monkeypatch.setattr(committee_summary.llm, "chat_complete", _llm_returning(json.dumps([1, 2])))
    assert _summarize() is None


def test_routine_only_still_empty_string(monkeypatch):
    # '' (nur Routine) bleibt von None (Fehler) unterscheidbar — '' ist cachebar.
    monkeypatch.setattr(committee_summary.llm, "chat_complete",
                        _llm_returning(json.dumps({"has_content": False, "items": []})))
    assert _summarize() == ""


# ---- Der Ort (Tims Befund 11.08.26) -----------------------------------------

def test_ort_kommt_aus_dem_raum_feld_nicht_aus_der_ueberschrift():
    """Die Sitzungsseite nennt den Ort NICHT in der Überschrift (die endet nach
    der Uhrzeit) — er steht im Feld „Raum". Die alte Heuristik las das letzte
    Stück der Überschrift und lieferte deshalb für jede Sitzung einen leeren
    Ort; in der Mail blieb eine Ortsmarke ohne Ort stehen."""
    from bs4 import BeautifulSoup
    from council.scraper import _extract_location

    seite = BeautifulSoup(
        "<h1>Kulturausschuss - 18.08.2026 - 17:00 Uhr</h1>"
        "<div class='smc-table-row'>"
        "<div class='smc-table-cell smc-cell-head siort_title'>Raum</div>"
        "<div class='smc-table-cell siort'>GLOBE Oldenburg, Beverbäker Wiesen 4, 26123 Oldenburg</div>"
        "</div>", "html.parser")
    assert _extract_location(seite) == "GLOBE Oldenburg, Beverbäker Wiesen 4, 26123 Oldenburg"

    # Doppelte Leerzeichen und ein hängendes Komma kommen im Bestand vor.
    mehrzeilig = BeautifulSoup(
        "<div class='siort'>Cäcilienschule Oldenburg, Haarenufer 11,\n  Aula</div>", "html.parser")
    assert _extract_location(mehrzeilig) == "Cäcilienschule Oldenburg, Haarenufer 11, Aula"

    # Keine Raum-Angabe → leer (der Aufrufer lässt die Ortszeile dann weg).
    assert _extract_location(BeautifulSoup("<h1>Rat - 01.06.2026</h1>", "html.parser")) == ""


def test_gecachter_altkopf_wird_abgeschnitten():
    """Bestands-Zusammenfassungen tragen den alten Kopf mit leerem Ort in sich.
    Ohne Schnitt stünde er in der Mail neben dem frischen — zweimal Gremium,
    einmal davon mit nackter Ortsmarke."""
    import importlib.util
    from pathlib import Path

    pfad = Path(__file__).resolve().parent.parent / "scripts" / "check_committees.py"
    spec = importlib.util.spec_from_file_location("check_committees_kopf", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)

    alt = ("<b>Kulturausschuss</b>\n📅 18.08.2026  17:00 Uhr\n📍 \n\n"
           "• <b>Ö 5</b>: Der GLOBE-Bericht wurde vorgestellt.")
    assert modul._ohne_altkopf(alt) == "• <b>Ö 5</b>: Der GLOBE-Bericht wurde vorgestellt."

    # Kopf mit Ort (ältere Sitzungen aus Protokollen) fliegt genauso raus.
    mit_ort = "<b>Rat</b>\n📅 01.06.2026  18:00 Uhr\n📍 Cäcilienschule\n\n• <b>Ö 3</b>: Haushalt."
    assert modul._ohne_altkopf(mit_ort) == "• <b>Ö 3</b>: Haushalt."

    # Neue Zusammenfassungen haben keinen Kopf — der Ausdruck trifft nichts.
    neu = "• <b>Ö 5</b>: Der Ausschuss berät über den GLOBE-Bericht."
    assert modul._ohne_altkopf(neu) == neu
    assert modul._ohne_altkopf(None) is None
