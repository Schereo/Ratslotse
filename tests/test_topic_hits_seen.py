"""Tests für den Gelesen-Status der Themen-Treffer (RL-903, nwz.sqlite)."""
from __future__ import annotations

from nwz.store import Store


def _setup(tmp_path):
    store = Store(tmp_path / "nwz.sqlite")
    topic = store.add_topic(7, "Radwege", "Ausbau von Radwegen")
    with store._conn:
        store._conn.executemany(
            "INSERT INTO council_topic_matches (topic_id, owner_id, decision_id, score) VALUES (?, 7, ?, ?)",
            [(topic.id, 101, 0.9), (topic.id, 102, 0.8), (topic.id, 103, 0.7)],
        )
    return store, topic


def test_unseen_counts_and_mark(tmp_path):
    store, topic = _setup(tmp_path)
    assert store.unseen_hit_counts(7) == {topic.id: 3}
    assert store.mark_topic_hits_seen(7, topic.id) == 3
    assert store.unseen_hit_counts(7) == {}
    # Idempotent: erneutes Markieren ändert nichts.
    assert store.mark_topic_hits_seen(7, topic.id) == 0


def test_new_match_counts_as_unseen_again(tmp_path):
    store, topic = _setup(tmp_path)
    store.mark_topic_hits_seen(7, topic.id)
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_topic_matches (topic_id, owner_id, decision_id, score) VALUES (?, 7, ?, ?)",
            (topic.id, 999, 0.95),
        )
    assert store.unseen_hit_counts(7) == {topic.id: 1}


def test_counts_are_per_owner(tmp_path):
    store, topic = _setup(tmp_path)
    # Fremder Owner sieht nichts von Topic 7.
    assert store.unseen_hit_counts(8) == {}
