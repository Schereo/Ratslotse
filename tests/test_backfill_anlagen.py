"""Backfill der Anlagen-Volltexte (scripts/backfill_anlagen_texte.py)."""

def test_kaputte_zeichenzuordnung_zaehlt_wie_kein_text():
    """Glyph-Nummern statt Buchstaben sind kein Volltext.

    Der Schlussbericht des Rechnungsprüfungsamts zum Jahresabschluss 2024
    (Dokument 295296) liefert 460.084 Zeichen und keinen einzigen Buchstaben:
    Seine Schrift bringt keine ToUnicode-Tabelle mit, deshalb extrahiert pypdf
    „/1 /2 /3 …" und Kästchen. Ohne diese Prüfung stünde das im Volltextindex
    und damit in den Treffern der KI-Frage — und der Bericht sähe aus, als sei
    er gelesen worden.
    """
    from scripts.backfill_anlagen_texte import MIN_BUCHSTABEN, buchstabenanteil

    glyphen = "\u25a1\n/1 /2 /3 /4 /5 /6 \u25a1 /7 /8 /9 \u25a1 /10 /11 /12\n" * 40
    assert buchstabenanteil(glyphen) < MIN_BUCHSTABEN

    echt = ("Der Rat der Stadt Oldenburg beschließt den Jahresabschluss 2024 "
            "in der vorgelegten Fassung. Die Prüfung ergab keine Beanstandung.")
    assert buchstabenanteil(echt) > 0.6

    assert buchstabenanteil("") == 0.0
