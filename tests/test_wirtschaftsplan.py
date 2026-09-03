"""Die Wirtschaftspläne der Eigenbetriebe — Eckwerte aus dem Beschlusstext.

Die Ausschnitte sind **echte** Beschlussvorschläge aus dem Bestand (Vorlagen
25/0722 und 18/0880), samt ihrer Eigenheiten: Zeilenumbrüche mitten im Wort,
Vorzeichen durch Leerraum vom Betrag getrennt, „EUR" gegen „Euro", und die
Steuerzeile, die es vor 2021 nicht gab. Gekürzt ist nur, was zwischen den
Zahlen steht.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from council.wirtschaftsplan import (  # noqa: E402
    TOLERANZ_EUR,
    Wirtschaftsplan,
    WirtschaftsplanFehler,
    betrieb_aus_titel,
    herkunft_fuer,
    ohne_eckwerte,
    parse_wirtschaftsplan,
)

TITEL_2026 = ("Wirtschaftsplan des Eigenbetriebes Gebäudewirtschaft und Hochbau "
              "der Stadt Oldenburg 2026 - Beschluss")

# Vorlage 25/0722, wörtlich — inklusive der Leerräume zwischen Vorzeichen und
# Betrag, die das PDF aus zwei Tabellenzellen erzeugt.
TEXT_2026 = """Beschlussvorschlag:

Der Wirtschaftsplan des Eigenbetriebes Gebäudewirtschaft und Hochbau der Stadt
Oldenburg für das Haushaltsjahr 2026 wird


im Erfolgsplan

mit Erträgen von 82.815.150 Euro
mit Aufwendungen von 82.824.771 Euro
mit steuerlichen Aufwendungen von                                      6.000 Euro
und einem Jahresergebnis von                                    -       15.621 Euro


und im Vermögensplan

mit Einzahlungen und Auszahlungen von je 51.134.100 Euro
und Verpflichtungsermächtigungen von 104.980.000 Euro

in der Fassung des Verwaltungsentwurfes vom 01.10.2025 - unter Einbeziehung der sich aus
den Beschlüssen des Ausschusses für Finanzen und Beteiligungen und des
Verwaltungsausschusses ergebenden Änderungen sowie der Stellenübersicht -
beschlossen.
"""

TITEL_2019 = ("Wirtschaftsplan des Eigenbetriebes Gebäudewirtschaft und Hochbau "
              "der Stadt Oldenburg 2019")

# Vorlage 18/0880: „EUR", keine Steuerzeile, positives Ergebnis mit „+", und
# ein Wort, das über den Zeilenumbruch getrennt ist („Olden-\nburg").
TEXT_2019 = """Beschlussvorschlag:

Der Wirtschaftsplan des Eigenbetriebes Gebäudewirtschaft und Hochbau der Stadt Olden-
burg für das Haushaltsjahr 2019 wird

im Erfolgsplan

mit Erträgen von 60.763.500 EUR
mit Aufwendungen von 60.413.800 EUR
und einem Jahresergebnis von + 349.700 EUR

und im Vermögensplan

mit Einzahlungen und Auszahlungen von je 38.612.100 EUR
und Verpflichtungsermächtigungen von 43.666.000 EUR

in der Fassung des Verwaltungsentwurfes vom 05.10.2018 - unter Einbeziehung der sich
aus den Beschlüssen des Ausschusses für Finanzen und Beteiligungen beschlossen.
"""

# Vorlage 25/0818 — der Normalfall außerhalb des EGH: keine Zahl im Beschluss.
TITEL_BBO = "Bäderbetrieb der Stadt Oldenburg (BBO): Wirtschaftsplan 2026 - Beschluss"
TEXT_BBO = """Beschlussvorschlag:
Dem Wirtschaftsplan 2026 des Eigenbetriebes „Bäderbetrieb der Stadt Oldenburg (Oldb)"
(BBO) wird in der als Anlage beigefügten Fassung zugestimmt.

Anlass:
Der Vermögensplan weist Investitionen in Höhe von 15.902.000 Euro aus.
"""


# --------------------------------------------------------------------------
# (a) Der aktuelle Aufbau
# --------------------------------------------------------------------------

def test_liest_die_eckwerte_des_aktuellen_jahrgangs():
    p = parse_wirtschaftsplan("25/0722", TITEL_2026, TEXT_2026)
    assert isinstance(p, Wirtschaftsplan)
    assert p.enterprise == "egh"
    assert p.year == 2026, "das Haushaltsjahr, nicht das Jahr der Vorlage (2025)"
    assert p.revenues == 82_815_150.0
    assert p.expenses == 82_824_771.0
    assert p.taxes == 6_000.0
    assert p.result == -15_621.0
    assert p.capital_plan == 51_134_100.0
    assert p.commitments == 104_980_000.0
    assert p.draft_date == "01.10.2025"


def test_das_vorzeichen_ueberlebt_den_leerraum():
    """„-       15.621" kommt aus zwei Tabellenzellen. Wird das Minus
    verschluckt, wird aus einem Fehlbetrag ein Überschuss — und die Probe
    fiele nicht darauf herein, weil sie dieselbe Zahl prüft."""
    p = parse_wirtschaftsplan("25/0722", TITEL_2026, TEXT_2026)
    assert p.result < 0


def test_die_probe_des_dokuments_geht_auf():
    p = parse_wirtschaftsplan("25/0722", TITEL_2026, TEXT_2026)
    rest = p.revenues - p.expenses - p.taxes - p.result
    assert abs(rest) <= TOLERANZ_EUR
    assert "geht auf" in p.probe_result


# --------------------------------------------------------------------------
# (b) Der alte Aufbau
# --------------------------------------------------------------------------

def test_liest_den_alten_aufbau_ohne_steuerzeile():
    """2019/2020: „EUR", kein steuerlicher Aufwand, „+" vor dem Ergebnis —
    und ein Wort, das über den Zeilenumbruch getrennt ist."""
    p = parse_wirtschaftsplan("18/0880", TITEL_2019, TEXT_2019)
    assert p.year == 2019
    assert p.taxes == 0.0, "keine Steuerzeile heißt 0, nicht None"
    assert p.result == 349_700.0
    assert abs(p.revenues - p.expenses - p.taxes - p.result) <= TOLERANZ_EUR


# --------------------------------------------------------------------------
# (c) Was NICHT gelesen wird — und dass es auffällt
# --------------------------------------------------------------------------

def test_ohne_eckwerte_kommt_nichts_zurueck():
    """Der Normalfall außerhalb des EGH ist `None` und **kein** Fehler.

    Wichtig ist der zweite Teil: Im Anlass-Absatz steht sehr wohl eine Zahl
    (15.902.000 Euro Investitionen). Ein Parser, der irgendeinen Betrag aus
    dem Fließtext zöge, lieferte hier eine Zahl ohne Gegenprobe — und sie
    stünde in derselben Tabelle wie die geprüften."""
    assert parse_wirtschaftsplan("25/0818", TITEL_BBO, TEXT_BBO) is None


def test_die_luecke_wird_benannt():
    lücke = ohne_eckwerte("25/0818", TITEL_BBO)
    assert lücke["enterprise"] == "bbo"
    assert "Anlage" in lücke["reason"]


def test_gerissene_probe_wirft():
    """Eine Zahl verstellt: Das Dokument widerspricht sich, und Schweigen wäre
    die schlechteste Antwort."""
    kaputt = TEXT_2026.replace("82.815.150", "82.815.999")
    with pytest.raises(WirtschaftsplanFehler) as fehler:
        parse_wirtschaftsplan("25/0722", TITEL_2026, kaputt)
    assert "geht nicht auf" in str(fehler.value)


def test_jahresprobe_faengt_das_falsche_jahr():
    """Fließtext und Titel müssen dasselbe Jahr nennen. Der Fall ist real
    denkbar: Eine Vorlage vom Oktober 2025 beschließt das Jahr 2026."""
    with pytest.raises(WirtschaftsplanFehler) as fehler:
        parse_wirtschaftsplan("25/0722", TITEL_2026.replace("2026", "2025"), TEXT_2026)
    assert "steht so nicht im Titel" in str(fehler.value)


def test_unbekannter_betrieb_wirft_statt_zu_raten():
    with pytest.raises(WirtschaftsplanFehler) as fehler:
        parse_wirtschaftsplan("25/0722", "Wirtschaftsplan 2026 der Sonstwas GmbH",
                              TEXT_2026)
    assert "Betrieb ist unbekannt" in str(fehler.value)


def test_betriebe_werden_am_titel_erkannt():
    assert betrieb_aus_titel(TITEL_2026)[0] == "egh"
    assert betrieb_aus_titel(TITEL_BBO)[0] == "bbo"
    assert betrieb_aus_titel("Wirtschaftsplan und Finanzplan 2026 für den "
                             "Abfallwirtschaftsbetrieb")[0] == "awb"
    assert betrieb_aus_titel("Bäderbetriebsgesellschaft Oldenburg mbH (BBGO): "
                             "Wirtschaftsplan 2026")[0] == "bbgo"
    assert betrieb_aus_titel("Wirtschaftsplan 2017 - Prognosebericht") is None


# --------------------------------------------------------------------------
# (d) Herkunft
# --------------------------------------------------------------------------

def test_die_herkunft_zeigt_auf_die_vorlage_und_nennt_den_stand():
    """Die einzige Finanz-Schicht, deren Quelle die Vorlage selbst ist — und
    der Stand gehört dazu: Es ist der Verwaltungsentwurf, nicht der
    Beschluss."""
    p = parse_wirtschaftsplan("25/0722", TITEL_2026, TEXT_2026)
    h = herkunft_fuer(p, url="https://buergerinfo.oldenburg.de/vo0050.php?__kvonr=28214")
    assert h.kind == "ris"
    assert "Beschlussvorschlag" in h.citation
    assert "01.10.2025" in h.as_of
    assert "geht auf" in h.probe_result


def test_speichern_und_lesen(tmp_path):
    from council.store import CouncilStore

    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        p = parse_wirtschaftsplan("25/0722", TITEL_2026, TEXT_2026)
        store.save_wirtschaftsplan(p, herkunft_fuer(p, url="https://example.org/x"))
        # Zweimal speichern ändert nichts — derselbe Betrieb, dasselbe Jahr.
        store.save_wirtschaftsplan(p, herkunft_fuer(p, url="https://example.org/x"))
        zeilen = store.get_wirtschaftsplaene("egh")
        assert len(zeilen) == 1
        assert zeilen[0]["result"] == -15_621.0
        assert zeilen[0]["enterprise_name"].startswith("Eigenbetrieb Gebäudewirtschaft")
        assert "business_plan_profit_loss" in zeilen[0]["probes"]
        assert store.wirtschaftsplan_jahre("egh") == [2026]
        assert store.wirtschaftsplan_jahre("bbo") == []
    finally:
        store.close()


def test_jede_zeile_traegt_ihre_herkunft(tmp_path):
    """Der Befund aus #660 als Wächter: Eine Zieltabelle, die ihre
    `herkunft_id` nicht füllt, ist eine Zahl ohne Beleg."""
    from council.store import CouncilStore

    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        for nr, title, text in (("25/0722", TITEL_2026, TEXT_2026),
                                ("18/0880", TITEL_2019, TEXT_2019)):
            p = parse_wirtschaftsplan(nr, title, text)
            store.save_wirtschaftsplan(p, herkunft_fuer(p, url="https://example.org/x"))
        assert "council_business_plans" not in store.herkunft_luecken()
    finally:
        store.close()
