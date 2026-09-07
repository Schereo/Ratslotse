"""Sitzzuteilung: die Randfälle des NKWG, jeder von Hand nachgerechnet.

``tests/test_wahlabend.py`` hält das amtliche Ergebnis 2021 fest — 50 Mandate,
die Hauptstraße des Verfahrens. Die Ratswahl 2026 kann anders ausgehen als
2021, und die Absätze, die 2021 nie zum Zug kamen, prüft dieser Abzug: die
Mehrheitsklausel (§ 36 Abs. 3), den Übergang der Personensitze auf die Liste
(§ 36 Abs. 5 Satz 5, Abs. 6), den Übergang in andere Wahlbereiche
(§ 37 Abs. 5), die unbesetzten Sitze (§ 36 Abs. 7) und die Losfälle.

Alle Zahlen sind klein und die Rechnung steht im Kommentar darüber. Die
Rechnung läuft in ganzen Zahlen: Der Bruchteil von ``v·s/T`` ist ``(v·s) mod
T``, Bruchteile vergleicht man also als Reste über demselben Nenner.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.election.seats import (  # noqa: E402
    Allocation,
    DistrictList,
    allocate,
    hare_niemeyer,
    party_seat_margins,
    votes_to_seat,
    with_extra_votes,
)


def _fuellliste(party: str, district: int, votes: int, n: int) -> DistrictList:
    """Eine Liste, die nur Stimmen beisteuert: alles Listenstimmen, ``n`` Plätze
    ohne Personenstimmen. Ihre Sitze gehen nach § 36 Abs. 6 der Reihe nach."""
    return DistrictList(party, district, votes, votes, {k: 0 for k in range(1, n + 1)}, n)


def _vollstaendig(a: Allocation, total_seats: int) -> None:
    """Kein Sitz darf unterwegs verschwinden: Was verteilt wurde, ist entweder
    ein Mandat oder ausdrücklich unbesetzt (§ 36 Abs. 7)."""
    assert sum(a.seats_by_party.values()) == total_seats, a.seats_by_party
    assert len(a.mandates) + a.vacant == total_seats, (len(a.mandates), a.vacant)


# --------------------------------------------- 1) Mehrheitsklausel § 36 Abs. 3

def test_mehrheitsklausel_greift_auch_ohne_restanspruch():
    """A hat 501 von 1.000 Stimmen — mehr als die Hälfte — und bei 10 Sitzen
    den KLEINSTEN Bruchteil von allen.

        A  501·10 = 5010 : 1000 -> 5 ganz, Rest  10
        B  250·10 = 2500 : 1000 -> 2 ganz, Rest 500
        C  249·10 = 2490 : 1000 -> 2 ganz, Rest 490
                                   9 ganz, 1 Restsitz

    Nach Absatz 2 ginge der Restsitz an B (Rest 500), A bliebe bei 5 — genau
    der Hälfte der Sitze. Absatz 3 zieht ihn deshalb vorab an A: 6/2/2. Die
    Klausel hängt nicht am Bruchteil; A hätte über ihn nie einen Sitz bekommen.
    """
    lists = [
        _fuellliste("A", 1, 501, 10),
        _fuellliste("B", 1, 250, 10),
        _fuellliste("C", 1, 249, 10),
    ]
    a = allocate(lists, 10)
    assert a.seats_by_party == {"A": 6, "B": 2, "C": 2}
    _vollstaendig(a, 10)

    # Ohne Klausel — 501 Stimmen sind hier nicht mehr die Mehrheit — bleibt es
    # bei der reinen Bruchteilsrechnung: der Restsitz geht an B.
    ohne = [
        _fuellliste("A", 1, 501, 10),
        _fuellliste("B", 1, 250, 10),
        _fuellliste("C", 1, 249, 10),
        _fuellliste("D", 1, 2, 10),
    ]
    assert allocate(ohne, 10).seats_by_party["A"] == 5


def test_mehrheitsklausel_aendert_nichts_wenn_abs2_schon_reicht():
    """A hat 560 von 1.000 Stimmen und bekommt schon nach Absatz 2 mehr als die
    Hälfte:

        A  560·10 = 5600 : 1000 -> 5 ganz, Rest 600  -> der Restsitz
        B  440·10 = 4400 : 1000 -> 4 ganz, Rest 400
                                   9 ganz, 1 Restsitz

    6 von 10 ist mehr als die Hälfte, Absatz 3 hat nichts zu tun. Das Ergebnis
    ist dasselbe, ob man die Klausel prüft oder nicht — genau deshalb darf
    ``allocate`` sie an den ganzen Zahlen festmachen (s. den Vergleich mit dem
    Gesetzeswortlaut unten).
    """
    lists = [_fuellliste("A", 1, 560, 10), _fuellliste("B", 1, 440, 10)]
    a = allocate(lists, 10)
    assert a.seats_by_party == {"A": 6, "B": 4} and a.ties == []
    _vollstaendig(a, 10)


def test_mehrheitsklausel_erspart_der_mehrheit_das_los():
    """Gleiche Bruchteile, und einer davon gehört der Mehrheit:

        A  534·10 = 5340 : 1000 -> 5 ganz, Rest 340
        B  234·10 = 2340 : 1000 -> 2 ganz, Rest 340
        C  232·10 = 2320 : 1000 -> 2 ganz, Rest 320
                                   9 ganz, 1 Restsitz

    Nach Absatz 2 entschiede zwischen A und B das Los. Verlöre A es, hätte A
    mit 5 von 10 nicht mehr als die Hälfte — und Absatz 3 gäbe ihr den Sitz
    doch. Das Los kann also gar nichts entscheiden; es wird nicht gezogen und
    nicht gemeldet.
    """
    lists = [
        _fuellliste("A", 1, 534, 10),
        _fuellliste("B", 1, 234, 10),
        _fuellliste("C", 1, 232, 10),
    ]
    a = allocate(lists, 10)
    assert a.seats_by_party == {"A": 6, "B": 2, "C": 2}
    assert a.ties == [], "kein Los, wo das Gesetz die Mehrheit vorzieht"
    _vollstaendig(a, 10)


def test_mehrheitsklausel_folgt_dem_wortlaut():
    """Der Wortlaut prüft das Ergebnis NACH Absatz 2 („erhält bei der Verteilung
    der Sitze nach Absatz 2 … nicht mehr als die Hälfte"), ``allocate`` prüft
    die ganzen Zahlen davor. Beides fällt zusammen, und zwar nicht zufällig:
    Vorab gibt es höchstens EINEN Restsitz, und wo die Mehrheit ihn nach
    Absatz 2 ohnehin bekommen hätte, ändert das Vorabziehen nichts.

    Hier steht das als Messung gegen eine Referenz, die den Wortlaut Schritt
    für Schritt nachbaut.
    """
    def nach_wortlaut(votes: dict[str, int], seats: int) -> dict[str, int]:
        plain, _ = hare_niemeyer(votes, seats)
        gesamt = sum(v for v in votes.values() if v > 0)
        for p, v in votes.items():
            if v * 2 > gesamt and plain[p] * 2 <= seats:
                return hare_niemeyer(votes, seats, first=p)[0]
        return plain

    rnd = random.Random(20260913)
    for _ in range(1500):
        votes = {f"P{i}": rnd.randint(1, 400) for i in range(rnd.randint(2, 5))}
        seats = rnd.randint(1, 25)
        lists = [_fuellliste(p, 1, v, 30) for p, v in votes.items()]
        assert allocate(lists, seats).seats_by_party == nach_wortlaut(votes, seats), (votes, seats)


def test_die_mehrheit_hat_beim_greifen_der_klausel_nie_bruchteil_null():
    """Warum die Klausel nie ins Leere greift: Greift sie, ist der Bruchteil der
    Mehrheit größer als null. Wäre er null, wäre ``v·s/T`` eine ganze Zahl —
    und weil ``v > T/2`` ist, wäre diese Zahl größer als ``s/2``, die Mehrheit
    hätte also schon mehr als die Hälfte. ``first in remainders`` ist damit für
    die Mehrheit immer erfüllt. Hier als Messung über Zufallszahlen."""
    rnd = random.Random(36)
    geprueft = 0
    for _ in range(50_000):
        votes = [rnd.randint(1, 500) for _ in range(rnd.randint(2, 5))]
        seats = rnd.randint(1, 20)
        gesamt = sum(votes)
        if votes[0] * 2 <= gesamt or (votes[0] * seats // gesamt) * 2 > seats:
            continue
        geprueft += 1
        assert (votes[0] * seats) % gesamt > 0, (votes, seats)
    assert geprueft > 100, "die Klausel kam in dieser Stichprobe gar nicht vor"


# ------------------------------- 2) Personensitze -> Liste § 36 Abs. 5 S. 5, 6

def test_ueberzaehlige_personensitze_gehen_auf_die_liste():
    """A bekommt 4 Sitze, aber nur EINE Bewerberin hat überhaupt Stimmen.

        Stufe 1: A 1000, B 1000 von 2000, 8 Sitze -> 4 und 4.
        Stufe 3: Liste 100, Personen 900, Summe 1000, 4 Sitze
                 Liste   100·4 = 400 : 1000 -> 0 ganz, Rest 400
                 Personen 900·4 = 3600 : 1000 -> 3 ganz, Rest 600  -> Restsitz
                 also 0 Listensitze, 4 Personensitze.

    Absatz 5 Satz 5: Es gibt nur eine Bewerberin mit Stimmen (Platz 2), also
    gehen 3 der 4 Personensitze auf die Liste über. Absatz 6 vergibt sie in
    Listenreihenfolge an die noch nicht Gewählten — Platz 2 bleibt außer
    Betracht, es sind die Plätze 1, 3 und 4.
    """
    lists = [
        DistrictList("A", 1, 1000, 100, {1: 0, 2: 900, 3: 0, 4: 0}, 4),
        _fuellliste("B", 1, 1000, 5),
    ]
    a = allocate(lists, 8)
    assert a.seats_by_party == {"A": 4, "B": 4}
    meins = sorted((m.position, m.kind) for m in a.mandates if m.party == "A")
    assert meins == [(1, "list"), (2, "direct"), (3, "list"), (4, "list")]
    _vollstaendig(a, 8)


def test_listensitze_ueberspringen_die_direkt_gewaehlten():
    """Absatz 6 Satz 2: „Außer Betracht bleiben die Bewerber, die nach Absatz 5
    einen Sitz erhalten haben."

        Stufe 3: Liste 300, Personen 300, Summe 600, 4 Sitze
                 Liste    300·4 = 1200 : 600 -> 2 ganz, Rest 0
                 Personen 300·4 = 1200 : 600 -> 2 ganz, Rest 0
                 kein Restsitz: 2 Listensitze, 2 Personensitze.

    Die Personensitze gehen an die Stimmenstärksten — Platz 3 (150) und Platz 5
    (120). Die beiden Listensitze gehen an die Plätze 1 und 2, nicht an 3.
    """
    lists = [
        DistrictList("A", 1, 600, 300, {1: 10, 2: 20, 3: 150, 4: 0, 5: 120}, 5),
        _fuellliste("B", 1, 600, 8),
    ]
    a = allocate(lists, 8)
    assert a.seats_by_party == {"A": 4, "B": 4}
    meins = sorted((m.position, m.kind) for m in a.mandates if m.party == "A")
    assert meins == [(1, "list"), (2, "list"), (3, "direct"), (5, "direct")]
    _vollstaendig(a, 8)


def test_fehlende_listenplaetze_verschlucken_keinen_sitz():
    """``candidates`` soll JEDEN Platz der Liste führen, auch mit 0 Stimmen —
    sonst hat Absatz 6 niemanden mehr, dem er den Listensitz zuteilen könnte.

    Hier führt B acht Bewerber*innen, aber nur eine Stimmenzeile. Der erste
    Listensitz geht an Platz 1, die übrigen sieben kann niemand bekommen. Sie
    dürfen deshalb nicht still verschwinden: Sie gehen den Weg des Überhangs —
    B hat keinen zweiten Wahlbereich, also bleiben sie unbesetzt
    (§ 37 Abs. 5, dann § 36 Abs. 7).
    """
    lists = [
        DistrictList("A", 1, 330, 100, {1: 10, 2: 120, 3: 100}, 3),
        DistrictList("B", 1, 1320, 1320, {1: 0}, 8),
    ]
    a = allocate(lists, 10)
    assert a.seats_by_party == {"A": 2, "B": 8}
    assert a.seats_by_list[("B", 1)] == 1, "nur ein Sitz ist hier zu besetzen"
    assert a.vacant == 7
    _vollstaendig(a, 10)


# ------------------------------------ 3) Übergang in andere Wahlbereiche § 37 Abs. 5

def test_uebergang_nimmt_die_beste_aus_ALLEN_wahlbereichen():
    """A gewinnt in Wahlbereich 1 zwei Sitze, hat dort aber nur eine Bewerberin.

        Stufe 1: A 9.550, B 19.100 von 28.650, 6 Sitze
                 A 9550·6 = 57.300 : 28.650 -> genau 2, B genau 4.
        Stufe 2: A auf ihre Wahlbereiche, 2 Sitze, Summe 9.550
                 WB 1  9000·2 = 18.000 : 9550 -> 1 ganz, Rest 8450 -> Restsitz
                 WB 2   300·2 =    600 : 9550 -> 0 ganz, Rest  600
                 WB 3   250·2 =    500 : 9550 -> 0 ganz, Rest  500
                 also 2 Sitze in WB 1, dort nur eine Bewerberin -> ein Überhang.

    Der Überhangsitz geht an die stimmenstärkste nicht gewählte Bewerberin der
    Partei in den ANDEREN Wahlbereichen: 240 in WB 3 schlägt 200 in WB 2. Und
    das gilt, obwohl WB 2 zuerst gerechnet wird — der Pool wird über alle
    Wahlbereiche gebildet, bevor ein einziger Übergangssitz vergeben ist.
    """
    lists = [
        DistrictList("A", 1, 9000, 9000, {1: 0}, 1),
        DistrictList("A", 2, 300, 0, {1: 200, 2: 100}, 2),
        DistrictList("A", 3, 250, 0, {1: 240, 2: 10}, 2),
        _fuellliste("B", 1, 19_100, 6),
    ]
    a = allocate(lists, 6)
    assert a.seats_by_party == {"A": 2, "B": 4}
    meins = sorted((m.district, m.position, m.kind, m.votes) for m in a.mandates if m.party == "A")
    assert meins == [(1, 1, "list", 0), (3, 1, "transfer", 240)]
    _vollstaendig(a, 6)


def test_die_reihenfolge_der_wahlbereiche_aendert_nichts():
    """Derselbe Fall rückwärts eingegeben. Würde der Pool wahlbereichsweise
    abgearbeitet, ginge der Überhang an die Erstbeste statt an die Beste — das
    Ergebnis hinge dann an der Zeilenreihenfolge der CSV."""
    lists = [
        DistrictList("A", 1, 9000, 9000, {1: 0}, 1),
        DistrictList("A", 2, 300, 0, {1: 200, 2: 100}, 2),
        DistrictList("A", 3, 250, 0, {1: 240, 2: 10}, 2),
        _fuellliste("B", 1, 19_100, 6),
    ]
    vorwaerts = allocate(lists, 6)
    rueckwaerts = allocate(list(reversed(lists)), 6)
    schluessel = lambda a: sorted((m.party, m.district, m.position, m.kind, m.votes) for m in a.mandates)  # noqa: E731
    assert schluessel(vorwaerts) == schluessel(rueckwaerts)
    assert vorwaerts.seats_by_list == rueckwaerts.seats_by_list


def test_uebergang_greift_nur_auf_nicht_gewaehlte_zu():
    """Wer in seinem Wahlbereich schon einen Sitz hat, ist raus („die dort
    keinen Sitz erhalten").

        Stufe 2: A hat 4 Sitze, Summe 5.000
                 WB 1  4000·4 = 16.000 : 5000 -> 3 ganz, Rest 1000 -> Restsitz
                 WB 2  1000·4 =  4.000 : 5000 -> 0 ganz, Rest 4000 -> Restsitz
                 4 Sitze in WB 1 auf 2 Bewerber*innen -> zwei Überhänge,
                 1 Sitz in WB 2 -> Platz 1 (600 Stimmen) ist gewählt.

    Im Pool stehen danach nur noch Platz 2 (400) und Platz 3 (0) aus WB 2. Die
    beiden Überhänge gehen an sie, nicht ein zweites Mal an Platz 1.
    """
    lists = [
        DistrictList("A", 1, 4000, 4000, {1: 0, 2: 0}, 2),
        DistrictList("A", 2, 1000, 0, {1: 600, 2: 400, 3: 0}, 3),
        _fuellliste("B", 1, 5000, 8),
    ]
    a = allocate(lists, 8)
    assert a.seats_by_party == {"A": 4, "B": 4}
    meins = sorted((m.district, m.position, m.kind) for m in a.mandates if m.party == "A")
    assert meins == [(1, 1, "list"), (1, 2, "list"), (2, 1, "direct"), (2, 2, "transfer")]
    _vollstaendig(a, 8)


# --------------------------------------- 4) Einzelwahlvorschlag, § 36 Abs. 7

def test_einzelwahlvorschlag_bekommt_seinen_sitz_und_laesst_den_zweiten_leer():
    """Ein Einzelwahlvorschlag ist eine Liste mit genau einer Bewerberin in
    genau einem Wahlbereich; ``service`` baut ihn als ``list_votes=0`` mit allen
    Stimmen auf Platz 1.

        Stufe 1: E 2.000, B 8.000 von 10.000, 10 Sitze -> E genau 2, B genau 8.

    Zwei Sitze, eine Bewerberin — und § 37 Abs. 5 hilft nicht, weil es keinen
    anderen Wahlbereich gibt, in den der Sitz übergehen könnte. Er bleibt nach
    § 36 Abs. 7 bis zum Ende der Wahlperiode unbesetzt.
    """
    lists = [
        DistrictList("E", 1, 2000, 0, {1: 2000}, 1),
        _fuellliste("B", 1, 8000, 12),
    ]
    a = allocate(lists, 10)
    assert a.seats_by_party == {"E": 2, "B": 8}
    meins = [(m.position, m.kind, m.votes) for m in a.mandates if m.party == "E"]
    assert meins == [(1, "direct", 2000)]
    assert a.seats_by_list[("E", 1)] == 1 and a.vacant == 1
    _vollstaendig(a, 10)

    # Der Normalfall daneben: ein Sitz, ein Mandat, nichts bleibt leer.
    knapp = [
        DistrictList("E", 1, 1000, 0, {1: 1000}, 1),
        _fuellliste("B", 1, 9000, 12),
    ]
    b = allocate(knapp, 10)
    assert b.seats_by_party == {"E": 1, "B": 9} and b.vacant == 0
    _vollstaendig(b, 10)


# ------------------------------------------------------------- 5) Losfälle

def test_losfaelle_werden_gemeldet_und_entscheiden_deterministisch():
    """Jede Stufe hat ihren Losfall (§ 36 Abs. 2 Satz 5, Abs. 5 Satz 4,
    § 37 Abs. 5 Satz 3). Gezogen wird hier nicht — der Vermerk sagt, wo die
    Wahlleitung ziehen müsste; entschieden wird deterministisch, damit dieselbe
    CSV nicht zweimal verschiedene Sitze zeigt."""
    # Stufe 1: drei gleiche Reste, zwei Restsitze.
    #   je 10·2 = 20 : 30 -> 0 ganz, Rest 20 bei allen dreien.
    stufe1 = [_fuellliste(p, 1, 10, 5) for p in ("A", "B", "C")]
    a = allocate(stufe1, 2)
    assert sum(a.seats_by_party.values()) == 2
    assert any("Stufe 1" in t for t in a.ties), a.ties
    _vollstaendig(a, 2)

    # Stufe 3: ein Personensitz, zwei Bewerber*innen mit je 300 Stimmen.
    #   Liste 400, Personen 600, Summe 1000, 1 Sitz ->
    #   Liste 400 : 1000 = 0 Rest 400, Personen 600 : 1000 = 0 Rest 600
    #   -> der Sitz ist ein Personensitz, und dort steht es 300 zu 300.
    stufe3 = [
        DistrictList("A", 1, 1000, 400, {1: 300, 2: 300}, 2),
        _fuellliste("B", 1, 9000, 12),
    ]
    b = allocate(stufe3, 10)
    assert b.seats_by_party["A"] == 1
    assert any("Stimmengleichheit" in t and "Wahlbereich 1" in t for t in b.ties), b.ties
    assert [(m.position, m.kind) for m in b.mandates if m.party == "A"] == [(1, "direct")]
    _vollstaendig(b, 10)

    # § 37 Abs. 5: ein Überhang, und im Pool stehen zwei mit je 250 Stimmen.
    #   Stufe 1: A 9.500, B 4.750 von 14.250, 3 Sitze -> A genau 2, B genau 1.
    #   Stufe 2: WB 1 9000·2 = 18.000 : 9500 -> 1 ganz, Rest 8500 -> Restsitz;
    #            WB 2  500·2 =  1.000 : 9500 -> 0 ganz, Rest 1000.
    #   2 Sitze in WB 1 auf eine Bewerberin -> ein Überhang.
    uebergang = [
        DistrictList("A", 1, 9000, 9000, {1: 0}, 1),
        DistrictList("A", 2, 500, 0, {1: 250, 2: 250}, 2),
        _fuellliste("B", 1, 4750, 5),
    ]
    c = allocate(uebergang, 3)
    assert c.seats_by_party == {"A": 2, "B": 1}
    assert any("Übergang" in t for t in c.ties), c.ties
    assert [(m.district, m.position, m.kind) for m in c.mandates if m.party == "A"] == [
        (1, 1, "list"), (2, 1, "transfer"),
    ]
    _vollstaendig(c, 3)


def test_ein_losvermerk_ohne_gleichstand_gibt_es_nicht():
    """Der Vermerk soll die Ausnahme bleiben: Wo die Reste verschieden sind,
    darf keiner stehen — sonst liest ihn am Wahlabend niemand mehr."""
    sauber = [
        _fuellliste("A", 1, 7300, 12),
        _fuellliste("B", 1, 6700, 12),
        _fuellliste("C", 1, 2400, 12),
    ]
    a = allocate(sauber, 20)
    assert a.seats_by_party == {"A": 9, "B": 8, "C": 3}
    assert a.ties == []


# --------------------------------------------------- 6) Abstände und Monotonie

def _monotonie_beispiel(x: int) -> list[DistrictList]:
    """Platz 1 der Partei A hat ``x`` Personenstimmen; alles andere fest.

    A: Listenstimmen 100, Plätze 1 (x), 2 (120), 3 (100)  -> Summe 320 + x
    B: 1.840 Listenstimmen, 10 Plätze ohne Personenstimmen
    10 Sitze.
    """
    return [
        DistrictList("A", 1, 320 + x, 100, {1: x, 2: 120, 3: 100}, 3),
        _fuellliste("B", 1, 1840, 10),
    ]


def test_mehr_personenstimmen_koennen_einen_sitz_kosten():
    """Der Gegenbeweis zur Monotonie-Annahme der Binärsuche — dreimal dieselbe
    Konstellation, nur Platz 1 mit mehr Stimmen:

    x = 0   Stufe 1: A 320 von 2.160, 10 Sitze
                     A 3200 : 2160 -> 1 ganz, Rest 1040
                     B 18400 : 2160 -> 8 ganz, Rest 1120 -> der Restsitz
                     A bekommt 1 Sitz. Stufe 3: Liste 100, Personen 220,
                     Summe 320 -> der eine Sitz ist ein Personensitz und geht
                     an Platz 2 (120). PLATZ 1 IST DRAUSSEN.

    x = 40  A 360 von 2.200: A 3600 : 2200 -> 1 ganz, Rest 1400 -> Restsitz,
                     also 2 Sitze. Stufe 3: Liste 100, Personen 260, Summe 360
                     Liste    200 : 360 -> 0 ganz, Rest 200 -> Restsitz
                     Personen 520 : 360 -> 1 ganz, Rest 160
                     1 Personensitz (Platz 2), 1 Listensitz -> Absatz 6 gibt
                     ihn Platz 1. PLATZ 1 IST DRIN, mit 40 Stimmen.

    x = 85  A 405 von 2.245, weiter 2 Sitze. Stufe 3: Personen 305, Summe 405
                     Liste    200 : 405 -> 0 ganz, Rest 200
                     Personen 610 : 405 -> 1 ganz, Rest 205 -> Restsitz
                     2 Personensitze: Platz 2 (120) und Platz 3 (100).
                     PLATZ 1 IST WIEDER DRAUSSEN — mit 85 Stimmen.

    x = 130 Personen 350, Summe 450: Personen 900 : 450 = genau 2, Liste 0.
                     Personensitze an Platz 1 (130) und Platz 2 (120).
                     PLATZ 1 IST WIEDER DRIN.

    Der eigene Zugewinn verschiebt auf Stufe 3 das Verhältnis Liste zu Personen
    (§ 36 Abs. 4) und macht aus dem Listensitz, der Platz 1 gehörte, einen
    Personensitz für jemand anderen. Das ist keine Panne, sondern das Gesetz.
    """
    assert not allocate(_monotonie_beispiel(0), 10).has_mandate("A", 1, 1)
    assert allocate(_monotonie_beispiel(40), 10).has_mandate("A", 1, 1)
    assert not allocate(_monotonie_beispiel(85), 10).has_mandate("A", 1, 1)
    assert allocate(_monotonie_beispiel(130), 10).has_mandate("A", 1, 1)


def test_votes_to_seat_meldet_nur_zahlen_die_den_sitz_wirklich_tragen():
    """Die Zusage von ``votes_to_seat`` trotz fehlender Monotonie: Die gemeldete
    Zahl trägt den Sitz. Sie ist nicht in jedem Fall die kleinste — hier tut es
    schon eine Handvoll Stimmen, gemeldet wird eine dreistellige Zahl, weil die
    Halbierung mit ``cap=180`` zuerst bei 90 landet und dort in dem Loch
    zwischen 81 und 99 steht.

    Genau das steht so im Docstring; dieser Test hält beides fest — die Zusage
    und ihre Grenze.
    """
    basis = _monotonie_beispiel(0)
    gemeldet = votes_to_seat(basis, 10, "A", 1, 1, 180)
    assert gemeldet is not None
    nachher = allocate(with_extra_votes(basis, "A", 1, 1, gemeldet), 10)
    assert nachher.has_mandate("A", 1, 1), f"{gemeldet} Stimmen tragen den Sitz nicht"
    # Die Grenze: 40 Stimmen hätten es auch getan.
    assert allocate(with_extra_votes(basis, "A", 1, 1, 40), 10).has_mandate("A", 1, 1)
    assert gemeldet > 40, "der Docstring verspricht keine Kleinstzahl — hier ist der Beleg"


def test_votes_to_seat_traegt_ueber_zufallsfaelle():
    """Dieselbe Zusage breit gemessen: Was gemeldet wird, trägt — und ``None``
    heißt, dass auch ``cap`` nicht reicht."""
    rnd = random.Random(52)
    for _ in range(40):
        lists = []
        for p in ("A", "B"):
            for d in (1, 2):
                n = rnd.randint(2, 4)
                cands = {k: rnd.randint(0, 300) for k in range(1, n + 1)}
                lv = rnd.randint(0, 400)
                lists.append(DistrictList(p, d, lv + sum(cands.values()), lv, cands, n))
        seats = rnd.randint(4, 12)
        dl = lists[rnd.randrange(len(lists))]
        pos = rnd.randint(1, dl.n_candidates)
        n = votes_to_seat(lists, seats, dl.party, dl.district, pos, 5000)
        if n is None:
            assert not allocate(with_extra_votes(lists, dl.party, dl.district, pos, 5000), seats).has_mandate(
                dl.party, dl.district, pos
            )
            continue
        assert allocate(with_extra_votes(lists, dl.party, dl.district, pos, n), seats).has_mandate(
            dl.party, dl.district, pos
        ), (n, dl)


def test_stufe_1_ist_monoton_und_traegt_party_seat_margins():
    """``party_seat_margins`` misst ``seats_by_party``, und das hängt nur an
    Stufe 1. Dort gilt die Monotonie, die ``votes_to_seat`` fehlt: Wachsen die
    Stimmen EINER Partei, wächst ihre Quote, die der anderen sinkt — die eigene
    Sitzzahl kann dabei nicht fallen. Hier über 60.000 Zufallsfälle gemessen,
    damit die Halbierung dort ohne Sternchen bleiben darf."""
    rnd = random.Random(11)
    for _ in range(60_000):
        votes = [rnd.randint(1, 300) for _ in range(rnd.randint(2, 5))]
        seats = rnd.randint(2, 15)
        basis = hare_niemeyer(dict(enumerate(votes)), seats)[0][0]
        for mehr in (1, 3, 10, 100):
            neu = list(votes)
            neu[0] += mehr
            assert hare_niemeyer(dict(enumerate(neu)), seats)[0][0] >= basis, (votes, seats, mehr)


def test_party_seat_margins_treffen_die_kippstellen():
    """420 / 330 / 250 von 1.000 Stimmen, 10 Sitze:

        A 4200 : 1000 -> 4 ganz, Rest 200
        B 3300 : 1000 -> 3 ganz, Rest 300
        C 2500 : 1000 -> 2 ganz, Rest 500 -> der eine Restsitz
                         9 ganz  ->  4 / 3 / 3

    A fehlen 38 Stimmen zum fünften Sitz: bei 458 von 1.038 ist ihr Rest
    ``4580 - 4·1038 = 428`` und schlägt den von C (``2500 - 2·1038 = 424``);
    eine Stimme weniger, und es steht 422 zu 426. Nach unten sind es 91: bei
    329 von 909 liegt A mit Rest 563 hinter B (573) und C (682) und verliert
    den vierten Sitz.

    Beide Zahlen stehen hier doppelt — als Wert UND als Kippstelle, damit der
    Test nicht bloß festhält, was heute herauskommt.
    """
    lists = [_fuellliste("A", 1, 420, 12), _fuellliste("B", 1, 330, 12), _fuellliste("C", 1, 250, 12)]
    assert allocate(lists, 10).seats_by_party == {"A": 4, "B": 3, "C": 3}
    gewinn, verlust = party_seat_margins(lists, 10, "A", 5000)
    assert (gewinn, verlust) == (38, 91)

    def sitze(n: int) -> int:
        return allocate(with_extra_votes(lists, "A", 1, None, n), 10).seats_by_party["A"]

    assert sitze(gewinn) == 5 and sitze(gewinn - 1) == 4
    assert sitze(-verlust) == 3 and sitze(-(verlust - 1)) == 4


def test_zwei_parteien_heisst_immer_mehrheitsklausel():
    """Ein Fallstrick beim Basteln von Beispielen, kein Fehler im Modul: Bei
    genau zwei Wahlvorschlägen hat der stärkere immer mehr als die Hälfte der
    Stimmen — § 36 Abs. 3 redet also fast immer mit.

    560 zu 440 bei 10 Sitzen ergibt 6 zu 4, und daran ändert sich lange nichts:
    Erst wenn A unter die Hälfte fällt (bei 120 Stimmen weniger steht es 440 zu
    440), verliert A den sechsten Sitz. Wer den Abstand „bis zum Verlust" an
    einem Zweiparteien-Beispiel prüft, misst die Mehrheitsklausel, nicht die
    Bruchteile.
    """
    lists = [_fuellliste("A", 1, 560, 12), _fuellliste("B", 1, 440, 12)]
    assert allocate(lists, 10).seats_by_party == {"A": 6, "B": 4}
    assert party_seat_margins(lists, 10, "A", 5000)[1] == 120
    knapp = allocate(with_extra_votes(lists, "A", 1, None, -119), 10)
    assert knapp.seats_by_party == {"A": 6, "B": 4}, "441 zu 440 ist noch die Mehrheit"
