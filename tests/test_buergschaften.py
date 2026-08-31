"""Bürgschaftsbestand aus dem Jahresabschluss (council/buergschaften.py).

Die Fixtures sind gekürzte, aber **wörtliche** Auszüge der echten Anhänge
(Stand 18.08.2026); die Dokumentnummer steht jeweils dabei, damit sich das im
Bürgerinfo nachschlagen lässt. Jede beweist eine Falle, die beim Vermessen der
acht Jahrgänge aufgefallen ist.

Der Aufbau folgt ``tests/test_ausgabenreihe.py``.
"""
from council import buergschaften as b

# Dok 295294, Jahresabschluss 2024 der Kernverwaltung, Anhang 6.2.10.
# Die Trennstriche am Zeilenende stehen so im extrahierten Text.
ANHANG_2024 = """
6.2.10 Eventualverbindlichkeiten
Der Bürgschaftsbestand hat sich in 2024 von rd. 214,8 Millionen Euro
(31.12.2023) auf rd. 220,3 Millionen Euro (31.12.2024) erhöht. Hintergrund
ist, dass die verbürgten Bestandsdarlehen seitens der Beteiligungen getilgt
wurden. Gleichzeitig wurden in 2024 neue Bürgschaften vergeben, die die
Eventualverbindlichkeit aus Bürgschaften im Saldo um rund 5,5 Millionen Euro
anwachsen lassen.
6.3 Erläuterung der wesentlichen Positionen der Ergebnisrechnung
"""

# Dok 265440, Jahresabschluss 2022. Zwei Eigenheiten in einem Auszug:
# „im Jahr 2022" statt „in 2022", und die Überschrift „6.3" ist beim
# Extrahieren MITTEN in den Satz gerutscht.
ANHANG_2022 = """
6.2.10 Eventualverbindlichkeiten 6.3 Der Bürgschaftsbestand hat sich im Jahr
2022 von 83,7 Millionen Euro (31.12.2021) auf 217,6 Millionen Euro
(31.12.2022) erhöht. Der Grund für die deutliche Erhöhung ist die Übernahme
von Bürgschaften zu Gunsten des Klinikums Oldenburg AöR in Höhe von 135,9
Millionen Euro. Erläuterung der wesentlichen Positionen
"""

# Dok 219464, Jahresabschluss 2019 — die andere Darreichungsform: eine frühe
# Übersichtstabelle, auf den Cent.
TABELLE_2019 = """
EUR
Ermächtigungsübertragungen für investive Auszahlungen 36.859.359,07
Bürgschaftsverpflichtungen 74.991.739,16
Über das Jahr 2019 hinaus gestundete Beträge 1.154.733,39
"""

# Dok 250436, Jahresabschluss 2021 — nennt den Bestand NICHT. Der Auszug ist
# echt: Das Wort kommt im ganzen Dokument nur in Investitionszeilen vor.
OHNE_2021 = """
I10.700905.550 Tami-Oelfken-Straße, Bürgschaft -48.061,44 0,00 0,00
I10.700905.560 Tami-Oelfken-Straße, Beiträge 0,00 -50.000,00 0,00
"""


def test_anhang_liefert_beide_enden_und_den_grund():
    g = b.parse_bestand(ANHANG_2024, 2024)
    assert g["balance"] == 220_300_000.0
    assert g["exact"] is False          # „rd." — die Quelle rundet selbst
    assert g["quelle"] == "anhang"
    # Das zweite Ende ist der Anfangsbestand: die halbe Kettenprobe.
    assert g["prior_year_year"] == 2023
    assert g["prior_year_stock"] == 214_800_000.0
    assert "getilgt" in g["grund"]


def test_zweiundzwanzig_traegt_die_klinikums_zahl():
    """Der Jahrgang, der die Reihe erklärt — und zwei Layout-Fallen.

    „im Jahr 2022" statt „in 2022", und die Überschrift 6.3 steht mitten im
    Satz. Beides steht so im echten Text; ein Muster, das den Satzanfang
    verankert, findet ihn nicht.
    """
    g = b.parse_bestand(ANHANG_2022, 2022)
    assert g["balance"] == 217_600_000.0
    assert g["prior_year_stock"] == 83_700_000.0
    # Die Zahl, ohne die der Sprung von 83,7 auf 217,6 unerklärt dasteht.
    assert b.klinikum_amount(g) == 135_900_000.0
    assert "Klinikum" in g["grund"]


def test_die_frueheren_jahrgaenge_kommen_auf_den_cent():
    g = b.parse_bestand(TABELLE_2019, 2019)
    assert g["balance"] == 74_991_739.16
    assert g["exact"] is True           # keine Rundung — das darf die Anzeige zeigen
    assert g["quelle"] == "tabelle"
    assert "prior_year_stock" not in g   # die Tabelle nennt nur ein Ende


def test_ein_jahrgang_ohne_bestand_erfindet_keinen():
    """2021 nennt den Bestand nicht. Dann kommt nichts — nicht die 0."""
    assert b.parse_bestand(OHNE_2021, 2021) is None


def test_die_luecke_wird_nur_dort_aus_dem_folgejahr_gefuellt_wo_sie_ist():
    """Der Nachtrag darf keinen Jahrgang überschreiben, der selbst spricht.

    Ab 2022 nennt JEDER Jahrgang auch den Vorjahresstand. Wer die alle
    übernimmt, ersetzt 2019 und 2020 durch gerundete Zweitnennungen und
    verliert dabei die Cent-Genauigkeit.
    """
    gefunden = [b.parse_bestand(TABELLE_2019, 2019),
                b.parse_bestand(ANHANG_2022, 2022),
                b.parse_bestand(ANHANG_2024, 2024)]
    r = b.series(gefunden)
    # 2021 und 2023 fehlen in dieser Auswahl und werden beide zu Recht aus dem
    # Anfangsbestand des Folgejahrs ergänzt.
    assert [z["year"] for z in r] == [2019, 2021, 2022, 2023, 2024]
    nachgetragen = {z["year"] for z in r if z["out_next_year"]}
    assert nachgetragen == {2021, 2023}

    # Der eigentliche Punkt: 2019, 2022 und 2024 sprechen selbst und behalten
    # ihre eigene Fundstelle — 2019 samt Cent-Genauigkeit.
    for z in r:
        if z["year"] in {2019, 2022, 2024}:
            assert z["out_next_year"] is False, z["year"]
    assert r[0]["exact"] is True and r[0]["balance"] == 74_991_739.16


def test_kettenprobe_findet_einen_widerspruch():
    """Zwei Dokumente, dieselbe Zahl — sonst reißt die Kette.

    Die Probe ist kein Rechenweg von uns: Der Anfangsbestand steht im einen
    Dokument, der Endbestand im anderen.
    """
    echt = [b.parse_bestand(ANHANG_2022, 2022), b.parse_bestand(ANHANG_2024, 2024)]
    assert b.kettenprobe(echt) == []        # 2024 kennt 2023 nicht → kein Riss

    gefaelscht = b.parse_bestand(ANHANG_2024, 2024)
    zerissen = [{**b.parse_bestand(ANHANG_2022, 2022), "year": 2023,
                 "balance": 200_000_000.0}, gefaelscht]
    risse = b.kettenprobe(zerissen)
    assert len(risse) == 1 and "214.8" in risse[0] and "200.0" in risse[0]


def test_rundungsdifferenz_ist_kein_riss():
    """Die Quelle rundet auf Zehntel-Millionen; zwei Rundungen dürfen sich um
    weniger als eine halbe Stelle unterscheiden, ohne dass jemand irrt."""
    a = {"year": 2023, "balance": 214_800_000.0, "out_next_year": False}
    b_ = {"year": 2024, "balance": 220_300_000.0, "out_next_year": False,
          "prior_year_year": 2023, "prior_year_stock": 214_760_000.0}
    assert b.kettenprobe([a, b_]) == []
