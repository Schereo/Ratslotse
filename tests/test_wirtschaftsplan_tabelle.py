"""Der Erfolgsplan aus der Anlage — Abfallwirtschaftsbetrieb.

Die Ausschnitte sind **echt**, aus den Anlagen 283481 (Wirtschaftsplan 2025,
Layout A) und 299038 (2026, Layout B), samt ihrer Eigenheiten: Beträge mit
„€"-Zeichen, sechs Spalten je Zeile, und die Ertragszeile, die fünfmal
vorkommt — einmal für alle Bereiche, viermal je Betriebszweig. Gekürzt ist nur,
was zwischen den geprüften Zeilen steht.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from council.wirtschaftsplan import WirtschaftsplanFehler  # noqa: E402
from council.wirtschaftsplan_tabelle import (  # noqa: E402
    BEREICHE_SCHWELLE,
    KOPF_FENSTER,
    TOLERANZ_EUR,
    bereichsprobe,
    einheit_an_der_kopfzeile,
    kopfspalten,
    kopfzeile_index,
    parse_erfolgsplan,
    prosa_summen,
)

# Layout A (Wirtschaftsplan 2025). Die Planspalte ist die DRITTE.
LAYOUT_A = """Erfolgsplan Abfallwirtschaftsbetrieb Stadt Oldenburg
Gewinn- und Verlustrechnung
(für alle Bereiche) Ist 2023 Plan 2024 Plan 2025 Plan 2026 Plan 2027 Plan 2028

Gesamtertrag 24.058.098 € 23.892.230 € 25.197.796 € 25.531.456 € 25.980.245 € 26.389.251 €
Gesamtaufwendungen 22.005.713 € 23.349.624 € 24.570.285 € 24.982.783 € 25.403.531 € 25.832.694 €
Gesamtergebnis 2.052.385 € 542.606 € 627.511 € 548.673 € 576.714 € 556.557 €

Der Erfolgsplan 2025 umfasst voraussichtlich anfallende Erträge in Höhe von insgesamt 25.197.796 € und voraussichtlich entstehende
Aufwendungen in Höhe von insgesamt 24.570.285 €.

Anlage 1 - Abfallbehandlungsanlagen -
Gesamtertrag 1.934.257 € 2.074.521 € 2.433.361 € 2.626.137 € 2.822.768 € 3.023.332 €
Anlage 2 - Abfallsammlung -
Gesamtertrag 15.724.264 € 15.828.985 € 16.404.734 € 16.372.898 € 16.494.245 € 16.618.019 €
Anlage 3 - Straßenreinigung -
Gesamtertrag 5.218.996 € 5.025.024 € 5.777.302 € 5.413.904 € 5.542.343 € 5.624.592 €
Anlage 4 - Werkstatt -
Gesamtertrag 1.180.581 € 963.700 € 1.029.400 € 1.118.518 € 1.120.889 € 1.123.307 €
"""

# Layout B (2026): andere Beschriftungen, „Ergebnis" statt „Ist" im Kopf.
LAYOUT_B = """Erfolgsplan Abfallwirtschaftsbetrieb Stadt Oldenburg
Pos. Bezeichnung Ergebnis 2024 Plan 2025 Plan 2026 Plan 2027 Plan 2028 Plan 2029
1. Umsatzerlöse 23.824.312 € 24.716.196 € 26.210.750 € 26.714.286 € 27.227.893 € 27.751.772 €
Summe Erträge 24.220.475 € 25.112.196 € 26.747.250 € 27.261.296 € 27.785.623 € 28.320.437 €
Summe Aufwendungen 23.904.250 € 24.462.985 € 26.036.000 € 26.550.046 € 27.074.373 € 27.609.186 €
11. Ergebnis nach Steuern 316.225 € 649.211 € 711.250 € 711.250 € 711.250 € 711.250 €
12. Sonstige Steuern 21.901 € 21.700 € 22.650 € 22.650 € 22.650 € 22.650 €
13. Jahresüberschuss (+) / Jahresfehlbetrag (-) 294.324 € 627.511 € 688.600 € 688.600 € 688.600 € 688.600 €
Der Erfolgsplan 2026 umfasst voraussichtlich anfallende Erträge in Höhe von insgesamt 26.747.250 Euro und voraussichtlich entstehende Aufwendungen in Höhe von insgesamt 26.036.000 Euro.
"""


# --------------------------------------------------------------------------
# (a) Beide Layouts
# --------------------------------------------------------------------------

def test_liest_layout_a_und_findet_die_planspalte():
    """Die Planspalte ist die dritte — gefunden über das Haushaltsjahr, nicht
    über die Position."""
    plan, proben = parse_erfolgsplan("24/0671", "awb", 2025, LAYOUT_A)
    assert plan.jahr == 2025
    assert plan.ertraege == 25_197_796.0
    assert plan.aufwendungen == 24_570_285.0
    assert plan.ergebnis == 627_511.0
    assert len(proben) == 6, "alle sechs Spalten werden geprüft, nicht nur die gespeicherte"


def test_liest_layout_b_mit_anderen_beschriftungen():
    """2026 heißt dieselbe Zeile „Summe Erträge" statt „Gesamtertrag" — und der
    Kopf schreibt „Ergebnis 2024" statt „Ist 2024"."""
    plan, proben = parse_erfolgsplan("25/0642", "awb", 2026, LAYOUT_B)
    assert plan.ertraege == 26_747_250.0
    assert plan.aufwendungen == 26_036_000.0
    assert plan.ergebnis == 711_250.0
    assert len(proben) == 6


def test_das_ergebnis_ist_nicht_der_jahresueberschuss():
    """In Layout B stehen unter der gelesenen Zeile noch „Sonstige Steuern" und
    „Jahresüberschuss". Gelesen wird die Zeile DIREKT unter den beiden Summen —
    sonst gälte `Erträge − Aufwendungen = Ergebnis` in der gespeicherten Zeile
    nicht mehr."""
    plan, _ = parse_erfolgsplan("25/0642", "awb", 2026, LAYOUT_B)
    assert plan.ergebnis == 711_250.0, "Ergebnis nach Steuern"
    assert plan.ergebnis != 688_600.0, "NICHT der Jahresüberschuss"
    assert abs(plan.ertraege - plan.aufwendungen - plan.ergebnis) <= TOLERANZ_EUR


def test_die_gespeicherte_zeile_erfuellt_dieselbe_beziehung_wie_der_beschlusstext():
    """`Erträge − Aufwendungen − Steuern = Ergebnis` gilt für JEDE Zeile der
    Tabelle, egal ob sie aus dem Beschlusstext oder aus einer Anlage kommt.
    Die Null bei `steuern` ist deshalb eine Aussage, keine Lücke."""
    plan, _ = parse_erfolgsplan("24/0671", "awb", 2025, LAYOUT_A)
    assert plan.steuern == 0.0
    assert abs(plan.ertraege - plan.aufwendungen - plan.steuern - plan.ergebnis) <= TOLERANZ_EUR


def test_kopfspalten_lesen_art_und_jahr():
    assert kopfspalten(LAYOUT_A.splitlines())[:3] == [
        ("ist", 2023), ("plan", 2024), ("plan", 2025)]
    assert kopfspalten(LAYOUT_B.splitlines())[0] == ("ist", 2024), '„Ergebnis“ ist auch Ist'


# --------------------------------------------------------------------------
# (b) Die drei Proben
# --------------------------------------------------------------------------

def test_spaltenprobe_faellt_bei_verstellter_zahl():
    kaputt = LAYOUT_A.replace("25.197.796 €", "25.197.999 €", 1)
    with pytest.raises(WirtschaftsplanFehler) as fehler:
        parse_erfolgsplan("24/0671", "awb", 2025, kaputt)
    assert "gehen nicht auf" in str(fehler.value)


def test_rundung_von_einem_euro_reisst_nicht():
    """Layout B rundet je Position — die Finanzplanung 2029 liegt im echten
    Dokument um 1 € daneben. Eine cent-genaue Schwelle verwürfe den Jahrgang
    wegen einer Rundung."""
    plan, proben = parse_erfolgsplan("25/0642", "awb", 2026, LAYOUT_B)
    letzte = proben[-1]
    assert abs(letzte.rest) == 1.0 and letzte.geht_auf


def test_prosa_probe_findet_beide_schreibweisen():
    assert prosa_summen(LAYOUT_A) == (2025, 25_197_796.0, 24_570_285.0), "mit €"
    assert prosa_summen(LAYOUT_B) == (2026, 26_747_250.0, 26_036_000.0), "mit Euro"


def test_prosa_die_der_tabelle_widerspricht_ist_ein_fehler():
    """Zwei Stellen desselben Dokuments dürfen sich nicht widersprechen."""
    kaputt = LAYOUT_A.replace("insgesamt 25.197.796 €", "insgesamt 25.000.000 €", 1)
    with pytest.raises(WirtschaftsplanFehler) as fehler:
        parse_erfolgsplan("24/0671", "awb", 2025, kaputt)
    assert "widersprechen sich" in str(fehler.value)


def test_fehlende_prosa_reisst_nicht():
    """Sie ist Fließtext, keine Tabellenzeile — ein Jahrgang, der sie weglässt,
    hat deswegen keine falschen Zahlen."""
    ohne = "\n".join(z for z in LAYOUT_A.splitlines() if "umfasst" not in z)
    plan, _ = parse_erfolgsplan("24/0671", "awb", 2025, ohne)
    assert plan.ertraege == 25_197_796.0


def test_bereichsprobe_misst_die_zweige():
    """Die vier Betriebszweige ergeben die Gesamtzeile — damit ist „die erste
    Zeile ist die Gesamtrechnung" gemessen und nicht angenommen."""
    n_zweige, reste = bereichsprobe(LAYOUT_A, "awb")
    assert n_zweige == 4
    assert abs(reste[0]) <= 1, "Ist 2023 geht auf"
    # Die Planspalte des echten Jahrgangs 2025 hat einen Widerspruch von
    # 447.001 € — im Fixture bewusst nachgebaut.
    assert abs(reste[2]) == 447_001.0


def test_widerspruch_in_den_zweigen_reisst_den_jahrgang_nicht():
    """Der reale Fall 2025: Die Zweige gehen in der Planspalte um 1,77 % nicht
    auf, die Summe selbst ist durch zwei andere Proben gedeckt. Dann fällt die
    Aufteilung und nicht die Summe (dieselbe Regel wie 2022 bei den Schulden).
    """
    plan, _ = parse_erfolgsplan("24/0671", "awb", 2025, LAYOUT_A)
    assert plan.ertraege == 25_197_796.0
    _, reste = bereichsprobe(LAYOUT_A, "awb")
    assert abs(reste[2]) / plan.ertraege < BEREICHE_SCHWELLE


def test_ein_betriebszweig_statt_der_gesamtzeile_faellt_durch():
    """Der Fall, für den die Bereichsprobe da ist: Griffe der Parser die Zeile
    eines Zweigs, wäre die Zahl um ein Vielfaches zu klein — und die Zweige
    lägen dann weit über 5 % daneben."""
    # Die Gesamtzeile entfernen: Jetzt ist die erste „Gesamtertrag"-Zeile die
    # des Zweigs Abfallbehandlungsanlagen.
    verstuemmelt = LAYOUT_A.replace(
        "Gesamtertrag 24.058.098 € 23.892.230 € 25.197.796 € 25.531.456 € "
        "25.980.245 € 26.389.251 €\n", "", 1)
    with pytest.raises(WirtschaftsplanFehler) as fehler:
        parse_erfolgsplan("24/0671", "awb", 2025, verstuemmelt)
    assert "Betriebszweige" in str(fehler.value) or "gehen nicht auf" in str(fehler.value)


# --------------------------------------------------------------------------
# (c) Grenzen
# --------------------------------------------------------------------------

def test_fehlendes_haushaltsjahr_wird_nicht_geraten():
    with pytest.raises(WirtschaftsplanFehler) as fehler:
        parse_erfolgsplan("24/0671", "awb", 2099, LAYOUT_A)
    assert "steht nicht in der Kopfzeile" in str(fehler.value)


def test_unbekannter_betrieb_hat_kein_vokabular():
    """Ein geratenes Vokabular fände irgendeine Zeile — und ihre Zahlen stünden
    unter einem Namen, den nie jemand nachgeschlagen hat."""
    with pytest.raises(WirtschaftsplanFehler) as fehler:
        parse_erfolgsplan("25/0818", "bbo", 2026, LAYOUT_A)
    assert "kein Zeilen-Vokabular" in str(fehler.value)


def test_speichern_neben_dem_beschlusstext(tmp_path):
    """AWB- und EGH-Zeilen stehen in derselben Tabelle und vertragen sich."""
    from council.store import CouncilStore
    from council.wirtschaftsplan_tabelle import herkunft_fuer

    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        plan, proben = parse_erfolgsplan("24/0671", "awb", 2025, LAYOUT_A)
        store.save_wirtschaftsplan(plan, herkunft_fuer(
            plan, proben, url="https://example.org/x", dokument_id=283481,
            label="Anlage Wirtschafts- und Finanzplan 2025"))
        zeilen = store.get_wirtschaftsplaene("awb")
        assert len(zeilen) == 1 and zeilen[0]["ertraege"] == 25_197_796.0
        assert "wirtschaftsplan_spalten" in zeilen[0]["proben"]
        assert store.wirtschaftsplan_jahre("awb") == [2025]
        assert "council_wirtschaftsplaene" not in store.herkunft_luecken()
    finally:
        store.close()


# --------------------------------------------------------------------------
# (f) Das Layout der Jahrgänge 2019–2021 — aus einem Scan, per OCR gelesen
# --------------------------------------------------------------------------

# Echt, aus Anlage 193959 (Wirtschaftsplan 2019). Der Jahrgang lag bis 08/2026
# nur als Bild vor; `scripts/backfill_anlagen_ocr.py` hat ihn lesbar gemacht.
# Gekürzt ist, was zwischen den geprüften Zeilen steht.
LAYOUT_C = """Erfolgsplan Abfallwirtschaftsbetrieb Stadt Oldenburg

Gewinn- und Verlustrechnung
(für alle Sparten)
\tIst 2017\tPlan 2018\tPlan 2019\tPlan 2020\tPlan 2021\tPlan 2022

Gesamtertrag\t21.011.173 €\t19.465.433 €\t20.280.001 €\t20.492.447 €\t20.906.615 €\t21.280.307 €
Gesamtaufwendungen\t20.086.318 €\t19.128.086 €\t19.989.470 €\t20.310.714 €\t20.638.383 €\t20.972.605 €
Gesamtergebnis\t924.855 €\t337.347 €\t290.531 €\t181.733 €\t268.232 €\t307.702 €

Ergebnis der gewöhnlichen
Geschäftstätigkeit\t412.363 €\t337.347 €\t290.531 €\t181.733 €\t268.232 €\t307.702 €

Jahresüberschuss\t285.253 €\t337.347 €\t290.531 €\t181.733 €\t268.232 €\t307.702 €

Eigenkapitalverzinsung
(Zuführung zum städt. Haushalt)
Sparte 6750 Straßenreinigung\t-28.963 €\t-27.800 €\t-21.500 €\t-21.500 €\t-21.500 €\t-21.500 €

Jahresergebnis\t85.565 €\t139.847 €\t93.031 €\t-15.767 €\t70.732 €\t110.202 €

Der Erfolgsplan 2019 umfasst voraussichtlich anfallende Erträge in Höhe von insgesamt 20.280.001 € und voraussichtlich entstehende Aufwendungen in Höhe von insgesamt 19.989.470 €.
"""

# Der Vorbericht steht rund 140 Zeilen VOR der Tabelle und redet von Millionen.
VORBERICHT = ("Der Erfolgsplan ist in Sparten gegliedert. Für 2019 werden "
              "Gesamterträge in Höhe von ca. 20,3 Mio. € erwartet.\n" + "\n" * 140)


def test_das_alte_layout_liest_sich_ohne_zutun():
    """Die Jahrgänge 2019–2021 brauchten KEINE Parser-Erweiterung.

    Nach dem ersten OCR-Lauf sah es anders aus — dort fehlte die Summenzeile,
    weil der Lauf nach sechs Seiten abbrach und sie auf Seite fünf der Tabelle
    steht. Der Befund „der Parser kennt dieses Layout nicht" war ein Artefakt
    des abgeschnittenen Textes, kein Befund über das Dokument."""
    plan, proben = parse_erfolgsplan("18/0741", "awb", 2019, LAYOUT_C)
    assert plan.ertraege == 20_280_001.0
    assert plan.aufwendungen == 19_989_470.0
    assert plan.ergebnis == 290_531.0
    assert len(proben) == 6 and all(p.geht_auf for p in proben)


def test_das_ergebnis_ist_nicht_das_jahresergebnis():
    """Dieselbe Falle wie in Layout B, nur mit anderem Wort: Unter dem
    Gesamtergebnis (290.531 €) steht noch ein „Jahresergebnis" (93.031 €) —
    die Differenz ist die Eigenkapitalverzinsung an den städtischen Haushalt."""
    plan, _ = parse_erfolgsplan("18/0741", "awb", 2019, LAYOUT_C)
    assert plan.ergebnis == 290_531.0
    assert plan.ergebnis != 93_031.0


# --------------------------------------------------------------------------
# (g) Die Skalen-Sperre
# --------------------------------------------------------------------------

def test_eine_tabelle_in_teur_wird_nicht_gelesen():
    """Die Spaltenprobe ist SKALENINVARIANT: Liegt eine ganze Spalte um den
    Faktor 1.000 daneben, kürzt sich der Faktor in `Erträge − Aufwendungen =
    Ergebnis` weg und die Probe geht auf. `TOLERANZ_EUR` kann das prinzipiell
    nicht sehen — deshalb eine eigene Sperre."""
    zeilen = LAYOUT_C.splitlines()
    i = kopfzeile_index(zeilen)
    zeilen[i - 1] += "  (alle Angaben in TEUR)"
    with pytest.raises(WirtschaftsplanFehler) as fehler:
        parse_erfolgsplan("18/0741", "awb", 2019, "\n".join(zeilen))
    assert "TEUR" in str(fehler.value)
    assert "skaleninvariant" in str(fehler.value)


@pytest.mark.parametrize("angabe", [
    "in TEUR", "in T€", "in T EUR", "in Tsd. EUR", "in Tausend Euro",
    "in Mio. €", "in Millionen Euro", "in Mrd. EUR",
])
def test_jede_schreibweise_der_einheit_sperrt(angabe):
    zeilen = LAYOUT_C.splitlines()
    i = kopfzeile_index(zeilen)
    zeilen[i - 1] += f"  ({angabe})"
    with pytest.raises(WirtschaftsplanFehler):
        parse_erfolgsplan("18/0741", "awb", 2019, "\n".join(zeilen))


def test_millionen_im_vorbericht_sperren_nicht():
    """Jeder Vorbericht redet irgendwo von „Mio. €". Wer darauf anspringt,
    kann keine einzige Tabelle mehr lesen — deshalb ein enges Fenster um die
    Kopfzeile statt einer Suche im ganzen Dokument."""
    plan, _ = parse_erfolgsplan("18/0741", "awb", 2019, VORBERICHT + LAYOUT_C)
    assert plan.ertraege == 20_280_001.0


def test_das_fenster_endet_wo_es_soll():
    """Vier Zeilen über der Kopfzeile — genug für Titel, Leerzeile,
    „Gewinn- und Verlustrechnung" und „(für alle Sparten)"."""
    zeilen = LAYOUT_C.splitlines()
    i = kopfzeile_index(zeilen)
    innen = list(zeilen); innen[i - KOPF_FENSTER] += " in TEUR"
    assert einheit_an_der_kopfzeile(innen, i) == "in TEUR"
    aussen = list(zeilen); aussen[i - KOPF_FENSTER - 1] += " in TEUR"
    assert einheit_an_der_kopfzeile(aussen, i) is None


def test_volle_euro_werden_nicht_gesperrt():
    """Die Gegenprobe: Ohne Einheiten-Angabe passiert nichts."""
    zeilen = LAYOUT_C.splitlines()
    assert einheit_an_der_kopfzeile(zeilen, kopfzeile_index(zeilen)) is None
    for text in (LAYOUT_A, LAYOUT_B):
        assert einheit_an_der_kopfzeile(text.splitlines(),
                                        kopfzeile_index(text.splitlines(), 4)) is None
