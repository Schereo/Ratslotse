"""Tragweite-Score (RL-U16): Auswahl, Mischung in den Wichtig-Wert, Parsing."""
from __future__ import annotations

import json
from types import SimpleNamespace

from council import impact
from council.scraper import CouncilSession
from council.store import CouncilStore

TEXT = "z" * 250


def _store(tmp_path) -> CouncilStore:
    store = CouncilStore(tmp_path / "council.sqlite")
    store.save_session(CouncilSession(1, "Rat", "2026-06-01", "17:00", "Ratssaal"))
    with store._conn:
        store._insert_decision(1, 0, "decision", None, "Ö 1", "Haushaltssatzung 2026", TEXT,
                               "angenommen", None, None, None, [], None, None, None)
        store._insert_decision(1, 1, "decision", None, "Ö 2", "Berufung Mitglied", TEXT,
                               "angenommen", None, None, None, [], None, None, None)
    return store


def test_needing_and_clamp(tmp_path):
    store = _store(tmp_path)
    todo = store.decisions_needing_impact()
    assert {d["title"] for d in todo} == {"Haushaltssatzung 2026", "Berufung Mitglied"}
    store.save_impact(todo[0]["id"], 250, "x")
    assert store.get_decision(todo[0]["id"])["impact"] == 100
    assert len(store.decisions_needing_impact()) == 1
    store.close()


def test_backfill_blends_impact_fifty_fifty(tmp_path):
    store = _store(tmp_path)
    ids = {d["title"]: d["id"] for d in store.decisions_needing_impact()}
    # Ohne impact: reine Heuristik (die Berufung landet niedrig).
    store.backfill_importance()
    base = store.get_decision(ids["Berufung Mitglied"])["importance"]
    assert base < 100
    # Mit impact 100: Mischung = round((heuristik + 100) / 2), hebt den Wert.
    store.save_impact(ids["Berufung Mitglied"], 100, "test")
    store.backfill_importance()
    blended = store.get_decision(ids["Berufung Mitglied"])["importance"]
    assert blended == round((base + 100) / 2) and blended > base
    # Ohne impact bleibt die reine Heuristik stehen.
    other = store.get_decision(ids["Haushaltssatzung 2026"])
    assert other["impact"] is None and other["importance"] is not None
    store.close()


def _fake_resp(payload: dict):
    msg = SimpleNamespace(content=json.dumps(payload, ensure_ascii=False))
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def test_rate_batch_filters_and_signals(monkeypatch):
    decisions = [{"id": 7, "title": "Haushaltssatzung", "beschluss": TEXT, "committee": "Rat",
                  "session_date": "2026-01-01", "outcome": "angenommen", "kind": "decision",
                  "amount_eur": 1_000_000.0}]
    seen = {}
    def fake(**kw):
        seen["user"] = kw["messages"][1]["content"]
        return _fake_resp({"ratings": [{"id": 7, "score": 92, "grund": "Haushalt"},
                                       {"id": 99, "score": 10, "grund": "halluziniert"}]})
    monkeypatch.setattr(impact.llm, "chat_complete", fake)
    assert impact.rate_batch(decisions) == [(7, 92, "Haushalt")]
    # Struktur-Signale stehen im Prompt (Kalibrier-Anforderung aus RL-U16).
    assert "Gremium Rat" in seen["user"] and "1.000.000" in seen["user"]
