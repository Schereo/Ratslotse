"""Sichert das Backup wirklich alles?"""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _db(pfad, zeilen=1):
    conn = sqlite3.connect(pfad)
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(zeilen)])
    conn.commit()
    conn.close()


def test_backup_nimmt_jede_datenbank_planzeichnungen_und_env(tmp_path, monkeypatch):
    """Die feste Liste (ratslotse.sqlite, council.sqlite) hätte eine dritte Datenbank
    still übersprungen — Tims Befund 12.08. Jetzt zählt der Ordner."""
    from scripts import backup_db as b

    data = tmp_path / "data"
    (data / "plaene").mkdir(parents=True)
    _db(data / "ratslotse.sqlite")
    _db(data / "council.sqlite")
    _db(data / "neue_datenbank.sqlite")          # die, die früher durchrutschte
    (data / "council.sqlite.bak-alt").write_text("kein Backup-Ziel")
    (data / "plaene" / "4711.jpg").write_bytes(b"\xff\xd8bild")
    (tmp_path / ".env").write_text("WEB_JWT_SECRET=geheim\n")

    monkeypatch.setattr(b, "ROOT", tmp_path)
    monkeypatch.setattr(b, "DATA", data)
    monkeypatch.setattr(b, "BACKUP_DIR", data / "backups")
    monkeypatch.delenv("BACKUP_RSYNC_TARGET", raising=False)

    indicators = b.main()
    assert indicators["Datenbanken gesichert"] == 3
    assert indicators["Planzeichnungen"] == 1
    assert indicators[".env gesichert"] == "ja"

    kopien = {p.name.split("_")[0] for p in (data / "backups").glob("*.sqlite")}
    assert kopien == {"ratslotse", "council", "neue"}   # neue_datenbank → Präfix "neue"
    assert (data / "backups" / "plaene" / "4711.jpg").read_bytes() == b"\xff\xd8bild"
    env_kopie = data / "backups" / "env.backup"
    assert "geheim" in env_kopie.read_text()
    assert oct(env_kopie.stat().st_mode)[-3:] == "600"

    # Die Kopie ist les- und benutzbar, nicht nur vorhanden.
    kopie = next((data / "backups").glob("ratslotse_*.sqlite"))
    conn = sqlite3.connect(kopie)
    assert conn.execute("SELECT count(*) FROM t").fetchone()[0] == 1
    conn.close()


def test_env_sicherung_laesst_sich_abschalten(tmp_path, monkeypatch):
    from scripts import backup_db as b

    data = tmp_path / "data"
    data.mkdir(parents=True)
    _db(data / "ratslotse.sqlite")
    (tmp_path / ".env").write_text("WEB_JWT_SECRET=geheim\n")
    monkeypatch.setattr(b, "ROOT", tmp_path)
    monkeypatch.setattr(b, "DATA", data)
    monkeypatch.setattr(b, "BACKUP_DIR", data / "backups")
    monkeypatch.setenv("BACKUP_ENV", "0")
    monkeypatch.delenv("BACKUP_RSYNC_TARGET", raising=False)

    assert b.main()[".env gesichert"] == "nein"
    assert not (data / "backups" / "env.backup").exists()


def test_regulaeres_backup_respektiert_release_barriere(tmp_path, monkeypatch):
    from kern.maintenance import BYPASS_ENV, MARKER_NAME
    from scripts import backup_db as b

    data = tmp_path / "data"
    data.mkdir()
    _db(data / "ratslotse.sqlite")
    (data / MARKER_NAME).touch()
    monkeypatch.setattr(b, "DATA", data)
    monkeypatch.setattr(b, "BACKUP_DIR", data / "backups")
    monkeypatch.delenv(BYPASS_ENV, raising=False)

    with pytest.raises(RuntimeError, match="Release-Wartung aktiv"):
        b.backup_databases()
    assert not (data / "backups").exists()


def _setup(tmp_path, monkeypatch):
    from scripts import backup_db as b
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(b, "ROOT", tmp_path)
    monkeypatch.setattr(b, "DATA", data)
    monkeypatch.setattr(b, "BACKUP_DIR", data / "backups")
    monkeypatch.delenv("BACKUP_RSYNC_TARGET", raising=False)
    return b, data


def test_eine_kaputte_kopie_wird_kein_stand(tmp_path, monkeypatch):
    """Bis 10/2026 schrieb die Backup-API direkt in die datierte Datei. Lief
    die Platte voll, blieb eine halbe Datei unter einem gültigen Namen liegen
    und verdrängte in der Rotation einen guten Stand."""
    b, data = _setup(tmp_path, monkeypatch)
    _db(data / "council.sqlite", zeilen=3)
    (data / "backups").mkdir()
    alt = data / "backups" / "council_2026-01-01.sqlite"
    _db(alt)

    def kaputt(pfad):
        raise b.SicherungKaputt("integrity_check → *** in database main ***")

    monkeypatch.setattr(b, "_pruefen", kaputt)
    with pytest.raises(b.SicherungKaputt):
        b.backup_db(data / "council.sqlite")
    # Kein neuer Stand, keine Zwischendatei, der alte Stand unangetastet.
    assert sorted(p.name for p in (data / "backups").iterdir()) == [alt.name]


def test_die_pruefung_erkennt_eine_zerschriebene_datei(tmp_path):
    from scripts import backup_db as b

    pfad = tmp_path / "x.sqlite"
    _db(pfad, zeilen=2000)
    roh = bytearray(pfad.read_bytes())
    roh[4096:4096 + 12] = b"\x0d" + b"\xff" * 11   # Kopf der ersten Tabellenseite
    pfad.write_bytes(bytes(roh))
    with pytest.raises((b.SicherungKaputt, sqlite3.DatabaseError)):
        b._pruefen(pfad)


def test_eine_gute_kopie_liegt_geprueft_unter_dem_datum(tmp_path, monkeypatch):
    b, data = _setup(tmp_path, monkeypatch)
    _db(data / "council.sqlite", zeilen=3)
    b.backup_db(data / "council.sqlite")
    namen = [p.name for p in (data / "backups").iterdir()]
    assert len(namen) == 1 and namen[0].startswith("council_") and not namen[0].startswith(".")


def test_der_staedte_speicher_behaelt_nur_zwei_staende(tmp_path, monkeypatch):
    """2,4 GB × 11 Stände = 27 GB auf einer Platte, die voll lief. Der
    Städte-Speicher ist aus öffentlichen Quellen wiederherstellbar."""
    b, data = _setup(tmp_path, monkeypatch)
    _db(data / "cities.sqlite")
    _db(data / "council.sqlite")
    (data / "backups").mkdir()
    for tag in range(1, 21):
        for stamm in ("cities", "council"):
            _db(data / "backups" / f"{stamm}_2026-01-{tag:02d}.sqlite")
    assert b.backup_db(data / "cities.sqlite") == 2
    assert len(list((data / "backups").glob("cities_*.sqlite"))) == 2
    # Die übrigen Datenbanken behalten ihre volle Rotation.
    assert b.backup_db(data / "council.sqlite") > 2
