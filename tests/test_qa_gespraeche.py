"""„Meine Gespräche" (5a/I-04 + Design 6a): Einwilligung, Speichern, Löschen.

Store-Logik direkt; die API-Verdrahtung deckt test_backend_api-Infrastruktur —
hier zählt: ohne Einwilligung wird nichts gespeichert, Gespräche sind strikt
ans Konto gebunden, Löschen räumt die Turns mit ab.
"""
from kern.store import Store


def _user(store, email="a@test.de"):
    return store.create_web_user(email, "hash")


def test_einwilligung_startet_ungefragt(tmp_path):
    store = Store(tmp_path / "nwz.sqlite")
    uid = _user(store)
    assert store.get_qa_speichern(uid) is None      # 6a①: Erstnutzungs-Frage fällig
    store.set_qa_speichern(uid, True)
    assert store.get_qa_speichern(uid) == 1
    store.set_qa_speichern(uid, False)
    assert store.get_qa_speichern(uid) == 0         # bewusst aus ≠ nie gefragt
    store.close()


def test_gespraech_lebenslauf(tmp_path):
    store = Store(tmp_path / "nwz.sqlite")
    uid = _user(store)
    gid = store.qa_gespraech_start(uid, "Wie ist der Stand bei der Cäcilienbrücke?")
    assert store.qa_turn_speichern(gid, uid, "Wie ist der Stand?", "Gut [1].", '{"cited": [1]}')
    assert store.qa_turn_speichern(gid, uid, "Und was kostet das?", "Viel.", None)
    liste = store.qa_gespraeche(uid)
    assert len(liste) == 1 and liste[0]["n_turns"] == 2
    assert liste[0]["titel"].startswith("Wie ist der Stand")
    g = store.qa_gespraech(gid, uid)
    assert [t["frage"] for t in g["turns"]] == ["Wie ist der Stand?", "Und was kostet das?"]
    store.close()


def test_gespraeche_sind_ans_konto_gebunden(tmp_path):
    store = Store(tmp_path / "nwz.sqlite")
    a, b = _user(store, "a@test.de"), _user(store, "b@test.de")
    gid = store.qa_gespraech_start(a, "Thema A")
    # Fremder Turn, fremde Lese- und Löschversuche laufen ins Leere.
    assert not store.qa_turn_speichern(gid, b, "f", "a", None)
    assert store.qa_gespraech(gid, b) is None
    assert not store.qa_gespraech_loeschen(gid, b)
    assert store.qa_gespraech(gid, a) is not None
    store.close()


def test_loeschen_raeumt_turns_mit_ab(tmp_path):
    store = Store(tmp_path / "nwz.sqlite")
    uid = _user(store)
    g1 = store.qa_gespraech_start(uid, "Eins")
    g2 = store.qa_gespraech_start(uid, "Zwei")
    store.qa_turn_speichern(g1, uid, "f1", "a1", None)
    store.qa_turn_speichern(g2, uid, "f2", "a2", None)
    assert store.qa_gespraech_loeschen(g1, uid)
    assert store._conn.execute("SELECT COUNT(*) FROM qa_gespraech_turns").fetchone()[0] == 1
    assert store.qa_gespraeche_loeschen(uid) == 1   # räumt g2
    assert store._conn.execute("SELECT COUNT(*) FROM qa_gespraech_turns").fetchone()[0] == 0
    store.close()


def test_konto_loeschung_nimmt_gespraeche_mit(tmp_path):
    store = Store(tmp_path / "nwz.sqlite")
    uid = _user(store)
    gid = store.qa_gespraech_start(uid, "Bleibt nicht")
    store.qa_turn_speichern(gid, uid, "f", "a", None)
    store.delete_web_user(uid)
    assert store._conn.execute("SELECT COUNT(*) FROM qa_gespraeche").fetchone()[0] == 0
    assert store._conn.execute("SELECT COUNT(*) FROM qa_gespraech_turns").fetchone()[0] == 0
    store.close()


def test_umbenennen_nur_am_eigenen_gespraech(tmp_path):
    store = Store(tmp_path / "nwz.sqlite")
    a, b = _user(store, "a@t.de"), _user(store, "b@t.de")
    gid = store.qa_gespraech_start(a, "Was ist beim Fliegerhorst geplant?")
    vorher = store.qa_gespraech(gid, a)["updated"]
    assert store.qa_gespraech_umbenennen(gid, a, "  Fliegerhorst\n Quartier ")
    g = store.qa_gespraech(gid, a)
    assert g["titel"] == "Fliegerhorst Quartier"     # Whitespace kollabiert
    assert g["updated"] == vorher                    # Pflege sortiert die Liste nicht um
    assert not store.qa_gespraech_umbenennen(gid, b, "Gekapert")   # fremdes Konto
    assert not store.qa_gespraech_umbenennen(gid, a, "   ")        # leer nach Trim
    assert store.qa_gespraech(gid, a)["titel"] == "Fliegerhorst Quartier"
    store.close()


def test_share_extras_und_alte_zeilen(tmp_path):
    """Geteilte Antworten tragen die Bausteine neben den Beschlüssen. Vor dem
    Nachtrag angelegte Zeilen haben keine extras-Spalte — die Migration ergänzt
    sie, und ihre Snapshots liefern dann leere Listen statt zu krachen."""
    pfad = tmp_path / "nwz.sqlite"
    store = Store(pfad)
    uid = _user(store)
    token = store.qa_share_anlegen(
        uid, "Frage?", "Antwort [5].", [{"id": 5, "title": "T"}],
        {"debatten": [{"sprecher": "Wenzel", "auszug": "Warnte."}],
         "presse": [], "anlagen": [], "parteien": [{"partei": "SPD"}]})
    share = store.qa_share_get(token)
    assert share["debatten"][0]["sprecher"] == "Wenzel"
    assert share["parteien"][0]["partei"] == "SPD"
    assert share["presse"] == [] and share["anlagen"] == []

    # Zeile aus der Zeit vor dem Nachtrag: extras ist NULL.
    with store._conn:
        store._conn.execute("UPDATE qa_shares SET extras = NULL WHERE token = ?", (token,))
    alt = store.qa_share_get(token)
    assert alt["antwort"] == "Antwort [5]." and alt["debatten"] == []
    store.close()

    # Alte Datei ohne die Spalte: Öffnen migriert, Lesen bleibt möglich.
    import sqlite3
    conn = sqlite3.connect(pfad)
    conn.executescript(
        "ALTER TABLE qa_shares RENAME TO qa_shares_alt;"
        "CREATE TABLE qa_shares (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL,"
        " frage TEXT NOT NULL, antwort TEXT NOT NULL, quellen TEXT, created TEXT NOT NULL);"
        "INSERT INTO qa_shares SELECT token, user_id, frage, antwort, quellen, created"
        " FROM qa_shares_alt;"
        "DROP TABLE qa_shares_alt;")
    conn.commit()
    conn.close()
    store = Store(pfad)
    assert "extras" in {r[1] for r in store._conn.execute("PRAGMA table_info(qa_shares)")}
    assert store.qa_share_get(token)["debatten"] == []
    store.close()
