"""Konto-Löschung (DSGVO Art. 17): Es darf nichts liegen bleiben.

`delete_web_user` räumte lange nur sechs Tabellen ab, während das Schema auf
sechzehn nutzerbezogene gewachsen war — Gerätetokens, Quiz-Antworten und
Themen-Treffer überlebten die Löschung. Diese Tests halten die Liste
vollständig: einer prüft sie gegen das Schema, einer löscht wirklich.
"""
import sqlite3

from kern.store import USER_OWNED_TABLES, Store


def _user_keyed_tables(conn) -> set[tuple[str, str]]:
    """Alle Tabellen mit `owner_id`, `user_id` oder `reporter_id`."""
    found = set()
    for (table,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ):
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for key in ("owner_id", "user_id", "reporter_id"):
            if key in cols:
                found.add((table, key))
    return found


def _insert_dummy(conn, table: str, key_col: str, user_id: int) -> None:
    """Eine Minimal-Zeile für `user_id` — füllt alle Pflichtspalten mit Dummys.

    Die Füllwerte hängen am `user_id`, damit die Zeilen zweier Konten nicht in
    dieselbe UNIQUE-Bedingung laufen (z. B. UNIQUE(topic_id, decision_id)).
    """
    info = list(conn.execute(f"PRAGMA table_info({table})"))
    pks = [r for r in info if r[5]]
    # Einspaltiger INTEGER-PK ist der rowid-Alias und vergibt sich selbst.
    rowid_alias = pks[0][1] if len(pks) == 1 and "INT" in (pks[0][2] or "").upper() else None

    names, values = [], []
    for _cid, name, ctype, notnull, default, _pk in info:
        if name == rowid_alias:
            continue
        if name == key_col:
            names.append(name)
            values.append(user_id)
        elif notnull and default is None:
            names.append(name)
            numeric = any(t in (ctype or "").upper() for t in ("INT", "REAL", "NUM"))
            values.append(user_id if numeric else f"x{user_id}")
    placeholders = ", ".join("?" * len(names))
    conn.execute(f"INSERT INTO {table} ({', '.join(names)}) VALUES ({placeholders})", values)


def test_delete_web_user_covers_every_user_table(tmp_path):
    """Wächst das Schema, muss `USER_OWNED_TABLES` mitwachsen.

    Ohne diesen Test bleiben bei einer Konto-Löschung stillschweigend Daten
    zurück, sobald jemand eine neue nutzerbezogene Tabelle anlegt.
    """
    from buergerportal.reports import PrivateReportStore

    database = tmp_path / "ratslotse.sqlite"
    store = Store(database)
    private_reports = PrivateReportStore(database)
    private_reports.close()
    im_schema = _user_keyed_tables(store._conn)
    store.close()

    fehlend = im_schema - set(USER_OWNED_TABLES)
    assert not fehlend, (
        "Diese nutzerbezogenen Tabellen räumt delete_web_user nicht ab. "
        f"Bitte in kern/store.py in USER_OWNED_TABLES ergänzen: {sorted(fehlend)}"
    )
    veraltet = set(USER_OWNED_TABLES) - im_schema
    assert not veraltet, f"Stehen in USER_OWNED_TABLES, aber nicht im Schema: {sorted(veraltet)}"


def test_delete_web_user_really_empties_every_table(tmp_path):
    """Nicht nur die Liste, auch das Löschen selbst: eine Zeile je Tabelle rein,
    Konto löschen, alles muss weg sein — und das fremde Konto unberührt."""
    from buergerportal.reports import DraftContent, PrivateReportStore

    database = tmp_path / "ratslotse.sqlite"
    store = Store(database)
    conn = store._conn
    with conn:
        conn.execute(
            "INSERT INTO web_users (id, email, password_hash, role, status, "
            "email_verified, created_at) VALUES "
            "(1, 'weg@test.de', 'x', 'user', 'active', 1, '2026-01-01')"
        )
        conn.execute(
            "INSERT INTO web_users (id, email, password_hash, role, status, "
            "email_verified, created_at) VALUES "
            "(2, 'bleibt@test.de', 'x', 'user', 'active', 1, '2026-01-01')"
        )
    private_reports = PrivateReportStore(database)
    for owner in (1, 2):
        report_id = private_reports.create_draft(
            reporter_id=owner,
            content=DraftContent(
                text=f"Fiktiver Entwurf {owner}",
                category="other",
                scope_kind="citywide",
                observed_on="2026-01-01",
            ),
        )
        private_reports.submit_owned_draft(
            report_id,
            reporter_id=owner,
            confirmed_text=f"Fiktive Beobachtung {owner}",
        )
    with conn:
        for table, key in USER_OWNED_TABLES:
            if table != "civic_reports":
                _insert_dummy(conn, table, key, 1)
                _insert_dummy(conn, table, key, 2)  # zweites Konto als Kontrolle

    store.delete_web_user(1)

    for table, key in USER_OWNED_TABLES:
        rest = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {key} = 1").fetchone()[0]
        assert rest == 0, f"{table} trägt nach der Löschung noch Daten des Kontos"
        fremd = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {key} = 2").fetchone()[0]
        assert fremd == 1, f"{table}: fremdes Konto wurde mitgelöscht"

    assert conn.execute("SELECT COUNT(*) FROM web_users WHERE id = 1").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM web_users WHERE id = 2").fetchone()[0] == 1
    observations = conn.execute(
        "SELECT text FROM civic_report_observations ORDER BY id"
    ).fetchall()
    assert [row[0] for row in observations] == ["Fiktive Beobachtung 2"]
    private_reports.close()
    store.close()


def test_feedback_roundtrip_and_unread(tmp_path):
    """Feedback ablegen, zählen, abhaken — die Grundlage des Admin-Tabs und
    des Zeichens in der Navigation."""
    store = Store(tmp_path / "ratslotse.sqlite")
    a = store.add_feedback(1, "a@test.de", "bug", "Knopf klemmt")
    b = store.add_feedback(2, "b@test.de", "feature", "Bitte Dunkelmodus")
    assert a and b and a != b
    assert store.count_unread_feedback() == 2

    # Neueste zuerst, damit Unerledigtes oben steht.
    alle = store.list_feedback()
    assert [f["id"] for f in alle] == [b, a]

    assert store.set_feedback_read(a, True) is True
    assert store.count_unread_feedback() == 1
    assert [f["id"] for f in store.list_feedback(only_unread=True)] == [b]

    # Umkehrbar — ein Fehlklick darf nichts kosten.
    assert store.set_feedback_read(a, False) is True
    assert store.count_unread_feedback() == 2

    # Unbekannte id meldet sich sauber ab, statt still nichts zu tun.
    assert store.set_feedback_read(9999, True) is False
    store.close()


# ---- Die zweite Datenbank ----

def test_council_db_kennt_ihre_nutzerbezogenen_tabellen(tmp_path):
    """Derselbe Wächter, aber für council.sqlite.

    Der Test oben scannt nur `ratslotse.sqlite` und konnte deshalb nicht sehen, dass
    in der zweiten Datenbank zwei Tabellen mit `owner_id` liegen. Zwischen den
    Datenbanken gibt es keine Fremdschlüssel — was hier nicht gelistet ist,
    überlebt die Konto-Löschung.
    """
    from council.store import COUNCIL_USER_OWNED_TABLES, CouncilStore

    cs = CouncilStore(tmp_path / "council.sqlite")
    im_schema = set()
    for (name,) in cs._conn.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        cols = {r[1] for r in cs._conn.execute(f"PRAGMA table_info({name})")}
        for spalte in ("owner_id", "user_id"):
            if spalte in cols:
                im_schema.add((name, spalte))
    cs.close()

    fehlend = im_schema - set(COUNCIL_USER_OWNED_TABLES)
    assert not fehlend, (
        "Diese Tabellen in council.sqlite hängen an einem Konto, werden aber bei "
        f"der Löschung nicht geräumt. In COUNCIL_USER_OWNED_TABLES ergänzen: {sorted(fehlend)}"
    )
    veraltet = set(COUNCIL_USER_OWNED_TABLES) - im_schema
    assert not veraltet, f"Gelistet, aber nicht im Schema: {sorted(veraltet)}"


def test_konto_loeschen_raeumt_auch_die_council_db(tmp_path):
    """Die Verhaltensspur „wem wurde welche Sitzung gemeldet" muss mit weg."""
    from council.store import CouncilStore

    cs = CouncilStore(tmp_path / "council.sqlite")
    for owner in (1, 2):
        cs._conn.execute(
            "INSERT INTO committee_notifications (ksinr, owner_id, agenda_hash, sent_at) "
            "VALUES (?, ?, 'h', '2026-07-01T10:00:00')", (100 + owner, owner))
        cs._conn.execute(
            "INSERT INTO session_followups_sent (ksinr, owner_id, sent_at) "
            "VALUES (?, ?, '2026-07-01T10:00:00')", (200 + owner, owner))
    cs._conn.commit()

    assert cs.delete_owner_data(1) == 2
    rest = [
        cs._conn.execute("SELECT owner_id FROM committee_notifications").fetchall(),
        cs._conn.execute("SELECT owner_id FROM session_followups_sent").fetchall(),
    ]
    cs.close()
    assert [r[0][0] for r in rest] == [2, 2], "nur die Zeilen von Konto 1 dürfen weg sein"


def test_zeitungsreste_werden_nur_leer_entfernt(tmp_path):
    """Die Tabellen-Hüllen aus der Zeitungs-Zeit (articles, editions …) wurden
    bei jedem Start neu angelegt. Sie fliegen jetzt raus — aber nur LEER:
    Wären wider Erwarten Daten drin, wäre Löschen der teurere Irrtum."""
    from kern.store import Store

    pfad = tmp_path / "alt.sqlite"
    # Bestands-Datenbank mit den alten Hüllen nachbauen.
    conn = sqlite3.connect(pfad)
    conn.executescript(
        "CREATE TABLE editions (catalog INTEGER PRIMARY KEY, title TEXT);"
        "CREATE TABLE articles (catalog INTEGER, refid TEXT, title TEXT);"
        "CREATE TABLE article_topic_matches (id INTEGER PRIMARY KEY, topic_id INTEGER);"
        "CREATE TABLE topic_classified_editions (owner_id INTEGER, topic_id INTEGER);")
    conn.commit()
    conn.close()

    store = Store(pfad)
    try:
        namen = {r[0] for r in store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert not (namen & {"articles", "editions", "article_topic_matches",
                             "topic_classified_editions"})
        # Und die Tabellen, die weiterleben, sind unberührt.
        assert "topics" in namen and "web_users" in namen and "topic_hits_seen" in namen
    finally:
        store.close()

    # Zweiter Fall: eine Hülle mit Inhalt bleibt stehen, statt Daten zu verlieren.
    pfad2 = tmp_path / "mit_inhalt.sqlite"
    conn = sqlite3.connect(pfad2)
    conn.executescript("CREATE TABLE articles (catalog INTEGER, title TEXT);")
    conn.execute("INSERT INTO articles VALUES (1, 'Alter Artikel')")
    conn.commit()
    conn.close()

    store = Store(pfad2)
    try:
        assert store._conn.execute(
            "SELECT count(*) FROM articles").fetchone()[0] == 1
    finally:
        store.close()


def test_neue_datenbank_legt_keine_zeitungstabellen_an(tmp_path):
    from kern.store import Store

    store = Store(tmp_path / "neu.sqlite")
    try:
        namen = {r[0] for r in store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
        assert not (namen & {"articles", "articles_fts", "editions",
                             "article_topic_matches", "topic_classified_editions"})
    finally:
        store.close()
