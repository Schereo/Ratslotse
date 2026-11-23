"""Unterlagen als eigene Schicht (docs/plan-vorlagen-aufbereiten.md, PR 6):
Kennung, Steckbrief, Seiten, Art — und dass das Neu-Einlesen nichts verliert."""
from __future__ import annotations

import json
from datetime import date, timedelta

from council import document_types, unterlagen_seiten as us
from council.scraper import AgendaItem, CouncilSession
from council.store import CouncilStore

URL = "https://buergerinfo.oldenburg.de/getfile.php?id={}&type=do"


def _sitzung(anlagen):
    tag = (date.today() + timedelta(days=5)).isoformat()
    punkt = AgendaItem(item_number="Ö 13.2", title="Beratende Mitglieder", template_number="26/0796",
                       kvonr=None, is_public=True, anlagen=anlagen)
    return CouncilSession(ksinr=4709, committee="Rat", session_date=tag, session_time="18:00",
                          location="PFL", agenda_items=[punkt])


def test_sitzung_zweimal_einlesen_verliert_weder_kennung_noch_text_noch_steckbrief(tmp_path):
    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        anlagen = [{"label": "Vorlage", "url": URL.format(315090)},
                   {"label": "2026-10-31 Reduzierung Anzahl beratende Mitglieder", "url": URL.format(315835)}]
        store.save_session(_sitzung(anlagen))
        store.set_punkt_anlagentext(URL.format(315835), "Fraktion Bündnis 90/Die Grünen\nÄnderungsantrag zu TOP 13.2")
        store.save_document_profile(315835, "amendment", applicants=["Grüne"], n_pages=2)
        store.save_session(_sitzung(anlagen))   # der nächste Abgleich
        r = store._conn.execute(
            "SELECT document_id, raw_text FROM council_agenda_attachments WHERE url = ?",
            (URL.format(315835),)).fetchone()
        assert r["document_id"] == 315835
        assert "Änderungsantrag" in r["raw_text"]
        docs = store.item_documents(4709, "Ö 13.2")
        assert [(d["document_id"], d["doc_type"]) for d in docs] == [(315835, "amendment")]
        assert docs[0]["applicants"] == ["Grüne"]
    finally:
        store.close()


def test_art_aus_label_und_kopf():
    assert document_types.classify("Änderungsantrag CDU Geschäftsordnung") == "amendment"
    assert document_types.classify("Berichtsantrag FDP") == "report_request"
    assert document_types.classify("Dringlichkeitsantrag CDU Hauptsatzung") == "motion"
    assert document_types.classify("Synopse alt/neu") == "synopsis"
    assert document_types.classify("Satzung über die Erhebung von Gebühren") == "statute"
    assert document_types.classify("Planzeichnung") == "plan"
    assert document_types.classify("Vorlage") == "template"
    # Ö 13.2: Das Label sagt nichts, der Kopf alles.
    label = "2026-10-31 Reduzierung Anzahl beratende Mitglieder"
    assert document_types.classify(label) == "other"
    assert document_types.classify(label, "Fraktion Bündnis 90/Die Grünen\nÄnderungsantrag zu TOP 13.2") == "amendment"
    # Rangfolge: Anträge vor Satzungen, ein Änderungsantrag zur Satzung ist ein Antrag.
    assert document_types.classify("Änderungsantrag zur Satzung") == "amendment"
    assert document_types.rank("amendment") < document_types.rank("statute") < document_types.rank("other")


def test_vorlagenseiten_aus_dem_druckkopf():
    t = ("Beschlussvorschlag:\nText eins\n\nAusdruck vom: 22.10.2026\nSeite: 2/3\nText zwei\n"
         "Ausdruck vom: 22.10.2026\nSeite: 3/3\nText drei\n")
    off = us.template_page_offsets(t)
    assert off is not None and len(off) == 3 and off[0] == 0
    assert t[off[1]:].startswith("Ausdruck vom")
    assert us.page_of(off, t.index("Text zwei")) == 2
    assert us.page_of(off, t.index("Text drei")) == 3
    # Lückenhaft (Seite 2 fehlt) heißt: lieber kein Seitensprung als ein falscher.
    assert us.template_page_offsets("a\nSeite: 3/3\nb") is None


def test_seitenanker_ueberleben_die_bereinigung():
    seiten = ["Antrag der Fraktion\nWir bean-\ntragen folgende Änderung am Paragraphen", "",
              "Begründung: Die bisherige Regelung hat sich nicht bewährt und wird ersetzt."]
    gespeichert = ("Antrag der Fraktion Wir beantragen folgende Änderung am Paragraphen\n"
                   "Begründung: Die bisherige Regelung hat sich nicht bewährt und wird ersetzt.")
    off = us.anchor_offsets(seiten, gespeichert)
    assert off is not None and len(off) == 3
    assert gespeichert[off[2]:].startswith("Begründung")
    assert off[1] == off[2]   # die leere Seite erbt den Anfang der nächsten
    assert us.page_of(off, gespeichert.index("bewährt")) == 3
    assert us.anchor_offsets(seiten, "ein ganz anderer Text ohne jede Übereinstimmung mit den Seiten") is None


# --- Eine Stelle in einer Unterlage (Notiz-Verweis → „Im Chat fragen“) ------

SEITEN = ["Seite eins: Anlass", "Seite zwei: Kosten 4 Mio. €", "Seite drei: Zeitplan"]
TEXT = "\n".join(SEITEN)
OFFSETS = [0, len(SEITEN[0]) + 1, len(SEITEN[0]) + len(SEITEN[1]) + 2]


def test_eine_stelle_in_einer_anlage_ist_genau_ihre_seite(tmp_path):
    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        store.save_anlagen(30078, [{"document_id": 312295, "label": "Anlage 1 Tarife", "url": URL.format(312295),
                                    "raw_text": TEXT, "status": "ok"}])
        store.save_document_profile(312295, "other", n_pages=3, page_offsets=OFFSETS)
        s = store.document_page(312295, 2)
        assert (s["kind"], s["label"], s["page"], s["n_pages"]) == ("attachment", "Anlage 1 Tarife", 2, 3)
        assert s["text"] == "Seite zwei: Kosten 4 Mio. €" and not s["whole"]
        # Eine Seite, die es nicht gibt, hat keinen Text — kein Raten.
        assert store.document_page(312295, 9)["text"] is None
        # Ohne Seite: der Anfang der ganzen Unterlage.
        ganz = store.document_page(312295, None)
        assert ganz["whole"] and "Zeitplan" in ganz["text"]
        # Eine Kennung, die keine Unterlage ist.
        assert store.document_page(999, 1) is None
    finally:
        store.close()


def test_ohne_seitengrenzen_oder_ohne_text_sagt_die_stelle_das(tmp_path):
    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        store.save_anlagen(30078, [
            {"document_id": 1, "label": "ohne Steckbrief", "url": URL.format(1), "raw_text": TEXT, "status": "ok"},
            {"document_id": 2, "label": "Scan", "url": URL.format(2), "status": "listed"}])
        ohne = store.document_page(1, 2)
        assert ohne["whole"] and ohne["text"].startswith("Seite eins")
        scan = store.document_page(2, 1)
        assert scan["label"] == "Scan" and scan["text"] is None
    finally:
        store.close()


def test_vorlage_und_protokoll_sind_auch_unterlagen(tmp_path):
    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        store.save_vorlage({"kvonr": 30078, "template_number": "26/0622", "title": "VBN-Tarifanpassung",
                            "document_id": 312296, "document_url": URL.format(312296), "raw_text": TEXT})
        store.save_document_profile(312296, "template", n_pages=3, page_offsets=OFFSETS)
        v = store.document_page(312296, 3)
        assert (v["kind"], v["label"], v["text"]) == ("template", "Vorlage 26/0622", "Seite drei: Zeitplan")
        store._conn.execute(
            "INSERT INTO council_protocols (ksinr, document_id, document_url, protocol_nr, raw_text, "
            "page_offsets, extracted_at) VALUES (4702, 314487, ?, '12/2026', ?, ?, '2026-09-01')",
            (URL.format(314487), TEXT, json.dumps(OFFSETS)))
        p = store.document_page(314487, 1)
        assert (p["kind"], p["label"], p["text"]) == ("protocol", "Protokoll 12/2026", "Seite eins: Anlass")
    finally:
        store.close()
