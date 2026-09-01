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

#: Tabellenlinien einer Seite, wie `seiten_linien` sie liefert.
def linien(waagerecht, senkrecht):
    return ([float(y) for y in waagerecht], [float(x) for x in senkrecht])

# ------------------------------------------------------------ Label-Sortierung

#: Echte Labels aus council_anlagen — jedes Muster, das der Bestand führt.
LABELS = [
    ("2026 EHH Änderungsliste Verwaltung I", "administration_1"),
    ("2026 EHH Änderungsliste Verwaltung III", "administration_3"),
    ("2025 EHH Änderungsliste Verwaltung II", "administration_2"),
    ("Ergebnishaushalt, Änderungsliste Verwaltung I", "administration_1"),
    ("Ergebnishaushalt, Änderungsliste Verw. I", "administration_1"),      # 2019–2021
    ("Ergebnishaushalt, Änderungsliste Verw. II", "administration_2"),
    ("2026 EHH beschlossene Änderungen AFB", "fc_decided"),
    ("EHH beschlossene Änderungen AFB am 20.01.2021", "fc_decided"),
    ("Ergebnishaushalt, beschlossene Änderungen AFB am 20.01.2021", "fc_decided"),
    ("2 EHH beschlossene Änderungen AFB am 15.01.2020", "fc_decided"),
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


def amount(text, x1, y):
    """Ein rechtsbündiger Betrag: die rechte Kante ist die Aussage."""
    return w(x1 - 4 * len(text), x1, y, text)


#: Kopfgeometrie wie auf den Tabellenseiten von 300528 gemessen.
def kopf(year):
    return [
        w(390, 441, 30, "Änderungen"), w(444, 462, 30, str(year)),
        w(222.6, 271.2, 50, "Bezeichnung"),
        w(383.4, 407.0, 52, "Ertrag"), w(442.0, 475.5, 52, "Aufwand"),
        w(600.0, 655.0, 50, "Erläuterungen"),
    ]


def position(y, seq, sub_budget, contributions, product="P10.111011.003",
             label=("Kommunikation",), page="300"):
    """Eine Positionszeile: Nummern links, Beträge rechtsbündig in den
    Spalten (Ertrag endet um 407, Aufwand um 470)."""
    aus = [w(70, 79, y, str(seq)), w(92, 101, y, sub_budget)]
    if page:
        aus.append(w(118, 131, y, page))
    if product:
        aus.append(w(152, 210, y, product))
    x = 223
    for part in label:
        aus.append(w(x, x + 5 * len(part), y, part))
        x += 5 * len(part) + 5
    for text, spalte in contributions:
        aus.append(amount(text, 407 if spalte == "e" else 470, y))
    return aus


def summenblock(year, zeilen, heading=None):
    """Ein Zusammenstellungs-Block als Wortzeilen (eigene Seite, kein
    Tabellenkopf). `zeilen`: (vorlabel, e, a, s, nachlabel)."""
    aus = []
    y = 30
    aus.append(w(200, 380, y, heading if heading is not None
                else f"Ergebnishaushalt {year}"))
    for vor, e, a, s, nach in zeilen:
        y += 20
        x = 40
        for part in vor.split():
            aus.append(w(x, x + 5 * len(part), y, part))
            x += 5 * len(part) + 5
        for text in (e, a, s):
            x = max(x, 300)
            aus.append(w(x, x + 4 * len(text), y, text))
            x += 4 * len(text) + 20
        for part in nach.split():
            aus.append(w(x, x + 5 * len(part), y, part))
            x += 5 * len(part) + 5
    return aus


def test_miniliste_rundlauf():
    """Der Normalfall: vier Positions-Formen, eine Liste, alle Proben grün."""
    deckblatt = [w(100, 200, 50, "Änderungsliste"), w(100, 160, 70, "Stand:"),
                 w(165, 220, 70, "24.11.2025")]
    tabelle = kopf(2026) + [
        # zweispaltig · einspaltig Aufwand · einspaltig Ertrag (negativ,
        # ungepunktet ginge auch) · Vermerk über „alle" THH ohne Betrag.
        *position(100, 1, "01", [("22.389", "e"), ("89.554", "a")]),
        *position(130, 2, "03", [("200.000", "a")], label=("Fliegerhorst",)),
        *position(160, 3, "04", [("-4.400.000", "e")],
                  label=("Allgemeine", "Finanzwirtschaft")),
        *position(190, 4, "alle", [], product=None, page=None,
                  label=("diverse",)),
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

    assert aus.as_of == "24.11.2025"
    assert aus.budget_year == 2026
    assert aus.eigene_zeile == {2026: "Änderungsliste Verw. I"}
    z1, z2, z3, z4 = aus.zeilen
    assert (z1.revenue, z1.expense) == (22_389, 89_554)
    assert (z2.revenue, z2.expense) == (None, 200_000)
    assert z2.label == "Fliegerhorst"
    assert (z3.revenue, z3.expense) == (-4_400_000, None)
    assert z1.page_draft == 300 and z1.product == "P10.111011.003"
    assert z4.sub_budget is None and z4.revenue is None and z4.expense is None
    # Ohne Tabellenlinien gibt es keine Erläuterungen — nie geraten.
    assert all(z.explanation is None for z in aus.zeilen)


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
    ], heading="2021")
    aus = parse_ehh_seiten([tabelle, summen])
    assert aus.eigene_zeile == {2021: "alle"}
    labels = {s.label for s in aus.summen if s.typ == "list"}
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
        *position(100, 1, "05", [("26.000", "a")], label=()),
        w(279, 339, 108, "Veterinärwesen"),
        # Zwei dicht folgende Positionen, ein Fragment GENAU dazwischen —
        # nicht eindeutig, wird verworfen.
        *position(150, 2, "06", [("10.000", "e")], label=()),
        w(264, 300, 160, "Zweifelsfall"),
        *position(170, 3, "07", [("20.000", "e")], label=()),
    ]
    summen = summenblock(2026, [
        ("Verwaltungsentwurf", "100.000.000", "90.000.000", "10.000.000", ""),
        ("Änderungsliste Verw. I", "30.000", "26.000", "4.000", ""),
        ("Überschuss/ Fehlbedarf", "100.030.000", "90.026.000", "10.004.000", ""),
    ])
    aus = parse_ehh_seiten([tabelle, summen])
    z1, z2, z3 = aus.zeilen
    assert z1.label == "Verbraucherschutz und Veterinärwesen"
    assert z2.label == "" and z3.label == ""


# ---------------------------------------------------------- Erläuterungs-Spalte

def test_erlaeuterungen_folgen_den_tabellenlinien():
    """Die Erläuterungs-Spalte hat keine Schlusssumme — die Zuordnung läuft
    über die Zeilenbänder der gedruckten Linien: mehrzeilig gewickelter Text
    landet an seiner Position, die Silbentrennung wird nur am GEMESSENEN
    Umbruch zusammengezogen (Ergänzungsstriche bleiben), und Fußzeilen
    außerhalb des Rasters bleiben draußen."""
    tabelle = kopf(2026) + [
        *position(100, 1, "01", [("22.389", "e")]),
        *position(130, 2, "03", [("200.000", "a")], label=("Fliegerhorst",)),
        # Erläuterung zu Position 1: drei Grundlinien im selben Band, ein
        # Trennstrich am Umbruch („Bescheini-/gungen“) und ein
        # Ergänzungsstrich am Umbruch („Brand-/und“).
        w(490, 520, 95, "Mittel"), w(522, 540, 95, "für"), w(542, 600, 95, "Bescheini-"),
        w(490, 530, 105, "gungen"), w(532, 545, 105, "im"), w(547, 590, 105, "Brand-"),
        w(490, 510, 115, "und"), w(512, 610, 115, "Katastrophenschutz."),
        # Erläuterung zu Position 2 — mit Zahl, die KEIN Betrag werden darf.
        w(490, 520, 133, "VWG:"), w(522, 570, 133, "Zuschuss"),
        w(572, 620, 133, "1.234.567"), w(622, 650, 133, "Euro."),
        # Fußzeile unterhalb des Linienrasters.
        w(490, 520, 270, "Seite"), w(522, 530, 270, "2"),
    ]
    summen = summenblock(2026, [
        ("Verwaltungsentwurf", "100.000.000", "90.000.000", "10.000.000", ""),
        ("Änderungsliste Verw. I", "22.389", "200.000", "-177.611", ""),
        ("Überschuss/ Fehlbedarf", "100.022.389", "90.200.000", "9.822.389", ""),
    ])

    aus = parse_ehh_seiten(
        [tabelle, summen],
        [linien([85, 120, 150, 250], [70, 220, 380, 440, 484]), linien([], [])])

    z1, z2 = aus.zeilen
    assert z1.explanation == "Mittel für Bescheinigungen im Brand- und Katastrophenschutz."
    assert z2.explanation == "VWG: Zuschuss 1.234.567 Euro."
    # Die Zahl in der Erläuterung ist Text geblieben, kein Betrag:
    assert (z2.revenue, z2.expense) == (None, 200_000)


def test_zwei_positionen_in_einem_band_bleiben_leer():
    """Läge eine Zeilengrenze nicht als Linie vor (zwei Positionen in einem
    Band), bleibt der Text liegen — lieber leer als an der falschen Zeile."""
    tabelle = kopf(2026) + [
        *position(100, 1, "01", [("100.000", "e")]),
        *position(110, 2, "02", [("200.000", "e")]),
        w(490, 540, 103, "Text"),
    ]
    summen = summenblock(2026, [
        ("Verwaltungsentwurf", "100.000.000", "90.000.000", "10.000.000", ""),
        ("Änderungsliste Verw. I", "300.000", "0", "300.000", ""),
        ("Überschuss/ Fehlbedarf", "100.300.000", "90.000.000", "10.300.000", ""),
    ])
    aus = parse_ehh_seiten(
        [tabelle, summen],
        [linien([85, 150], [484]), linien([], [])])
    assert all(z.explanation is None for z in aus.zeilen)


# ------------------------------------------------------- Spalte „Vorschlag von“

#: Kopfgeometrie von 230011: dieselbe Tabelle wie oben, aber mit der
#: zweizeilig gesetzten Urheber-Spalte ganz rechts (Linien bei 758/815).
def kopf_mit_urheber(year):
    return kopf(year) + [w(767, 806, 40, "Vorschlag"), w(779, 794, 52, "von")]


def urheber_wort(y, teile, x0=762):
    """Ein mehrzeilig gewickeltes Urheber-Label in seiner Spalte."""
    return [w(x0, x0 + 5 * len(t), y + 10 * i, t) for i, t in enumerate(teile)]


def test_urheber_je_position_aus_der_letzten_spalte():
    """Die Spalte „Vorschlag von“ landet an der Position — auch mehrzeilig
    gewickelt und auch, wenn das Label ober- und unterhalb der
    Positions-Grundlinie steht (die Zellen sind vertikal zentriert)."""
    tabelle = kopf_mit_urheber(2021) + [
        *position(100, 1, "01", [("20.000", "a")], label=("Gleichstellung",)),
        *urheber_wort(95, ["SPD/", "BÜNDNIS 90/", "DIE GRÜNEN"]),
        *position(140, 2, "02", [("30.000", "a")], label=("Personal",)),
        *urheber_wort(138, ["Verw.", "I"]),
    ]
    summen = summenblock(2021, [
        ("Verwaltungsentwurf", "100.000.000", "90.000.000", "10.000.000", ""),
        ("Änderungsliste v. 19.11.2020 Verw. I", "0", "30.000", "-30.000", ""),
        ("", "0", "20.000", "-20.000", "SPD/ BÜNDNIS 90/DIE GRÜNEN"),
        ("Überschuss/ Fehlbedarf", "100.000.000", "90.050.000", "9.950.000", ""),
    ])
    aus = parse_ehh_seiten(
        [tabelle, summen],
        [linien([85, 120, 175], [70, 220, 380, 440, 484, 758, 815]), linien([], [])])

    z1, z2 = aus.zeilen
    assert z1.author == "SPD/ BÜNDNIS 90/ DIE GRÜNEN"
    assert z2.author == "Verw. I"
    # Und die Erläuterungs-Spalte hat den Urheber NICHT mitgenommen:
    assert z1.explanation is None and z2.explanation is None


def test_urheber_bleibt_aus_der_erlaeuterung_heraus():
    """Ohne rechte Grenze zog die Erläuterung das Urheber-Label mitten in den
    Satz — die Labels wickeln auf eigenen Grundlinien und fielen beim Falten
    zwischen die Wörter („… gegen Gewalt an SPD/ Frauen …“)."""
    tabelle = kopf_mit_urheber(2021) + [
        *position(100, 1, "01", [("20.000", "a")], label=("Gleichstellung",)),
        w(490, 540, 95, "Mittel"), w(542, 580, 95, "gegen"),
        w(490, 530, 105, "Gewalt."),
        *urheber_wort(95, ["SPD/", "BÜNDNIS 90/", "DIE GRÜNEN"]),
    ]
    summen = summenblock(2021, [
        ("Verwaltungsentwurf", "100.000.000", "90.000.000", "10.000.000", ""),
        ("", "0", "20.000", "-20.000", "SPD/ BÜNDNIS 90/DIE GRÜNEN"),
        ("Überschuss/ Fehlbedarf", "100.000.000", "90.020.000", "9.980.000", ""),
    ])
    aus = parse_ehh_seiten(
        [tabelle, summen],
        [linien([85, 120], [70, 220, 380, 440, 484, 758, 815]), linien([], [])])
    assert aus.zeilen[0].explanation == "Mittel gegen Gewalt."
    assert aus.zeilen[0].author == "SPD/ BÜNDNIS 90/ DIE GRÜNEN"


def test_urheberprobe_reisst_bei_falscher_zuordnung():
    """Die Zuschreibung wird gerechnet, nicht gelesen: Stimmt die Summe je
    Urheber nicht mit seiner Zusammenstellungs-Zeile überein, gilt das
    Dokument als ungelesen — lieber gar keine Liste als eine Kürzung an der
    falschen Fraktion."""
    tabelle = kopf_mit_urheber(2021) + [
        # Beide Positionen tragen denselben Urheber — die Koalitionszeile
        # (20.000) bliebe dann ohne Deckung.
        *position(100, 1, "01", [("20.000", "a")], label=("Gleichstellung",)),
        *urheber_wort(98, ["Verw.", "I"]),
        *position(140, 2, "02", [("30.000", "a")], label=("Personal",)),
        *urheber_wort(138, ["Verw.", "I"]),
    ]
    summen = summenblock(2021, [
        ("Verwaltungsentwurf", "100.000.000", "90.000.000", "10.000.000", ""),
        ("Änderungsliste v. 19.11.2020 Verw. I", "0", "30.000", "-30.000", ""),
        ("", "0", "20.000", "-20.000", "SPD/ BÜNDNIS 90/DIE GRÜNEN"),
        ("Überschuss/ Fehlbedarf", "100.000.000", "90.050.000", "9.950.000", ""),
    ])
    with pytest.raises(ListenFehler, match="Urheberprobe"):
        parse_ehh_seiten(
            [tabelle, summen],
            [linien([85, 120, 175], [70, 220, 380, 440, 484, 758, 815]), linien([], [])])


def test_vorschlag_im_fliesstext_ist_keine_spalte():
    """Das Wort allein reicht nicht: In 271304 steht „Der eingebrachte
    Vorschlag zur Erhöhung der Bewohnerparkgebühren der Politik …“ mitten in
    einer Erläuterung. Ohne „von“ direkt darunter ist es keine Spalte — die
    Erläuterung bleibt vollständig, der Urheber leer."""
    tabelle = kopf(2024) + [
        *position(100, 1, "01", [("20.000", "a")], label=("Parken",)),
        w(490, 502, 95, "Der"), w(504, 550, 95, "eingebrachte"),
        w(552, 588, 95, "Vorschlag"), w(590, 602, 95, "zur"),
        w(604, 639, 95, "Erhöhung"),
    ]
    summen = summenblock(2024, [
        ("Verwaltungsentwurf", "100.000.000", "90.000.000", "10.000.000", ""),
        ("Änderungsliste Verw. I", "0", "20.000", "-20.000", ""),
        ("Überschuss/ Fehlbedarf", "100.000.000", "90.020.000", "9.980.000", ""),
    ])
    aus = parse_ehh_seiten(
        [tabelle, summen],
        [linien([85, 120], [70, 220, 380, 440, 484, 815]), linien([], [])])
    assert aus.zeilen[0].author is None
    assert aus.zeilen[0].explanation == "Der eingebrachte Vorschlag zur Erhöhung"


# ------------------------------------------- Bezeichnung an gezeichneten Linien

def test_bezeichnung_folgt_der_gezeichneten_spalte():
    """Die Wickel-Nachlese nimmt die Spaltenkanten aus dem Linienraster, wo
    die Seite eines zeichnet. Der zentrierte Kopf „Bezeichnung“ liegt je
    Jahrgang verschieden weit neben seiner Spalte — geschätzt fielen im
    Bestand 175 von 1.799 Namen angeschnitten aus („von und Frauen“ statt
    „Chancengleichstellung von Männern und Frauen“)."""
    # Kopfgeometrie von 230011 (nicht die von 300528 aus `kopf`): Der Kopf
    # „Bezeichnung“ steht ab 266, die gezeichnete Spalte aber schon ab 221
    # und bis 359. Die Schätzung daraus ist [241, 354] — „Chancengleich-
    # stellung“ (ab 226) fällt links heraus, „Männern“ (bis 355) rechts.
    kopf_230011 = [
        w(389, 436, 30, "Änderungen"), w(438, 456, 30, "2021"),
        w(266, 316, 52, "Bezeichnung"),
        w(379, 403, 50, "Ertrag"), w(437, 470, 50, "Aufwand"),
        w(595, 649, 52, "Erläuterungen"),
    ]
    tabelle = kopf_230011 + [
        w(226, 306, 92, "Chancengleichstellung"), w(308, 321, 92, "von"),
        w(324, 355, 92, "Männern"),
        *position(100, 1, "01", [("20.000", "a")], label=()),
        w(270, 283, 108, "und"), w(286, 311, 108, "Frauen"),
    ]
    summen = summenblock(2021, [
        ("Verwaltungsentwurf", "100.000.000", "90.000.000", "10.000.000", ""),
        ("Änderungsliste Verw. I", "0", "20.000", "-20.000", ""),
        ("Überschuss/ Fehlbedarf", "100.000.000", "90.020.000", "9.980.000", ""),
    ])
    mit = parse_ehh_seiten(
        [tabelle, summen],
        [linien([85, 120], [63, 84, 107, 138, 221, 359, 422, 484]), linien([], [])])
    assert mit.zeilen[0].label == "Chancengleichstellung von Männern und Frauen"

    # Ohne Linien bleibt die alte Schätzung — sie schneidet, und genau das
    # ist der Grund für die Linien-Fassung.
    ohne = parse_ehh_seiten([tabelle, summen])
    assert ohne.zeilen[0].label == "von und Frauen"
