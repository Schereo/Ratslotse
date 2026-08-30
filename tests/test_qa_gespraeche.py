"""„Meine Gespräche" (5a/I-04 + Design 6a): Einwilligung, Speichern, Löschen.

Store-Logik direkt; die API-Verdrahtung deckt test_backend_api-Infrastruktur —
hier zählt: ohne Einwilligung wird nichts gespeichert, Gespräche sind strikt
ans Konto gebunden, Löschen räumt die Turns mit ab.
"""
import json
import sys
from pathlib import Path

from kern.store import Store

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))


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
    assert liste[0]["title"].startswith("Wie ist der Stand")
    g = store.qa_gespraech(gid, uid)
    assert [t["question"] for t in g["turns"]] == ["Wie ist der Stand?", "Und was kostet das?"]
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
    assert g["title"] == "Fliegerhorst Quartier"     # Whitespace kollabiert
    assert g["updated"] == vorher                    # Pflege sortiert die Liste nicht um
    assert not store.qa_gespraech_umbenennen(gid, b, "Gekapert")   # fremdes Konto
    assert not store.qa_gespraech_umbenennen(gid, a, "   ")        # leer nach Trim
    assert store.qa_gespraech(gid, a)["title"] == "Fliegerhorst Quartier"
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


def test_geteilter_inhalt_kann_moderiert_werden(tmp_path):
    store = Store(tmp_path / "nwz.sqlite")
    uid = _user(store)
    token = store.qa_share_anlegen(uid, "Frage?", "Antwort.", [])
    assert store.qa_share_owner_id(token) == uid
    assert store.qa_share_delete(token)
    assert store.qa_share_get(token) is None
    assert store.qa_share_owner_id(token) is None
    assert not store.qa_share_delete(token)
    store.close()


def test_snapshot_traegt_die_kondensierte_frage(tmp_path):
    """Tims Befund 21.08.2026: Beim Zurückwechseln auf den Fragen-Tab lud der
    Parteien-Baustein komplett neu.

    Ursache war der Snapshot: Gespeichert wurde nur die Frage, WIE SIE GESTELLT
    wurde („Und was kostet das?"). Bausteine, die nach der Antwort nachladen,
    schlüsseln aber auf die KONDENSIERTE Fassung — nach dem Wiederherstellen
    also ein anderer Schlüssel, damit ein Fehlgriff im Zwischenspeicher und ein
    neuer Lauf, der obendrein mit der kontextlosen Frage suchte."""
    from app.routers.council import AskBody, _turn_speichern

    store = Store(tmp_path / "nwz.sqlite")
    try:
        uid = _user(store)
        store.set_qa_speichern(uid, True)
        body = AskBody(question="Und was kostet das?", gespraech_id=None)
        gid = _turn_speichern(store, {"id": uid}, body,
                              "Was kostet die Sanierung der Cäcilienbrücke?",
                              "Rund 40 Mio. € [1].", [], [])
        assert gid is not None
        turn = store.qa_gespraech(gid, uid)["turns"][0]
        # Die Frage bleibt, wie sie gestellt wurde — im Verlauf soll stehen,
        # was der Mensch getippt hat.
        assert turn["question"] == "Und was kostet das?"
        # … die Suchfassung liegt daneben, damit der wiederhergestellte Turn
        # denselben Schlüssel trägt wie der live erzeugte.
        assert json.loads(turn["sources"])["kontext"] == \
            "Was kostet die Sanierung der Cäcilienbrücke?"
    finally:
        store.close()


def test_liste_blaettert_statt_bei_50_zu_enden(tmp_path):
    """Tims Befund 30.08.2026: Die Liste zeigte dauerhaft 50 Gespräche.

    Ursache war ein hartes `LIMIT 50` ohne Blättern — die älteren Gespräche
    lagen weiter in der DB, waren über die Liste aber nicht mehr erreichbar.
    Geprüft wird deshalb beides: dass eine Seite kurz bleibt UND dass man
    über die Seiten am Ende jedes einzelne Gespräch einsammelt.
    """
    store = Store(tmp_path / "nwz.sqlite")
    uid = _user(store)
    ids = [store.qa_gespraech_start(uid, f"Gespräch {i:03d}") for i in range(120)]

    assert store.qa_gespraeche_anzahl(uid) == 120
    erste = store.qa_gespraeche(uid, limit=30)
    assert len(erste) == 30
    assert erste[0]["title"] == "Gespräch 119"      # neueste zuerst

    gesammelt, offset = [], 0
    while True:
        seite = store.qa_gespraeche(uid, limit=30, offset=offset)
        if not seite:
            break
        gesammelt += seite
        offset += len(seite)
    assert [g["id"] for g in gesammelt] == list(reversed(ids))   # lückenlos

    # Die Konto-Karte will nur die Zahl — limit=0 liefert keine Zeilen.
    assert store.qa_gespraeche(uid, limit=0) == []
    store.close()


def test_gleiche_sekunde_blaettert_ohne_dubletten(tmp_path):
    """`updated` hat Sekundenauflösung: In einem Rutsch angelegte Gespräche
    tragen dieselbe Zeit. Ohne zweites Sortierkriterium wäre ihre Reihenfolge
    beliebig — über OFFSET erschiene dann eines doppelt, ein anderes nie."""
    store = Store(tmp_path / "nwz.sqlite")
    uid = _user(store)
    ids = {store.qa_gespraech_start(uid, f"Gleichzeitig {i}") for i in range(20)}
    gesehen = [g["id"] for off in (0, 5, 10, 15)
               for g in store.qa_gespraeche(uid, limit=5, offset=off)]
    assert len(gesehen) == len(set(gesehen)) == 20 and set(gesehen) == ids
    store.close()


def test_suche_findet_auch_ausserhalb_der_ersten_seite(tmp_path):
    """Gesucht wird in der DB, nicht in der geladenen Seite — sonst fände das
    Suchfeld genau die Gespräche nicht, für die es gebaut wurde."""
    store = Store(tmp_path / "nwz.sqlite")
    uid = _user(store)
    store.qa_gespraech_start(uid, "Cäcilienbrücke: Stand der Sanierung")
    for i in range(60):
        store.qa_gespraech_start(uid, f"Anderes Thema {i}")

    treffer = store.qa_gespraeche(uid, suche="cäcilien")
    assert [g["title"] for g in treffer] == ["Cäcilienbrücke: Stand der Sanierung"]
    assert store.qa_gespraeche_anzahl(uid, suche="cäcilien") == 1
    # Groß/klein egal — auch am Umlaut, den SQLites lower() nicht kennt.
    assert store.qa_gespraeche_anzahl(uid, suche="CÄCILIEN") == 1
    assert store.qa_gespraeche_anzahl(uid, suche="Anderes") == 60
    # Leeres Suchwort ist keine Suche.
    assert store.qa_gespraeche_anzahl(uid, suche="   ") == 61
    store.close()


def test_suchwort_mit_platzhaltern_bleibt_text(tmp_path):
    """`%` und `_` sind LIKE-Platzhalter — ungeschützt fände „%" alles."""
    store = Store(tmp_path / "nwz.sqlite")
    uid = _user(store)
    store.qa_gespraech_start(uid, "Grünanteil 100 % im Quartier")
    store.qa_gespraech_start(uid, "Radweg am Hafen")
    assert store.qa_gespraeche_anzahl(uid, suche="%") == 1
    assert store.qa_gespraeche_anzahl(uid, suche="100 %") == 1
    assert store.qa_gespraeche_anzahl(uid, suche="_") == 0
    store.close()
