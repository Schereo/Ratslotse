"""Ligaturen im gespeicherten Bestand auflösen (scripts/ligaturen_reparieren.py):
Trockenlauf als Vorgabe, Text und Seitenanfänge gemeinsam."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import ligaturen_reparieren as skript  # noqa: E402
from council.store import CouncilStore  # noqa: E402

SEITEN = ["Bericht der städƟschen Gesellschaften. ", "Der WirtschaŌsplan wird eingehalten. ", "Ende."]


def _db(tmp_path) -> Path:
    pfad = tmp_path / "council.sqlite"
    store = CouncilStore(pfad)
    text = "".join(SEITEN)
    offsets = [0, len(SEITEN[0]), len(SEITEN[0]) + len(SEITEN[1])]
    with store._conn:
        store._conn.execute("INSERT INTO council_attachments (document_id, kvonr, label, url, raw_text, status, fetched_at) "
                            "VALUES (316197, 1, 'Quartalsbericht', 'u', ?, 'ok', 'x')", (text,))
        store._conn.execute("INSERT INTO council_attachments (document_id, kvonr, label, url, raw_text, status, fetched_at) "
                            "VALUES (1, 1, 'sauber', 'u', 'Nichts zu tun.', 'ok', 'x')")
    store.save_document_profile(316197, "report", page_offsets=offsets)
    store.close()
    return pfad


def _lesen(pfad: Path):
    store = CouncilStore(pfad)
    text = store._conn.execute("SELECT raw_text FROM council_attachments WHERE document_id = 316197").fetchone()[0]
    off = json.loads(store._conn.execute(
        "SELECT page_offsets FROM council_documents WHERE document_id = 316197").fetchone()[0])
    store.close()
    return text, off


def test_trockenlauf_schreibt_nichts(tmp_path):
    pfad = _db(tmp_path)
    bericht = skript.main(["--db", str(pfad)])
    assert bericht["anlagen"] == 1
    assert "städƟschen" in _lesen(pfad)[0]


def test_schreiben_repariert_text_und_seitenanfaenge(tmp_path):
    pfad = _db(tmp_path)
    skript.main(["--db", str(pfad), "--schreiben"])
    text, off = _lesen(pfad)
    assert "städtischen" in text and "Wirtschaftsplan" in text
    assert text[off[1]:].startswith("Der Wirtschaftsplan") and text[off[2]:] == "Ende."
    # Ein zweiter Lauf findet nichts mehr.
    assert skript.main(["--db", str(pfad), "--schreiben"])["anlagen"] == 0


def test_abgebrochener_lauf_verschiebt_die_seiten_nicht_ein_zweites_mal(tmp_path):
    """Zwei Zeilen am Punkt teilen sich die Seitenanfänge. Ist die erste schon
    repariert (der Lauf brach danach ab), darf die zweite die neuen Anfänge
    nicht noch einmal verschieben (Review 23.11.2026)."""
    from council import unterlagen_seiten
    from council.anlagentext import gespeicherten_text_reparieren

    pfad = tmp_path / "council.sqlite"
    store = CouncilStore(pfad)
    alt = "".join(SEITEN)
    offsets = [0, len(SEITEN[0]), len(SEITEN[0]) + len(SEITEN[1])]
    neu, neu_off = gespeicherten_text_reparieren(alt, offsets)
    with store._conn:
        for ksinr, text in ((1, neu), (2, alt)):   # Zeile 1 repariert, Zeile 2 noch nicht
            store._conn.execute("INSERT INTO council_agenda_attachments (ksinr, item_number, label, url, raw_text, "
                                "document_id) VALUES (?, 'Ö 1', 'Bericht', 'u', ?, 77)", (ksinr, text))
    store.save_document_profile(77, "report", page_offsets=neu_off, text_hash=unterlagen_seiten.text_hash(neu))
    store.close()
    skript.main(["--db", str(pfad), "--schreiben"])
    store = CouncilStore(pfad)
    texte = [r[0] for r in store._conn.execute("SELECT raw_text FROM council_agenda_attachments ORDER BY ksinr")]
    off = json.loads(store._conn.execute("SELECT page_offsets FROM council_documents WHERE document_id = 77").fetchone()[0])
    store.close()
    assert texte == [neu, neu] and off == neu_off
