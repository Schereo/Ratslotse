"""Die Gebührenbedarfsberechnung — zwei Proben je Block, aus dem Dokument selbst.

Die Ausschnitte sind **echt**, aus den Anlagen 269066 (Jahrgang 2024),
283467 (2025) und 299051 (2026) — samt der drei Eigenheiten, die dieses Modul
überhaupt nötig machen:

* Zahlen zerreißen im Textextrakt an Leerzeichen („-295. 000 €", „7 71.000"),
* im Jahrgang 2024 stehen erst alle Beträge und danach erst ihre
  Beschriftungen,
* und die Abfallsammlung hat gar keine einzelne Gebühr.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from council.fees import (  # noqa: E402
    PROBE_DIVISION,
    PROBE_KASKADE,
    PROBE_SATZANZAHL,
    PROBE_VORJAHRESVERGLEICH,
    GebuehrenFehler,
    herkunft_fuer,
    herkunft_fuer_satz,
    lies,
    lies_gebuehrensaetze,
    parse_anlage,
    teile_anlagen,
)
from council.store import CouncilStore  # noqa: E402

# Echt, Anlage 283467 (2025). Beschriftung und Betrag stehen nebeneinander.
ANLAGE_1_2025 = """Anlage 1
- Abfallbehandlungsanlagen -
(Entsorgung von Rest- und Bioabfällen)
Gebührenbedarfsberechnung  2025
Kostenkalkulation für 2025       11.661.361 €
Kosten, die durch Dritte erstattet werden   -3.668.314 € Tz. 1
Erlöse nach § 2 Absatz 4 und 8 der Abfallgebührensatzung -5.000 € Tz. 2
Nachsorgekosten, die aus der Rückstellung erstattet werden -240.000 € Tz. 3
Gebührenwirksame Kosten         7.748.047 €
Über-/Unterdeckung aus Vorjahren   -361.777 € Tz. 4
Kosten, die durch Gebühren zu decken sind          7.386.270 €
angelieferte Jahresabfallmenge in Mg   52.845  Tz. 5
Gebührenermittlung:
Kosten, die durch Gebühren zu decken sind         7.386.270 €
angelieferte Abfallmenge in Mg  52.845
Ergebnis/Gebühr je Mg             139,772 €
Gebührenvorschlag 139,70 €
"""

# Echt, Anlage 299051 (2026): „-295. 000 €" mit Leerzeichen in der Zahl.
ANLAGE_1_2026 = """Anlage 1
- Abfallbehandlungsanlagen -
Gebührenbedarfsberechnung  2026
Kostenkalkulation für 2026 12.555.550 €
Kosten, die durch Dritte erstattet werden -3.731.300 € Tz. 1
Erlöse nach § 2 Absatz 4 und 8 der Abfallgebührensatzung -6.500 € Tz. 2
Nachsorgekosten, die aus der Rückstellung erstattet werden -295. 000 € Tz. 3
Gebührenwirksame Kosten 8.522.750 €
Über-/Unterdeckung aus Vorjahren -359.470 € Tz. 4
Kosten, die durch Gebühren zu decken sind 8.163.280 €
angelieferte Jahresabfallmenge in Mg 53.985 Tz. 5
Gebührenermittlung:
Kosten, die durch Gebühren zu decken sind 8.163.280 €
angelieferte Abfallmenge in Mg 53.985
Ergebnis/Gebühr je Mg 151,214 €
Gebührenvorschlag 151,21 €
"""

# Echt, Anlage 269066 (2024): ERST die Beträge, DANN die Beschriftungen.
ANLAGE_1_2024 = """Anlage 1
- Abfallbehandlungsanlagen -
(Entsorgung von Rest- und Bioabfällen)
10.901.750 €
-3.525.453 € Tz. 1
-6.000 € Tz. 2
-222.500 € Tz. 3
7.147.797 €
-250.680 € Tz. 4
6.897.117 €
51.200 Tz. 5
6.897.117 €
51.200
134,709 €
Gebührenbedarfsberechnung  2024
Kostenkalkulation für 2024
Kosten, die durch Dritte erstattet werden
Gebührenwirksame Kosten
Über-/Unterdeckung aus Vorjahren
Kosten, die durch Gebühren zu decken sind
angelieferte Jahresabfallmenge in Mg
Ergebnis/Gebühr je Mg
Gebührenvorschlag 134,70 €
"""

# Echt, Anlage 299051 (2026): „7 71.000" — zerrissen an anderer Stelle.
ANLAGE_3_2026 = """Anlage 3
- Straßenreinigung -
Gebührenbedarfsberechnung  2026
Kostenkalkulation für 2026 6.189.369 €
Kosten, die durch Dritte erstattet werden -1.903.600 € Tz. 1
Bereinigte Kosten 4.285.769 €
Interessenquote -1.071.442 € Tz. 2
Gebührenwirksame Kosten 3.214.327 €
Über-/Unterdeckung aus Vorjahren -100.000 € Tz. 3
Kosten, die durch Gebühren zu decken sind 3.114.327 €
Summe aller gebührenpflichtigen Quadratwurzeln gem. 7 71.000
Gebührenermittlung:
Kosten, die durch Gebühren zu decken sind 3.114.327 €
Summe aller gebührenpflichtigen Quadratwurzeln gem. 7 71.000
Gebühr  rd. je Meter Quadratwurzel 4,039 €
Gebührenvorschlag je Meter Quadratwurzel 4,04 €
"""

# Echt, Anlage 299051 (2026): vier Stufen, KEINE einzelne Gebühr.
ANLAGE_2_2026 = """Anlage 2
- Abfallsammlung -
Gebührenbedarfsberechnung  2026
Kostenkalkulation für 2026 17.892.020 €
Kosten, die durch Dritte erstattet werden -809.300 € Tz. 1
Bereinigte Kosten 17.082.720 €
Erlöse aus der Biotonne und Sperr- und Grüngutabfuhr -1.290.700 € Tz. 2
Erlöse aus Biogrundmengenpauschale -628.800 € Tz. 3
Bereinigte Kosten 15.163.220 €
Über-/Unterdeckung aus Vorjahren -1.401.208 € Tz. 4
Kosten, die durch Gebühren zu decken sind 13.762.012 €
bereitgestelltes Behältervolumen (14 - täglich) für:
35 - 240 l Behälter 6.300.000 l
400 - 1100 l Behälter 2.000.000 l
Behältervolumen total 8.300.000 l
"""

ANLAGE_3_2025 = """Anlage 3
- Straßenreinigung -
Gebührenbedarfsberechnung 2025
Kostenkalkulation für 2025 4.000 €
Interessenquote -260 €
Kosten, die durch Gebühren zu decken sind 3.740 €
Summe aller gebührenpflichtigen Quadratwurzeln 1.000
Gebühr je Meter Quadratwurzel 3,740 €
Gebührenvorschlag je Meter Quadratwurzel 3,74 €
"""

# Echt, Anlage 283467 (2025): das alte Layout bündelt zwölf Sätze in einer
# Zeile. Schrägstriche teilen die fünf gestaffelten Anlieferungstarife.
ANLAGE_4_2025 = """Anlage 4
Entwicklung abfallwirtschaftlicher Gebühren im langfristigen Vergleich
Jahr Gebühr je Mg GG allg. Litergebühr BioGrundmenge 60 L Sperrmüllkarte
Grüngutkarte Sperrmüllanlieferung 1m³/2m³
Grüngutanlieferung bis 0,5m³/1m³/2m³
Gebühr je m bei wöchentlicher Reinigung
Vorschläge 2025 139,70 50,-- 1,34 15,-- 25,-- 20,-- 8,--/16,--
3,--/6,--/12,-- 3,74
"""

# Echt, Anlage 299051 (2026), auf die für die Probe nötigen ersten beiden
# Jahresspalten gekürzt. Das neue Layout rechnet jede Veränderung selbst vor.
ANLAGE_4_2026 = """Anlage 4 Stand: 27.10.2025
KTR Bezeichnung Gebühr Veränderung in % (ggü. Vorjahr) Vorschlag 2026 2025
AB Gebühr je Mg 8,24% 151,21 € 139,70 €
AS Grundgebühr 24,00% 62,00 € 50,00 €
AS Allg. Litergebühr 0,00% 1,34 € 1,34 €
AS Biogrundmenge 60 L 0,00% 15,00 € 15,00 €
AS Sperrmüllkarte 0,00% 25,00 € 25,00 €
AS Grüngutkarte 0,00% 20,00 € 20,00 €
AS Sperrmüllanlieferung 1m³ 0,00% 8,00 € 8,00 €
AS Sperrmüllanlieferung 2m³ 0,00% 16,00 € 16,00 €
AS Grüngutanlieferung bis 0,5m³ 0,00% 3,00 € 3,00 €
AS Grüngutanlieferung bis 1m³ 0,00% 6,00 € 6,00 €
AS Grüngutanlieferung bis 2m³ 0,00% 12,00 € 12,00 €
SR Gebühr je Meter Quadratwurzel 8,02% 4,04 € 3,74 €
"""


# --------------------------------------------------------------------------
# (a) Die Kaskade
# --------------------------------------------------------------------------

def test_die_kaskade_geht_auf():
    """Kalkulation minus alle Abzüge ergibt die zu deckenden Kosten.

    Die Zwischensummen („Gebührenwirksame Kosten") fallen von allein heraus:
    Sie sind positiv, die Abzüge negativ. Ihre Namen wechseln zwischen den
    drei Bereichen — an ihnen zu hängen hieße, drei Vokabulare zu pflegen."""
    b = parse_anlage(teile_anlagen(ANLAGE_1_2025)[0])
    assert b.cost_calculation == 11_661_361.0
    assert b.deductions == -(3_668_314 + 5_000 + 240_000 + 361_777)
    assert b.costs_to_cover == 7_386_270.0


def test_eine_verstellte_zahl_faellt_durch():
    kaputt = ANLAGE_1_2025.replace("-240.000 €", "-250.000 €")
    with pytest.raises(GebuehrenFehler) as fehler:
        parse_anlage(teile_anlagen(kaputt)[0])
    assert "Rest" in str(fehler.value)


def test_ein_euro_rundung_reisst_nicht():
    """Zwei der elf geprüften Kaskaden gehen um genau 1 € daneben — das
    Dokument rundet seine Abzüge. Dieselbe Signatur wie beim Erfolgsplan."""
    knapp = ANLAGE_1_2025.replace("7.386.270 €", "7.386.271 €")
    b = parse_anlage(teile_anlagen(knapp)[0])
    assert b.costs_to_cover == 7_386_271.0


def test_positive_ueberdeckung_wird_nur_bei_exakter_kaskade_abgezogen():
    """2020 druckt die Überdeckung ohne Minuszeichen, zieht sie aber ab.

    Der Parser darf das nicht blind aus dem Wort ableiten: Der Betrag wird nur
    umgedreht, weil er exakt die Lücke zwischen gebührenwirksamen und zu
    deckenden Kosten schließt.
    """
    text = """
    Anlage 1 - Abfallbehandlungsanlagen - Gebührenbedarfsrechnung 2020
    Kostenkalkulation für 2020 9.761.550 €
    Kosten, die durch Dritte erstattet werden - 2.881.800 €
    Erlöse - 3.000 €
    Nachsorgekosten - 168.200 €
    Gebührenwirksame Kosten 6.708.550 €
    Über-/Unterdeckung aus Vorjahren 280.500 €
    Kosten, die durch Gebühren zu decken sind 6.428.050 €
    Ergebnis/Gebühr je Mg 121,974 €
    angelieferte Abfallmenge in Mg 52.700
    Gebührenvorschlag 121,95 €
    """
    b = parse_anlage(text)
    assert b.year == 2020
    assert b.deductions == -(2_881_800 + 3_000 + 168_200 + 280_500)
    assert b.costs_to_cover == 6_428_050
    assert b.fee == 121.974 and b.reference_quantity == 52_700

    kaputt = text.replace("280.500 €", "280.400 €")
    with pytest.raises(GebuehrenFehler, match="Rest"):
        parse_anlage(kaputt)


# --------------------------------------------------------------------------
# (b) Die Division — und wie sie die Bezugsmenge findet
# --------------------------------------------------------------------------

def test_die_division_geht_auf():
    b = parse_anlage(teile_anlagen(ANLAGE_1_2025)[0])
    assert b.reference_quantity == 52_845
    assert b.reference_unit == "Mg"
    assert b.fee == 139.772
    assert abs(b.costs_to_cover / b.reference_quantity - b.fee) < 0.001
    assert b.fee_proposed == 139.70


def test_zerrissene_zahl_mit_leerzeichen_nach_dem_punkt():
    """„-295. 000 €" — hier IST entscheidbar, dass die Zahl weitergeht:
    vor dem Punkt eine Ziffer, dahinter genau drei."""
    b = parse_anlage(teile_anlagen(ANLAGE_1_2026)[0])
    assert b.deductions == -(3_731_300 + 6_500 + 295_000 + 359_470)
    assert b.costs_to_cover == 8_163_280.0


def test_zerrissene_menge_wird_an_der_gebuehr_erkannt():
    """„7 71.000" für 771.000 — hier ist NICHT entscheidbar, wo die Zahl
    anfängt. Erkannt wird sie daran, dass sie die gedruckte Gebühr ergibt:
    3.114.327 ÷ 771.000 = 4,039."""
    b = parse_anlage(teile_anlagen(ANLAGE_3_2026)[0])
    assert b.reference_quantity == 771_000
    assert b.reference_unit == "Meter Quadratwurzel"
    assert b.fee == 4.039


def test_ohne_passende_menge_wird_nichts_gespeichert():
    ohne = ANLAGE_1_2025.replace("52.845", "99.999")
    with pytest.raises(GebuehrenFehler) as fehler:
        parse_anlage(teile_anlagen(ohne)[0])
    assert "Division" in str(fehler.value)


# --------------------------------------------------------------------------
# (c) Der Jahrgang mit getrennten Blöcken
# --------------------------------------------------------------------------

def test_beschriftungen_und_betraege_getrennt():
    """Im Jahrgang 2024 legt der Textextrakt erst alle Zahlen der Anlage und
    danach erst ihre Zeilennamen. Ein Muster, das die Zahl neben ihrer
    Beschriftung sucht, findet dort nichts — die Zuordnung kommt aus der
    Reihenfolge und gilt nur, weil sie die Kaskade erfüllt."""
    b = parse_anlage(teile_anlagen(ANLAGE_1_2024)[0])
    assert b.cost_calculation == 10_901_750.0
    assert b.costs_to_cover == 6_897_117.0
    assert b.reference_quantity == 51_200
    assert b.fee == 134.709


def test_nicht_der_gerundete_vorschlag():
    """Die errechnete Gebühr hat drei Nachkommastellen (134,709), der
    Vorschlag zwei (134,70). Wer den Vorschlag nimmt, speichert eine Zahl,
    die die Division nicht erfüllt."""
    b = parse_anlage(teile_anlagen(ANLAGE_1_2024)[0])
    assert b.fee == 134.709
    assert b.fee_proposed == 134.70


def test_die_einheit_wird_nicht_erfunden():
    """Im Jahrgang 2024 steht zwischen „je Mg" und der Zahl das Wort
    „Gebührenvorschlag" — ein freier Text als Einheit stünde so in der
    Datenbank."""
    b = parse_anlage(teile_anlagen(ANLAGE_1_2024)[0])
    assert b.reference_unit == "Mg"


# --------------------------------------------------------------------------
# (d) Der Bereich ohne einzelne Gebühr
# --------------------------------------------------------------------------

def test_abfallsammlung_hat_keine_division():
    """Sie erhebt eine Grundgebühr UND eine Gebühr je Liter Behältervolumen.
    Eine Division „Kosten ÷ Menge" gibt es dort nicht, und eine erfundene
    wäre schlimmer als keine. Die Kaskade ist trotzdem geprüft."""
    b = parse_anlage(teile_anlagen(ANLAGE_2_2026)[0])
    assert b.area == "abfallsammlung"
    assert b.costs_to_cover == 13_762_012.0
    assert b.fee is None and b.reference_quantity is None


def test_die_herkunft_nennt_nur_die_gelaufenen_proben():
    ohne_division = parse_anlage(teile_anlagen(ANLAGE_2_2026)[0])
    h = herkunft_fuer(ohne_division, url=None, document_id=299051, label="x")
    assert PROBE_KASKADE in h.probe and PROBE_DIVISION not in h.probe

    mit = parse_anlage(teile_anlagen(ANLAGE_1_2025)[0])
    h2 = herkunft_fuer(mit, url=None, document_id=283467, label="x")
    assert PROBE_KASKADE in h2.probe and PROBE_DIVISION in h2.probe
    assert "÷" in h2.probe_result


# --------------------------------------------------------------------------
# (e) Mehrere Anlagen in einem Dokument
# --------------------------------------------------------------------------

def test_ein_gerissener_bereich_nimmt_die_anderen_nicht_mit():
    kaputt = ANLAGE_1_2025.replace("-240.000 €", "-250.000 €")
    gelesen, risse = lies(kaputt + ANLAGE_2_2026)
    assert [b.area for b in gelesen] == ["abfallsammlung"]
    assert len(risse) == 1


def test_die_drei_bereiche_werden_getrennt():
    gelesen, risse = lies(ANLAGE_1_2026 + ANLAGE_2_2026 + ANLAGE_3_2026)
    assert not risse
    assert [b.area for b in gelesen] == [
        "abfallbehandlung", "abfallsammlung", "strassenreinigung"]
    assert {b.year for b in gelesen} == {2026}


# --------------------------------------------------------------------------
# (f) Anlage 4 — konkrete Tarife
# --------------------------------------------------------------------------

def test_altes_layout_liefert_zwoelf_benannte_tarife():
    saetze = lies_gebuehrensaetze(
        ANLAGE_1_2025 + ANLAGE_3_2025 + ANLAGE_4_2025, "24/0999")
    assert len(saetze) == 12
    assert {s.year for s in saetze} == {2025}
    assert next(s for s in saetze if s.schluessel == "grundgebuehr").amount == 50
    assert next(s for s in saetze if s.schluessel == "litergebuehr").amount == 1.34
    assert next(s for s in saetze if s.schluessel == "sperrmuell_2m3").amount == 16
    assert next(s for s in saetze if s.schluessel == "gruengut_05m3").amount == 3


def test_neues_layout_prueft_jede_aenderung_gegen_das_vorjahr():
    saetze = lies_gebuehrensaetze(
        ANLAGE_1_2026 + ANLAGE_3_2026 + ANLAGE_4_2026, "25/0999")
    grund = next(s for s in saetze if s.schluessel == "grundgebuehr")
    assert len(saetze) == 12
    assert (grund.amount, grund.prior_year, grund.change_pct) == (62, 50, 24)

    kaputt = ANLAGE_4_2026.replace("24,00%", "23,00%")
    with pytest.raises(GebuehrenFehler, match="ergeben 24.00 %"):
        lies_gebuehrensaetze(ANLAGE_1_2026 + ANLAGE_3_2026 + kaputt)


def test_tarifzeile_und_eckwerte_duerfen_nicht_unbemerkt_fehlen():
    ohne_karte = ANLAGE_4_2026.replace(
        "AS Sperrmüllkarte 0,00% 25,00 € 25,00 €", "")
    with pytest.raises(GebuehrenFehler, match="Sperrmüllkarte"):
        lies_gebuehrensaetze(ANLAGE_1_2026 + ANLAGE_3_2026 + ohne_karte)

    falscher_eckwert = ANLAGE_4_2025.replace("139,70 50,--", "139,80 50,--")
    with pytest.raises(GebuehrenFehler, match="eigene Bedarfsberechnung"):
        lies_gebuehrensaetze(ANLAGE_1_2025 + ANLAGE_3_2025 + falscher_eckwert)


def test_tarife_werden_mit_eigener_fundstelle_gespeichert(tmp_path):
    saetze = lies_gebuehrensaetze(
        ANLAGE_1_2026 + ANLAGE_3_2026 + ANLAGE_4_2026, "25/0999")
    herkuenfte = [herkunft_fuer_satz(
        s, url="https://example.org/299051", document_id=299051,
        label="Gebührenbedarfsberechnung 2026") for s in saetze]
    assert PROBE_SATZANZAHL in herkuenfte[0].probe
    assert PROBE_VORJAHRESVERGLEICH in herkuenfte[0].probe

    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        assert store.save_gebuehrensaetze(saetze, herkuenfte) == 12
        rows = store.get_gebuehrensaetze()
        assert len(rows) == 12
        assert all(r["herkunft_id"] for r in rows)
        assert store.herkunft_luecken() == {}
    finally:
        store.close()
