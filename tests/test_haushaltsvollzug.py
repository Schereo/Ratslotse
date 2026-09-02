"""Der Haushaltsvollzug — die vierteljährlichen Finanz- und Leistungsberichte.

Die Zahlen und Beschriftungen dieser Auszüge sind **echt**, aus den Anlagen
295049 (Bericht zum 30.06.2025, Layout ab 2021) und 191470 (Bericht zum
30.06.2018, Layout bis 2020) — samt ihrer Eigenheiten: der leeren Zelle, wo
ein Teilhaushalt keine Einzahlungen plant, dem umbrochenen Namen des
Teilhaushalts 09, und der Ermächtigungsübertragung, die im älteren Layout in
der dritten Spalte steht statt in der letzten.

Auch die **Spaltenkanten** sind gemessen und nicht ausgedacht: Der Parser
entscheidet über die Geometrie des Dokuments, und ein Auszug mit erfundenen
Abständen prüfte etwas anderes als den Betrieb. Was hier fehlt, ist allein die
PDF-Datei drumherum — ``pymupdf`` ist bewusst keine Abhängigkeit dieses
Projekts (s. Modulkopf von ``council/budget_execution.py``), und ein Test, der
es braucht, liefe in der CI gar nicht erst. Die Naht dafür ist
``lies_tabellenseiten``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from council import herkunft
from council.budget_execution import (
    BASIS_ANSATZ,
    BASIS_MIT_UEBERTRAG,
    HINWEIS_OCR,
    PROBE_SPALTEN,
    PROBE_SUMME,
    PROBE_ZEILE,
    PROBE_ZEITRAUM,
    VollzugFehler,
    _tabelle_lesen,
    herkunft_fuer,
    lies_ocr_text,
    lies_tabellenseiten,
    stichtag,
)
from council.store import CouncilStore

# --------------------------------------------------------------------------
# Die Auszüge
# --------------------------------------------------------------------------

#: Rechte Kanten der elf Zahlenspalten, gemessen in Anlage 295049.
SPALTEN_2025 = [255.4, 311.9, 368.4, 424.9, 484.7, 544.5, 601.0, 659.8,
                716.3, 742.3, 807.6]
#: Dieselben in Anlage 191470 — anderes Layout, andere Kanten.
SPALTEN_2018 = [300.6, 355.9, 401.6, 459.8, 516.9, 571.8, 636.7, 683.4,
                730.0, 781.9, 820.0]
SPALTEN_2018_FH = [280.3, 329.9, 377.9, 434.2, 515.6, 565.2, 614.7, 664.3,
                   713.9, 763.4, 799.3]

#: Anlage 295049, „1. Ergebnishaushalt“. Ansatz | Prognose | Abweichung |
#: nachrichtlich Ermächtigungsübertragungen — die Belegung ab 2021.
EHH_2025 = [
    (1, "Verwaltungsführung",
     ["660.550", "9.624.601", "-8.964.051", "636.550", "9.913.655",
      "-9.277.105", "-24.000", "289.054", "-313.054", "-3,5", "201.796"]),
    (2, "Personal- und Verwaltungsmanagement",
     ["2.520.619", "44.697.956", "-42.177.337", "3.219.187", "43.903.837",
      "-40.684.650", "698.568", "-794.119", "1.492.687", "3,5", "382.903"]),
    (3, "Wirtschaftsförderung, Liegenschaften",
     ["8.538.664", "8.094.564", "444.100", "6.534.841", "7.854.264",
      "-1.319.423", "-2.003.823", "-240.300", "-1.763.523", "397,1", "142.559"]),
    (4, "Finanzmanagement und Recht",
     ["455.233.407", "94.010.862", "361.222.545", "491.822.955", "90.999.611",
      "400.823.344", "36.589.548", "-3.011.251", "39.600.799", "11,0", "539.336"]),
    (5, "Sicherheit und Ordnung",
     ["29.998.176", "60.328.291", "-30.330.115", "30.093.703", "60.506.818",
      "-30.413.115", "95.527", "178.527", "-83.000", "-0,3", "225.262"]),
    (6, "Kultur, Museen, Sport",
     ["1.659.686", "36.412.804", "-34.753.118", "1.950.000", "37.441.000",
      "-35.491.000", "290.314", "1.028.196", "-737.882", "-2,1", "477.213"]),
    (7, "Stadtplanung",
     ["958.560", "7.534.298", "-6.575.738", "822.102", "7.413.743",
      "-6.591.641", "-136.458", "-120.555", "-15.903", "-0,2", "564.109"]),
    (8, "Verkehr und Straßenbau",
     ["17.150.870", "43.759.834", "-26.608.964", "17.178.911", "44.677.794",
      "-27.498.883", "28.041", "917.960", "-889.919", "-3,3", "1.364.228"]),
    # Der einzige Teilhaushalt, dessen Name umbricht — im Dokument steht er auf
    # zwei Zeilen, die Beträge dazwischen. Deshalb hier als Paar geführt.
    (9, ["Klima, Umwelt, Mobilität, Bau, Grün,", "Friedhöfe"],
     ["6.186.750", "31.513.961", "-25.327.211", "6.025.750", "31.471.062",
      "-25.445.312", "-161.000", "-42.899", "-118.101", "-0,5", "917.101"]),
    (10, "Soziales und Gesundheit",
     ["156.740.629", "254.341.277", "-97.600.648", "162.802.710",
      "269.453.234", "-106.650.524", "6.062.081", "15.111.957", "-9.049.876",
      "-9,3", "372.624"]),
    (11, "Jugend und Familie",
     ["37.564.652", "159.025.985", "-121.461.333", "37.882.539",
      "159.324.543", "-121.442.004", "317.887", "298.558", "19.329", "0,0",
      "46.213"]),
    (12, "Schule und Bildung",
     ["9.735.151", "68.890.722", "-59.155.571", "9.735.151", "69.660.466",
      "-59.925.315", "0", "769.744", "-769.744", "-1,3", "769.745"]),
    (13, "Nicht rechtsfähige Stiftungen",
     ["412.705", "599.941", "-187.236", "412.705", "599.941", "-187.236",
      "0", "0", "0", "0,0", "0"]),
    (0, "Summen",
     ["727.360.419", "818.835.096", "-91.474.677", "769.117.104",
      "833.219.968", "-64.102.864", "41.756.685", "14.384.872", "27.371.813",
      "29,9", "6.003.089"]),
]

#: Anlage 191470, „1. Ergebnishaushalt“. Hier steht die Ermächtigungs-
#: übertragung an DRITTER Stelle und ist in die Saldo-Spalte eingerechnet.
EHH_2018 = [
    (1, "Verwaltungsführung",
     ["519.230", "6.465.841", "89.938", "-6.036.549", "457.530", "6.340.237",
      "-5.882.707", "-61.700", "-215.542", "153.842", "-2,5"]),
    (2, "Personal- und Verwaltungsmanagement",
     ["1.559.772", "26.271.632", "158.626", "-24.870.486", "1.622.392",
      "27.616.938", "-25.994.546", "62.620", "1.186.680", "-1.124.060", "4,5"]),
    (3, "Wirtschaftsförderung, Liegenschaften",
     ["2.371.075", "6.164.540", "104.140", "-3.897.605", "3.454.421",
      "6.159.363", "-2.704.942", "1.083.346", "-109.317", "1.192.663", "-30,6"]),
    (4, "Finanzmanagement und Recht",
     ["360.590.807", "44.458.003", "532.813", "315.599.991", "387.916.851",
      "46.290.758", "341.626.093", "27.326.044", "1.299.942", "26.026.102",
      "8,25"]),
    (5, "Sicherheit und Ordnung",
     ["20.248.414", "38.643.008", "125.047", "-18.519.641", "22.734.306",
      "37.787.271", "-15.052.965", "2.485.892", "-980.784", "3.466.675",
      "-18,7"]),
    (6, "Kultur, Museen, Sport",
     ["1.937.498", "28.976.088", "191.293", "-27.229.883", "2.428.098",
      "29.872.203", "-27.444.105", "490.600", "704.822", "-214.222", "0,8"]),
    (7, "Stadtplanung",
     ["522.993", "4.912.497", "0", "-4.389.504", "522.993", "4.772.497",
      "-4.249.504", "0", "-140.000", "140.000", "-3,2"]),
    (8, "Verkehr und Straßenbau",
     ["15.338.611", "36.902.567", "544.083", "-22.108.039", "15.338.610",
      "37.446.649", "-22.108.039", "-1", "-1", "0", "0,0"]),
    (9, "Umwelt, Bauordnung, Grün u. Friedhöfe",
     ["4.874.741", "17.078.280", "876.232", "-13.079.771", "5.062.800",
      "17.994.512", "-12.931.712", "188.059", "40.000", "148.059", "-1,1"]),
    (10, "Soziales und Gesundheit",
     ["109.608.282", "172.801.768", "206.099", "-63.399.585", "109.736.224",
      "176.666.549", "-66.930.325", "127.942", "3.658.682", "-3.530.740",
      "5,6"]),
    (11, "Jugend und Familie",
     ["26.853.529", "105.442.888", "61.096", "-78.650.455", "26.600.000",
      "105.200.000", "-78.600.000", "-253.529", "-303.984", "50.455", "-0,1"]),
    (12, "Schule und Bildung",
     ["5.156.082", "52.709.662", "554.496", "-48.108.076", "5.556.082",
      "52.764.158", "-47.208.076", "400.000", "-500.000", "900.000", "-1,9"]),
    # Die leere Zelle: Dieser Teilhaushalt hat keine Ermächtigungsübertragung,
    # und der Bericht druckt dort NICHTS — keine Null.
    (13, "Nicht rechtsfähige Stiftungen",
     ["272.280", "230.968", None, "41.312", "272.280", "230.968", "41.312",
      "0", "0", "0", "0,0"]),
    (0, "Summen",
     ["549.853.314", "541.057.742", "3.443.863", "5.351.709", "581.702.587",
      "549.142.103", "32.560.484", "31.849.273", "4.640.498", "27.208.775",
      None]),
]

#: Anlage 191470, „2. Finanzhaushalt - Investitionen“. Vier Teilhaushalte
#: planen gar keine Einzahlungen; ihre Zellen sind leer.
FHH_2018 = [
    (1, "Verwaltungsführung",
     [None, "10.000", "13.388", "-23.388", None, "21.300", "-21.300", "0",
      "-2.088", "2.088", "-8,9"]),
    (2, "Personal- und Verwaltungsmanagement",
     [None, "1.410.000", "187.483", "-1.597.483", None, "1.597.500",
      "-1.597.500", "0", "17", "-17", "0,0"]),
    (3, "Wirtschaftsförderung, Liegenschaften",
     ["10.660.800", "6.897.000", "6.866.374", "-3.102.574", "10.335.300",
      "15.659.964", "-5.324.664", "-325.500", "1.896.590", "-2.222.090",
      "71,6"]),
    (4, "Finanzmanagement und Recht",
     ["1.214.200", "22.092.700", "6.700", "-20.885.200", "1.462.250",
      "21.880.791", "-20.418.541", "248.050", "-218.609", "466.659", "-2,2"]),
    (5, "Sicherheit und Ordnung",
     ["179.000", "1.884.700", "717.795", "-2.423.495", "171.000", "1.448.011",
      "-1.277.011", "-8.000", "-1.154.484", "1.146.484", "-47,3"]),
    (6, "Kultur, Museen, Sport",
     [None, "1.279.400", "483.553", "-1.762.953", None, "1.762.953",
      "-1.762.953", "0", "0", "0", "0,0"]),
    (7, "Stadtplanung",
     ["2.094.200", "727.000", "9.156.192", "-7.788.992", "816.000",
      "2.866.500", "-2.050.500", "-1.278.200", "-7.016.692", "5.738.492",
      "-73,7"]),
    (8, "Verkehr und Straßenbau",
     ["4.858.250", "11.332.500", "9.016.037", "-15.490.287", "4.042.809",
      "13.456.175", "-9.413.366", "-815.441", "-6.892.362", "6.076.921",
      "-39,2"]),
    (9, "Umwelt, Bauordnung, Grün u. Friedhöfe",
     ["127.000", "1.028.300", "2.455.237", "-3.356.537", "127.000",
      "1.373.637", "-1.246.637", "0", "-2.109.900", "2.109.900", "-62,9"]),
    (10, "Soziales und Gesundheit",
     [None, "11.200", "27.578", "-38.778", None, "40.544", "-40.544", "0",
      "1.766", "-1.766", "4,6"]),
    (11, "Jugend und Familie",
     ["900.000", "2.731.000", "4.909.719", "-6.740.719", "610.400",
      "2.567.219", "-1.956.819", "-289.600", "-5.073.500", "4.783.900",
      "-71,0"]),
    (12, "Schule und Bildung",
     [None, "2.831.602", "1.020.454", "-3.852.056", "379.790", "4.231.846",
      "-3.852.056", "379.790", "379.790", "0", "0,0"]),
    (13, "Unselbständige Stiftungen",
     ["31.800", "1.050.000", None, "-1.018.200", "31.800", "1.050.000",
      "-1.018.200", "0", "0", "0", "0,0"]),
    (0, "Summen",
     ["20.065.250", "53.285.402", "34.860.510", "-68.080.662", "17.976.349",
      "67.956.440", "-49.980.091", "-2.088.901", "-20.189.472", "18.100.571",
      "-26,6"]),
]

KOPF_2025 = ("Auswertung der Berichte zum 30. Juni 2025 1. Ergebnishaushalt "
             "Ansatz des Haushaltsjahres Teilhaushalte Prognose zum "
             "30. Juni 2025 Plan/Ist-Abweichung 2025 2025 nachrichtlich:")
KOPF_2018 = ("Auswertung der Berichte zum 30.06.2018 1. Ergebnishaushalt "
             "Teilhaushalte Plan 2018 Prognose zum 31.12.2018 "
             "Plan/Ist-Abweichung 2018")
KOPF_2018_FH = ("2. Finanzhaushalt - Investitionen Teilhaushalte Plan 2018 "
                "Prognose zum 31.12.2018 Plan/Ist-Abweichung 2018")

#: Zeilenhöhe und Wortbreiten, gemessen im Dokument.
_HOEHE = 16.2
_BREITE = 5.6


def _wort(text: str, rechts: float, y: float):
    """Ein Wortrahmen, rechtsbündig an ``rechts`` — so setzt der Bericht."""
    return (round(rechts - len(text) * _BREITE, 1), round(rechts, 1),
            round(y, 1), text)


def zeilen_bauen(rohzeilen, spalten, erste_grundlinie: float = 176.6):
    """Die Auszüge oben → visuelle Zeilen, wie sie aus dem PDF kämen.

    Eine Beschriftung als Liste bricht um: Ihre Bruchstücke bekommen eigene
    Grundlinien über und unter der Zahlenzeile, genau wie im Dokument."""
    aus: list[list[tuple]] = []
    for i, (nr, label, werte) in enumerate(rohzeilen):
        y = erste_grundlinie + i * _HOEHE
        zeile: list[tuple] = []
        marke = "Summen" if nr == 0 else f"{nr:02d}"
        zeile.append(_wort(marke, 60.0 + len(marke) * _BREITE, y))
        if isinstance(label, str):
            x = 70.0
            for teil in label.split(" "):
                zeile.append(_wort(teil, x + len(teil) * _BREITE, y))
                x += len(teil) * _BREITE + 3.0
        else:
            for k, teil in enumerate(label):
                versatz = -_HOEHE * 0.3 + k * _HOEHE * 0.6
                bruch = [_wort(w, 70.0 + (j + len(w)) * _BREITE, y + versatz)
                         for j, w in enumerate(teil.split(" "))]
                aus.append(bruch)
        for wert, rechts in zip(werte, spalten):
            if wert is not None:
                zeile.append(_wort(wert, rechts, y))
        aus.append(zeile)
    for z in aus:
        z.sort(key=lambda w: w[0])
    return aus


def lies(rohzeilen, spalten, _kopf=None, art="result"):
    return _tabelle_lesen(zeilen_bauen(rohzeilen, spalten), art)


# --------------------------------------------------------------------------
# (a) Die Proben, die diese Schicht tragen
# --------------------------------------------------------------------------

def test_die_neuere_tabelle_geht_auf_und_kennt_ihre_ansatz_basis():
    positionen, basis, ergebnis = lies(EHH_2025, SPALTEN_2025, KOPF_2025)
    assert basis == BASIS_ANSATZ
    assert len(positionen) == 14 * 3

    summe = {p.kind: p for p in positionen if p.is_total}
    assert summe["revenue"].budgeted == 727_360_419
    assert summe["expense"].budgeted == 818_835_096
    # Die Zahl, um die es in dieser Schicht geht: Der Plan sagt −91,5
    # Millionen, die Verwaltung erwartet zum Halbjahr −64,1 Millionen.
    assert summe["result"].budgeted == -91_474_677
    assert summe["result"].forecast == -64_102_864
    assert summe["result"].deviation == 27_371_813
    assert "Gleichungen gehen auf" in ergebnis


def test_das_aeltere_layout_wird_erkannt_ohne_die_kopfzeile_zu_lesen():
    """Die Kopfzeile steht gar nicht im Auszug — entschieden hat die Rechnung."""
    positionen, basis, _e = lies(EHH_2018, SPALTEN_2018, KOPF_2018)
    assert basis == BASIS_MIT_UEBERTRAG

    summe = {p.kind: p for p in positionen if p.is_total}
    # Der Saldo des älteren Layouts sind die VERFÜGBAREN Mittel: 5,35 Mio. €
    # statt der 8,80 Mio. €, die Erträge minus Aufwendungen ergäben. Genau
    # dafür gibt es `plan_basis`.
    assert summe["result"].budgeted == 5_351_709
    assert summe["revenue"].budgeted - summe["expense"].budgeted == 8_795_572
    assert summe["expense"].carryover == 3_443_863


def test_die_uebertragung_haengt_an_der_aufwandszeile_und_sonst_nirgends():
    """§ 20 KomHKVO ermächtigt zu AUFWENDUNGEN — nicht zu Erträgen."""
    positionen, _b, _e = lies(EHH_2025, SPALTEN_2025, KOPF_2025)
    je_art = {(p.sub_budget, p.kind): p for p in positionen}
    assert je_art[(1, "expense")].carryover == 201_796
    assert je_art[(1, "revenue")].carryover is None
    assert je_art[(1, "result")].carryover is None


def test_eine_leere_zelle_bleibt_leer_und_wird_nicht_zur_null():
    """Vier Teilhaushalte planen 2018 keine Einzahlungen. Der Bericht druckt
    dort nichts — eine erfundene Null sähe aus wie eine Auskunft."""
    positionen, _b, _e = lies(FHH_2018, SPALTEN_2018_FH, KOPF_2018_FH, "cash")
    je_art = {(p.sub_budget, p.kind): p for p in positionen}
    assert je_art[(1, "inflow")].budgeted is None
    assert je_art[(1, "outflow")].budgeted == 10_000
    # Und die Summenzeile zählt die leeren Zellen als nichts, nicht als Lücke.
    assert je_art[(0, "inflow")].budgeted == 20_065_250


def test_ein_betrag_eine_spalte_daneben_reisst_die_zeilenprobe():
    kaputt = [(nr, label, list(werte)) for nr, label, werte in EHH_2025]
    # Ansatz-Ergebnis des Teilhaushalts 10 um eine Stelle verrutscht.
    kaputt[9][2][2] = "-97.006.648"
    with pytest.raises(VollzugFehler) as fehler:
        lies(kaputt, SPALTEN_2025, KOPF_2025)
    assert "Zeile 10" in str(fehler.value)


def test_eine_veraenderte_summenzeile_reisst_die_summenprobe():
    kaputt = [(nr, label, list(werte)) for nr, label, werte in EHH_2025]
    # Die Summenzeile in sich stimmig lassen, aber gegen die Teile verschieben:
    # Erträge und Ergebnis gemeinsam um 10.000 € heben.
    kaputt[-1][2][0] = "727.370.419"
    kaputt[-1][2][2] = "-91.464.677"
    kaputt[-1][2][6] = "41.746.685"
    kaputt[-1][2][8] = "27.361.813"
    with pytest.raises(VollzugFehler) as fehler:
        lies(kaputt, SPALTEN_2025, KOPF_2025)
    assert "Summenzeile" in str(fehler.value)


def test_eine_tabelle_mit_zu_wenigen_spalten_kommt_nicht_herein():
    schmal = [(nr, label, werte[:8]) for nr, label, werte in EHH_2025]
    with pytest.raises(VollzugFehler) as fehler:
        lies(schmal, SPALTEN_2025[:8], KOPF_2025)
    assert "Zahlenspalten" in str(fehler.value)


# --------------------------------------------------------------------------
# (b) Stichtag und Haushaltsjahr
# --------------------------------------------------------------------------

@pytest.mark.parametrize("text,erwartet", [
    ("Auswertung der Berichte zum 30.06.2018", "2018-06-30"),
    ("Auswertung der Berichte zum 31. Dezember 2023", "2023-12-31"),
    ("Auswertung der Berichte zum 30. September 2025", "2025-09-30"),
    ("Auswertung der Berichte zum 31. März 2025", "2025-03-31"),
])
def test_der_stichtag_wird_in_beiden_schreibweisen_gelesen(text, erwartet):
    assert stichtag(text).isoformat() == erwartet


def test_ohne_erkennbaren_stichtag_kommt_kein_bericht_herein():
    seiten = [("result", zeilen_bauen(EHH_2025, SPALTEN_2025),
               "1. Ergebnishaushalt Plan/Ist-Abweichung 2025"),
              ("letters", 1.0, "")]
    lesung = lies_tabellenseiten(iter(seiten))
    assert lesung.berichte == []
    assert any("kein Stichtag" in r for r in lesung.risse)


def test_widerspricht_das_abweichungsjahr_dem_stichtag_wird_gemeldet():
    """Ein Bericht zum 31. Dezember erscheint erst im Folgejahr — ohne diese
    Probe ließe er sich dort einordnen."""
    seiten = [("result", zeilen_bauen(EHH_2025, SPALTEN_2025),
               KOPF_2025.replace("Plan/Ist-Abweichung 2025",
                                 "Plan/Ist-Abweichung 2026")),
              ("letters", 1.0, "")]
    lesung = lies_tabellenseiten(iter(seiten))
    assert lesung.berichte == []
    assert any("Plan/Ist-Abweichung" in r for r in lesung.risse)


def test_ein_gelesener_bericht_traegt_alle_vier_proben():
    seiten = [("result", zeilen_bauen(EHH_2025, SPALTEN_2025), KOPF_2025),
              ("letters", 1.0, "")]
    (bericht,) = lies_tabellenseiten(iter(seiten)).berichte
    assert bericht.budget_year == 2025
    assert bericht.as_of == "2025-06-30"
    assert set(bericht.probes) == {PROBE_SPALTEN, PROBE_ZEILE, PROBE_SUMME,
                                   PROBE_ZEITRAUM}


def test_eine_kaputte_tabelle_reisst_die_andere_nicht_mit():
    """Im Bericht zum 30.06.2024 weist die Stadt eine Aufwands-Abweichung aus,
    die ihre eigenen Spalten nicht hergeben — aber nur im ERGEBNIShaushalt.
    Wer daran das ganze Dokument verwirft, verliert einen Finanzhaushalt, an
    dem nichts falsch ist."""
    kaputt = [(nr, label, list(werte)) for nr, label, werte in EHH_2018]
    kaputt[11][2][8] = "-540.377"
    seiten = [("result", zeilen_bauen(kaputt, SPALTEN_2018), KOPF_2018),
              ("cash", zeilen_bauen(FHH_2018, SPALTEN_2018_FH), KOPF_2018_FH),
              ("letters", 1.0, "")]
    lesung = lies_tabellenseiten(iter(seiten))
    assert [b.budget for b in lesung.berichte] == ["cash"]
    assert any("Zeile 12" in r for r in lesung.risse)


def test_ein_pdf_ohne_zeichenzuordnung_sagt_das_statt_zu_schweigen():
    """Anlage 266188 (Bericht zum 30.06.2023) ist Glyphen-Salat. Ein leeres
    Ergebnis ohne Grund sähe aus wie „kein Vollzugsbericht“."""
    lesung = lies_tabellenseiten(iter([("letters", 0.02, "")]))
    assert lesung.berichte == []
    assert any("Zeichenzuordnung" in r for r in lesung.risse)


def test_ein_fachausschuss_auszug_faellt_still_durch():
    """Die Fassungen der Eigenbetriebe tragen dieselben Label. Sie sollen hier
    nichts liefern — und auch nicht lärmen."""
    lesung = lies_tabellenseiten(iter([("letters", 0.7, "")]))
    assert lesung.berichte == []
    assert lesung.risse == []


# --------------------------------------------------------------------------
# (c) Die Beschriftung
# --------------------------------------------------------------------------

def test_ein_umbrochener_name_wird_wieder_zusammengesetzt():
    positionen, _b, _e = lies(EHH_2025, SPALTEN_2025, KOPF_2025)
    namen = {p.sub_budget: p.label for p in positionen if p.kind == "result"}
    assert namen[9] == "Klima, Umwelt, Mobilität, Bau, Grün, Friedhöfe"
    assert namen[8] == "Verkehr und Straßenbau"
    assert namen[10] == "Soziales und Gesundheit"
    assert namen[0] == "Summen"


# --------------------------------------------------------------------------
# (d) Die Herkunft
# --------------------------------------------------------------------------

def test_die_herkunft_nennt_dokument_fundstelle_und_probe():
    seiten = [("result", zeilen_bauen(EHH_2025, SPALTEN_2025), KOPF_2025),
              ("letters", 1.0, "")]
    (bericht,) = lies_tabellenseiten(iter(seiten)).berichte
    h = herkunft_fuer(bericht, document_id=295049,
                      label="FLB 30.06.2025 finale Fassung",
                      url="https://buergerinfo.oldenburg.de/getfile.php?id=295049")
    assert h.kind == "ris"
    assert h.document_id == 295049
    assert "1. Ergebnishaushalt" in h.citation
    assert "30.06.2025" in h.as_of


# --------------------------------------------------------------------------
# Die OCR-Lesung: ein Scan ohne Textlayer (Anlage 266188, 30.06.2023)
# --------------------------------------------------------------------------

#: Echt: die beiden Tabellenseiten des Berichts zum 30.06.2023, wie die
#: Texterkennung sie liest — Markdown-Tabellen, eine Zeile je Teilhaushalt.
OCR_2023 = (Path(__file__).parent / "fixtures" / "vollzug_ocr_2023.txt").read_text()


def test_die_ocr_lesung_liest_beide_tabellen_mit_denselben_proben():
    """Aus den OCR-Zellen entstehen Wörter mit gedachten Rahmen; danach läuft
    dieselbe Tabellenlesung wie beim PDF — Spaltenbelegung über die Rechnung,
    Zeilen- und Summenprobe, Stichtag und Abweichungsjahr aus dem Text."""
    lesung = lies_ocr_text(OCR_2023)
    assert lesung.risse == []
    assert [b.budget for b in lesung.berichte] == ["cash", "result"]
    ehh = next(b for b in lesung.berichte if b.budget == "result")
    assert (ehh.budget_year, ehh.as_of, ehh.plan_basis) == (2023, "2023-06-30", BASIS_ANSATZ)
    assert set(ehh.probes) == {PROBE_SPALTEN, PROBE_ZEILE, PROBE_SUMME, PROBE_ZEITRAUM}
    assert ehh.probe_result.startswith(HINWEIS_OCR)
    summe = ehh.summe
    assert (summe["revenue"].budgeted, summe["revenue"].forecast) == (666_679_334, 670_606_575)
    assert (summe["result"].budgeted, summe["result"].forecast) == (-8_864_946, -40_767_080)
    assert summe["expense"].carryover == 12_475_152
    thh9 = next(p for p in ehh.positionen if p.sub_budget == 9 and p.kind == "result")
    assert thh9.label == "Klima, Umwelt, Mobilität, Bau, Grün, Friedhöfe"
    assert thh9.deviation == 1_064
    fhh = next(b for b in lesung.berichte if b.budget == "cash")
    assert fhh.summe["outflow"].forecast == 103_424_283
    assert len(fhh.positionen) == 14 * 3
    # Die Herkunft nennt die OCR als Quelle — wer die Zahl prüft, weiß, dass
    # sie über eine Texterkennung kam.
    h = herkunft_fuer(ehh, document_id=266188, label="Bericht", url="https://example.org/266188")
    assert HINWEIS_OCR in (h.probe_result or "")


def test_eine_falsch_erkannte_ziffer_reisst_die_ocr_tabelle():
    """Die Rahmen sind gedacht, die Proben nicht: Eine verdrehte Ziffer in
    einer Zelle lässt die Zeilengleichung reißen — und nur diese Tabelle
    fällt, die andere bleibt."""
    kaputt = OCR_2023.replace("| 04 | Finanzmanagement und Recht | 430.933.963 |",
                              "| 04 | Finanzmanagement und Recht | 430.939.963 |")
    lesung = lies_ocr_text(kaputt)
    assert [b.budget for b in lesung.berichte] == ["cash"]
    assert len(lesung.risse) == 1 and "Zeile 4" in lesung.risse[0]


def test_ein_ocr_text_ohne_tabellen_bleibt_still():
    """Erläuterungsseiten tragen die Marke „1. Ergebnishaushalt“ auch — ohne
    Tabelle dahinter ist das kein Riss, sondern nichts."""
    lesung = lies_ocr_text("Auswertung der Berichte zum 30.06.2023\n1. Ergebnishaushalt\n"
                           "Die Erträge entwickeln sich planmäßig.\n")
    assert lesung.berichte == [] and lesung.risse == []


def test_jede_probe_dieser_schicht_steht_im_register():
    """Ohne Eintrag in ``herkunft.PROBEN`` ließe sich die Herkunft gar nicht
    bauen — und auf der Seite stünde ein Prüfzeichen ohne Erklärung."""
    for name in (PROBE_SPALTEN, PROBE_ZEILE, PROBE_SUMME, PROBE_ZEITRAUM):
        assert name in herkunft.PROBEN
        assert herkunft.PROBEN[name].strip().endswith(".")
        assert len(herkunft.PROBEN[name]) > 40


# --------------------------------------------------------------------------
# (e) Der Speicherweg
# --------------------------------------------------------------------------

def _bericht(rohzeilen, spalten, kopf, art="result"):
    seiten = [(art, zeilen_bauen(rohzeilen, spalten), kopf), ("letters", 1.0, "")]
    return lies_tabellenseiten(iter(seiten)).berichte[0]


def test_speichern_und_lesen(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        bericht = _bericht(EHH_2025, SPALTEN_2025, KOPF_2025)
        n = store.save_haushaltsvollzug(bericht, herkunft_fuer(
            bericht, document_id=295049, label="FLB 30.06.2025", url=None))
        assert n == 42

        summen = store.get_haushaltsvollzug(totals_only=True)
        assert len(summen) == 3
        ergebnis = next(z for z in summen if z["kind"] == "result")
        assert ergebnis["forecast"] == -64_102_864
        assert ergebnis["plan_basis"] == BASIS_ANSATZ
        assert ergebnis["herkunft_id"] is not None
        assert PROBE_SUMME in ergebnis["probes"]

        assert store.haushaltsvollzug_einheiten() == {(2025, "2025-06-30", "result")}
        assert store.haushaltsvollzug_stichtage() == [
            {"budget_year": 2025, "as_of": "2025-06-30", "budgets": "result",
             "plan_basis": BASIS_ANSATZ}]
        # Und keine Zeile steht ohne Herkunft da.
        assert "council_budget_execution" not in store.herkunft_luecken()
    finally:
        store.close()


def test_zweimal_einlesen_aendert_keine_zeile(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        bericht = _bericht(EHH_2025, SPALTEN_2025, KOPF_2025)
        h = herkunft_fuer(bericht, document_id=295049, label="FLB", url=None)
        store.save_haushaltsvollzug(bericht, h)
        vorher = store.get_haushaltsvollzug()
        store.save_haushaltsvollzug(bericht, h)
        nachher = store.get_haushaltsvollzug()
        assert [{k: v for k, v in z.items() if k != "fetched_at"} for z in vorher] \
            == [{k: v for k, v in z.items() if k != "fetched_at"} for z in nachher]
    finally:
        store.close()


def test_die_beiden_haushalte_eines_stichtags_stehen_nebeneinander(tmp_path):
    """Ergebnis- und Finanzhaushalt teilen den Schlüssel bis auf ``budget``.
    Wer nach Stichtag löschte, risse mit dem einen den anderen mit.

    Der Auszug ist der von 2018, und er zeigt nebenbei die Eigenheit, wegen
    der der Stichtag von JEDER Seite eingesammelt wird: Die
    Finanzhaushalts-Seite trägt die Überschrift „Auswertung der Berichte zum
    …“ gar nicht — sie steht nur über der Ergebnis-Seite."""
    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        lesung = lies_tabellenseiten(iter([
            ("result", zeilen_bauen(EHH_2018, SPALTEN_2018), KOPF_2018),
            ("cash", zeilen_bauen(FHH_2018, SPALTEN_2018_FH), KOPF_2018_FH),
            ("letters", 1.0, "")]))
        assert [b.budget for b in lesung.berichte] == ["cash", "result"]
        for b in lesung.berichte:
            assert b.as_of == "2018-06-30"
            store.save_haushaltsvollzug(b, herkunft_fuer(
                b, document_id=191470, label="FLB 30.06.2018", url=None))
        assert store.haushaltsvollzug_einheiten() == {
            (2018, "2018-06-30", "result"), (2018, "2018-06-30", "cash")}
        (stand,) = store.haushaltsvollzug_stichtage()
        assert sorted(stand["budgets"].split(",")) == ["cash", "result"]
    finally:
        store.close()


def test_der_jahrgang_kommt_in_den_datenstand(tmp_path):
    """Ohne Eintrag in ``finanzquellen`` wüsste der Datenstand-Block nichts von
    der Schicht — und der Cron meldete nie, dass ein Quartal ausbleibt."""
    from council import finanzquellen

    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        bericht = _bericht(EHH_2025, SPALTEN_2025, KOPF_2025)
        store.save_haushaltsvollzug(bericht, herkunft_fuer(
            bericht, document_id=295049, label="FLB", url=None))
        zeile = next(z for z in finanzquellen.datenstand(store)
                     if z["key"] == "budget_execution")
        assert zeile["jahrgaenge"] == [2025]
        assert zeile["tabelle"] == "council_budget_execution"
        assert zeile["automatisch"] is False
        assert "ingest_haushaltsvollzug" in zeile["was"] + str(
            finanzquellen.QUELLEN["budget_execution"].nachschub)
    finally:
        store.close()
