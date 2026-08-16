"""Der Beteiligungsbericht nach § 151 NKomVG.

Alle Fixtures sind verkürzte, aber **wörtliche** Ausschnitte aus echten
pypdf-Extrakten der Berichte auf oldenburg.de — jeder mit genau der Eigenheit,
an der ein naiver Parser scheitert:

- **EGH 2024** führt die Jahresspalten **absteigend** (2024 → 2020), der
  **AWB** zwei Seiten weiter **aufsteigend** (2020 → 2024). Wer die
  Reihenfolge annimmt statt die Kopfzeile zu lesen, dreht eine der beiden
  Zeitreihen um.
- **GSG 2022** trägt ein Jahresergebnis ``5.698.082.44`` — Punkt statt Komma,
  ein Tippfehler im Bericht. Die Zeile **muss** verworfen werden; „vier Werte
  für fünf Jahre" heißt, dass niemand mehr weiß, welche Zahl zu welchem Jahr
  gehört.
- **EGH 2023** schließt seine Gewinn- und Verlustrechnung mit
  ``2.103.265, 69`` — Leerzeichen hinter dem Komma. Dieselbe Sorte Schaden wie
  im Gesamtabschluss (``105.667.339, 23``).
- **AWB 2023** setzt Leerraum um den Tausenderpunkt: ``23.439 .654,83``.
- Die **Großleitstelle** führt noch im Bericht für 2024 die Jahre 2017–2021 —
  „die letzte Spalte ist das Berichtsjahr" ist falsch.
- Die **Bilanz** weist ihre Summe zweimal aus, unter AKTIVA und unter PASSIVA.
  Steht sie nur einmal da oder weichen beide ab, gibt es keine Bilanzprobe.

Die Jahrgänge **vor 2022** sind bewusst nicht abgedeckt: Der Bericht ist dort
anders aufgebaut (keine Kennzahlen-Tabellen, zweispaltige Bilanz) und wird
gar nicht erst gelesen. Der Test dazu prüft, dass er das auch sagt.
"""
from __future__ import annotations

import pytest

from council import beteiligungsbericht as bb
from council import finanzquellen, herkunft
from council.store import CouncilStore

# --- Fixtures: wörtliche Ausschnitte ----------------------------------------

#: EGH 2024, Seite 40 — Jahresspalten absteigend, Einheit in Klammern.
KENN_EGH_2024 = (
    "Kennzahlen im Zeitverlauf: \n \n"
    " 2024 2023 2022 2021 2020 \n"
    "Jahresergebnis (in Euro) -2.726.407,50 2.754.962,22 4.360.849,65 "
    "2.103.265,69 1.195.102,99 \n"
    "Bilanzsumme (in Euro) 580.193.968,91 572.543.885,42 559.822.592,60 "
    "539.607.102,86  528.495.093,84  \n"
    "Eigenkapitalquote (in \nProzent) \n46,99 48,09 48,69 49,71 50,36 \n \n \n"
    "Beteiligungsspezifische Kennzahlen im Zeitverlauf: \n \n"
    "EGH 2024 2023 2022 2021 2020  \n"
    "Anteil an investiven Maßnahmen  \n(in Prozent): \n- Allgemein \n6,0 \n")

#: AWB 2024 — dieselbe Tabelle, Jahresspalten **aufsteigend**, Einheit auf
#: der nächsten Zeile.
KENN_AWB_2024 = (
    "Kennzahlen im Zeitverlauf: \n \n"
    " 2020 2021 2022 2023 2024 \n"
    "Jahresergebnis \n(in Euro) \n"
    "394.110,66 495.386,14 537.531,45 650.289,04 294.324,26  \n"
    "Bilanzsumme \n(in Euro) \n"
    "21.967.669,43 22.115.244,70 23.439.654,83 26.498.799,15   "
    "25.500.408,17    \n"
    "Eigenkapitalquote \n(in Prozent) \n58,6 59,7 58,1 53,4 56,2   \n \n"
    "Beteiligungsspezifische Kennzahlen im Zeitverlauf: \n")

#: AWB 2023 — Leerraum um den Tausenderpunkt (``23.439 .654,83``).
KENN_AWB_2023 = (
    "Kennzahlen im Zeitverlauf: \n \n"
    " 2019 2020 2021 2022 2023 \n"
    "Jahresergebnis \n(in Euro) \n"
    "408.616,20  394.110,66  495.386,14  537.531,45  650 .289,04  \n"
    "Bilanzsumme \n(in Euro) \n"
    "21.894.589,68  21.967.669,43  22.115.244,70  23.439 .654,83  "
    "26.498.799,15  \n"
    "Eigenkapitalquote \n(in Prozent) \n57,8  58,6  59,7  58,1  53,4  \n \n"
    "Beteiligungsspezifische Kennzahlen im Zeitverlauf: \n")

#: GSG 2022 — der Tippfehler ``5.698.082.44`` (Punkt statt Komma).
KENN_GSG_2022 = (
    "Kennzahlen im Zeitverlauf: \n \n"
    " 2018 2019 2020 2021 2022 \n"
    "Jahresergebnis 5.317.606,55 € 5.698.082.44 € 5.414.549,65 € "
    "5.757.654,95 € 6.161.514,39 € \n"
    "Bilanzsumme 279.624.042,36 € 298.128.169,01 € 300.906.698,53 € "
    "305.231.613,36 € 320.415.740,39 € \n"
    "Eigenkapital- \nquote \n37,3 % 36,4 % 37,5 % 38,4 % 38,1 % \n \n"
    "Beteiligungsspezifische Kennzahlen im Zeitverlauf: \n")

#: Die Großleitstelle — Berichtsjahr 2024, Kennzahlen aber 2017–2021.
KENN_GOL = (
    "Kennzahlen im Zeitverlauf: \n \n"
    " 2017 2018 2019 2020 2021 \n"
    "Jahresergebnis \n(in Euro) \n"
    "398.872,26  198.354,80  513.079,40  1.169.022,30  806.298,05  \n"
    "Bilanzsumme \n(in Euro) \n"
    "6.219.632,18  6.193.811,67  6.095.822,32  8.946.979,30  8.765.540,37  \n"
    "Eigenkapitalquote \n(in Prozent) \n41,93  45,31 54,46 50,17  60,41 \n \n"
    "Beteiligungsspezifische Kennzahlen im Zeitverlauf: \n")

#: EGH 2024 — die Bilanz, gekürzt auf Kopf und Summenzeilen.
BILANZ_EGH_2024 = (
    "6) Bilanzdaten, Gewinn- und Verlustrechnung und Kennzahlen \n \nBilanz: \n \n"
    "AKTIVA \n  31.12.2024 31.12.2023 31.12.2022 \n"
    "A. ANLAGEVERMÖGEN   \n"
    "I. Immaterielle Vermögensgegenstände 24.120,00 37.267,00 56.777,00 \n"
    "C. RECHNUNGSABGRENZUNGSPOSTEN 508.671,62 481.992,14 398.869,57 \n"
    "BILANZSUMME 580.193.968,91 572.543.885,42 559.822.592,60 \n \n"
    "PASSIVA \n  31.12.2024 31.12.2023 31.12.2022 \n"
    "A. EIGENKAPITAL   \nI. Stammkapital 22.000.000,00 22.000.000,00 22.000.000,00 \n"
    "E. RECHNUNGSABGREZUNGSPOSTEN 27.293,54 47.615,18 47.774,72 \n"
    "BILANZSUMME 580.193.968,91 572.543.885,42 559.822.592,60 \n \n"
    "Gewinn- und Verlustrechnung: \n  31.12.2024 31.12.2023 31.12.2022 \n"
    "1. Umsatzerlöse 66.262.339,54 65.210.791,75 63.199.333,25 \n"
    "13. Jahresüberschuss     -2.726.407,50     2.754.962,22       4.360.849,65 \n")

#: EGH 2023 — die GuV mit dem Leerzeichen hinter dem Komma.
GUV_EGH_2023 = (
    "Bilanz: \n \nAKTIVA \n  31.12.2023 31.12.2022 31.12.2021 \n"
    "BILANZSUMME 572.543.885,42 559.822.592,60 539.607.102,86 \n \n"
    "PASSIVA \n  31.12.2023 31.12.2022 31.12.2021 \n"
    "BILANZSUMME 572.543.885,42 559.822.592,60 539.607.102,86 \n \n"
    "Gewinn- und Verlustrechnung: \n  31.12.2023 31.12.2022 31.12.2021 \n"
    "12. Ergebnis nach Steuern 2.757.673,33 4.364.393,50 2.106.988,53 \n"
    "13. Sonstige Steuern 2.711,11 3.543,85 3.722,84 \n"
    "14. Jahresüberschuss     2.754.962,22     4.360.849,65        2.103.265, 69 \n")

#: Die vier beschreibenden Abschnitte, wörtlich (EGH 2024, gekürzt). Die
#: Kontaktzeilen stehen **absichtlich** mit drin: Der Test prüft, dass sie
#: nicht gespeichert werden.
ABSCHNITTE_EGH = (
    "Eigenbetrieb Gebäudewirtschaft und Hochbau (EGH) \n \n"
    "1) Gegenstand des Eigenbetriebes \n \n"
    "Gegenstand des Eigenbetriebes ist es, alle gebäudewirtschaftlichen und alle "
    "damit im Zusammenhang \nstehenden Aufgaben sowie allgemeine "
    "Serviceleistungen in einer Organisationsform wahrzunehmen. \n \n"
    "2) Beteiligungsverhältnisse \n \n"
    "Gesellschafter Anteil \nin Euro in Prozent \n"
    "Stadt Oldenburg 22.000.000,00 100,0 \n"
    "Stammkapital 22.000.000,00 100,0 \n \n"
    "3) Besetzung der Aufsichtsorgane \n \n"
    "Mitglieder des Betriebsausschusses  Funktion/Legitimierung \n"
    "Ruth Regina Drügemöller, Vorsitzende \nIngrid Kruse, stellvertretende Vorsitzende \n"
    "Ratsmitglied \nRatsmitglied \n"
    "Anschrift: Industriestraße 1 e \n26121 Oldenburg \n"
    "Telefon: (0441) 235 - 2565 \n"
    "E-Mail: gebaeudewirtschaft@example.org \n \n"
    "4) Beteiligungen \n \n"
    "Der Eigenbetrieb ist an keinen anderen Unternehmen oder Einrichtungen beteiligt. \n \n"
    "5) Grundzüge des Geschäftsverlaufs/Lage des Eigenbetriebs und Ausblick \n \n"
    "A. Vorbemerkungen \n \n1. Rechtliche Betriebsgrundlage \n"
    "Der Eigenbetrieb wird nach handelsrechtlichen Grundsätzen geführt. \n \n")

ABSCHLUSS_EGH = (
    "7) Vorliegen der Voraussetzungen des § 136 Absatz 1 NKomVG/Stand der "
    "Erfüllung des öffentlichen \nZwecks \n \n"
    "Die Voraussetzungen des § 136 Absatz 1 NKomVG sind erfüllt. \n \n"
    "8) Auswirkungen auf die Haushalts- und Finanzwirtschaft der Stadt Oldenburg \n \n"
    "Der EGH zahlt jährlich eine Eigenkapitalverzinsung von 4,69 Prozent auf das "
    "Stammkapital in Höhe von \n22.000.000 Euro an die Stadt Oldenburg. \n")


def _bericht_2024() -> list[str]:
    """Ein vollständiger kleiner Bericht: Titel, Inhaltsverzeichnis, zwei
    Gesellschaften mit Trennseite, Abschnitten, Bilanz und Kennzahlen.

    Die Seitenzahlen im Inhaltsverzeichnis sind die **gedruckten** (Fußzeile);
    die Trennseite liegt eine PDF-Seite später, weil das Titelblatt nicht
    mitzählt. Genau dieser Versatz ist die Seitenprobe."""
    return [
        # PDF-Seite 1 — Titelblatt
        "Beteiligungsbericht \nfür das Berichtsjahr 2024 \n",
        # 2 — Inhaltsverzeichnis: EGH ab gedruckter Seite 2, GSG ab 5
        ("Inhaltsverzeichnis \n \n"
         "2.2.1 Eigenbetrieb Gebäudewirtschaft und Hochbau ................. 2 \n"
         "2.4.9 GSG Oldenburg Bau- und Wohngesellschaft mbH ............... 5 \n"),
        # 3 (gedruckt 2) — Trennseite EGH
        "Stadt Oldenburg – Beteiligungsbericht 2024 \n- 2/6 - \n \n2.2.1 \n"
        "Eigenbetrieb Gebäudewirtschaft \nund Hochbau \n",
        # 4 — Abschnitte 1)–5)
        ABSCHNITTE_EGH,
        # 5 — Bilanz, GuV, Kennzahlen, Abschnitte 7) und 8)
        BILANZ_EGH_2024 + KENN_EGH_2024 + ABSCHLUSS_EGH,
        # 6 (gedruckt 5) — Trennseite GSG
        "Stadt Oldenburg – Beteiligungsbericht 2024 \n- 5/6 - \n \n2.4.9 \n"
        "GSG Oldenburg Bau- und Wohngesellschaft mbH \n",
        # 7 — GSG mit dem Tippfehler
        "1) Gegenstand des Unternehmens \n \nBau und Bewirtschaftung von Wohnungen. \n \n"
        + KENN_GSG_2022,
    ]


# --- Erkennung und Formatbruch ----------------------------------------------

def test_jahrgang_aus_dem_kopf():
    assert bb.jahrgang("Beteiligungsbericht \nfür das Berichtsjahr 2024 \n") == 2024
    assert bb.jahrgang("Stadt Oldenburg – Beteiligungsbericht 2022 \n- 3/201 -") == 2022
    assert bb.jahrgang("Irgendein anderes Dokument") is None


def test_alte_jahrgaenge_werden_gar_nicht_erst_gelesen():
    """Vor 2022 ist der Bericht anders aufgebaut — und sagt das auch.

    Kein stiller Fehlschlag: Ein leeres Ergebnis ohne Begründung sähe aus wie
    ein kaputter Parser."""
    e = bb.lies(["Beteiligungsbericht \nfür das Berichtsjahr 2021 \n"])
    assert e["jahrgang"] == 2021
    assert e["gesellschaften"] == []
    assert any("Formatbruch" in w for w in e["warnungen"])


# --- Beträge ----------------------------------------------------------------

@pytest.mark.parametrize("roh, erwartet", [
    ("-2.726.407,50", -2726407.50),
    ("- 11.116.380,86", -11116380.86),
    ("0", 0.0),
    ("46,99", 46.99),
    ("580.193.968,91", 580193968.91),
    # Der Tippfehler aus dem Bericht 2022: die letzte Gruppe hat zwei Stellen.
    ("5.698.082.44", None),
    ("keine Zahl", None),
])
def test_betrag(roh, erwartet):
    assert bb._betrag(roh) == erwartet


def test_entzerren_raeumt_beide_schadensarten():
    """Leerraum um den Tausenderpunkt und hinter dem Komma."""
    assert "23.439.654,83" in bb._entzerren("23.439 .654,83")
    assert "2.103.265,69" in bb._entzerren("2.103.265, 69")
    # Fließtext bleibt unangetastet: kein Komma mit zwei Ziffern dahinter.
    assert bb._entzerren("Erstens, zweitens") == "Erstens, zweitens"


# --- Kennzahlen -------------------------------------------------------------

def test_kennzahlen_absteigende_jahresspalten():
    reihen, warnungen = bb.kennzahlen(KENN_EGH_2024)
    assert warnungen == []
    assert reihen["jahresergebnis"][2024] == -2726407.50
    assert reihen["jahresergebnis"][2020] == 1195102.99
    assert reihen["bilanzsumme"][2024] == 580193968.91
    assert reihen["eigenkapitalquote"][2024] == 46.99


def test_kennzahlen_aufsteigende_jahresspalten():
    """Dieselbe Tabelle, andere Richtung — die Kopfzeile entscheidet.

    Ohne sie läge das Jahresergebnis 2024 (294.324,26) unter 2020."""
    reihen, warnungen = bb.kennzahlen(KENN_AWB_2024)
    assert warnungen == []
    assert reihen["jahresergebnis"][2024] == 294324.26
    assert reihen["jahresergebnis"][2020] == 394110.66
    assert reihen["bilanzsumme"][2024] == 25500408.17


def test_kennzahlen_mit_leerraum_in_den_betraegen():
    reihen, warnungen = bb.kennzahlen(KENN_AWB_2023)
    assert warnungen == []
    assert reihen["jahresergebnis"][2023] == 650289.04
    assert reihen["bilanzsumme"][2022] == 23439654.83


def test_tippfehler_verwirft_die_zeile_statt_sie_zu_raten():
    """``5.698.082.44`` ist kein Betrag — und dann ist die ganze Zeile hin.

    Vier Werte auf fünf Jahre zu verteilen hieße raten, welches Jahr leer
    ausgeht. Die beiden anderen Zeilen bleiben."""
    reihen, warnungen = bb.kennzahlen(KENN_GSG_2022)
    assert "jahresergebnis" not in reihen
    assert reihen["bilanzsumme"][2018] == 279624042.36
    assert reihen["eigenkapitalquote"][2022] == 38.1
    assert any("jahresergebnis" in w and "verworfen" in w for w in warnungen)


def test_berichtsjahr_steht_nicht_immer_in_der_tabelle():
    """Die Großleitstelle führt im Bericht für 2024 die Jahre 2017–2021."""
    reihen, _ = bb.kennzahlen(KENN_GOL)
    assert sorted(reihen["jahresergebnis"]) == [2017, 2018, 2019, 2020, 2021]
    assert 2024 not in reihen["jahresergebnis"]


def test_historische_daten_liegen_nicht_vor_ist_kein_fehler():
    reihen, warnungen = bb.kennzahlen(
        "Kennzahlen im Zeitverlauf: \nHistorische Daten liegen noch nicht vor. \n")
    assert reihen == {}
    assert warnungen == []


# --- Bilanz und Gewinn- und Verlustrechnung ---------------------------------

def test_bilanzsummen_aus_aktiva_und_passiva():
    summen = bb.bilanzsummen(BILANZ_EGH_2024)
    assert summen == {2024: 580193968.91, 2023: 572543885.42, 2022: 559822592.60}


def test_bilanz_ohne_zweite_summenzeile_gibt_nichts():
    """Eine Bilanz, die ihre Summe nur einmal nennt, ist keine Probe."""
    nur_aktiva = BILANZ_EGH_2024.split("PASSIVA")[0]
    assert bb.bilanzsummen(nur_aktiva) == {}


def test_bilanz_die_nicht_aufgeht_gibt_nichts():
    kaputt = BILANZ_EGH_2024.replace(
        "BILANZSUMME 580.193.968,91 572.543.885,42 559.822.592,60 \n \n"
        "Gewinn",
        "BILANZSUMME 580.193.968,92 572.543.885,42 559.822.592,60 \n \nGewinn")
    assert bb.bilanzsummen(kaputt) == {}


def test_guv_schlusszeile_ohne_postennummer():
    """Die Postennummer (13., 14., …) darf nicht als Betrag mitgelesen werden."""
    assert bb.guv_ergebnisse(BILANZ_EGH_2024)[2024] == -2726407.50
    # …und das Leerzeichen hinter dem Komma ist geräumt.
    assert bb.guv_ergebnisse(GUV_EGH_2023)[2021] == 2103265.69


# --- Zuordnung Abschnitt → Gesellschaft -------------------------------------

def test_gliederung_verlangt_dass_beide_angaben_uebereinstimmen():
    seiten = _bericht_2024()
    ges, warnungen = bb.gliederung(seiten)
    assert [g.key for g in ges] == ["egh", "gsg"]
    assert [g.seite_gedruckt for g in ges] == [2, 5]
    assert warnungen == []


def test_verschobene_trennseite_wird_uebersprungen():
    """Sagt das Inhaltsverzeichnis etwas anderes als die Trennseite, ist die
    Zuordnung nicht gesichert — dann lieber nichts."""
    seiten = _bericht_2024()
    # Eingeschoben hinter der EGH-Trennseite: EGH steht weiter richtig, die
    # GSG rutscht eine Seite weiter und passt nicht mehr zum Verzeichnis.
    seiten.insert(3, "Eine eingeschobene Seite \n")
    ges, warnungen = bb.gliederung(seiten)
    assert [g.key for g in ges] == ["egh"]
    assert any("nicht gesichert" in " ".join(w.split()) for w in warnungen)


def test_unbekannte_gesellschaft_kommt_mit_notschluessel_herein():
    key, name, konzern, bekannt = bb.erkenne_gesellschaft("Neue Stadtwerke GmbH")
    assert bekannt is False
    assert key == "neue_stadtwerke_gmbh"
    assert konzern is None


def test_komplementaer_gmbh_wird_nicht_mit_der_kg_verwechselt():
    assert bb.erkenne_gesellschaft(
        "Weser-Ems Halle Oldenburg Beteiligungs-GmbH")[0] == "weh_komplementaer"
    assert bb.erkenne_gesellschaft(
        "Weser-Ems Halle Oldenburg GmbH & Co. KG")[0] == "weh"


# --- Abschnitte -------------------------------------------------------------

def test_abschnitte_werden_der_reihe_nach_getrennt():
    a = bb.abschnitte(ABSCHNITTE_EGH + ABSCHLUSS_EGH)
    assert set(a) == {"gegenstand", "beteiligungsverhaeltnisse", "aufsichtsorgane",
                      "beteiligungen", "haushalt"}
    assert "gebäudewirtschaftlichen" in a["gegenstand"]
    assert "Eigenkapitalverzinsung" in a["haushalt"]
    # Abschnitt 5 wird nicht gespeichert (der Lagebericht der Gesellschaft).
    assert "Vorbemerkungen" not in a.get("beteiligungen", "")


def test_kontaktangaben_werden_nicht_gespeichert():
    """Namen der Aufsichtsratsmitglieder bleiben — sie üben ein öffentliches
    Amt aus. Anschrift, Telefonnummer und E-Mail gehören nicht in den Bestand.

    Das Repo hält fremde Adressen ausdrücklich draußen
    (``scripts/lint_adressen.py``); die Fixture trägt deshalb example.org."""
    a = bb.abschnitte(ABSCHNITTE_EGH)
    organe = a["aufsichtsorgane"]
    assert "Drügemöller" in organe
    assert "@" not in organe
    assert "Telefon" not in organe
    assert "Industriestraße" not in organe


# --- Ein ganzer Bericht -----------------------------------------------------

def test_lies_ganzer_bericht_mit_proben():
    e = bb.lies(_bericht_2024())
    assert e["jahrgang"] == 2024
    assert [g.key for g in e["gesellschaften"]] == ["egh", "gsg"]
    egh = e["gesellschaften"][0]
    assert egh.kennzahlen["bilanzsumme"][2024] == 580193968.91
    assert egh.abschnitte["gegenstand"]
    # Bilanzprobe und Ergebnisprobe für die drei Bilanzjahre.
    proben = {(x["kennzahl"], x["jahr"]): x for x in e["dokumentproben"]}
    assert proben[("bilanzsumme", 2024)]["ok"]
    assert proben[("jahresergebnis", 2024)]["ok"]
    assert all(x["ok"] for x in e["dokumentproben"])


def test_ueberlappung_bestaetigt_und_widerspricht():
    a = bb.Gesellschaft(key="egh", name="EGH", gliederung="2.2.1", seite=3,
                        seite_gedruckt=2)
    a.kennzahlen = {"bilanzsumme": {2022: 559822592.60, 2023: 572543885.42}}
    b = bb.Gesellschaft(key="egh", name="EGH", gliederung="2.2.1", seite=3,
                        seite_gedruckt=2)
    b.kennzahlen = {"bilanzsumme": {2022: 559822592.60, 2023: 999.0}}
    u = bb.ueberlappung({2023: [a], 2024: [b]})
    assert u["bestaetigt"][("egh", "bilanzsumme", 2022)] == 2
    assert [w["jahr"] for w in u["widersprueche"]] == [2023]


# --- Einlesen und Speichern -------------------------------------------------

def _store(tmp_path) -> CouncilStore:
    return CouncilStore(tmp_path / "council.sqlite")


def test_einlesen_speichert_nur_geprueftes(tmp_path):
    store = _store(tmp_path)
    p = finanzquellen.Protokoll(still=True)
    aus = bb.einlesen(store, {2024: {
        "seiten": _bericht_2024(),
        "url": "https://example.org/beteiligungsbericht_2024.pdf",
        "label": "Beteiligungsbericht 2024"}}, p)

    assert aus["gesellschaften"] == 2
    assert aus["widersprueche"] == 0
    # Der einzelne Bericht kann nur die Bilanz- und die Ergebnisprobe bieten;
    # was keine trägt (die Jahre ohne Bilanz, die Eigenkapitalquote), fällt weg.
    assert aus["kennzahlen"] > 0
    assert aus["verworfen"] > 0
    assert store.beteiligungsbericht_jahre() == [2024]
    # Jede Zeile trägt ihre Herkunft.
    store.herkunft_aufraeumen()
    assert store.herkunft_luecken() == {}
    store.close()


def test_gespeicherte_kennzahl_traegt_probe_und_messwert(tmp_path):
    store = _store(tmp_path)
    bb.einlesen(store, {2024: {
        "seiten": _bericht_2024(),
        "url": "https://example.org/beteiligungsbericht_2024.pdf",
        "label": "Beteiligungsbericht 2024"}},
        finanzquellen.Protokoll(still=True))
    zeilen = [z for z in store.get_gesellschaft_kennzahlen("egh")
              if z["kennzahl"] == "bilanzsumme" and z["jahr"] == 2024]
    assert len(zeilen) == 1
    h = store.get_herkunft([zeilen[0]["herkunft_id"]])[0]
    assert h["art"] == "stadt"
    assert h["probe"] == "beteiligung_bilanzprobe"
    assert "Abschnitt 2.2.1" in h["fundstelle"]
    assert h["seite"] == 2
    assert "0.00" in h["probe_ergebnis"]
    store.close()


def test_texte_stehen_ausdruecklich_als_ungeprueft(tmp_path):
    """Fließtext trägt keine Rechenprobe — und behauptet auch keine."""
    store = _store(tmp_path)
    bb.einlesen(store, {2024: {
        "seiten": _bericht_2024(),
        "url": "https://example.org/beteiligungsbericht_2024.pdf",
        "label": "Beteiligungsbericht 2024"}},
        finanzquellen.Protokoll(still=True))
    texte = store.get_gesellschaft_texte("egh")
    assert texte
    for t in texte:
        h = store.get_herkunft([t["herkunft_id"]])[0]
        assert h["probe"] == herkunft.UNGEPRUEFT
        assert h["url"]
        assert h["fundstelle"]
    store.close()


def test_leeres_ergebnis_ersetzt_keinen_bestand(tmp_path):
    """Ändert die Stadt den Aufbau, liefert der Parser irgendwann nichts — und
    das sieht für einen unbeaufsichtigten Lauf aus wie „es gibt nichts"."""
    store = _store(tmp_path)
    gut = {2024: {"seiten": _bericht_2024(),
                  "url": "https://example.org/bb2024.pdf",
                  "label": "Beteiligungsbericht 2024"}}
    bb.einlesen(store, gut, finanzquellen.Protokoll(still=True))
    vorher = len(store.get_gesellschaft_kennzahlen())
    assert vorher > 0

    p = finanzquellen.Protokoll(still=True)
    aus = bb.einlesen(store, {2024: {
        "seiten": ["Beteiligungsbericht \nfür das Berichtsjahr 2024 \n"],
        "url": "https://example.org/bb2024.pdf",
        "label": "Beteiligungsbericht 2024"}}, p)
    assert aus["kennzahlen"] == 0
    assert len(store.get_gesellschaft_kennzahlen()) == vorher
    store.close()


def test_konzernvergleich_ist_einordnung_und_verwirft_nichts(tmp_path):
    """Beitrag im Gesamtabschluss gegen Jahresergebnis im Beteiligungsbericht.

    Gemessen für 2024: Klinikum und Weser-Ems Halle stimmen auf die
    Tausenderstelle, der Eigenbetrieb Gebäudewirtschaft liegt 25 TEUR daneben
    (der Konzern zählt nur die ordentlichen Posten). Beides bleibt stehen."""
    store = _store(tmp_path)
    bb.einlesen(store, {2024: {
        "seiten": _bericht_2024(),
        "url": "https://example.org/bb2024.pdf",
        "label": "Beteiligungsbericht 2024"}},
        finanzquellen.Protokoll(still=True))

    quelle = herkunft.Herkunft(art="ris", dokument_id=302709,
                               label="Gesamtabschluss 2024",
                               url="https://example.org/ga2024.pdf",
                               probe="konzern_traegersumme")
    store.save_konzern_jahrgang(2024, [], [
        {"art": "ertraege", "traeger_key": "egh", "traeger": "EGH",
         "betrag_teur": 69889.0, "vorjahr_teur": None},
        {"art": "aufwendungen", "traeger_key": "egh", "traeger": "EGH",
         "betrag_teur": 72590.0, "vorjahr_teur": None},
    ], quelle)

    v = bb.konzernvergleich(store, 2024)
    assert len(v) == 1
    assert v[0]["gesellschaft"] == "egh"
    assert v[0]["konzern_beitrag"] == pytest.approx(-2701000.0)
    assert v[0]["jahresergebnis"] == pytest.approx(-2726407.50)
    # 25 TEUR Unterschied — und die Kennzahl steht trotzdem im Bestand.
    assert abs(v[0]["differenz"]) == pytest.approx(25407.50)
    assert store.get_gesellschaft_kennzahlen("egh")
    store.close()
