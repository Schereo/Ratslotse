"""Grafiken eines Vorberichts als Daten (council/budget_charts.py) — die
Fälle stammen aus dem Vorbericht zum Haushaltsentwurf 2027 (Anlage 316689)."""
from __future__ import annotations

import pytest

from council import budget_charts as bc


def test_zahlen_wie_der_vorbericht_sie_schreibt():
    assert bc.parse_number("-24,8") == -24.8
    assert bc.parse_number("‐21.356.491") == -21356491.0          # U+2010 aus der Tabelle 2.1-1
    assert bc.parse_number("103.376.627,00 €") == 103376627.0
    assert bc.parse_number("6,2%") == 6.2
    assert bc.parse_number("2027") == 2027.0 and bc.parse_number("Plan") is None and bc.parse_number("1.2.3") is None


def test_tabelle_mit_kopf_und_bezeichnungen():
    kopf, zeilen = bc.from_table([
        ["", "Ist 2025", "Plan 2026", "Plan 2027"],
        ["geplante Aufnahme", "0,00 €", "0,00 €", "103.376.627,00 €"],
        ["Zinsaufwand für Liquiditätskredite", "0,00 €", None, "1.550.700,00 €"],
    ])
    assert kopf == ["Ist 2025", "Plan 2026", "Plan 2027"]
    assert zeilen[1] == {"label": "Zinsaufwand für Liquiditätskredite", "values": [0.0, None, 1550700.0]}


def test_diagrammgitter_ist_keine_tabelle():
    """find_tables hält die Gitterlinien eines Diagramms für eine Tabelle:
    21 Spalten, je Zeile ein verstreuter Wert (Grafik 2.1.1-1)."""
    gitter = [["48,4"] + [""] * 20, [""] * 4 + ["14,6 6,3"] + [""] * 16, [""] * 21]
    assert not bc.is_table(gitter)
    assert bc.is_table([["", "2026", "2027"], ["Erträge", "812,8", "766,4"], ["Aufwand", "883,9", "939,1"]])


def _wort(x, y, text, breite=20):
    return (x, y, x + breite, y + 9, text)


def _fehlbetraege():
    """Grafik 2.1.1-1 nachgestellt: die Werte stehen in der Textebene NICHT in
    Jahresfolge — 24,3 (2023) vor 14,6 (2022). Links die Achse, negative Werte
    unter der Nulllinie, die Jahre in einer Zeile."""
    jahre = [_wort(110 + 30 * i, 544, str(2020 + i)) for i in range(7)]
    achse = [_wort(80, y, t) for y, t in ((332, "80,0"), (366, "30,0"), (399, "-20,0"), (433, "-70,0"))]
    werte = [_wort(112, 344, "48,4"), _wort(141, 357, "29,7"), _wort(200, 360, "24,3"), _wort(171, 367, "14,6"),
             _wort(232, 373, "6,3"), _wort(258, 413, "-24,8"), _wort(288, 439, "-64,9")]
    titel = [_wort(140, 300, "Entwicklung"), _wort(200, 300, "der"), _wort(220, 300, "Fehlbeträge")]
    return werte + achse + jahre + titel


def test_diagramm_ordnet_nach_lage_nicht_nach_textfolge():
    kopf, reihen, beiwerk = bc.from_diagram(_fehlbetraege())
    assert kopf == [str(j) for j in range(2020, 2027)]
    assert reihen == [{"label": "Reihe 1", "values": [48.4, 29.7, 14.6, 24.3, 6.3, -24.8, -64.9]}]
    assert "Fehlbeträge" in beiwerk and "80,0" not in beiwerk       # die Achse ist kein Beiwerk und kein Wert
    assert bc.is_regular(reihen)


def test_plan_und_prognose_unter_dem_jahr_gehoeren_zur_kategorie():
    jahre = [_wort(100, 500, "2025"), _wort(160, 500, "2026"), _wort(220, 500, "2026"), _wort(280, 503, "2027")]
    zusatz = [_wort(160, 511, "Plan"), _wort(220, 511, "Prognose"), _wort(160, 540, "Legende")]
    werte = [_wort(100, 300, "240,9"), _wort(160, 320, "227,0"), _wort(220, 330, "217,0"), _wort(280, 400, "153,4")]
    kopf, reihen, _ = bc.from_diagram(jahre + zusatz + werte)
    assert kopf == ["2025", "2026 Plan", "2026 Prognose", "2027"]          # „2027" sitzt 3 pt tiefer
    assert reihen[0]["values"] == [240.9, 227.0, 217.0, 153.4]


def test_gruppe_nebeneinander_stapel_uebereinander():
    jahre = [_wort(100 + 80 * i, 500, str(2025 + i)) for i in range(2)]
    gruppe = [_wort(90, 300, "783,8"), _wort(115, 290, "768,2"), _wort(170, 310, "795,7"), _wort(195, 280, "832,5")]
    _, reihen, _ = bc.from_diagram(jahre + gruppe)
    assert [r["values"] for r in reihen] == [[783.8, 795.7], [768.2, 832.5]]
    stapel = [_wort(100, 420, "52,81"), _wort(100, 350, "27,46"), _wort(180, 415, "54,65"), _wort(180, 340, "28,73")]
    _, reihen, _ = bc.from_diagram(jahre + stapel)
    assert [r["values"] for r in reihen] == [[52.81, 54.65], [27.46, 28.73]]   # von unten nach oben


def test_unregelmaessig_gelesen_wird_verworfen():
    assert not bc.is_regular([{"label": "a", "values": [1.0, 2.0]}, {"label": "b", "values": [3.0, None]}])
    # Eine Tabelle, für ein Diagramm gehalten: 6,2 neben 221 Mio. (Grafik 2.4.1.3-1).
    assert not bc.is_regular([{"label": "a", "values": [6.2, 221124932.0]}])


def test_kompakt_nennt_seite_nummer_und_werte():
    g = bc.Chart(number="2.1.1-1", page=10, caption="2020 – 2025 Ist, 2026 Prognose (Grafik 2.1.1-1)", kind="diagram",
                 title="Entwicklung der Fehlbeträge", header=["2025", "2026"], rows=[{"label": "Reihe 1", "values": [-24.8, -64.9]}])
    text = bc.compact([g])
    assert "[Grafik 2.1.1-1] PDF-S. 10 · Diagramm" in text and "-24,8 | -64,9" in text


def test_aus_pdf_braucht_pymupdf():
    pytest.importorskip("pymupdf")
    assert bc.from_pdf(_leeres_pdf()) == []


def _leeres_pdf() -> bytes:
    import pymupdf
    dok = pymupdf.open()
    dok.new_page().insert_text((72, 72), "Vorbericht ohne Grafik")
    return dok.tobytes()
