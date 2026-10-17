"""Das Neulesen des Bestands (``scripts/pdf_neu_lesen.py``).

Was hier festgehalten wird, sind die Riegel: Ohne ``--ausfuehren`` bleibt die
Datenbank unberührt; Haushalts-Anlagen werden nie angefasst; ein Protokoll,
dessen Seitenzahl sich ändert, wird nicht überschrieben; und ein zweiter Lauf
setzt fort, statt alles noch einmal zu laden. Download und PDF-Lesen sind
Attrappen — die Suite fasst nichts Echtes an, und PyMuPDF fehlt in der CI.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

from council import anlagentext
from council.store import CouncilStore

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("pdf_neu_lesen", ROOT / "scripts" / "pdf_neu_lesen.py")
pnl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pnl)

ALT = "Im Falle einer Verringerung de r Ausstattung gelten die Arbei tsverträge weiter."
NEU = "Im Falle einer Verringerung der Ausstattung gelten die Arbeitsverträge weiter."


class _Antwort:
    def __init__(self, url: str) -> None:
        self.content = url.encode()

    def raise_for_status(self) -> None:
        pass


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Eine Vorlage, zwei Protokolle (eins bleibt bei 3 Seiten, eins hätte 2),
    eine gewöhnliche und eine Haushalts-Anlage — alle mit pypdf-Rissen."""
    pfad = tmp_path / "council.sqlite"
    cs = CouncilStore(pfad)
    c = cs._conn
    c.execute("INSERT INTO council_templates (kvonr, template_number, title, document_url, "
              "raw_text, n_pages, fetched_at, status, office) VALUES "
              "(10, '26/0001', 'Ausstattung der Fraktionsbüros', 'http://x/v10', ?, 1, "
              "datetime('now'), 'ok', 'altes Amt')", (ALT,))
    for ksinr in (20, 21):
        c.execute("INSERT INTO council_protocols (ksinr, document_url, raw_text, n_pages, "
                  "extracted_at) VALUES (?, ?, ?, 3, datetime('now'))",
                  (ksinr, f"http://x/p{ksinr}", ALT))
    c.execute("INSERT INTO council_templates (kvonr, template_number, title, fetched_at) "
              "VALUES (11, '26/0002', 'Jahresabschluss 2025 der Stadt', datetime('now'))")
    c.executemany("INSERT INTO council_attachments (document_id, kvonr, label, url, raw_text, "
                  "n_pages, status, fetched_at) VALUES (?, ?, ?, ?, ?, 1, 'ok', datetime('now'))",
                  [(30, 10, "Antrag CDU", "http://x/a30", ALT * 4),
                   (31, 11, "Jahresabschluss 2025", "http://x/a31", ALT * 4)])
    c.commit()
    cs.close()

    def seiten(daten: bytes, extraktor: str = anlagentext.PYMUPDF) -> list[str]:
        assert extraktor == anlagentext.PYMUPDF
        url = daten.decode()
        if url.endswith("p21"):
            return [NEU, ""]  # zwei Seiten statt drei
        if url.endswith("p20"):
            return [NEU, "", ""]
        return [NEU * 4 if "/a" in url else NEU]

    geladen: list[str] = []
    sitzung = types.SimpleNamespace(get=lambda url, timeout: geladen.append(url) or _Antwort(url))
    monkeypatch.setattr(pnl, "_session", sitzung)
    monkeypatch.setattr(pnl.anlagentext, "pdf_seiten", seiten)
    monkeypatch.setitem(sys.modules, "pymupdf", types.ModuleType("pymupdf"))
    return pfad, geladen


def _lesen(pfad: Path, sql: str, *werte):
    cs = CouncilStore(pfad)
    try:
        return cs._conn.execute(sql, werte).fetchone()[0]
    finally:
        cs.close()


def test_wortrisse_zaehlt_die_luecken():
    # „de r“ zählt bewusst nicht: Paare unter vier Buchstaben wären Rauschen
    # (wie in der Messung in council/anlagentext.py).
    assert pnl.wortrisse(ALT, NEU) == 1
    assert pnl.wortrisse(NEU, ALT) == 0


def test_haushalts_anlagen_sind_keine_kandidaten(db):
    pfad, _ = db
    cs = CouncilStore(pfad)
    try:
        assert [z["id"] for z in pnl.kandidaten(cs, "anlagen")] == [30]
    finally:
        cs.close()


def test_trockenlauf_schreibt_nichts(db):
    pfad, geladen = db
    bericht = pnl.main(["--db", str(pfad), "--abstand", "0"])
    assert _lesen(pfad, "SELECT raw_text FROM council_templates WHERE kvonr = 10") == ALT
    assert _lesen(pfad, "SELECT raw_text FROM council_protocols WHERE ksinr = 20") == ALT
    assert bericht["vorlagen"]["wuerde_geaendert"] == 1
    assert bericht["protokolle"]["wuerde_geaendert"] == 1
    assert bericht["protokolle"]["gesperrt:Seitenzahl"] == 1
    assert bericht["vorlagen"]["risse_vorher"] == 1 and bericht["vorlagen"]["risse_nachher"] == 0
    assert "http://x/a31" not in geladen
    assert not (pfad.parent / pnl.FORTSCHRITT).exists()


def test_ausfuehren_schreibt_und_setzt_fort(db):
    pfad, geladen = db
    bericht = pnl.main(["--db", str(pfad), "--abstand", "0", "--ausfuehren"])
    assert _lesen(pfad, "SELECT raw_text FROM council_templates WHERE kvonr = 10") == NEU
    # Die Ernte zieht mit — über das UPDATE, nicht über save_vorlage, das per
    # INSERT OR REPLACE alle übrigen Spalten zurücksetzte.
    assert _lesen(pfad, "SELECT template_number FROM council_templates WHERE kvonr = 10") == \
        "26/0001"
    assert _lesen(pfad, "SELECT raw_text FROM council_protocols WHERE ksinr = 20") == "\n".join(
        [NEU, "", ""])
    assert _lesen(pfad, "SELECT page_offsets FROM council_protocols WHERE ksinr = 20") == \
        f"[0, {len(NEU) + 1}, {len(NEU) + 2}]"
    # Seitenzahl geändert: bleibt, wie es war.
    assert _lesen(pfad, "SELECT raw_text FROM council_protocols WHERE ksinr = 21") == ALT
    assert _lesen(pfad, "SELECT raw_text FROM council_attachments WHERE document_id = 30") == \
        NEU * 4
    assert _lesen(pfad, "SELECT raw_text FROM council_attachments WHERE document_id = 31") == \
        ALT * 4
    assert bericht["protokolle"]["geschrieben"] == 1

    geladen.clear()
    pnl.main(["--db", str(pfad), "--abstand", "0", "--ausfuehren"])
    # Ein zweiter Lauf lädt nichts noch einmal — auch das gesperrte Protokoll
    # nicht; es steht im Bericht des ersten Laufs.
    assert geladen == []


def test_nur_anders_umbrochen_wird_nicht_geschrieben(db, monkeypatch):
    """Dieselben Wörter, andere Zeilenumbrüche: kein Gewinn, aber ein neues
    Embedding. Die 20 neuesten Vorlagen waren am 17.10.2026 alle so."""
    pfad, _ = db
    echt = pnl.anlagentext.pdf_seiten
    monkeypatch.setattr(pnl.anlagentext, "pdf_seiten", lambda daten, extraktor="pymupdf": (
        [ALT.replace(" gelten", "\ngelten")] if daten.decode().endswith("v10")
        else echt(daten, extraktor)))
    bericht = pnl.main(["--db", str(pfad), "--abstand", "0", "--ausfuehren", "--art", "vorlagen"])
    assert bericht["vorlagen"]["nur_leerraum"] == 1
    assert _lesen(pfad, "SELECT raw_text FROM council_templates WHERE kvonr = 10") == ALT


def test_ohne_pymupdf_bricht_er_ab(db, monkeypatch):
    """Sonst läse der Lauf den Bestand mit pypdf NEU — Stunden für nichts."""
    pfad, geladen = db
    monkeypatch.setitem(sys.modules, "pymupdf", None)
    assert pnl.main(["--db", str(pfad), "--abstand", "0", "--ausfuehren"]) == {
        "abgebrochen": "pymupdf fehlt"}
    assert geladen == []
