"""Das Wahlergebnis je Wahlbezirk für die Stadtkarte.

Tims Wunsch (23.09.2026): auf „Mein Viertel“ die Stadt in der Farbe der
Liste, die in jedem Bezirk vorn lag; ein Klick auf einen Ortsbereich zeigt
seine Bezirke, ein Tipp auf einen Bezirk die ganze Aufteilung
(``docs/plan-viertel-wahlkarte.md``).

Hier wird gerechnet, was Web und App sonst je für sich rechneten: wer vorn
lag, mit welchem Vorsprung, in welchen Ortsbereichen der Bezirk liegt und
wie der Wahlbereich MIT Briefwahl aussieht. Drei Wahlen gehen auf dieselbe
Karte — die Ratswahl (Listen), der erste Wahlgang der OB-Wahl und die
Stichwahl (Personen). Die Eingänge unterscheiden sich, die Antwort nicht.

**Nur Urnenbezirke haben eine Fläche.** Die Briefwahl trug 2026 ein Drittel
der Stimmen und hat keinen Ort; sie steht deshalb in ``areas`` (je
Wahlbereich) und in ``postal_share_pct``, nie in einer Bezirksfarbe.

**Welche Bezirke zu einem Ortsbereich gehören**, steht in
``kommunalwahl/geo/wahlbezirk-ortsbereiche.json``
(``scripts/wahl_geodaten.py ueberlappung``). Die Bezirke liegen nicht in den
Ortsbereichen — 23 von 91 zu weniger als 80 % in einem —, deshalb gehört
jeder Bezirk zu JEDEM Ortsbereich, den er nennenswert berührt.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache

from ..antworten import (
    ElectionMap,
    ElectionMapArea,
    ElectionMapChoice,
    ElectionMapContestant,
    ElectionMapDistrict,
    ElectionMapPlace,
    ElectionMapShare,
    ElectionMapWin,
)
from . import archive, elections, mayor, mayor_districts, votemanager
from .register import KOMMUNALWAHL

_log = logging.getLogger("ratslotse.web.wahlabend")

OVERLAP_PATH = KOMMUNALWAHL / "geo" / "wahlbezirk-ortsbereiche.json"
#: Die eingefrorenen Bezirke des ersten OB-Wahlgangs (``wahl_einfrieren.py``).
MAYOR_DISTRICTS_FILE = "praesentation-ob-wahlbezirke.json"

#: Die zweite Farbe der Stichwahl — dieselbe wie auf der Stichwahl-Karte
#: (``stichwahl-karte.tsx::kartenfarbe``): Orange statt Grün, weil Grün neben
#: Rot auf einer Fläche die Ampel wäre (DESIGNSPRACHE „Parteifarben").
RUNOFF_SECOND = ("#e8590c", "#ff8a3d")

ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII", 9: "IX"}


class UnknownElection(LookupError):
    """Die Karte kennt diese Wahl nicht (oder noch nicht)."""


class UnknownPlace(LookupError):
    """Kein Ortsbereich dieses Namens berührt einen Wahlbezirk."""


@dataclass(frozen=True)
class _Row:
    """Ein Bezirk, gleich aus welcher Wahl: Stimmen je Slug."""
    number: int
    name: str
    area: int
    postal: bool
    counted: bool
    turnout_pct: float | None
    valid_votes: int | None
    votes: dict[str, int | None]


# ------------------------------------------------------------------ Ortsbereiche

@lru_cache(maxsize=1)
def overlap() -> dict[int, tuple[ElectionMapPlace, ...]]:
    """Bezirksnummer → Ortsbereiche mit Flächenanteil."""
    roh = json.loads(OVERLAP_PATH.read_text(encoding="utf-8"))
    return {int(nr): tuple(ElectionMapPlace(name=e["place"], share=float(e["share"])) for e in orte)
            for nr, orte in roh["districts"].items()}


def places() -> set[str]:
    return {p["name"] for orte in overlap().values() for p in orte}


# ------------------------------------------------------------------ Wahlen

def _label(w: elections.Election) -> str:
    if w.kind == "council":
        return "Ratswahl"
    return "Stichwahl" if w.first_round else "OB-Wahl"


def _choice(w: elections.Election) -> ElectionMapChoice:
    return ElectionMapChoice(slug=w.slug, label=_label(w), kind=w.kind, date=w.date)


def _mayor_file(w: elections.Election):
    if w.archive_folder is None:
        return None
    datei = w.archive_folder / MAYOR_DISTRICTS_FILE
    return datei if datei.is_file() else None


def choices(now: datetime | None = None) -> list[elections.Election]:
    """Die Wahlen, die die Karte zeigen kann — in Stimmzettel-Reihenfolge
    des Abends: Ratswahl, OB-Wahl, Stichwahl.

    Die Geometrie ist die von 2026; eine Wahl mit anderen Bezirken (2021)
    kommt nicht darauf. Eine Ratswahl braucht ihren eingefrorenen Stand, die
    OB-Wahl ihre Bezirksdatei, die Stichwahl nur ihren Wahlschluss — davor
    gibt es nichts zu färben.
    """
    now = now or datetime.now(timezone.utc)
    rat = elections.active()
    out: list[elections.Election] = []
    if rat.kind == "council" and (archive.verfuegbar(rat) or rat.polls_close <= now):
        out.append(rat)
    ob = elections.mayor_of(rat)
    if ob is not None and (_mayor_file(ob) is not None or ob.polls_close <= now):
        out.append(ob)
    stich = elections.runoff()
    if stich is not None and stich.polls_close <= now:
        out.append(stich)
    return out


# ------------------------------------------------------------------ Eingänge

def _council(w: elections.Election) -> tuple[list[ElectionMapContestant], list[_Row]]:
    from . import service  # service zieht archive nach — erst hier, sonst ein Ring

    teile = archive.snapshot(w.slug)
    reg, snap = teile if teile is not None else (service.load_register(), votemanager.fetch())
    liste = service.districts(reg, snap, "map")
    wer = [ElectionMapContestant(slug=p.slug, short=p.short, name=p.official,
                                 color=p.color, color_dark=p.color_dark) for p in reg.parties]
    zeilen = [_Row(number=d["number"], name=_ort(d["name"]), area=d["area"], postal=d["postal"],
                   counted=d["counted"], turnout_pct=d["totals"]["turnout_pct"],
                   valid_votes=d["totals"]["valid_votes"],
                   votes={p["slug"]: p["votes"] for p in d["parties"]})
              for d in liste["districts"]]
    return wer, zeilen


def _ort(name: str) -> str:
    """„101 Amt für Gebäudewirtschaft" → „Amt für Gebäudewirtschaft" — die
    Nummer steht in ``number``; doppelt gelesen stört sie."""
    kopf, _, rest = name.partition(" ")
    return rest.strip() if kopf.isdigit() and rest.strip() else name


def _mayor_rows(bezirke: tuple[mayor_districts.MayorDistrict, ...]) -> list[_Row]:
    return [_Row(number=d.number, name=_ort(d.name), area=d.area, postal=d.postal, counted=d.counted,
                 turnout_pct=(round(100 * d.voters / d.eligible, 1)
                              if d.voters is not None and d.eligible else None),
                 valid_votes=d.valid_votes, votes=dict(d.votes))
            for d in bezirke]


@lru_cache(maxsize=4)
def _frozen_mayor(slug: str) -> tuple[mayor_districts.MayorDistrict, ...]:
    w = elections.get(slug)
    datei = _mayor_file(w) if w is not None else None
    if w is None or datei is None:
        return ()
    known = {c.slug: c.name for c in mayor.candidates(w)}
    return mayor_districts.parse_overview(json.loads(datei.read_text(encoding="utf-8")), known)


def _nachname(name: str) -> str:
    return name.split()[-1] if name.split() else name


def _mayor(w: elections.Election) -> tuple[list[ElectionMapContestant], list[_Row]]:
    known = mayor.candidates(w)
    bezirke = _frozen_mayor(w.slug) if _mayor_file(w) is not None else ()
    if not bezirke:
        bezirke = mayor.fetch(w=w).districts
    farben = {c.slug: (c.color or "#64748b", c.color_dark or "#94a3b8") for c in known}
    if w.first_round and len(known) == 2:
        # Wer im ersten Wahlgang vorn lag, behält seine Farbe; die andere
        # Person wird orange — wie auf der Stichwahl-Karte.
        vorher = _frozen_mayor(w.first_round)
        summe = {c.slug: sum(d.votes.get(c.slug) or 0 for d in vorher) for c in known}
        erster = max(known, key=lambda c: (summe[c.slug], c.slug))
        for c in known:
            if c.slug != erster.slug:
                farben[c.slug] = RUNOFF_SECOND
    wer = [ElectionMapContestant(slug=c.slug, short=_nachname(c.name), name=c.name,
                                 color=farben[c.slug][0], color_dark=farben[c.slug][1]) for c in known]
    return wer, _mayor_rows(bezirke)


# ------------------------------------------------------------------ Rechnen

def _shares(votes: dict[str, int | None], valid: int | None) -> list[ElectionMapShare]:
    basis = valid or sum(v or 0 for v in votes.values())
    out = [ElectionMapShare(slug=s, votes=v,
                            share_pct=round(100 * v / basis, 1) if v is not None and basis else None)
           for s, v in votes.items()]
    return sorted(out, key=lambda e: (-(e["votes"] or -1), e["slug"]))


def _lead(parteien: list[ElectionMapShare]) -> tuple[str | None, str | None, float | None]:
    mit = [p for p in parteien if p["votes"]]
    if not mit:
        return None, None, None
    erster = mit[0]
    zweiter = mit[1] if len(mit) > 1 else None
    if zweiter is not None and zweiter["votes"] == erster["votes"]:
        return None, None, 0.0  # Gleichstand: niemand „lag vorn"
    abstand = None
    if erster["share_pct"] is not None:
        abstand = round(erster["share_pct"] - ((zweiter or {}).get("share_pct") or 0.0), 1)
    return erster["slug"], zweiter["slug"] if zweiter else None, abstand


def _district(z: _Row) -> ElectionMapDistrict:
    parteien = _shares(z.votes, z.valid_votes) if z.counted else _shares(
        {s: None for s in z.votes}, None)
    leader, zweiter, abstand = _lead(parteien) if z.counted else (None, None, None)
    return ElectionMapDistrict(
        number=z.number, name=z.name, area=z.area, counted=z.counted,
        leader=leader, runner_up=zweiter, margin_pct=abstand,
        turnout_pct=z.turnout_pct if z.counted else None,
        valid_votes=z.valid_votes if z.counted else None,
        places=list(overlap().get(z.number, ())), parties=parteien,
    )


def _areas(zeilen: list[_Row], nur: set[int] | None) -> list[ElectionMapArea]:
    out: list[ElectionMapArea] = []
    for nr in sorted({z.area for z in zeilen}):
        if nur is not None and nr not in nur:
            continue
        mine = [z for z in zeilen if z.area == nr]
        gezaehlt = [z for z in mine if z.counted]
        summe: dict[str, int | None] = {}
        for z in gezaehlt:
            for s, v in z.votes.items():
                summe[s] = (summe.get(s) or 0) + (v or 0)
        gueltig = sum(z.valid_votes or 0 for z in gezaehlt) or None
        parteien = _shares(summe, gueltig) if gezaehlt else []
        out.append(ElectionMapArea(number=nr, roman=ROMAN.get(nr, str(nr)), counted=len(gezaehlt),
                                   total=len(mine), valid_votes=gueltig,
                                   leader=_lead(parteien)[0], parties=parteien))
    return out


def build(slug: str | None = None, place: str | None = None,
          now: datetime | None = None) -> ElectionMap:
    moeglich = choices(now)
    if not moeglich:
        raise UnknownElection("Es gibt noch keine Wahl mit Ergebnissen je Bezirk.")
    if slug is None:
        w = moeglich[0]
    else:
        w = next((m for m in moeglich if m.slug == slug), None)
        if w is None:
            raise UnknownElection(f"Die Karte kennt die Wahl „{slug}“ nicht.")
    if place is not None and place not in places():
        raise UnknownPlace(f"Kein Wahlbezirk liegt in „{place}“.")

    wer, zeilen = _council(w) if w.kind == "council" else _mayor(w)
    urne = [z for z in zeilen if not z.postal]
    brief = sum(z.valid_votes or 0 for z in zeilen if z.postal and z.counted)
    alle = sum(z.valid_votes or 0 for z in zeilen if z.counted)
    bezirke = [_district(z) for z in sorted(urne, key=lambda z: z.number)]
    siege: dict[str, int] = {}
    for d in bezirke:
        if d["leader"]:
            siege[d["leader"]] = siege.get(d["leader"], 0) + 1
    gezaehlt = sum(1 for d in bezirke if d["counted"])
    if place is not None:
        bezirke = [d for d in bezirke if any(p["name"] == place for p in d["places"])]
        # Größter Anteil im Ortsbereich zuerst — der Bezirk, der „am meisten"
        # dazugehört, steht oben.
        bezirke.sort(key=lambda d: (-next(p["share"] for p in d["places"] if p["name"] == place), d["number"]))
    return ElectionMap(
        election=_choice(w), elections=[_choice(m) for m in moeglich],
        phase="before" if gezaehlt == 0 else ("complete" if gezaehlt == len(urne) else "counting"),
        contestants=wer,
        postal_share_pct=round(100 * brief / alle, 1) if alle else None,
        total=len(urne), counted=gezaehlt,
        wins=[ElectionMapWin(slug=s, districts=n) for s, n in sorted(siege.items(), key=lambda t: (-t[1], t[0]))],
        place=place, districts=bezirke,
        areas=_areas(zeilen, {d["area"] for d in bezirke} if place is not None else None),
    )
