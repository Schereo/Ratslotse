"""Zwei Fehler, die eine gewachsene Datenbank still falsch machen.

Beide sind am 01.09.2026 auf dev aufgetreten, beide ohne eine einzige
Fehlermeldung — `SELECT *` wirft nicht, wenn eine Spalte fehlt, und eine
leer danebengelegte Spalte sieht aus wie „noch nie gesetzt".

1. **Umbenennen ohne Migration.** Der Umbau auf englische Bezeichner machte
   aus `qa_speichern` im CODE `saves_conversations` — ohne die Spalte
   mitzunehmen. Der `ALTER TABLE`-Block prüfte auf den NEUEN Namen, fand ihn
   nicht und legte ihn LEER an. Danach stand die Einwilligung „Gespräche
   speichern" für alle auf „nie gefragt", obwohl der Wert in der alten Spalte
   weiter da war.
2. **Eine Spalte, die an einer FREMDEN Bedingung hängt.** `limits_unlocked`
   wurde nur angelegt, wenn `deep_limit` fehlte. Auf jeder Datenbank, die
   `deep_limit` schon hatte, entstand sie nie — und der Rate-Limiter griff
   stillschweigend auch bei Konten, die davon befreit sein sollten.
"""
from __future__ import annotations

import ast
import re
import sqlite3
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from kern.store import Store  # noqa: E402


def _alte_datenbank(pfad: Path, mit_leerer_neuer: bool = False) -> None:
    """Eine GEWACHSENE Datenbank im Stand vor dem Umbau.

    Nicht von Hand gebaut: erst das echte Schema anlegen lassen, dann die
    beiden Spalten auf ihre alten Namen zurückdrehen. Eine handgeschriebene
    Tabelle hätte ein anderes Schema als das echte — und der Test prüfte
    etwas anderes als das, was auf dem Server passiert.
    """
    Store(str(pfad))._conn.close()
    conn = sqlite3.connect(pfad)
    conn.execute("ALTER TABLE web_users RENAME COLUMN saves_conversations TO qa_speichern")
    conn.execute("ALTER TABLE web_users RENAME COLUMN limits_unlocked TO limits_frei")
    if mit_leerer_neuer:
        # Der Zustand, in dem dev nach dem Deploy stand.
        conn.execute("ALTER TABLE web_users ADD COLUMN saves_conversations INTEGER")
    conn.execute(
        "INSERT INTO web_users (email, password_hash, created_at, qa_speichern, limits_frei) "
        "VALUES ('pruef@example.org', 'x', datetime('now'), 1, 1)")
    conn.commit()
    conn.close()


def _spalten(pfad: Path) -> set[str]:
    with sqlite3.connect(pfad) as c:
        return {r[1] for r in c.execute("PRAGMA table_info(web_users)")}


def test_die_alten_spalten_ziehen_um(tmp_path):
    pfad = tmp_path / "ratslotse.sqlite"
    _alte_datenbank(pfad)
    Store(str(pfad))._conn.close()
    sp = _spalten(pfad)
    assert "saves_conversations" in sp and "qa_speichern" not in sp
    assert "limits_unlocked" in sp and "limits_frei" not in sp


def test_die_werte_ueberleben(tmp_path):
    """Das eigentlich Wichtige: Eine Einwilligung darf nicht verschwinden."""
    pfad = tmp_path / "ratslotse.sqlite"
    _alte_datenbank(pfad)
    Store(str(pfad))._conn.close()
    with sqlite3.connect(pfad) as c:
        an, frei = c.execute(
            "SELECT saves_conversations, limits_unlocked FROM web_users").fetchone()
    assert an == 1, "die Einwilligung ist verloren gegangen"
    assert frei == 1


def test_eine_leer_danebengelegte_spalte_wird_geheilt(tmp_path):
    """Der Zustand, in dem dev nach dem Deploy stand: beide Spalten da, die
    neue leer. Ohne Heilung benennt sich nichts mehr um — der Zielname ist ja
    belegt — und der Wert bleibt für immer unsichtbar."""
    pfad = tmp_path / "ratslotse.sqlite"
    _alte_datenbank(pfad, mit_leerer_neuer=True)
    with sqlite3.connect(pfad) as c:
        assert c.execute("SELECT saves_conversations FROM web_users").fetchone()[0] is None
    Store(str(pfad))._conn.close()
    sp = _spalten(pfad)
    assert "qa_speichern" not in sp, "die alte Spalte muss weg sein"
    with sqlite3.connect(pfad) as c:
        assert c.execute("SELECT saves_conversations FROM web_users").fetchone()[0] == 1


def test_zweimal_oeffnen_aendert_nichts(tmp_path):
    pfad = tmp_path / "ratslotse.sqlite"
    _alte_datenbank(pfad)
    Store(str(pfad))._conn.close()
    erst = _spalten(pfad)
    Store(str(pfad))._conn.close()
    assert _spalten(pfad) == erst


def test_jede_neue_spalte_prueft_sich_selbst():
    """Der zweite Fehler, als Regel: Ein ``ALTER TABLE … ADD COLUMN x`` darf
    nur unter einer Bedingung stehen, die ``x`` SELBST prüft. Hängt es an
    einer Nachbarspalte, entsteht es auf gewachsenen Datenbanken nie — und
    weil `SELECT *` nicht wirft, merkt das niemand."""
    baum = ast.parse((WURZEL / "kern" / "store.py").read_text())
    muster = re.compile(r"ALTER TABLE (\w+) ADD COLUMN (\w+)")
    fehler: list[str] = []

    def geh(knoten, bedingungen: frozenset[str]) -> None:
        """Steigt hinab und merkt sich ALLE umschließenden Bedingungen —
        die Prüfung steht meist eine Ebene über dem `ALTER TABLE`."""
        if isinstance(knoten, ast.Constant) and isinstance(knoten.value, str):
            m = muster.search(knoten.value)
            if m and m.group(2) not in bedingungen:
                fehler.append(f"{m.group(1)}.{m.group(2)} (Zeile {knoten.lineno}) "
                              f"steht unter {sorted(bedingungen) or 'keiner Prüfung'}")
            return
        for kind in ast.iter_child_nodes(knoten):
            neu = bedingungen
            if isinstance(knoten, ast.If) and kind in knoten.body:
                neu = bedingungen | {n.value for n in ast.walk(knoten.test)
                                     if isinstance(n, ast.Constant)
                                     and isinstance(n.value, str)}
            geh(kind, neu)

    geh(baum, frozenset())
    assert not fehler, ("Diese Spalten entstehen auf einer gewachsenen Datenbank "
                        "nie:\n  " + "\n  ".join(fehler))
