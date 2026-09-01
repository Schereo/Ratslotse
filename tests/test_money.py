"""Tests for the heuristic € extraction (council.money).

Der zweite Teil („Stückpreise", „Schwellen", „Der Recall bleibt") hält die
Musterschärfung vom 18.08.2026 fest. Jeder Fall dort ist ein **gemessener**
Fehlgriff aus dem Bestand, mit der Beschluss-ID im Docstring — und jeder Test
im Recall-Abschnitt ist ein echter Betrag, der genau diese Schärfung überleben
muss. Beide Richtungen zusammen sind die Zusicherung: Fehlgriffe raus, echte
Beträge bleiben.
"""
from council.money import (extract_amounts, ist_preisbeschluss, ist_sammelbericht,
                           largest_amount)


def test_plain_amount():
    assert largest_amount("Kosten von 250.000 € werden bewilligt.") == 250_000


def test_decimal_with_thousands():
    # The grouped form must keep its decimals (regression: matched only "12.500").
    assert largest_amount("Betrag: 12.500,50 EUR") == 12_500.50


def test_plain_decimal():
    assert largest_amount("Zuschuss von 1500,00 Euro") == 1_500.0


def test_scaled_millions():
    assert largest_amount("Investition von 1,2 Mio. €") == 1_200_000
    assert largest_amount("rund 3 Millionen Euro") == 3_000_000


def test_scaled_billions():
    assert largest_amount("Haushaltsvolumen 1,5 Mrd. €") == 1_500_000_000


def test_largest_wins():
    assert largest_amount("200.000 € Förderung bei 500.000 € Gesamtkosten") == 500_000


def test_no_currency_token_ignored():
    # Bare numbers (years, counts) must not be picked up as money.
    assert extract_amounts("Im Jahr 2024 gab es 15 Stimmen dafür.") == []
    assert largest_amount("Beschluss ohne Betrag") is None


def test_sanity_ceiling():
    # Absurd values (parse artefacts) are dropped.
    assert largest_amount("99.999.999.999 €") is None


def test_empty():
    assert extract_amounts("") == []
    assert largest_amount(None) is None


# --- Stückpreise: der Beschluss setzt einen Preis, kein Volumen -------------
#
# Die fünf Fälle sind gemessen (Bestand 18.08.2026). Vor der Schärfung trug
# jeder von ihnen seinen Stückpreis als Beschlussbetrag — und damit ein
# Geld-Signal im Wichtig-Wert.

def test_das_ein_euro_tagesticket_ist_kein_beschlussbetrag():
    """Beschluss 6984: „1 Euro-Tagesticket" — der Preis steht im Namen der Sache."""
    assert largest_amount(
        "Ermittlung der Kosten für die Einführung eines 1 Euro-Tagestickets der "
        "VWG in Oldenburg an allen Samstagen") is None


def test_der_essenspreis_ist_kein_beschlussbetrag():
    """Beschluss 2112: Rahmenkonzept Schulverpflegung, eine Preisliste.

    Die Liste braucht beide Wege: Am Fundort greift „Spontanessen", die
    mittlere Zeile („für einzelne Tage 3,70 €") trägt kein Preiswort mehr und
    fällt erst über den Titel."""
    assert largest_amount("Spontanessen 3,90 €") is None
    assert largest_amount("Vorbestellung als Abonnement 3,50 €") is None
    assert largest_amount(
        "Primarbereich Vorbestellung als Abonnement 3,50 €, Vorbestellung für "
        "einzelne Tage 3,70 €, Spontanessen 3,90 €",
        "Rahmenkonzept „Schulverpflegung in Oldenburg“") is None


def test_die_parkgebuehr_ist_kein_beschlussbetrag():
    """Beschluss 5491: „Änderung der Parkgebühren", Zielniveau 6 € pro Tag."""
    assert largest_amount(
        "Das Zielniveau für die maximale Parkgebühr pro Tag sollte bei 6 € liegen.") is None


def test_das_entgelt_der_fahrradgarage_ist_kein_beschlussbetrag():
    """Beschluss 3824: „Festsetzung der Entgelte", Jahreskarte 70 €."""
    assert largest_amount(
        "Die Entgelte werden festgesetzt: Tageskarte 1,00 €, Wochenkarte 5,00 €, "
        "Monatskarte 10,00 €, Jahreskarte 70,00 €.") is None


def test_das_parkhausentgelt_ist_kein_beschlussbetrag():
    """Beschluss 1839: „Erhöhung der Entgelte", Jahreskarte 324 €."""
    assert largest_amount(
        "Monatskarte 30,00 € (keine Änderung), Jahreskarte 324,00 €") is None


def test_der_titel_entscheidet_ueber_den_ganzen_beschluss():
    """Eine Tariftabelle verliert ihr Tarifwort ab der zweiten Zeile.

    Der Titel trägt es weiter — 175 Beschlüsse im Bestand haben eines, und
    nach allen übrigen Filtern tragen genau drei davon noch einen Betrag."""
    assert ist_preisbeschluss("Änderung der Parkgebühren")
    assert ist_preisbeschluss("Festsetzung der Entgelte Fahrradsammelgarage")
    assert not ist_preisbeschluss("Überplanmäßige Bewilligung für den Teilhaushalt 11")
    tabelle = "Zone 1: Innenstadt ab 01.06.2023 0,50 €, ab 01.01.2024 0,70 €"
    assert largest_amount(tabelle, "Änderung der Parkgebühren") is None
    # Ohne Titel bleibt die zweite Tabellenzeile stehen — deshalb gibt es ihn.
    assert largest_amount(tabelle) == 0.70


def test_ein_kaufpreis_ist_sehr_wohl_ein_beschlussbetrag():
    """Gegenprobe zum Preis-Filter: „Preis" allein darf nicht ausschließen.

    Beschluss 4339 (VHS-Anteile) und 7872 (Grundstück Fliegerhorst) — beide
    verlören sonst ihr Volumen."""
    assert largest_amount("Der Kaufpreis beträgt 390.585 Euro.") == 390_585
    assert largest_amount(
        "zu einem Kaufpreis von 309.952,00 Euro (232,00 Euro pro Quadratmeter)") == 309_952


# --- Schwellen: die Zahl ist die Grenze, nicht der Betrag -------------------

def test_die_berichtsschwelle_ist_kein_betrag():
    """Beschlüsse 423/619/1349 — Sammelberichte über alles unter der Grenze."""
    assert largest_amount(
        "Unterrichtung des Rates über die über- und außerplanmäßigen Auszahlungen "
        "und Aufwendungen unter 50.000 EUR in der Zeit vom 01.01.2017 bis "
        "31.12.2017") is None


def test_der_sammelbericht_traegt_seine_meldeschwelle_nicht_als_betrag():
    """Beschlüsse 2355/3499/8411 …: 17 Zeilen, jede mit 50.000 € als Grenze.

    Die ältere Fassung schrieb „unter 50.000 EUR", die neuere „bis zu
    50.000 Euro" — nur die erste fiel unter die Fundort-Regel."""
    for grenzwort in ("unter", "bis zu"):
        title = (f"Über- und außerplanmäßige Auszahlungen, Aufwendungen und "
                 f"Verpflichtungsermächtigungen {grenzwort} 50.000 Euro in der "
                 f"Zeit vom 01.01.2025 bis 30.06.2025")
        assert ist_sammelbericht(title), grenzwort
        assert largest_amount(f"{title}. Der Bericht wird zur Kenntnis genommen.",
                              title) is None, grenzwort


def test_bis_zu_allein_macht_noch_keine_schwelle():
    """Die Gegenprobe zur Sammelbericht-Regel — und ihr eigentlicher Grund.

    26 Beträge im Bestand stehen hinter einem „bis zu", 14 sind Grenzen und
    **12 sind echte Volumen**. Eine Regel auf das Wort allein kostete diese
    zwölf. Beschlüsse 4809 (Klinikum) und 5993 (BTB)."""
    assert largest_amount(
        "Ausfallbürgschaft der Stadt Oldenburg für ein Darlehen der Klinikum "
        "Oldenburg AöR in Höhe von bis zu 116,5 Millionen Euro.",
        "Klinikum Oldenburg AöR: Ausfallbürgschaft") == 116_500_000
    assert largest_amount(
        "Unterstützung bis zu 1,5 Mio. Euro für den BTB (Schwimm- und Gebäudesanierung).",
        "Bau und Sanierung von Sporthallen und Schwimmbädern") == 1_500_000


def test_wertgrenzen_gelten_fuer_die_ganze_aufzaehlung():
    """Beschlüsse 8107/8453: drei Grenzen in einer Liste.

    Ab dem dritten Aufzählungspunkt ist „überschreiten" aus jedem Fenster
    gewandert — „Wertgrenze" wird deshalb am ganzen Text geprüft."""
    assert largest_amount(
        "Wertgrenzen Betriebsausschuss EGH. Maßnahmen, die folgende Wertgrenzen "
        "überschreiten: • 400.000 Euro bei Auftragsvergaben • 75.000 Euro bei "
        "Planungsleistungen • 125.000 Euro bei sonstigen Leistungen") is None


# --- Der Recall bleibt: echte Beträge überleben die Schärfung ---------------
#
# Sechs Formen, an denen die Schärfung in einer früheren Fassung echte Beträge
# verloren hat. Sie stehen hier, damit das nicht zurückkommt.

def test_ein_jaehrlicher_zuschuss_behaelt_seinen_betrag():
    """Ein Haushalt ist von Natur aus jährlich — „jährlich" ist keine Stückzahl.

    Beschlüsse 2888 (13.739,52 EUR), 5085 (80.000 €), 4246 (13.888,88 €)."""
    assert largest_amount(
        "Bewilligung eines institutionellen Zuschusses in Höhe von jährlich "
        "13.739,52 EUR") == 13_739.52
    assert largest_amount(
        "den Betrieb der Geschäftsstelle des SSB mit jährlich maximal "
        "80.000,00 Euro zu fördern") == 80_000
    assert largest_amount(
        "OLEC e.V. für die Jahre 2020 bis 2022 mit einem Betrag von 48.000 € "
        "pro Jahr") == 48_000


def test_ein_beilaeufiges_tarifwort_kostet_nicht_den_betrag():
    """Beschluss 2771: 20 Mio. € Rettungsschirm, „Gebühren" kommt beiläufig vor.

    Genau daran ist die Tarif-Regel am ganzen Text gescheitert — sie kostete
    fünf echte Beträge, um drei Tarife zu treffen."""
    assert largest_amount(
        "Rettungsschirm für die Kommunen: ein Programm über 20 Mio. €. Ausfälle "
        "bei Steuern und Gebühren sind auszugleichen.", "Corona-Krise gebietet "
        "einen Rettungsschirm für die Kommunen") == 20_000_000


def test_eine_ueberplanmaessige_bewilligung_behaelt_ihren_betrag():
    """Beschluss 7291: 430.000 €, im Text steht „Nutzungsentgelten"."""
    assert largest_amount(
        "Überplanmäßige Bewilligung in Höhe von 430.000 Euro für den Teilhaushalt "
        "11. Der Mehrbedarf entsteht bei den Nutzungsentgelten.",
        "Überplanmäßige Bewilligung in Höhe von 430.000 Euro") == 430_000


def test_die_zuwendungsannahme_behaelt_ihren_betrag():
    """Die Spendenreihe hängt daran (council/spenden.py) — auch bei 60,00 EUR.

    Kleine Beträge sind nicht automatisch Stückpreise."""
    assert largest_amount(
        "Die Stadt Oldenburg nimmt die angebotenen Zuwendungen in Höhe von "
        "total 60,00 EUR laut anliegender Liste an.") == 60
    assert largest_amount(
        "Die Stadt Oldenburg nimmt die angebotenen Zuwendungen in Höhe von "
        "total 140.664,24 EUR laut anliegender Liste an.") == 140_664.24


def test_ein_stueckpreis_neben_einem_volumen_kostet_das_volumen_nicht():
    """Gefiltert wird am Fundort, nicht am Text — sonst gewinnt der Fehlgriff."""
    assert largest_amount(
        "Für den Neubau werden 2.500.000 € bewilligt; die Kosten liegen bei "
        "275 €/m².") == 2_500_000
