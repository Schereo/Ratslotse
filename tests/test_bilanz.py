"""Bilanz der Stadt — Abschnitt 2.1 des Jahresabschlusses.

Die Fixtures sind **echte** pypdf-Extrakte aus den Jahresabschluss-Anlagen im
Ratsinformationssystem, gekürzt um Unterpositionen, an denen nichts hängt
(``3.2 Beteiligungen``, ``2.5 Kunstgegenstände``, …). Was stehen bleibt, sind
die neun Hauptposten, die Unterzeilen aus :data:`bilanz.ROLLEN` und jede
Stelle, an der sich der Parser verlesen kann. Beide Fixtures gehen auf den
Cent auf — in beiden Spalten.

Sie decken die **zwei** Layouts ab, die die Stadt benutzt:

* :data:`B_2019` — römische Ziffern, Aktiva-Block **vor** Passiva-Block, mit
  gedruckter Bilanzsumme unter der Tabelle (und die steht doppelt da, einmal
  je Spaltenblock).
* :data:`B_2024` — arabische Ziffern, beide Seiten **zweispaltig
  verschränkt**: Die Aktivseite fängt mitten in der Zeile wieder an, direkt
  hinter den Beträgen der Passivseite. Dazu Fußnotenmarken („1)"), ein
  Klammerbetrag (die Vorbelastung aus Haushaltsresten) und **keine**
  gedruckte Bilanzsumme — ab 2021 der Normalfall.

Der dritte Fall, 2020 (römisch **und** verschränkt), braucht keine eigene
Fixture: Er ist die Kreuzung der beiden hier, und dass der Parser ohne eine
einzige Fallunterscheidung auskommt, ist genau der Punkt.
"""
from __future__ import annotations

import re

import pytest

from council import bilanz, finanzquellen
from council.store import CouncilStore

# --- 2019: Blocksatz, römisch, mit gedruckter Bilanzsumme --------------------

B_2019 = """Bilanz Stadt Oldenburg zum 31.12.2019
Aktiva 2018 2019
 - Euro - - Euro -
I. Immaterielles Vermögen 59.188.979,75 62.738.068,55
1.1 Konzessionen 5.100,00 4.558,00
1.3 Ähnliche Rechte
1.4 Geleist. Investitionszuwendungen
u -zuschüsse 51.649.336,00 54.496.322,00
II. Sachvermögen 606.731.392,48 610.501.602,80
2.1 Unbeb. Grundstücke u. grundst.-
gleiche Rechte 115.162.247,05 116.271.293,86
2.3 Infrastrukturvermögen 405.255.542,33 396.919.521,91
JA 17
III. Finanzvermögen 386.321.921,99 430.128.253,77
3.9 Durchlaufende Posten und
Sonstige Vermögensgegenstände 11.025.419,02 44.504.174,06
IV. Liquide Mittel 86.225.547,94 72.529.788,52
V. Aktive Rechnungsabgrenzung 17.565.955,89 17.671.780,50


Passiva 2018 2019
 - Euro - - Euro -
I. Nettoposition 800.332.466,04 809.656.760,94
1.1 Basisreinvermögen 519.381.880,49 521.442.541,74
1.4 Sonderposten 204.195.753,24 197.664.163,24
II. Schulden 84.775.512,21 98.648.410,90
2.1 Geldschulden 63.667.298,70 60.054.456,32
2.3 Verb. aus Lieferungen und
Leistungen 4.928.198,51 5.293.902,58
III. Rückstellungen 261.483.344,08 276.036.747,45
3.1 Pensionsrückst. und ähnliche
Verpflichtungen 239.047.363,00 251.616.299,00
3.1.1 Pensionsrückstellungen 207.506.392,00 218.038.387,00
3.1.2 Beihilferückstellungen 31.540.971,00 33.577.912,00
IV. Passive Rechnungsabgrenzung 9.442.475,72 9.227.574,85


Bilanzsumme 2018 2019
 - Euro - - Euro -
 1.156.033.798,05 1.193.569.494,14


Bilanzsumme 2018 2019
 - Euro - - Euro -
 1.156.033.798,05 1.193.569.494,14

Vermerke unter der Bilanz
"""

# --- 2024: verschränkt, arabisch, ohne gedruckte Bilanzsumme ----------------
#
# Die drei Stellen, an denen ein Parser hier scheitert, stehen bewusst drin:
#
#   * „4.372.861,06 4.439.504,15 2.   Sachvermögen 1) 608…" — die Aktivseite
#     fängt hinter den Beträgen der Passivseite wieder an, mitten in der
#     Zeile. Wer an `^` trennt, verliert jeden zweiten Hauptposten.
#   * „(7.443.753,16) (6.003.088,68)" — die Vorbelastung aus Haushaltsresten
#     gehört zu keiner Bilanzposition und hinge sonst als dritter und vierter
#     Betrag an der Zeile davor.
#   * „1) " hinter dem Namen — die Fußnotenmarke steht zwischen Label und
#     Betrag und darf im Bezeichnungstext nicht landen.

B_2024 = """Bilanz Stadt Oldenburg zum 31.12.2024
Aktiva 2023 2024

Passiva 2023 2024
 - Euro - - Euro -

 - Euro - - Euro -
1.   Immaterielles Vermögen 1) 84.509.900,30 91.394.171,68

1.       Nettoposition 923.994.532,25 926.869.052,49
1.1 Konzessionen 2.390,00 1.848,00

1.1     Basisreinvermögen 524.002.467,39 524.851.409,44
1.4 Geleistete
Investitionszuweisungen und -
zuschüsse
73.863.334,00 80.456.214,00

1.2     Rücklagen 187.515.505,50 210.654.550,36
1.2.3  Rücklagen aus Investitions-
zuwendungen für nicht abnutzbare
Vermögensgegenstände
4.372.861,06 4.439.504,15 2.   Sachvermögen 1) 608.118.677,60 605.573.107,06

1.3     Jahresergebnis 24.172.129,20 6.136.250,91 2.3 Infrastrukturvermögen 371.184.733,54 361.653.777,68

            mit Angabe des Betrages der
Vorbelastung aus Haushaltsresten für
Aufwendungen (in Klammern)
(7.443.753,16) (6.003.088,68)
2.8 Vorräte 64.741,41 85.882,61

1.4     Sonderposten 1) 188.304.430,16 185.226.841,78 3.   Finanzvermögen 1) 493.171.333,76 645.348.451,45

2.       Schulden 84.383.735,40 207.116.175,19 4.   Liquide Mittel 143.077.382,44 118.001.891,26

2.1     Geldschulden 46.577.117,75 43.690.971,71 5.   Aktive Rechnungsabgrenzung 18.017.383,10 19.671.338,55

2.5     Sonstige Verbindlichkeiten 27.152.869,01 156.518.905,60
JA 18

3.       Rückstellungen 329.095.270,90 337.210.902,05

3.1     Pensionsrückstellungen und
ähnliche Verpflichtungen 1) 290.925.292,00 311.789.660,00

3.1.1  Pensionsrückstellungen 249.721.281,00 266.259.316,00

3.1.2  Beihilferückstellungen 41.204.011,00 45.530.344,00

4.       Passive Rechnungsabgrenzung 9.421.138,65 8.792.830,27

3. Ergebnisrechnung einschließlich Plan-Ist-Vergleich
"""

#: Die Summen, die beide Fixtures ergeben müssen — ausgerechnet aus den neun
#: Hauptposten, nicht abgeschrieben.
SUMME = {2018: 1_156_033_798.05, 2019: 1_193_569_494.14,
         2023: 1_346_894_677.20, 2024: 1_479_988_960.00}


def _lies(text: str, jahr: int) -> dict:
    """Parsen und die Pflichtprobe bestehen — sonst ist der Test schon kaputt."""
    jahrgang, fehler, _ = bilanz.bilanzprobe(bilanz.parse_bilanz(text, jahr))
    assert jahrgang is not None, fehler
    return jahrgang


def _werte(jahrgang: dict) -> dict[str, float]:
    return {p["rolle"]: p["wert"] for p in jahrgang["posten"]}


# --- Beide Layouts ----------------------------------------------------------

@pytest.mark.parametrize("text, jahr", [(B_2019, 2019), (B_2024, 2024)])
def test_beide_layouts_gehen_auf(text, jahr):
    """Aktiva = Passiva, auf den Cent — in beiden Layouts und beiden Spalten."""
    jahrgang = _lies(text, jahr)
    posten = jahrgang["posten"]
    assert jahrgang["bilanzsumme"] == pytest.approx(SUMME[jahr], abs=0.01)
    assert jahrgang["ausgleich_differenz"] == pytest.approx(0.0, abs=0.01)
    # Auch die Vorjahresspalte trägt für sich — daraus entsteht beim Einlesen
    # der älteste Stichtag, der kein eigenes Dokument hat.
    for seite in (bilanz.AKTIVA, bilanz.PASSIVA):
        assert bilanz.summe(posten, seite, "wert_vorjahr") == pytest.approx(
            SUMME[jahr - 1], abs=0.01)


@pytest.mark.parametrize("text, jahr", [(B_2019, 2019), (B_2024, 2024)])
def test_alle_pflichtposten_stehen_auf_ihrer_seite(text, jahr):
    posten = {p["rolle"]: p for p in _lies(text, jahr)["posten"]}
    assert set(bilanz.PFLICHT_ROLLEN) <= set(posten)
    for rolle in bilanz.HAUPTPOSTEN[bilanz.AKTIVA]:
        assert posten[rolle]["seite"] == bilanz.AKTIVA
        assert posten[rolle]["ebene"] == 1
    for rolle in bilanz.HAUPTPOSTEN[bilanz.PASSIVA]:
        assert posten[rolle]["seite"] == bilanz.PASSIVA


def test_verschraenktes_layout_verliert_keinen_hauptposten():
    """Die Probe auf die Bauart ab 2021: Die Aktivseite fängt **mitten in der
    Zeile** wieder an, hinter den Beträgen der Passivseite. Ein Parser, der
    Zeilen an ``^`` trennt, verlöre genau die vier Posten hier."""
    werte = _werte(_lies(B_2024, 2024))
    assert werte["sachvermoegen"] == 605_573_107.06
    assert werte["infrastrukturvermoegen"] == 361_653_777.68
    assert werte["finanzvermoegen"] == 645_348_451.45
    assert werte["liquide_mittel"] == 118_001_891.26
    assert werte["aktive_rap"] == 19_671_338.55


def test_roemische_und_arabische_nummern_stehen_daneben():
    """Die Gliederungsnummer wird mitgeschrieben, aber nichts hängt an ihr —
    sonst brauchte jedes Layout seinen eigenen Zweig."""
    n2019 = {p["rolle"]: p["nr"] for p in _lies(B_2019, 2019)["posten"]}
    n2024 = {p["rolle"]: p["nr"] for p in _lies(B_2024, 2024)["posten"]}
    assert n2019["sachvermoegen"] == "II" and n2024["sachvermoegen"] == "2"
    # Dieselbe Nummer, zwei verschiedene Posten: „1." ist ab 2021 auf der
    # Aktivseite das immaterielle Vermögen und auf der Passivseite die
    # Nettoposition. Deshalb ist die Rolle der Schlüssel.
    assert n2024["immaterielles_vermoegen"] == n2024["nettoposition"] == "1"


def test_der_wortlaut_des_dokuments_bleibt_stehen():
    """Die Bezeichnung ist der Wortlaut, nicht unser Kurzname — 2019 kürzt die
    Stadt ab, 2024 schreibt sie aus. Beide Schreibweisen müssen ankommen, und
    die Fußnotenmarke darf nicht mit hineinrutschen."""
    b19 = {p["rolle"]: p["bezeichnung"] for p in _lies(B_2019, 2019)["posten"]}
    b24 = {p["rolle"]: p["bezeichnung"] for p in _lies(B_2024, 2024)["posten"]}
    assert b19["pensionen_gesamt"] == "Pensionsrückst. und ähnliche Verpflichtungen"
    assert b24["pensionen_gesamt"] == "Pensionsrückstellungen und ähnliche Verpflichtungen"
    assert b24["immaterielles_vermoegen"] == "Immaterielles Vermögen"   # ohne „1)"
    assert b24["sonderposten"] == "Sonderposten"
    assert not any(re.search(r"\d\)", w) for w in b24.values())


def test_seitenfuss_und_klammerbetrag_verdraengen_keinen_posten():
    """Zwei Fallen des PDF-Extrakts, beide mitten in der Tabelle: der
    Seitenfuß „JA 18" auf eigener Zeile und die Vorbelastung aus
    Haushaltsresten in Klammern. Letztere hinge sonst als dritter und vierter
    Betrag an der Zeile davor — und die flöge über die Zwei-Spalten-Regel
    heraus."""
    werte = _werte(_lies(B_2024, 2024))
    assert werte["infrastrukturvermoegen"] == 361_653_777.68
    assert werte["rueckstellungen"] == 337_210_902.05
    assert 6_003_088.68 not in werte.values()


# --- Die Pflichtprobe -------------------------------------------------------

def test_aktiva_ungleich_passiva_verwirft_den_jahrgang():
    """Eine Bilanz, die nicht ausgeglichen ist, ist keine Bilanz, sondern ein
    Lesefehler — und dann ist auch alles andere an diesem Stichtag unsicher.
    Deshalb fällt der ganze Jahrgang, nicht nur die eine Zeile."""
    kaputt = B_2024.replace("4.       Passive Rechnungsabgrenzung 9.421.138,65 8.792.830,27",
                            "4.       Passive Rechnungsabgrenzung 9.421.138,65 8.782.830,27")
    jahrgang, fehler, hinweise = bilanz.bilanzprobe(bilanz.parse_bilanz(kaputt, 2024))
    assert jahrgang is None
    assert fehler and "gleicht nicht aus" in fehler[0]
    assert hinweise == []


def test_die_toleranz_deckt_die_cent_rundung_und_sonst_nichts():
    """Ein Euro Luft, nicht mehr: Die Bilanz rechnet auf den Cent, und was um
    Beträge daneben liegt, ist keine Rundung, sondern ein Lesefehler."""
    assert bilanz.TOLERANZ == 1.0
    knapp = B_2024.replace("4.       Passive Rechnungsabgrenzung 9.421.138,65 8.792.830,27",
                           "4.       Passive Rechnungsabgrenzung 9.421.138,65 8.792.830,77")
    jahrgang, fehler, _ = bilanz.bilanzprobe(bilanz.parse_bilanz(knapp, 2024))
    assert jahrgang is not None and not fehler


def test_ein_fehlender_hauptposten_ist_kein_stiller_ausfall():
    """Ohne einen der neun Hauptposten ließe sich der Ausgleich gar nicht
    rechnen — und dann ist nicht nachweisbar, dass überhaupt die richtige
    Tabelle gelesen wurde. Das ist ein Fehler, kein Hinweis."""
    ohne = B_2019.replace("V. Aktive Rechnungsabgrenzung 17.565.955,89 17.671.780,50\n", "")
    jahrgang, fehler, _ = bilanz.bilanzprobe(bilanz.parse_bilanz(ohne, 2019))
    assert jahrgang is None
    assert fehler and "aktive_rap" in fehler[0]


def test_ohne_abschnitt_kein_jahrgang():
    jahrgang, fehler, _ = bilanz.bilanzprobe(
        bilanz.parse_bilanz("Rechenschaftsbericht 2024\nkeine Tabelle hier.", 2024))
    assert jahrgang is None and fehler


# --- Die Kür: sie kostet, wenn sie reißt, nur sich selbst --------------------

def test_ein_jahrgang_ohne_gedruckte_bilanzsumme_geht_trotzdem_durch():
    """Ab 2021 druckt die Stadt keine Bilanzsumme mehr unter die Tabelle. Das
    ist kein Mangel: Der Ausgleich beider Seiten belegt sie ohnehin."""
    jahrgang = _lies(B_2024, 2024)
    assert "gedruckte_summe" not in jahrgang
    assert jahrgang["proben"] == ["bilanz_ausgleich", "rueckstellungs_gliederung"]
    # 2019 hat sie — dort ist sie die dritte Bestätigung.
    alt = _lies(B_2019, 2019)
    assert "bilanzsumme_gedruckt" in alt["proben"]
    assert alt["gedruckte_summe"] == pytest.approx(SUMME[2019], abs=0.01)


def test_eine_falsche_gedruckte_summe_kostet_nur_ihre_probe():
    falsch = B_2019.replace("1.156.033.798,05 1.193.569.494,14",
                            "1.156.033.798,05 1.193.569.000,00")
    jahrgang, fehler, hinweise = bilanz.bilanzprobe(bilanz.parse_bilanz(falsch, 2019))
    assert jahrgang is not None and not fehler
    assert "bilanzsumme_gedruckt" not in jahrgang["proben"]
    assert hinweise and "gedruckte Bilanzsumme" in hinweise[0]


# --- Die Gliederung der Rückstellungen --------------------------------------

@pytest.mark.parametrize("text, jahr", [(B_2019, 2019), (B_2024, 2024)])
def test_pension_plus_beihilfe_ergibt_die_oberposition(text, jahr):
    """Der Widerspruch, der diesen Parser ausgelöst hat: Es sind **zwei**
    Zahlen, und beide stimmen. 3.1 schließt die Beihilfe ein, 3.1.1 nicht."""
    jahrgang = _lies(text, jahr)
    w = _werte(jahrgang)
    assert w["pensionsrueckstellungen"] + w["beihilferueckstellungen"] == pytest.approx(
        w["pensionen_gesamt"], abs=0.01)
    assert "rueckstellungs_gliederung" in jahrgang["proben"]
    # Und die Ebenen sagen, welche Zahl über welcher steht.
    ebenen = {p["rolle"]: p["ebene"] for p in jahrgang["posten"]}
    assert ebenen["rueckstellungen"] == 1
    assert ebenen["pensionen_gesamt"] == 2
    assert ebenen["pensionsrueckstellungen"] == ebenen["beihilferueckstellungen"] == 3


def test_2024_traegt_die_zahlen_aus_dem_kopfkommentar():
    """Die drei Beträge, um die es geht — als Regressionsanker, damit ein
    Umbau am Parser sie nicht lautlos verschiebt."""
    w = _werte(_lies(B_2024, 2024))
    assert w["pensionen_gesamt"] == 311_789_660.00
    assert w["pensionsrueckstellungen"] == 266_259_316.00
    assert w["beihilferueckstellungen"] == 45_530_344.00
    # Die Kreditschulden daneben: ein Siebtel der Pensionszusagen.
    assert w["geldschulden"] == 43_690_971.71


def test_eine_gerissene_gliederung_ist_ein_hinweis_kein_ausfall():
    """Die Gliederungsprobe ist Kür. Reißt sie, verliert der Jahrgang **nur
    sie** — die Bilanz gleicht sich ja weiterhin aus, und 3.1.1/3.1.2 gehen
    in keine Summe ein."""
    kaputt = B_2024.replace("3.1.2  Beihilferückstellungen 41.204.011,00 45.530.344,00",
                            "3.1.2  Beihilferückstellungen 41.204.011,00 45.000.000,00")
    jahrgang, fehler, hinweise = bilanz.bilanzprobe(bilanz.parse_bilanz(kaputt, 2024))
    assert jahrgang is not None and not fehler
    assert jahrgang["bilanzsumme"] == pytest.approx(SUMME[2024], abs=0.01)
    assert "rueckstellungs_gliederung" not in jahrgang["proben"]
    assert hinweise and "Rückstellungs-Gliederung" in hinweise[0]


def test_ein_jahrgang_ohne_aufschluesselung_verliert_nur_die_probe():
    """2017 weist den Sammelposten aus, ohne ihn aufzuteilen. Das ist kein
    Fehler — die Zeilen fehlen dort schlicht."""
    ohne = re.sub(r"3\.1\.[12].*\n", "", B_2024)
    jahrgang, fehler, hinweise = bilanz.bilanzprobe(bilanz.parse_bilanz(ohne, 2024))
    assert jahrgang is not None and not fehler and not hinweise
    assert jahrgang["proben"] == ["bilanz_ausgleich"]


# --- Über Dokumentgrenzen: die Vorjahreskette -------------------------------

def _kette() -> dict[int, dict]:
    """Zwei benachbarte Jahrgänge, wie sie beim Einlesen nebeneinanderliegen:
    2023 aus der Vorjahresspalte von 2024, 2024 aus seiner eigenen."""
    j2024 = _lies(B_2024, 2024)
    j2023 = {"jahr": 2023, "posten": [{**p, "wert": p["wert_vorjahr"]}
                                      for p in j2024["posten"]]}
    return {2023: j2023, 2024: j2024}


def test_vorjahreskette_haelt_wenn_beide_dasselbe_sagen():
    assert bilanz.vorjahreskette(_kette()) == []


def test_vorjahreskette_findet_einen_riss():
    """Der Stichtagswert des einen Abschlusses steht im nächsten noch einmal
    als Vorjahr. Zwei getrennt gelesene Dokumente, dieselbe Zahl — weicht
    eine ab, hat sich einer der beiden verlesen."""
    kette = _kette()
    for p in kette[2023]["posten"]:
        if p["rolle"] == "sachvermoegen":
            p["wert"] += 1000.0
    risse = bilanz.vorjahreskette(kette)
    assert len(risse) == 1
    jahr, folge, warum = risse[0]
    assert (jahr, folge) == (2023, 2024)
    assert "sachvermoegen" in warum


def test_vorjahreskette_schweigt_ohne_nachbarn():
    """Ein einzelner Jahrgang hat keine Kette — das ist kein Riss."""
    assert bilanz.vorjahreskette({2024: _lies(B_2024, 2024)}) == []


# --- Über Parsergrenzen: die Kassenprobe ------------------------------------

def test_kassenprobe_gegen_die_finanzrechnung():
    """Die stärkste Probe des Bereichs: „Liquide Mittel" der Bilanz und
    „Endbestand an Zahlungsmitteln" der Finanzrechnung sind dieselbe Zahl —
    gelesen aus zwei verschieden gebauten Tabellen von zwei getrennt
    geschriebenen Parsern."""
    jahrgaenge = {2024: _lies(B_2024, 2024)}
    assert bilanz.kassenprobe(jahrgaenge, {2024: 118_001_891.26}) == []


def test_kassenprobe_findet_die_abweichung():
    jahrgaenge = {2024: _lies(B_2024, 2024)}
    risse = bilanz.kassenprobe(jahrgaenge, {2024: 118_000_000.00})
    assert len(risse) == 1
    jahr, warum = risse[0]
    assert jahr == 2024
    assert "Liquide Mittel" in warum and "Endbestand" in warum


def test_kassenprobe_schweigt_ohne_finanzrechnung():
    """Ein Jahrgang ohne eingelesene Finanzrechnung fällt still weg —
    fehlende Gegenprobe ist kein Fehler."""
    assert bilanz.kassenprobe({2024: _lies(B_2024, 2024)}, {}) == []


# --- Die Fundstelle ---------------------------------------------------------

def test_die_stiftungsbilanz_wird_nicht_fuer_die_stadt_gehalten():
    """Weiter hinten im selben Heft stehen die Bilanzen der nicht
    rechtsfähigen Stiftungen: dieselbe Gliederung, dieselben Zeilennamen, und
    sie gehen genauso auf — nur um Bilanzsummen von 2,8 Mio. € statt 1,2 Mrd.
    Ein Parser, der die erwischt, merkt es an **keiner** Rechenprobe."""
    stiftung = """Bilanz Stadt Oldenburg zum 31.12.2019
Aktiva 2018 2019
 - Euro - - Euro -
I. Immaterielles Vermögen
II. Sachvermögen 1.637.364,30 2.245.751,32
III. Finanzvermögen 621.831,84 447.484,65
IV. Liquide Mittel 114.186,21 83.200,23
V. Aktive Rechnungsabgrenzung
Passiva 2018 2019
 - Euro - - Euro -
I. Nettoposition 2.161.727,34 2.131.333,82
II. Schulden 211.655,01 645.102,38
III. Rückstellungen
IV. Passive Rechnungsabgrenzung
"""
    # Inhaltsverzeichnis, echte Bilanz, Stiftungsbilanz — in dieser Folge
    # steht es im Dokument, und der erste Treffer ist der falsche.
    text = ("2.1 Bilanz der Stadt Oldenburg zum 31.12.2019 JA 17\n\n"
            + B_2019 + "\n7. Nicht rechtsfähige Stiftungen\n\n" + stiftung)
    jahrgang = _lies(text, 2019)
    assert jahrgang["bilanzsumme"] == pytest.approx(SUMME[2019], abs=0.01)


# --- Der Anhang: die Erläuterungen ------------------------------------------
#
# Gekürzter, sonst wörtlicher Ausschnitt aus Abschnitt 6.2 des Jahresabschlusses
# 2024. 6.2.7 ist der Grund, aus dem es diese Tabelle gibt: Die Schulden
# springen 2024 von 84,4 auf 207,1 Mio. €, und ohne diesen Text läse sich das
# als Verdreifachung.

ANHANG_2024 = """6.2 Erläuterung der wesentlichen Bilanzpositionen
6.2.1 Immaterielles Vermögen JA 34
6.2.2 Sachvermögen JA 35
6.2.3 Finanzvermögen JA 36
6.2.4 Liquide Mittel JA 38
6.2.5 Aktive Rechnungsabgrenzung JA 38
6.2.6 Nettoposition JA 39
6.2.7 Schulden JA 40
6.2.8 Rückstellungen JA 41
6.2.9 Passive Rechnungsabgrenzung JA 42
6.2.10 Eventualverbindlichkeiten JA 43

6.2.1 Immaterielles Vermögen

Das immaterielle Vermögen ist im Vergleich zum Vorjahr um 6,9 Millionen Euro
gestiegen. Ursächlich sind im Wesentlichen die geleisteten Investitionszuwen-
dungen und -zuschüsse.

6.2.2 Sachvermögen

Das Sachvermögen hat sich um 2,5 Millionen Euro verringert. Den Abschreibungen
stehen Zugänge im Bereich der unbebauten Grundstücke gegenüber.

6.2.3 Finanzvermögen

Das Finanzvermögen ist um 152,2 Millionen Euro gestiegen. Der Anstieg entfällt
im Wesentlichen auf die privatrechtlichen Forderungen aus dem Cash-Pooling.

6.2.4 Liquide Mittel

JA 38

Der Bestand an liquiden Mitteln beträgt zum Bilanzstichtag 118,0 Millionen
Euro.

6.2.5 Aktive Rechnungsabgrenzung

Die aktive Rechnungsabgrenzung betrifft im Wesentlichen im Voraus geleistete
Zahlungen.

6.2.6 Nettoposition

Die Nettoposition hat sich um 2,9 Millionen Euro erhöht. Der Zugang entfällt
auf die Rücklagen aus Überschüssen des ordentlichen Ergebnisses, denen ein
geringerer Jahresüberschuss als im Vorjahr gegenübersteht.

6.2.7 Schulden

Nach einem weiteren Jahr ohne eine Kreditneuaufnahme führten die geleisteten
Tilgungen dazu, dass sich die Geldschulden erneut um 2,9 Millionen Euro redu-
zierten auf nun 43,7 Millionen Euro.

Die Sonstigen Verbindlichkeiten haben sich im Jahresvergleich um 129,4 Millio-
nen Euro auf 156,5 Millionen Euro erhöht. Diese Steigerung ist auf statistische
Anforderungen im Zusammenhang mit dem Cash-Pooling zurückzuführen. Da die
Stadt Oldenburg sowohl Cashpool-Einheit als auch Cashpool-Führer ist und diese
Beträge jeweils einzeln aufzuführen sind, ergibt sich eine Bilanzverlängerung
in dem Maße, wie die Kernverwaltung dem Cashpool Gelder zur Verfügung stellt.
Im Rahmen der erstmaligen Buchung führt dies zu Verbindlichkeiten von 138,2
Millionen Euro. Der korrespondierende Posten findet sich auf der Aktivseite der
Bilanz in der Position 3.8 Privatrechtliche Forderungen.

Insgesamt haben sich die Schulden, ohne den Sondereffekt aus dem Cash-Pooling,
von 84,4 Millionen Euro um 15,5 Millionen Euro verringert.

6.2.8 Rückstellungen

Die Pensionsrückstellungen wurden um 16,5 Millionen Euro erhöht, die Beihilfe-
rückstellungen um 4,3 Millionen Euro.

6.2.9 Passive Rechnungsabgrenzung

Die passive Rechnungsabgrenzung betrifft im Wesentlichen Erträge, die erst im
Folgejahr wirksam werden.

6.2.10 Eventualverbindlichkeiten

Die Stadt haftet aus Bürgschaften in Höhe von 12,3 Millionen Euro.
"""


def test_der_anhang_erlaeutert_die_neun_hauptposten_in_bilanzreihenfolge():
    abschnitte = bilanz.parse_erlaeuterungen(ANHANG_2024, 2024)
    assert [a["rolle"] for a in abschnitte] == list(bilanz.PFLICHT_ROLLEN)
    ok, warum = bilanz.erlaeuterungsprobe(abschnitte)
    assert ok, warum


def test_das_inhaltsverzeichnis_ist_nicht_der_anhang():
    """Im Verzeichnis stehen alle zehn Überschriften **dichter** beieinander
    als irgendwo sonst — „nimm die dichteste Fundstelle" landete also genau
    dort und lieferte neun leere Erläuterungen."""
    for a in bilanz.parse_erlaeuterungen(ANHANG_2024, 2024):
        assert len(a["text"]) > 60, a


def test_der_cash_pooling_text_kommt_vollstaendig_mit():
    """Die Auflage aus ``council/bilanz.py``: **Ohne diesen Text darf die Zahl
    207,1 Mio. € nicht angezeigt werden.** Er muss also ankommen — mit
    aufgelöster Silbentrennung, ohne Seitenfüße, in Absätzen."""
    nach_rolle = {a["rolle"]: a for a in bilanz.parse_erlaeuterungen(ANHANG_2024, 2024)}
    schulden = nach_rolle["schulden"]
    assert schulden["nr"] == 7
    assert schulden["ueberschrift"] == "Schulden"
    assert "Bilanzverlängerung" in schulden["text"]
    assert "138,2" in schulden["text"]
    assert "3.8 Privatrechtliche Forderungen" in schulden["text"]
    # Silbentrennung am Zeilenende zusammengezogen, Absätze erhalten.
    assert "redu- zierten" not in schulden["text"]
    assert "reduzierten" in schulden["text"]
    assert schulden["text"].count("\n\n") >= 2
    # Und der Abschnitt endet, wo der nächste anfängt.
    assert "Pensionsrückstellungen wurden" not in schulden["text"]


def test_seitenfuss_zerreisst_keinen_erlaeuterungssatz():
    liquide = next(a for a in bilanz.parse_erlaeuterungen(ANHANG_2024, 2024)
                   if a["rolle"] == "liquide_mittel")
    assert "JA 38" not in liquide["text"]


def test_eventualverbindlichkeiten_gehoeren_zu_keiner_bilanzposition():
    """6.2.10 erläutert keinen Bilanzposten — es gibt nur neun Hauptposten."""
    abschnitte = bilanz.parse_erlaeuterungen(ANHANG_2024, 2024)
    assert len(abschnitte) == 9
    assert not any("Bürgschaften" in a["text"] for a in abschnitte)


def test_ein_verschobener_abschnitt_faellt_auf():
    """Ein Erläuterungstext unter der falschen Bilanzposition wäre eine
    Falschaussage, die keine Rechenprobe je bemerkte. Geprüft wird deshalb
    die Zuordnung — mit demselben Muster, mit dem der Parser oben seine
    Bilanzzeile erkennt."""
    verschoben = ANHANG_2024.replace("6.2.7 Schulden\n", "6.2.7 Rückstellungen\n")
    ok, warum = bilanz.erlaeuterungsprobe(
        bilanz.parse_erlaeuterungen(verschoben, 2024))
    assert not ok
    assert "6.2.7" in warum and "schulden" in warum


def test_ein_leerer_abschnitt_zaehlt_nicht_als_erlaeuterung():
    ok, warum = bilanz.erlaeuterungsprobe(
        [{"rolle": r, "nr": i + 1, "ueberschrift": b, "text": "" if r == "schulden" else "x"}
         for i, (r, b) in enumerate(zip(
             bilanz.PFLICHT_ROLLEN,
             ("Immaterielles Vermögen", "Sachvermögen", "Finanzvermögen",
              "Liquide Mittel", "Aktive Rechnungsabgrenzung", "Nettoposition",
              "Schulden", "Rückstellungen", "Passive Rechnungsabgrenzung")))])
    assert not ok and "keinen Text" in warum


# --- Speichern und wieder herausholen ---------------------------------------

@pytest.fixture()
def quelle():
    from council import herkunft
    return herkunft.Herkunft(
        probe=["bilanz_ausgleich", "bilanz_kassenprobe"],
        fundstelle="Abschnitt 2.1 — Bilanz der Stadt Oldenburg zum 31.12.2024",
        probe_ergebnis="Aktiva und Passiva stimmen auf den Cent überein",
        stand="31.12.2024", art="ris", dokument_id=4711,
        label="Jahresabschluss 2024", url="https://example.org/ja2024.pdf")


def test_store_bilanz_roundtrip(tmp_path, quelle):
    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        jahrgang = _lies(B_2024, 2024)
        assert store.save_bilanz(2024, jahrgang["posten"], quelle) == len(jahrgang["posten"])
        assert store.bilanz_jahre() == [2024]
        rows = store.get_bilanz(2024)
        werte = {r["rolle"]: r["wert"] for r in rows}
        assert werte["pensionen_gesamt"] == 311_789_660.00
        assert sum(r["wert"] for r in rows if r["ebene"] == 1
                   and r["seite"] == "aktiva") == pytest.approx(SUMME[2024], abs=0.01)
        # Aktiva vor Passiva — die Bilanz druckt es so.
        assert rows[0]["seite"] == "aktiva" and rows[-1]["seite"] == "passiva"
        # Die Herkunft hängt an jeder Zeile und trägt beide Proben.
        h = store.get_herkunft([rows[0]["herkunft_id"]])[0]
        assert "bilanz_kassenprobe" in h["probe"]
        # Ein zweiter Lauf ersetzt den Stichtag, statt ihn zu verdoppeln.
        store.save_bilanz(2024, jahrgang["posten"], quelle)
        assert len(store.get_bilanz(2024)) == len(jahrgang["posten"])
    finally:
        store.close()


def test_store_erlaeuterungen_roundtrip(tmp_path, quelle):
    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        abschnitte = bilanz.parse_erlaeuterungen(ANHANG_2024, 2024)
        assert store.save_bilanz_erlaeuterungen(2024, abschnitte, quelle) == 9
        raus = store.get_bilanz_erlaeuterungen(2024)
        assert [r["nr"] for r in raus] == list(range(1, 10))
        schulden = next(r for r in raus if r["rolle"] == "schulden")
        assert "Cash-Pooling" in schulden["text"]
    finally:
        store.close()


# --- Der Ingest -------------------------------------------------------------

def test_bilanz_ist_eine_eigene_einheit_des_jahresabschlusses():
    """Der Cron zieht einen Jahrgang nach, solange **eine** seiner Ebenen
    fehlt. Stünde die Bilanz nicht unter ``EBENEN``, käme sie in den acht
    Jahrgängen, die schon im Bestand stehen, nie nach."""
    assert "bilanz" in finanzquellen.EBENEN
    einheiten = finanzquellen._einheiten_jahresabschluss({"label": "Jahresabschluss 2024"})
    assert (2024, "bilanz") in einheiten


def test_jede_probe_der_bilanz_ist_erklaert():
    """Was in ``herkunft.PROBEN`` fehlt, steht auf der Seite ohne Erklärung —
    und eine Probe, die niemand versteht, ist keine."""
    from council import herkunft
    vergeben = {"bilanz_ausgleich", "bilanzsumme_gedruckt", "rueckstellungs_gliederung",
                "bilanz_vorjahreskette", "bilanz_kassenprobe", "bilanz_erlaeuterung"}
    assert vergeben <= set(herkunft.PROBEN)
    for tabelle in ("council_bilanz", "council_bilanz_erlaeuterungen"):
        assert tabelle in herkunft.HERKUNFT_TABELLEN
