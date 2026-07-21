"""„Lotti erklärt's einfach" (RL-904): Auswahl, Persistenz, LLM-Parsing."""
from __future__ import annotations

import json
from types import SimpleNamespace

from council import simple_summary
from council.scraper import CouncilSession
from council.store import CouncilStore

LANG = "x" * 250  # substanzieller Beschlusstext (≥ 200 Zeichen)


def _store_with_decisions(tmp_path) -> CouncilStore:
    store = CouncilStore(tmp_path / "council.sqlite")
    store.save_session(CouncilSession(1, "Verkehrsausschuss", "2026-06-01", "17:00", "Fleiwa"))
    store.save_session(CouncilSession(2, "Kulturausschuss", "2026-07-01", "17:00", "PFL"))
    with store._conn:
        # Kandidat (neuere Sitzung zuerst erwartet).
        store._insert_decision(2, 0, "decision", None, "Ö 1", "Museumskonzept", LANG,
                               "angenommen", None, None, None, [], None, None, None)
        # Kandidat, ältere Sitzung.
        store._insert_decision(1, 0, "decision", None, "Ö 2", "Radweg", LANG,
                               "angenommen", None, None, None, [], None, None, None)
        # Kein Kandidat: zu kurzer Text, Subvote, ohne Beschlusstext.
        store._insert_decision(1, 1, "decision", None, "Ö 3", "Kurz", "Zu kurz.",
                               "angenommen", None, None, None, [], None, None, None)
        store._insert_decision(1, 2, "subvote", "Ö 2", None, "Änderungsantrag", LANG,
                               "abgelehnt", None, None, None, [], None, None, None)
        store._insert_decision(1, 3, "decision", None, "Ö 4", "Bericht", None,
                               "zur_kenntnis", None, None, None, [], None, None, None)
    return store


def test_selection_and_save(tmp_path):
    store = _store_with_decisions(tmp_path)
    pending = store.decisions_needing_simple_summary()
    assert [d["title"] for d in pending] == ["Museumskonzept", "Radweg"]
    assert pending[0]["committee"] == "Kulturausschuss"

    store.save_simple_summary(pending[0]["id"], "Die Stadt beschließt ein neues Museumskonzept.")
    pending2 = store.decisions_needing_simple_summary()
    assert [d["title"] for d in pending2] == ["Radweg"]
    # Kurzfassung kommt im Detail an (SELECT d.*).
    detail = store.get_decision(pending[0]["id"])
    assert detail["simple_summary"].startswith("Die Stadt beschließt")

    assert store.decisions_needing_simple_summary(limit=1) == pending2
    store.close()


def _fake_resp(payload: dict):
    msg = SimpleNamespace(content=json.dumps(payload, ensure_ascii=False))
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def test_generate_one_parses_and_guards(monkeypatch):
    decision = {"id": 1, "title": "Radweg", "beschluss": LANG,
                "committee": "Verkehrsausschuss", "session_date": "2026-06-01"}

    monkeypatch.setattr(simple_summary.llm, "chat_complete",
                        lambda **kw: _fake_resp({"einfach": "Die Stadt baut den Radweg aus."}))
    assert simple_summary.generate_one(decision) == "Die Stadt baut den Radweg aus."

    # Leere oder ausufernde Antworten → None (kein Speichern, späterer Retry).
    monkeypatch.setattr(simple_summary.llm, "chat_complete",
                        lambda **kw: _fake_resp({"einfach": ""}))
    assert simple_summary.generate_one(decision) is None
    monkeypatch.setattr(simple_summary.llm, "chat_complete",
                        lambda **kw: _fake_resp({"einfach": "z" * 800}))
    assert simple_summary.generate_one(decision) is None

    # LLM-Fehler dürfen den Lauf nicht reißen.
    def boom(**kw):
        raise RuntimeError("offline")
    monkeypatch.setattr(simple_summary.llm, "chat_complete", boom)
    assert simple_summary.generate_one(decision) is None
