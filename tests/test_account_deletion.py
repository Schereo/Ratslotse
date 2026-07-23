"""Konto-Löschung (DSGVO Art. 17): Es darf nichts liegen bleiben.

`delete_web_user` räumte lange nur sechs Tabellen ab, während das Schema auf
sechzehn nutzerbezogene gewachsen war — Gerätetokens, Quiz-Antworten und
Themen-Treffer überlebten die Löschung. Diese Tests halten die Liste
vollständig: einer prüft sie gegen das Schema, einer löscht wirklich.
"""
from nwz.store import USER_OWNED_TABLES, Store


def _user_keyed_tables(conn) -> set[tuple[str, str]]:
    """Alle Tabellen des angelegten Schemas mit `owner_id`/`user_id`."""
    found = set()
    for (table,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ):
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for key in ("owner_id", "user_id"):
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
    store = Store(tmp_path / "nwz.sqlite")
    im_schema = _user_keyed_tables(store._conn)
    store.close()

    fehlend = im_schema - set(USER_OWNED_TABLES)
    assert not fehlend, (
        "Diese nutzerbezogenen Tabellen räumt delete_web_user nicht ab. "
        f"Bitte in nwz/store.py in USER_OWNED_TABLES ergänzen: {sorted(fehlend)}"
    )
    veraltet = set(USER_OWNED_TABLES) - im_schema
    assert not veraltet, f"Stehen in USER_OWNED_TABLES, aber nicht im Schema: {sorted(veraltet)}"


def test_delete_web_user_really_empties_every_table(tmp_path):
    """Nicht nur die Liste, auch das Löschen selbst: eine Zeile je Tabelle rein,
    Konto löschen, alles muss weg sein — und das fremde Konto unberührt."""
    store = Store(tmp_path / "nwz.sqlite")
    conn = store._conn
    with conn:
        for table, key in USER_OWNED_TABLES:
            _insert_dummy(conn, table, key, 1)
            _insert_dummy(conn, table, key, 2)  # zweites Konto als Kontrolle
        conn.execute(
            "INSERT INTO web_users (id, email, password_hash, role, status, created_at)"
            " VALUES (1, 'weg@test.de', 'x', 'user', 'active', '2026-01-01')")
        conn.execute(
            "INSERT INTO web_users (id, email, password_hash, role, status, created_at)"
            " VALUES (2, 'bleibt@test.de', 'x', 'user', 'active', '2026-01-01')")

    store.delete_web_user(1)

    for table, key in USER_OWNED_TABLES:
        rest = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {key} = 1").fetchone()[0]
        assert rest == 0, f"{table} trägt nach der Löschung noch Daten des Kontos"
        fremd = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {key} = 2").fetchone()[0]
        assert fremd == 1, f"{table}: fremdes Konto wurde mitgelöscht"

    assert conn.execute("SELECT COUNT(*) FROM web_users WHERE id = 1").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM web_users WHERE id = 2").fetchone()[0] == 1
    store.close()
