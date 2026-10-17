"""Das einmalige Neulesen des OCR-Bestands mit aufgerichteten Seiten.

Was hier feststeht, sind die beiden Sicherungen, ohne die ein Neulesen den
Bestand schlechter machen könnte: Ein von Hand geprüftes Dokument wird nicht
überschrieben, und ein Text, der sich zwischen Lesen und Einspielen geändert
hat, auch nicht.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from council.store import CouncilStore  # noqa: E402
from scripts import ocr_neu_aufrichten as neu  # noqa: E402


def _store(tmp_path: Path, *zeilen: tuple[int, str, str | None]) -> Path:
    pfad = tmp_path / "c.sqlite"
    store = CouncilStore(pfad)
    with store._conn:
        for did, text, modell in zeilen:
            store._conn.execute(
                "INSERT INTO council_attachments (document_id, kvonr, label, url, raw_text, "
                "n_pages, fetched_at, status, ocr_model) "
                "VALUES (?, 1, 'Wirtschaftsplan', ?, ?, 2, datetime('now'), 'ok', ?)",
                (did, f"https://example.org/{did}", text, modell))
    store.close()
    return pfad


def _text(pfad: Path, did: int) -> str:
    store = CouncilStore(pfad)
    try:
        return store._conn.execute(
            "SELECT raw_text FROM council_attachments WHERE document_id = ?", (did,)
        ).fetchone()[0]
    finally:
        store.close()


def test_nur_ocr_texte_und_ohne_die_ausgenommenen(tmp_path):
    pfad = _store(tmp_path, (1, "getippt", None), (2, "gescannt", "modell/x"),
                  (188333, "von Hand geprüft", "modell/x"))
    store = CouncilStore(pfad)
    try:
        assert [r["document_id"] for r in neu.kandidaten(store)] == [2]
    finally:
        store.close()


def _abgelegt(verzeichnis: Path, did: int, alt: str, neu_text: str) -> None:
    verzeichnis.mkdir(exist_ok=True)
    (verzeichnis / f"{did}.txt").write_text(neu_text)
    (verzeichnis / f"{did}.alt.txt").write_text(alt)
    (verzeichnis / f"{did}.json").write_text(json.dumps(
        {"document_id": did, "seiten": 2, "gedreht": 1, "modell": "modell/y"}))


def test_einspielen_uebernimmt_den_neuen_text(tmp_path):
    pfad = _store(tmp_path, (2, "seitlich gelesen", "modell/x"))
    _abgelegt(tmp_path / "aus", 2, "seitlich gelesen", "aufrecht gelesen")
    assert neu.einspielen(pfad, tmp_path / "aus")["uebernommen"] == 1
    assert _text(pfad, 2) == "aufrecht gelesen"
    # Der alte Text bleibt als Sicherung liegen.
    assert (tmp_path / "aus" / "2.alt.txt").read_text() == "seitlich gelesen"


def test_geaenderter_bestand_wird_nicht_ueberschrieben(tmp_path):
    """Hat zwischen Lesen und Einspielen jemand den Text angefasst, gewinnt
    der Bestand — ein Neulesen darf keine jüngere Korrektur zurückdrehen."""
    pfad = _store(tmp_path, (2, "inzwischen korrigiert", "modell/x"))
    _abgelegt(tmp_path / "aus", 2, "seitlich gelesen", "aufrecht gelesen")
    ergebnis = neu.einspielen(pfad, tmp_path / "aus")
    assert ergebnis == {"uebernommen": 0, "geaendert_uebersprungen": 1}
    assert _text(pfad, 2) == "inzwischen korrigiert"


def test_zweites_einspielen_aendert_nichts(tmp_path):
    pfad = _store(tmp_path, (2, "seitlich gelesen", "modell/x"))
    _abgelegt(tmp_path / "aus", 2, "seitlich gelesen", "aufrecht gelesen")
    neu.einspielen(pfad, tmp_path / "aus")
    assert neu.einspielen(pfad, tmp_path / "aus")["uebernommen"] == 0
    assert _text(pfad, 2) == "aufrecht gelesen"
