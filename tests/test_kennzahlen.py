"""Kennzahlenübersicht des Rechenschaftsberichts (council/kennzahlen.py).

Die Fixtures sind gekürzte, aber **wörtliche** Auszüge der echten Berichte
(Stand 18.08.2026); die Dokumentnummer steht jeweils dabei. Jede beweist eine
Falle, die beim Vermessen der sechs Jahrgänge aufgefallen ist.

Der Aufbau folgt ``tests/test_anlagenspiegel.py``.
"""
from council import indicators as kz

# Dok 295295, Rechenschaftsbericht 2024 — fünf Jahresspalten, Beschriftungen
# über bis zu drei Zeilen, Werte in drei Formaten (Prozent, Tausenderpunkt,
# Vorzeichen).
TABELLE_2024 = """Haushaltsjahr 2020 2021 2022 2023 2024

Eigenkapitalquote I
(ohne Sonderposten)
53,15%
 53,72% 53,15% 54,62% 50,11%
Anzahl der
Einwohnenden (31.12.
HH-Jahr)
170.693


171.493

173.987 175.878 176.068
Verschuldung in EUR
pro Einwohner
(ohne Rückstellungen)
544,23


491,22 567,12 533,35 1.226,28
Neuverschuldung in EUR
pro Einwohner
(nur Geldschulden)
-21,32
 -19,49 -14,15 -18,01 -16,39
Vermögen in EUR
pro Einwohner
7.203,36 7.441,59 7.561,23 7.555,68 8.294,05
Personalintensitätsquote 25,09%  23,68% 23,62% 24,13% 24,17%

Einwohnerzahl Stand 31.12.2024
*): 176.068

Eigenkapitalquote I
Ermittlung: 100 * Nettoposition (ohne Sonderposten) / Bilanzsumme

RB 121

Neuverschuldung pro Einwohner (nur Geldschulden)
Ermittlung: (Geldschulden Haushaltsjahr - Geldschulden Vorjahr) / Einwohnerzahl

Vermögen pro Einwohner
Ermittlung: Aktiva (ohne Aktive Rechnungsabgrenzung) / Einwohnerzahl
"""

# Dok 219465, Rechenschaftsbericht 2019 — das ältere Layout: ganze Prozent
# statt zwei Nachkommastellen, keine Einwohner-Zeile, und im Rechenweg-Teil
# zweimal der Tippfehler „Eigenkaptalquote".
TABELLE_2019 = """Haushaltsjahr 2015 2016 2017 2018 2019
Eigenkapitalquote I
(ohne Sonderposten)
48% 48% 49% 52% 51%
Vermögen in EUR
pro Einwohner
6.518,41  6.469,95 6.544,95  6.727,26  6.918,67


Eigenkaptalquote I
 Ermittlung: 100 * Nettoposition (ohne Sonderposten) / Bilanzsumme
   Vermögen pro Einwohner
Ermittlung: Gesamtvermögen (inkl. Liquide Mittel) / Einwohnerzahl
"""

# Dok 265441, Rechenschaftsbericht 2022 — hier heißt die Zeile „Aktive
# Personalintensität", und der PDF-Auszug bricht „Einwohnerzahl" mitten
# entzwei.
TABELLE_2022 = """Haushaltsjahr 2018 2019 2020 2021 2022
Aktive Personalintensität 24,42% 24,49% 25,09% 23,68% 23,62%
Ei
nwohnerzahl Stand 31.12.2022: 173.987 (Prognose)
Personalintensitätsquote
Ermittlung: Aufwendungen für aktives Personal * 100 / ordentliche Aufwendungen
"""


def test_fuenf_jahresspalten_werden_gelesen():
    """Die Jahre stehen im Kopf — geraten wird keins.

    Alle sechs Berichte zeigen fünf Spalten. Käme einer mit sechs, verteilte
    ein fester Wert die Zahlen versetzt, und jede Reihe wäre um ein Jahr
    verschoben — der Fehler, der bei einer Jahresreihe niemandem auffällt.
    """
    assert kz.jahresspalten(TABELLE_2024) == [2020, 2021, 2022, 2023, 2024]
    assert kz.jahresspalten(TABELLE_2019) == [2015, 2016, 2017, 2018, 2019]
    assert kz.jahresspalten("Haushaltsjahr 2024") == []


def test_mehrzeilige_beschriftungen_finden_ihre_kennzahl():
    zeilen, unbekannt = kz.parse_kennzahlen(TABELLE_2024, 2024)
    assert unbekannt == []
    werte = {(z["indicator"], z["year"]): z["wert"] for z in zeilen}
    assert werte[("eigenkapitalquote_1", 2020)] == 53.15
    assert werte[("einwohner", 2024)] == 176_068
    assert werte[("verschuldung_je_einwohner", 2024)] == 1226.28
    assert werte[("neuverschuldung_je_einwohner", 2020)] == -21.32
    assert werte[("vermoegen_je_einwohner", 2024)] == 8294.05


def test_neuverschuldung_ist_keine_verschuldung():
    """Das eine Wort enthält das andere — die Muster sind deshalb verankert.

    Ohne Anker fiele „Neuverschuldung in EUR pro Einwohner" auf das Muster
    der Verschuldung, und zwei Zeilen stritten sich um denselben Schlüssel.
    """
    zeilen, _ = kz.parse_kennzahlen(TABELLE_2024, 2024)
    keys = {z["indicator"] for z in zeilen}
    assert "neuverschuldung_je_einwohner" in keys
    assert "verschuldung_je_einwohner" in keys
    neu = [z for z in zeilen if z["indicator"] == "neuverschuldung_je_einwohner"]
    assert all(z["wert"] < 0 for z in neu)          # nicht die andere Zeile


def test_die_fussnote_wird_keine_tabellenzeile():
    """„Einwohnerzahl Stand 31.12.2024*): 176.068" steht unter der Tabelle.

    Ihre Zahl sieht aus wie ein Tabellenwert. Zwei Umbruch-Varianten kommen
    im Bestand vor: 2024 bricht die Zeile vor der Zahl, 2022 mitten im Wort
    („Ei\\nnwohnerzahl").
    """
    for text, year in ((TABELLE_2024, 2024), (TABELLE_2022, 2022)):
        zeilen, unbekannt = kz.parse_kennzahlen(text, year)
        assert unbekannt == []
        assert not any("nwohnerzahl" in z["label"].lower() for z in zeilen)


def test_seitenmarke_wird_kein_wert():
    """„RB 121" steht mitten im Text, und „121" passt auf das Zahlenmuster."""
    zeilen, _ = kz.parse_kennzahlen(TABELLE_2024, 2024)
    assert 121 not in {z["wert"] for z in zeilen}


def test_aktive_personalintensitaet_ist_dieselbe_zeile():
    """2022 heißt sie anders — der Rechenweg ist derselbe.

    „Personalintensität", „Aktive Personalintensität" und
    „Personalintensitätsquote" sind drei Namen für eine Zeile. Wer sie
    trennt, bekommt drei Reihen mit je zwei Punkten.
    """
    zeilen, unbekannt = kz.parse_kennzahlen(TABELLE_2022, 2022)
    assert unbekannt == []
    assert {z["indicator"] for z in zeilen} == {"personalintensitaet"}
    assert len(zeilen) == 5


def test_tippfehler_im_rechenweg_wird_erkannt():
    """Der Bericht 2019 schreibt „Eigenkaptalquote" — ohne i."""
    formeln = kz.parse_formeln(TABELLE_2019, 2019)
    keys = {f["indicator"] for f in formeln}
    assert "eigenkapitalquote_1" in keys


def test_rechenweg_endet_nicht_in_der_naechsten_ueberschrift():
    """Umbrochen wird nur am Trennstrich — sonst ist die Zeile vollständig.

    Zwischen einem Rechenweg und der nächsten Überschrift steht im Bericht
    2019 keine Leerzeile. Wer bis zur nächsten Leerzeile liest, zieht die
    Überschrift in die Formel.
    """
    formeln = {f["indicator"]: f["formula"] for f in kz.parse_formeln(TABELLE_2019, 2019)}
    assert formeln["eigenkapitalquote_1"] == \
        "100 * Nettoposition (ohne Sonderposten) / Bilanzsumme"
    assert formeln["vermoegen_je_einwohner"] == \
        "Gesamtvermögen (inkl. Liquide Mittel) / Einwohnerzahl"


def test_trennstrich_am_zeilenende_wird_geheilt():
    """„Gesamtaufwen-\\ndungen" darf nicht als zwei Wörter enden."""
    text = ("Haushaltsjahr 2015 2016 2017 2018 2019\n"
            "Steuerquote 49% 47% 46% 50% 48%\n"
            "Steuerquote\n"
            "Ermittlung: Steuerträge und ähnliche Abgaben * 100 / ordentliche "
            "Gesamtaufwen-\ndungen\n")
    formula = kz.parse_formeln(text, 2019)[0]["formula"]
    assert formula.endswith("ordentliche Gesamtaufwendungen")


def test_umbruch_ohne_trennstrich_wird_auch_geheilt():
    """Die zweite Umbruch-Art: „… / ordentliche\nGesamtaufwendungen".

    Sie hat keinen Trennstrich. Eine Regel, die nur den Strich kennt, hört
    nach „ordentliche" auf — und ein abgeschnittener Rechenweg ist ein
    falsches Zitat, kein fehlendes. Fortgesetzt wird deshalb, bis eine leere
    Zeile oder eine der dreizehn Überschriften kommt.
    """
    # Dok 250437, Rechenschaftsbericht 2021 — wörtlich.
    text = ("Haushaltsjahr 2017 2018 2019 2020 2021\n"
            "Personalintensität 25,32% 25,13% 25,48% 26,03% 24,72%\n"
            "Personalintensität  \n"
            "Ermittlung: Aufwand für Personal (inklusive Versorgung) * 100 / ordentliche \n"
            "Gesamtaufwendungen \n"
            "   \n"
            "Steuerquote:  \n"
            "Ermittlung: Steuerträge und ähnliche Abgaben * 100 / ordentliche Gesamtaufwendungen\n")
    formeln = {f["indicator"]: f["formula"] for f in kz.parse_formeln(text, 2021)}
    assert formeln["personalintensitaet"] == (
        "Aufwand für Personal (inklusive Versorgung) * 100 / ordentliche "
        "Gesamtaufwendungen")
    # Und die nächste Überschrift ist NICHT mitgerutscht.
    assert "Steuerquote" not in formeln["personalintensitaet"]


def test_toleranz_kommt_aus_der_gedruckten_genauigkeit():
    """48 % gegen 48,32 % ist dieselbe Zahl in zwei Auflösungen.

    Der Bericht 2019 druckt ganze Prozent, ab 2021 stehen zwei
    Nachkommastellen. Ein stumpfer Vergleich meldete jede zweite Zeile.
    """
    assert kz.toleranz(0, 2) == 0.5
    assert kz.toleranz(2, 2) == 0.005


def test_fassungen_trennen_rechenwege_und_nicht_schreibweisen():
    """Neuer Rechenweg = neue Nummer. „inkl." und „inklusive" sind einer."""
    formeln = [
        {"indicator": "vermoegen_je_einwohner", "report_year": 2019,
         "formula": "Gesamtvermögen (inkl. Liquide Mittel) / Einwohnerzahl"},
        {"indicator": "vermoegen_je_einwohner", "report_year": 2020,
         "formula": "Gesamtvermögen (inklusive Liquide Mittel) / Einwohnerzahl"},
        {"indicator": "vermoegen_je_einwohner", "report_year": 2022,
         "formula": "Aktiva (ohne Aktive Rechnungsabgrenzung) / Einwohnerzahl"},
    ]
    n = kz.fassungen(formeln)
    assert n[("vermoegen_je_einwohner", 2019)] == n[("vermoegen_je_einwohner", 2020)]
    assert n[("vermoegen_je_einwohner", 2022)] == 2


def test_ueberlappung_unterscheidet_korrektur_und_definitionswechsel():
    """Drei Ausgänge, und der dritte ist der Grund für diese Einteilung.

    Ein geänderter Rechenweg schaltet den Vergleich NICHT ab — er benennt
    nur, was herauskommt. Sonst bliebe unbemerkt, dass zwei der drei
    Wechsel im Bestand gar keine sind: „Gesamtschulden" wurde „Schulden",
    und die Werte blieben auf den Cent gleich.
    """
    def zelle(bericht, wert, fassung=1, indicator="steuerquote"):
        return {"indicator": indicator, "year": 2021, "report_year": bericht,
                "wert": wert, "stellen": 2, "fassung": fassung}

    bestaetigt, funde = kz.ueberlappungsprobe([
        zelle(2021, 45.90), zelle(2022, 49.05), zelle(2023, 45.92),
        zelle(2021, 26.03, 1, "personalintensitaet"),
        zelle(2022, 25.09, 2, "personalintensitaet"),
        zelle(2021, 556.74, 1, "verschuldung_je_einwohner"),
        zelle(2022, 556.74, 2, "verschuldung_je_einwohner"),
    ])
    assert bestaetigt == 0
    arten = {f["art"] for f in funde}
    assert arten == {"revision", "definition", "umbenennung"}
    revision = next(f for f in funde if f["art"] == "revision")
    assert (revision["alt"], revision["neu"]) == (45.90, 49.05)


def test_vermoegensprobe_multipliziert_zwei_zeilen_gegen_die_bilanz():
    """Die schärfste Probe: zwei Tabellenzeilen mal, und die Bilanz kommt raus.

    Über 2017–2024 geht sie in jedem Jahrgang auf. Die Toleranz ist
    gerechnet, nicht gegriffen: Ein je-Kopf-Wert mit zwei Nachkommastellen
    darf um einen halben Cent danebenliegen, mal 176.068 Einwohnenden also
    um rund 880 €.
    """
    zeilen = [
        {"indicator": "vermoegen_je_einwohner", "year": 2024, "report_year": 2024,
         "wert": 8294.05, "stellen": 2},
        {"indicator": "population", "year": 2024, "report_year": 2024,
         "wert": 176_068.0, "stellen": 0},
    ]
    bilanz = [{"year": 2024, "role": r, "wert": w} for r, w in (
        ("immaterielles_vermoegen", 91_394_171.68), ("sachvermoegen", 605_573_107.06),
        ("finanzvermoegen", 645_348_451.45), ("liquide_mittel", 118_001_891.26),
        ("aktive_rap", 19_671_338.55))]
    # 8.294,05 € × 176.068 = 1.460.316.795,40 €; Aktiva ohne aktive
    # Rechnungsabgrenzung = 1.460.317.621,45 €. Die Differenz von 826,05 € auf
    # 1,46 Mrd. € ist genau das, was die gedruckte Cent-Stelle offenlässt —
    # die Toleranz von 880,34 € ist daraus gerechnet, nicht gegriffen.
    geprueft, risse = kz.vermoegensprobe(zeilen, bilanz)
    assert (geprueft, risse) == (1, [])

    zeilen[0]["wert"] = 8300.00
    geprueft, risse = kz.vermoegensprobe(zeilen, bilanz)
    assert geprueft == 0 and len(risse) == 1


def test_vermoegensprobe_mischt_keine_berichte():
    """Zwei Zeilen aus zwei Berichten wären eine andere Rechnung."""
    zeilen = [
        {"indicator": "vermoegen_je_einwohner", "year": 2024, "report_year": 2024,
         "wert": 8294.05, "stellen": 2},
        {"indicator": "population", "year": 2024, "report_year": 2023,
         "wert": 176_068.0, "stellen": 0},
    ]
    bilanz = [{"year": 2024, "role": "sachvermoegen", "wert": 1.0}]
    assert kz.vermoegensprobe(zeilen, bilanz) == (0, [])


def test_bilanz_gegenprobe_kennt_nur_die_drei_quoten():
    """Bei den je-Kopf-Zahlen rechnet die Stadt mit anderer Abgrenzung.

    „Verschuldung je Einwohner" heißt hier 1.226 €, in ``council_schulden``
    1.673 € — verschiedene Abgrenzung, eigenes Label, niemals in eine Reihe.
    Ein Abgleich meldete dort verlässlich eine Differenz, die keine ist.
    """
    assert set(kz.BILANZ_QUOTE) == {
        "eigenkapitalquote_2", "anlagenintensitaet", "infrastrukturquote"}

    zeilen = [{"indicator": "anlagenintensitaet", "year": 2024, "report_year": 2024,
               "wert": 40.92, "stellen": 2}]
    bilanz = [{"year": 2024, "role": r, "wert": w} for r, w in (
        ("immaterielles_vermoegen", 91_394_171.68), ("sachvermoegen", 605_573_107.06),
        ("finanzvermoegen", 645_348_451.45), ("liquide_mittel", 118_001_891.26),
        ("aktive_rap", 19_671_338.55))]
    assert kz.gegen_bilanz(zeilen, bilanz) == (1, [])

    zeilen[0]["wert"] = 44.0
    geprueft, risse = kz.gegen_bilanz(zeilen, bilanz)
    assert geprueft == 0 and len(risse) == 1


def test_neueste_nimmt_den_juengsten_bericht():
    zeilen = [
        {"indicator": "steuerquote", "year": 2021, "report_year": 2021, "wert": 45.90},
        {"indicator": "steuerquote", "year": 2021, "report_year": 2023, "wert": 45.92},
        {"indicator": "steuerquote", "year": 2021, "report_year": 2022, "wert": 49.05},
    ]
    series = kz.neueste(zeilen)
    assert len(series) == 1
    assert series[0]["wert"] == 45.92 and series[0]["report_year"] == 2023
