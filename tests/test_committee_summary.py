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
        committee="Bauausschuss", session_date="2026-09-10", session_time="17:00",
        location="Rathaus", agenda_items=[_item()], session_url="http://x/si0057",
    )


def test_valid_json_builds_summary(monkeypatch):
    payload = json.dumps({"has_content": True, "items": [{"number": "Ö 5", "summary": "Neuer B-Plan."}]})
    monkeypatch.setattr(committee_summary.llm, "chat_complete", _llm_returning(payload))
    out = _summarize()
    assert out and "Bauausschuss" in out and "Neuer B-Plan." in out
    assert "10.09.2026" in out


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
