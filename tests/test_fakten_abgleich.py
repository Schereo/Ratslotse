"""Der Abgleich der Fakten-Eval (``eval/fakten_abgleich.py``) — offline.

Jede Regel hier hat einen Anlass aus echten Antworten und echten Prompts:
die deutschen Zahlformate aus dem Faktencheck vom 23.09.2026, die
„davon“-Zeilen unter dem falschen Jahr (derselbe Faktencheck), die Rundung
„rund 337 Millionen“. Wer eine Regel lockert, sieht hier, welchen Befund er
damit nicht mehr sähe.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from eval import fakten_abgleich as fa  # noqa: E402

# Der Schuldenblock, wie ihn qa.geld_block am 23.09.2026 baute — mit dem
# Fehler: Die Aufschlüsselung von 2025 hängt unter „Ein Jahr davor (2024)“.
SCHULDEN_KONTEXT = """SCHULDENSTAND (Statistisches Jahrbuch der Stadt, Tabelle 1108). Beleg: Tabelle 1108 — Stand der Verschuldung 1995 bis 2025, Stand Schuldenstand zum 31.12.2025:
- Schuldenstand am Jahresende 2025: 336.994.000 € — das sind 1.908 € je Einwohner*in
- Ein Jahr davor (2024): 294.851.000 €
  - davon Schulden aus Kreditmarktmitteln: 40.804.000 €
  - davon Schulden der Eigenbetriebe einschließlich Kliniken und innere Darlehen: 296.190.000 €
- Dieselbe Frage, andere Abgrenzung — Kernhaushalt (nur Geldschulden) 2024: 43.690.972 € (Quelle: Bilanz)
- Dieselbe Frage, andere Abgrenzung — Konzern Stadt (anteilig, mit Beteiligungen) 2024: 740.330.163 €
"""

INVEST_KONTEXT = """INVESTITIONEN — TATSÄCHLICH ABGEFLOSSEN, Stand Rechnungsergebnisse 2010–2025:
- Tatsächliche Investitions-Auszahlungen 2025: 60.773.000 €
- Ein Jahr davor (2024): 67.954.000 €
- Höchster Wert der Reihe (sie beginnt 2010): 2020 mit 70.481.000 €
  - davon Baumaßnahmen: 16.208.000 €
  - davon Sonstige Investitionstätigkeit: 20.083.000 €

EINZELNE VORHABEN:
- Ausleihung an Beteiligungen, 2025 (Finanzmanagement und Recht): 26,6 Mio. € — im Programm 2024 noch -5,3 Mio. €
"""


def _werte(text):
    return [(z.wert, z.art) for z in fa.zahlen(text)]


# --------------------------------------------------------------------------- #
# Zahlen lesen
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("text, wert, art", [
    ("336.994.000 €", 336_994_000, "€"),
    ("336,9 Mio. €", 336_900_000, "€"),
    ("rund 337 Millionen Euro", 337_000_000, "€"),
    ("1.908 €", 1908, "€"),
    ("20,4 %", 20.4, "%"),
    ("20,4 Prozent", 20.4, "%"),
    ("0,3 Mrd. €", 300_000_000, "€"),
    ("1,2 Milliarden", 1_200_000_000, "€"),
    ("72.600 TEUR", 72_600_000, "€"),
    ("rund 43,7 Mio €", 43_700_000, "€"),
    ("Hebesatz 539", 539, ""),
])
def test_deutsche_zahlformate(text, wert, art):
    (z,) = [z for z in fa.zahlen(text) if z.art != "jahr"]
    assert z.wert == pytest.approx(wert)
    assert z.art == art


def test_jahre_und_daten_sind_keine_betraege():
    assert _werte("Stand 31.12.2025") == [(2025, "jahr")]
    assert _werte("2010–2025") == [(2010, "jahr"), (2025, "jahr")]
    assert _werte("von 2019 bis 2024") == [(2019, "jahr"), (2024, "jahr")]


def test_minus_nur_vor_der_ziffer():
    assert _werte("noch -5,3 Mio. €") == [(-5_300_000, "€")]
    assert _werte("2010-2025") == [(2010, "jahr"), (2025, "jahr")]


def test_aufloesung_folgt_der_angabe():
    (a,) = fa.zahlen("336,9 Mio. €")
    (b,) = fa.zahlen("337 Mio. €")
    (c,) = fa.zahlen("336.994.000 €")
    assert a.aufloesung == pytest.approx(100_000)
    assert b.aufloesung == pytest.approx(1_000_000)
    assert c.aufloesung == pytest.approx(1_000)


# --------------------------------------------------------------------------- #
# Rundung
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("text, gold, erwartet", [
    ("rund 337 Millionen Euro", 336_994_000, True),
    ("336,9 Mio. €", 336_994_000, True),
    ("0,3 Mrd. €", 294_851_000, True),
    ("rund 300 Mio. €", 294_851_000, True),    # grob, aber eine Rundung
    ("295 Mio. €", 294_851_000, True),
    ("1 Mrd. €", 740_330_163, False),          # keine Rundung mehr
    ("338 Mio. €", 336_994_000, False),        # falsch gerundet
    ("20 %", 20.4, True),
    ("21 %", 20.4, False),
    ("1.908 €", 1908, True),
    ("1.900 €", 1908, True),
    ("1.800 €", 1908, False),
    # Kaufmännisch gerundet, nicht „zur geraden Ziffer“ (Pythons `round`):
    # 35.850.000 € ist „35,9 Mio. €“ — `round(358.5)` ergäbe 35,8.
    ("35,9 Mio. €", 35_850_000, True),
    ("35,8 Mio. €", 35_850_000, True),         # abgeschnitten, wie „über 336 Mio.“
    ("36,0 Mio. €", 35_850_000, False),
])
def test_rundung(text, gold, erwartet):
    (z,) = fa.zahlen(text)
    assert fa.passt(z, gold) is erwartet


def test_zwei_genaue_zahlen_nah_beieinander_sind_verschieden():
    """Gemessen am 23.09.: Der Rekordwert 2020 (70.481.000 €) galt bei 0,5 %
    Toleranz als der Investitionsplan 2026 (70.273.312 €)."""
    (z,) = fa.zahlen("70.481.000 €")
    assert not fa.passt(z, 70_273_312)
    # Zwei Quellen derselben Zahl dagegen schon (Jahrbuch / Abschluss 2024).
    (z,) = fa.zahlen("764.745.000 €")
    assert fa.passt(z, 764_416_063.76)


def test_einheiten_werden_nicht_verwechselt():
    (proz,) = fa.zahlen("20,4 %")
    (euro,) = fa.zahlen("20,4 €")
    assert not fa.einheit_passt(proz, "€")
    assert not fa.einheit_passt(euro, "%")
    (jahr,) = fa.zahlen("2025")
    assert not fa.einheit_passt(jahr, "€") and not fa.einheit_passt(jahr, "Stellen")


# --------------------------------------------------------------------------- #
# Jahreszuordnung im Kontext
# --------------------------------------------------------------------------- #

def test_davon_zeilen_unter_dem_vorjahr_sind_falsch_zugeordnet():
    """Der Befund des Faktenchecks: Die Aufschlüsselung 2025 unter „2024“."""
    b = fa.zahl_im_text({"wert": 40_804_000, "jahr": 2025, "einheit": "€"}, SCHULDEN_KONTEXT)
    assert b.status == "falsch_zugeordnet"
    assert b.jahre == [[2024]]


def test_zahl_mit_eigenem_jahr_ist_richtig_zugeordnet():
    for wert in (336_994_000, 1908):
        assert fa.zahl_im_text({"wert": wert, "jahr": 2025}, SCHULDEN_KONTEXT).status == "ok"
    assert fa.zahl_im_text({"wert": 294_851_000, "jahr": 2024}, SCHULDEN_KONTEXT).status == "ok"
    assert fa.zahl_im_text({"wert": 294_851_000, "jahr": 2025}, SCHULDEN_KONTEXT).status \
        == "falsch_zugeordnet"


def test_investitionen_unter_dem_rekordjahr():
    """Zweiter Befund: Die Auszahlungsarten 2025 unter „Höchster Wert … 2020“."""
    b = fa.zahl_im_text({"wert": 20_083_000, "jahr": 2025}, INVEST_KONTEXT)
    assert b.status == "falsch_zugeordnet" and b.jahre == [[2020]]


def test_zwei_jahre_in_einer_zeile():
    assert fa.zahl_im_text({"wert": 26_600_000, "jahr": 2025}, INVEST_KONTEXT).status == "ok"
    assert fa.zahl_im_text({"wert": 5_300_000, "jahr": 2024}, INVEST_KONTEXT).status == "ok"
    assert fa.zahl_im_text({"wert": 5_300_000, "jahr": 2025}, INVEST_KONTEXT).status \
        == "falsch_zugeordnet"


def test_leerzeile_trennt_bloecke():
    text = "Kopf 2024:\n- a: 5.000 €\n\n- b: 7.000 €"
    zl = fa.zeilen(text)
    (b,) = [z for z in fa.zahlen(text) if z.wert == 7000]
    assert fa.jahre_der_zahl(zl, b) == set()


def test_fehlt_ganz():
    assert fa.zahl_im_text({"wert": 60_773_000, "jahr": 2025}, SCHULDEN_KONTEXT).status == "fehlt"


def test_bezeichnung_muss_in_der_zeile_oder_darueber_stehen():
    gold = {"wert": 296_190_000, "label": ["Eigenbetrieb"]}
    assert fa.zahl_im_text(gold, SCHULDEN_KONTEXT).status == "ok"
    gold = {"wert": 296_190_000, "label": ["Kreditmarkt"]}
    assert fa.zahl_im_text(gold, SCHULDEN_KONTEXT).status == "falsch_zugeordnet"


# --------------------------------------------------------------------------- #
# Antworten
# --------------------------------------------------------------------------- #

def test_antwort_mit_vorjahr_im_selben_satz():
    antwort = "Ende 2025 lag der Schuldenstand bei rund 337 Mio. €, 2024 waren es 295 Mio. €."
    assert fa.zahl_im_text({"wert": 336_994_000, "jahr": 2025}, antwort, satz=True).status == "ok"
    assert fa.zahl_im_text({"wert": 294_851_000, "jahr": 2024}, antwort, satz=True).status == "ok"


def test_jahr_dahinter_nur_in_der_naehe():
    antwort = "Rund 337 Mio. € Schulden hatte die Stadt zuletzt – 2024 waren es noch 295 Mio. €."
    zl = fa.zeilen(antwort)
    z = fa.zahlen(antwort)[0]
    assert fa.jahre_der_zahl(zl, z, satz=True) == set()


def test_angehaengtes_jahr_geht_vor():
    """Gemessen 23.09. (Gemini): 850,2 Mio. galt als Wert von 2020."""
    antwort = "Von 588,2 Millionen Euro im Jahr 2020 auf 850,2 Millionen Euro im Jahr 2025."
    assert fa.zahl_im_text({"wert": 850_170_000, "jahr": 2025}, antwort, satz=True).status == "ok"
    assert fa.zahl_im_text({"wert": 588_167_000, "jahr": 2020}, antwort, satz=True).status == "ok"


def test_komma_trennt_in_antworten():
    antwort = "Die Gebühr ist 2026 um 8,0 % gestiegen, von 3,74 € auf 4,04 € je Meter."
    assert fa.zahl_im_text({"wert": 3.74, "jahr": 2025}, antwort, satz=True).status == "ok"


def test_ausgangswert_einer_veraenderung_traegt_nicht_das_neue_jahr():
    antwort = "Die Gebühr stieg 2026 um 8 Prozent: von 3,74 Euro auf 4,04 Euro je Meter."
    assert fa.zahl_im_text({"wert": 3.74, "jahr": 2025}, antwort, satz=True).status == "ok"
    assert fa.zahl_im_text({"wert": 4.04, "jahr": 2026}, antwort, satz=True).status == "ok"


def test_ausgangswert_mit_rund_traegt_nicht_das_endjahr():
    """Gemessen 24.09. (GPT-6 Luna): 269 Mio. galt als Wert von 2025."""
    antwort = ("Vom Jahresende 2020 bis zum Jahresende 2025 stieg der Schuldenstand um "
               "25,17 Prozent – von rund 269 Millionen auf rund 337 Millionen Euro.")
    assert fa.zahl_im_text({"wert": 269_230_000, "jahr": 2020}, antwort, satz=True).status == "ok"
    assert fa.zahl_im_text({"wert": 336_994_000, "jahr": 2025}, antwort, satz=True).status == "ok"


def test_elternzeile_zaehlt_ihr_erstes_jahr():
    kontext = ("- Wirtschaftsplan 2026: Ergebnis 711.250 €; im Plan 2025 waren es 627.511 €\n"
               "  - Erfolgsplan: Aufwendungen 26,0 Mio. €")
    assert fa.zahl_im_text({"wert": 26_036_000, "jahr": 2026}, kontext).status == "ok"


def test_verbot_mit_jahr_trifft_nur_die_verwechslung():
    verbot = {"art": "zahl", "wert": 294_851_000, "als_jahr": 2025, "grund": "Vorjahr"}
    richtig = "Ende 2025: 337 Mio. €. Im Jahr 2024 waren es 295 Mio. €."
    falsch = "Der Schuldenstand 2025 beträgt 295 Mio. €."
    for text, erwartet in ((richtig, None), (falsch, "295 Mio. € — Vorjahr")):
        assert fa.verboten_im_text(verbot, text, fa.zahlen(text), fa.zeilen(text)) == erwartet


@pytest.mark.parametrize("antwort, erwartet", [
    ("Die Angaben nennen keine Schuldenzahlen anderer Städte, daher kann ich nicht sagen, "
     "ob das viel ist.", True),
    ("Dazu liegen mir keine Zahlen vor.", True),
    ("Vergleichsdaten zu den Schulden anderer Städte sind nicht im Bestand.", True),
    ("Das lässt sich mit den vorhandenen Daten nicht beantworten.", True),
    ("Die Unterlagen nennen keinen Schuldenstand für Osnabrück.", True),
    ("Die Ratsunterlagen geben keine Auskunft über die Schulden von Osnabrück.", True),
    ("Die vorliegenden Unterlagen des Oldenburger Stadtrats enthalten keine Informationen.", True),
    ("Die Seite sagt nichts dazu, wie viel Braunschweig ausgibt.", True),
    ("Wer wie gestimmt hat, steht bei uns nicht.", True),
    ("Die Ratsunterlagen geben dazu wenig her.", True),
    ("Die Ratsunterlagen geben nicht her, wie viel Gewerbesteuer die EWE zahlt.", True),
    ("Die Ratsunterlagen geben keine direkte Auskunft darüber.", True),
    ("Angaben zum Gehalt stehen in den vorliegenden Informationen nicht.", True),
    ("Wie viel er verdient, geht aus den vorliegenden Unterlagen nicht hervor.", True),
    ("Ein Wolfsburger Vergleichswert fehlt.", True),
    ("Aus den Unterlagen lässt sich kein Gewinner nennen.", True),
    ("Wie viel davon auf Kredite entfiel, ist in den vorliegenden Angaben nicht aufgeschlüsselt.",
     True),
    ("Die Hundesteuer ist nicht einzeln ausgewiesen.", True),
    ("Ein Schuldenvergleich mit anderen Städten ist anhand der vorliegenden Zahlen "
     "nicht möglich.", True),
    # Recherche-Berichte, 23.09.2026: fetter Kernsatz, andere Wendungen.
    ("Aus den vorliegenden Unterlagen lässt sich **nicht feststellen, wie Christoph Baak "
     "abgestimmt hat**.", True),
    ("**Nein – in den mitgelieferten Unterlagen findet sich kein Beschluss des Rates.**", True),
    ("Ein Hebesatz für die Grundsteuer C ist in den Unterlagen nicht dokumentiert.", True),
    ("Nein – in den mitgelieferten Unterlagen ist kein Ratsbeschluss zur Einführung einer "
     "Grundsteuer C dokumentiert.", True),
    ("Dafür lässt sich aus dem vorliegenden Material kein Betrag nennen.", True),
    ("Einen entsprechenden Ist-Wert für 2026 enthalten die Unterlagen nicht.", True),
    ("Die Unterlagen enthalten die Zahl 222.117.000 Euro für 2025.", False),
    ("Die Schulden lagen Ende 2025 bei 337 Mio. €.", False),
    ("Die Stadt muss das nicht bezahlen, das trägt das Land.", False),
    ("Der Rat beschloss **am 1. Juni 2026** einstimmig den Zuschuss.", False),
])
def test_verweigerung(antwort, erwartet):
    assert fa.verweigert(antwort) is erwartet


def test_erfundene_zahl_und_abgeleitete():
    kontext = "Plan: 80.781.520 €\nIst: 60.773.000 €\nEinwohner: 176.614"
    assert fa.erfundene_zahlen("Rund 81 Mio. € geplant, 60,8 Mio. € ausgegeben.", kontext) == []
    # Differenz und Anteil sind Rechnungen aus zwei Kontextzahlen, keine Erfindung.
    assert fa.erfundene_zahlen("Das sind 20 Mio. € weniger, rund 75 %.", kontext) == []
    assert fa.erfundene_zahlen("Dazu kommen 12,5 Mio. € für Schulen.", kontext) == ["12,5 Mio. €"]


# --------------------------------------------------------------------------- #
# Die Einteilung
# --------------------------------------------------------------------------- #

FALL = {
    "id": "t", "frage": "Wie hoch sind die Schulden?", "antwort_in_daten": True,
    "gold": [{"art": "zahl", "wert": 336_994_000, "jahr": 2025, "einheit": "€"},
             {"art": "text", "muss": [["Eigenbetrieb", "Eigenbetriebe"]]}],
    "verboten": [{"art": "zahl", "wert": 294_851_000, "als_jahr": 2025, "grund": "Vorjahr"}],
}
KONTEXT_OK = SCHULDEN_KONTEXT + "\nAbgrenzung: Kernhaushalt und Eigenbetriebe."


def test_einteilung_ok():
    e = fa.bewerten(FALL, KONTEXT_OK, "Ende 2025 rund 337 Mio. € (Kernhaushalt und Eigenbetriebe).")
    assert e["fehlerart"] == "ok" and e["kontext_ok"] and e["antwort_ok"]


def test_einteilung_kontext_fehlt_geht_vor():
    e = fa.bewerten(FALL, "gar nichts", "Ende 2025 rund 337 Mio. €, Eigenbetriebe.")
    assert e["fehlerart"] == "kontext_fehlt" and not e["kontext_ok"]


def test_einteilung_modell_ausgelassen_und_falsch():
    e = fa.bewerten(FALL, KONTEXT_OK, "Die Stadt hat Schulden bei den Eigenbetrieben.")
    assert e["fehlerart"] == "modell_ausgelassen"
    e = fa.bewerten(FALL, KONTEXT_OK, "Der Schuldenstand 2025 beträgt 295 Mio. € (Eigenbetriebe).")
    assert e["fehlerart"] == "modell_falsch"


def test_einteilung_verweigert_zu_unrecht():
    e = fa.bewerten(FALL, KONTEXT_OK, "Dazu liegen mir keine Zahlen vor.")
    assert e["fehlerart"] == "modell_verweigert_zu_unrecht"


def test_einteilung_erfunden():
    e = fa.bewerten(FALL, KONTEXT_OK,
                    "Ende 2025 rund 337 Mio. €, Eigenbetriebe; dazu 12,5 Mio. € Kassenkredite.")
    assert e["fehlerart"] == "modell_erfunden" and e["erfunden"] == ["12,5 Mio. €"]


def test_einteilung_ohne_modellaufruf():
    e = fa.bewerten(FALL, None, "Auf dieser Seite siehst du den Schuldenstand.")
    assert e["fehlerart"] == "kontext_fehlt"


def test_einteilung_antwort_nicht_in_daten():
    fall = {"frage": "Wie hoch sind die Schulden von Osnabrück?", "antwort_in_daten": False,
            "gold": [], "verboten": []}
    kontext = "Steuerkraftmesszahl 2026: Oldenburg 348.164.000 €, Osnabrück 273.609.000 €"
    assert fa.bewerten(fall, kontext, "Dazu liegen mir keine Zahlen vor.")["fehlerart"] == "ok"
    # Ersatzweise die Steuerkraft zu nennen, ohne zu sagen, dass es keine
    # Schulden sind, ist der Befund des Faktenchecks (Gemini, rat[1]).
    e = fa.bewerten(fall, kontext, "Osnabrück liegt bei 273,6 Mio. €.")
    assert e["fehlerart"] == "modell_falsch"
    e = fa.bewerten(fall, kontext, "Osnabrück hat rund 512 Mio. € Schulden.")
    assert e["fehlerart"] == "modell_erfunden"


def test_frage_zaehlt_nicht_als_kontext():
    fall = {"frage": "Was macht der Eigenbetrieb?", "gold": [{"art": "text", "muss": ["Eigenbetrieb"]}]}
    e = fa.bewerten(fall, "System: …\nFrage: Was macht der Eigenbetrieb?", "Der Eigenbetrieb …")
    assert e["fehlerart"] == "kontext_fehlt"


def test_optionaler_fakt_zaehlt_nur_im_kontext():
    fall = {**FALL, "gold": FALL["gold"] + [
        {"art": "zahl", "wert": 740_330_163, "jahr": 2024, "pflicht": False}]}
    e = fa.bewerten(fall, KONTEXT_OK, "Ende 2025 rund 337 Mio. € (Eigenbetriebe).")
    assert e["fehlerart"] == "ok"


# --- Datumsgold: Monat und Jahr genügen, wo die Frage nicht nach dem Tag fragt
#
# Messung 23.09.2026 (#1494/#1499): „Was wurde hier zuletzt beschlossen?“ mit
# „Im Juni 2026 …“ beantwortet zählte als Auslassung, weil das Gold
# „01.06.2026“ verlangte. `antwort_auch` lässt die gröbere Angabe in der
# ANTWORT gelten — im Kontext bleibt das genaue Datum Pflicht.

DATUM_GOLD = {"art": "text", "muss": [["01.06.2026", "1. Juni 2026", "2026-06-01"]],
              "antwort_auch": ["Juni 2026"]}


def test_monat_und_jahr_reichen_in_der_antwort():
    assert fa.gold_im_text(DATUM_GOLD, "Im Juni 2026 hat der Rat das beschlossen.",
                           satz=True).status == "ok"


def test_monat_und_jahr_reichen_im_kontext_nicht():
    """Sonst stünde jeder Beschluss aus dem Juni für diesen einen."""
    assert fa.gold_im_text(DATUM_GOLD, "Rat, Juni 2026: Bebauungsplan 851").status == "fehlt"


def test_ohne_antwort_auch_bleibt_der_tag_pflicht():
    gold = {k: v for k, v in DATUM_GOLD.items() if k != "antwort_auch"}
    assert fa.gold_im_text(gold, "Im Juni 2026 …", satz=True).status == "fehlt"


# --- Ausgeschriebene kleine Zahlen -----------------------------------------
#
# GPT-6 Luna, 23.09.2026: „es gab fünf Gegenstimmen“, „bei neun
# Enthaltungen“ — beide richtig, beide als Auslassung gezählt.

def test_ausgeschriebene_zahl_zaehlt():
    gold = {"art": "zahl", "wert": 5, "einheit": "Gegenstimmen"}
    assert fa.gold_im_text(gold, "Mehrheitlich angenommen; es gab fünf Gegenstimmen.",
                           satz=True).status == "ok"


def test_ein_artikel_ist_keine_zahl():
    assert [z.wert for z in fa.zahlen("Ein Beschluss, eine Enthaltung.", woerter=True)] == []


def test_im_kontext_zaehlen_nur_ziffern():
    """Ein „neun“ aus einem fremden Protokollsatz soll den Goldfakt nicht im
    falschen Beschluss finden."""
    assert fa.zahlen("einstimmig bei neun Enthaltungen") == []


def test_ausgeschriebene_zahl_ist_nie_ein_erfundener_betrag():
    assert fa.erfundene_zahlen("Es gab neun Enthaltungen.", "Kontext ohne Zahl") == []


def test_das_vielfache_gilt_fuer_beide_zahlen():
    """„von 50 auf höchstens 79 Millionen Euro“ nennt zwei Beträge (Luna, 23.09.)."""
    gold = {"art": "zahl", "wert": 50_000_000, "einheit": "€"}
    antwort = "Die Bürgschaft wurde von 50 auf höchstens 79 Millionen Euro erhöht."
    assert fa.gold_im_text(gold, antwort, satz=True).status == "ok"


def test_eine_nackte_zahl_ohne_bindewort_bleibt_nackt():
    werte = [z.wert for z in fa.zahlen("Im Jahr 50 v. Chr. kostete es 79 Millionen Euro.")]
    assert 50_000_000 not in werte


def test_nicht_genannt_ist_eine_absage():
    assert fa.verweigert("Die Einwohnerzahl von Bloherfelde ist in den hier vorliegenden "
                         "Angaben nicht genannt.")


# --- Verbot mit Ausnahme: dieselbe Zahl, richtig benannt ---------------------
#
# `rat-kongresshalle-kosten`: Die Ausfallbürgschaft (79 Mio. €) als Baupreis
# ist die Verwechslung; als Bürgschaft genannt ist sie richtig — und traf bis
# 23.09.2026 trotzdem (Gemini, zwei Läufe, `modell_falsch`).

VERBOT_79 = {"art": "zahl", "wert": 79_000_000, "grund": "Bürgschaft, nicht Baupreis",
             "ausser_im_satz_mit": ["Bürgschaft", "bürgt"]}


def _verstoss(antwort: str) -> str | None:
    return fa.verboten_im_text(VERBOT_79, antwort, fa.zahlen(antwort), fa.zeilen(antwort))


def test_die_buergschaft_als_buergschaft_ist_kein_verstoss():
    # Wortlaut der Gemini-Antwort vom 23.09.2026 (gekürzt).
    assert _verstoss("Der Neubau kostet rund 78,68 Millionen Euro netto [7911]. Zur "
                     "Finanzierung wurde die städtische Ausfallbürgschaft von 50 Millionen "
                     "Euro auf maximal 79 Millionen Euro erhöht [7912].") is None


def test_die_buergschaft_als_baupreis_bleibt_ein_verstoss():
    assert _verstoss("Die Kongresshalle kostet 79 Mio. Euro. Die Bürgschaft ist ein "
                     "eigener Beschluss.") is not None


def test_die_andere_buergschaft_als_andere_genannt_ist_kein_verstoss():
    """`rat-kongresshalle-buergschaft`: GPT-6 Sol nannte die 16,9 Mio. € der
    Kramermarktfläche ausdrücklich als ANDERES Vorhaben (23.09.2026)."""
    faelle = json.loads((WURZEL / "eval" / "cases_fakten_rat.json").read_text(encoding="utf-8"))
    (verbot,) = next(f for f in faelle if f["id"] == "rat-kongresshalle-buergschaft")["verboten"]
    richtig = ("Für dessen Sanierung erhöhte der Rat im Februar 2026 eine Ausfallbürgschaft von "
               "12 auf 16,9 Millionen Euro. Diese 16,9 Millionen Euro sind nicht Teil der hier "
               "erfragten Neubau-Bürgschaft.")
    falsch = "Die Stadt bürgt für die Kongresshalle mit 16,9 Millionen Euro."
    assert fa.verboten_im_text(verbot, richtig, fa.zahlen(richtig), fa.zeilen(richtig)) is None
    assert fa.verboten_im_text(verbot, falsch, fa.zahlen(falsch), fa.zeilen(falsch)) is not None


def test_die_jahresreihe_ist_keine_jahresfalle():
    """`rat-btb-zuschuss-2027`: Die Beträge der anderen Jahre dürfen genannt
    werden — nur nicht als der für 2027."""
    faelle = json.loads((WURZEL / "eval" / "cases_fakten_rat.json").read_text(encoding="utf-8"))
    verbote = next(f for f in faelle if f["id"] == "rat-btb-zuschuss-2027")["verboten"]
    reihe = ("Für 2027 ist ein maximaler Zuschuss von 177.500 Euro ausgewiesen, 191.000 Euro "
             "2030. Für 2026 nennt die Vorlage 173.000 Euro.")
    falsch = "Im Jahr 2027 bekommt der BTB 173.000 Euro."
    assert not [v for v in verbote if fa.verboten_im_text(v, reihe, fa.zahlen(reihe), fa.zeilen(reihe))]
    assert [v for v in verbote if fa.verboten_im_text(v, falsch, fa.zahlen(falsch), fa.zeilen(falsch))]


def test_zum_jahresende_haengt_das_jahr_an():
    """GPT-6 Sol, 23.09.2026: „von 211.503.000 Euro zum Jahresende 2015 auf
    336.994.000 Euro zum Jahresende 2025“ — die zweite Zahl gehört zu 2025."""
    t = "stieg von 211.503.000 Euro zum Jahresende 2015 auf 336.994.000 Euro zum Jahresende 2025."
    zl = fa.zeilen(t)
    jahre = {z.wert: fa.jahre_der_zahl(zl, z, satz=True) for z in fa.zahlen(t) if z.art == "€"}
    assert jahre[336_994_000] == {2025}
    # Der Ausgangswert („von … auf“) trägt nach der bestehenden Regel gar kein
    # Jahr — das ist unscharf, nicht falsch.
    assert 2025 not in jahre[211_503_000]


def test_ein_abgeschnittenes_mil_ist_millionen():
    """Die Presse-Auszüge im Prompt enden mitten im Wort („57,3 Mil“) — wer
    „57,3 Millionen Euro“ daraus macht, erfindet nichts."""
    kontext = "Pauschalfestpreis von 57,3 Mil\nNÄCHSTER BLOCK"
    assert fa.erfundene_zahlen("Der Festpreis beträgt 57,3 Millionen Euro.", kontext) == []
    assert fa.zahlen("rund 57,3 Millimeter")[0].wert == 57.3


def test_eine_abkuerzung_beendet_den_satz_nicht():
    """„50 Mio. Euro auf 79 Mio. Euro“ ist EIN Satz — sonst fiele das Wort
    „Bürgschaft“ vor der ersten Zahl aus dem Satz der zweiten."""
    assert _verstoss("Die Bürgschaft stieg von 50 Mio. Euro auf 79 Mio. Euro.") is None
