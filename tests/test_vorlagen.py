"""Vorlagen-Ingestion: vo0050-Parsing, Auszug-Heuristik, Store-Roundtrip, FTS."""
from __future__ import annotations

import pytest

from council import vorlagen
from council.scraper import AgendaItem, CouncilSession
from council.store import CouncilStore

# Nachbau der echten vo0050-Struktur (SessionNet SMC): Metadaten als
# div-Tabelle, jedes Dokument mit Icon- und Label-Link auf getfile.php.
VO_HTML = """<html><body>
<div class="smc-table-row"><div class="smc-table-cell smc-cell-head vobetr_title">Betreff</div>
<div class="smc-table-cell vobetr">Radweg Haarenufer<br />- Beschlussantrag</div></div>
<div class="smc-table-row"><div class="smc-table-cell smc-cell-head voname_title">Vorlage</div>
<div class="smc-table-cell voname">26/0330</div></div>
<div class="smc-table-row"><div class="smc-table-cell smc-cell-head vovaname_title">Art</div>
<div class="smc-table-cell vovaname">Beschlussvorlage</div></div>
<a href="getfile.php?id=307787&amp;type=do"><img alt="" /></a>
<a href="getfile.php?id=307787&amp;type=do" title="Dokument Download Dateityp: pdf">Vorlage</a>
<a href="getfile.php?id=307786&amp;type=do">Anlage - Lageplan</a>
</body></html>"""


def test_parse_vorlage_page():
    meta = vorlagen.parse_vorlage_page(VO_HTML)
    assert meta["vorlage_nr"] == "26/0330"
    assert meta["title"].startswith("Radweg Haarenufer")
    assert meta["art"] == "Beschlussvorlage"
    # Haupt-PDF ist der Link mit Label "Vorlage" — nicht die Anlage.
    assert meta["document_id"] == 307787
    assert "getfile.php?id=307787" in meta["document_url"]


def test_parse_vorlage_page_invalid_and_no_pdf():
    assert vorlagen.parse_vorlage_page("<html><body>Fehlermeldung</body></html>") is None
    no_pdf = vorlagen.parse_vorlage_page(VO_HTML.replace(">Vorlage</a>", ">Entwurf</a>"))
    assert no_pdf is not None and no_pdf["document_url"] is None


def test_excerpt_prefers_sachverhalt_over_beschlussvorschlag():
    raw = (
        "Stadt Oldenburg\nSeite: 1/3 01.02.2026\n"
        "Beschlussvorschlag:\nDer Rat beschließt den Bau.\n"
        "Sachverhalt:\nDie Stadt plant einen Radweg am Haarenufer, weil dort viele Menschen radeln.\n"
        "Seite: 2/3"
    )
    out = vorlagen.excerpt(raw, 300)
    assert out.startswith("Sachverhalt")
    assert "Radweg am Haarenufer" in out
    assert "Seite:" not in out  # Seiten-Boilerplate entfernt


def test_excerpt_fallback_and_word_boundary():
    # Ohne Sachverhalt/Begründung: Beschlussvorschlag als Fallback.
    out = vorlagen.excerpt("Kopfzeile\nBeschlussvorschlag: Es wird beschlossen.", 300)
    assert out.startswith("Beschlussvorschlag")
    # Kürzung an Wortgrenze mit Ellipse.
    long = "Sachverhalt: " + "Wort " * 200
    cut = vorlagen.excerpt(long, 100)
    assert len(cut) <= 102 and cut.endswith("…") and not cut.endswith("Wor …")
    assert vorlagen.excerpt("", 100) == ""


@pytest.fixture
def store(tmp_path):
    s = CouncilStore(tmp_path / "council.sqlite")
    yield s
    s.close()


def _seed_session(store, ksinr=1, kvonr=555, vorlage_nr="26/0330"):
    store.save_session(CouncilSession(
        ksinr, "Rat der Stadt", "2026-01-01", "18:00", "Rathaus",
        agenda_items=[AgendaItem("Ö 1", "Radweg Haarenufer", vorlage_nr=vorlage_nr, kvonr=kvonr)],
    ))


def test_vorlagen_store_roundtrip(store):
    _seed_session(store)
    assert store.missing_vorlage_kvonrs() == [555]
    store.save_vorlage({
        "kvonr": 555, "vorlage_nr": "26/0330", "title": "Radweg Haarenufer",
        "art": "Beschlussvorlage", "document_id": 1, "document_url": "https://x/pdf",
        "raw_text": "Sachverhalt: Es soll ein Radweg gebaut werden.", "n_pages": 2, "status": "ok",
    })
    assert store.missing_vorlage_kvonrs() == []
    v = store.get_vorlage_by_nr("26/0330")
    assert v["title"] == "Radweg Haarenufer" and v["kvonr"] == 555
    # Revisions-Nummer fällt auf die Basis-Vorlage zurück; Unbekanntes → None.
    assert store.get_vorlage_by_nr("26/0330/1")["kvonr"] == 555
    assert store.get_vorlage_by_nr("99/9999") is None
    assert store.get_vorlage_by_nr("") is None
    texts = store.vorlage_texts_for(["26/0330", "", None, "99/9999"])
    assert texts == {"26/0330": "Sachverhalt: Es soll ein Radweg gebaut werden."}


def test_vorlagen_failed_is_retried_no_pdf_is_not(store):
    _seed_session(store, kvonr=7, vorlage_nr="26/0001")
    store.mark_vorlage_failed(7)
    assert store.missing_vorlage_kvonrs() == [7]  # failed → beim nächsten Lauf erneut
    store.save_vorlage({"kvonr": 7, "vorlage_nr": "26/0001", "status": "no_pdf"})
    assert store.missing_vorlage_kvonrs() == []   # no_pdf → nicht erneut


def test_fts_includes_vorlage_text(store):
    _seed_session(store)
    store._insert_decision(1, 0, "decision", None, "Ö 1", "Radweg Haarenufer", "Wird gebaut.",
                           "angenommen", None, None, None, [], "26/0330", None, None)
    store._conn.commit()
    store.save_vorlage({"kvonr": 555, "vorlage_nr": "26/0330", "status": "ok",
                        "raw_text": "Im Sachverhalt geht es um Quartiersgaragen am Hafen."})
    assert store.rebuild_fts() == 1
    # "Quartiersgaragen" steht NUR im Vorlagen-Text — der Treffer beweist den Join.
    hits = store.search_decisions_fts("Quartiersgaragen")
    assert len(hits) == 1


def test_qa_context_includes_vorlage_excerpt():
    from council.qa import _build_context
    ctx = _build_context([{
        "id": 5, "title": "Radweg", "committee": "Rat", "session_date": "2026-01-01",
        "outcome": "angenommen", "summary": "Kurz.",
        "vorlage_excerpt": "Sachverhalt: Darum geht es wirklich.",
    }])
    assert "— Aus der Vorlage: Sachverhalt: Darum geht es wirklich." in ctx
    # Ohne Auszug bleibt die Zeile unverändert schlank.
    assert "Aus der Vorlage" not in _build_context([{"id": 6, "title": "X", "summary": "S"}])
