"""Die Liste der Fragen ohne belegte Antwort (Teil A / PR 4).

Sie zeigt Nutzerfragen im Admin-Panel — deshalb gehört festgehalten, was NICHT
mitkommt. Und der Filter selbst muss stimmen: Eine Antwort mit Quellen darf
hier nie auftauchen, sonst liest man Erfolge als Fehlschläge.
"""
from __future__ import annotations

from datetime import date, timedelta

from kern.store import Store


def _turn(store: Store, frage: str, quellen: str | None, tage_her: int = 0) -> None:
    wann = (date.today() - timedelta(days=tage_her)).isoformat() + "T10:00:00"
    with store._conn:
        store._conn.execute(
            "INSERT OR IGNORE INTO qa_conversations (id, user_id, title, created, updated)"
            " VALUES (1, 7, 't', ?, ?)", (wann, wann))
        store._conn.execute(
            "INSERT INTO qa_conversation_turns (conversation_id, user_id, question, answer,"
            " sources, created) VALUES (1, 7, ?, 'Dazu liegt nichts vor.', ?, ?)",
            (frage, quellen, wann))


def test_nur_antworten_ohne_quelle(tmp_path):
    store = Store(tmp_path / "r.sqlite")
    _turn(store, "Was wurde zum Stadion beschlossen?", '{"cited": [1, 2]}')
    _turn(store, "Was ist mit dem Giftmüll am Fliegerhorst?", '{"cited": []}')
    _turn(store, "Wie viele Bäume wurden gefällt?", None)

    fragen = [s["question"] for s in store.sackgassen()]

    assert "Was wurde zum Stadion beschlossen?" not in fragen
    assert len(fragen) == 2
    store.close()


def test_kein_konto_und_keine_gespraechskennung(tmp_path):
    """Eine Liste mit Kennung neben der Frage wäre ein Leseprotokoll."""
    store = Store(tmp_path / "r.sqlite")
    _turn(store, "Eine Frage", '{"cited": []}')

    eintrag = store.sackgassen()[0]

    assert set(eintrag) == {"question", "answer", "created"}
    store.close()


def test_kaputtes_json_gilt_als_ohne_quelle(tmp_path):
    """Ein unlesbares `sources` heißt „nichts belegt", nicht „Absturz"."""
    store = Store(tmp_path / "r.sqlite")
    _turn(store, "Eine Frage", "{kein json")
    assert len(store.sackgassen()) == 1
    store.close()


def test_alte_faelle_fallen_aus_dem_fenster(tmp_path):
    store = Store(tmp_path / "r.sqlite")
    _turn(store, "Alt", '{"cited": []}', tage_her=90)
    _turn(store, "Neu", '{"cited": []}')
    assert [s["question"] for s in store.sackgassen(30)] == ["Neu"]
    store.close()


def test_liste_ist_gedeckelt(tmp_path):
    store = Store(tmp_path / "r.sqlite")
    for i in range(60):
        _turn(store, f"Frage {i}", '{"cited": []}')
    assert len(store.sackgassen(limit=40)) == 40
    store.close()
