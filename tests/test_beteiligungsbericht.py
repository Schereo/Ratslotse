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
    assert bb.budget_year("Beteiligungsbericht \nfür das Berichtsjahr 2024 \n") == 2024
    assert bb.budget_year("Stadt Oldenburg – Beteiligungsbericht 2022 \n- 3/201 -") == 2022
    assert bb.budget_year("Irgendein anderes Dokument") is None


def test_alte_jahrgaenge_werden_gar_nicht_erst_gelesen():
    """Vor 2022 ist der Bericht anders aufgebaut — und sagt das auch.

    Kein stiller Fehlschlag: Ein leeres Ergebnis ohne Begründung sähe aus wie
    ein kaputter Parser."""
    e = bb.lies(["Beteiligungsbericht \nfür das Berichtsjahr 2021 \n"])
    assert e["budget_year"] == 2021
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
    reihen, warnungen = bb.indicators(KENN_EGH_2024)
    assert warnungen == []
    assert reihen["jahresergebnis"][2024] == -2726407.50
    assert reihen["jahresergebnis"][2020] == 1195102.99
    assert reihen["bilanzsumme"][2024] == 580193968.91
    assert reihen["eigenkapitalquote"][2024] == 46.99


def test_kennzahlen_aufsteigende_jahresspalten():
    """Dieselbe Tabelle, andere Richtung — die Kopfzeile entscheidet.

    Ohne sie läge das Jahresergebnis 2024 (294.324,26) unter 2020."""
    reihen, warnungen = bb.indicators(KENN_AWB_2024)
    assert warnungen == []
    assert reihen["jahresergebnis"][2024] == 294324.26
    assert reihen["jahresergebnis"][2020] == 394110.66
    assert reihen["bilanzsumme"][2024] == 25500408.17


def test_kennzahlen_mit_leerraum_in_den_betraegen():
    reihen, warnungen = bb.indicators(KENN_AWB_2023)
    assert warnungen == []
    assert reihen["jahresergebnis"][2023] == 650289.04
    assert reihen["bilanzsumme"][2022] == 23439654.83


def test_tippfehler_verwirft_die_zeile_statt_sie_zu_raten():
    """``5.698.082.44`` ist kein Betrag — und dann ist die ganze Zeile hin.

    Vier Werte auf fünf Jahre zu verteilen hieße raten, welches Jahr leer
    ausgeht. Die beiden anderen Zeilen bleiben."""
    reihen, warnungen = bb.indicators(KENN_GSG_2022)
    assert "jahresergebnis" not in reihen
    assert reihen["bilanzsumme"][2018] == 279624042.36
    assert reihen["eigenkapitalquote"][2022] == 38.1
    assert any("jahresergebnis" in w and "verworfen" in w for w in warnungen)


def test_berichtsjahr_steht_nicht_immer_in_der_tabelle():
    """Die Großleitstelle führt im Bericht für 2024 die Jahre 2017–2021."""
    reihen, _ = bb.indicators(KENN_GOL)
    assert sorted(reihen["jahresergebnis"]) == [2017, 2018, 2019, 2020, 2021]
    assert 2024 not in reihen["jahresergebnis"]


def test_historische_daten_liegen_nicht_vor_ist_kein_fehler():
    reihen, warnungen = bb.indicators(
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
    ges, warnungen = bb.classification(seiten)
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
    ges, warnungen = bb.classification(seiten)
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
    assert e["budget_year"] == 2024
    assert [g.key for g in e["gesellschaften"]] == ["egh", "gsg"]
    egh = e["gesellschaften"][0]
    assert egh.indicators["bilanzsumme"][2024] == 580193968.91
    assert egh.abschnitte["gegenstand"]
    # Bilanzprobe und Ergebnisprobe für die drei Bilanzjahre.
    probes = {(x["indicator"], x["year"]): x for x in e["dokumentproben"]}
    assert probes[("bilanzsumme", 2024)]["ok"]
    assert probes[("jahresergebnis", 2024)]["ok"]
    assert all(x["ok"] for x in e["dokumentproben"])


def test_ueberlappung_bestaetigt_und_widerspricht():
    a = bb.Gesellschaft(key="egh", name="EGH", classification="2.2.1", page=3,
                        seite_gedruckt=2)
    a.indicators = {"bilanzsumme": {2022: 559822592.60, 2023: 572543885.42}}
    b = bb.Gesellschaft(key="egh", name="EGH", classification="2.2.1", page=3,
                        seite_gedruckt=2)
    b.indicators = {"bilanzsumme": {2022: 559822592.60, 2023: 999.0}}
    u = bb.ueberlappung({2023: [a], 2024: [b]})
    assert u["bestaetigt"][("egh", "bilanzsumme", 2022)] == 2
    assert [w["year"] for w in u["widersprueche"]] == [2023]


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
    assert aus["indicators"] > 0
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
              if z["indicator"] == "bilanzsumme" and z["year"] == 2024]
    assert len(zeilen) == 1
    h = store.get_herkunft([zeilen[0]["herkunft_id"]])[0]
    assert h["art"] == "stadt"
    assert h["probe"] == "beteiligung_bilanzprobe"
    assert "Abschnitt 2.2.1" in h["citation"]
    assert h["page"] == 2
    assert "0.00" in h["probe_result"]
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
        assert h["citation"]
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
    assert aus["indicators"] == 0
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

    source = herkunft.Herkunft(art="ris", document_id=302709,
                               label="Gesamtabschluss 2024",
                               url="https://example.org/ga2024.pdf",
                               probe="konzern_traegersumme")
    store.save_konzern_jahrgang(2024, [], [
        {"art": "revenues", "entity_key": "egh", "entity": "EGH",
         "amount_keur": 69889.0, "prior_year_keur": None},
        {"art": "expenses", "entity_key": "egh", "entity": "EGH",
         "amount_keur": 72590.0, "prior_year_keur": None},
    ], source)

    v = bb.konzernvergleich(store, 2024)
    assert len(v) == 1
    assert v[0]["company"] == "egh"
    assert v[0]["konzern_beitrag"] == pytest.approx(-2701000.0)
    assert v[0]["jahresergebnis"] == pytest.approx(-2726407.50)
    # 25 TEUR Unterschied — und die Kennzahl steht trotzdem im Bestand.
    assert abs(v[0]["difference"]) == pytest.approx(25407.50)
    assert store.get_gesellschaft_kennzahlen("egh")
    store.close()


# --- Abschnitt 3: Aufsichtsorgane -------------------------------------------
#
# Alle Fixtures hier sind wörtliche `council_gesellschaft_texte`-Inhalte aus
# den Berichten 2022–2024, jeder mit genau einer Eigenheit.

#: AWB 2023 — der Fall, für den es die Rechenprobe gibt: **acht** Namen,
#: **sieben** „Ratsmitglied". Der Bericht selbst ist unvollständig; jede
#: Zuordnung wäre ab der Lücke um einen Platz verschoben. Dazu zwei
#: Zeilenumbrüche mitten im Eintrag (einer hinter dem Komma, einer im Wort)
#: und am Ende der Steckbrief-Kasten der Seite.
AUFSICHT_AWB_2023 = (
    "Mitglieder des Betriebsausschusses  Funktion/Legitimierung \n"
    "Klaus Raschke, Vorsitzender  \n"
    "Dr. Sebastian Rohe, stellvertretender Vorsitzender, \nbis zum 27.02.2023 \n"
    "Claudia Petra Küpker, Küpker, stellvertretende Vor-\nsitzende, ab 28.02.2023 \n"
    "Dr. Alaa Alhamwi, bis zum 27.11.2023 \n"
    "Ruth Regina Drügemöller, ab 28.11.2023 \n"
    "Claudia Oeljeschleger \n"
    "Christine Wolff, ab 28. Februar 2023 \n"
    "Jens Lükermann  \n"
    "Ratsmitglied  \nRatsmitglied \n \nRatsmitglied \n \nRatsmitglied \n"
    "Ratsmitglied \n \nRatsmitglied \nRatsmitglied  \n"
    "Abfallwirtschaftsbetrieb Stadt Oldenburg (AWB)  \n \n\n26123 Oldenburg \n\n\n\n"
    "Betriebssatzung vom: \n \n18. Dezember 1995 \n"
    "zuletzt geändert am 26. September 2011 \n"
    "Betriebsleitung: Volker Schneider-Kühn \n"
    "Torsten von Varel, stellvertretender Betriebsleiter")

#: Großleitstelle 2022 — die Namensspalte ist nach Trägern gegliedert
#: („Stadt Oldenburg:"), und diese Überschriften haben in der Funktionsspalte
#: keine Entsprechung. Wer sie als Personen zählt, hat zwölf Namen gegen acht
#: Ämter und verliert eine Zuordnung, die in Ordnung ist.
AUFSICHT_GOL_2022 = (
    "Mitglieder des Verwaltungsrates  Funktion/Legitimierung \n"
    "Stadt Oldenburg: \nDr. Julia Figura \nMargrit Conty \n \n"
    "Landkreis Ammerland: \nKarin Harms \nDr. Hans Fittje \n \n"
    "Landkreis Cloppenburg: \nAnne Tapken \nHerbert Holthaus \n \n"
    "Landkreis Oldenburg: \nChristian Wolf \nWerner Wulf \n \n"
    "Stadtkämmerin \nRatsmitglied \n \n \nLandrätin \nKreistagsmitglied  \n \n \n"
    "Kreisrätin \nKreistagsmitglied  \n \n \n1. Kreisrat (Vorsitzender) \n"
    "Kreistagsmitglied \n\n26121 Oldenburg \n\n\nBetriebssatzung vom: \n \n"
    "20. Januar 2007 \nzuletzt geändert am 15. September 2015 \n"
    "Geschäftsführung: Frank Leenderts")

#: TGO 2022 — **zwei** Gremien in einem Abschnitt, nacheinander.
AUFSICHT_TGO_2022 = (
    "Mitglieder der Gesellschafterversammlung   Funktion/Legitimierung \n"
    "Jürgen Krogmann, Vorsitzender \nBernhard Ellberg \nJutta Schober-Stockmann \n"
    "Prof. Dr. Bruder \nProf. Dr.-Ing. Weisensee \n"
    "Oberbürgermeister \nRatsmitglied \nRatsmitglied \nVertreter Universität \n"
    "Vertreter Hochschule \n \n"
    "Mitglieder des Aufsichtsrates   Funktion/Legitimierung \n"
    "Jürgen Krogmann  \nDr. Alaa Alhamwi  \nPaul Behrens  \nKlaus Raschke  \n"
    "Bernhard Ellberg, Vorsitzender \nJutta Schober-Stockmann  \n"
    "Prof. Dr. Bruder  \nProf. Dr.-Ing. Weisensee \n"
    "Oberbürgermeister \nRatsmitglied \nRatsmitglied \nRatsmitglied \n"
    "Ratsmitglied \nRatsmitglied \nVertreter Universität \nVertreter Hochschule")

#: TGO Besitz 2024 — **keine** Funktionsspalte, und statt Personen benennt
#: der Bericht Entsendungsrechte. „Vertreter/in der …" darf hier nicht als
#: Funktion durchgehen, sonst bliebe die Namensspalte leer.
AUFSICHT_TGO_BESITZ_2024 = (
    "Mitglieder der Gesellschafterversammlung   \n"
    "Vertreter/in der TGO Technologie- und Gründerzentrum Oldenburg mbH  \n"
    "Vertreter/in der Norddeutschen Landesbank Girozentrale, Hannover \n"
    "Vertreter/in der Oldenburgischen Landesbank AG, Oldenburg  \n"
    "Vertreter/in von Peter Waskönig (Erben), Saterland")

#: Bäderbetrieb 2024 — zwei Herren Rohe in derselben Liste. Die Vorlage für
#: die Namensvettern-Probe der API.
AUFSICHT_BBO_2024 = (
    "Mitglieder des Betriebsausschusses  Funktion/Legitimierung \n"
    "Nicolai Beerheide, Vorsitzender  \n"
    "Rita Schilling, stellvertretende Vorsitzende \n"
    "Dr. Sebastian Rohe \nBenno Sönke Schulz (bis 17. Juni 2024) \n"
    "Dr. Georg Rohe (ab 17. Juni 2024) \n"
    "Ratsmitglied \nRatsmitglied \nRatsmitglied \nRatsmitglied \nRatsmitglied")


def test_aufsichtsorgane_paart_spalten_wenn_die_probe_haelt():
    personen, zuordenbar = bb.aufsichtsorgane(AUFSICHT_BBO_2024)
    assert zuordenbar
    assert [p.name for p in personen] == [
        "Nicolai Beerheide", "Rita Schilling", "Dr. Sebastian Rohe",
        "Benno Sönke Schulz", "Dr. Georg Rohe"]
    assert all(p.position == "Ratsmitglied" for p in personen)
    assert all(p.committee == "Betriebsausschuss" for p in personen)
    assert [p.chair_role for p in personen[:3]] == ["chair", "deputy", None]
    assert personen[3].note == "bis 17. Juni 2024"
    assert personen[4].note == "ab 17. Juni 2024"
    assert [p.sort_order for p in personen] == [0, 1, 2, 3, 4]


def test_aufsichtsorgane_ohne_probe_bleibt_jedes_amt_leer():
    """Acht Namen, sieben Ämter — dann steht an **keinem** Namen ein Amt.

    Der AWB-Abschnitt 2023 ist der gemessene Fall: Der Bericht selbst führt
    eine Funktionszeile weniger, als er Personen nennt. Jede Zuordnung wäre ab
    der Lücke um einen Platz verschoben, und das hieße, einer namentlich
    genannten Person ein Amt anzuhängen, das sie nie hatte."""
    personen, zuordenbar = bb.aufsichtsorgane(AUFSICHT_AWB_2023)
    assert not zuordenbar
    assert all(p.position is None for p in personen)
    # Die Umbrüche mitten im Eintrag sind zusammengefügt, nicht gezählt.
    assert [p.name for p in personen] == [
        "Klaus Raschke", "Dr. Sebastian Rohe", "Claudia Petra Küpker",
        "Dr. Alaa Alhamwi", "Ruth Regina Drügemöller", "Claudia Oeljeschleger",
        "Christine Wolff", "Jens Lükermann"]
    assert personen[2].chair_role == "deputy"
    assert personen[2].note == "ab 28.02.2023"


def test_aufsichtsorgane_verwirft_den_seitenrand():
    """Der Steckbrief-Kasten neben der Tabelle ist keine Aufsichtsperson.

    Anschrift, Satzungsdatum und Betriebsleitung stehen im Extrakt hinter der
    Funktionsspalte — und die Betriebsleitung trägt Namen. Ungefiltert säße
    „Volker Schneider-Kühn" im Betriebsausschuss."""
    namen = [p.name for p in bb.aufsichtsorgane(AUFSICHT_AWB_2023)[0]]
    assert "Volker Schneider-Kühn" not in namen
    assert "Torsten von Varel" not in namen
    assert not any(n.startswith("26123") or "Betriebssatzung" in n
                   or "Abfallwirtschaftsbetrieb" in n for n in namen)


def test_aufsichtsorgane_traegergliederung_zaehlt_nicht_als_person():
    personen, zuordenbar = bb.aufsichtsorgane(AUFSICHT_GOL_2022)
    assert zuordenbar
    assert "Stadt Oldenburg" not in [p.name for p in personen]
    assert len(personen) == 8
    assert personen[0].name == "Dr. Julia Figura"
    assert personen[0].position == "Stadtkämmerin"
    assert personen[-1].position == "Kreistagsmitglied"
    assert personen[-2].position == "1. Kreisrat (Vorsitzender)"
    assert {p.committee for p in personen} == {"Verwaltungsrat"}


def test_aufsichtsorgane_trennt_mehrere_gremien():
    personen, zuordenbar = bb.aufsichtsorgane(AUFSICHT_TGO_2022)
    assert zuordenbar
    assert [p.committee for p in personen] == (
        ["Gesellschafterversammlung"] * 5 + ["Aufsichtsrat"] * 8)
    # Die Reihenfolge läuft über beide Gremien durch — sie ist der Schlüssel.
    assert [p.sort_order for p in personen] == list(range(13))
    aufsichtsrat = [p for p in personen if p.committee == "Aufsichtsrat"]
    assert aufsichtsrat[4].chair_role == "chair"
    assert aufsichtsrat[-1].position == "Vertreter Hochschule"


def test_aufsichtsorgane_ohne_funktionsspalte_ist_kein_befund():
    """Wo der Bericht keine Ämter nennt, ist nichts falsch zuzuordnen.

    Die TGO Besitz GmbH & Co. KG führt statt Personen die Entsendungsrechte
    ihrer Gesellschafter. Das ist kein gerissener Parser, sondern ein anders
    gebauter Abschnitt — die Namen kommen herein, die Ämter bleiben leer, und
    die Seite muss deshalb keine Warnung zeigen."""
    personen, zuordenbar = bb.aufsichtsorgane(AUFSICHT_TGO_BESITZ_2024)
    assert zuordenbar
    assert len(personen) == 4
    assert all(p.position is None for p in personen)
    assert personen[0].name.startswith("Vertreter/in der TGO")


# --- Abschnitt 2: Beteiligungsverhältnisse ----------------------------------

#: Großleitstelle — sechs gleiche Anteile. 6 × 16,67 % sind 100,02 %, und das
#: ist eine gerundete Tabelle und keine falsche.
EIGNER_GOL = (
    "Gesellschafter Anteil \nin Euro in Prozent \n"
    "Stadt Oldenburg 20.000,00 16,67 \nLandkreis Ammerland 20.000,00 16,67 \n"
    "Landkreis Cloppenburg 20.000,00 16,67 \nLandkreis Oldenburg 20.000,00 16,67 \n"
    "Landkreis Wesermarsch 20.000,00 16,67 \nStadt Delmenhorst 20.000,00 16,67 \n"
    "Stammkapital 120.000,00 100,0")

#: TGO Besitz 2024 — die Namen stehen über den Zahlen und sind mitten im Wort
#: umbrochen („Girozent-\nrale"). Dazu der Steckbrief-Kasten am Ende.
EIGNER_TGO_BESITZ_2024 = (
    "Gesellschafter Kapitalanteil \nin Euro in Prozent \n"
    "TGO Technologie- und Gründerzentrum \nOldenburg GmbH (Komplementärin) \n"
    "585.429,20 51,0 \n"
    "Norddeutsche Landesbank Girozent-\nrale, Hannover (Kommanditistin) \n"
    "102.258,38 8,91 \n"
    "Oldenburgische Landesbank AG, Olden-\nburg (Kommanditistin) \n"
    "102.258,38 8,91 \n"
    "Landessparkasse zu Oldenburg, Olden-\nburg (Kommanditistin) \n"
    "102.258,38 8,91 \n"
    "Oldenburgische Landesbrandkasse, \nOldenburg (Kommanditistin) \n"
    "102.258,38 8,91 \n"
    "Oldenburger Volksbank eG, Oldenburg \n(Kommanditistin) \n51.129,19 4,45 \n"
    "Peter Waskönig (Erben), Saterland \n(Kommanditist) \n51.129,19 4,45 \n"
    "Schomaker Bauträger GmbH & Co. KG, \nDörpen (Kommanditistin) \n"
    "51.129,19 4,45 \n"
    "Stammkapital 1.147.850,29 100,0 \n  \n\n26129 Oldenburg  \n\n\n\n"
    "Gesellschaftsvertrag vom: \n \n13. Dezember 2000 \n"
    "Handelsregister: Amtsgericht Oldenburg HRA 3722")

#: Stadion Oldenburg GmbH & Co. KG 2024 — die Anteile ergeben 5.000 €, die
#: Summenzeile nennt 25.000 €. Das Dokument widerspricht sich selbst.
EIGNER_STADION_2024 = (
    "Gesellschafter Anteil \nin Euro in Prozent \n"
    "Stadion Oldenburg \nBeteiligungs-GmbH  \n(Komplementärin) \n0,00 0,0 \n"
    "Stadt Oldenburg  \n(Kommanditistin) \n5.000,00 100,0 \n"
    "Stammkapital 25.000,00 100,0")


def test_stammkapital_ist_kein_eigentuemer():
    eigner, probe = bb.beteiligungsverhaeltnisse(EIGNER_GOL)
    assert [e.name for e in eigner] == [
        "Stadt Oldenburg", "Landkreis Ammerland", "Landkreis Cloppenburg",
        "Landkreis Oldenburg", "Landkreis Wesermarsch", "Stadt Delmenhorst"]
    assert all(e.amount_eur == 20000.0 and e.share_pct == 16.67
               for e in eigner)
    assert "120.000,00" in probe and "100,02" in probe


def test_eigentuemer_fuegt_umbrochene_namen_zusammen():
    eigner, probe = bb.beteiligungsverhaeltnisse(EIGNER_TGO_BESITZ_2024)
    assert len(eigner) == 8
    assert eigner[1].name == ("Norddeutsche Landesbank Girozentrale, Hannover "
                              "(Kommanditistin)")
    assert eigner[1].amount_eur == 102258.38
    assert eigner[0].share_pct == 51.0
    assert probe and "1.147.850,29" in probe
    # Der Steckbrief-Kasten hinter der Tabelle ist kein Gesellschafter.
    assert not any("Amtsgericht" in e.name or "26129" in e.name for e in eigner)


def test_gerissene_anteilsprobe_liefert_gar_keine_eigentuemer():
    """0,00 € + 5.000,00 € sind nicht die 25.000 €, die die Summenzeile nennt.

    Der Bericht 2024 sagt das über die Stadion Oldenburg GmbH & Co. KG so.
    Welche der beiden Zahlen stimmt, verrät die Tabelle nicht — also kommt
    keine halbe Eigentümerliste heraus, sondern keine."""
    eigner, probe = bb.beteiligungsverhaeltnisse(EIGNER_STADION_2024)
    assert eigner == []
    assert probe is None


def test_personen_und_eigentuemer_landen_mit_herkunft_im_bestand(tmp_path):
    store = _store(tmp_path)
    bb.einlesen(store, {2024: {
        "seiten": _bericht_2024(),
        "url": "https://example.org/beteiligungsbericht_2024.pdf",
        "label": "Beteiligungsbericht 2024"}},
        finanzquellen.Protokoll(still=True))

    personen = store.get_gesellschaft_personen()
    assert [p["name"] for p in personen] == ["Ruth Regina Drügemöller",
                                             "Ingrid Kruse"]
    assert all(p["position"] == "Ratsmitglied" for p in personen)
    assert all(p["roles_assignable"] == 1 for p in personen)
    h = store.get_herkunft([personen[0]["herkunft_id"]])[0]
    assert h["probe"] == "beteiligung_spaltenprobe"
    assert "Betriebsausschuss" in h["citation"]

    eigner = store.get_gesellschaft_eigentuemer()
    assert [e["name"] for e in eigner] == ["Stadt Oldenburg"]
    assert eigner[0]["amount_eur"] == 22000000.0
    he = store.get_herkunft([eigner[0]["herkunft_id"]])[0]
    assert he["probe"] == "beteiligung_anteilsprobe"
    assert "22.000.000,00" in he["probe_result"]

    # Keine Zeile ohne Herkunft — auch die beiden neuen Tabellen nicht.
    store.herkunft_aufraeumen()
    assert store.herkunft_luecken() == {}
    store.close()
