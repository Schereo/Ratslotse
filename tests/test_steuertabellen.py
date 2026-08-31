"""Die beiden Steuertabellen des Statistischen Jahrbuchs (1103 und 1105).

Die Fixtures sind **echte Auszüge** vom 18.08.2026 — genau der Textextrakt, den
pypdf aus ``1103-2025-AZ.pdf`` und ``1104-1105-2025-AZ.pdf`` liefert. Sie
tragen jede Eigenheit, an der ein naiver Parser scheitert oder, schlimmer,
still das Falsche liest:

- **Die Zeilennamen brechen um**, und zwar unregelmäßig: „Grundsteuer" /
  „A und B" auf zwei Zeilen, „Gemeindeanteil" / „an der" / „Umsatzsteuer" auf
  drei — und dort stehen die Zahlen sogar auf einer **vierten**.
- **Der Titel bricht ebenfalls um**, mitten in der Jahresangabe.
- **Die Fußnotenziffer klebt an der Jahreszahl** („seit 19801"), dieselbe Falle
  wie in den Tabellen 1102 und 1107.
- **1105 steht auf demselben Blatt wie 1104** — ein Zeilenleser ohne
  Bereichsgrenze zieht die Steuereinnahmen von 2004 bis 2025 mit herein.
- **Der Spaltenkopf von 1105 verschränkt sich**: Die Zeile „A B steuer" trägt
  die beiden Grundsteuer-Spalten UND die zweite Hälfte von „Gewerbe-".

Der schwerste Teil ist keiner davon, sondern die **Jahresbeschriftung**.
Datensatz 1106 hat gezeigt, was eine ungeprüfte kostet: Die ganze Reihe war um
ein Jahr zu früh beschriftet, und es fiel jahrelang niemandem auf, weil jede
einzelne Zahl für sich plausibel aussah. Beide Tabellen hier werden deshalb
gegen eine zweite Quelle gehalten, bevor etwas gespeichert wird — und die
Gegenproben in diesem Modul unterstellen ausdrücklich den Versatz und
verlangen, dass die Prüfung ihn findet.
"""
from __future__ import annotations

import pytest

from council import herkunft
from council import steuertabellen as stt
from council.store import CouncilStore

# --- Fixtures ---------------------------------------------------------------

#: Textextrakt der echten Datei ``1103-2025-AZ.pdf``. Ungekürzt — die Tabelle
#: hat acht Zeilen, und jede wird gebraucht: sechs Steuerarten, die
#: Finanzzuweisungen und die Summe.
PDF_1103 = """Stadt Oldenburg (Oldb) - Statistik
1103   Steuern und steuerähnliche Erträge sowie allgemeine
           Finanzzuweisungen und Umlagen 2023 bis 2025
                                   Haushaltsjahr
in
Tausend
Euro
in
Prozent
S 1 S 2 S 3 S 4 S 5 S 6 S 7 S 8 S 9 S 10 S 11 S 12 S 13
Grundsteuer
A und B 33.770 8,66 33.879 7,76 34.120 8,56 34.171 7,27 34.120 8,49 32.585 6,98
Gewerbesteuer
-umlage 124.234 31,86 176.840 40,52 133.440 33,49 202.918 43,16 155.526 38,72 222.117 47,56
Einkommens-
steueranteil 92.400 23,69 91.325 20,93 98.000 24,60 99.621 21,19 104.112 25,92 106.086 22,72
Gemeindeanteil
an der
Umsatzsteuer
19.900 5,10 19.943 4,57 20.800 5,22 20.887 4,44 21.153 5,27 22.233 4,76
Vergnügungs-
steuer 3.500 0,90 3.537 0,81 4.000 1,00 2.233 0,47 3.500 0,87 3.368 0,72
Hundesteuer 805 0,21 813 0,19 820 0,21 819 0,17 820 0,20 819 0,18
Finanz-
zuweisungen 115.365 29,58 110.049 25,22 107.227 26,91 109.498 23,29 82.465 20,53 79.787 17,09
total 389.974 100,00 436.386 100,00 398.407 100,00 470.147 100,00 401.696 100,00 466.995 100,00
Quelle: Stadt Oldenburg - Fachdienst Finanzen
Einnahmeart
2023
Kapitel 11 - Verwaltung und Finanzen
2024 2025
nach dem
Haushaltsplan
 Rechnungs-
result
nach dem
Haushaltsplan
 Rechnungs-
result
nach dem
Haushaltsplan
vorläufiges
Rechnungs-
result
Fachdienst Geo und Daten"""

#: **Die Ausgabe davor** — 2022 bis 2024. Sie ist nicht mehr abrufbar (die
#: Adresse ``1103-2024-AZ.pdf`` antwortet mit 404, nachgemessen am 17.08.2026);
#: genau darum gibt es das Archiv. Die Ist-Spalten sind echt, die Plan-Spalte
#: für 2022 ist gesetzt — sie stand nur in der verschwundenen Ausgabe.
#:
#: Sie beweist das Eigentliche: 2022 steht in **keiner** aktuellen Ausgabe
#: mehr. Ohne Archiv wäre der Jahrgang für immer weg.
PDF_1103_AUSGABE_2024 = """Stadt Oldenburg (Oldb) - Statistik
1103   Steuern und steuerähnliche Erträge sowie allgemeine
           Finanzzuweisungen und Umlagen 2022 bis 2024
S 1 S 2 S 3 S 4 S 5 S 6 S 7 S 8 S 9 S 10 S 11 S 12 S 13
Grundsteuer
A und B 33.500 9,54 33.757 8,61 33.770 8,66 33.879 7,76 34.120 8,56 34.171 7,27
Gewerbesteuer
-umlage 112.000 31,90 143.674 36,66 124.234 31,86 176.840 40,52 133.440 33,49 202.918 43,16
Einkommens-
steueranteil 84.000 23,92 89.049 22,72 92.400 23,69 91.325 20,93 98.000 24,60 99.621 21,19
Gemeindeanteil
an der
Umsatzsteuer
 18.500 5,27 19.628 5,01 19.900 5,10 19.943 4,57 20.800 5,22 20.887 4,44
Vergnügungs-
steuer 3.300 0,94 3.548 0,91 3.500 0,90 3.537 0,81 4.000 1,00 2.233 0,47
Hundesteuer 800 0,23 805 0,21 805 0,21 813 0,19 820 0,21 819 0,17
Finanz-
zuweisungen 99.000 28,20 101.500 25,90 115.365 29,58 110.049 25,22 107.227 26,91 109.498 23,29
total 351.100 100,00 391.961 100,00 389.974 100,00 436.386 100,00 398.407 100,00 470.147 100,00
Quelle: Stadt Oldenburg - Fachdienst Finanzen
Einnahmeart
Kapitel 11 - Verwaltung und Finanzen"""

#: Textextrakt der echten Datei ``1104-1105-2025-AZ.pdf`` — **beide** Tabellen,
#: wie sie dort stehen. 1104 ist gekürzt (die Ränder und ein paar Jahre in der
#: Mitte); 1105 ist vollständig, alle neun Änderungsjahre.
PDF_1105 = """Stadt Oldenburg (Oldb) - Statistik
1104   Steuereinnahmen in Tausend Euro 2004 bis 2025
               (Jahres-Rechnungsergebnis)
Haus- Grund- Gewerbe- Ein- Gemeinde- Getränke- Vergnügungs- sonstige total
halts- steuer steuer kommens- anteil steuer 1 steuer Steuern 2
year A + B =-umlage steuer- an der
S 1 S 2 S 3 S 4 S 5 S 6 S 7 S 8 S 9
2004 23.690 48.861 34.774 5.866 0    1.290 459 114.940
2015 31.321 86.249 69.083 10.873 0    4.027 656 202.209
2025 32.585 222.117 106.086 22.233 0    3.368 819 387.208
Quelle: Stadt Oldenburg - Fachdienst Finanzen
1  Die Getränkesteuer wird seit 01.Januar 1994 nicht mehr erhoben.
2  Die Angabe zu den "sonstigen Steuern" beinhaltet per Saldo die Hunde- und die Jagdsteuer.
1105   Realsteuer-Hebesätze in Prozent seit 19801
                      Grundsteuer Gewerbe-
A B steuer
S 1 S 2 S 3 S 4
1980 200 300 370
1984 270 330 370
1988 270 340 380
1994 290 360 390
1997 290 360 410
2002 340 410 410
2011 360 430 430
2015 390 445 439
2025 500 539 439
Quelle: Stadt Oldenburg - Fachdienst Finanzen
1 Ausgewiesen sind die Jahre, in denen sich die Hebesätze geändert haben.
Jahr
Kapitel 11 - Verwaltung und Finanzen
Fachdienst Geo und Daten"""

#: Die Aufkommensreihe der Grundsteuer A+B aus Tabelle 1104
#: (``council_steuern``), in Euro — **vollständig und echt**, 1998 bis 2025.
#:
#: Vollständig, weil die Gegenprobe sie so braucht: Sie verschiebt die Reihe um
#: ein Jahr und verlangt, dass die Prüfung anschlägt. Mit Löchern verschöbe sie
#: manche Jahre bloß ins „nicht prüfbar", und der Test bewiese nichts.
GRUNDSTEUER_IST = {
    1998: 17_629_000, 1999: 18_603_000, 2000: 19_000_000, 2001: 19_988_000,
    2002: 22_897_000, 2003: 23_288_000, 2004: 23_690_000, 2005: 23_944_000,
    2006: 24_286_000, 2007: 24_700_000, 2008: 25_074_000, 2009: 25_314_000,
    2010: 25_876_000, 2011: 28_286_000, 2012: 28_104_000, 2013: 28_262_000,
    2014: 28_872_000, 2015: 31_321_000, 2016: 31_381_000, 2017: 31_634_000,
    2018: 32_154_000, 2019: 32_465_000, 2020: 33_201_000, 2021: 33_274_000,
    2022: 33_757_000, 2023: 33_879_000, 2024: 34_171_000, 2025: 32_585_000,
}

#: Die vollständige Ist-Reihe je Steuerart für die drei Jahre, die 1103 führt —
#: plus 2022 für die Archiv-Ausgabe. Alles echte Werte aus dem Open-Data-CSV.
IST_REIHE: dict[int, dict[str, float]] = {
    2022: {"Grundsteuer A+B": 33_757_000, "Gewerbesteuer (-umlage)": 143_674_000,
           "Einkommensteueranteil": 89_049_000,
           "Gemeindeanteil an der Umsatzsteuer": 19_628_000,
           "Vergnügungssteuer": 3_548_000, "sonstige Steuern": 805_000},
    2023: {"Grundsteuer A+B": 33_879_000, "Gewerbesteuer (-umlage)": 176_840_000,
           "Einkommensteueranteil": 91_325_000,
           "Gemeindeanteil an der Umsatzsteuer": 19_943_000,
           "Vergnügungssteuer": 3_537_000, "sonstige Steuern": 813_000},
    2024: {"Grundsteuer A+B": 34_171_000, "Gewerbesteuer (-umlage)": 202_918_000,
           "Einkommensteueranteil": 99_621_000,
           "Gemeindeanteil an der Umsatzsteuer": 20_887_000,
           "Vergnügungssteuer": 2_233_000, "sonstige Steuern": 819_000},
    2025: {"Grundsteuer A+B": 32_585_000, "Gewerbesteuer (-umlage)": 222_117_000,
           "Einkommensteueranteil": 106_086_000,
           "Gemeindeanteil an der Umsatzsteuer": 22_233_000,
           "Vergnügungssteuer": 3_368_000, "sonstige Steuern": 819_000},
}

GEWERBE = "Gewerbesteuer (-umlage)"


# --- Tabelle 1103: lesen ----------------------------------------------------

def test_die_umgebrochenen_zeilennamen_finden_ihre_steuerart():
    """Jede der sechs Steuerarten wird zugeordnet — keine bleibt liegen.

    Die Namen brechen im Extrakt an verschiedenen Stellen um, und bei einem
    steht der ganze Name auf eigenen Zeilen und die Zahlen auf der nächsten.
    Eine nicht zugeordnete Zeile wäre nicht bloß eine fehlende Reihe: Sie
    fehlte in der Summenprobe, und die risse."""
    gelesen = stt.parse_1103(PDF_1103)
    assert gelesen["unbekannt"] == []
    assert set(gelesen["zeilen"]) == {
        "Grundsteuer A+B", GEWERBE, "Einkommensteueranteil",
        "Gemeindeanteil an der Umsatzsteuer", "Vergnügungssteuer",
        "sonstige Steuern", stt.ZUWEISUNGEN, stt.SUMME}


def test_die_jahresspanne_steht_im_umgebrochenen_titel():
    assert stt.erkenne_1103(PDF_1103) == (2023, 2025)
    assert stt.parse_1103(PDF_1103)["years"] == [2023, 2024, 2025]


def test_eine_angeklebte_fussnotenziffer_verschiebt_das_jahr_nicht():
    """„2023 bis 20251" — dieselbe Falle wie in den Tabellen 1102 und 1107."""
    text = PDF_1103.replace("Umlagen 2023 bis 2025", "Umlagen 2023 bis 20251")
    assert stt.erkenne_1103(text) == (2023, 2025)


def test_die_quelle_sagt_selbst_welches_ergebnis_vorlaeufig_ist():
    """Die jüngste Spalte heißt „vorläufiges Rechnungsergebnis" — und nur sie.

    Das ist keine Kosmetik: Eine Zahl, die sich mit dem Jahresabschluss noch
    ändern kann, darf nicht wie eine abgerechnete dastehen."""
    assert stt.parse_1103(PDF_1103)["provisional"] == [2025]
    zeilen = stt.lies_1103(PDF_1103, IST_REIHE)["zeilen"]
    provisional = {z["year"] for z in zeilen if z["provisional"]}
    assert provisional == {2025}


def test_der_befund_steht_wie_gedruckt():
    """Die drei Gewerbesteuer-Jahre, gegen die Tabelle nachgeschlagen."""
    zeilen = {z["year"]: z for z in stt.lies_1103(PDF_1103, IST_REIHE)["zeilen"]
              if z["art"] == GEWERBE}
    assert zeilen[2023]["plan"] == 124_234_000
    assert zeilen[2023]["ist"] == 176_840_000
    assert zeilen[2024]["plan"] == 133_440_000
    assert zeilen[2025]["ist"] == 222_117_000


# --- Tabelle 1103: die Proben -----------------------------------------------

def test_summenprobe_geht_in_allen_sechs_spalten_auf():
    """Sechs Rechnungen: drei Jahre, je einmal Plan und einmal Ergebnis."""
    abweichungen = stt.summenprobe(stt.parse_1103(PDF_1103))
    assert set(abweichungen) == {2023, 2024, 2025}
    for year, spalten in abweichungen.items():
        assert spalten == {"plan": 0, "ist": 0}, year


def test_eine_fehlende_zeile_reisst_die_summenprobe():
    """Genau dafür ist sie da: Was der Parser übersieht, fällt hier auf.

    Ohne diese Probe fehlte die Hundesteuer still in der Reihe, und alle
    übrigen Zahlen blieben richtig — der Fehler wäre unsichtbar."""
    ohne = PDF_1103.replace(
        "Hundesteuer 805 0,21 813 0,19 820 0,21 819 0,17 820 0,20 819 0,18\n", "")
    result = stt.lies_1103(ohne, IST_REIHE)
    assert result["zeilen"] == []
    assert "Summenprobe" in result["abbruch"]


def test_anteilsprobe_haelt_betrag_und_prozentsatz_zusammen():
    assert stt.anteilsprobe(stt.parse_1103(PDF_1103)) == []


def test_ein_verrutschtes_feld_reisst_die_anteilsprobe():
    """Wären die Felder einer Zeile um eins verschoben, stünde jeder Betrag
    neben dem Prozentsatz seines Nachbarn. Die Beträge blieben plausibel."""
    verrutscht = PDF_1103.replace(
        "-umlage 124.234 31,86 176.840 40,52",
        "-umlage 124.234 40,52 176.840 31,86")
    result = stt.lies_1103(verrutscht, IST_REIHE)
    assert result["zeilen"] == []
    assert "Anteilsprobe" in result["abbruch"]


# --- Die Jahresbeschriftung — die Lehre aus Datensatz 1106 -------------------

def test_die_beschriftung_wird_gegen_tabelle_1104_geprueft():
    """Alle drei Jahrgänge kommen herein, weil die zweite Tabelle sie bestätigt."""
    result = stt.lies_1103(PDF_1103, IST_REIHE)
    assert result["years"] == [2023, 2024, 2025]
    assert result["verworfen"] == []
    assert "steuerplan_istabgleich" in result["probes"]


def test_ein_jahresversatz_wuerde_auffallen():
    """Die Gegenprobe: Wir unterstellen den Fehler und verlangen, dass er auffällt.

    Genau so war Datensatz 1106 beschriftet — jede Zeile um ein Jahr zu früh.
    Hier ist die Ist-Reihe um ein Jahr verschoben; kein einziger Jahrgang darf
    dann noch durchkommen."""
    verschoben = {year + 1: werte for year, werte in IST_REIHE.items()}
    result = stt.lies_1103(PDF_1103, verschoben)
    assert result["zeilen"] == []
    assert result["years"] == []
    assert len(result["verworfen"]) == 3


def test_ein_jahrgang_ohne_zweitquelle_kommt_nicht_rein():
    """Fehlt 1104 ein Jahr, bleibt es draußen — die anderen bleiben drin.

    Nicht der ganze Lauf scheitert: Ein künftiger Jahrgang, den die Ist-Reihe
    noch nicht führt, ist kein Fehler, sondern eine Wartezeit."""
    ohne_2025 = {j: w for j, w in IST_REIHE.items() if j != 2025}
    result = stt.lies_1103(PDF_1103, ohne_2025)
    assert result["years"] == [2023, 2024]
    assert [v["year"] for v in result["verworfen"]] == [2025]
    assert "ohne Zweitquelle" in result["verworfen"][0]["reason"]
    assert all(z["year"] != 2025 for z in result["zeilen"])


def test_ein_widersprechender_betrag_verwirft_den_jahrgang():
    """Nicht nur fehlende Jahre — auch abweichende Beträge."""
    falsch = {j: dict(w) for j, w in IST_REIHE.items()}
    falsch[2024][GEWERBE] = 199_000_000
    result = stt.lies_1103(PDF_1103, falsch)
    assert result["years"] == [2023, 2025]
    assert "1103 202918 vs. 1104 199000" in result["verworfen"][0]["reason"]


# --- Das Archiv: die Reihe wächst -------------------------------------------

def test_das_archiv_verlaengert_die_reihe_ueber_drei_jahrgaenge_hinaus():
    """Der eigentliche Grund für den Archiv-Job.

    Jede Ausgabe von 1103 führt drei Jahrgänge. Die Ausgabe 2024 ist nicht mehr
    abrufbar — mit ihr wäre 2022 verloren. Aus beiden zusammen werden vier."""
    alt = stt.lies_1103(PDF_1103_AUSGABE_2024, IST_REIHE)
    neu = stt.lies_1103(PDF_1103, IST_REIHE)
    assert alt["years"] == [2022, 2023, 2024]
    assert neu["years"] == [2023, 2024, 2025]

    zusammen = stt.zusammenlegen(
        [("1103-2024-AZ.pdf", alt["zeilen"]), ("1103-2025-AZ.pdf", neu["zeilen"])],
        lambda z: (z["year"], z["art"]))
    assert sorted({z["year"] for z in zusammen}) == [2022, 2023, 2024, 2025]


def test_bei_gleichem_jahrgang_gewinnt_die_juengere_ausgabe():
    """Sie trägt das abgerechnete Ergebnis, wo die ältere ein vorläufiges hatte.

    Geprüft an der Herkunft: Die überlappenden Jahrgänge müssen die jüngere
    Ausgabe als Quelle nennen, der nur in der älteren enthaltene die ältere."""
    alt = stt.lies_1103(PDF_1103_AUSGABE_2024, IST_REIHE)["zeilen"]
    neu = stt.lies_1103(PDF_1103, IST_REIHE)["zeilen"]
    zusammen = {(z["year"], z["art"]): z for z in stt.zusammenlegen(
        [("1103-2024-AZ.pdf", alt), ("1103-2025-AZ.pdf", neu)],
        lambda z: (z["year"], z["art"]))}
    assert zusammen[(2022, GEWERBE)]["ausgabe"] == "1103-2024-AZ.pdf"
    assert zusammen[(2024, GEWERBE)]["ausgabe"] == "1103-2025-AZ.pdf"
    # 2024 stand in beiden Ausgaben mit demselben Ergebnis — die jüngere
    # gewinnt trotzdem, weil nur so ein revidierter Wert ankäme.
    assert zusammen[(2024, GEWERBE)]["ist"] == 202_918_000


# --- Tabelle 1105: die Hebesatz-Treppe --------------------------------------

def test_1105_liest_die_neun_aenderungsjahre():
    zeilen = stt.parse_1105(PDF_1105)
    assert [z["year"] for z in zeilen] == [
        1980, 1984, 1988, 1994, 1997, 2002, 2011, 2015, 2025]
    assert zeilen[-1] == {"year": 2025, "Grundsteuer A": 500,
                          "Grundsteuer B": 539, "Gewerbesteuer": 439}


def test_die_nachbartabelle_auf_demselben_blatt_wird_nicht_mitgelesen():
    """1104 steht darüber und hat achtspaltige Zeilen mit denselben Jahren.

    Ohne Bereichsgrenze käme „2015 31.321 …" als Hebesatzzeile herein."""
    years = [z["year"] for z in stt.parse_1105(PDF_1105)]
    assert years.count(2015) == 1
    assert 2004 not in years


def test_das_startjahr_steht_im_titel_trotz_klebender_fussnote():
    """„seit 19801" — die Ziffer gehört zur Fußnote, nicht zum Jahr."""
    assert stt.erkenne_1105(PDF_1105) == 1980


def test_der_spaltenkopf_wird_gelesen_nicht_geraten():
    assert stt.spaltenprobe(PDF_1105) is True


def test_vertauschte_spalten_lassen_nichts_herein():
    """Stünde die Gewerbesteuer eines Tages links, käme ihr Satz sonst unter
    dem Namen der Grundsteuer heraus — plausibel und falsch."""
    gedreht = PDF_1105.replace("                      Grundsteuer Gewerbe-\nA B steuer",
                               "                      Gewerbe- Grundsteuer\nsteuer A B")
    result = stt.lies_1105(gedreht, GRUNDSTEUER_IST)
    assert result["zeilen"] == []
    assert "Reihenfolge" in result["abbruch"]


def test_die_treppe_wird_nicht_interpoliert():
    """Gespeichert werden **nur** die Änderungsjahre — nichts dazwischen.

    Ein Hebesatz gilt, bis der Rat ihn ändert. Zwischen 2015 und 2025 liegen
    zehn Jahre, in denen er 445 war; würden wir sie füllen, sähe es aus, als
    hätte jemand jedes Jahr entschieden. Und würde jemand interpolieren, stünde
    für 2020 ein Satz, den es nie gab."""
    zeilen = stt.lies_1105(PDF_1105, GRUNDSTEUER_IST)["zeilen"]
    years = sorted({z["year"] for z in zeilen})
    assert years == [1980, 1984, 1988, 1994, 1997, 2002, 2011, 2015, 2025]
    # Kein Jahr zwischen zwei Stufen, insbesondere keines der zehn ab 2016.
    assert not [j for j in range(2016, 2025) if j in years]
    b = {z["year"]: z for z in zeilen if z["art"] == "Grundsteuer B"}
    assert b[2015]["rate"] == 445
    assert b[2025] == {"year": 2025, "art": "Grundsteuer B",
                       "rate": 539, "prior_rate": 445}


def test_eine_zeile_die_nichts_aendert_faellt_auf():
    """Die Tabelle sagt in ihrer Fußnote, dass sie nur Änderungsjahre führt.

    Eine Wiederholung wäre entweder ein Fehler der Tabelle oder einer im
    Lesen — in beiden Fällen nichts, was gespeichert gehört."""
    doppelt = PDF_1105.replace("2025 500 539 439",
                               "2024 390 445 439\n2025 500 539 439")
    assert stt.treppenprobe(stt.parse_1105(doppelt)) == [2024]
    result = stt.lies_1105(doppelt, GRUNDSTEUER_IST)
    assert result["zeilen"] == []
    assert "Änderungsjahre" in result["abbruch"]


# --- Die Jahresbeschriftung von 1105 ----------------------------------------

def test_die_sprungjahr_probe_bestaetigt_die_beschriftung():
    """Wo der Satz stieg, zieht das Aufkommen im GENANNTEN Jahr an.

    2002 am deutlichsten: Hebesatz +13,9 %, Aufkommen +14,55 % — und im Jahr
    darauf nur noch +1,71 %."""
    sprung = stt.sprungjahrprobe(stt.parse_1105(PDF_1105), GRUNDSTEUER_IST)
    assert [e["year"] for e in sprung["bestanden"]] == [2002, 2011, 2015]
    assert sprung["gerissen"] == []
    zweitausendzwei = sprung["bestanden"][0]
    assert zweitausendzwei["im_jahr"] > 0.14
    assert zweitausendzwei["danach"] < 0.02


def test_ein_jahresversatz_wuerde_die_sprungjahr_probe_reissen():
    """Die Gegenprobe — dieselbe Logik wie bei 1103, andere Mechanik.

    So war Datensatz 1106 beschriftet: Die Zeile trug das Jahr, die Zahl
    gehörte ins nächste. Übertragen auf 1105 hieße das, ein Hebesatz hätte
    erst ein Jahr später gewirkt — der Anstieg des Aufkommens läge dann NACH
    dem genannten Jahr. Beide Richtungen werden unterstellt; die Probe muss
    jede finden, und dann darf nichts gespeichert werden."""
    for richtung, versatz in (("zu früh", +1), ("zu spät", -1)):
        verschoben = {year + versatz: value
                      for year, value in GRUNDSTEUER_IST.items()}
        sprung = stt.sprungjahrprobe(stt.parse_1105(PDF_1105), verschoben)
        assert sprung["bestanden"] == [], richtung
        assert [e["year"] for e in sprung["gerissen"]] == [2002, 2011, 2015], richtung

        result = stt.lies_1105(PDF_1105, verschoben)
        assert result["zeilen"] == [], richtung
        assert "Jahresversatz" in result["abbruch"], richtung


def test_das_reformjahr_wird_nicht_faelschlich_als_versatz_gelesen():
    """2025 stieg der Satz um 21 %, das Aufkommen sank um 4,6 %.

    Das ist **kein** Versatz, sondern die Grundsteuerreform: Sie stellte
    gleichzeitig alle Messbeträge um. Die Probe misst den Hebesatz am
    Aufkommen und kann das nicht trennen — also sagt sie „nicht prüfbar"
    statt „gerissen". Sonst bräche der Lauf in dem Moment, in dem 2026 in der
    Ist-Reihe steht."""
    mit_2026 = {**GRUNDSTEUER_IST, 2026: 33_000_000}
    sprung = stt.sprungjahrprobe(stt.parse_1105(PDF_1105), mit_2026)
    assert 2025 not in [e["year"] for e in sprung["gerissen"]]
    offen = {e["year"]: e["reason"] for e in sprung["nicht_pruefbar"]}
    assert "Grundsteuerreform" in offen[2025]
    # Und die Reihe kommt trotzdem herein.
    assert stt.lies_1105(PDF_1105, mit_2026)["abbruch"] is None


def test_jahre_ohne_aufkommensreihe_werden_benannt_nicht_behauptet():
    """Vor 1998 gibt es keine Aufkommensreihe — das wird gesagt."""
    sprung = stt.sprungjahrprobe(stt.parse_1105(PDF_1105), GRUNDSTEUER_IST)
    offen = {e["year"] for e in sprung["nicht_pruefbar"]}
    assert {1984, 1988, 1994}.issubset(offen)


# --- Herkunft und Speichern -------------------------------------------------

def test_jede_probe_ist_dem_herkunfts_system_bekannt():
    """Ein Probenname, den `council/herkunft.py` nicht kennt, lässt sich gar
    nicht erst speichern (`ValueError`). Hier fällt er schon im Test auf."""
    probes = (stt.lies_1103(PDF_1103, IST_REIHE)["probes"]
              + stt.lies_1105(PDF_1105, GRUNDSTEUER_IST)["probes"])
    assert probes
    for name in probes:
        assert name in herkunft.PROBEN
        assert name in stt.PROBEN_KURZ


def test_gespeichert_wird_mit_herkunft_und_kommt_gleich_wieder_heraus(tmp_path):
    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        result = stt.lies_1103(PDF_1103, IST_REIHE)
        store.save_steuerplan(result["zeilen"], herkunft.Herkunft(
            art="stadt", url=stt.TABELLE_1103_URL,
            label="Statistisches Jahrbuch, Tabelle 1103",
            probe=result["probes"]))
        hebe = stt.lies_1105(PDF_1105, GRUNDSTEUER_IST)
        store.save_hebesaetze(hebe["zeilen"], herkunft.Herkunft(
            art="stadt", url=stt.TABELLE_1105_URL,
            label="Statistisches Jahrbuch, Tabelle 1105",
            probe=hebe["probes"]))

        plan = {(z["year"], z["art"]): z for z in store.get_steuerplan()}
        assert plan[(2024, GEWERBE)]["plan"] == 133_440_000
        assert plan[(2025, GEWERBE)]["provisional"] == 1
        assert store.steuerplan_jahre() == [2023, 2024, 2025]
        assert store.hebesatz_jahre() == [
            1980, 1984, 1988, 1994, 1997, 2002, 2011, 2015, 2025]
        # Keine Zeile ohne Herkunftsnachweis — die eine Zahl, die null sein muss.
        luecken = store.herkunft_luecken()
        assert not {t: n for t, n in luecken.items()
                    if t in ("council_steuerplan", "council_hebesaetze")}
    finally:
        store.close()


def test_ein_zweiter_lauf_wirft_aeltere_jahrgaenge_nicht_weg(tmp_path):
    """Der Lauf schreibt je Ausgabe einmal. Die zweite Ausgabe darf die
    Jahrgänge der ersten nicht mit wegräumen — sonst wäre das Archiv umsonst."""
    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        h = herkunft.Herkunft(art="stadt", url=stt.TABELLE_1103_URL,
                              probe=["steuerplan_summenzeile"])
        store.save_steuerplan(
            stt.lies_1103(PDF_1103_AUSGABE_2024, IST_REIHE)["zeilen"], h)
        store.save_steuerplan(stt.lies_1103(PDF_1103, IST_REIHE)["zeilen"], h)
        assert store.steuerplan_jahre() == [2022, 2023, 2024, 2025]
    finally:
        store.close()


@pytest.mark.parametrize("label,erwartet", [
    ("Grundsteuer A und B", "Grundsteuer A+B"),
    ("Gewerbesteuer -umlage", GEWERBE),
    ("Einkommens- steueranteil", "Einkommensteueranteil"),
    ("Gemeindeanteil an der Umsatzsteuer", "Gemeindeanteil an der Umsatzsteuer"),
    ("Vergnügungs- steuer", "Vergnügungssteuer"),
    ("Hundesteuer", "sonstige Steuern"),
    ("Finanz- zuweisungen", stt.ZUWEISUNGEN),
    ("total", stt.SUMME),
    ("Grunderwerbsteuer", None),
])
def test_zeilennamen_werden_auf_die_arten_der_ist_reihe_abgebildet(label, erwartet):
    """Die Schreibweisen müssen exakt denen aus `council_steuern` entsprechen —
    daran hängt der Abgleich, und ein Tippfehler ließe ihn still ins Leere
    laufen. „Grunderwerbsteuer" steht als Gegenprobe dabei: Sie ist keine
    Zeile dieser Tabelle und darf auch nicht versehentlich als Grundsteuer
    durchgehen."""
    assert stt.steuerart(label) == erwartet
