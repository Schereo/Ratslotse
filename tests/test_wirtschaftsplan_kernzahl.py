"""Die Kernzahl aus dem Beschlusstext, bestätigt durch die Anlage.

Die Ausschnitte sind echt (Vorlagen 25/0819 Bäderbetriebsgesellschaft,
25/0850 Stadion, 25/0818 Bäderbetrieb) — mit ihren drei Schreibweisen und der
Vorzeichen-Falle, die der Grund für dieses Modul ist.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from council.wirtschaftsplan import WirtschaftsplanFehler, betrieb_aus_titel  # noqa: E402
from council.wirtschaftsplan_kernzahl import (  # noqa: E402
    herkunft_fuer,
    kernzahl_aus_beschluss,
    parse_kernzahl,
)

TITEL_BBGO = ("Bäderbetriebsgesellschaft Oldenburg mbH (BBGO): "
              "Wirtschaftsplan 2026 - Beschluss")
# Vorzeichen steht ZUSÄTZLICH vor der Zahl.
TEXT_BBGO = """Beschlussvorschlag:
Der Wirtschaftsplan 2026 der Bäderbetriebsgesellschaft Oldenburg mbH (BBGO),
bestehend aus Ergebnisplanung, Bilanzplanung, Liquiditätsplanung, Vermögensplanung
und Spartenrechnungsplanung wird in der anliegenden Fassung mit einem für die
Gesellschaft ausgewiesenen Jahresfehlbetrag von -10.128.335 Euro beschlossen.
"""
ANLAGE_BBGO = """Jahresüberschuss /-fehlbetrag  -5.709.453 -5.685.391 -6.010.229 -10.128.335 -10.389.720
"""

TITEL_STADION = "Stadion Oldenburg GmbH & Co. KG: Wirtschaftsplan 2026 - Beschluss"
# KEIN Minus vor der Zahl — das Wort trägt die Richtung.
TEXT_STADION = """Beschlussvorschlag:
Der Wirtschaftsplan für das Wirtschaftsjahr 2026 der Stadion Oldenburg GmbH & Co. KG,
bestehend aus der Ergebnis- und Vermögensplanung, wird in der anliegenden Fassung mit
einem maximalen Fehlbetrag in Höhe von 651.500 Euro beschlossen.
"""
ANLAGE_STADION = """Gesamtergebnis 240.000 € -    651.500 € -    628.100 € -    763.600 € -
"""

TITEL_BBO = "Bäderbetrieb der Stadt Oldenburg (BBO): Wirtschaftsplan 2026 - Beschluss"
TEXT_BBO = """Auswirkungen:
 a) Finanzen
Der Wirtschaftsplan 2026 schließt mit einem geplanten Jahresfehlbetrag in Höhe von
0,00 Euro ab. Der Ergebnishaushalt wird nicht belastet.
"""


# --------------------------------------------------------------------------
# (a) Die Vorzeichen-Falle
# --------------------------------------------------------------------------

def test_fehlbetrag_ohne_minus_wird_negativ():
    """„maximalen Fehlbetrag in Höhe von 651.500 Euro" sind MINUS 651.500 €.

    Das Wort trägt die Richtung, nicht die Ziffernfolge. Wer beides gleich
    liest, macht aus einem Verlust einen Gewinn."""
    wort, amount = kernzahl_aus_beschluss(TEXT_STADION)
    assert "Fehlbetrag" in wort
    assert amount == -651_500.0


def test_fehlbetrag_mit_minus_wird_nicht_doppelt_gedreht():
    wort, amount = kernzahl_aus_beschluss(TEXT_BBGO)
    assert amount == -10_128_335.0, "nicht +10.128.335 durch doppelte Negation"


def test_ausgeglichener_plan_ist_null_und_nicht_minus_null():
    """`-abs(0.0)` wäre `-0.0` und stünde als „-0,00 €" auf der Seite."""
    _, amount = kernzahl_aus_beschluss(TEXT_BBO)
    assert amount == 0.0
    assert str(amount) == "0.0"


def test_ueberschuss_mit_negativem_betrag_wirft():
    """Wort und Zahl sagen Verschiedenes — das ist ein Fehler, kein Fall für
    stilles Umdrehen."""
    text = TEXT_BBGO.replace("Jahresfehlbetrag von -10.128.335",
                             "Jahresüberschuss von -10.128.335")
    with pytest.raises(WirtschaftsplanFehler) as fehler:
        kernzahl_aus_beschluss(text)
    assert "sagen Verschiedenes" in str(fehler.value)


# --------------------------------------------------------------------------
# (b) Die Gegenprobe über zwei Dokumente
# --------------------------------------------------------------------------

def test_zahl_aus_dem_beschluss_steht_in_der_anlage():
    plan, wort, lage = parse_kernzahl(
        "25/0819", TITEL_BBGO, TEXT_BBGO, 2026, [ANLAGE_BBGO])
    assert plan.enterprise == "bbgo"
    assert plan.result == -10_128_335.0
    assert lage == "belegt"


def test_nur_das_ergebnis_kommt_aus_dieser_quelle():
    """Erträge und Aufwendungen bleiben NULL — die Quelle nennt sie nicht, und
    eine 0 wäre eine Behauptung."""
    plan, _, _ = parse_kernzahl("25/0819", TITEL_BBGO, TEXT_BBGO, 2026, [ANLAGE_BBGO])
    assert plan.revenues is None and plan.expenses is None
    assert plan.result is not None


def test_widerspruch_zwischen_beschluss_und_anlage_wirft():
    """Zwei Dokumente desselben Vorgangs dürfen sich nicht widersprechen."""
    with pytest.raises(WirtschaftsplanFehler) as fehler:
        parse_kernzahl("25/0819", TITEL_BBGO, TEXT_BBGO, 2026,
                       ["Jahresüberschuss /-fehlbetrag -1.234.567"])
    assert "widersprechen sich" in str(fehler.value)


def test_ohne_anlagentext_wird_uebernommen_aber_angeschrieben():
    """Keine lesbare Anlage ist KEIN Widerspruch — der Beschlusstext bleibt die
    maßgebliche Stelle, aber die Herkunft sagt, dass die Gegenprobe fehlte."""
    plan, _, lage = parse_kernzahl("23/0858", TITEL_STADION, TEXT_STADION, 2026, [])
    assert plan.result == -651_500.0
    assert lage == "ohne_anlage"


def test_null_gilt_als_nicht_gegenpruefbar():
    """Die Ziffer 0 steht in jeder Anlage hundertfach — daran ändert auch OCR
    nichts, und deshalb ist das eine eigene Lage."""
    plan, _, lage = parse_kernzahl("25/0818", TITEL_BBO, TEXT_BBO, 2026,
                                   ["irgendein Text mit 0 darin"])
    assert plan.result == 0.0
    assert lage == "ausgeglichen"


def test_die_anlage_darf_die_zahl_verklebt_fuehren():
    """Im Textextrakt kleben Zahlen aneinander („9.996.40910.570.144") — der
    Beleg darf daran nicht scheitern."""
    _, _, lage = parse_kernzahl("25/0819", TITEL_BBGO, TEXT_BBGO, 2026,
                                ["...-6.010.229-10.128.335-10.389.720..."])
    assert lage == "belegt"


# --------------------------------------------------------------------------
# (c) Die beiden Stadion-Gesellschaften
# --------------------------------------------------------------------------

def test_planungsgesellschaft_und_betriebsgesellschaft_sind_zwei():
    """2024 legen BEIDE einen Wirtschaftsplan vor (−152.000 € und −190.000 €).
    Ein gemeinsames Muster „Stadion" schrieb den einen Betrag unter den Namen
    der anderen — und die Tabelle hätte es nie gemerkt, weil (betrieb, year)
    der Schlüssel ist."""
    assert betrieb_aus_titel(
        "Stadionplanungsgesellschaft mbH: Wirtschaftsplan 2024")[0] == "stadion_planung"
    assert betrieb_aus_titel(
        "Stadion Oldenburg GmbH & Co. KG: Wirtschaftsplan 2024")[0] == "stadion"


def test_kein_beschlusstext_mit_zahl_liefert_nichts():
    assert parse_kernzahl("x/1", TITEL_BBGO, "Beschlussvorschlag: Zustimmung.",
                          2026, []) is None


# --------------------------------------------------------------------------
# (d) Herkunft und Speichern
# --------------------------------------------------------------------------

def test_die_herkunft_nennt_die_beleglage():
    plan, wort, lage = parse_kernzahl(
        "25/0819", TITEL_BBGO, TEXT_BBGO, 2026, [ANLAGE_BBGO])
    h = herkunft_fuer(plan, wort, lage, url=None, kvonr=28315)
    assert "wirtschaftsplan_kernzahl" in h.probe
    assert "in der Anlage" in h.probe_result
    assert "kvonr=28315" in h.url


def test_zeile_ohne_ertraege_laesst_sich_speichern(tmp_path):
    """Der Grund für den Schema-Umbau: Diese Quelle nennt kein Tripel."""
    from council.store import CouncilStore

    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        plan, wort, lage = parse_kernzahl(
            "25/0819", TITEL_BBGO, TEXT_BBGO, 2026, [ANLAGE_BBGO])
        store.save_wirtschaftsplan(plan, herkunft_fuer(
            plan, wort, lage, url=None, kvonr=28315))
        zeilen = store.get_wirtschaftsplaene("bbgo")
        assert len(zeilen) == 1
        assert zeilen[0]["revenues"] is None
        assert zeilen[0]["result"] == -10_128_335.0
        assert "council_wirtschaftsplaene" not in store.herkunft_luecken()
    finally:
        store.close()


# --------------------------------------------------------------------------
# (e) Der Eigenbetrieb Hafen — der einzige, der „Verlust" sagt
# --------------------------------------------------------------------------

TITEL_HAFEN = ("Wirtschaftsplan 2019 für den Eigenbetrieb Hafen der Stadt "
               "Oldenburg (Oldb) - Beschluss -")
# Echt, aus Vorlage 18/0790. Kein „Fehlbetrag", kein „Überschuss" — und die
# Einheit steht als „EUR", nicht als „€" oder „Euro".
TEXT_HAFEN = """Beschlussvorschlag:
Dem Wirtschaftsplan 2019 des Eigenbetriebes Hafen der Stadt Oldenburg (Oldb) wird in der
als Anlage beigefügten Fassung zugestimmt.

Begründung:
Für das Wirtschaftsjahr 2019 ist für den Eigenbetrieb Hafen der Stadt Oldenburg (Oldb) im
vorliegenden Wirtschaftsplan (Erfolgsplan) ein Verlust von 273.950 EUR ermittelt worden.
Der erwartete Zuschussbedarf 2019 ist damit gegenüber 2018 um 76.050 EUR geringer.
"""
# Echt, aus Anlage 194665 — dieselbe Zahl, anderer Satz, anderes Dokument.
ANLAGE_HAFEN = """Der Erfolgsplan 2019 schließt mit einem erwarteten Verlust von 273.950 EUR ab. Der
Verlust wird durch den Kernhaushalt ausgeglichen.
"""


def test_verlust_ist_ein_minus():
    """Der Hafen schreibt weder „Fehlbetrag" noch „Überschuss". Ohne dieses
    Wort blieben seine beiden einzigen Jahrgänge draußen — und zwar lautlos:
    Die Vorlage wäre nie erkannt worden, es hätte nie einen Fehler gegeben."""
    wort, amount = kernzahl_aus_beschluss(TEXT_HAFEN)
    assert wort.lower() == "verlust"
    assert amount == -273_950.0


def test_die_einheit_darf_auch_EUR_heissen():
    """Die übrigen Betriebe schreiben „€" oder „Euro", der Hafen „EUR"."""
    assert kernzahl_aus_beschluss(TEXT_HAFEN)[1] == -273_950.0


def test_hafen_ist_zweifach_belegt():
    plan, wort, lage = parse_kernzahl("18/0790", TITEL_HAFEN, TEXT_HAFEN, 2019,
                                      [ANLAGE_HAFEN])
    assert plan.enterprise == "hafen"
    assert plan.enterprise_name == "Eigenbetrieb Hafen der Stadt Oldenburg"
    assert plan.result == -273_950.0
    assert lage == "belegt"


def test_gewinn_bleibt_positiv():
    """Das Gegenstück zu „Verlust" — sonst drehte die Vorzeichen-Regel jede
    Zahl ins Minus, die zufällig neben einem dieser Wörter steht."""
    text = TEXT_HAFEN.replace("ein Verlust von 273.950 EUR",
                              "ein Gewinn von 273.950 EUR")
    wort, amount = kernzahl_aus_beschluss(text)
    assert wort.lower() == "gewinn"
    assert amount == 273_950.0


# ---------------------------------------------------------------------------
# Die Investitionen des Vermögensplans
#
# ANLASS (Tim, 21.08.2026): „Ich habe in den Wirtschaftsplan vom Bäderbetrieb
# reingeguckt und da stehen ja ganz, ganz viele Zahlen drin. Wie kann es sein,
# dass hier das Jahresergebnis immer Null ist?" — Die Null stimmt (sieben von
# sieben Jahrgängen schreiben „Jahresfehlbetrag in Höhe von 0,00 EUR"), aber
# derselbe Beschlusstext nennt zweistellige Millionenbeträge, die wir nicht
# gelesen haben.
# ---------------------------------------------------------------------------

#: Der Beschlusstext 2026 des Bäderbetriebs, gekürzt auf die zwei Sätze, um die
#: es geht. 10.702.000 + 50.000 = 10.752.000 — die Probe steht im Text selbst.
TEXT_BBO = (
    "Der Wirtschaftsplan 2026 weist in seiner Erfolgsrechnung ein "
    "ausgeglichenes Ergebnis aus. Der Vermögensplan weist Investitionen in "
    "Höhe von 10.752.000 Euro aus. Die Finanzierung der geplanten "
    "Investitionen erfolgt durch eine Kreditaufnahme am Kreditmarkt "
    "(10.702.000 Euro) und aus der Verwendung von Abschreibungen (vermindert "
    "um die Tilgungsleistungen) und der Liquidität (50.000 Euro). "
    "Der Wirtschaftsplan 2026 schließt mit einem geplanten Jahresfehlbetrag "
    "in Höhe von 0,00 Euro ab. Der Ergebnishaushalt wird nicht belastet."
)


def test_investitionen_mit_eigener_probe():
    from council.wirtschaftsplan_kernzahl import investitionen_aus_beschluss

    assert investitionen_aus_beschluss(TEXT_BBO) == 10_752_000.0


def test_ursprünglicher_plan_wird_nicht_gelesen():
    """Die teuerste Falle dieses Musters.

    Zwei Jahrgänge (2024, 2025) sind ANPASSUNGS-Vorlagen: Sie zitieren den
    alten Stand, bevor sie ihn ändern. Wer „Der ursprüngliche Vermögensplan
    2025 weist Investitionen in Höhe von 19.535.418 Euro aus" liest,
    speichert eine überholte Zahl als aktuelle — und sie ginge auch noch
    durch die Finanzierungsprobe, weil der zitierte Satz seine eigenen
    Klammerbeträge mitbringt."""
    from council.wirtschaftsplan_kernzahl import investitionen_aus_beschluss

    text = TEXT_BBO.replace("Der Vermögensplan weist",
                            "Der ursprüngliche Vermögensplan weist")
    assert investitionen_aus_beschluss(text) is None


def test_ohne_finanzierungssatz_keine_zahl():
    """Eine Summe ohne Gegenrechnung wird nicht gespeichert."""
    from council.wirtschaftsplan_kernzahl import investitionen_aus_beschluss

    text = TEXT_BBO.split("Die Finanzierung")[0]
    assert investitionen_aus_beschluss(text) is None


def test_finanzierung_die_nicht_aufgeht_faellt_durch():
    """Der eigentliche Wert der Probe: Sie fängt einen Lesefehler.

    Wäre der Kreditbetrag verlesen, ergäben die Teile nicht mehr die Summe —
    und dann steht lieber nichts da als eine falsche Zahl."""
    from council.wirtschaftsplan_kernzahl import investitionen_aus_beschluss

    text = TEXT_BBO.replace("(10.702.000 Euro)", "(9.702.000 Euro)")
    assert investitionen_aus_beschluss(text) is None


def test_probe_haengt_nur_dran_wo_sie_lief():
    """Die Herkunft darf keine Probe behaupten, die es nicht gab."""
    from council.wirtschaftsplan import Wirtschaftsplan
    from council.wirtschaftsplan_kernzahl import (
        PROBE_INVESTITIONEN, herkunft_fuer)

    def plan(investitionen):
        return Wirtschaftsplan(
            enterprise="bbo", enterprise_name="Bäderbetrieb der Stadt Oldenburg",
            year=2026, template_number="25/0818/1", revenues=None, expenses=None,
            steuern=None, result=0.0, capital_plan=None,
            commitments=None, draft_date=None, investitionen=investitionen)

    mit = herkunft_fuer(plan(10_752_000.0), "0,00 Euro", "ausgeglichen",
                        url=None, kvonr=1)
    ohne = herkunft_fuer(plan(None), "0,00 Euro", "ausgeglichen",
                         url=None, kvonr=1)
    assert PROBE_INVESTITIONEN in mit.probe
    assert PROBE_INVESTITIONEN not in ohne.probe
