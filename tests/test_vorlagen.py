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


def test_parties_in_text():
    from council.parties import parties_in_text
    assert parties_in_text("Antrag SPD CDU Grüne FDP Vernunft 2026 Juni") == ["Grüne", "SPD", "CDU", "FDP"]
    assert parties_in_text("Änderungsantrag der Gruppe FDP/Volt") == ["FDP", "Volt"]
    # Wortgrenzen: „Begrünung" ist keine Partei, „Revolte" kein Volt.
    assert parties_in_text("Antrag zur Begrünung der Revolte") == []
    assert parties_in_text("Antrag der SPD-Fraktion vom 10.03.2026") == ["SPD"]
    assert parties_in_text("") == [] and parties_in_text(None) == []


def test_parse_vorlage_page_collects_anlagen():
    meta = vorlagen.parse_vorlage_page(VO_HTML)
    assert len(meta["anlagen"]) == 1
    assert meta["anlagen"][0]["document_id"] == 307786
    assert meta["anlagen"][0]["label"] == "Anlage - Lageplan"


def test_build_anlage_rows_classifies_antraege():
    rows = vorlagen._build_anlage_rows([
        {"document_id": 1, "url": "https://x/1", "label": "Anlage - Lageplan"},
        {"document_id": 2, "url": "https://x/2", "label": "Antrag der SPD-Fraktion vom 10.03.2026"},
    ])
    plan, antrag = rows[0], rows[1]
    assert plan["is_antrag"] == 0 and plan["status"] == "listed" and plan["antragsteller"] == []
    # Antrag: als solcher erkannt + Antragsteller aus dem Label; der PDF-Download
    # schlägt gegen https://x/2 fehl → status failed, aber die Zeile bleibt nutzbar.
    assert antrag["is_antrag"] == 1
    assert antrag["antragsteller"] == ["SPD"]
    assert antrag["status"] == "failed"
    # skip_document_ids: bekannter Antrag wird nicht erneut geladen (kein Download-Versuch).
    skipped = vorlagen._build_anlage_rows(
        [{"document_id": 2, "url": "https://x/2", "label": "Antrag der SPD-Fraktion"}],
        skip_document_ids=frozenset({2}),
    )[0]
    assert skipped["is_antrag"] == 0 and skipped["status"] == "listed"


def test_anlagen_store_and_stats(store):
    _seed_session(store)  # ksinr=1, kvonr=555, "26/0330", Rat der Stadt, 2026-01-01
    store.save_vorlage({"kvonr": 555, "vorlage_nr": "26/0330", "status": "ok", "raw_text": "Sachverhalt: X."})
    store._insert_decision(1, 0, "decision", None, "Ö 1", "Radweg", "Wird gebaut.",
                           "angenommen", None, None, None, [], "26/0330", None, None)
    store._conn.commit()
    n = store.save_anlagen(555, [
        {"document_id": 90, "url": "https://x/90", "label": "Antrag der SPD-Fraktion",
         "is_antrag": 1, "antragsteller": ["SPD"], "raw_text": "Die SPD beantragt…", "n_pages": 2, "status": "ok"},
        {"document_id": 91, "url": "https://x/91", "label": "Anlage - Lageplan", "status": "listed"},
    ])
    assert n == 2
    # scanned-Markierung + Idempotenz (bestehende IDs bleiben, rowcount 0)
    assert store.kvonrs_without_anlagen_scan() == []
    assert store.save_anlagen(555, [{"document_id": 90, "url": "u", "label": "l"}]) == 0
    # Decision-Page-Liste: Antrag zuerst, Antragsteller geparst
    anlagen = store.anlagen_for_vorlage_nr("26/0330")
    assert [a["document_id"] for a in anlagen] == [90, 91]
    assert anlagen[0]["antragsteller"] == ["SPD"]
    # Erfolgsquote: 1 SPD-Antrag, Vorlage im Rat angenommen
    stats = store.antrag_stats()
    assert stats["n_antraege"] == 1 and stats["n_mit_beschluss"] == 1
    assert stats["parties"] == [{"party": "SPD", "n": 1, "angenommen": 1, "abgelehnt": 0}]


def test_antrag_stats_prefers_rat_decision(store):
    """Ausschuss lehnt ab, der Rat nimmt an → es zählt der Rat."""
    store.save_session(CouncilSession(10, "Bauausschuss", "2026-01-10", "17:00", "Rathaus",
                                      agenda_items=[AgendaItem("Ö 2", "X", vorlage_nr="26/0500", kvonr=700)]))
    store.save_session(CouncilSession(11, "Rat der Stadt", "2026-02-01", "17:00", "Rathaus"))
    store._insert_decision(10, 0, "decision", None, "Ö 2", "X", "B", "abgelehnt", None, None, None, [], "26/0500", None, None)
    store._insert_decision(11, 0, "decision", None, "Ö 9", "X", "B", "angenommen", None, None, None, [], "26/0500", None, None)
    store._conn.commit()
    store.save_vorlage({"kvonr": 700, "vorlage_nr": "26/0500", "status": "ok"})
    store.save_anlagen(700, [{"document_id": 95, "url": "u", "label": "Antrag der CDU-Fraktion",
                              "is_antrag": 1, "antragsteller": ["CDU"], "status": "ok"}])
    stats = store.antrag_stats()
    assert stats["parties"] == [{"party": "CDU", "n": 1, "angenommen": 1, "abgelehnt": 0}]


def test_fts_includes_antrag_text(store):
    _seed_session(store)
    store._insert_decision(1, 0, "decision", None, "Ö 1", "Radweg", "Wird gebaut.",
                           "angenommen", None, None, None, [], "26/0330", None, None)
    store._conn.commit()
    store.save_vorlage({"kvonr": 555, "vorlage_nr": "26/0330", "status": "ok", "raw_text": "Sachverhalt."})
    store.save_anlagen(555, [{"document_id": 90, "url": "u", "label": "Antrag der SPD-Fraktion",
                              "is_antrag": 1, "antragsteller": ["SPD"], "status": "ok",
                              "raw_text": "Wir beantragen Lastenradstellplätze am Bahnhof."}])
    store.rebuild_fts()
    # "Lastenradstellplätze" steht NUR im Antrags-PDF — der Treffer beweist den Join.
    assert len(store.search_decisions_fts("Lastenradstellplätze")) == 1


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


def test_qa_context_marks_impact_extremes_only():
    """Tragweite fließt als Hinweis in den QA-Kontext — aber nur an den Skalen-Enden
    (hoch mit Begründung, gering als Formalie); das Mittelfeld bleibt still."""
    from council.qa import _build_context

    hoch = _build_context([{"id": 1, "title": "Haushalt", "summary": "S",
                            "impact": 85, "impact_reason": "Bindet Millionen."}])
    assert "— Tragweite: hoch (Bindet Millionen.)" in hoch
    gering = _build_context([{"id": 2, "title": "Berufung", "summary": "S", "impact": 5}])
    assert "— Tragweite: gering (Formalie)" in gering
    mitte = _build_context([{"id": 3, "title": "B-Plan", "summary": "S", "impact": 50}])
    assert "Tragweite" not in mitte
    ohne = _build_context([{"id": 4, "title": "Neu", "summary": "S"}])
    assert "Tragweite" not in ohne


def test_list_entities_recency_and_trending_tags(store):
    """Aktualitäts-Felder je Entity + Trend-Tags der letzten Monate."""
    from datetime import date, timedelta
    recent = (date.today() - timedelta(days=30)).isoformat()
    old = "2019-05-01"
    store.save_session(CouncilSession(1, "Rat der Stadt", recent, "17:00", "Rathaus"))
    store.save_session(CouncilSession(2, "Rat der Stadt", old, "17:00", "Rathaus"))
    for ks, tags in [(1, '["Radverkehr", "Wärmeplanung"]'), (2, '["Radverkehr"]')]:
        store._insert_decision(ks, 0, "decision", None, "Ö 1", f"D{ks}", "B", "angenommen",
                               None, None, None, [], None, None, None)
    with store._conn:
        store._conn.execute("UPDATE council_decisions SET policy_tags='[\"Radverkehr\", \"Wärmeplanung\"]' WHERE ksinr=1")
        store._conn.execute("UPDATE council_decisions SET policy_tags='[\"Radverkehr\"]' WHERE ksinr=2")
        ids = [r[0] for r in store._conn.execute("SELECT id FROM council_decisions ORDER BY id").fetchall()]
        # Entity „aktiv": Beschluss von vor 30 Tagen; „ruhend": nur 2019.
        store._conn.execute("INSERT INTO council_entities (id, slug, name, kind, n) VALUES (1,'aktiv','Aktiv','ort',1)")
        store._conn.execute("INSERT INTO council_entities (id, slug, name, kind, n) VALUES (2,'ruhend','Ruhend','ort',5)")
        store._conn.execute("INSERT INTO council_entity_links VALUES (1, ?)", (ids[0],))
        store._conn.execute("INSERT INTO council_entity_links VALUES (2, ?)", (ids[1],))
    ents = {e["slug"]: e for e in store.list_entities()}
    assert ents["aktiv"]["n_recent"] == 1 and ents["aktiv"]["last_date"] == recent
    assert ents["ruhend"]["n_recent"] == 0 and ents["ruhend"]["last_date"] == old
    # Trending: nur der junge Beschluss zählt → Radverkehr 1, Wärmeplanung 1; alt fällt raus.
    tags = {t["tag"]: t["n"] for t in store.trending_tags(days_back=180)}
    assert tags == {"Radverkehr": 1, "Wärmeplanung": 1}


def test_parties_for_faction_gruppen_multi_mapping():
    """Gruppen-Anträge zählen für jede beteiligte Partei; Non-Parteien nicht."""
    from council.parties import parties_for_faction
    assert parties_for_faction("Gruppe FDP/Volt") == ["FDP", "Volt"]
    assert parties_for_faction("FDP/Volt-Gruppe") == ["FDP", "Volt"]
    assert parties_for_faction("SPD-Fraktion") == ["SPD"]
    assert parties_for_faction("Verwaltung") == []
    assert parties_for_faction("WFO/LKR") == []  # keine Partei mehr
    assert parties_for_faction(None) == []


def test_decision_row_zaehlt_gruppe_fuer_beide_parteien(store):
    _seed_session(store)
    store._insert_decision(1, 0, "decision", None, "Ö 1", "Radweg", "B", "angenommen",
                           None, None, None, ["Gruppe FDP/Volt"], None, None, None)
    store._conn.commit()
    d = store.get_decisions(1)[0]
    assert d["parties"] == ["FDP", "Volt"]
    # decision_ids_for_party findet den Beschluss über BEIDE Parteien
    assert store.decision_ids_for_party("FDP") == [d["id"]]
    assert store.decision_ids_for_party("Volt") == [d["id"]]


def test_suggested_entity_topics_prefers_concrete_active(store):
    """Themen-Vorschläge: konkrete Orte/Projekte mit jüngster Aktivität —
    Organisationen, Einzeltreffer und Altbestand fliegen raus."""
    from datetime import date, timedelta
    recent = (date.today() - timedelta(days=30)).isoformat()
    store.save_session(CouncilSession(1, "Rat der Stadt", recent, "17:00", "Rathaus"))
    store.save_session(CouncilSession(2, "Rat der Stadt", "2019-05-01", "17:00", "Rathaus"))
    with store._conn:
        for i in range(4):
            store._insert_decision(1, i, "decision", None, f"Ö {i}", f"D{i}", "B",
                                   "angenommen", None, None, None, [], None, None, None)
        store._insert_decision(2, 0, "decision", None, "Ö 9", "Alt", "B",
                               "angenommen", None, None, None, [], None, None, None)
        ids = [r[0] for r in store._conn.execute(
            "SELECT id FROM council_decisions ORDER BY id").fetchall()]
        ents = [(1, "veloroute-4", "Veloroute 4", "projekt", 3),
                (2, "haarenufer", "Haarenufer", "ort", 2),
                (3, "spd-fraktion", "SPD-Fraktion", "organisation", 4),
                (4, "einmal-ort", "Einmal-Ort", "ort", 1),
                (5, "alt-projekt", "Alt-Projekt", "projekt", 5)]
        for eid, slug, name, kind, n in ents:
            store._conn.execute(
                "INSERT INTO council_entities (id, slug, name, kind, n) VALUES (?,?,?,?,?)",
                (eid, slug, name, kind, n))
        store._conn.execute(
            "INSERT INTO council_entity_meta (slug, description) VALUES ('veloroute-4', "
            "'Geplanter Radschnellweg quer durch Oldenburg.')")
        links = [(1, ids[0]), (1, ids[1]), (1, ids[2]),   # Veloroute: 3 aktuelle
                 (2, ids[1]), (2, ids[3]),                # Haarenufer: 2 aktuelle
                 (3, ids[0]), (3, ids[1]), (3, ids[2]),   # Organisation: gefiltert
                 (4, ids[0]),                             # nur 1 Treffer → raus
                 (5, ids[4])]                             # nur Altbestand → raus
        store._conn.execute("UPDATE council_decisions SET interest = 80 WHERE id = ?", (ids[0],))
        for eid, did in links:
            store._conn.execute("INSERT INTO council_entity_links VALUES (?, ?)", (eid, did))
    got = store.suggested_entity_topics(days_back=180)
    assert [(g["name"], g["n_recent"]) for g in got] == [("Veloroute 4", 3), ("Haarenufer", 2)]
    assert got[0]["description"].startswith("Geplanter Radschnellweg")
