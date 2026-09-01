"""Finanzrechnung der Kernverwaltung — die Kassensicht des Jahresabschlusses.

Beide Fixtures sind ECHTE pypdf-Extrakte aus Abschnitt 4.1 der jeweiligen
Jahresabschluss-Anlage im Ratsinformationssystem, unverändert bis auf
abgeschnittene Leerzeichen am Zeilenende. Sie decken die **zwei** Layouts ab,
die die Stadt in acht Jahrgängen benutzt hat:

* :data:`FR_2024` — 41 Zeilen, sieben Spalten, Ermächtigungen aus Vorjahren
  ganz rechts. Posten 35 steht dort ohne Punkt („35 Saldo aus …").
* :data:`FR_2019` — 42 Zeilen: eine Einzahlungsart mehr („08. Einzahlungen
  aus der Veräußerung geringwertiger Vermögensgegenstände"), wodurch sich
  **jede** Nummer ab 08 um eins verschiebt. Dazu die Querverweise in den
  Bezeichnungen („(Zeile 10 abzüglich Zeile 17)") und der Seitenfuß „JA 29",
  der zwischen den Tabellenseiten steht.
"""
from __future__ import annotations

import re

import pytest

from council import finanzberichte, finanzquellen
from council.store import CouncilStore

FR_2024 = """Finanzrechnung Kernverwaltung
Einzahlungen und Auszahlungen Ergebnis des
Vorjahres
2023
Ansätze des
Haushaltsjahres
2024
Veränderung
durch Nachtrag
mehr (+) /
weniger (-) 2024
Ergebnis des
Haushaltsjahres
2024
mehr (+) /
weniger (-) 4)
2024
Ermächtigung
aus Haushalts-
vorjahren
2024
 - Euro -
1 2 3 4 5 6 7
Einzahlungen aus laufender
Verwaltungstätigkeit
01. Steuern und ähnliche Abgaben 319.113.489,85 302.740.000,00  374.143.236,61 71.403.236,61
02. Zuwendungen und allgemeine Umlagen 1) 167.579.246,27 164.748.413,98  179.400.265,47 14.651.851,49
03. sonstige Transfereinzahlungen 9.009.917,13 7.939.884,00  8.839.139,61 899.255,61
04. öffentlich-rechtliche Entgelte 2) 23.213.266,75 24.553.515,00  26.884.726,85 2.331.211,85
05. privatrechtliche Entgelte 3) 19.556.802,82 18.059.920,00  18.364.138,89 304.218,89
06. Kostenerstattungen und Kostenumlagen 3) 130.469.547,35 127.664.972,09  124.507.065,56 -3.157.906,53
07. Zinsen und ähnliche Einzahlungen 17.101.798,41 15.961.300,00  19.519.243,71 3.557.943,71
08. sonstige haushaltswirksame Einzahlungen 14.749.060,11  14.170.600,00  19.377.184,71 5.206.584,71
09. = Summe der Einzahlungen aus
laufender Verwaltungstätigkeit 700.793.128,69 675.838.605,07  771.035.001,41 95.196.396,34
Auszahlungen aus laufender
Verwaltungstätigkeit
10. Personalauszahlungen 160.665.347,04 176.035.742,62  174.782.361,74 -1.253.380,88 352.202,54
11. Versorgungsauszahlungen 214,20
12. Auszahlungen für Sach- und
Dienstleistungen und für den Erwerb
geringwertiger Vermögensgegenstände
39.267.054,32
 45.170.315,24  42.935.156,20 -2.235.159,04 4.842.186,38
13. Zinsen und ähnliche Auszahlungen 2.263.024,09 3.422.000,00  4.062.300,32 640.300,32
14. Transferauszahlungen 3) 282.741.338,83 297.659.573,00  328.729.171,34 31.069.598,34 2.045.006,52
15. sonstige haushaltswirksame Auszahlungen 153.310.021,68 156.770.947,38  162.221.981,54 5.451.034,16 172.957,61
16. = Summe der Auszahlungen aus
laufender Verwaltungstätigkeit 638.247.000,16 679.058.578,24  712.730.971,14 33.672.392,90 7.412.353,05
17. Saldo aus laufender
Verwaltungstätigkeit 62.546.128,53 -3.219.973,17  58.304.030,27 61.524.003,44 -7.412.353,05

JA 29


Einzahlungen und Auszahlungen Ergebnis des
Vorjahres
2023
Ansätze des
Haushaltsjahres
2024
Veränderung
durch Nachtrag
mehr (+) /
weniger (-) 2024
Ergebnis des
Haushaltsjahres
2024
mehr (+) /
weniger (-) 4)
2024
Ermächtigung
aus Haushalts-
vorjahren
2024
 - Euro -
1 2 3 4 5 6 7
Einzahlungen für Investitionstätigkeit
18. Zuwendungen für Investitionstätigkeit 9.037.296,14 3.640.700,00  7.885.630,45 4.244.930,45
19. Beiträge u.ä. Entgelte für
Investitionstätigkeit 1.833.449,18 4.224.700,00  1.747.821,05 -2.476.878,95
20. Veräußerung von Sachvermögen 857.251,11 4.671.400,00  763.780,40 -3.907.619,60
21. Veräußerung von
Finanzvermögensanlagen

22. sonstige Investitionstätigkeit 5.210.881,70 5.571.000,00  5.290.586,48 -280.413,52
23. = Summe der Einzahlungen für
Investitionstätigkeit 16.938.878,13 18.107.800,00  15.687.818,38 -2.419.981,62
Auszahlungen für Investitionstätigkeit
24. Erwerb von Grundstücken und Gebäuden 4.124.660,15  3.579.000,00  5.938.538,56 2.359.538,56 3.839.726,94
25. Baumaßnahmen 12.484.250,14 22.291.400,00  14.951.098,27 -7.340.301,73 42.291.517,03
26. Erwerb von beweglichem Sachvermögen 10.123.008,49  11.596.550,00  6.810.573,00 -4.785.977,00 6.112.089,51
27. Erwerb von Finanzvermögensanlagen 27.219.841,96 19.935.000,00  29.293.201,10 9.358.201,10
28. Aktivierbare Zuwendungen 9.044.402,97 13.763.000,00  11.795.798,21 -1.967.201,79 6.524.922,60
29. Sonstige Investitionstätigkeit 14.584.737,00 37.887.917,00  27.581.067,00 -10.306.850,00
30. = Summe der Auszahlungen aus
Investitionstätigkeit 77.580.900,71 109.052.867,00  96.370.276,14 -12.682.590,86 58.768.256,08
31. Saldo aus Investitionstätigkeit -60.642.022,58 -90.945.067,00  -80.682.457,76 10.262.609,24 -58.768.256,08
32. Finanzmittel-Überschuss/-Fehlbetrag 1.904.105,95 -94.165.040,17  -22.378.427,49 71.786.612,68 -66.180.609,13

JA 30


Einzahlungen und Auszahlungen Ergebnis des
Vorjahres
2023
Ansätze des
Haushaltsjahres
2024
Veränderung
durch Nachtrag
mehr (+) /
weniger (-) 2024
Ergebnis des
Haushaltsjahres
2024
mehr (+) /
weniger (-) 4)
2024
Ermächtigung
aus Haushalts-
vorjahren
2024
 - Euro -
1 2 3 4 5 6 7
Ein-, Auszahlungen aus
Finanzierungstätigkeit
33. Einzahlungen aus Finanzierungstätigkeit;
Aufnahme von Krediten und inneren Darlehen
für Investitionstätigkeit
34.850.364,83
34. Auszahlungen aus Finanzierungstätigkeit;
Tilgung von Krediten und Rückzahlung von
inneren Darlehen für Investitionstätigkeit
38.017.790,73
 2.886.200,00  2.886.146,04 -53,96
35 Saldo aus Finanzierungstätigkeit -3.167.425,90 -2.886.200,00  -2.886.146,04 53,96
36. Finanzmittelveränderung -1.263.319,95 -97.051.240,17  -25.264.573,53 71.786.666,64 -66.180.609,13
37. haushaltsunwirksame Einzahlungen 5) 150.627.325,34   103.838.918,93 103.838.918,93
38. haushaltsunwirksame Auszahlungen 5) 152.278.092,55   103.649.836,58 103.649.836,58
39. Saldo aus haushaltsunwirksamen
Vorgängen 5) -1.650.767,21   189.082,35 189.082,35
40. +/- Anfangsbestand an Zahlungsmitteln zu
Beginn des Jahres 5) 145.991.469,60
   143.077.382,44 143.077.382,44
41. = Endbestand an Zahlungsmitteln
(Liquide Mittel am Ende d. Jahres) 5) 143.077.382,44 -97.051.240,17  118.001.891,26 215.053.131,43 -66.180.609,13

1) nicht für Investitionstätigkeit
2) ohne Beträge und Entgelte für Investitionstätigkeit
3) außer für Investitionstätigkeit
4) Spalte 6 = Spalte 5 - Summe (Spalte 3 + Spalte 4) (Vergleich zwischen den Jahresergebnissen und den
 Haushaltsansätzen gemäß § 54 KomHKVO)
5) Die Zeilen 37 bis 41 können optional ergänzt werden.




JA 31


JA 32
4.2"""

FR_2019 = """Finanzrechnung der Kernverwaltung
Einzahlungen und Auszahlungen Ergebnis des
Vorjahres 2018
Ansätze des
Haushaltsjahres
2019
Veränderung
durch Nachtrag
mehr (+) /
weniger (-) 2019
Ergebnis des
Haushaltsjahres
2019
mehr (+) /
weniger (-) 4)
2019
Ermächtigung
aus Haushalts-
vorjahren 2019
Zu Spalte 6: Davon bisher
nicht bewilligte über-
/außerplanmäßige
Aufwendungen 5) 2019
 - Euro -
1 2 3 4 5 6 7 8
Einzahlungen aus laufender
Verwaltungstätigkeit
01. Steuern und ähnliche Abgaben 267.403.408,58 274.387.800,00  278.488.129,69 4.100.329,69
02. Zuwendungen und allgemeine Umlagen 1) 141.488.754,51 124.837.659,00  130.570.558,45 5.732.899,45
03. sonstige Transfereinzahlungen 8.623.606,73 8.301.900,00  13.442.614,63 5.140.714,63
04. öffentlich-rechtliche Entgelte 2) 18.444.993,71 19.277.990,00  18.463.101,37 -814.888,63
05. privatrechtliche Entgelte 3) 18.310.212,92 16.712.536,61  18.169.050,79 1.456.514,18
06. Kostenerstattungen und Kostenumlagen 93.654.602,71 85.105.065,00  92.373.273,95 7.268.208,95
07. Zinsen und ähnliche Einzahlungen 10.920.391,46 9.367.250,00  11.658.702,35 2.291.452,35
08. Einzahlungen aus der Veräußerung
geringwertiger Vermögensgegenstände 180,00
09. sonstige haushaltswirksame Einzahlungen 14.488.825,34 13.636.500,00  14.272.150,28 635.650,28
10. = Summe der Einzahlungen aus
laufender Verwaltungstätigkeit 573.334.975,96 551.626.700,61  577.437.581,51 25.810.880,90
Auszahlungen aus laufender
Verwaltungstätigkeit
11. Personalauszahlungen 125.574.101,37 132.102.110,02  131.273.619,46 -828.490,56 8.072,96
12. Versorgungsauszahlungen    6,00 6,00
13. Auszahlungen für Sach- und
Dienstleistungen und für den Erwerb
geringwertiger Vermögensgegenstände
26.883.514,55 28.024.207,25  27.312.245,31 -711.961,94 3.516.841,96
14. Zinsen und ähnliche Auszahlungen 2.367.687,23 2.969.800,00  2.405.710,43 -564.089,57
15. Transferauszahlungen 217.208.483,48 212.171.170,77  224.405.628,43 12.234.457,66 3.713.816,80
16. sonstige haushaltswirksame Auszahlungen 127.511.243,72 141.958.869,71  134.859.644,97 -7.099.224,74 160.765,25
17. = Summe der Auszahlungen aus
laufender Verwaltungstätigkeit 499.545.030,35 517.226.157,75  520.256.854,60 3.030.696,85 7.399.496,97
18. Saldo aus laufender
Verwaltungstätigkeit (Zeile 10 abzüglich
Zeile 17)
73.789.945,61 34.400.542,86  57.180.726,91 22.780.184,05 -7.399.496,97

JA 29


Einzahlungen und Auszahlungen Ergebnis des
Vorjahres 2018
Ansätze des
Haushaltsjahres
2019
Veränderung
durch Nachtrag
mehr (+) /
weniger (-) 2019
Ergebnis des
Haushaltsjahres
2019
mehr (+) /
weniger (-) 4)
2019
Ermächtigung
aus Haushalts-
vorjahren 2019
Zu Spalte 6: Davon bisher
nicht bewilligte über-
/außerplanmäßige
Aufwendungen 5) 2019
 - Euro -
1 2 3 4 5 6 7 8
Einzahlungen für Investitionstätigkeit
19. Zuwendungen für Investitionstätigkeit 2.962.715,14 3.699.950,00  3.331.826,16 -368.123,84
20. Beiträge u.ä. Entgelte für
Investitionstätigkeit 2.931.093,12 2.707.700,00  4.302.812,92 1.595.112,92
21. Veräußerung von Sachvermögen 6.701.478,98 17.090.000,00  15.554.779,55 -1.535.220,45
22. Finanzvermögensanlagen
23. sonstige Investitionstätigkeit 1.462.350,60 2.302.166,00  1.803.898,31 -498.267,69
24. = Summe der Einzahlungen aus
Investitionstätigkeit 14.057.637,84 25.799.816,00  24.993.316,94 -806.499,06
Auszahlungen für Investitionstätigkeiten
25. Erwerb von Grundstücken und Gebäuden 1.977.095,57 4.349.000,00  3.306.034,34 -1.042.965,66 4.520.744,87
26. Baumaßnahmen 15.875.853,27 23.986.100,00  18.680.975,31 -5.305.124,69 18.227.224,01
27. Erwerb von beweglichem Sachvermögen 4.536.170,52 7.748.800,00  6.700.653,79 -1.048.146,21 4.687.305,88
28. Erwerb von Finanzvermögensanlagen 336.610,26 315.000,00  343.661,16 28.661,16
29. Aktivierbare Zuwendungen 6.376.968,30 10.095.000,00  6.003.861,65 -4.091.138,35 7.577.070,03
30. Sonstige Investitionstätigkeit 19.000.000,00 66.200.000,00  30.204.000,00 -35.996.000,00
31. = Summe der Auszahlungen aus
Investitionstätigkeit 48.102.697,92 112.693.900,00  65.239.186,25 -47.454.713,75 35.012.344,79
32. Saldo aus Investitionstätigkeit -34.045.060,08 -86.894.084,00  -40.245.869,31 46.648.214,69 -35.012.344,79
33. Finanzmittel-Überschuss/-Fehlbetrag
(Summen Zeile 18 und 32) 39.744.885,53 -52.493.541,14  16.934.857,60 69.428.398,74 -42.411.841,76

JA 30


Einzahlungen und Auszahlungen Ergebnis des
Vorjahres 2018
Ansätze des
Haushaltsjahres
2019
Veränderung
durch Nachtrag
mehr (+) /
weniger (-) 2019
Ergebnis des
Haushaltsjahres
2019
mehr (+) /
weniger (-) 4)
2019
Ermächtigung
aus Haushalts-
vorjahren 2019
Zu Spalte 6: Davon bisher
nicht bewilligte über-
/außerplanmäßige
Aufwendungen 5) 2019
 - Euro -
1 2 3 4 5 6 7 8
Ein-, Auszahlungen aus
Finanzierungstätigkeit
34. Einzahlungen aus Finanzierungstätigkeit;
Aufnahme von Krediten und inneren Darlehen
für Investitionstätigkeit
90.086.129,66   43.283.420,60 43.283.420,60
35. Auszahlungen aus Finanzierungstätigkeit;
Tilgung von Krediten und Rückzahlung von
inneren Darlehen für Investitionstätigkeit
93.679.245,51 3.613.000,00  46.896.262,98 43.283.262,98
36. Saldo aus Finanzierungstätigkeit (Saldo
aus Zeile 34 und 35) -3.593.115,85 -3.613.000,00  -3.612.842,38 157,62
37. Finanzmittelveränderung (Summe Zeile
33 und 36) 36.151.769,68 -56.106.541,14  13.322.015,22 69.428.556,36 -42.411.841,76
38. haushaltsunwirksame Einzahlungen (u.a.
Geldanlagen, Liquiditätskredite) 148.335.986,35   133.126.797,80 133.126.797,80
39. haushaltsunwirksame Auszahlungen (u.a.
Geldanlagen, Liquiditätskredite) 159.985.258,61   160.144.572,44 160.144.572,44
40. Saldo aus haushaltsunwirksamen
Vorgängen (Zeile 38 und Zeile 39) -11.649.272,26   -27.017.774,64 -27.017.774,64
41. +/- Anfangsbestand an Zahlungsmitteln zu
Beginn des Jahres 61.723.050,52   86.225.547,94 86.225.547,94
42. = Endbestand an Zahlungsmitteln
(Liquide Mittel am Ende d. Jahres) (Summe
a. Zeilen 37,40,41)
86.225.547,94 -56.106.541,14  72.529.788,52 128.636.329,66 -42.411.841,76

1) nicht für Investitionstätigkeit
2) ohne Beträge u.ä. Entgelte für Investitionstätigkeit
3) außer für Investitionstätigkeit
4) Spalte 6 = Spalte 5 - Summe (Spalte 3 + Spalte 4) (Vergleich zwischen den Jahresergebnissen und den
 Haushaltsansätzen gemäß § 54 KomHKVO)
5) Die Angaben in Spalte 8 können dem Jahresabschluss in einer gesonderten Anlage beigefügt werden.
6) Die Zeilen 38 bis 42 können optional ergänzt werden.

JA 31
4.2"""


def _rollen(text: str, year: int) -> dict[str, dict]:
    zeilen, fehler, _ = finanzberichte.finanzprobe(
        finanzberichte.parse_finanzrechnung(text, year))
    assert fehler == []
    return {z["role"]: z for z in zeilen if z["role"]}


# --- Was auf der Seite steht -------------------------------------------------

def test_kassensicht_2024_neben_dem_jahresueberschuss():
    """Die Zahl, um die es geht: Die Ergebnisrechnung desselben Dokuments
    weist für 2024 einen Überschuss von 6,1 Mio. € aus — hier stehen
    22,4 Mio. € weniger Geld in der Kasse. Beides ist richtig."""
    r = _rollen(FR_2024, 2024)
    assert r["balance_operating"]["result"] == 58_304_030.27
    assert r["balance_capital"]["result"] == -80_682_457.76
    assert r["cash_surplus"]["result"] == -22_378_427.49
    assert r["total_out_capital"]["result"] == 96_370_276.14
    # Und die Antwort auf „warum wird das Geplante nicht gebaut?": Geld aus
    # Vorjahren, das in diesem Jahr noch ausgegeben werden durfte.
    assert r["total_out_capital"]["authorization"] == 58_768_256.08
    # Bis in die Kasse hinein: nach Tilgung, mit Anfangs- und Endbestand.
    assert r["cash_change"]["result"] == -25_264_573.53
    assert r["opening_balance"]["result"] == 143_077_382.44
    assert r["closing_balance"]["result"] == 118_001_891.26


def test_der_ansatz_steht_daneben():
    """Die Finanzrechnung führt Plan und Ist nebeneinander — geplant war ein
    Fehlbetrag von 94,2 Mio. €, geworden sind es 22,4 Mio. €."""
    r = _rollen(FR_2024, 2024)
    assert r["cash_surplus"]["plan"] == -94_165_040.17
    assert r["total_out_capital"]["plan"] == 109_052_867.00
    assert r["total_out_capital"]["plan_kind"] == "budget"


# --- Die Kaskade -------------------------------------------------------------

@pytest.mark.parametrize("text,year", [(FR_2024, 2024), (FR_2019, 2019)])
def test_die_kaskade_geht_in_beiden_layouts_auf(text, year):
    zeilen = finanzberichte.parse_finanzrechnung(text, year)
    uebernommen, fehler, _ = finanzberichte.finanzprobe(zeilen)
    assert fehler == []
    assert uebernommen == zeilen
    r = {z["role"]: z for z in zeilen if z["role"]}
    for field in ("result", "plan"):
        assert (r["total_in_operating"][field] - r["total_out_operating"][field]
                == pytest.approx(r["balance_operating"][field], abs=1.0))
        assert (r["total_in_capital"][field] - r["total_out_capital"][field]
                == pytest.approx(r["balance_capital"][field], abs=1.0))
        assert (r["balance_operating"][field] + r["balance_capital"][field]
                == pytest.approx(r["cash_surplus"][field], abs=1.0))


def test_die_nummern_verschieben_sich_die_rollen_nicht():
    """Der Grund, warum an der Rolle gehangen wird und nicht an der Nummer:
    Der Finanzmittelsaldo ist 2019 die Zeile 33 und 2024 die Zeile 32."""
    assert _rollen(FR_2019, 2019)["cash_surplus"]["nr"] == 33
    assert _rollen(FR_2024, 2024)["cash_surplus"]["nr"] == 32


def test_ein_jahrgang_der_die_probe_reisst_wird_verworfen():
    """Eine einzige veränderte Ziffer in einer Auszahlungsart, und die
    Summenzeile stimmt nicht mehr — dann kommt der ganze Jahrgang nicht in
    den Bestand, statt mit einer stillen Lücke angezeigt zu werden."""
    kaputt = FR_2024.replace("25. Baumaßnahmen 12.484.250,14 22.291.400,00",
                             "25. Baumaßnahmen 12.484.250,14 12.291.400,00")
    assert kaputt != FR_2024
    zeilen = finanzberichte.parse_finanzrechnung(kaputt, 2024)
    uebernommen, fehler, _ = finanzberichte.finanzprobe(zeilen)
    assert uebernommen == []
    assert any("Auszahlungen für Investitionstätigkeit" in f for f in fehler)


def test_eine_fehlende_summenzeile_ist_kein_stiller_ausfall():
    ohne = FR_2024.replace("32. Finanzmittel-Überschuss/-Fehlbetrag", "32. Sonstiges")
    uebernommen, fehler, _ = finanzberichte.finanzprobe(
        finanzberichte.parse_finanzrechnung(ohne, 2024))
    assert uebernommen == []
    assert any("cash_surplus" in f for f in fehler)


# --- Die optionalen Zeilen ---------------------------------------------------

def test_die_optionalen_zeilen_duerfen_fehlen():
    """Das Dokument sagt es selbst: „Die Zeilen 37 bis 41 können optional
    ergänzt werden." Fehlen sie, bleibt der Jahrgang gültig — nur die
    Bestandskette fehlt dann."""
    gekuerzt = FR_2024[:FR_2024.index("37. haushaltsunwirksame")]
    zeilen = finanzberichte.parse_finanzrechnung(gekuerzt, 2024)
    uebernommen, fehler, hinweise = finanzberichte.finanzprobe(zeilen)
    assert fehler == []
    roles = {z["role"] for z in uebernommen if z["role"]}
    assert "cash_surplus" in roles and "cash_change" in roles
    assert "closing_balance" not in roles and "opening_balance" not in roles
    assert any("closing_balance" in h for h in hinweise)


def test_eine_gerissene_kuer_kostet_nur_die_kuer():
    """Stimmt der Endbestand nicht, verschwinden die drei Bestandszeilen —
    der Finanzmittelsaldo bleibt, weil er an einer anderen Probe hängt."""
    kaputt = FR_2024.replace(
        "(Liquide Mittel am Ende d. Jahres) 5) 143.077.382,44 -97.051.240,17  "
        "118.001.891,26 215.053.131,43",
        "(Liquide Mittel am Ende d. Jahres) 5) 143.077.382,44 -97.051.240,17  "
        "218.001.891,26 315.053.131,43")
    assert kaputt != FR_2024
    uebernommen, fehler, hinweise = finanzberichte.finanzprobe(
        finanzberichte.parse_finanzrechnung(kaputt, 2024))
    assert fehler == []
    roles = {z["role"] for z in uebernommen if z["role"]}
    assert "cash_surplus" in roles
    assert "closing_balance" not in roles
    assert any("closing_balance verworfen" in h for h in hinweise)


# --- Die Fallen des PDF-Extrakts ---------------------------------------------

def test_der_seitenfuss_verdraengt_keinen_posten():
    """„JA 29" steht am Ende der ersten Tabellenseite — also VOR dem echten
    Posten 29 auf der zweiten. Wer ihn für eine Zeilennummer hält, verliert
    eine Auszahlungsart und reißt damit die Summenprobe."""
    assert "JA 29" in FR_2024
    zeilen = finanzberichte.parse_finanzrechnung(FR_2024, 2024)
    z29 = next(z for z in zeilen if z["nr"] == 29)
    assert z29["label"].startswith("Sonstige Investitionstätigkeit")
    assert z29["result"] == 27_581_067.00


def test_querverweise_nehmen_der_zeile_nicht_ihre_zahlen():
    """2019 heißt der Saldo „Saldo aus laufender Verwaltungstätigkeit (Zeile 10
    abzüglich Zeile 17)". Die „10" darin sieht aus wie eine Zeilennummer."""
    assert "(Zeile 10 abzüglich" in FR_2019
    r = _rollen(FR_2019, 2019)
    assert r["balance_operating"]["result"] == 57_180_726.91
    assert "Zeile" not in r["balance_operating"]["label"]


def test_postennummer_auch_ohne_punkt():
    """2021–2024 schreibt die Stadt „35 Saldo aus Finanzierungstätigkeit"."""
    assert re.search(r"^35 Saldo", FR_2024, re.M)
    assert _rollen(FR_2024, 2024)["balance_financing"]["result"] == -2_886_146.04


def test_zeile_ohne_ansatz_erfindet_keinen():
    """„12. Versorgungsauszahlungen 6,00 6,00" (2019): Ergebnis und Abweichung
    sind derselbe Betrag, weil kein Ansatz dahintersteht. Ein erfundener
    Ansatz von 6,00 € risse die Summenprobe des Ansatzes."""
    z = next(z for z in finanzberichte.parse_finanzrechnung(FR_2019, 2019)
             if z["nr"] == 12)
    assert z["result"] == 6.0 and z["plan"] is None and z["budgeted"] is None


def test_bestandszeilen_tragen_keinen_ansatz():
    """Ein Kassenbestand wird nicht veranschlagt. Was der Spaltenapparat dort
    als Plan fände, wäre der Vorjahreswert — deshalb steht dort nichts."""
    r = _rollen(FR_2024, 2024)
    for role in ("opening_balance", "closing_balance", "balance_non_budgetary"):
        assert r[role]["plan"] is None and r[role]["deviation"] is None
        assert r[role]["result"] is not None


def test_ermaechtigungsspalte_nur_wo_der_kopf_sie_hinter_dem_ergebnis_fuehrt():
    """2019 und 2024 führen sie rechts außen. Fällt die Spaltenüberschrift
    weg, wird nichts geraten — die letzte Zahl der Zeile ist dann eine
    andere Spalte."""
    assert _rollen(FR_2019, 2019)["total_out_capital"]["authorization"] \
        == 35_012_344.79
    ohne = FR_2024.replace("Ermächtigung\naus Haushalts-\nvorjahren", "Zu Spalte 6")
    assert ohne != FR_2024
    r = _rollen(ohne, 2024)
    assert all(z["authorization"] is None for z in r.values())
    # Die Zahlen selbst bleiben unberührt.
    assert r["cash_surplus"]["result"] == -22_378_427.49


def test_ermaechtigungen_haben_ihre_eigene_probe():
    """Reißt ihre Summe, fällt die Spalte — nicht der Jahrgang. So bleibt der
    Jahrgang 2022 im Bestand, dessen PDF-Extrakt Leerzeichen mitten in die
    übertragenen Beträge setzt („3.912. 463,20")."""
    kaputt = FR_2024.replace("-7.340.301,73 42.291.517,03",
                             "-7.340.301,73 12.291.517,03")
    assert kaputt != FR_2024
    uebernommen, fehler, hinweise = finanzberichte.finanzprobe(
        finanzberichte.parse_finanzrechnung(kaputt, 2024))
    assert fehler == []
    assert any("Ermächtigungen verworfen" in h for h in hinweise)
    assert all(z["authorization"] is None for z in uebernommen)
    r = {z["role"]: z for z in uebernommen if z["role"]}
    assert r["cash_surplus"]["result"] == -22_378_427.49


# --- Über Dokumentgrenzen hinweg ---------------------------------------------

def test_kassenkette_zwischen_zwei_jahrgaengen():
    """Der Endbestand von 2019 (72,5 Mio. €) müsste im Jahresabschluss des
    Folgejahres als Anfangsbestand wieder auftauchen. Passt er nicht,
    verlieren beide Jahrgänge ihre Finanzrechnung."""
    a = finanzberichte.parse_finanzrechnung(FR_2019, 2019)
    b = [dict(z) for z in finanzberichte.parse_finanzrechnung(FR_2024, 2024)]
    assert finanzberichte.kassenkette({2019: a, 2020: b}) != []
    for z in b:
        if z["role"] == "opening_balance":
            z["result"] = 72_529_788.52
    assert finanzberichte.kassenkette({2019: a, 2020: b}) == []


def test_kassenkette_schweigt_ohne_bestandszeilen():
    """Fehlende Zeilen sind kein gerissenes Glied — sie sind laut Dokument
    optional."""
    a = finanzberichte.parse_finanzrechnung(FR_2019, 2019)
    ohne = [z for z in finanzberichte.parse_finanzrechnung(FR_2024, 2024)
            if z["role"] != "opening_balance"]
    assert finanzberichte.kassenkette({2019: a, 2020: ohne}) == []


# --- Speichern ---------------------------------------------------------------

def test_store_finanzrechnung_roundtrip(tmp_path, source):
    store = CouncilStore(tmp_path / "c.sqlite")
    zeilen, _, _ = finanzberichte.finanzprobe(
        finanzberichte.parse_finanzrechnung(FR_2024, 2024))
    q = source("Jahresabschluss 2024", "https://example.org/ja2024.pdf",
               probe="cash_flow_cascade")
    assert store.save_finanzrechnung(2024, zeilen, q) == len(zeilen)
    assert store.save_finanzrechnung(2024, zeilen, q) == len(zeilen)  # idempotent
    assert store.finanzrechnung_jahre() == [2024]
    geladen = {z["role"]: z for z in store.get_finanzrechnung(2024) if z["role"]}
    assert geladen["cash_surplus"]["result"] == -22_378_427.49
    assert geladen["total_out_capital"]["authorization"] == 58_768_256.08
    assert geladen["closing_balance"]["plan"] is None
    # Jede Zeile weiß, woher sie kommt.
    assert all(z["herkunft_id"] for z in store.get_finanzrechnung(2024))
    assert store.herkunft_luecken().get("council_finanzrechnung") is None
    store.close()


def test_kasse_ist_eine_eigene_einheit_des_jahresabschlusses():
    """Ein Jahrgang gilt erst als fertig, wenn auch seine Finanzrechnung
    drinsteht — sonst käme sie für die schon gelesenen Jahrgänge nie nach."""
    assert "kasse" in finanzquellen.EBENEN

