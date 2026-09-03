"""Der Umzug `nwz.sqlite` → `ratslotse.sqlite` und sein Stolperstein.

Die Datenbank hieß bis 08/2026 anders. Damit kein Deployment von Hand
umbenennen muss, zieht der Start die Datei selbst um. Der Umzug ist einmalig
und erkennt sich daran, dass die Zieldatei noch nicht da ist.

Genau diese Erkennung hatte eine Lücke: Eine **leere** Zieldatei zählte als
„schon umgezogen". Sie entsteht, sobald irgendetwas den neuen Pfad einmal
öffnet, ohne zu schreiben — und danach unterbleibt der Umzug für immer. Der
Start legte dann das Schema in der leeren Datei an, und die App käme mit
leeren Konten hoch, während die echten Daten unter dem alten Namen liegen.

Am 01.09.2026 stand auf Prod eine 0-Byte-`ratslotse.sqlite` neben einer
37-MB-`nwz.sqlite` mit 22 Konten. Der nächste Release nach `main` hätte
gereicht.
"""
from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import kern.store as store_mod  # noqa: E402
from kern.store import Store, _umzug_von_nwz  # noqa: E402


def _db_mit_inhalt(pfad: Path, email: str = "pruef@example.org") -> None:
    conn = sqlite3.connect(pfad)
    conn.execute("CREATE TABLE web_users (id INTEGER PRIMARY KEY, email TEXT)")
    conn.execute("INSERT INTO web_users (email) VALUES (?)", (email,))
    conn.commit()
    conn.close()


def test_umzug_benennt_die_alte_datei_um(tmp_path):
    """Der Normalfall, den es seit 08/2026 gibt."""
    alt, ziel = tmp_path / "nwz.sqlite", tmp_path / "ratslotse.sqlite"
    _db_mit_inhalt(alt)
    _umzug_von_nwz(ziel)
    assert ziel.exists() and not alt.exists()
    with sqlite3.connect(ziel) as c:
        assert c.execute("SELECT COUNT(*) FROM web_users").fetchone()[0] == 1
    _umzug_von_nwz(ziel)  # idempotent: ein zweiter Start ändert nichts


def test_umzug_checkt_echten_wal_vollstaendig_ein(tmp_path):
    """Ein nach einem Prozessabbruch verbliebener WAL landet vollständig im Ziel."""
    alt, ziel = tmp_path / "nwz.sqlite", tmp_path / "ratslotse.sqlite"
    skript = """
import os
import sqlite3
import sys

conn = sqlite3.connect(sys.argv[1])
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA wal_autocheckpoint=0")
conn.execute("CREATE TABLE web_users (id INTEGER PRIMARY KEY, email TEXT)")
conn.execute("INSERT INTO web_users (email) VALUES ('im-wal@example.org')")
conn.commit()
os._exit(0)
"""
    subprocess.run([sys.executable, "-c", skript, str(alt)], check=True)
    wal = tmp_path / "nwz.sqlite-wal"
    assert wal.exists() and wal.stat().st_size > 0, "die Fixture braucht echte WAL-Seiten"

    _umzug_von_nwz(ziel)

    assert ziel.exists() and not alt.exists()
    assert not wal.exists()
    with sqlite3.connect(ziel) as c:
        assert c.execute("SELECT email FROM web_users").fetchone()[0] == \
            "im-wal@example.org"


def test_offene_fremde_wal_verbindung_blockiert_umzug(tmp_path):
    """Auch eine untätige WAL-Verbindung muss den Dateiumzug verhindern."""
    alt, ziel = tmp_path / "nwz.sqlite", tmp_path / "ratslotse.sqlite"
    fremd = sqlite3.connect(alt)
    assert fremd.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    fremd.execute("CREATE TABLE web_users (id INTEGER PRIMARY KEY, email TEXT)")
    fremd.execute("INSERT INTO web_users (email) VALUES ('vorher@example.org')")
    fremd.commit()

    with pytest.raises(RuntimeError, match="Sicherer Datenbank-Umzug"):
        _umzug_von_nwz(ziel)

    assert alt.exists() and not ziel.exists()
    # Der fehlgeschlagene Versuch darf auch die weiterhin laufende Verbindung
    # nicht beschädigen. Ihr nächster Commit bleibt Teil des späteren Umzugs.
    fremd.execute("INSERT INTO web_users (email) VALUES ('nachher@example.org')")
    fremd.commit()
    fremd.close()

    _umzug_von_nwz(ziel)
    with sqlite3.connect(ziel) as connection:
        assert connection.execute(
            "SELECT email FROM web_users ORDER BY id"
        ).fetchall() == [("vorher@example.org",), ("nachher@example.org",)]


def test_eine_leere_zieldatei_blockiert_den_umzug_nicht(tmp_path):
    """Der Fehler vom 01.09.2026 — der eigentliche Grund für diese Datei."""
    alt, ziel = tmp_path / "nwz.sqlite", tmp_path / "ratslotse.sqlite"
    _db_mit_inhalt(alt)
    ziel.touch()                       # 0 Byte, wie auf Prod
    assert ziel.stat().st_size == 0
    _umzug_von_nwz(ziel)
    assert not alt.exists(), "die alte Datei muss umgezogen sein"
    with sqlite3.connect(ziel) as c:
        assert c.execute("SELECT COUNT(*) FROM web_users").fetchone()[0] == 1, \
            "die Konten müssen überlebt haben"


def test_zwei_gefuellte_datenbanken_brechen_fail_closed_ab(tmp_path):
    """Ein unentscheidbarer Bestand wird weder überschrieben noch still benutzt."""
    alt, ziel = tmp_path / "nwz.sqlite", tmp_path / "ratslotse.sqlite"
    _db_mit_inhalt(ziel, "ziel@example.org")
    _db_mit_inhalt(alt, "alt@example.org")
    with pytest.raises(RuntimeError, match="Sicherer Datenbank-Umzug"):
        _umzug_von_nwz(ziel)

    assert alt.exists() and ziel.exists(), "beide Datenbanken müssen unangetastet bleiben"
    with sqlite3.connect(ziel) as c:
        assert c.execute("SELECT email FROM web_users").fetchone()[0] == "ziel@example.org"
    with sqlite3.connect(alt) as c:
        assert c.execute("SELECT email FROM web_users").fetchone()[0] == "alt@example.org"


def test_ohne_alte_datei_passiert_nichts(tmp_path):
    """Frischer Checkout: Es gibt nichts umzuziehen, und eine leere Zieldatei
    darf trotzdem nicht gelöscht werden — sie ist dann die Datenbank."""
    ziel = tmp_path / "ratslotse.sqlite"
    ziel.touch()
    _umzug_von_nwz(ziel)
    assert ziel.exists()


def test_eine_leere_alte_datei_zieht_nicht_um(tmp_path):
    """Auf dev liegt seit dem Umzug eine 0-Byte-`nwz.sqlite`. Die darf die
    gefüllte Zieldatei niemals ersetzen."""
    alt, ziel = tmp_path / "nwz.sqlite", tmp_path / "ratslotse.sqlite"
    _db_mit_inhalt(ziel)
    alt.touch()
    _umzug_von_nwz(ziel)
    with sqlite3.connect(ziel) as c:
        assert c.execute("SELECT COUNT(*) FROM web_users").fetchone()[0] == 1


def test_spezialziel_beansprucht_keine_nwz_datei(tmp_path):
    """Der Legacy-Umzug gilt nur für den kanonischen neuen Dateinamen."""
    alt, spezialziel = tmp_path / "nwz.sqlite", tmp_path / "testkonto.sqlite"
    _db_mit_inhalt(alt)

    _umzug_von_nwz(spezialziel)

    assert alt.exists()
    assert not spezialziel.exists()


def test_nicht_leerer_verwaister_wal_bricht_ab(tmp_path):
    """Ohne alte Hauptdatei darf ein WAL nicht als bedeutungsloser Rest gelten."""
    ziel = tmp_path / "ratslotse.sqlite"
    wal = tmp_path / "nwz.sqlite-wal"
    wal.write_bytes(b"nicht eingecheckte Seiten")

    with pytest.raises(RuntimeError, match="Sicherer Datenbank-Umzug"):
        _umzug_von_nwz(ziel)

    assert wal.exists()
    assert not ziel.exists()


def test_gefuelltes_ziel_ignoriert_wal_neben_leerer_altdatei_nicht(tmp_path):
    """Auch nach vermeintlichem Umzug bleibt ein nichtleerer alter WAL ein Blocker."""
    alt, ziel = tmp_path / "nwz.sqlite", tmp_path / "ratslotse.sqlite"
    wal = tmp_path / "nwz.sqlite-wal"
    _db_mit_inhalt(ziel)
    alt.touch()
    wal.write_bytes(b"nicht eingecheckte Seiten")

    with pytest.raises(RuntimeError, match="Sicherer Datenbank-Umzug"):
        _umzug_von_nwz(ziel)

    assert alt.exists() and wal.exists() and ziel.exists()
    with sqlite3.connect(ziel) as c:
        assert c.execute("SELECT COUNT(*) FROM web_users").fetchone()[0] == 1


def test_rename_fehler_bricht_store_start_ab(tmp_path, monkeypatch):
    """Ein fehlgeschlagenes Rename darf nie eine leere Zieldatei öffnen."""
    alt, ziel = tmp_path / "nwz.sqlite", tmp_path / "ratslotse.sqlite"
    _db_mit_inhalt(alt)
    echtes_rename = Path.rename

    def rename_scheitert(self, target):
        if self == alt:
            raise PermissionError("Rename absichtlich blockiert")
        return echtes_rename(self, target)

    monkeypatch.setattr(Path, "rename", rename_scheitert)
    with pytest.raises(RuntimeError, match="Sicherer Datenbank-Umzug"):
        Store(ziel)

    assert alt.exists(), "die Quelldatenbank muss erhalten bleiben"
    assert not ziel.exists(), "Store darf keine neue leere Zieldatenbank anlegen"


@pytest.mark.parametrize("checkpoint", [(1, 4, 3), (0, 4, 3)])
def test_busy_oder_unvollstaendiger_checkpoint_bricht_ab(
        tmp_path, monkeypatch, checkpoint):
    """Busy und nicht vollständig eingecheckte WAL-Seiten blockieren das Rename."""
    alt, ziel = tmp_path / "nwz.sqlite", tmp_path / "ratslotse.sqlite"
    _db_mit_inhalt(alt)

    class CheckpointVerbindung:
        geschlossen = False

        def execute(self, sql):
            assert sql == "PRAGMA wal_checkpoint(TRUNCATE)"
            return self

        def fetchone(self):
            return checkpoint

        def close(self):
            self.geschlossen = True

    verbindung = CheckpointVerbindung()
    monkeypatch.setattr(store_mod.sqlite3, "connect", lambda *a, **kw: verbindung)

    with pytest.raises(RuntimeError, match="Sicherer Datenbank-Umzug"):
        _umzug_von_nwz(ziel)

    assert verbindung.geschlossen
    assert alt.exists()
    assert not ziel.exists()


def test_cleanup_fehler_bricht_ab_und_naechster_start_repariert(
        tmp_path, monkeypatch):
    """Ein partieller Erfolg wird nicht benutzt, bevor WAL/SHM-Reste weg sind."""
    alt, ziel = tmp_path / "nwz.sqlite", tmp_path / "ratslotse.sqlite"
    wal = tmp_path / "nwz.sqlite-wal"
    shm = tmp_path / "nwz.sqlite-shm"
    _db_mit_inhalt(alt)
    echtes_rename = Path.rename
    echtes_unlink = Path.unlink

    def rename_mit_resten(self, target):
        ergebnis = echtes_rename(self, target)
        if self == alt:
            wal.touch()
            shm.touch()
        return ergebnis

    def shm_unlink_scheitert(self, *args, **kwargs):
        if self == shm:
            raise PermissionError("SHM-Cleanup absichtlich blockiert")
        return echtes_unlink(self, *args, **kwargs)

    with monkeypatch.context() as m:
        m.setattr(Path, "rename", rename_mit_resten)
        m.setattr(Path, "unlink", shm_unlink_scheitert)
        with pytest.raises(RuntimeError, match="Sicherer Datenbank-Umzug"):
            _umzug_von_nwz(ziel)

    assert ziel.exists() and not alt.exists()
    assert shm.exists(), "der simulierte Cleanup-Fehler muss sichtbar bleiben"

    _umzug_von_nwz(ziel)
    assert not wal.exists() and not shm.exists()
    with sqlite3.connect(ziel) as c:
        assert c.execute("SELECT COUNT(*) FROM web_users").fetchone()[0] == 1
    _umzug_von_nwz(ziel)  # auch der reparierte Zustand bleibt idempotent
