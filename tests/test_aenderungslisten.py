"""Wächter über die Änderungslisten-Extraktion (council/aenderungslisten.py).

Die Wort-Fixtures sind handgebaute MINIATUREN nach den gemessenen Koordinaten
der echten Dokumente (300528 u. a.): Kopfwörter, Spaltenkanten und
Grundlinien stimmen mit dem Original überein, der Inhalt ist auf das
reduziert, was die jeweilige Regel prüft. Die echten 18 PDFs (2019–2026)
liefen beim Bau vollständig durch — hier stehen die Regeln, nicht die PDFs.
"""
from __future__ import annotations

import pytest

from council.aenderungslisten import (
    ListenFehler,
    liste_aus_label,
    parse_ehh_seiten,
)

# ------------------------------------------------------------ Label-Sortierung

#: Echte Labels aus council_anlagen — jedes Muster, das der Bestand führt.
LABELS = [
    ("2026 EHH Änderungsliste Verwaltung I", "verwaltung_1"),
    ("2026 EHH Änderungsliste Verwaltung III", "verwaltung_3"),
    ("2025 EHH Änderungsliste Verwaltung II", "verwaltung_2"),
    ("Ergebnishaushalt, Änderungsliste Verwaltung I", "verwaltung_1"),
    ("Ergebnishaushalt, Änderungsliste Verw. I", "verwaltung_1"),      # 2019–2021
    ("Ergebnishaushalt, Änderungsliste Verw. II", "verwaltung_2"),
    ("2026 EHH beschlossene Änderungen AFB", "afb_beschlossen"),
    ("EHH beschlossene Änderungen AFB am 20.01.2021", "afb_beschlossen"),
    ("Ergebnishaushalt, beschlossene Änderungen AFB am 20.01.2021", "afb_beschlossen"),
    ("2 EHH beschlossene Änderungen AFB am 15.01.2020", "afb_beschlossen"),
    # Was draußen bleibt: anderer Haushalt oder andere Bauform.
    ("2026 FHH Änderungsliste Verwaltung I", None),
    ("2026 EHH Änderungsliste Verwaltung I EGH", None),
    ("EGH - Ergebnishaushalt, beschlossene Änderungen AFB am 20.01.2021", None),
    ("Klävemann-Stiftung - Ergebnishaushalt, Änderungsliste Verwaltung I", None),
    ("Ver. Old. Sozialstiftung - Ergebnishaushalt, Änderungsliste Verw. I", None),
    ("WFO-Änderungsliste Ergebnishaushalt (Stand 20.01.2021)", None),
    ("BBO - Finanzhaushalt, beschlossene Änderungen AFB am 20.01.2021", None),
    ("2026 EHH (Erfolgsplan) EGH - beschlossene Änderungen AFB", None),
    ("2026 EHH Synopse", None),
    ("Änderungsantrag der CDU-Fraktion", None),
]


@pytest.mark.parametrize(("label", "erwartet"), LABELS)
def test_label_sortierung(label, erwartet):
    assert liste_aus_label(label) == erwartet


# ------------------------------------------------- Fixtures: Wort-Miniaturen

def w(x0, x1, y, text):
    return (float(x0), float(x1), float(y), text)


def betrag(text, x1, y):
    """Ein rechtsbündiger Betrag: die rechte Kante ist die Aussage."""
    return w(x1 - 4 * len(text), x1, y, text)


#: Kopfgeometrie wie auf den Tabellenseiten von 300528 gemessen.
def kopf(jahr):
    return [
        w(390, 441, 30, "Änderungen"), w(444, 462, 30, str(jahr)),
        w(222.6, 271.2, 50, "Bezeichnung"),
        w(383.4, 407.0, 52, "Ertrag"), w(442.0, 475.5, 52, "Aufwand"),
        w(600.0, 655.0, 50, "Erläuterungen"),
    ]


def position(y, lfd, thh, beitraege, produkt="P10.111011.003",
             bezeichnung=("Kommunikation",), seite="300"):
    """Eine Positionszeile: Nummern links, Beträge rechtsbündig in den
    Spalten (Ertrag endet um 407, Aufwand um 470)."""
    aus = [w(70, 79, y, str(lfd)), w(92, 101, y, thh)]
    if seite:
        aus.append(w(118, 131, y, seite))
    if produkt:
        aus.append(w(152, 210, y, produkt))
    x = 223
    for teil in bezeichnung:
        aus.append(w(x, x + 5 * len(teil), y, teil))
        x += 5 * len(teil) + 5
    for text, spalte in beitraege:
        aus.append(betrag(text, 407 if spalte == "e" else 470, y))
    return aus


def summenblock(jahr, zeilen, ueberschrift=None):
    """Ein Zusammenstellungs-Block als Wortzeilen (eigene Seite, kein
    Tabellenkopf). `zeilen`: (vorlabel, e, a, s, nachlabel)."""
    aus = []
    y = 30
    aus.append(w(200, 380, y, ueberschrift if ueberschrift is not None
                else f"Ergebnishaushalt {jahr}"))
    for vor, e, a, s, nach in zeilen:
        y += 20
        x = 40
        for teil in vor.split():
            aus.append(w(x, x + 5 * len(teil), y, teil))
            x += 5 * len(teil) + 5
        for text in (e, a, s):
            x = max(x, 300)
            aus.append(w(x, x + 4 * len(text), y, text))
            x += 4 * len(text) + 20
        for teil in nach.split():
            aus.append(w(x, x + 5 * len(teil), y, teil))
            x += 5 * len(teil) + 5
    return aus


def test_miniliste_rundlauf():
    """Der Normalfall: vier Positions-Formen, eine Liste, alle Proben grün."""
    deckblatt = [w(100, 200, 50, "Änderungsliste"), w(100, 160, 70, "Stand:"),
                 w(165, 220, 70, "24.11.2025")]
    tabelle = kopf(2026) + [
        # zweispaltig · einspaltig Aufwand · einspaltig Ertrag (negativ,
        # ungepunktet ginge auch) · Vermerk über „alle" THH ohne Betrag.
        *position(100, 1, "01", [("22.389", "e"), ("89.554", "a")]),
        *position(130, 2, "03", [("200.000", "a")], bezeichnung=("Fliegerhorst",)),
        *position(160, 3, "04", [("-4.400.000", "e")],
                  bezeichnung=("Allgemeine", "Finanzwirtschaft")),
        *position(190, 4, "alle", [], produkt=None, seite=None,
                  bezeichnung=("diverse",)),
        # Erläuterungs-Zahl weit rechts — darf kein Betrag werden.
        w(560, 600, 100, "1.234.567"), w(602, 630, 100, "Euro"),
    ]
    summen = summenblock(2026, [
        ("Verwaltungsentwurf, Stand: 01.10.2025",
         "100.000.000", "90.000.000", "10.000.000", ""),
        ("Änderungsliste Verw. I", "-4.377.611", "289.554", "-4.667.165", ""),
        ("Überschuss/ Fehlbedarf", "95.622.389", "90.289.554", "5.332.835", ""),
    ])

    aus = parse_ehh_seiten([deckblatt, tabelle, summen])

    assert aus.stand == "24.11.2025"
    assert aus.jahrgang == 2026
    assert aus.eigene_zeile == {2026: "Änderungsliste Verw. I"}
    z1, z2, z3, z4 = aus.zeilen
    assert (z1.ertrag, z1.aufwand) == (22_389, 89_554)
    assert (z2.ertrag, z2.aufwand) == (None, 200_000)
    assert z2.bezeichnung == "Fliegerhorst"
    assert (z3.ertrag, z3.aufwand) == (-4_400_000, None)
    assert z1.seite_entwurf == 300 and z1.produkt == "P10.111011.003"
    assert z4.thh is None and z4.ertrag is None and z4.aufwand is None


def test_falsche_spalte_reisst():
    """Stünde ein Betrag in der falschen Spalte, ginge die Positionsprobe
    nicht auf — genau dafür ist sie da."""
    tabelle = kopf(2026) + [
        *position(100, 1, "01", [("22.389", "a")]),   # gehörte nach „e"
    ]
    summen = summenblock(2026, [
        ("Verwaltungsentwurf", "100.000.000", "90.000.000", "10.000.000", ""),
        ("Änderungsliste Verw. I", "22.389", "0", "22.389", ""),
        ("Überschuss/ Fehlbedarf", "100.022.389", "90.000.000", "10.022.389", ""),
    ])
    with pytest.raises(ListenFehler, match="Positionsprobe"):
        parse_ehh_seiten([tabelle, summen])


def test_summenzeile_mit_ungepunkteter_null():
    """„−390.000 0 −390.000“ ist eine echte Summenzeile (244160, Block 2023)."""
    tabelle = kopf(2022) + [*position(100, 1, "01", [("-390.000", "e")])]
    summen = summenblock(2022, [
        ("Verwaltungsentwurf", "100.000.000", "90.000.000", "10.000.000", ""),
        ("Änderungsliste Verw. II", "-390.000", "0", "-390.000", ""),
        ("Überschuss/ Fehlbedarf", "99.610.000", "90.000.000", "9.610.000", ""),
    ])
    aus = parse_ehh_seiten([tabelle, summen])
    assert aus.eigene_zeile == {2022: "Änderungsliste Verw. II"}


def test_afb_uebersicht_mit_fraktionszeile():
    """Die frühe AFB-Bauform: nacktes Jahr als Überschrift, „Verw.-Entwurf“,
    die politische Liste OHNE Stichwort — nur Beträge plus Urheber-Label."""
    tabelle = kopf(2021) + [
        *position(100, 1, "01", [("988.200", "e")]),
        *position(130, 2, "02", [("1.728.605", "a")]),
    ]
    summen = summenblock(2021, [
        ("Verw.-Entwurf v. 07.10.2020", "100.000.000", "90.000.000", "10.000.000", ""),
        ("Änderungsliste v. 19.11.2020", "988.200", "0", "988.200", "Verw. I"),
        ("", "0", "1.728.605", "-1.728.605", "SPD/ BÜNDNIS 90/DIE GRÜNEN"),
        ("Überschuss/ Fehlbedarf:", "100.988.200", "91.728.605", "9.259.595", ""),
    ], ueberschrift="2021")
    aus = parse_ehh_seiten([tabelle, summen])
    assert aus.eigene_zeile == {2021: "alle"}
    labels = {s.label for s in aus.summen if s.typ == "liste"}
    assert "SPD/ BÜNDNIS 90/DIE GRÜNEN" in labels


def test_kettenriss_faellt_auf_endsumme_minus_entwurf():
    """Weist die Zusammenstellung ihre Endsumme nicht vollständig aus
    (2026er-AFB vor der Politik-Zeile), trägt „Endsumme − Entwurf“."""
    tabelle = kopf(2026) + [
        *position(100, 1, "01", [("100.000", "e")]),
        *position(130, 2, "02", [("50.000", "a")]),
    ]
    summen = summenblock(2026, [
        ("Verwaltungsentwurf", "100.000.000", "90.000.000", "10.000.000", ""),
        # Die ausgewiesene Liste erklärt die Endsumme NICHT (50.000 fehlen).
        ("Änderungsliste Verw. I", "100.000", "0", "100.000", ""),
        ("Überschuss/ Fehlbedarf", "100.100.000", "90.050.000", "10.050.000", ""),
    ])
    aus = parse_ehh_seiten([tabelle, summen])
    assert aus.eigene_zeile == {2026: "beschlossen"}


def test_wickel_nachlese():
    """Mehrzeilige Bezeichnungen: eindeutige Fragmente werden angebaut, auch
    wenn auf ihrer Grundlinie Erläuterungs-Text weiterläuft — mehrdeutige
    bleiben liegen (lieber Lücke als falscher Name)."""
    tabelle = kopf(2026) + [
        w(264, 337, 92, "Verbraucherschutz"), w(339, 353, 92, "und"),
        w(521, 620, 92, "Lebensmittelkontrolleuren"),   # Erläuterung, stört nicht
        *position(100, 1, "05", [("26.000", "a")], bezeichnung=()),
        w(279, 339, 108, "Veterinärwesen"),
        # Zwei dicht folgende Positionen, ein Fragment GENAU dazwischen —
        # nicht eindeutig, wird verworfen.
        *position(150, 2, "06", [("10.000", "e")], bezeichnung=()),
        w(264, 300, 160, "Zweifelsfall"),
        *position(170, 3, "07", [("20.000", "e")], bezeichnung=()),
    ]
    summen = summenblock(2026, [
        ("Verwaltungsentwurf", "100.000.000", "90.000.000", "10.000.000", ""),
        ("Änderungsliste Verw. I", "30.000", "26.000", "4.000", ""),
        ("Überschuss/ Fehlbedarf", "100.030.000", "90.026.000", "10.004.000", ""),
    ])
    aus = parse_ehh_seiten([tabelle, summen])
    z1, z2, z3 = aus.zeilen
    assert z1.bezeichnung == "Verbraucherschutz und Veterinärwesen"
    assert z2.bezeichnung == "" and z3.bezeichnung == ""
