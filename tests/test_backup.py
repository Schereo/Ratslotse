"""Sichert das Backup wirklich alles?"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _db(pfad, zeilen=1):
    conn = sqlite3.connect(pfad)
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(zeilen)])
    conn.commit()
    conn.close()


def test_backup_nimmt_jede_datenbank_planzeichnungen_und_env(tmp_path, monkeypatch):
    """Die feste Liste (nwz.sqlite, council.sqlite) hätte eine dritte Datenbank
    still übersprungen — Tims Befund 12.08. Jetzt zählt der Ordner."""
    from scripts import backup_db as b

    data = tmp_path / "data"
    (data / "plaene").mkdir(parents=True)
    _db(data / "nwz.sqlite")
    _db(data / "council.sqlite")
    _db(data / "neue_datenbank.sqlite")          # die, die früher durchrutschte
    (data / "council.sqlite.bak-alt").write_text("kein Backup-Ziel")
    (data / "plaene" / "4711.jpg").write_bytes(b"\xff\xd8bild")
    (tmp_path / ".env").write_text("WEB_JWT_SECRET=geheim\n")

    monkeypatch.setattr(b, "ROOT", tmp_path)
    monkeypatch.setattr(b, "DATA", data)
    monkeypatch.setattr(b, "BACKUP_DIR", data / "backups")
    monkeypatch.delenv("BACKUP_RSYNC_TARGET", raising=False)

    kennzahlen = b.main()
    assert kennzahlen["Datenbanken gesichert"] == 3
    assert kennzahlen["Planzeichnungen"] == 1
    assert kennzahlen[".env gesichert"] == "ja"

    kopien = {p.name.split("_")[0] for p in (data / "backups").glob("*.sqlite")}
    assert kopien == {"nwz", "council", "neue"}   # neue_datenbank → Präfix "neue"
    assert (data / "backups" / "plaene" / "4711.jpg").read_bytes() == b"\xff\xd8bild"
    env_kopie = data / "backups" / "env.backup"
    assert "geheim" in env_kopie.read_text()
    assert oct(env_kopie.stat().st_mode)[-3:] == "600"

    # Die Kopie ist les- und benutzbar, nicht nur vorhanden.
    kopie = next((data / "backups").glob("nwz_*.sqlite"))
    conn = sqlite3.connect(kopie)
    assert conn.execute("SELECT count(*) FROM t").fetchone()[0] == 1
    conn.close()


def test_env_sicherung_laesst_sich_abschalten(tmp_path, monkeypatch):
    from scripts import backup_db as b

    data = tmp_path / "data"
    data.mkdir(parents=True)
    _db(data / "nwz.sqlite")
    (tmp_path / ".env").write_text("WEB_JWT_SECRET=geheim\n")
    monkeypatch.setattr(b, "ROOT", tmp_path)
    monkeypatch.setattr(b, "DATA", data)
    monkeypatch.setattr(b, "BACKUP_DIR", data / "backups")
    monkeypatch.setenv("BACKUP_ENV", "0")
    monkeypatch.delenv("BACKUP_RSYNC_TARGET", raising=False)

    assert b.main()[".env gesichert"] == "nein"
    assert not (data / "backups" / "env.backup").exists()
