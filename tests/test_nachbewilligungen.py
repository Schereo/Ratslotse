"""Nachbewilligungen nach § 117 NKomVG — RIS-Serie und Rechenschaftsbericht.

Alle Fixtures sind **echte Auszüge** aus dem Bestand vom 18.08.2026: die
Vorlagentitel wörtlich aus ``council_vorlagen``, die Beschlussvorschläge und
die Kapitel-3-Tabellen wörtlich aus dem Textextrakt der
Rechenschaftsberichte 2022/2023/2024 (Dokumente 265441, 280862, 295295).
Nichts hier ist nachgebaut — jede Eigenheit, die geprüft wird, steht so im
Original:

- **Elf Ausreißer im Titel.** „1 Million EUR" ausgeschrieben, „341.000 EU"
  als Tippfehler, „450.000,00 €" mit Cent und Eurozeichen, „insgesamt
  500.000 Euro" — und die sieben ganz ohne Betrag im Titel.
- **Die Deckungsvorschlags-Falle.** Der Beschlussvorschlag nennt nach der
  Bewilligung die Deckung, mit denselben Worten und manchmal mit einer
  größeren Zahl.
- **Verpflichtungsermächtigungen** sind keine Ausgaben dieses Jahres.
- **Der Januar-Beschluss zählt zum Vorjahr** — der Bericht für 2024 führt die
  Vorlage 25/0002.
- **Die Sammelbericht-Schwelle** („bis zu 50.000 Euro") ist eine Grenze, kein
  Betrag.
- **Zwei echte Dokument-Widersprüche**, die gemeldet und nicht geglättet
  werden: die 288.000 € des Berichts 2022 und die 1.051.184,65 € des
  Berichts 2023.
"""
from __future__ import annotations

import pytest

from council import herkunft
from council import nachbewilligungen as nb

# --- Fixtures: echte Vorlagentitel -----------------------------------------

#: Die Regelfälle — Betrag steht kanonisch im Titel.
TITEL_REGEL = [
    ("18/0258", "Überplanmäßige Bewilligung in Höhe von 250.000 EUR für den "
                "Teilhaushalt 04 -Beschluss-", 250_000.0),
    ("23/0617", "Überplanmäßige Bewilligung für Mehraufwendungen in Höhe von "
                "11.716.000 Euro für den Teilhaushalt 10, Budget 50", 11_716_000.0),
    ("25/0241", "Außerplanmäßige Bewilligung einer Mehrauszahlung in Höhe von "
                "450.000 Euro für den Straßenbau", 450_000.0),
]

#: Die Ausreißer. Jeder einzelne stand einmal für eine Lücke der ersten Stufe.
TITEL_AUSREISSER = [
    # Ausgeschriebene Skala.
    ("18/0807", "Überplanmäßige Bewilligung in Höhe von 1 Million EUR für "
                "Abrissmaßnahmen zum Vorhaben \"Fliegerhorst\" im Bereich "
                "Energetisches Nachbarschaftsquartier (ENaQ) - Beschluss -",
     1_000_000.0),
    # Tippfehler der Stadt: „EU" statt „EUR". Wörtlich so im Bestand.
    ("19/0839", "Überplanmäßige Bewilligung von Mehraufwendungen in Höhe von "
                "341.000 EU für Personalaufwendungen im Teilhaushalt 02, "
                "Budget 10 (Amt für Personal- und Verwaltungsmanagement) - "
                "Beschluss", 341_000.0),
    # Cent und Eurozeichen, dazu die umgedrehte Wortstellung: erst das
    # Vorhaben, dann die Bewilligung.
    ("22/0668", "Stadion Marschweg/Ausbau technische Infrastruktur - "
                "Außerplanmäßige Verpflichtungsermächtigung in Höhe von "
                "3.853.000,00 € - Beschluss", 3_853_000.0),
    # Nachkommastellen mitten im Titel.
    ("20/0440", "Unterrichtung des Rates über eine überplanmäßige Bewilligung "
                "in Höhe von 187.804,11 EUR für die Wehdestraße - Bericht",
     187_804.11),
    # „insgesamt" zwischen Wendung und Zahl.
    ("25/0559", "Außerplanmäßige Bewilligung zweier Verpflichtungsermächtigungen "
                "in Höhe von insgesamt 500.000 Euro für einen Vertrag mit den "
                "Nds. Landesforsten - Kompensation -Beschluss", 500_000.0),
]

#: Die sieben Titel ohne Betrag — sie brauchen die zweite Stufe.
TITEL_OHNE_BETRAG = [
    "Stadionneubau Maastrichter Straße; außerplanmäßige Bewilligung von "
    "Mehraufwendungen für die Bauleitplanung - Beschluss",
    "Überplanmäßige Eigenkapitalstärkung für das Klinikum Oldenburg AöR - Beschluss",
    "Überplanmäßige Bewilligung für den Teilhaushalt 04, Budget 22",
]

#: Die Sammelberichte. Der Betrag im Titel ist die Wertgrenze.
TITEL_SAMMEL = [
    "Unterrichtung des Rates über die über- und außerplanmäßigen Auszahlungen "
    "und Aufwendungen unter 50.000 EUR in der Zeit vom 01.01.2017 bis "
    "31.12.2017 - Bericht -",
    "Über- und außerplanmäßige Auszahlungen, Aufwendungen und "
    "Verpflichtungsermächtigungen bis zu 50.000 Euro in der Zeit vom "
    "01.01.2024 bis 31.12.2024 - Bericht",
]

# --- Fixtures: echte Beschlussvorschläge ------------------------------------

#: 25/0606 — die Deckungsvorschlags-Falle in Reinform: Bewilligung und Deckung
#: nennen denselben Wortlaut. Hier sind beide gleich groß; die Falle schnappt
#: erst zu, wenn sie es nicht sind (s. VORSCHLAG_DECKUNG_GROESSER).
VORSCHLAG_STRASSENBAU = """Beschlussvorschlag:

Gemäß § 117 NKomVG wird für die Maßnahme Kreuzung Schützenhofstr./Bremer Str. für
die Begleichung der Schlussrechnung außerplanmäßig eine Mehrauszahlung in Höhe von
105.000 Euro zum Projekt I10.700906.500, „Kreuzung Schützenhofstr./Bremer Str."
bewilligt.

Zur Deckung stehen Minderauszahlungen in Höhe von 105.000 Euro bei der Maßnahme
I10.700603.500.003, „Hindenburgstr.-Prinzessinweg, Straßenbau" zur Verfügung.
"""

#: 23/0811 — schreibt „Mehrauszahlung **von** 7,3 Millionen Euro", nicht
#: „in Höhe von". Ohne diesen Zweig bliebe die Vorlage ohne Betrag.
VORSCHLAG_KLINIKUM = """Beschlussvorschlag:

Für die Eigenkapitalerhöhung des Klinikums im Dezember 2023 wird gemäß
§ 117 NKomVG überplanmäßig eine Mehrauszahlung von 7,3 Millionen Euro zum IPSP Ele-
ment I10.093400.525 „Kapitalstärkung Klinikum, 2023" bewilligt.

Zur Deckung stehen Minderauszahlungen bei dem Projekt I10.093123.520 „Ausleihung an
Beteiligungen, 2023" in entsprechender Höhe zur Verfügung.
"""

#: 24/0836 — der einfache Fall der zweiten Stufe, mit „zusätzliche
#: Haushaltsmittel in Höhe von".
VORSCHLAG_RECHTSAMT = """Beschlussvorschlag:
Für das Budget des Rechtsamts (Budget 22) im Teilhaushalt 04 werden gemäß
§ 117 NKomVG im Ergebnishaushalt zum Produkt P10.111022 „Rechtsberatung, Prozess-
führung und Zentrale Vergabestelle" zusätzliche Haushaltsmittel in Höhe von 65.000 Euro
bewilligt.

Der Mehrbedarf wird durch Mehrerträge bei der Gewerbesteuer (Budget 20.3) im Teilhaus-
halt 04 gedeckt.
"""

#: Der Fall, den die Deckungsregel wirklich abfängt: gebaut aus dem Wortlaut
#: von 23/0893, aber mit einer **größeren** Deckungssumme — genau die
#: Konstellation, in der „größter Betrag gewinnt" (so macht es
#: ``council/money.py``) die falsche Zahl liefert.
VORSCHLAG_DECKUNG_GROESSER = """Beschlussvorschlag:

Für das Budget 20.1 (Beteiligungen) des Amtes für Controlling und Finanzen im Teilhaushalt
04 werden im Ergebnishaushalt zusätzliche Mehraufwendungen in Höhe von 800.000 Euro
zur Leistung P10.111003.005 „Beteiligungen" bewilligt.

Als Deckungsmittel stehen im Budget 20.1 im Teilhaushalt 04 Mehrerträge in Höhe von
2.500.000 Euro bei der Leistung P10.111003.005 „Beteiligungen" zur Verfügung.
"""

# --- Fixtures: Rechenschaftsbericht, Kapitel 3 ------------------------------

#: Bericht 2022, Kapitel 3 — wörtlich, inklusive der Zeilenumbrüche des
#: Textextrakts. Enthält den Widerspruch: Der Fließtext nennt 26.969.523,30 €,
#: die Tabelle darunter ergibt 26.681.523,30 €.
RB_2022 = """RB 46
3 Über- und außerplanmäßige Aufwendungen und Auszahlungen
Für d
as Haushaltsjahr 2022 hat der Rat gemäß § 117 NKomVG über- und außer-
planmäßige Aufwendungen und Auszahlungen beschlossen beziehungsweise wurde
er über Eilentscheidungen und die vom Oberbürgermeister oder Vertretung als uner-
heblich gemäß § 6 der Haushaltssatzung entschiedenen Fälle unterrichtet. Es wur-
den über- und außerplanmäßige Aufwendungen und Auszahlungen von insgesamt
26.969.523,30 Euro genehmigt. Davon entfielen 10.032.086,30 Euro auf investive
und 16.649.437,00 Euro auf konsumtive Zwecke. Darüber hinaus wurde im Jahr
2022 eine überplanmäßige Verpflichtungsermächtigung in Höhe von 150.000 Euro
bewilligt.
Über-/ außerplanmäßige
Aufwendungen bzw. Aus-
zahlungen
Anzahl Konsumtive Auf-
wendungen
Investive Auszah-
lungen
Beschluss des Rates 5 15.335.742,00
6 8.490.000,00
Vom Oberbürgermeister
entschieden
3 110.000,00
17 310.901,65
Gemäß Haushaltsvermerk
durch den Fachdienst 200
6 1.203.695,00
6 1.051.184,65
Eilentscheidungen 0
1 180.000,00
Summe 16.649.437,00 10.032.086,30
RB 47
3.1 Über- und außerplanmäßige Aufwendungen
29.03.22 55 / 22KERN Amt f.Zuwanderung u. Integration 20.3/ 09.DECK Rat
22/0259 P10.313000 Hilfen für Asylbewerber P10.111003.004.002
15.09.2022 01K 04K 1
23/0010 01 / 01KERN Büro des Oberbürgermeisters 20.3 / 09.DECK
19.07.22 08I Am t für Verkehr und Straßenbau 180.000,00 08I 180.000,00 Gesperrt 1 und BM
22/0544 41/19I925 Paradewall, Straßenbau 41/19I903
4 Ermächtigungsübertragungen 2022/2023 – Erläuterungen
"""

#: Bericht 2023 — hier stimmt der Fließtext mit der Summenzeile überein, aber
#: die investive Spalte nicht: „Fachdienst 200" trägt Anzahl 0 und trotzdem
#: 1.051.184,65 €, auf den Cent der Vorjahreswert an derselben Stelle.
RB_2023 = """RB 42
3 Über- und außerplanmäßige Aufwendungen und Auszahlungen

Für das Haushaltsjahr 2023 hat der Rat gemäß § 117 NKomVG über- und außer-
planmäßige Aufwendungen und Auszahlungen beschlossen beziehungsweise wurde
er über Eilentscheidungen und die vom Oberbürgermeister oder Vertretung als uner-
heblich gemäß § 6 der Haushaltssatzung entschiedenen Fälle unterrichtet. Es wur-
den über- und außerplanmäßige Aufwendungen und Auszahlungen von insgesamt
40.236.162,59 Euro genehmigt. Davon entfielen 8.835.307,05 Euro auf investive und
31.400.855,54 Euro auf konsumtive Zwecke. Darüber hinaus wurden im Jahr 2023
vom Rat sechs über- bzw. außerplanmäßige Verpflichtungsermächtigungen in Höhe
von insgesamt 4.870.000,00 Euro bewilligt.

Über-/ außerplanmäßige
Aufwendungen bzw. Aus-
zahlungen
Anzahl Konsumtive Auf-
wendungen
Investive Auszah-
lungen
Beschluss des Rates 15 25.401.400,00
11  8.470.300,00
Vom Oberbürgermeister
entschieden
3 42.467,80

20  365.007,05
Gemäß Haushaltsvermerk
durch den Fachdienst 200
21 5.956.987,74

0  1.051.184,65
Eilentscheidungen 0
0
Summe  31.400.855,54  8.835.307,05

RB 44
3.1 Über- und außerplanmäßige Aufwendungen
21.03.23 20.0 / 09KERN Amt f. Controlling u. Finanzen 20.3/ 09.DECK Rat
23/0147 1090100003 Außengelände WEH P10.111003.004.002
4 Ermächtigungsübertragungen 2023/2024 – Erläuterungen
"""

#: Bericht 2024 — der saubere Jahrgang: beide Spalten und der Fließtext gehen
#: auf den Cent auf. Er ist die Gegenprobe dafür, dass die Probe nicht
#: grundsätzlich meckert.
RB_2024 = """RB 44
3 Über- und außerplanmäßige Aufwendungen und Auszahlungen

Für das Haushaltsjahr 2024 hat der Rat gemäß § 117 NKomVG über- und außer-
planmäßige Aufwendungen und Auszahlungen beschlossen beziehungsweise wurde
er über Eilentscheidungen und die vom Oberbürgermeister oder Vertretung als uner-
heblich gemäß § 6 der Haushaltssatzung entschiedenen Fälle unterrichtet. Es wur-
den über- und außerplanmäßige Aufwendungen und Auszahlungen von insgesamt
57.492.845,28 Euro genehmigt. Davon entfielen 11.653.645,24 Euro auf investive
und 45.839.200,04 Euro auf konsumtive Zwecke. Darüber hinaus wurden im Jahr
2024 vom Rat drei über- bzw. außerplanmäßige Verpflichtungsermächtigungen in
Höhe von insgesamt 1.480.000,00 Euro bewilligt. Zudem wurde eine außerplanmä-
ßige Verpflichtungsermächtigung in Höhe von 35.000,00 Euro durch den Oberbür-
germeister bewilligt. Der Rat wurde hierüber nachrichtlich unterrichtet.

Über-/ außerplanmäßige
Aufwendungen bzw. Aus-
zahlungen
Anzahl Konsumtive Auf-
wendungen
Investive Auszah-
lungen
Beschluss des Rates 15 31.203.646,29
6  10.968.000,00
Vom Oberbürgermeister
entschieden
4 120.000,00

18  505.645,24
Gemäß Haushaltsvermerk
durch den Fachdienst 200
21 14.515.553,75

1  180.000,00
Eilentscheidungen 0
0
Summe  45.839.200,04  11.653.645,24

RB 46
3.1 Über- und außerplanmäßige Aufwendungen
02.04.24 51.0 / 17KERN Jugendamt, Kernbudget 03 / 03KERN 1
25/0002 217551520 Gemeinwesenarbeit Dietrichsfeld P10.111000.002
18.06.24 10 / 07.0KE Amt f. Personal- und Verwaltungsmanagement 20.3 / 09.DECK Rat
24/0359 1071000001 Personal und Organisation P10.111003.004.002 vom
4 Ermächtigungsübertragungen 2024/2025 – Erläuterungen
"""


# --- Stufe 1: der Titel -----------------------------------------------------

@pytest.mark.parametrize("nr,titel,erwartet", TITEL_REGEL + TITEL_AUSREISSER)
def test_betrag_aus_titel(nr, titel, erwartet):
    """Jeder Regelfall und jeder Ausreißer wird aus dem Titel gelesen."""
    wert, quelle = nb.amount(titel)
    assert wert == pytest.approx(erwartet), nr
    assert quelle == "titel", nr


@pytest.mark.parametrize("titel", TITEL_OHNE_BETRAG)
def test_titel_ohne_betrag_liefert_nichts(titel):
    """Ohne Betrag im Titel und ohne Vorschlag bleibt es leer — nicht 0."""
    assert nb.amount(titel) == (None, None)


def test_rueckgabe_ist_wert_dann_quelle():
    """Die Reihenfolge des Tupels ist (Betrag, Quelle) — nicht umgekehrt."""
    wert, quelle = nb.amount(TITEL_REGEL[0][1])
    assert isinstance(wert, float)
    assert quelle == "titel"


# --- Stufe 2: der Beschlussvorschlag ---------------------------------------

def test_zweite_stufe_schliesst_die_luecke():
    """Ein Titel ohne Betrag, ein Vorschlag mit — die Stufe greift."""
    wert, quelle = nb.amount(
        "Überplanmäßige Bewilligung für den Teilhaushalt 04, Budget 22",
        VORSCHLAG_RECHTSAMT)
    assert wert == pytest.approx(65_000.0)
    assert quelle == "beschlussvorschlag"


def test_zweite_stufe_liest_mehrauszahlung_von():
    """„eine Mehrauszahlung **von** 7,3 Millionen Euro" — ohne „in Höhe"."""
    wert, quelle = nb.amount(
        "Überplanmäßige Eigenkapitalstärkung für das Klinikum Oldenburg AöR",
        VORSCHLAG_KLINIKUM)
    assert wert == pytest.approx(7_300_000.0)
    assert quelle == "beschlussvorschlag"


def test_deckungsbetrag_gewinnt_nicht():
    """Die Deckungsvorschlags-Falle: der **erste** Betrag zählt, nicht der
    größte. Nähme man den größten, stünden hier 2.500.000 statt 800.000."""
    wert, _ = nb.amount(
        "Überplanmäßige Bewilligung für Mehraufwendungen für den Teilhaushalt 04",
        VORSCHLAG_DECKUNG_GROESSER)
    assert wert == pytest.approx(800_000.0)


def test_zweite_stufe_aus_volltext_wenn_spalte_leer():
    """``beschlussvorschlag`` ist im Bestand fast überall leer (7 von 5019).
    Steht sie nicht, wird der Vorschlag aus ``raw_text`` geerntet."""
    volltext = "Sachverhalt und Vorgeschichte\n\n" + VORSCHLAG_STRASSENBAU
    wert, quelle = nb.amount(
        "Antrag auf Bewilligung einer außerplanmäßigen Auszahlung für die "
        "Straßenbaumaßnahme Kreuzung Schützenhofstraße/Bremer Straße",
        None, volltext)
    assert wert == pytest.approx(105_000.0)
    assert quelle == "beschlussvorschlag"


# --- Die drei Fallen -------------------------------------------------------

@pytest.mark.parametrize("titel", TITEL_SAMMEL)
def test_sammelbericht_schwelle_ist_kein_betrag(titel):
    """„bis zu 50.000 Euro" ist die Wertgrenze, unter der der Rat gar nicht
    entscheidet — nicht die Summe dessen, was darunter anfiel."""
    assert nb.art(titel) == nb.ART_SCHWELLE
    assert nb.amount(titel) == (None, None)


def test_sammelbericht_schlaegt_verpflichtungsermaechtigung():
    """Der Sammelbericht 21/0023 nennt beides im Titel. Er ist trotzdem eine
    Schwelle — sonst stünde eine Wertgrenze als Verpflichtungsermächtigung im
    Bestand."""
    titel = ("Über- und außerplanmäßige Auszahlungen, Aufwendungen und "
             "Verpflichtungsermächtigungen bis zu 50.000 Euro in der Zeit vom "
             "01.01.2020 bis 31.12.2020 - Bericht")
    assert nb.art(titel) == nb.ART_SCHWELLE


def test_verpflichtungsermaechtigung_zaehlt_nicht_mit():
    """Eine VE bindet künftige Jahre; sie ist keine Ausgabe dieses Jahres.
    Der Rechenschaftsbericht zählt sie getrennt, wir auch."""
    ve = nb.Bewilligung(
        template_number="23/0359", titel="…", art=nb.ART_VERPFLICHTUNG,
        kategorie="ausserplanmaessig", year=2023, amount=840_000.0,
        amount_source="titel",
        beschluesse=({"committee": "Rat", "outcome": "angenommen"},))
    echt = nb.Bewilligung(
        template_number="23/0617", titel="…", art=nb.ART_BEWILLIGUNG,
        kategorie="ueberplanmaessig", year=2023, amount=11_716_000.0,
        amount_source="titel",
        beschluesse=({"committee": "Rat", "outcome": "angenommen"},))
    assert not ve.zaehlt_in_summe
    summen = nb.jahressummen([ve, echt])
    assert summen[2023]["summe"] == pytest.approx(11_716_000.0)
    assert summen[2023]["verpflichtungen"] == 1
    assert summen[2023]["commitments_amount"] == pytest.approx(840_000.0)


def test_januar_beschluss_zaehlt_zum_vorjahr():
    """Der Bericht für 2024 führt die Vorlage 25/0002; sie ist die Meldung
    über das Jahr 2024. Maßgeblich ist der Jahrgang der Vorlagen-Nummer,
    nicht das Sitzungsdatum — sonst läge man 20 bis 27 Prozent daneben."""
    assert nb.haushaltsjahr("24/0834") == 2024
    assert nb.haushaltsjahr("25/0002") == 2025
    # Das Kapitel für 2024 nennt eine Vorlage aus 2025 — den Sammelbericht.
    # `nur_rat=False`, weil er kein Ratsbeschluss ist, sondern die Meldung
    # über die Fälle unter der Wertgrenze.
    alle = nb.vorlagen_im_kapitel(RB_2024, nur_rat=False)
    assert "25/0002" in alle, "der Januar-Fall steht im Kapitel fürs Vorjahr"
    assert "24/0359" in nb.vorlagen_im_kapitel(RB_2024)


def test_ohne_beschluss_keine_summe():
    """Fünf Vorlagen tragen gar keine Beschlusszeile. Beantragtes ist kein
    bewilligtes Geld — 22/0925 allein verschöbe 2022 um 1,4 Mio. €."""
    beantragt = nb.Bewilligung(
        template_number="22/0925", titel="…", art=nb.ART_BEWILLIGUNG,
        kategorie="ueberplanmaessig", year=2022, amount=1_400_000.0,
        amount_source="titel", beschluesse=())
    assert not beantragt.beschlossen
    assert not beantragt.zaehlt_in_summe
    assert nb.jahressummen([beantragt]) == {}


def test_nur_kenntnis_ist_kein_ratsbeschluss():
    """„Unterrichtung … (Eilentscheidung) - Bericht" heißt: entschieden hat
    ein anderer. Der Rechenschaftsbericht bestätigt das für 22/0544 mit dem
    Vermerk „1 und BM"."""
    unterrichtung = nb.Bewilligung(
        template_number="22/0544", titel="…", art=nb.ART_BEWILLIGUNG,
        kategorie="ueberplanmaessig", year=2022, amount=180_000.0,
        amount_source="titel",
        beschluesse=({"committee": "Rat", "outcome": "zur_kenntnis"},))
    assert unterrichtung.nur_kenntnis
    assert not unterrichtung.im_rat
    assert not unterrichtung.zaehlt_in_summe


# --- Klassifikation --------------------------------------------------------

def test_kategorie_unterscheidet_ueber_und_ausser():
    assert nb.kategorie("Überplanmäßige Bewilligung …") == "ueberplanmaessig"
    assert nb.kategorie("Außerplanmäßige Bewilligung …") == "ausserplanmaessig"
    assert nb.kategorie("Über- und außerplanmäßige Auszahlungen …") == "beides"


def test_einschlag_erkennt_umgedrehte_wortstellung():
    """22/0668 nennt erst das Vorhaben, dann die Bewilligung."""
    assert nb.ist_nachbewilligung(
        "Stadion Marschweg/Ausbau technische Infrastruktur - Außerplanmäßige "
        "Verpflichtungsermächtigung in Höhe von 3.853.000,00 € - Beschluss")
    assert not nb.ist_nachbewilligung("Bebauungsplan 831 - Beschluss")


# --- Serie aus Vorlagen ----------------------------------------------------

def test_aus_vorlagen_zaehlt_je_vorlage_einmal():
    """287 Beschlusszeilen stehen über 156 Vorlagen — Finanzausschuss und Rat
    entscheiden dieselbe Sache. Je Zeile gezählt wäre der Betrag doppelt."""
    vorlagen = [{"template_number": "23/0617",
                 "title": "Überplanmäßige Bewilligung für Mehraufwendungen in "
                          "Höhe von 11.716.000 Euro für den Teilhaushalt 10"}]
    beschluesse = {"23/0617": [
        {"committee": "Ausschuss für Finanzen und Beteiligungen",
         "outcome": "angenommen", "session_date": "2023-11-20"},
        {"committee": "Rat", "outcome": "angenommen",
         "session_date": "2023-11-27"}]}
    serie = nb.aus_vorlagen(vorlagen, beschluesse)
    assert len(serie) == 1
    assert nb.jahressummen(serie)[2023]["faelle"] == 1
    assert nb.jahressummen(serie)[2023]["summe"] == pytest.approx(11_716_000.0)


def test_aus_vorlagen_ignoriert_fremde_titel():
    fremd = [{"template_number": "23/0100", "title": "Bebauungsplan 831"}]
    assert nb.aus_vorlagen(fremd) == []


# --- Probe 1: Titelbetrag im Volltext --------------------------------------

def test_probe_volltext():
    b = nb.aus_vorlagen([{
        "template_number": "25/0606",
        "title": "Außerplanmäßige Bewilligung einer Mehrauszahlung in Höhe von "
                 "105.000 Euro für die Straßenbaumaßnahme"}])[0]
    assert nb.probe_volltext(b, VORSCHLAG_STRASSENBAU)
    assert not nb.probe_volltext(b, "ein Text ganz ohne diesen Betrag")


def test_probe_volltext_ohne_titelbetrag_ist_nicht_bestanden():
    """„Nicht geprüft" darf nicht wie „bestanden" aussehen."""
    b = nb.Bewilligung(template_number="24/0836", titel="…", art=nb.ART_BEWILLIGUNG,
                       kategorie="ueberplanmaessig", year=2024, amount=65_000.0,
                       amount_source="beschlussvorschlag")
    assert not nb.probe_volltext(b, VORSCHLAG_RECHTSAMT)


# --- Kapitel 3: die vier Kanäle --------------------------------------------

@pytest.mark.parametrize("text,year,council_amount,rat_anzahl,gesamt", [
    (RB_2022, 2022, 23_825_742.00, 11, 26_681_523.30),
    (RB_2023, 2023, 33_871_700.00, 26, 40_236_162.59),
    (RB_2024, 2024, 42_171_646.29, 21, 57_492_845.28),
])
def test_kapitel3_liest_die_vier_kanaele(text, year, council_amount, rat_anzahl, gesamt):
    kap = nb.kapitel3(text, year)
    assert kap is not None
    assert len(kap.kanaele) == 4, "alle vier Wege, auch die leeren"
    rat = kap.kanal("rat")
    assert rat.amount == pytest.approx(council_amount)
    assert rat.count == rat_anzahl
    assert kap.gesamt == pytest.approx(gesamt)


def test_eilentscheidung_ohne_konsumtiven_betrag():
    """„Eilentscheidungen 0" hat gar keinen Betrag — die investive Zeile
    darunter aber schon. Ein Muster, das den Betrag erzwingt, nimmt die
    Anzahl der nächsten Zeile als Betrag der vorigen."""
    kap = nb.kapitel3(RB_2022, 2022)
    eil = kap.kanal("eilentscheidung")
    assert eil.count_operating == 0
    assert eil.amount_operating == 0.0
    assert eil.count_capital == 1
    assert eil.amount_capital == pytest.approx(180_000.0)


def test_kanal_findet_die_tabelle_nicht_die_prosa():
    """Der einleitende Satz nennt „Eilentscheidungen" auch. Wer dort landet,
    liest keine Zellen mehr — 2022 fehlten so 180.000 €."""
    kap = nb.kapitel3(RB_2022, 2022)
    assert kap.kanal("eilentscheidung") is not None


def test_verpflichtungsermaechtigungen_kommen_aus_dem_fliesstext():
    """Sie stehen hinter „Darüber hinaus" und **nie** in der Gesamtsumme.
    Der Zwischenraum enthält „bzw." — ein Punkt-Verbot bräche daran ab."""
    assert nb.kapitel3(RB_2022, 2022).commitments_amount == pytest.approx(150_000.0)
    assert nb.kapitel3(RB_2023, 2023).commitments_amount == pytest.approx(4_870_000.0)
    assert nb.kapitel3(RB_2024, 2024).commitments_amount == pytest.approx(1_480_000.0)


def test_ratsanteil_sinkt():
    """Der Befund, um den es geht — nüchtern, ohne Wertung."""
    anteile = [nb.kapitel3(t, j).rats_anteil
               for t, j in ((RB_2022, 2022), (RB_2023, 2023), (RB_2024, 2024))]
    assert anteile[0] > anteile[1] > anteile[2]
    assert anteile[2] == pytest.approx(73.4, abs=0.1)


def test_kapitel3_ohne_summenzeile_kommt_nicht_herein():
    """Ein Kapitel ohne Summenzeile ließe sich nicht prüfen."""
    assert nb.kapitel3("3 Über- und außerplanmäßige Aufwendungen und "
                       "Auszahlungen\nirgendwas", 2022) is None
    assert nb.kapitel3("ein Dokument ohne dieses Kapitel", 2022) is None


# --- Probe 3: das Dokument gegen sich selbst -------------------------------

def test_probe_tabelle_2024_geht_auf():
    """Die Gegenprobe: Der saubere Jahrgang besteht beides."""
    p = nb.probe_tabelle(nb.kapitel3(RB_2024, 2024))
    assert p.bestanden
    assert p.abweichung_konsumtiv == pytest.approx(0.0)
    assert p.abweichung_investiv == pytest.approx(0.0)


def test_probe_tabelle_meldet_die_288000_von_2022():
    """Der Fließtext nennt 26.969.523,30 €, seine eigene Tabelle ergibt
    26.681.523,30 €. Angezeigt, nicht repariert."""
    p = nb.probe_tabelle(nb.kapitel3(RB_2022, 2022))
    assert p.spalten_ok, "die Spalten selbst stimmen"
    assert not p.gesamt_ok
    assert p.abweichung_gesamt == pytest.approx(288_000.0)
    # Deutsche Schreibweise — der Satz landet über `probe_result` im
    # Beleg-Chip und damit vor Leser*innen.
    assert "288.000,00 €" in p.als_text()


def test_probe_tabelle_meldet_den_uebernahmerest_von_2023():
    """„Fachdienst 200" trägt investiv Anzahl 0 und trotzdem 1.051.184,65 € —
    auf den Cent der Vorjahreswert. Die Summenzeile rechnet ihn nicht mit."""
    p = nb.probe_tabelle(nb.kapitel3(RB_2023, 2023))
    assert not p.spalten_ok
    assert p.abweichung_konsumtiv == pytest.approx(0.0)
    assert p.abweichung_investiv == pytest.approx(1_051_184.65)
    assert p.gesamt_ok, "der Fließtext passt zur Summenzeile"


def test_probe_tabelle_wird_nicht_geglaettet():
    """Eine gerissene Probe bleibt gerissen und sagt, um wie viel."""
    p = nb.probe_tabelle(nb.kapitel3(RB_2022, 2022))
    assert not p.bestanden
    assert "€" in p.als_text()


# --- Probe 2: unsere Serie gegen den Bericht -------------------------------

def test_probe_ratsabgleich_meldet_die_abweichung():
    """2023 stimmt auf 100 € — der Abgleich rechnet, statt zu behaupten."""
    serie = nb.aus_vorlagen(
        [{"template_number": "23/0617",
          "title": "Überplanmäßige Bewilligung für Mehraufwendungen in Höhe "
                   "von 33.871.800 Euro für den Teilhaushalt 10"}],
        {"23/0617": [{"committee": "Rat", "outcome": "angenommen",
                      "session_date": "2023-11-27"}]})
    abgleich = nb.probe_ratsabgleich(serie, nb.kapitel3(RB_2023, 2023))
    assert abgleich.bericht_summe == pytest.approx(33_871_700.00)
    assert abgleich.deviation == pytest.approx(100.0)
    assert abgleich.abweichung_prozent == pytest.approx(0.0003, abs=0.0001)
    assert "+100,00 €" in abgleich.als_text()


def test_de_betrag_schreibt_deutsch():
    """Diese Sätze stehen im Beleg-Chip, nicht im Log."""
    assert nb.de_amount(288_000.0) == "288.000,00"
    assert nb.de_amount(288_000.0, vorzeichen=True) == "+288.000,00"
    assert nb.de_amount(-1_051_184.65, vorzeichen=True) == "−1.051.184,65"


#: Die am vollen Bestand gemessenen Werte der Rats-Serie. Sie stehen hier,
#: **weil ein Docstring sie schon einmal falsch behauptet hat**: Die Prosa
#: nannte für 2022 +1,31 % / 24.136.742,00 € mit zwei Ursachen, gemessen sind
#: es +0,55 % / 23.956.742,00 € mit einer. Der Fehler war grün durch alle
#: Tests gelaufen, weil keiner die Zahl festnagelte. Jetzt tut es einer.
#:
#: Wer diese Werte ändert, ändert eine Aussage über eine amtliche Quelle —
#: erst nachmessen, dann anfassen.
GEMESSEN = {
    2022: {"unsere": 23_956_742.00, "faelle": 12,
           "bericht": 23_825_742.00, "bericht_faelle": 11,
           "deviation": 131_000.00},
    2023: {"unsere": 33_871_800.00, "faelle": 26,
           "bericht": 33_871_700.00, "bericht_faelle": 26,
           "deviation": 100.00},
    2024: {"unsere": 43_096_100.00, "faelle": 21,
           "bericht": 42_171_646.29, "bericht_faelle": 21,
           "deviation": 924_453.71},
}


@pytest.mark.parametrize("year", sorted(GEMESSEN))
def test_gemessene_abweichungen_sind_festgenagelt(year):
    """Die Berichtsseite der Messung — sie hängt nur am Fixture und prüft,
    dass der Parser die Zahlen des Dokuments unverändert liest."""
    soll = GEMESSEN[year]
    kap = nb.kapitel3({2022: RB_2022, 2023: RB_2023, 2024: RB_2024}[year], year)
    rat = kap.kanal("rat")
    assert rat.amount == pytest.approx(soll["bericht"])
    assert rat.count == soll["bericht_faelle"]
    # Und die Rechnung, die daraus die Abweichung macht.
    assert soll["unsere"] - soll["bericht"] == pytest.approx(soll["deviation"])


def test_2024er_abweichung_ist_auf_den_cent_erklaert():
    """Die 2,19 % sind keine Unschärfe, sondern eine Definitionsdifferenz:
    Wir zählen, was die Vorlage beantragt, der Bericht, was gebucht wurde.
    Drei Vorlagen wurden niedriger gebucht — zusammen exakt die Differenz."""
    niedriger_gebucht = [
        ("24/0411", 190_000.00, 51_500.00),
        ("24/0678", 430_000.00, 230_000.00),
        ("24/0648", 11_232_400.00, 10_646_446.29),
    ]
    difference = sum(beantragt - gebucht for _, beantragt, gebucht
                    in niedriger_gebucht)
    assert difference == pytest.approx(GEMESSEN[2024]["deviation"])


def test_probe_ratsabgleich_nennt_die_fehlenden_nummern():
    """Der Bericht nennt dieselben Fälle mit Nummern — wer fehlt, wird
    benannt statt weggelassen."""
    serie = nb.aus_vorlagen(
        [{"template_number": "24/0359",
          "title": "Überplanmäßige Bewilligung in Höhe von 100.000 Euro"}],
        {"24/0359": [{"committee": "Rat", "outcome": "angenommen",
                      "session_date": "2024-06-17"}]})
    abgleich = nb.probe_ratsabgleich(
        serie, nb.kapitel3(RB_2024, 2024), nb.vorlagen_im_kapitel(RB_2024))
    assert abgleich.nur_bei_uns == ()
    assert "24/0359" not in abgleich.nur_im_bericht


def test_vorlagen_im_kapitel_nimmt_nur_die_ratsbeschluesse():
    """Nicht jede Nummer im Kapitel ist ein Fall. 22/0544 trägt den Vermerk
    „1 und BM" (Oberbürgermeister), 23/0010 ist der Sammelbericht — beide
    stehen im Abschnitt, sind aber keine Ratsbeschlüsse. Der erste Ansatz
    nahm sie mit und behauptete damit Fälle, die der Bericht nicht führt."""
    nur_rat = nb.vorlagen_im_kapitel(RB_2022)
    assert "22/0259" in nur_rat, "der echte Ratsbeschluss"
    assert "22/0544" not in nur_rat, "Vermerk 1 und BM = Oberbürgermeister"
    assert "23/0010" not in nur_rat, "Sammelbericht, kein Fall"
    # Die weite Frage ist eine andere und bleibt beantwortbar.
    alle = nb.vorlagen_im_kapitel(RB_2022, nur_rat=False)
    assert {"22/0259", "22/0544", "23/0010"} <= alle


def test_vorlagen_im_kapitel_2024():
    """2024: der Rats-Fall ist drin, die Unterrichtung des OB (Vermerk „1",
    Sammelbericht-Nummer 25/0002) nicht."""
    nur_rat = nb.vorlagen_im_kapitel(RB_2024)
    assert "24/0359" in nur_rat
    assert "25/0002" not in nur_rat


# --- Der Rats-Anteil folgt dem Bericht, nicht dem Gremiennamen -------------

def _bewilligung(nr, amount, committee, outcome="angenommen"):
    return nb.Bewilligung(
        template_number=nr, titel="…", art=nb.ART_BEWILLIGUNG,
        kategorie="ueberplanmaessig", year=2024, amount=amount,
        amount_source="titel",
        beschluesse=({"committee": committee, "outcome": outcome},))


def test_finanzausschuss_zaehlt_als_ratsbeschluss():
    """**Der gefährlichste Fehler dieser Schicht.** Der Finanzausschuss
    entscheidet abschließend, und der Rechenschaftsbericht bucht das als
    „Beschluss des Rates". 2024 hatten 8 von 21 Fällen keine Plenarsitzung
    mehr — wer wörtlich zählt, veröffentlicht 30.896.100 statt 43.096.100 €
    und damit 28 % zu wenig, ausgerechnet für die Kennzahl „der Rats-Anteil
    sinkt"."""
    plenum = _bewilligung("24/0359", 100_000.0, "Rat")
    ausschuss = _bewilligung("24/0834", 375_000.0,
                             "Ausschuss für Finanzen und Beteiligungen")
    assert plenum.im_rat and plenum.ratsentscheidung
    assert not ausschuss.im_rat, "das Plenum hat nicht abgestimmt"
    assert ausschuss.ratsentscheidung, "der Bericht bucht es trotzdem als Rat"
    summen = nb.jahressummen([plenum, ausschuss], nur_rat=True)
    assert summen[2024]["summe"] == pytest.approx(475_000.0)
    assert summen[2024]["faelle"] == 2


def test_fremder_ausschuss_zaehlt_nicht_als_ratsbeschluss():
    """Ein Betriebsausschuss beschließt über den Haushalt eines
    Eigenbetriebs — ein anderer Haushalt, nicht diese Summe."""
    fremd = _bewilligung(
        "24/0900", 50_000.0,
        "Betriebsausschuss Eigenbetrieb Gebäudewirtschaft und Hochbau")
    assert not fremd.ratsentscheidung
    assert nb.jahressummen([fremd], nur_rat=True) == {}


# --- Herkunft ---------------------------------------------------------------

def test_proben_sind_in_herkunft_eingetragen():
    """Eine Probe ohne Erklärsatz käme über ``Herkunft`` nicht in die DB."""
    for name in (nb.PROBE_VOLLTEXT, nb.PROBE_TABELLE, nb.PROBE_RAT):
        assert name in herkunft.PROBEN
        assert herkunft.PROBEN[name].strip().endswith(".")


def test_herkunft_laesst_sich_bauen():
    h = herkunft.Herkunft(
        art="ris", probe=[nb.PROBE_TABELLE, nb.PROBE_RAT],
        dokument_id=295295, fundstelle="Kapitel 3",
        probe_result="Spalten und Gesamtsumme gehen auf den Cent auf.")
    assert h.geprueft
    assert h.proben == [nb.PROBE_TABELLE, nb.PROBE_RAT]
