"""Ein Leser, der offen bleibt, macht eine lange Ernte unbrauchbar langsam.

Die Adapter ernten INNERHALB einer Schleife über ``raw_objects``:
``iter_papers`` liest die Sitzungen und holt dabei stundenlang Vorlagen, die
es über dieselbe Verbindung schreibt. Bleibt der Lese-Cursor dabei offen,
hält er in SQLites WAL-Modus einen Snapshot fest — und solange der steht,
darf die WAL nicht eingecheckt werden. Sie wächst dann unbegrenzt, und jeder
weitere Zugriff wird teurer.

Gemessen an Hildesheim (11.09.2026): 362 MB WAL nach elf Stunden, Durchsatz
von 343 auf 8 Vorlagen je Stunde gefallen. **Kein Fehler, kein roter Test,
keine auffällige Kennzahl** — der Lauf wurde nur immer langsamer, bis er
aussah wie ein hängender Prozess.
"""
from __future__ import annotations

import sqlite3

import pytest

from council.cities.store import CitiesStore

#: Groß genug, dass die Schreibvorgänge die Vorgabe von SQLites
#: automatischem Einchecken (1.000 Seiten, gut 4 MB) deutlich überschreiten —
#: darunter bewiese ein kleiner WAL-Stand gar nichts.
SEITE = "x" * 20_000


def _fuellen(store: CitiesStore, kind: str, anzahl: int) -> None:
    for i in range(anzahl):
        store.put_raw_object("teststadt", kind, f"{kind}{i}",
                             {"id": f"{kind}{i}", "html": SEITE})


@pytest.fixture()
def store(tmp_path):
    with CitiesStore(tmp_path / "raw.sqlite") as s:
        _fuellen(s, "meeting", 20)
        yield s


def test_einchecken_gelingt_mitten_in_der_iteration(store):
    """Der Kern: schreiben, während über ``raw_objects`` iteriert wird.

    Mit einem offenen Cursor scheitert das Einchecken hart
    (``sqlite3.OperationalError: database table is locked``) — gemessen am
    Stand vor dem Fix. Es genügt also nicht, auf ``busy`` zu prüfen.
    """
    for nummer, _ in enumerate(store.raw_objects("teststadt", "meeting")):
        if nummer < 2:
            continue
        _fuellen(store, "paper", 200)
        try:
            busy, _log, _eingecheckt = store._conn.execute(
                "PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        except sqlite3.OperationalError as e:  # pragma: no cover — genau der Fehler
            pytest.fail(
                f"Einchecken der WAL scheitert während der Iteration ({e}). "
                "`raw_objects` hält wieder einen Cursor über die ganze Schleife "
                "offen — erst die Kennungen mit fetchall() lesen, dann je Zeile "
                "eine eigene Abfrage (s. CitiesStore.raw_objects).")
        assert busy == 0, (
            "Ein Leser blockiert das Einchecken der WAL — dieselbe Ursache, "
            "nur milder gemeldet. Siehe CitiesStore.raw_objects.")
        return
    pytest.fail("Die Fixture liefert zu wenige Sitzungen für die Probe.")


def test_die_wal_waechst_in_der_iteration_nicht_unbegrenzt(store, tmp_path):
    """Das eigentliche Symptom, nicht nur sein Mechanismus.

    Ohne den Fix stand hier bereits nach diesem Miniaturlauf ein zweistelliger
    MB-Wert; im echten Lauf waren es 362 MB.
    """
    wal = tmp_path / "raw.sqlite-wal"
    for nummer, _ in enumerate(store.raw_objects("teststadt", "meeting")):
        _fuellen(store, f"paper{nummer}", 50)
        if nummer >= 5:
            break
    assert wal.stat().st_size < 8_000_000, (
        f"Die WAL steht bei {wal.stat().st_size / 1e6:.1f} MB, obwohl SQLite "
        "bei gut 4 MB von selbst einchecken soll — es wird also durch einen "
        "offenen Leser daran gehindert. Siehe CitiesStore.raw_objects.")


def test_raw_objects_liefert_je_kennung_die_juengste_fassung(store):
    """Der Umbau darf an der Bedeutung nichts ändern.

    ``raw_objects`` verspricht je ``oparl_id`` die zuletzt geholte Fassung,
    in der Reihenfolge, in der sie geholt wurden.
    """
    store.put_raw_object("teststadt", "meeting", "meeting3",
                         {"id": "meeting3", "html": "neuer Stand"})
    objekte = list(store.raw_objects("teststadt", "meeting"))
    assert len(objekte) == 20, "je Kennung genau eine Fassung"
    (drei,) = [o for o in objekte if o["id"] == "meeting3"]
    assert drei["html"] == "neuer Stand", "die jüngste Fassung gewinnt"
    assert objekte[-1]["id"] == "meeting3", "zuletzt geholt steht hinten"
