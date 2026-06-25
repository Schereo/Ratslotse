"""Regression tests for CouncilStore migrations + topic classification.

The key case: opening a database whose ``council_decisions`` predates the topic
classification columns must migrate cleanly. A column-dependent index in the
static SCHEMA (run before the migration) broke this in production once.
"""
import sqlite3

import pytest

from council.store import CouncilStore

# council_decisions as it existed before the policy_field/policy_tags/summary columns.
_OLD_SCHEMA = """
CREATE TABLE council_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ksinr INTEGER NOT NULL, position INTEGER NOT NULL,
    kind TEXT NOT NULL DEFAULT 'decision', parent_item TEXT, item_number TEXT, title TEXT,
    beschluss TEXT, outcome TEXT, vote TEXT, gegenstimmen INTEGER, enthaltungen INTEGER,
    factions TEXT, vorlage_nr TEXT, kvonr INTEGER, raw_result TEXT);
CREATE INDEX idx_decisions_ksinr ON council_decisions(ksinr);
CREATE TABLE council_sessions (ksinr INTEGER PRIMARY KEY, committee TEXT, session_date TEXT,
    session_time TEXT, location TEXT, fetched_at TEXT NOT NULL DEFAULT '');
INSERT INTO council_sessions VALUES (1,'Rat','2025-01-01','18:00','Rathaus','2025-01-01');
INSERT INTO council_decisions (ksinr,position,kind,item_number,title,beschluss,outcome)
    VALUES (1,0,'decision','1','Alt-Beschluss','Bestand vor Migration','angenommen');
"""


def _old_db(path) -> str:
    conn = sqlite3.connect(path)
    conn.executescript(_OLD_SCHEMA)
    conn.commit()
    conn.close()
    return str(path)


def test_migrates_pre_classification_db(tmp_path):
    """Opening an old-schema DB must add the columns + index without crashing."""
    db = _old_db(tmp_path / "old.sqlite")
    store = CouncilStore(db)  # used to raise "no such column: policy_field"

    cols = {r[1] for r in store._conn.execute("PRAGMA table_info(council_decisions)").fetchall()}
    assert {"policy_field", "policy_tags", "summary"} <= cols
    idx = {r[1] for r in store._conn.execute("PRAGMA index_list(council_decisions)").fetchall()}
    assert "idx_decisions_field" in idx
    # The existing row survived and is simply unclassified.
    assert len(store.get_unclassified_decisions()) == 1


def test_migration_is_idempotent(tmp_path):
    db = _old_db(tmp_path / "old.sqlite")
    CouncilStore(db).close()
    CouncilStore(db).close()  # second open must not raise


def test_classification_roundtrip_and_filter(tmp_path):
    store = CouncilStore(_old_db(tmp_path / "old.sqlite"))
    [(did,)] = store._conn.execute("SELECT id FROM council_decisions").fetchall()

    store.set_classifications({did: {"field": "verkehr", "tags": ["Radverkehr"], "summary": "Ein Radweg."}})
    assert store.policy_field_stats() == [{"field": "verkehr", "count": 1}]
    rows = store.search_decisions(field="verkehr")
    assert len(rows) == 1 and rows[0]["policy_tags"] == ["Radverkehr"]
    assert store.search_decisions(field="klima_umwelt") == []
    assert store.count_decisions(field="verkehr") == 1

    store.reset_classifications()
    assert len(store.get_unclassified_decisions()) == 1
    assert store.policy_field_stats() == []
