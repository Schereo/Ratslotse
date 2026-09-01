"""Die 66 Tabellennamen ziehen um — und zwar VOR dem Schema.

Der eine Fehler, gegen den diese Datei antritt: ``CREATE TABLE IF NOT EXISTS``
mit dem neuen Namen läuft, BEVOR die alte Tabelle umbenannt ist. Dann liegt die
neue Tabelle leer da, der Zielname ist belegt, die Umbenennung unterbleibt für
immer — und die Daten bleiben unsichtbar unter dem alten Namen. Ohne eine
einzige Fehlermeldung. Genau so ist am 01.09.2026 die Einwilligung in
``web_users`` verschwunden, nur eben spaltenweise (#917).
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from council import store as council_store  # noqa: E402
from kern import store as kern_store  # noqa: E402


def _alt_umbenennen(pfad: Path, karte: list[tuple[str, str]], nur: set[str] | None = None) -> None:
    """Eine GEWACHSENE Datenbank nachstellen: erst das echte Schema anlegen
    lassen, dann Tabellen auf ihre ALTEN Namen zurückdrehen."""
    conn = sqlite3.connect(pfad)
    vorhanden = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for alt, neu in karte:
        if neu in vorhanden and (nur is None or neu in nur):
            conn.execute(f"ALTER TABLE {neu} RENAME TO {alt}")
    conn.commit()
    conn.close()


@pytest.mark.parametrize("modul,Kl,probe,zeile", [
    (council_store, council_store.CouncilStore, "council_press",
     "INSERT INTO council_press (id, url, title, date, text, fetched_at) "
     "VALUES (1, 'https://example.org/p', 'Stadion', '2026-08-01', 'Neubau', '2026-08-01')"),
    (kern_store, kern_store.Store, "qa_conversations",
     "INSERT INTO qa_conversations (user_id, title, created, updated) "
     "VALUES (1, 'Frage', '2026-08-01', '2026-08-01')"),
])
def test_alte_tabellen_ziehen_um_und_behalten_ihre_zeilen(tmp_path, modul, Kl, probe, zeile):
    pfad = tmp_path / "db.sqlite"
    Kl(str(pfad))._conn.close()
    conn = sqlite3.connect(pfad); conn.execute(zeile); conn.commit(); conn.close()
    _alt_umbenennen(pfad, modul.TABELLEN_UMBENANNT)
    alt = {b: a for a, b in modul.TABELLEN_UMBENANNT}[probe]
    with sqlite3.connect(pfad) as c:
        assert c.execute(f"SELECT COUNT(*) FROM {alt}").fetchone()[0] == 1
    Kl(str(pfad))._conn.close()
    with sqlite3.connect(pfad) as c:
        namen = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert not any(a in namen for a, _ in modul.TABELLEN_UMBENANNT), "alte Namen übrig"
        assert c.execute(f"SELECT COUNT(*) FROM {probe}").fetchone()[0] == 1, "die Zeile ist verloren"


def test_eine_leer_danebengelegte_tabelle_wird_geheilt(tmp_path):
    """Der Zustand nach einem Start mit halbfertigem Code: beide da, neue leer."""
    pfad = tmp_path / "council.sqlite"
    council_store.CouncilStore(str(pfad))._conn.close()
    conn = sqlite3.connect(pfad)
    conn.execute("ALTER TABLE council_press RENAME TO council_presse")
    conn.execute("INSERT INTO council_presse (id, url, title, date, text, fetched_at) "
                 "VALUES (1, 'https://example.org/p', 'Stadion', '2026-08-01', 'x', '2026-08-01')")
    conn.execute("CREATE TABLE council_press (id INTEGER PRIMARY KEY)")      # leer daneben
    conn.commit(); conn.close()
    council_store.CouncilStore(str(pfad))._conn.close()
    with sqlite3.connect(pfad) as c:
        namen = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "council_presse" not in namen
        assert c.execute("SELECT title FROM council_press").fetchone()[0] == "Stadion"


def test_zwei_gefuellte_tabellen_bleiben_unangetastet(tmp_path, caplog):
    pfad = tmp_path / "council.sqlite"
    council_store.CouncilStore(str(pfad))._conn.close()
    conn = sqlite3.connect(pfad)
    conn.execute("ALTER TABLE council_press RENAME TO council_presse")
    conn.execute("INSERT INTO council_presse (id, url, title, date, text, fetched_at) "
                 "VALUES (1, 'u', 'alt', 'd', 'x', 'f')")
    conn.execute("CREATE TABLE council_press (id INTEGER PRIMARY KEY, title TEXT)")
    conn.execute("INSERT INTO council_press VALUES (9, 'neu')")
    conn.commit(); conn.close()
    with caplog.at_level("WARNING"):
        council_store.CouncilStore(str(pfad))._conn.close()
    with sqlite3.connect(pfad) as c:
        assert c.execute("SELECT COUNT(*) FROM council_presse").fetchone()[0] == 1
        assert c.execute("SELECT title FROM council_press WHERE id = 9").fetchone()[0] == "neu"
    assert "Zwei gefüllte Tabellen" in caplog.text


def test_fts_index_ueberlebt_den_umzug(tmp_path):
    pfad = tmp_path / "council.sqlite"
    council_store.CouncilStore(str(pfad))._conn.close()
    conn = sqlite3.connect(pfad)
    conn.execute("INSERT INTO council_press_fts(rowid, content) VALUES (7, 'Stadion Neubau Marschweg')")
    conn.commit(); conn.close()
    _alt_umbenennen(pfad, council_store.TABELLEN_UMBENANNT, nur={"council_press_fts"})
    council_store.CouncilStore(str(pfad))._conn.close()
    with sqlite3.connect(pfad) as c:
        namen = {r[0] for r in c.execute("SELECT name FROM sqlite_master")}
        assert "council_presse_fts" not in namen and "council_presse_fts_content" not in namen
        assert c.execute("SELECT rowid FROM council_press_fts WHERE council_press_fts MATCH 'marschweg'").fetchone()[0] == 7


def test_zweimal_oeffnen_aendert_nichts(tmp_path):
    pfad = tmp_path / "council.sqlite"
    council_store.CouncilStore(str(pfad))._conn.close()
    _alt_umbenennen(pfad, council_store.TABELLEN_UMBENANNT)
    council_store.CouncilStore(str(pfad))._conn.close()
    with sqlite3.connect(pfad) as c:
        erst = sorted(r[0] for r in c.execute("SELECT name FROM sqlite_master"))
    council_store.CouncilStore(str(pfad))._conn.close()
    with sqlite3.connect(pfad) as c:
        assert sorted(r[0] for r in c.execute("SELECT name FROM sqlite_master")) == erst


@pytest.mark.parametrize("modul", [council_store, kern_store])
def test_die_karte_ist_sauber(modul):
    """Kein selbstgleiches Paar, keine Dublette, kein Zielname, der zugleich ein
    alter ist — und kein kürzerer Name vor einem längeren, der ihn enthält."""
    karte = modul.TABELLEN_UMBENANNT
    assert all(a != b for a, b in karte)
    alt, neu = [a for a, _ in karte], [b for _, b in karte]
    assert len(set(alt)) == len(alt) and len(set(neu)) == len(neu)
    assert not set(alt) & set(neu)
    for i, (a, _) in enumerate(karte):
        assert not any(b.startswith(a) for b, _ in karte[i + 1:]), f"{a} frisst einen längeren"


@pytest.mark.parametrize("modul", [council_store, kern_store])
def test_das_schema_kennt_keinen_alten_namen_mehr(modul):
    """Sonst legte der Start die alte Tabelle leer wieder an."""
    quelle = Path(modul.__file__).read_text()
    angelegt = set(re.findall(r'CREATE (?:VIRTUAL )?TABLE(?: IF NOT EXISTS)? (\w+)', quelle))
    alte = {a for a, _ in modul.TABELLEN_UMBENANNT}
    assert not (angelegt & alte), f"Schema legt alte Namen an: {sorted(angelegt & alte)}"


def test_der_umzug_laeuft_vor_dem_schema():
    """Die Reihenfolge ist der ganze Punkt."""
    for modul in (council_store, kern_store):
        q = Path(modul.__file__).read_text()
        assert q.index("self._tabellen_umbenennen()") < q.index("self._conn.executescript(SCHEMA)"), modul.__name__
