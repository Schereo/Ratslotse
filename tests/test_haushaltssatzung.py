"""Die Haushaltssatzung — der Rahmen, den der Haushaltsplan bekommt.

Die Ausschnitte sind **echt**, aus den Anlagen 271310 (Haushaltssatzung 2024),
212186 (2020, ältere Schreibweise „EUR") und 218588 (Nachtrag 2020) — samt
ihrer Eigenheiten: der „Nachrichtlich"-Zeile, die diese Schicht überhaupt erst
prüfbar macht, und dem Verwaltungsentwurf, der als solcher kenntlich bleiben
muss.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from council.haushaltssatzung import (  # noqa: E402
    PROBE_FINANZHAUSHALT,
    PROBE_HEBESATZ,
    SatzungFehler,
    herkunft_fuer,
    parse_satzung,
)

# Echt, Anlage 271310. Beträge mit „Euro", Grundsteuer noch in § 5.
SATZUNG_2024 = """ Haushaltssatzung
2024
Verwaltungsentwurf
Stadt Oldenburg (Oldb)
Haushaltssatzung
der Stadt Oldenburg (Oldb) für das Haushaltsjahr 2024
Aufgrund des § 112 des Niedersächsischen Kommunalverfassungsgesetzes (NKomVG)
hat der Rat der Stadt Oldenburg (Oldb) in der Sitzung am xx.xx.2023 folgende
Haushaltssatzung beschlossen:
§ 1
Der Haushaltsplan für das Haushaltsjahr 2024 wird
1. im Ergebnishaushalt mit dem jeweiligen Gesamtbetrag
1.1 der ordentlichen Erträge auf 695.625.370 Euro
1.2 der ordentlichen Aufwendungen auf 723.467.364 Euro
1.3 der außerordentlichen Erträge auf 3.526.500 Euro
1.4 der außerordentlichen Aufwendungen auf 685.500 Euro
2. im Finanzhaushalt mit dem jeweiligen Gesamtbetrag
2.1 der Einzahlungen aus laufender Verwaltungstätigkeit 677.844.544 Euro
2.2 der Auszahlungen aus laufender Verwaltungstätigkeit 674.591.036 Euro
2.3 der Einzahlungen für Investitionstätigkeit 18.802.000 Euro
2.4 der Auszahlungen für Investitionstätigkeit 107.770.867 Euro
2.5 der Einzahlungen für Finanzierungstätigkeit 0 Euro
2.6 der Auszahlungen für Finanzierungstätigkeit 2.903.100 Euro
festgesetzt.
Nachrichtlich:  Gesamtbetrag der Einzahlungen des Finanzhaushaltes 696.646.544 Euro
Gesamtbetrag der Auszahlungen des Finanzhaushaltes 785.265.003 Euro
§ 2
Kredite für Investitionen und Investitionsförderungsmaßnahmen werden nicht veranschlagt.
§ 3
Der Gesamtbetrag der Verpflichtungsermächtigungen wird auf 28.202.400 Euro festgesetzt.
§ 4
Der Höchstbetrag, bis zu dem im Haushaltsjahr 2024 Liquiditätskredite zur rechtzeitigen Leistung
von Auszahlungen in Anspruch genommen werden dürfen, wird auf 100.000.000 Euro festgesetzt.
§ 5
Die Steuersätze (Hebesätze) für die Realsteuern werden für das Haushaltsjahr 2024 wie folgt
festgesetzt:
1. Grundsteuer
1.1 für die land- und forstwirtschaftlichen Betriebe
     (Grundsteuer A) 390 v. H.
1.2 für die Grundstücke
     (Grundsteuer B) 445 v.H.
2. Gewerbesteuer 439 v.H.
"""

# Echt, Anlage 212186. Beträge mit „EUR" — die Falle der älteren Jahrgänge.
SATZUNG_2020_EUR = SATZUNG_2024.replace("Euro", "EUR").replace("2024", "2020")

# Echt, Anlage 218588 — ganz andere Tabelle.
NACHTRAG = """Aufgrund des § 115 des Niedersächsischen Kommunalverfassungsgesetzes (NKomVG)
hat der Rat der Stadt Oldenburg (Oldb) in der Sitzung am xx.xx.2020 folgende
Nachtragshaushaltssatzung beschlossen:
Mit dem Nachtragshaushaltsplan werden die bisherigen festgesetzten Gesamtbeträge
erhöht um vermindert um Gesamtbetrag
ordentliche Erträge 588.790.868 2.731.100 591.521.968
für das Haushaltsjahr 2020
"""


# --------------------------------------------------------------------------
# (a) Die Probe, die diese Schicht trägt
# --------------------------------------------------------------------------

def test_die_satzung_prueft_sich_selbst():
    """Drei Einzahlungszeilen ergeben die „Nachrichtlich"-Summe darunter.

    Das ist der einzige Grund, dass diese Schicht ohne Zweitquelle auskommt:
    Zwei unabhängig gesetzte Stellen desselben Dokuments."""
    s = parse_satzung(SATZUNG_2024)
    assert s.in_operating + s.in_capital + s.in_financing == s.in_total
    assert s.out_operating + s.aus_invest + s.out_financing == s.out_total
    assert s.in_total == 696_646_544.0
    assert s.out_total == 785_265_003.0


def test_eine_verstellte_zahl_faellt_durch():
    """Cent-genau, keine Toleranz: Die Satzung führt volle Euro, und ihre
    eigene Summe ging in allen acht Jahrgängen exakt auf. Eine Toleranz wäre
    hier kein Schutz, sondern ein blinder Fleck."""
    kaputt = SATZUNG_2024.replace("18.802.000 Euro", "18.802.001 Euro")
    with pytest.raises(SatzungFehler) as fehler:
        parse_satzung(kaputt)
    assert "widersprechen sich" in str(fehler.value)


def test_ohne_nachrichtlich_wird_nichts_gespeichert():
    """Ohne die Summenzeile prüft diese Schicht nichts nach — und eine
    ungeprüfte Zahl kommt nicht in den Bestand."""
    ohne = SATZUNG_2024.replace("Nachrichtlich:  Gesamtbetrag der Einzahlungen "
                                "des Finanzhaushaltes 696.646.544 Euro", "")
    with pytest.raises(SatzungFehler) as fehler:
        parse_satzung(ohne)
    assert "Nachrichtlich" in str(fehler.value)


# --------------------------------------------------------------------------
# (b) Was hier steht, ist nicht beschlossen
# --------------------------------------------------------------------------

def test_jede_satzung_im_ris_ist_ein_entwurf():
    """Alle neun Dokumente tragen „Verwaltungsentwurf" und „xx.xx.JJJJ" als
    Sitzungsdatum. Wer das wegließe, machte aus einem Vorschlag der Verwaltung
    einen Ratsbeschluss."""
    s = parse_satzung(SATZUNG_2024)
    assert s.fassung == "entwurf"
    assert s.session_date is None, "„xx.xx.2023“ ist kein Datum"


def test_ohne_entwurfsvermerk_heisst_es_unbekannt_und_nicht_beschlossen():
    """Behauptet wird nichts. Ein Dokument ohne Vermerk ist nicht dadurch
    beschlossen, dass der Vermerk fehlt."""
    neutral = (SATZUNG_2024.replace("Verwaltungsentwurf", "")
                           .replace("xx.xx.2023", "15.12.2023"))
    s = parse_satzung(neutral)
    assert s.fassung == "unbekannt"
    assert s.session_date == "15.12.2023"


def test_die_herkunft_nennt_die_fassung_im_stand():
    """Die Fassung gehört in den Stand und nicht in eine Fußnote."""
    s = parse_satzung(SATZUNG_2024)
    h = herkunft_fuer(s, url=None, document_id=271310, label="Haushaltssatzung 2024")
    assert "Verwaltungsentwurf" in h.stand
    assert PROBE_FINANZHAUSHALT in h.probe
    assert PROBE_HEBESATZ not in h.probe, "ohne Jahrbuch-Abgleich keine Hebesatz-Probe"

    mit = herkunft_fuer(s, url=None, document_id=271310, label="x",
                        hebesatz_geprueft="Hebesatz gegen Tabelle 1105 gehalten")
    assert PROBE_HEBESATZ in mit.probe


# --------------------------------------------------------------------------
# (c) Die Schreibweisen
# --------------------------------------------------------------------------

def test_EUR_statt_Euro():
    """Die Jahrgänge 2019 und 2020 schreiben durchgängig „EUR".

    Dieselbe Falle wie beim Eigenbetrieb Hafen — und sie ist lautlos: Ein
    Muster, das nur „Euro" kennt, findet dort einfach nichts und meldet keinen
    Fehler, sondern eine fehlende Zeile."""
    s = parse_satzung(SATZUNG_2020_EUR)
    assert s.year == 2020
    assert s.in_total == 696_646_544.0


def test_kredite_nicht_veranschlagt_ist_eine_null_und_keine_luecke():
    """§ 2 sagt in jedem gelesenen Jahrgang „werden nicht veranschlagt".
    Das ist eine Aussage — die Stadt nimmt keine Investitionskredite auf."""
    s = parse_satzung(SATZUNG_2024)
    assert s.investment_loans == 0.0


def test_fehlende_grundsteuer_ist_keine_luecke_im_einlesen():
    """Ab dem Jahrgang 2025 nennt § 5 nur noch die Gewerbesteuer und verweist
    für die Grundsteuer auf eine eigene Satzung."""
    ab2025 = SATZUNG_2024[:SATZUNG_2024.index("§ 5")] + """§ 5
Der Steuersatz (Hebesatz) für die Gewerbesteuer wird für das Haushaltsjahr 2025 auf
439 v. H.
festgesetzt.
Die Grundsteuerhebesätze sind der aktuellen Satzung der Stadt Oldenburg (Oldb) zu entnehmen.
"""
    s = parse_satzung(ab2025)
    assert s.hebesatz_gewerbesteuer == 439
    assert s.hebesatz_grundsteuer_a is None
    assert s.hebesatz_grundsteuer_b is None


def test_hebesaetze_werden_gelesen():
    s = parse_satzung(SATZUNG_2024)
    assert (s.hebesatz_grundsteuer_a, s.hebesatz_grundsteuer_b,
            s.hebesatz_gewerbesteuer) == (390, 445, 439)


# --------------------------------------------------------------------------
# (d) Der Nachtrag
# --------------------------------------------------------------------------

def test_der_nachtrag_wird_erkannt_und_abgewiesen():
    """Er trägt dasselbe Wort im Label und eine ganz andere Tabelle
    (bisher / erhöht um / vermindert um / Gesamtbetrag). Ein Parser, der es
    versuchte, ordnete Spalten falsch zu — und die Summenprobe fände dazu
    keine „Nachrichtlich"-Zeile, an der sie das merken könnte."""
    with pytest.raises(SatzungFehler) as fehler:
        parse_satzung(NACHTRAG)
    assert "Nachtrag" in str(fehler.value)


def test_ohne_haushaltsjahr_wird_nichts_geraten():
    with pytest.raises(SatzungFehler):
        parse_satzung("Irgendein Text ohne Jahresangabe.")


# --------------------------------------------------------------------------
# (e) Speichern
# --------------------------------------------------------------------------

def test_speichern_und_wiederlesen(tmp_path):
    from council.store import CouncilStore

    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        s = parse_satzung(SATZUNG_2024)
        store.save_haushaltssatzung(s, herkunft_fuer(
            s, url=None, document_id=271310, label="Haushaltssatzung 2024"))
        zeilen = store.get_haushaltssatzungen()
        assert len(zeilen) == 1
        z = zeilen[0]
        assert z["year"] == 2024 and z["fassung"] == "entwurf"
        assert z["liquidity_loans"] == 100_000_000.0
        assert z["investment_loans"] == 0.0
        assert store.haushaltssatzung_jahre() == [2024]
        assert "council_haushaltssatzung" not in store.herkunft_luecken()
    finally:
        store.close()


def test_derselbe_jahrgang_zweimal_gibt_eine_zeile(tmp_path):
    """2021 liegt zweimal im Bestand (Anlagen 229865 und 230043, gleicher
    Inhalt). Der Primärschlüssel fängt das — sonst stünde der Jahrgang
    doppelt in jeder Auswertung."""
    from council.store import CouncilStore

    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        s = parse_satzung(SATZUNG_2024)
        for dokument in (229865, 230043):
            store.save_haushaltssatzung(s, herkunft_fuer(
                s, url=None, document_id=dokument, label="Haushaltssatzung"))
        assert len(store.get_haushaltssatzungen()) == 1
    finally:
        store.close()
