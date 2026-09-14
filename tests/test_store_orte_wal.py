"""Ein Leser, der offen bleibt, macht die Ortszuordnung unbrauchbar langsam.

``scripts/extract_decision_locations.py`` arbeitet INNERHALB einer Schleife
über ``decision_location_batches``: Es fragt je Batch ein Sprachmodell — das
dauert Sekunden — und schreibt die Zuordnungen anschließend über dieselbe
Verbindung. Bleibt der Lese-Cursor dabei offen, hält er in SQLites WAL-Modus
einen Snapshot fest, und solange der steht, darf die WAL nicht eingecheckt
werden. Sie wächst dann unbegrenzt, und jeder weitere Zugriff wird teurer.

Gemessen an derselben Bauform im Städte-Speicher (11.09.2026, s.
``tests/test_cities_store_wal.py``): 362 MB WAL nach elf Stunden, Durchsatz
von 343 auf 8 Objekte je Stunde gefallen. **Kein Fehler, kein roter Test,
keine auffällige Kennzahl** — der Lauf wurde nur immer langsamer, bis er
aussah wie ein hängender Prozess. Ein Neustart heilte es sprunghaft.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from council.store import CouncilStore  # noqa: E402

#: Groß genug, dass die Schreibvorgänge die Vorgabe von SQLites automatischem
#: Einchecken (1.000 Seiten, gut 4 MB) deutlich überschreiten — darunter
#: bewiese ein kleiner WAL-Stand gar nichts.
SEITE = "x" * 20_000


def _beschluesse(store: CouncilStore, anzahl: int) -> None:
    """Beschlüsse mit je einer Vorlage, deren Text eine ganze Seite trägt."""
    with store._conn:
        store._conn.executemany(
            "INSERT INTO council_templates (kvonr, template_number, raw_text, "
            "fetched_at, status) VALUES (?,?,?,'2026-01-01T00:00:00','ok')",
            [(500 + i, f"26/{i:04d}", f"Vorlage {i} zur Teststraße {i}. {SEITE}")
             for i in range(anzahl)])
        store._conn.executemany(
            "INSERT INTO council_decisions (id, ksinr, position, kind, title, "
            "kvonr, template_number, official_text) VALUES (?,1,?,'decision',?,?,?,?)",
            [(100 + i, i, f"Beschluss {i}", 500 + i, f"26/{i:04d}", f"Text {i}")
             for i in range(anzahl)])


def _nachschieben(store: CouncilStore, marke: str, anzahl: int) -> None:
    """Schreiben über DIESELBE Verbindung — so wie es der Aufrufer tut."""
    with store._conn:
        store._conn.executemany(
            "INSERT INTO council_templates (kvonr, template_number, raw_text, "
            "fetched_at, status) VALUES (?,?,?,'2026-01-01T00:00:00','ok')",
            [(hash((marke, i)) % 10_000_000 + 1_000_000, f"{marke}/{i}", SEITE)
             for i in range(anzahl)])


@pytest.fixture()
def store(tmp_path):
    s = CouncilStore(tmp_path / "council.sqlite")
    _beschluesse(s, 24)
    try:
        yield s
    finally:
        s.close()


def test_einchecken_gelingt_mitten_in_der_iteration(store):
    """Der Kern: schreiben, während über die Batches iteriert wird.

    Mit einem offenen Cursor scheitert das Einchecken hart
    (``sqlite3.OperationalError: database table is locked``) — gemessen am
    Stand vor dem Fix. Es genügt also nicht, auf ``busy`` zu prüfen.
    """
    for nummer, batch in enumerate(store.decision_location_batches(batch_size=4)):
        if nummer < 2:
            continue
        # Genau das, was das Skript hier tut: die Funde des Batches speichern …
        for row in batch:
            store.save_decision_locations(
                row["id"], [{"name": "Teststraße", "confidence": 0.9}], "hash")
        _nachschieben(store, f"lauf{nummer}", 300)
        try:
            busy, _log, _eingecheckt = store._conn.execute(
                "PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        except sqlite3.OperationalError as e:  # pragma: no cover — genau der Fehler
            pytest.fail(
                f"Einchecken der WAL scheitert während der Iteration ({e}). "
                "`decision_location_batches` hält wieder einen Cursor über die "
                "ganze Schleife offen — erst die Kennungen mit fetchall() lesen, "
                "dann je Batch eine eigene Abfrage (s. OrteMixin).")
        assert busy == 0, (
            "Ein Leser blockiert das Einchecken der WAL — dieselbe Ursache, "
            "nur milder gemeldet. Siehe OrteMixin.decision_location_batches.")
        return
    pytest.fail("Die Fixture liefert zu wenige Batches für die Probe.")


def test_die_wal_waechst_in_der_iteration_nicht_unbegrenzt(store, tmp_path):
    """Das eigentliche Symptom, nicht nur sein Mechanismus.

    Ohne den Fix stand hier bereits nach diesem Miniaturlauf ein zweistelliger
    MB-Wert; im echten Lauf waren es 362 MB.
    """
    wal = tmp_path / "council.sqlite-wal"
    for nummer, _batch in enumerate(store.decision_location_batches(batch_size=4)):
        _nachschieben(store, f"runde{nummer}", 100)
        if nummer >= 4:
            break
    assert wal.stat().st_size < 8_000_000, (
        f"Die WAL steht bei {wal.stat().st_size / 1e6:.1f} MB, obwohl SQLite "
        "bei gut 4 MB von selbst einchecken soll — es wird also durch einen "
        "offenen Leser daran gehindert. Siehe "
        "OrteMixin.decision_location_batches.")


def test_batches_liefern_unveraendert_beschluss_und_vorlagentext(store):
    """Der Umbau darf an der Bedeutung nichts ändern.

    Jeder Beschluss kommt genau einmal, mit dem Text seiner Vorlage, in
    absteigender Kennung — und im Tageslauf nur, solange er offen ist.
    """
    zeilen = [row for batch in store.decision_location_batches(batch_size=5)
              for row in batch]
    assert [r["id"] for r in zeilen] == list(range(123, 99, -1)), \
        "alle 24 Beschlüsse, absteigend"
    assert zeilen[0]["title"] == "Beschluss 23"
    assert zeilen[0]["vorlage_text"].startswith("Vorlage 23 zur Teststraße 23.")
    assert zeilen[0]["vorlage_fetched_at"] == "2026-01-01T00:00:00"
    assert zeilen[0]["existing_source_hash"] is None

    # Gescanntes fällt beim nächsten Tageslauf heraus, der Voll-Backfill
    # nimmt es weiterhin mit.
    store.save_decision_locations(123, [], "fertig")
    offen = [r["id"] for b in store.decision_location_batches(batch_size=5) for r in b]
    assert 123 not in offen and len(offen) == 23
    alle = [r["id"] for b in store.decision_location_batches(
        batch_size=5, pending_only=False) for r in b]
    assert len(alle) == 24

    # Die Kappe zählt Beschlüsse, nicht Batches.
    gekappt = [r["id"] for b in store.decision_location_batches(
        batch_size=5, pending_only=False, limit=7) for r in b]
    assert gekappt == list(range(123, 116, -1))
