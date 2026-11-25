"""Der Spiegel Prod → dev (scripts/dev_mirror.py).

Was er halten muss, und warum:

* Nutzerbezogene Tabellen verlassen Prod nie mit Inhalt — sie werden in der
  Kopie geleert, bevor sie übertragen wird.
* Was es nur auf dev gibt (Anreicherungen hinter Schaltern, die Testkonten
  von dev), überlebt den Tausch.
* Eine unplausibel kleine Kopie wird nicht eingespielt — dev bleibt dann,
  wie es ist.
* Was verloren ginge, steht im Bericht, statt still zu verschwinden.
"""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

from council.scraper import CouncilSession
from council.store import COUNCIL_USER_OWNED_TABLES, COUNCIL_USER_TEXT_TABLES, CouncilStore

WURZEL = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("dev_mirror", WURZEL / "scripts" / "dev_mirror.py")
assert _spec and _spec.loader
mirror = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mirror)

NUTZER = [t for t, _ in COUNCIL_USER_OWNED_TABLES]
NUTZER_UND_TEXT = NUTZER + list(COUNCIL_USER_TEXT_TABLES)


def _db(pfad: Path, beschluesse: int) -> str:
    cs = CouncilStore(str(pfad))
    cs.save_session(CouncilSession(1, "Rat", "2026-06-01", "17:00", "Rathaus"))
    with cs._conn:
        for i in range(beschluesse):
            cs._conn.execute("INSERT INTO council_decisions (id, ksinr, position, item_number, title, kind)"
                             " VALUES (?, 1, ?, ?, 'Punkt', 'decision')", (i + 1, i, str(i)))
    cs.close()
    return str(pfad)


def _sql(pfad: str, sql: str, *args):
    con = sqlite3.connect(pfad)
    with con:
        rows = con.execute(sql, args).fetchall()
    con.close()
    return rows


def _feedback(pfad: str, frage: str) -> None:
    _sql(pfad, "INSERT INTO council_qa_feedback (question, rating, user_id, created) VALUES (?, 1, 7, '2026-11-23')",
         frage)


def test_kopie_traegt_keine_nutzerdaten(tmp_path):
    prod = _db(tmp_path / "prod.sqlite", 3)
    _feedback(prod, "Frage einer echten Person")
    _sql(prod, "INSERT INTO council_partei_meinungen_cache (key, question, result, created_at)"
               " VALUES ('k', 'Was denkt die SPD über meine Straße?', '{}', '2026-11-23')")
    kopie = str(tmp_path / "kopie.sqlite")
    bericht = mirror.snapshot(prod, kopie, NUTZER_UND_TEXT)
    assert bericht["cleared"]["council_qa_feedback"] == 1
    assert bericht["cleared"]["council_partei_meinungen_cache"] == 1
    assert _sql(kopie, "SELECT count(*) FROM council_qa_feedback") == [(0,)]
    assert _sql(kopie, "SELECT count(*) FROM council_partei_meinungen_cache") == [(0,)]
    # Auch nicht in freien Seiten: Ein bloßes DELETE ließe den Text in der Datei.
    roh = Path(kopie).read_bytes()
    assert b"Frage einer echten Person" not in roh
    assert "meine Straße".encode() not in roh
    assert not Path(kopie + ".arbeit").exists()
    # Die Quelle bleibt unberührt.
    assert _sql(prod, "SELECT count(*) FROM council_qa_feedback") == [(1,)]


#: Tabellen, deren Fragetext ERZEUGT ist (Quiz, Vorschlagsfragen) — kein
#: Nutzer-Freitext, darf deshalb mit nach dev.
ERZEUGTER_TEXT = {"council_quiz_questions", "page_questions"}


def test_jede_tabelle_mit_fragetext_ist_eingeordnet(tmp_path):
    """Eine neue Tabelle, die Fragen speichert, muss jemand einordnen: an einem
    Konto (COUNCIL_USER_OWNED_TABLES), Nutzer-Freitext ohne Konto
    (COUNCIL_USER_TEXT_TABLES) oder erzeugter Text (ERZEUGTER_TEXT hier). Sonst
    trüge der dev-Spiegel sie mit gestellten Fragen von Prod nach dev — so
    ging es dem Zwischenspeicher der Parteien-Meinungen bis zum 23.11.2026."""
    import re
    pfad = _db(tmp_path / "c.sqlite", 1)
    con = sqlite3.connect(pfad)
    verdacht = re.compile(r"(^|_)(question|questions|frage|fragen|query|anfrage)(_|$)", re.I)
    eingeordnet = set(NUTZER_UND_TEXT) | ERZEUGTER_TEXT
    offen = []
    for (tabelle,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'"):
        if "_fts" in tabelle:
            continue
        spalten = [r[1] for r in con.execute(f'PRAGMA table_info("{tabelle}")')]
        if any(verdacht.search(sp) for sp in spalten) and tabelle not in eingeordnet:
            offen.append(tabelle)
    con.close()
    assert not offen, (
        f"Tabellen mit Fragetext, die niemand eingeordnet hat: {offen}. "
        "Nutzer-Freitext → council.store.COUNCIL_USER_TEXT_TABLES (oder mit Konto-Spalte "
        "COUNCIL_USER_OWNED_TABLES); erzeugter Text → ERZEUGTER_TEXT in diesem Test.")


def test_dev_behaelt_anreicherungen_und_testkonten(tmp_path):
    prod = _db(tmp_path / "prod.sqlite", 10)
    dev = _db(tmp_path / "dev.sqlite", 9)
    _sql(dev, "INSERT INTO template_terms (template_number, sources_hash, prompt_version, model, status, payload,"
              " created_at) VALUES ('26/0331', 'h', 1, 'm', 'ok', '{}', '2026-11-20')")
    _feedback(dev, "Testfrage auf dev")
    kopie = str(tmp_path / "kopie.sqlite")
    mirror.snapshot(prod, kopie, NUTZER)

    import os
    os.chmod(dev, 0o644)
    bericht = mirror.swap(kopie, dev, NUTZER, backup=str(tmp_path / "sicherung.sqlite"))

    assert bericht["swapped"] is True
    assert os.stat(dev).st_mode & 0o777 == 0o644   # Rechte der alten Datei
    assert bericht["preserved"]["template_terms"] == 1
    assert _sql(dev, "SELECT count(*) FROM council_decisions") == [(10,)]   # jetzt die von Prod
    assert _sql(dev, "SELECT template_number FROM template_terms") == [("26/0331",)]
    assert _sql(dev, "SELECT question FROM council_qa_feedback") == [("Testfrage auf dev",)]
    assert _sql(str(tmp_path / "sicherung.sqlite"), "SELECT count(*) FROM council_decisions") == [(9,)]


def test_unplausibel_kleine_kopie_wird_nicht_eingespielt(tmp_path):
    prod = _db(tmp_path / "prod.sqlite", 5)
    dev = _db(tmp_path / "dev.sqlite", 10)
    kopie = str(tmp_path / "kopie.sqlite")
    mirror.snapshot(prod, kopie, NUTZER)
    with pytest.raises(SystemExit, match="Unplausibel"):
        mirror.swap(kopie, dev, NUTZER)
    assert _sql(dev, "SELECT count(*) FROM council_decisions") == [(10,)]


def test_bericht_nennt_was_verloren_ginge(tmp_path):
    """Eine Tabelle, die dev voller hat und die an einer Beschluss-id hängt,
    wird nicht übernommen (die Nummer bedeutet auf Prod etwas anderes) — aber
    sie steht im Bericht."""
    prod = _db(tmp_path / "prod.sqlite", 10)
    dev = _db(tmp_path / "dev.sqlite", 10)
    for i in range(1, 9):
        _sql(dev, "INSERT INTO council_entity_obs (decision_id, slug, name, kind) VALUES (?, 'x', 'X', 'project')", i)
    kopie = str(tmp_path / "kopie.sqlite")
    mirror.snapshot(prod, kopie, NUTZER)
    bericht = mirror.swap(kopie, dev, NUTZER, dry_run=True)
    assert bericht["lost_tables"]["council_entity_obs"] == {"dev": 8, "prod": 0}
    assert "council_entity_obs" in mirror.markdown(bericht)
    assert bericht["swapped"] is False
    assert _sql(dev, "SELECT count(*) FROM council_entity_obs") == [(8,)]   # Trockenlauf: nichts getauscht


def test_leere_prod_tabelle_ohne_beschluss_id_kommt_von_dev(tmp_path):
    """Eine neue dev-Anreicherung, die noch niemand in die Liste eingetragen
    hat, verschwindet nicht über Nacht."""
    prod = _db(tmp_path / "prod.sqlite", 10)
    dev = _db(tmp_path / "dev.sqlite", 10)
    for tabelle in (prod, dev):
        _sql(tabelle, "CREATE TABLE neue_anreicherung (template_number TEXT PRIMARY KEY, payload TEXT)")
    _sql(dev, "INSERT INTO neue_anreicherung VALUES ('26/0001', '{}')")
    kopie = str(tmp_path / "kopie.sqlite")
    mirror.snapshot(prod, kopie, NUTZER)
    bericht = mirror.swap(kopie, dev, NUTZER)
    assert bericht["auto_preserved"]["neue_anreicherung"] == 1
    assert _sql(dev, "SELECT template_number FROM neue_anreicherung") == [("26/0001",)]


def test_tabelle_die_prod_noch_nicht_kennt_ueberlebt(tmp_path):
    """Neue dev-Anreicherung, deren Code noch nicht released ist: Auf Prod
    gibt es die Tabelle gar nicht. Am 24.11.2026 gingen so die
    Haushaltsentwurf-Befunde und 235 Beteiligungs-Prognosen verloren."""
    prod = _db(tmp_path / "prod.sqlite", 10)
    dev = _db(tmp_path / "dev.sqlite", 10)
    _sql(dev, "CREATE TABLE nur_auf_dev (document_id INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
    _sql(dev, "CREATE INDEX idx_nur_auf_dev ON nur_auf_dev(payload)")
    _sql(dev, "INSERT INTO nur_auf_dev VALUES (7, '{}')")
    kopie = str(tmp_path / "kopie.sqlite")
    mirror.snapshot(prod, kopie, NUTZER)
    bericht = mirror.swap(kopie, dev, NUTZER)
    assert bericht["auto_preserved"]["nur_auf_dev"] == 1
    assert "nur_auf_dev" not in bericht["lost_tables"]
    assert _sql(dev, "SELECT document_id FROM nur_auf_dev") == [(7,)]
    assert _sql(dev, "SELECT name FROM sqlite_master WHERE name = 'idx_nur_auf_dev'") == [("idx_nur_auf_dev",)]


def test_dev_only_tabelle_die_prod_nicht_kennt_ueberlebt(tmp_path, monkeypatch):
    """Eingetragen in DEV_ONLY_TABLES zählt sie als bewahrt — auch mit einer
    Spalte, die sonst gegen die automatische Übernahme spräche."""
    monkeypatch.setattr(mirror, "DEV_ONLY_TABLES", (*mirror.DEV_ONLY_TABLES, "gelistet"))
    prod = _db(tmp_path / "prod.sqlite", 10)
    dev = _db(tmp_path / "dev.sqlite", 10)
    _sql(dev, "CREATE TABLE gelistet (decision_id INTEGER PRIMARY KEY)")
    _sql(dev, "INSERT INTO gelistet VALUES (3)")
    kopie = str(tmp_path / "kopie.sqlite")
    mirror.snapshot(prod, kopie, NUTZER)
    bericht = mirror.swap(kopie, dev, NUTZER)
    assert bericht["preserved"]["gelistet"] == 1
    assert _sql(dev, "SELECT decision_id FROM gelistet") == [(3,)]


def test_tabelle_nur_auf_dev_mit_beschluss_id_bleibt_verloren(tmp_path):
    """Hängt sie an einer umgebungseigenen Nummer und steht nicht in der Liste,
    wird sie nicht übernommen — aber gemeldet."""
    prod = _db(tmp_path / "prod.sqlite", 10)
    dev = _db(tmp_path / "dev.sqlite", 10)
    _sql(dev, "CREATE TABLE haengt_an_id (decision_id INTEGER, x TEXT)")
    _sql(dev, "INSERT INTO haengt_an_id VALUES (3, 'a')")
    kopie = str(tmp_path / "kopie.sqlite")
    mirror.snapshot(prod, kopie, NUTZER)
    bericht = mirror.swap(kopie, dev, NUTZER, dry_run=True)
    assert bericht["lost_tables"]["haengt_an_id"] == {"dev": 1, "prod": None}


def test_liste_nennt_nur_tabellen_ohne_umgebungseigene_nummer():
    """Jede Tabelle in DEV_ONLY_TABLES muss es im Schema geben und darf an
    keiner umgebungseigenen Nummer hängen — sonst zeigte sie nach dem Tausch
    auf fremde Beschlüsse."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        pfad = _db(Path(d) / "c.sqlite", 1)
        con = sqlite3.connect(pfad)
        for tabelle in mirror.DEV_ONLY_TABLES:
            spalten = {r[1] for r in con.execute(f'PRAGMA table_info("{tabelle}")')}
            assert spalten, f"{tabelle} steht in DEV_ONLY_TABLES, gibt es im Schema aber nicht"
            assert not spalten & mirror.ENV_ID_COLUMNS, f"{tabelle} hängt an {spalten & mirror.ENV_ID_COLUMNS}"
        con.close()
