"""Anlagen im Recherche-Prompt: Substanz statt Fußnote."""
from council.qa import ANLAGEN_ZEICHEN, _anlagen_block


def _anlage(nr, label, fundstelle):
    return {"nr": nr, "label": label, "vorlage_nr": "23/0211",
            "vorlage_titel": "Mobilitätsplan Oldenburg 2030",
            "fundstelle": fundstelle}


def test_fundstelle_wird_nicht_unter_ihrer_laenge_gekappt():
    """Die Suche liefert rund 1.100 Zeichen; bei 500 flog die Hälfte weg."""
    lang = "A" * 1100
    block = _anlagen_block([_anlage(1, "Gutachten Radverkehr", lang)])
    assert "A" * 1100 in block
    assert ANLAGEN_ZEICHEN >= 1100


def test_ueberlange_fundstelle_bleibt_begrenzt():
    block = _anlagen_block([_anlage(1, "Gutachten", "B" * 5000)])
    assert "B" * ANLAGEN_ZEICHEN in block
    assert "B" * (ANLAGEN_ZEICHEN + 1) not in block


def test_dieselbe_anlage_belegt_nur_einen_platz():
    """Byte-gleiche Dateien liegen doppelt im Bestand, mit eigener id."""
    block = _anlagen_block([
        _anlage(1, "TK 1 Langb Radverkehr Mobilitätsplan OL PGV", "erst"),
        _anlage(2, "TK 1 Langb Radverkehr Mobilitätsplan OL PGV", "zweit"),
        _anlage(3, "Zeitplanung Radverkehr 2030", "dritt"),
    ])
    assert block.count("TK 1 Langb Radverkehr") == 1
    assert "Zeitplanung Radverkehr 2030" in block


def test_ohne_anlagen_kein_block():
    assert _anlagen_block([]) == ""
    assert _anlagen_block(None) == ""
