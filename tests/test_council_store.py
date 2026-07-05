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
    assert {"policy_field", "policy_tags", "summary", "importance"} <= cols
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


def test_dedup_keys():
    from council.store import _dedup_keys

    def collide(a, b):
        return bool(set(a) & set(b))

    # Same base Vorlage across committees/revisions collapses ("22/0348" == "22/0348/1").
    assert collide(_dedup_keys("Ausfallbürgschaft Klinikum lang", "22/0348", 1),
                   _dedup_keys("Ausfallbürgschaft Klinikum kurz", "22/0348/1", 2))
    # Same Vorlage but a title spelling variant still collapses (via the Vorlage key).
    assert collide(_dedup_keys("VWG Förderantrags lang genug", "23/0587", 5),
                   _dedup_keys("VWG Förderantrages lang genug", "23/0587", 6))
    # Recurring series: different Vorlage, identical wording collapses (via the title key).
    assert collide(_dedup_keys("Überplanmäßige Bewilligung Teilhaushalt zehn", "20/1", 1),
                   _dedup_keys("Überplanmäßige Bewilligung Teilhaushalt zehn", "21/2", 2))
    # Genuinely distinct decisions do not collapse.
    assert not collide(_dedup_keys("Radweg Nadorster Straße Ausbau", "20/1", 1),
                       _dedup_keys("Kita Neubau Kreyenbrück Planung", "21/2", 2))
    # Tiny titles without a Vorlage fall back to the id (never merge distinct decisions).
    assert not collide(_dedup_keys("T10", None, 10), _dedup_keys("T11", None, 11))


def test_decisions_fts(tmp_path):
    store = CouncilStore(_old_db(tmp_path / "old.sqlite"))
    for i, (t, b) in enumerate([("Radweg Nadorster Straße", "Ausbau eines Radwegs beschlossen"),
                                ("Haushaltssatzung 2024", "Der Haushalt wird beschlossen")], 50):
        store._conn.execute(
            "INSERT INTO council_decisions(id,ksinr,position,kind,item_number,title,beschluss,outcome) "
            "VALUES (?,1,0,'decision','1',?,?,'angenommen')", (i, t, b))
    store._conn.commit()
    store.rebuild_fts()
    assert store.search_decisions_fts("radweg")[0][0] == 50
    assert store.search_decisions_fts("nadorster strasse")[0][0] == 50  # ß → ss folding
    assert store.search_decisions_fts("haushalt")[0][0] == 51
    assert store.search_decisions_fts("zz") == []  # terms < 3 chars dropped


def test_entities(tmp_path):
    store = CouncilStore(_old_db(tmp_path / "old.sqlite"))  # seeds a session ksinr=1
    for i, t in ((60, "Bebauungsplan Fliegerhorst Nord"), (61, "Altlastensanierung Fliegerhorst Süd")):
        store._conn.execute(
            "INSERT INTO council_decisions(id,ksinr,position,kind,item_number,title,beschluss,outcome,policy_field,amount_eur) "
            "VALUES (?,1,0,'decision','1',?,'b','angenommen','bauen_wohnen',1000000.0)", (i, t))
    store._conn.commit()
    store.save_entities([("fliegerhorst", "Fliegerhorst", "ort", 2)],
                        [("fliegerhorst", 60), ("fliegerhorst", 61)])
    assert [e["slug"] for e in store.list_entities()] == ["fliegerhorst"]
    assert [e["slug"] for e in store.entities_for_decision(60)] == ["fliegerhorst"]
    d = store.entity_detail("fliegerhorst")
    assert d and len(d["decisions"]) == 2 and d["money"] == 2_000_000
    assert d["fields"] == [{"field": "bauen_wohnen", "n": 2}]
    assert store.entity_detail("does-not-exist") is None


def test_money_by_field_and_trends_drivers(tmp_path):
    store = CouncilStore(_old_db(tmp_path / "old.sqlite"))  # session ksinr=1, date 2025-01-01
    seed = [
        # id, title, field, amount, vorlage_nr
        (70, "Neubau Schwimmbad", "kultur_sport", 5_000_000.0, "22/0100"),
        (71, "Neubau Schwimmbad", "kultur_sport", 5_000_000.0, "22/0100/1"),  # Rat-Zwilling → dedupliziert
        (72, "Sanierung Radweg", "verkehr", 2_000_000.0, "22/0200"),
        (73, "Jahresabschluss 2023 der Stadt", "finanzen", 999_000_000.0, "22/0300"),  # Buchhaltung → ausgeschlossen
    ]
    for i, title, field, amt, vnr in seed:
        store._conn.execute(
            "INSERT INTO council_decisions(id,ksinr,position,kind,item_number,title,beschluss,"
            "outcome,policy_field,amount_eur,vorlage_nr) "
            "VALUES (?,1,0,'decision','1',?,'b','angenommen',?,?,?)", (i, title, field, amt, vnr))
    store._conn.commit()

    # Buchhaltung raus, Zwilling dedupliziert → Schwimmbad einmal (5M), Radweg 2M.
    assert store.money_by_field() == [
        {"field": "kultur_sport", "total": 5_000_000, "n": 1},
        {"field": "verkehr", "total": 2_000_000, "n": 1},
    ]

    t = store.activity_trends()
    qi = t["quarters"].index("2025-Q1")
    # Geldbalken schließen den 999-Mio-Jahresabschluss aus (5M + 2M, Zwilling hier mitgezählt).
    assert t["money"][qi] == 12_000_000
    drv = t["money_drivers"][qi]
    assert drv and drv["title"] == "Neubau Schwimmbad" and drv["eur"] == 5_000_000


def test_entity_meta_description_and_geo(tmp_path):
    store = CouncilStore(_old_db(tmp_path / "old.sqlite"))  # session ksinr=1
    store._conn.execute(
        "INSERT INTO council_decisions(id,ksinr,position,kind,item_number,title,beschluss,outcome,policy_field) "
        "VALUES (80,1,0,'decision','1','Fliegerhorst Bebauungsplan','Beschluss','angenommen','bauen_wohnen')")
    store._conn.commit()
    store.save_entities([("fliegerhorst", "Fliegerhorst", "ort", 1)], [("fliegerhorst", 80)])

    # description: missing → set → read back via entity_detail; idempotent backfill list
    assert [e["slug"] for e in store.entities_without_description()] == ["fliegerhorst"]
    d = store.entity_detail("fliegerhorst")
    assert d["description"] is None and d["geo"] is None
    assert store.entity_decisions_brief("fliegerhorst")[0]["title"] == "Fliegerhorst Bebauungsplan"
    store.set_entity_descriptions([("fliegerhorst", "Ein ehemaliges Militärgelände im Norden.")])
    assert store.entities_without_description() == []
    assert store.entity_detail("fliegerhorst")["description"] == "Ein ehemaliges Militärgelände im Norden."

    # geo: place entity is geocode-pending → set → exposed (geojson parsed), description kept
    assert [e["slug"] for e in store.entities_to_geocode()] == ["fliegerhorst"]
    store.set_entity_geo("fliegerhorst", 53.17, 8.24, '{"type":"Point","coordinates":[8.24,53.17]}')
    assert store.entities_to_geocode() == []
    full = store.entity_detail("fliegerhorst")
    assert full["geo"]["lat"] == 53.17 and full["geo"]["geojson"]["type"] == "Point"
    assert full["description"] == "Ein ehemaliges Militärgelände im Norden."


def test_entity_money_dedup(tmp_path):
    store = CouncilStore(_old_db(tmp_path / "old.sqlite"))  # session ksinr=1
    seed = [
        (70, "Neubau Halle", "22/0100", 600000.0),
        (71, "Neubau Halle", "22/0100/1", 600000.0),  # Rat-Zwilling derselben Vorlage → einmal
        (72, "Sanierung Dach", "22/0200", 200000.0),
        (73, "Jahresabschluss 2023 der Hallen GmbH", "22/0300", 99000000.0),  # Buchhaltung → raus
    ]
    for i, title, vnr, amt in seed:
        store._conn.execute(
            "INSERT INTO council_decisions(id,ksinr,position,kind,item_number,title,beschluss,"
            "outcome,amount_eur,vorlage_nr) VALUES (?,1,0,'decision','1',?,'b','angenommen',?,?)",
            (i, title, amt, vnr))
    store._conn.commit()
    store.save_entities([("halle", "Halle", "ort", 4)], [("halle", i) for i in (70, 71, 72, 73)])
    # 600k (Zwilling einmal) + 200k = 800k; der 99-Mio-Jahresabschluss ist ausgeschlossen.
    assert store.entity_detail("halle")["money"] == 800000


def test_entity_obs_incremental(tmp_path):
    """Incremental NER: scan only new decisions, retain raw observations so an entity
    seen once now + again later still crosses the min_n threshold."""
    store = CouncilStore(_old_db(tmp_path / "old.sqlite"))  # session 1, decision id=1
    for i, title in [(2, "Beschluss zum Fliegerhorst"), (3, "Sanierung Rathaus")]:
        store._conn.execute(
            "INSERT INTO council_decisions(id,ksinr,position,kind,item_number,title,beschluss,outcome) "
            "VALUES (?,1,0,'decision','1',?,'b','angenommen')", (i, title))
    store._conn.commit()

    # First pass scans decisions 1 + 2.
    store.add_entity_observations(
        [(1, "fliegerhorst", "Fliegerhorst", "ort"),
         (2, "fliegerhorst", "Fliegerhorst", "ort"),
         (1, "rathaus", "Rathaus", "ort")],
        [1, 2])
    store.rebuild_entities_from_obs(min_n=2)
    assert store.scanned_entity_decision_ids() == {1, 2}
    slugs = {e["slug"]: e["n"] for e in store.list_entities()}
    assert slugs.get("fliegerhorst") == 2           # 2 decisions → published
    assert "rathaus" not in slugs                    # only 1 so far → below threshold

    # Incremental pass: decision 3 also mentions Rathaus → it now crosses min_n,
    # because the earlier observation (decision 1) was retained.
    store.add_entity_observations([(3, "rathaus", "Rathaus", "ort")], [3])
    store.rebuild_entities_from_obs(min_n=2)
    assert store.scanned_entity_decision_ids() == {1, 2, 3}
    assert {e["slug"]: e["n"] for e in store.list_entities()}.get("rathaus") == 2

    # --full reset clears observations + scan marks.
    store.reset_entity_obs()
    assert store.scanned_entity_decision_ids() == set()
    assert store.rebuild_entities_from_obs(min_n=2) == (0, 0)


def test_council_members_merge_by_slug(tmp_path):
    store = CouncilStore(_old_db(tmp_path / "old.sqlite"))  # session 1 = Rat, 2025-01-01
    store._conn.execute("INSERT INTO council_sessions VALUES (2,'Bauausschuss','2025-02-01','17:00','Rathaus','2025-02-01')")
    rows = [
        (1, "Dr. Max Mustermann", "SPD", "vorsitz"),   # title variant of the same person …
        (2, "Max Mustermann", "SPD", "mitglied"),       # … merges by slug → one entry, unique key
        (1, "Erika Musterfrau", "CDU", "mitglied"),
        (1, "Frau Schmidt", "", "verwaltung"),          # excluded role
    ]
    for ksinr, name, party, role in rows:
        store._conn.execute("INSERT INTO council_attendance(ksinr,name,party,role) VALUES (?,?,?,?)", (ksinr, name, party, role))
    store._conn.commit()

    members = store.list_members()
    slugs = [m["slug"] for m in members]
    assert "max-mustermann" in slugs and "erika-musterfrau" in slugs
    assert "frau-schmidt" not in slugs                       # verwaltung excluded
    assert len(set(slugs)) == len(slugs)                     # unique keys (the filter bug)
    mm = next(m for m in members if m["slug"] == "max-mustermann")
    assert mm["n"] == 2 and mm["committees"] == 2 and mm["party"] == "SPD"

    d = store.member_detail("max-mustermann")
    assert d and d["n_sessions"] == 2 and d["party"] == "SPD"
    chairs = {c["committee"]: c["chair"] for c in d["committees"]}
    assert chairs["Rat"] is True and chairs["Bauausschuss"] is False
    assert store.member_detail("gibt-es-nicht") is None


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
