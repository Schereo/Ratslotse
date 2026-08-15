"""Tests für den Gelesen-Status der Themen-Treffer (RL-903, nwz.sqlite)."""
from __future__ import annotations

from kern.store import Store


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


def test_geloeschtes_thema_zaehlt_nicht_mehr_mit(tmp_path):
    """DER Fehler hinter „der Zähler geht nicht weg" (25.07.2026).

    Ein gelöschtes Thema stand in keiner Liste mehr, seine Treffer zählten aber
    weiter — und weil der Seitenleisten-Zähler über ALLE Themen summiert, gab es
    keine Oberfläche mehr, über die man sie je als gesehen hätte markieren
    können. Die Zahl blieb für immer stehen.
    """
    store, topic = _setup(tmp_path)
    assert sum(store.unseen_hit_counts(7).values()) == 3

    store.delete_topic(topic.id)
    assert store.unseen_hit_counts(7) == {}


def test_loeschen_raeumt_die_treffer_wirklich_weg(tmp_path):
    """Nicht nur unsichtbar machen — die Zeilen müssen weg sein, sonst wächst
    die Datenbank mit Karteileichen und eine neu vergebene topic_id erbte sie."""
    store, topic = _setup(tmp_path)
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_agenda_matches (owner_id, ksinr, topic_id, item_number, matched_at) "
            "VALUES (7, 4711, ?, 'Ö 5', '2026-01-01')", (topic.id,))
    store.mark_topic_hits_seen(7, topic.id)

    store.delete_topic(topic.id)
    for tabelle in ("council_topic_matches", "topic_hits_seen", "council_agenda_matches"):
        n = store._conn.execute(f"SELECT COUNT(*) FROM {tabelle} WHERE topic_id = ?", (topic.id,)).fetchone()[0]
        assert n == 0, f"{tabelle} hat {n} Zeile(n) überlebt"


def test_purge_raeumt_altlasten_und_ist_idempotent(tmp_path):
    """Bestandsdaten: vor dem Fix gelöschte Themen haben Zeilen hinterlassen."""
    store, topic = _setup(tmp_path)
    # Löschen wie früher — nur die Themenzeile.
    with store._conn:
        store._conn.execute("DELETE FROM topics WHERE id = ?", (topic.id,))
    assert store._conn.execute("SELECT COUNT(*) FROM council_topic_matches").fetchone()[0] == 3

    assert store.purge_orphaned_topic_rows() == {"council_topic_matches": 3}
    assert store._conn.execute("SELECT COUNT(*) FROM council_topic_matches").fetchone()[0] == 0
    assert store.purge_orphaned_topic_rows() == {}


def test_purge_laesst_lebende_themen_in_ruhe(tmp_path):
    store, topic = _setup(tmp_path)
    assert store.purge_orphaned_topic_rows() == {}
    assert store.unseen_hit_counts(7) == {topic.id: 3}


def test_purge_stale_raeumt_auch_die_gelesen_marken(tmp_path):
    """Die zweite Hälfte von „warum sind hier überall 25 neu?" (Tim, 15.08.2026).

    Eine Neu-Extraktion vergibt neue Beschluss-IDs. Aufgeräumt wurden bislang
    nur die Treffer — die Gelesen-Marken blieben auf toten IDs liegen. Sie
    markierten damit nichts mehr und wuchsen unbegrenzt weiter.
    """
    store, topic = _setup(tmp_path)
    store.mark_topic_hits_seen(7, topic.id)
    assert store.unseen_hit_counts(7) == {}

    # 101 überlebt die Neu-Extraktion, 102 und 103 nicht.
    assert store.purge_stale_topic_matches({101}) == 2
    assert [r[0] for r in store._conn.execute(
        "SELECT decision_id FROM topic_hits_seen ORDER BY decision_id")] == [101]
    # Und was übrig ist, gilt weiter als gelesen.
    assert store.unseen_hit_counts(7) == {}


def test_gedeckelte_trefferliste_ist_als_solche_erkennbar(tmp_path):
    """Die Karte darf den Deckel nicht als Endzahl ausgeben: „40 Beschlüsse"
    sah bei „genau 40 gefunden" und „bei 40 abgeschnitten" identisch aus —
    und weil top-k 25 war, trug auf Prod JEDES Thema dieselbe 25."""
    store, topic = _setup(tmp_path)
    store.save_topic_decision_matches(topic.id, 7, [(201, 0.5), (202, 0.4)])
    assert store.topic_match_caps(7) == {topic.id: False}

    store.save_topic_decision_matches(topic.id, 7, [(201, 0.5)],
                                      gedeckelt=True, kandidaten=90)
    assert store.topic_match_caps(7) == {topic.id: True}
    # Mit dem Thema verschwindet auch die Meta-Zeile.
    store.delete_topic(topic.id)
    assert store.topic_match_caps(7) == {}


def test_gelesen_stand_ueberlebt_einen_reparaturlauf(tmp_path):
    """`--ohne-meldungen` heißt: Dieser Lauf ist keine Neuigkeit.

    Nach einer Neu-Extraktion tragen dieselben Beschlüsse neue IDs. Wer die
    Liste schon geöffnet hatte, darf sie nicht wieder als ungelesen vorfinden
    — sonst leuchtet nach jedem technischen Lauf bei jedem Thema wieder
    „n neu".
    """
    store, topic = _setup(tmp_path)
    ungesehen = store.add_topic(7, "Stadtbäume", "Baumschutz")
    store.save_topic_decision_matches(ungesehen.id, 7, [(301, 0.5)])
    store.mark_topic_hits_seen(7, topic.id)

    gesehen_vorher = store.topics_mit_gelesen_stand()
    assert gesehen_vorher == {topic.id}

    # Neu-Extraktion: alle IDs neu vergeben.
    store.purge_stale_topic_matches(set())
    store.save_topic_decision_matches(topic.id, 7, [(901, 0.9), (902, 0.8)])
    store.save_topic_decision_matches(ungesehen.id, 7, [(903, 0.7)])
    for tid in (topic.id, ungesehen.id):
        if tid in gesehen_vorher:
            store.mark_topic_hits_seen(7, tid)

    # Das angesehene Thema bleibt still, das nie geöffnete meldet ehrlich neu.
    assert store.unseen_hit_counts(7) == {ungesehen.id: 1}
