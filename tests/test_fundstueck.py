"""Interessantheit + Fundstück des Tages (RL-U11): Auswahl, Persistenz, Parsing."""
from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

from council import fundstueck, interest
from council.scraper import CouncilSession
from council.store import CouncilStore

TEXT = "y" * 250


def _store(tmp_path) -> CouncilStore:
    store = CouncilStore(tmp_path / "council.sqlite")
    # Jahrestag: gleicher Kalendertag wie heute, vor 6 Jahren.
    today = date.today()
    anniv = today.replace(year=today.year - 6).isoformat()
    store.save_session(CouncilSession(1, "Rat", anniv, "17:00", "Ratssaal"))
    store.save_session(CouncilSession(2, "Kulturausschuss", "2024-03-05", "17:00", "PFL"))
    with store._conn:
        store._insert_decision(1, 0, "decision", None, "Ö 1", "Grüne Wellen fürs Rad", TEXT,
                               "angenommen", "einstimmig", None, None, [], None, None, None)
        store._insert_decision(2, 0, "decision", None, "Ö 1", "Museumskonzept", TEXT,
                               "angenommen", None, None, None, [], None, None, None)
        store._insert_decision(2, 1, "decision", None, "Ö 2", "Geschäftsordnung", TEXT,
                               "angenommen", None, None, None, [], None, None, None)
    return store


def test_interest_roundtrip_and_selection(tmp_path):
    store = _store(tmp_path)
    todo = store.decisions_needing_interest()
    assert len(todo) == 3

    ids = {d["title"]: d["id"] for d in todo}
    store.save_interest(ids["Grüne Wellen fürs Rad"], 82, "kurios und alltagsnah")
    store.save_interest(ids["Museumskonzept"], 70, "konkretes Projekt")
    store.save_interest(ids["Geschäftsordnung"], 10, "Formalie")
    assert store.decisions_needing_interest() == []
    # Clamping.
    store.save_interest(ids["Geschäftsordnung"], 150, None)
    assert store.get_decision(ids["Geschäftsordnung"])["interest"] == 100
    store.close()


def test_pick_prefers_anniversary_then_archive(tmp_path):
    store = _store(tmp_path)
    ids = {d["title"]: d["id"] for d in store.decisions_needing_interest()}
    store.save_interest(ids["Grüne Wellen fürs Rad"], 60, "")
    store.save_interest(ids["Museumskonzept"], 90, "")
    store.save_interest(ids["Geschäftsordnung"], 10, "")

    picked = fundstueck.pick_candidate(store, date.today())
    assert picked is not None
    decision, years = picked
    # Jahrestag schlägt den höheren Archiv-Score.
    assert decision["title"] == "Grüne Wellen fürs Rad" and years == 6

    # Ist der Jahrestags-Fund kürzlich verwendet, fällt die Wahl aufs Archiv.
    store.save_fundstueck(date.today().isoformat(), decision["id"], "Heute vor 6 Jahren", "s")
    picked2 = fundstueck.pick_candidate(store, date.today())
    assert picked2 is not None and picked2[0]["title"] == "Museumskonzept" and picked2[1] == 0
    store.close()


def test_fundstueck_persistence_and_lookup(tmp_path):
    store = _store(tmp_path)
    ids = {d["title"]: d["id"] for d in store.decisions_needing_interest()}
    store.save_fundstueck("2026-07-22", ids["Museumskonzept"], "Aus dem Archiv", "Der Rat …")
    f = store.get_fundstueck("2026-07-22")
    assert f["story"] == "Der Rat …" and f["title"] == "Museumskonzept"
    assert f["committee"] == "Kulturausschuss"
    assert store.get_fundstueck("2026-07-23") is None
    assert store.fundstueck_days_present(["2026-07-22", "2026-07-23"]) == {"2026-07-22"}
    assert ids["Museumskonzept"] in store.recent_fundstueck_decision_ids(10_000)
    # Upsert überschreibt.
    store.save_fundstueck("2026-07-22", ids["Museumskonzept"], "Aus dem Archiv", "Neu.")
    assert store.get_fundstueck("2026-07-22")["story"] == "Neu."
    store.close()


def _fake_resp(payload: dict):
    msg = SimpleNamespace(content=json.dumps(payload, ensure_ascii=False))
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def test_rate_batch_filters_hallucinated_ids(monkeypatch):
    decisions = [
        {"id": 1, "title": "A", "beschluss": TEXT, "committee": "Rat",
         "session_date": "2024-01-01", "outcome": "angenommen"},
        {"id": 2, "title": "B", "beschluss": TEXT, "committee": "Rat",
         "session_date": "2024-01-01", "outcome": "angenommen"},
    ]
    payload = {"ratings": [
        {"id": 1, "score": 77, "grund": "gut"},
        {"id": 999, "score": 50, "grund": "halluziniert"},
        {"id": 2, "score": 130, "grund": "out of range"},
    ]}
    monkeypatch.setattr(interest.llm, "chat_complete", lambda **kw: _fake_resp(payload))
    assert interest.rate_batch(decisions) == [(1, 77, "gut")]


def test_write_story_guards(monkeypatch):
    decision = {"id": 1, "title": "Grüne Wellen", "beschluss": TEXT, "committee": "Rat",
                "session_date": "2020-07-22", "outcome": "angenommen", "interest_reason": ""}
    monkeypatch.setattr(fundstueck.llm, "chat_complete",
                        lambda **kw: _fake_resp({"story": "Der Rat beschloss 2020, grüne Wellen fürs Rad zu testen."}))
    assert fundstueck.write_story(decision).startswith("Der Rat beschloss 2020")
    monkeypatch.setattr(fundstueck.llm, "chat_complete",
                        lambda **kw: _fake_resp({"story": "x" * 300}))
    assert fundstueck.write_story(decision) is None


def test_kicker():
    assert fundstueck.kicker_for(0) == "Aus dem Archiv"
    assert fundstueck.kicker_for(1) == "Heute vor einem Jahr"
    assert fundstueck.kicker_for(6) == "Heute vor 6 Jahren"
