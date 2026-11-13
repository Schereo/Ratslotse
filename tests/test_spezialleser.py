"""Spezialleser für Prüfvermerke und Abwägungstabellen (council/spezialleser.py)
— gegen selbst gebaute PDFs im Layout der echten (Schlussbericht 2025 zu
26/0674, Abwägung B-Plan 837 zu 26/0592)."""
from __future__ import annotations

import pytest

from council import document_types, spezialleser, template_dossier

pymupdf = pytest.importorskip("pymupdf")


def _schlussbericht() -> bytes:
    doc = pymupdf.open()
    legende = doc.new_page(width=595, height=842)
    # Die Legende setzt die Kennungen eingerückt — sie zählen nicht mit.
    legende.insert_text((102, 410), "B", fontname="hebo", fontsize=11)
    legende.insert_text((140, 410), "Beanstandung", fontsize=11)
    s = doc.new_page(width=595, height=842)
    s.insert_text((77, 120), "3.2.2", fontname="hebo", fontsize=11)
    s.insert_text((113, 120), "Vier-Augen-Prinzip", fontname="hebo", fontsize=11)
    s.insert_text((71, 160), "Auch 2025 fehlt die Funktionstrennung.", fontsize=11)
    s.insert_text((46, 200), "WB", fontname="hebo", fontsize=11)
    s.insert_text((71, 200), "Das Rechnungsprüfungsamt beanstandet die fehlende Funktions-", fontsize=11)
    s.insert_text((71, 214), "trennung bei der Vergabe von Benutzerrechten.", fontsize=11)
    s.insert_text((77, 260), "3.2.3", fontname="hebo", fontsize=11)
    s.insert_text((113, 260), "Software-Inventur", fontname="hebo", fontsize=11)
    s.insert_text((46, 300), "H", fontname="hebo", fontsize=11)
    s.insert_text((71, 300), "Das Rechnungsprüfungsamt wird den Prozess weiterhin verfolgen.", fontsize=11)
    return doc.tobytes()


def _abwaegung() -> bytes:
    doc = pymupdf.open()
    for nr, absender, vorschlag in ((1, "Feuerwehr", "Die Stellungnahme wird zur Kenntnis genommen."),
                                    (2, "Bürger 1", "Der Anregung wird nicht gefolgt."),
                                    (3, "Bürger 2", "Der Anregung wird gefolgt, die Begründung wird ergänzt.")):
        s = doc.new_page(width=842, height=595)
        s.insert_text((83, 155), "Nr.:", fontname="hebo", fontsize=10)
        s.insert_text((113, 155), "Schreiben", fontname="hebo", fontsize=10)
        s.insert_text((89, 190), str(nr), fontname="hebo", fontsize=10)
        s.insert_text((113, 190), "E-Mail vom", fontsize=10)
        s.insert_text((169, 190), absender, fontsize=10)
        s.insert_text((78, 250), "Stellungnahmen", fontname="hebo", fontsize=10)
        s.insert_text((425, 250), "Prüfungsvorschläge", fontname="hebo", fontsize=10)
        s.insert_text((78, 290), "Wir haben Bedenken gegen die Planung.", fontsize=10)
        s.insert_text((425, 290), vorschlag, fontsize=10)
    return doc.tobytes()


def test_pruefvermerke_mit_textziffer_ohne_legende():
    v = spezialleser.pruefvermerke(_schlussbericht())
    assert [(x["code"], x["tz"], x["heading"], x["page"]) for x in v] == [
        ("WB", "3.2.2", "Vier-Augen-Prinzip", 2), ("H", "3.2.3", "Software-Inventur", 2)]
    assert v[0]["text"].startswith("Das Rechnungsprüfungsamt beanstandet die fehlende Funktionstrennung")
    assert spezialleser.pruefvermerke_zusammenfassung(v) == "1 wiederholte Beanstandung, 1 Hinweis"


def test_abwaegung_zaehlt_ohne_namen():
    a = spezialleser.abwaegung(_abwaegung())
    assert a == {"statements": 3, "public": 2, "institutions": 1, "followed": 2, "not_followed": 1,
                 "noted": 1, "pages": 3}
    assert "Bürger" not in str(a) and "Feuerwehr" not in str(a)


def test_scan_ohne_tabelle():
    leer = pymupdf.open()
    leer.new_page()
    assert spezialleser.abwaegung(leer.tobytes()) is None
    assert spezialleser.pruefvermerke(leer.tobytes()) == []


def test_arten_erkannt():
    assert document_types.classify("Abwägung der Stellungnahmen") == "objection_table"
    assert document_types.classify("Abwägungssynopse - frühzeitige Beteiligung") == "objection_table"
    assert document_types.classify("Schlussbericht des Rechnungsprüfungsamtes über die Prüfung des "
                                   "Jahresabschlusses 2025") == "audit_report"
    assert document_types.classify("Stellungnahme des Seniorenbeirats") == "statement"


def test_dossier_bekommt_vermerke_als_belegbaren_block():
    notes = spezialleser.pruefvermerke(_schlussbericht())
    m = {"template": {"template_number": "26/0674", "title": "Jahresabschluss 2025", "raw_text": "Vorlage " * 20,
                      "document_id": 1, "office": None, "proposed_decision": None},
         "form": "F4",
         "documents": [
             {"document_id": 2, "label": "Schlussbericht des RPA", "doc_type": "audit_report", "text": "",
              "structure": {"summary": spezialleser.pruefvermerke_zusammenfassung(notes), "notes": notes}},
             {"document_id": 3, "label": "Abwägung", "doc_type": "objection_table", "text": "",
              "structure": spezialleser.abwaegung(_abwaegung())}]}
    nutzer, quellen, _ = template_dossier.build_input(m)
    assert '"pruefvermerke_A1": "1 wiederholte Beanstandung, 1 Hinweis"' in nutzer
    assert '"statements": 3' in nutzer and "Bürger" not in nutzer
    zitat = "Das Rechnungsprüfungsamt beanstandet die fehlende Funktionstrennung bei der Vergabe"
    assert template_dossier.evidence.locate(zitat, quellen["A1"], None) == (True, 2)
