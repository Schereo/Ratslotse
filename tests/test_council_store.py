"""Regression tests for CouncilStore migrations + topic classification.

The key case: opening a database whose ``council_decisions`` predates the topic
classification columns must migrate cleanly. A column-dependent index in the
static SCHEMA (run before the migration) broke this in production once.
"""
import json
import sqlite3

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


def test_party_analysis(tmp_path):
    store = CouncilStore(_old_db(tmp_path / "old.sqlite"))
    motions = [
        (["Bündnis 90/Die Grünen"], "verkehr", "angenommen", 0, 0),
        (["Bündnis 90/DIE GRÜNEN", "SPD"], "klima_umwelt", "angenommen", 2, 1),
        (["CDU"], "finanzen", "abgelehnt", 5, 0),
        (["Verwaltung"], "finanzen", "angenommen", 0, 0),  # non-party → ignored
    ]
    for i, (fac, field, oc, g, e) in enumerate(motions, start=10):
        store._conn.execute(
            "INSERT INTO council_decisions "
            "(ksinr,position,kind,item_number,title,beschluss,outcome,gegenstimmen,enthaltungen,factions,policy_field) "
            "VALUES (1,?,'decision',?,?,?,?,?,?,?,?)",
            (i, str(i), "T", "B", oc, g, e, json.dumps(fac), field),
        )
    store._conn.commit()

    a = store.party_analysis()
    assert a["coverage"]["with_factions"] == 3  # the Verwaltung-only motion is excluded
    # The two Grünen spellings collapse to one party.
    gruene = next(s for s in a["success_rates"] if s["party"] == "Grüne")
    assert gruene["motions"] == 2 and gruene["angenommen"] == 2 and gruene["rate"] == 1.0
    assert a["topic_matrix"]["matrix"]["Grüne"]["verkehr"] == 1
    assert {"a": "Grüne", "b": "SPD", "count": 1} in a["alliances"]


def test_goal_links(tmp_path):
    store = CouncilStore(_old_db(tmp_path / "old.sqlite"))
    store._conn.execute(
        "INSERT INTO council_decisions (id,ksinr,position,kind,item_number,title,beschluss,outcome,policy_field) "
        "VALUES (20,1,0,'decision','1','Photovoltaik Schuldach','Solaranlage aufs Dach','angenommen','klima_umwelt')"
    )
    store._conn.commit()

    cands = store.get_goal_candidates(["photovoltaik", "solar"])
    assert any(c["id"] == 20 for c in cands)

    store.save_goal_links("klima_2035", {20: {"relevant": True, "stance": "voran", "grund": "Solar."}})
    assert store.goal_summary()["klima_2035"] == {"voran": 1, "bremst": 0, "neutral": 0, "total": 1}
    det = store.goal_detail("klima_2035")
    assert len(det) == 1 and det[0]["stance"] == "voran" and det[0]["title"].startswith("Photovoltaik")

    # Incremental cron: a decision already linked to the goal is excluded.
    assert all(c["id"] != 20 for c in store.get_goal_candidates(["photovoltaik"], exclude_goal="klima_2035"))

    store.clear_goal_links("klima_2035")
    assert store.goal_summary() == {}


def test_qa_keywords_and_fetch(tmp_path):
    from council.qa import extract_keywords
    assert "radverkehr" in extract_keywords("Was wurde zum Radverkehr beschlossen?")
    kw = extract_keywords("Welche Photovoltaik-Projekte gibt es?")
    assert "photovoltaik" in kw  # hyphenated compound is split
    assert "welche" not in kw    # stopword dropped

    store = CouncilStore(_old_db(tmp_path / "old.sqlite"))
    store._conn.execute(
        "INSERT INTO council_decisions (id,ksinr,position,kind,item_number,title,beschluss,outcome) "
        "VALUES (30,1,0,'decision','1','A','b','angenommen')"
    )
    store._conn.commit()
    got = store.get_decisions_by_ids([30, 999])  # 999 missing → skipped, order preserved
    assert len(got) == 1 and got[0]["id"] == 30


def test_similar_neighbours(tmp_path):
    store = CouncilStore(_old_db(tmp_path / "old.sqlite"))
    for i in (10, 11, 12):
        store._conn.execute(
            f"INSERT INTO council_decisions (id,ksinr,position,kind,item_number,title,beschluss,outcome) "
            f"VALUES ({i},1,0,'decision','1','T{i}','b','angenommen')"
        )
    store._conn.commit()

    store.set_similar([(10, 11, 0, 0.9), (10, 12, 1, 0.7), (11, 10, 0, 0.9)])
    sim = store.get_similar(10)
    assert [s["id"] for s in sim] == [11, 12]  # ordered by rank
    assert sim[0]["score"] == 0.9 and sim[0]["title"] == "T11"
    assert store.get_similar(12) == []  # no neighbours stored for 12
    # set_similar replaces everything
    store.set_similar([(10, 12, 0, 0.8)])
    assert [s["id"] for s in store.get_similar(10)] == [12]
    assert any(e["id"] == 10 and "T10" in e["text"] for e in store.decisions_for_embedding())


def test_embedding_vectors(tmp_path):
    store = CouncilStore(_old_db(tmp_path / "old.sqlite"))
    store.save_embeddings([(1, b"abcd"), (2, b"efgh")])
    rows = store.get_embeddings()
    assert len(rows) == 2 and bytes(rows[0]["vector"]) == b"abcd"
    store.save_embeddings([(3, b"xyz")])  # replaces everything
    assert [r["decision_id"] for r in store.get_embeddings()] == [3]


def test_party_filter(tmp_path):
    store = CouncilStore(_old_db(tmp_path / "old.sqlite"))
    store._conn.execute(
        "INSERT INTO council_decisions (id,ksinr,position,kind,item_number,title,beschluss,outcome,factions) "
        "VALUES (40,1,0,'decision','1','A','b','angenommen',?)", (json.dumps(["Bündnis 90/Die Grünen", "Fossil Free"]),))
    store._conn.execute(
        "INSERT INTO council_decisions (id,ksinr,position,kind,item_number,title,beschluss,outcome,factions) "
        "VALUES (41,1,0,'decision','2','B','b','angenommen',?)", (json.dumps(["CDU"]),))
    store._conn.commit()

    # _decision_row exposes normalised parties (Fossil Free filtered out).
    assert store.get_decision(40)["parties"] == ["Grüne"]
    assert store.decision_ids_for_party("Grüne") == [40]
    assert [x["id"] for x in store.search_decisions(party="Grüne")] == [40]
    assert store.count_decisions(party="CDU") == 1 and store.count_decisions(party="SPD") == 0


def test_news_links(tmp_path):
    store = CouncilStore(_old_db(tmp_path / "old.sqlite"))
    store.set_news_links([
        (1, 5, "abc", "Hauptbericht", "2025-01-01", 0.7),
        (1, 5, "def", "Kurzmeldung", "2025-02-01", 0.6),
    ])
    n = store.get_news_for_decision(1)
    assert len(n) == 2 and n[0]["score"] == 0.7 and n[0]["title"] == "Hauptbericht"  # by score
    assert store.decision_dates().get(1) == "2025-01-01"
    store.set_news_links([])  # replaces
    assert store.get_news_for_decision(1) == []


def test_qa_resolve_citations():
    from council.qa import resolve_citations
    answer = "Beschlossen [2030], ein Modell [3269, 3346] und ungültig [9999]."
    cleaned, cited = resolve_citations(answer, {2030, 3269, 3346})
    assert cited == [2030, 3269, 3346]   # multi-id bracket is parsed
    assert "[3269, 3346]" in cleaned
    assert "9999" not in cleaned          # invalid citation stripped from the text
