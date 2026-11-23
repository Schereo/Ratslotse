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


def _umgebung(tmp_path, monkeypatch):
    from scripts import backup_db as b

    data = tmp_path / "data"
    data.mkdir(parents=True)
    monkeypatch.setattr(b, "ROOT", tmp_path)
    monkeypatch.setattr(b, "DATA", data)
    monkeypatch.setattr(b, "BACKUP_DIR", data / "backups")
    monkeypatch.setattr(b, "CRONTAB_BEFEHL", ["false"])
    monkeypatch.delenv("BACKUP_RSYNC_TARGET", raising=False)
    return b, data


def test_handkopien_laufen_nicht_als_datenbank_durch(tmp_path, monkeypatch):
    """Eine Handkopie mit Punkt im Stamm lief bis 23.11.2026 als eigene
    Datenbank durch die Rotation — elf Stände zu 800 MB."""
    b, data = _umgebung(tmp_path, monkeypatch)
    _db(data / "council.sqlite")
    _db(data / "council.vor-pymupdf-2026-10-18.sqlite")

    stats = b.main()
    assert stats["Datenbanken gesichert"] == 1
    assert stats["Handkopien übersprungen"] == 1
    assert [p.name.split("_")[0] for p in (data / "backups").glob("*.sqlite")] == ["council"]


def test_einzeldateien_ordner_und_crontab_kommen_mit(tmp_path, monkeypatch):
    b, data = _umgebung(tmp_path, monkeypatch)
    _db(data / "council.sqlite")
    (data / "wahlabend-verlauf-ratswahl-2026.json").write_text('{"stand": 1}')
    (data / "strassen-snapshot.json").write_text("[]")
    (data / "tippspiel-geloescht.json").write_text("{}")      # nicht auf der Liste
    (data / "transkripte").mkdir()
    (data / "transkripte" / "rat-2026-11-02.txt").write_text("Wortbeitrag")
    script = tmp_path / "crontab"
    script.write_text("#!/bin/sh\necho '15 3 * * * backup_db.py'\n")
    script.chmod(0o755)
    monkeypatch.setattr(b, "CRONTAB_BEFEHL", [str(script)])

    stats = b.main()
    einzeln = data / "backups" / "einzeldateien"
    assert stats["Einzeldateien"] == 2
    assert sorted(p.name for p in einzeln.iterdir()) == [
        "strassen-snapshot.json", "wahlabend-verlauf-ratswahl-2026.json"]
    assert stats["Sitzungs-Transkripte"] == 1
    assert (data / "backups" / "transkripte" / "rat-2026-11-02.txt").read_text() == "Wortbeitrag"
    assert stats["crontab gesichert"] == "ja"
    kopie = data / "backups" / "crontab.backup"
    assert "backup_db.py" in kopie.read_text()
    assert oct(kopie.stat().st_mode)[-3:] == "600"

    # Was unter data/ verschwindet, verschwindet auch aus der Sicherung.
    (data / "strassen-snapshot.json").unlink()
    b.main()
    assert [p.name for p in einzeln.iterdir()] == ["wahlabend-verlauf-ratswahl-2026.json"]


def test_ohne_crontab_kein_fehler(tmp_path, monkeypatch):
    b, data = _umgebung(tmp_path, monkeypatch)
    _db(data / "council.sqlite")
    assert b.main()["crontab gesichert"] == "nein"
    assert not (data / "backups" / "crontab.backup").exists()


def test_kopien_tragen_keinen_wal_und_die_rotation_raeumt_begleiter(tmp_path, monkeypatch):
    """Die Kopie erbte den WAL-Modus; jedes spätere Öffnen ließ -wal/-shm
    liegen, die die Rotation nie mitnahm (23.11.2026: 218 Stück)."""
    b, data = _umgebung(tmp_path, monkeypatch)
    conn = sqlite3.connect(data / "council.sqlite")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.commit()
    conn.close()
    backups = data / "backups"
    backups.mkdir()
    # Ein uralter Stand samt Begleitern und ein verwaister Begleiter.
    _db(backups / "council_2020-01-01.sqlite")
    (backups / "council_2020-01-01.sqlite-wal").write_bytes(b"")
    (backups / "council_2020-01-01.sqlite-shm").write_bytes(b"")
    (backups / "council_2019-05-05.sqlite-shm").write_bytes(b"")
    # Genug jüngere Wochen, dass 2020 auch als Wochenstand herausfällt.
    for monat, tag in [(m, t) for m in (9, 10, 11) for t in range(1, 22, 3)]:
        _db(backups / f"council_2026-{monat:02d}-{tag:02d}.sqlite")

    b.main()
    kopie = max(backups.glob("council_*.sqlite"))
    conn = sqlite3.connect(f"file:{kopie}?mode=ro", uri=True)
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    conn.close()
    assert not (backups / "council_2020-01-01.sqlite").exists()
    assert not list(backups.glob("*.sqlite-*"))
