"""Wächter über die FHH-Änderungslisten (council/aenderungslisten_fhh.py).

Die Wort-Fixtures sind handgebaute MINIATUREN nach den gemessenen Koordinaten
der echten Dokumente (300530, 210923, 244466 u. a.): Linienraster,
Spaltenkanten und Grundlinien stimmen mit dem Original überein, der Inhalt
ist auf das reduziert, was die jeweilige Regel prüft.

Jede Regel hier hat einen Riss im echten Bestand als Anlass — die Kommentare
nennen ihn, damit niemand sie später für Übervorsicht hält und wegräumt.
"""
from __future__ import annotations

import pytest

from council.aenderungslisten_fhh import (
    ListenFehler,
    liste_aus_label,
    parse_fhh_seiten,
)


def w(x0, x1, y, text):
    return (float(x0), float(x1), float(y), text)


def amount(text, x1, y):
    """Ein rechtsbündiger Betrag: die rechte Kante ist die Aussage."""
    return w(x1 - 4 * len(text), x1, y, text)


#: Das Linienraster von 300530: elf Spalten, zwölf senkrechte Kanten.
#: Die fünf Betragsspalten liegen zwischen 313,8 und 581,7.
SENKRECHT = [51.2, 73.3, 98.1, 135.7, 198.1, 313.8, 367.6, 421.5, 475.4,
             529.3, 581.7, 789.7]
#: Rechte Kanten der fünf Betragsspalten — dort enden ihre Zahlen.
KANTE = {"soll": 365, "ein": 419, "aus": 473, "ve": 527, "neu": 579}


def linien(waagerecht, senkrecht=None):
    return ([float(y) for y in waagerecht],
            [float(x) for x in (SENKRECHT if senkrecht is None else senkrecht)])


def kopf(year):
    """Der Tabellenkopf — samt seines „+ / −", das ein Gedankenstrich ist."""
    return [
        w(322, 339, 30, "Soll"), w(342, 358, 30, "laut"),
        w(408, 466, 30, "Änderungen"), w(469, 491, 30, str(year)),
        w(323, 357, 42, "Entwurf"), w(386, 403, 42, "Ein-"), w(439, 459, 42, "Aus-"),
        w(372, 417, 54, "zahlungen"), w(427, 472, 54, "zahlungen"),
        w(498, 510, 54, "VE"),
        # Die „+ / −"-Zeile: der Strich ist nach den Regeln des Moduls ein
        # Betrag (Null) und stand vor dem Zeilenmodell in JEDER Spalte.
        w(389, 400, 66, "+/-"), w(444, 455, 66, "+/-"), w(499, 510, 66, "+/-"),
        w(535, 562, 66, "neues"), w(564, 581, 66, "Soll"),
        w(226, 282, 78, "Bezeichnung"), w(660, 721, 78, "Erläuterungen"),
    ]


def position(y, lfd, thh, werte, produkt="I10.089904.500",
             bezeichnung=("Quartiersgarage",), seite="70"):
    """Eine Positionszeile. `werte`: dict aus KANTE-Schlüssel → Text."""
    aus = [w(54, 59, y, str(lfd)), w(78, 88, y, thh)]
    if seite:
        aus.append(w(105, 120, y, seite))
    if produkt:
        aus.append(w(134, 194, y, produkt))
    x = 200
    for teil in bezeichnung:
        aus.append(w(x, x + 5 * len(teil), y, teil))
        x += 5 * len(teil) + 5
    for feld, text in werte.items():
        aus.append(amount(text, KANTE[feld], y))
    return aus


def summenblock(year, zeilen):
    """Eine Zusammenstellungs-Seite: Kopfwörter und Zeilen.
    `zeilen`: (label, ein, aus, saldo, ve, urheber)."""
    aus = [w(180, 300, 20, "Zusammenstellung"), w(303, 330, 20, "der"),
           w(333, 430, 20, "Veränderungen"),
           w(360, 400, 32, str(year)),
           w(250, 310, 44, "Einzahlungen"), w(318, 381, 44, "Auszahlungen"),
           w(408, 434, 44, "Saldo"), w(483, 496, 44, "VE")]
    y = 60
    for label, ein, aus_, balance, ve, urheber in zeilen:
        y += 20
        x = 45
        for teil in label.split():
            aus.append(w(x, x + 5 * len(teil), y, teil))
            x += 5 * len(teil) + 5
        for text, kante in ((ein, 312), (aus_, 382), (balance, 455), (ve, 519)):
            if text is not None:
                aus.append(amount(text, kante, y))
        if urheber:
            x = 530
            for teil in urheber.split():
                aus.append(w(x, x + 5 * len(teil), y, teil))
                x += 5 * len(teil) + 5
    return aus


# ------------------------------------------------------------ Label-Sortierung

LABELS = [
    ("2026 FHH Änderungsliste Verwaltung I", "verwaltung_1"),
    ("2026 FHH Änderungsliste Verwaltung III", "verwaltung_3"),
    ("Finanzhaushalt, Änderungsliste Verw. II", "verwaltung_2"),
    ("2025 FHH Änderungsliste Verwaltung 1", "verwaltung_1"),
    ("2026 FHH beschlossene Änderungen AFB", "afb_beschlossen"),
    ("FHH beschlossene Änderungen AFB am 20.01.2021", "afb_beschlossen"),
    # Was draußen bleibt: andere Haushalte mit eigenen FHH-Listen …
    ("2026 FHH Änderungsliste Verwaltung I EGH", None),
    ("FHH BBO beschlossene Änderungen AFB am 20.01.2021", None),
    ("Klävemann-Stiftung - Finanzhaushalt, Änderungsliste Verwaltung I", None),
    ("WFO-Änderungsliste Finanzhaushalt (Stand: 20.01.2021)", None),
    # … und der Ergebnishaushalt, den das Nachbarmodul liest.
    ("2026 EHH Änderungsliste Verwaltung I", None),
    ("Ergebnishaushalt, beschlossene Änderungen AFB am 20.01.2021", None),
]


@pytest.mark.parametrize(("label", "erwartet"), LABELS)
def test_label_sortierung(label, erwartet):
    assert liste_aus_label(label) == erwartet


# --------------------------------------------------------------- Der Normalfall

def test_miniliste_rundlauf():
    """Fünf Betragsspalten, eine Liste, alle Proben grün."""
    tabelle = kopf(2026) + [
        *position(120, 1, "03", {"soll": "0", "ein": "0", "aus": "400.000",
                                 "neu": "400.000"}),
        *position(180, 2, "04", {"soll": "500.000", "ein": "0", "aus": "230.000",
                                 "neu": "730.000"},
                  produkt="I10.093753.520", bezeichnung=("VHS",)),
    ]
    summen = summenblock(2026, [
        ("Verwaltungsentwurf Stand: 01.10.25", "31.350.463", "93.502.920",
         "-62.152.457", "0", None),
        ("Änderungsliste Verw. I", "0", "630.000", "-630.000", "0", None),
        ("", "31.350.463", "94.132.920", "-62.782.457", "0", None),
    ])
    aus = parse_fhh_seiten([tabelle, summen], [linien([100, 150, 210]), linien([], [])])

    z1, z2 = aus.zeilen
    assert (z1.lfd, z1.thh, z1.produkt) == (1, 3, "I10.089904.500")
    assert (z1.planned_draft, z1.inflow, z1.outflow, z1.planned_new) == (
        0, 0, 400_000, 400_000)
    assert z2.bezeichnung == "VHS"
    assert z2.planned_new == 730_000
    # Die Zusammenstellung: Entwurf, eine Liste, die Endsumme ohne Beschriftung.
    assert [s.typ for s in aus.summen] == ["entwurf", "liste", "endsumme"]
    assert aus.summen[1].ve == 0


def test_zeilenprobe_reisst_bei_verrutschter_spalte():
    """Die schärfste Probe des Moduls: Jede Zeile rechnet sich selbst vor.
    Landet ein Betrag eine Spalte daneben, geht sie nicht auf."""
    tabelle = kopf(2026) + [
        # 500.000 + 0 + 230.000 ≠ 400.000 — so sähe eine verrutschte Spalte aus.
        *position(120, 1, "03", {"soll": "500.000", "ein": "0", "aus": "230.000",
                                 "neu": "400.000"}),
    ]
    summen = summenblock(2026, [
        ("Verwaltungsentwurf Stand: 01.10.25", "0", "0", "0", "0", None),
        ("Änderungsliste Verw. I", "0", "230.000", "-230.000", "0", None),
        ("", "0", "230.000", "-230.000", "0", None),
    ])
    with pytest.raises(ListenFehler, match="Zeilenprobe"):
        parse_fhh_seiten([tabelle, summen], [linien([100, 150]), linien([], [])])


# ------------------------------------------------------- Die gefundenen Fallen

def test_kopf_und_fusszeile_bleiben_draussen():
    """Der Tabellenkopf trägt „+/-" über jeder Spalte — ein Gedankenstrich und
    damit ein Betrag (Null). Die Fußzeile setzt ihre Seitenzahl in die
    Auszahlungs-Spalte. Beides gehört zu keiner Position: Der Kopf steht über
    der ersten, die Fußzeile unter dem Rahmen."""
    tabelle = kopf(2026) + [
        *position(120, 1, "03", {"soll": "0", "ein": "0", "aus": "400.000",
                                 "neu": "400.000"}),
        w(430, 434, 260, "3"),          # Fußzeile „Seite 3"
    ]
    summen = summenblock(2026, [
        ("Verwaltungsentwurf Stand: 01.10.25", "0", "0", "0", "0", None),
        ("Änderungsliste Verw. I", "0", "400.000", "-400.000", "0", None),
        ("", "0", "400.000", "-400.000", "0", None),
    ])
    aus = parse_fhh_seiten([tabelle, summen], [linien([100, 200]), linien([], [])])
    z = aus.zeilen[0]
    assert (z.planned_draft, z.inflow, z.outflow, z.planned_new) == (
        0, 0, 400_000, 400_000)


def test_betraege_unter_der_grundlinie():
    """Ein Teil des Bestands setzt die Beträge 44 bis 67 pt UNTER die
    Positionszeile (210923) — dort liegt jeder näher an der FOLGENDEN
    Position. Nach Abstand zugeordnet rutschte alles um eine Zeile."""
    tabelle = kopf(2026) + [
        *position(104, 1, "03", {}),
        *position(182, 2, "04", {}, produkt="I10.093753.520",
                  bezeichnung=("Zweites",)),
        # Die Beträge zu Position 1 stehen 67 pt tiefer, die zu Position 2
        # 45 pt — beide vor der jeweils nächsten Position.
        *[amount(t, KANTE[k], 171)
          for k, t in (("soll", "0"), ("aus", "577.000"), ("neu", "577.000"))],
        *[amount(t, KANTE[k], 227)
          for k, t in (("soll", "0"), ("aus", "30.000"), ("neu", "30.000"))],
    ]
    summen = summenblock(2026, [
        ("Verwaltungsentwurf Stand: 01.10.25", "0", "0", "0", "0", None),
        ("Änderungsliste Verw. I", "0", "607.000", "-607.000", "0", None),
        ("", "0", "607.000", "-607.000", "0", None),
    ])
    aus = parse_fhh_seiten([tabelle, summen], [linien([90, 260]), linien([], [])])
    z1, z2 = aus.zeilen
    assert z1.outflow == 577_000
    assert z2.outflow == 30_000


def test_summenzeile_des_blocks_ist_keine_position():
    """Unter der letzten Position steht die Summenzeile des Blocks, noch im
    Rahmen. Sie trägt kein „neues Soll" — daran ist sie zu erkennen. Ohne
    diesen Filter las 300530 jeden Betrag doppelt."""
    tabelle = kopf(2026) + [
        *position(120, 1, "03", {"soll": "0", "ein": "0", "aus": "400.000",
                                 "neu": "400.000"}),
        # Die Blocksumme: zwei Spalten, kein neues Soll.
        amount("-34.800", KANTE["ein"], 200),
        amount("400.000", KANTE["aus"], 200),
    ]
    summen = summenblock(2026, [
        ("Verwaltungsentwurf Stand: 01.10.25", "0", "0", "0", "0", None),
        ("Änderungsliste Verw. I", "0", "400.000", "-400.000", "0", None),
        ("", "0", "400.000", "-400.000", "0", None),
    ])
    aus = parse_fhh_seiten([tabelle, summen], [linien([100, 230]), linien([], [])])
    assert len(aus.zeilen) == 1
    assert aus.zeilen[0].outflow == 400_000


def test_klammerbetrag_und_einstelliger_teilhaushalt():
    """Zwei Schreibweisen aus dem Bestand: „(275.900)" als neues Soll (244466)
    und ein einstelliger Teilhaushalt „8" statt „08" (302945). Beides kostete
    vorher die ganze Position beziehungsweise das ganze Dokument."""
    tabelle = kopf(2026) + [
        *position(120, 1, "8", {"soll": "250.000", "aus": "25.900",
                                "neu": "(275.900)"}),
    ]
    summen = summenblock(2026, [
        ("Verwaltungsentwurf Stand: 01.10.25", "0", "0", "0", "0", None),
        ("Änderungsliste Verw. I", "0", "25.900", "-25.900", "0", None),
        ("", "0", "25.900", "-25.900", "0", None),
    ])
    aus = parse_fhh_seiten([tabelle, summen], [linien([100, 150]), linien([], [])])
    z = aus.zeilen[0]
    assert z.thh == 8
    assert z.planned_new == 275_900


def test_ohne_entwurf_und_endsumme():
    """Die Beschluss-Dateien führen je Block nur die Listen — kein
    Verwaltungsentwurf, keine Schlusszeile (212802 überschreibt seine Seite
    mit „Übersicht aller Änderungen"). Dann sind die Listen selbst die
    Referenz, und ihre Summe trägt die Positionsprobe."""
    tabelle = kopf(2026) + [
        *position(120, 1, "03", {"soll": "0", "ein": "0", "aus": "400.000",
                                 "neu": "400.000"}),
        *position(180, 2, "04", {"soll": "0", "ein": "0", "aus": "195.000",
                                 "neu": "195.000"}, bezeichnung=("Zweites",)),
    ]
    summen = summenblock(2026, [
        ("Änderungsliste Verw. I", "0", "400.000", "-400.000", None, None),
        # Die politische Zeile: Label NUR rechts, in der Spalte „Vorschlag von".
        ("", "0", "195.000", "-195.000", None, "SPD/ CDU/ FDP"),
    ])
    aus = parse_fhh_seiten([tabelle, summen], [linien([100, 150, 210]), linien([], [])])
    assert [s.typ for s in aus.summen] == ["liste", "liste"]
    assert aus.summen[1].label == "SPD/ CDU/ FDP"
    # Die Positionen treffen die Summe BEIDER Listen — das Dokument ist
    # kumuliert, keine einzelne Zeile summiert sie allein.
    assert aus.eigene_zeile[2026] == "alle"


def test_doppelt_gedruckte_position_wird_eine():
    """Der Bestand druckt Positionen über zwei Tabellenzeilen: gleiche Lfd.
    Nr., zwei Erläuterungsblöcke, Beträge nur einmal (210923, Position 3)."""
    tabelle = kopf(2026) + [
        *position(120, 3, "04", {"soll": "0", "ein": "0", "aus": "500.000",
                                 "neu": "500.000"}),
        *position(180, 3, "04", {}),
    ]
    summen = summenblock(2026, [
        ("Verwaltungsentwurf Stand: 01.10.25", "0", "0", "0", "0", None),
        ("Änderungsliste Verw. I", "0", "500.000", "-500.000", "0", None),
        ("", "0", "500.000", "-500.000", "0", None),
    ])
    aus = parse_fhh_seiten([tabelle, summen], [linien([100, 150, 210]), linien([], [])])
    assert len(aus.zeilen) == 1
    assert aus.zeilen[0].outflow == 500_000


def test_widerspruechliche_doppelzeile_reisst():
    """Zwei Zeilen mit derselben Lfd. Nr. und VERSCHIEDENEN Beträgen sind kein
    Umbruch, sondern ein Lesefehler — dann fällt das Dokument.

    Auf ZWEI Seiten, denn so tritt der Fall im Bestand auf (212802): Auf
    einer Seite fasst der Leser die Doppelzeile schon beim Zuordnen zusammen;
    über Seitengrenzen hinweg kann er das nicht, und erst dort zeigt sich der
    Widerspruch.
    """
    seite_a = kopf(2026) + [
        *position(120, 3, "04", {"soll": "0", "aus": "500.000", "neu": "500.000"}),
    ]
    seite_b = kopf(2026) + [
        *position(120, 3, "04", {"soll": "0", "aus": "300.000", "neu": "300.000"}),
    ]
    summen = summenblock(2026, [
        ("Verwaltungsentwurf Stand: 01.10.25", "0", "0", "0", "0", None),
        ("Änderungsliste Verw. I", "0", "800.000", "-800.000", "0", None),
        ("", "0", "800.000", "-800.000", "0", None),
    ])
    with pytest.raises(ListenFehler, match="steht zweimal"):
        parse_fhh_seiten(
            [seite_a, seite_b, summen],
            [linien([100, 150]), linien([100, 150]), linien([], [])])
