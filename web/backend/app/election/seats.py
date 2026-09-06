"""Sitzzuteilung bei der niedersächsischen Kommunalwahl (NKWG §§ 36, 37).

Dreimal Hare/Niemeyer, in dieser Reihenfolge:

1. Die Sitze des Rates auf die Wahlvorschläge nach ihren Gesamtstimmen im
   ganzen Wahlgebiet (§ 37 Abs. 2 i. V. m. § 36 Abs. 2 und 3).
2. Die Sitze jeder Partei auf ihre Listen in den Wahlbereichen nach den dort
   erzielten Stimmen (§ 37 Abs. 3). Es gibt keine feste Sitzzahl je
   Wahlbereich.
3. Die Sitze jeder Wahlbereichsliste auf die Liste und auf die Gesamtheit der
   Bewerber*innen, im Verhältnis Listenstimmen zu Personenstimmen
   (§ 36 Abs. 4). Personensitze gehen nach höchster Stimmenzahl (Abs. 5),
   Listensitze nach Listenreihenfolge an die noch nicht Gewählten (Abs. 6).

Bekommt eine Liste mehr Sitze, als sie Bewerber*innen hat, wandern die Sitze
zu den nicht gewählten Bewerber*innen derselben Partei in den anderen
Wahlbereichen, nach Stimmenzahl (§ 37 Abs. 5). Ein Einzelwahlvorschlag hat
keine anderen Wahlbereiche; sein zweiter Sitz bliebe unbesetzt (§ 36 Abs. 7).

Die Rechnung läuft in ganzen Zahlen: Der Bruchteil von ``v·s/T`` ist
``(v·s) mod T``, und der Vergleich zweier Bruchteile mit demselben Nenner ist
ein Vergleich der Reste. Kein Gleitkomma, keine Rundungsfrage.

Verifiziert gegen das amtliche Ergebnis der Ratswahl Oldenburg 2021: alle
50 Mandate, einschließlich der Unterscheidung „direkt" / „Listenplatz n"
(``tests/test_wahlabend.py``). Die Absätze, die 2021 nie zum Zug kamen —
Mehrheitsklausel, Übergänge, unbesetzte Sitze, Losfälle — stehen von Hand
nachgerechnet in ``tests/test_wahlabend_randfaelle.py``.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal, TypeVar

K = TypeVar("K")

MandateKind = Literal["direct", "list", "transfer", "unknown"]


@dataclass(frozen=True)
class DistrictList:
    """Der Wahlvorschlag EINER Partei in EINEM Wahlbereich."""

    party: str
    district: int
    #: Listenstimmen + Personenstimmen (§ 35 Nr. 4). Das ist die Zahl, die am
    #: Wahlabend als Erstes vorliegt.
    total: int
    #: Listenstimmen (§ 35 Nr. 1). ``None`` = noch nicht ausgezählt.
    list_votes: int | None
    #: Listenplatz -> Personenstimmen. ``None`` = noch nicht ausgezählt.
    #: Erwartet wird JEDER Platz der Liste, auch mit 0 Stimmen: § 36 Abs. 6
    #: vergibt die Listensitze der Reihe nach an alle Bewerber*innen, nicht nur
    #: an die mit Stimmen. Fehlt ein Platz, kann der Sitz hier niemandem
    #: zugeteilt werden — ``allocate`` behandelt ihn dann wie einen Überhang.
    candidates: Mapping[int, int] | None
    #: Wie viele Bewerber*innen die Liste hat — aus dem Register, unabhängig
    #: davon, ob schon Stimmen vorliegen.
    n_candidates: int


@dataclass(frozen=True)
class Mandate:
    party: str
    district: int
    #: Listenplatz; ``None``, solange die Personenstimmen fehlen.
    position: int | None
    votes: int | None
    kind: MandateKind


@dataclass
class Allocation:
    seats_by_party: dict[str, int]
    seats_by_list: dict[tuple[str, int], int]
    mandates: list[Mandate]
    #: Menschentext: wo das Los entschieden hätte. Leer im Normalfall.
    ties: list[str] = field(default_factory=list)
    #: § 36 Abs. 7 — mehr Sitze als Bewerber*innen, nirgends unterzubringen.
    vacant: int = 0

    def has_mandate(self, party: str, district: int, position: int) -> bool:
        return any(
            m.party == party and m.district == district and m.position == position
            for m in self.mandates
        )


def hare_niemeyer(
    votes: Mapping[K, int], seats: int, first: K | None = None
) -> tuple[dict[K, int], list[tuple[K, K]]]:
    """Standardquote mit Ausgleich nach größten Resten (§ 36 Abs. 2).

    ``first`` bekommt einen der Restsitze vorab (§ 36 Abs. 3, Mehrheitsklausel).
    Zurück kommen die Sitze je Schlüssel und die Paare, bei denen der letzte
    vergebene und der erste nicht vergebene Rest gleich waren — dort hätte das
    Los entschieden, hier gewinnt die Reihenfolge der Eingabe.
    """
    result: dict[K, int] = {k: 0 for k in votes}
    total = sum(v for v in votes.values() if v > 0)
    if seats <= 0 or total <= 0:
        return result, []
    remainders: dict[K, int] = {}
    for k, v in votes.items():
        if v <= 0:
            continue
        result[k] = v * seats // total
        remainders[k] = v * seats % total
    left = seats - sum(result.values())
    ranked = sorted(remainders, key=lambda k: remainders[k], reverse=True)
    if first is not None and left > 0 and first in remainders:
        result[first] += 1
        left -= 1
        ranked.remove(first)
    ties: list[tuple[K, K]] = []
    if 0 < left < len(ranked) and remainders[ranked[left - 1]] == remainders[ranked[left]]:
        ties.append((ranked[left - 1], ranked[left]))
    for k in ranked[:left]:
        result[k] += 1
    return result, ties


def allocate(lists: Sequence[DistrictList], total_seats: int) -> Allocation:
    """Alle drei Stufen. ``lists`` trägt je Partei und Wahlbereich einen Eintrag."""
    parties: list[str] = []
    for dl in lists:
        if dl.party not in parties:
            parties.append(dl.party)
    by_party: dict[str, list[DistrictList]] = {p: [] for p in parties}
    for dl in lists:
        by_party[dl.party].append(dl)

    # Stufe 1 — Parteien (§ 37 Abs. 2)
    party_votes = {p: sum(dl.total for dl in by_party[p]) for p in parties}
    all_votes = sum(party_votes.values())
    majority: str | None = None
    if all_votes > 0:
        for p in parties:
            if party_votes[p] * 2 > all_votes:
                floor_seats = party_votes[p] * total_seats // all_votes
                if floor_seats * 2 <= total_seats:
                    majority = p
    seats_by_party, ties1 = hare_niemeyer(party_votes, total_seats, first=majority)
    notes = [f"Los zwischen {a} und {b} (Stufe 1)" for a, b in ties1]

    seats_by_list: dict[tuple[str, int], int] = {}
    mandates: list[Mandate] = []
    vacant = 0
    for p in parties:
        # Stufe 2 — Wahlbereiche (§ 37 Abs. 3)
        per_district = {dl.district: dl.total for dl in by_party[p]}
        seats_wb, ties2 = hare_niemeyer(per_district, seats_by_party[p])
        notes += [f"Los zwischen Wahlbereich {a} und {b} ({p}, Stufe 2)" for a, b in ties2]
        overflow = 0
        unseated: list[tuple[int, int, int]] = []  # (Stimmen, Wahlbereich, Platz)
        for dl in by_party[p]:
            s = seats_wb[dl.district]
            if s > dl.n_candidates:  # § 37 Abs. 5
                overflow += s - dl.n_candidates
                s = dl.n_candidates
            seats_by_list[(p, dl.district)] = s
            if s == 0:
                if dl.candidates:
                    unseated += [(v, dl.district, k) for k, v in dl.candidates.items()]
                continue
            if dl.candidates is None or dl.list_votes is None:
                # Personenstimmen fehlen noch: Sitze ja, Namen nein.
                mandates += [Mandate(p, dl.district, None, None, "unknown") for _ in range(s)]
                continue
            # Stufe 3 — Liste vs. Bewerber*innen (§ 36 Abs. 4)
            with_votes = {k: v for k, v in dl.candidates.items() if v > 0}
            split, ties3 = hare_niemeyer(
                {"list": dl.list_votes, "persons": sum(with_votes.values())}, s
            )
            notes += [f"Los zwischen Liste und Personen ({p}, Wahlbereich {dl.district})" for _ in ties3]
            person_seats, list_seats = split["persons"], split["list"]
            if person_seats > len(with_votes):  # § 36 Abs. 5 Satz 5
                list_seats += person_seats - len(with_votes)
                person_seats = len(with_votes)
            elected: set[int] = set()
            ranked = sorted(with_votes.items(), key=lambda kv: (-kv[1], kv[0]))
            if person_seats and len(ranked) > person_seats and ranked[person_seats - 1][1] == ranked[person_seats][1]:
                notes.append(f"Los bei Stimmengleichheit ({p}, Wahlbereich {dl.district})")
            for k, v in ranked[:person_seats]:
                mandates.append(Mandate(p, dl.district, k, v, "direct"))
                elected.add(k)
            for k in sorted(dl.candidates):
                if list_seats == 0:
                    break
                if k in elected:
                    continue
                mandates.append(Mandate(p, dl.district, k, dl.candidates[k], "list"))
                elected.add(k)
                list_seats -= 1
            if list_seats:
                # ``candidates`` führt weniger Plätze, als die Liste Bewerber*innen
                # hat — hier ist niemand mehr zu benennen. Der Sitz verschwindet
                # deshalb nicht, er geht den Weg des Überhangs: § 37 Abs. 5, sonst
                # § 36 Abs. 7.
                overflow += list_seats
                seats_by_list[(p, dl.district)] = s - list_seats
            unseated += [(v, dl.district, k) for k, v in dl.candidates.items() if k not in elected]
        # § 37 Abs. 5 — Übergang in andere Wahlbereiche, nach Stimmenzahl
        unseated.sort(key=lambda t: (-t[0], t[1], t[2]))
        if 0 < overflow < len(unseated) and unseated[overflow - 1][0] == unseated[overflow][0]:
            notes.append(f"Los bei Stimmengleichheit ({p}, Übergang in einen anderen Wahlbereich)")
        for _ in range(overflow):
            if not unseated:
                vacant += 1  # § 36 Abs. 7
                continue
            v, d, k = unseated.pop(0)
            mandates.append(Mandate(p, d, k, v, "transfer"))
            seats_by_list[(p, d)] = seats_by_list.get((p, d), 0) + 1
    return Allocation(seats_by_party, seats_by_list, mandates, notes, vacant)


def with_extra_votes(
    lists: Iterable[DistrictList], party: str, district: int, position: int | None, extra: int
) -> list[DistrictList]:
    """Dieselben Listen, nur eine Partei um ``extra`` Stimmen reicher — als
    Personenstimmen für ``position`` oder, ohne Platz, als Listenstimmen."""
    out: list[DistrictList] = []
    for dl in lists:
        if dl.party != party or dl.district != district:
            out.append(dl)
            continue
        if position is not None and dl.candidates is not None:
            cands = dict(dl.candidates)
            cands[position] = cands.get(position, 0) + extra
            out.append(DistrictList(dl.party, dl.district, dl.total + extra, dl.list_votes, cands, dl.n_candidates))
        else:
            lv = None if dl.list_votes is None else dl.list_votes + extra
            out.append(DistrictList(dl.party, dl.district, dl.total + extra, lv, dl.candidates, dl.n_candidates))
    return out


def votes_to_seat(
    lists: Sequence[DistrictList], total_seats: int, party: str, district: int, position: int, cap: int
) -> int | None:
    """Wie viele zusätzliche Personenstimmen diese Person bis zum Sitz braucht —
    alles andere unverändert. ``None``, wenn selbst ``cap`` nicht reicht; ``0``,
    wenn sie den Sitz schon hat.

    **Mehr Stimmen sind nicht monoton — und die Halbierung setzt das voraus.**
    Personenstimmen verschieben auf Stufe 3 das Verhältnis Liste zu Personen
    (§ 36 Abs. 4). Wer den Sitz über die Liste hat (§ 36 Abs. 6), kann ihn
    dadurch verlieren: Die eigenen Stimmen machen aus dem Listensitz einen
    Personensitz, und den bekommt jemand mit mehr Stimmen. Mit noch mehr
    Stimmen ist er wieder da. Gemessen an zufälligen Konstellationen trifft das
    rund einen von tausend Fällen (``tests/test_wahlabend_randfaelle.py``).

    Die Halbierung kann über so ein Loch hinweglaufen und dann eine zu hohe
    Zahl melden. Was sie NICHT kann, ist eine Zahl melden, die den Sitz nicht
    trägt: Die Grenze ``hi`` wird nur auf einen Wert gesetzt, der gerade
    geprüft wurde. Genau das hält ``found`` fest — der zurückgegebene Wert ist
    immer ein geprüfter Treffer, nie ein bloß errechneter. Ein feineres Raster
    davor hilft nicht verlässlich: Der tragende Abschnitt kann schmaler sein
    als jede bezahlbare Schrittweite.

    **Die Zusage ist deshalb**: „mit so vielen Stimmen hat sie den Sitz" — und
    nicht in jedem Fall „weniger täten es nicht".
    """

    def carries(extra: int) -> bool:
        allocation = allocate(with_extra_votes(lists, party, district, position, extra), total_seats)
        return allocation.has_mandate(party, district, position)

    if allocate(lists, total_seats).has_mandate(party, district, position):
        return 0
    if not carries(cap):
        return None
    lo, hi, found = 1, cap, cap
    while lo < hi:
        mid = (lo + hi) // 2
        if carries(mid):
            hi = found = mid
        else:
            lo = mid + 1
    return found


def party_seat_margins(
    lists: Sequence[DistrictList], total_seats: int, party: str, cap: int
) -> tuple[int | None, int | None]:
    """(Stimmen bis zum nächsten Sitz, Stimmen bis zum Verlust eines Sitzes)
    auf Stufe 1 — als Listenstimmen im stärksten Wahlbereich gedacht.
    Der zweite Wert ist ``None`` ohne Sitz; der erste, wenn ``cap`` nicht reicht.

    Hier trägt die Halbierung anders als in ``votes_to_seat``: Gemessen
    wird ``seats_by_party``, und das hängt nur an Stufe 1. Wachsen die Stimmen
    EINER Partei, wächst ihre Quote und die der anderen sinkt — ihre Sitzzahl
    kann dabei nicht fallen (über 200.000 Zufallsfälle geprüft, s. Tests). Die
    Nicht-Monotonie von ``votes_to_seat`` sitzt eine Stufe tiefer.

    Die Zahl ist parteiweit gemeint. Sie kann größer sein, als der stärkste
    Wahlbereich überhaupt Stimmen hat — dann ist sie „so viel Rückhalt in der
    Stadt", nicht „so viele Stimmen in diesem Wahlbereich"."""
    base = allocate(lists, total_seats).seats_by_party.get(party, 0)
    own = [dl for dl in lists if dl.party == party]
    if not own:
        return None, None
    strongest = max(own, key=lambda dl: dl.total).district

    def seats_with(extra: int) -> int:
        return allocate(with_extra_votes(lists, party, strongest, None, extra), total_seats).seats_by_party.get(party, 0)

    gain: int | None
    if seats_with(cap) <= base:
        gain = None
    else:
        lo, hi = 1, cap
        while lo < hi:
            mid = (lo + hi) // 2
            if seats_with(mid) > base:
                hi = mid
            else:
                lo = mid + 1
        gain = lo
    loss: int | None = None
    if base > 0:
        lo, hi = 1, min(cap, sum(dl.total for dl in own))
        if seats_with(-hi) < base:
            while lo < hi:
                mid = (lo + hi) // 2
                if seats_with(-mid) < base:
                    hi = mid
                else:
                    lo = mid + 1
            loss = lo
    return gain, loss
