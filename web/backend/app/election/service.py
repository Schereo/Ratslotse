"""Der Wahlabend als EINE Antwort: Stand, Sitze, Namen, Hochrechnung.

Zwei Betriebsarten:

* **live** — die drei CSVs des Votemanagers (``votemanager.fetch``), einmal je
  Minute. Das Zusammensetzen dauert rund zwei Sekunden (die Abstände „wie
  viele Stimmen bis zum Sitz" sind je Kandidat*in eine Binärsuche über die
  ganze Zuteilung); deshalb wird das fertige Bild gehalten und nach Ablauf im
  Hintergrund erneuert, während die alte Antwort weiter ausgeliefert wird.
* **probe** — die Zahlen von 2021 im Register von 2026 (Generalprobe), auf
  Wunsch mit nur den ersten ``counted`` Wahlbezirken ausgezählt. So lässt sich
  die Seite vor dem Wahlabend mit echten Zahlen ansehen, und die Hochrechnung
  hat eine Antwort, die sie treffen muss (das Endergebnis von 2021).

Dazu der **Verlauf** (``history.py``): Jedes fertige Live-Bild hinterlässt
einen Punkt, die Generalprobe bekommt eine synthetische Reihe.

**Der Abend darf an nichts sterben.** Was der Votemanager meldet, steht nicht
in unserer Hand: eine leere Spalte, eine Bezirksdatei, die der
Wahlbereichsdatei vorausläuft, eine Liste, die es im Register nicht gibt.
``live()`` wirft deshalb NIE — es fällt in Stufen zurück (volles Bild →
Bild ohne Hochrechnung und Abstände → letzter guter Stand mit Vermerk →
leeres Bild mit Fehlertext), und jede Stufe sagt in ``notes``, dass sie
gegriffen hat. Ein 500er am Wahlabend wäre die einzige Antwort, die niemand
gebrauchen kann.
"""
from __future__ import annotations

import logging
import math
import threading
import time
from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import cast
from zoneinfo import ZoneInfo

from ..antworten import (
    ElectionArea,
    ElectionAreaParty,
    ElectionCandidate,
    ElectionHistoryPoint,
    ElectionMandate,
    ElectionNight,
    ElectionParty,
    ElectionSource,
    ElectionTotals,
)
from . import history, votemanager
from .projection import Projection, project
from .reference import Reference
from .reference import load as load_reference
from .register import Register
from .register import load as load_register
from .seats import Allocation, DistrictList, allocate, party_seat_margins, votes_to_seat
from .votemanager import AreaRow, ListRow, Snapshot

#: Suchgrenzen der Abstände. Größer heißt nur „außer Reichweite".
CAP_PARTY = 80_000
CAP_CANDIDATE = 30_000
TTL_SECONDS = votemanager.TTL_SECONDS
#: So lange wartet ein Aufruf auf das erste Bild, statt es selbst zu bauen.
BUILD_WAIT_SECONDS = 30.0

#: Die Vermerke der Rückfallstufen. Sie stehen in ``notes`` — Menschentext,
#: kein neues Feld: Der Vertrag bleibt, wie er ist, und beide Clients zeigen
#: die Hinweise schon.
NOTE_REDUCED = "Hochrechnung und Abstände sind gerade ausgesetzt — die ausgezählten Zahlen stimmen."
NOTE_STALE = "Der Abruf klemmt gerade — angezeigt wird der letzte gelungene Stand."
NOTE_EMPTY = "Der Stand ist im Moment nicht abrufbar; die Seite versucht es weiter."

_log = logging.getLogger(__name__)


# ------------------------------------------------------------------ Bausteine

def _pct(part: int | None, whole: int | None) -> float | None:
    """Ein Anteil in Prozent — oder ``None``, wenn die Zahlen keinen ergeben.

    Am Wahlabend kommt, was gemeldet wird: eine leere Spalte, eine negative
    Zahl (Tippfehler in einer Schnellmeldung), eine Teilsumme, die größer ist
    als die Summe, in die sie gehört (zwei Dateien, zwei Stände). „−4 %" oder
    „380 %" sähen aus wie ein Ergebnis; ``None`` heißt „unbekannt", und genau
    das zeigen beide Clients dann auch an."""
    if part is None or not whole or part < 0 or whole < 0:
        return None
    try:
        value = round(100 * part / whole, 2)
    except (OverflowError, ZeroDivisionError):
        return None
    return value if 0 <= value <= 100 else None


def _round(value: float) -> int | None:
    """``round``, ohne daran zu sterben. Aus einer verunglückten Meldung kann
    in der Hochrechnung ``inf`` oder ``nan`` werden — ``round`` wirft darauf."""
    if not math.isfinite(value):
        return None
    try:
        return round(value)
    except (OverflowError, ValueError):
        return None


def _totals(row: AreaRow | None) -> ElectionTotals:
    if row is None:
        return ElectionTotals(eligible=None, voters=None, turnout_pct=None, valid_votes=None, invalid_ballots=None)
    return ElectionTotals(
        eligible=row.eligible,
        voters=row.voters,
        turnout_pct=_pct(row.voters, row.eligible),
        valid_votes=row.valid_votes,
        invalid_ballots=row.invalid_ballots,
    )


def _votes_by_party(reg: Register, city: AreaRow | None, area_rows: dict[int, AreaRow]) -> tuple[dict[str, int | None], int | None]:
    """Stimmen je Wahlvorschlag und die gültigen Stimmen der Stadt — die
    Grundlage aller Anteile. Die Stadtzeile ist die Quelle; solange sie noch
    leer ist, summieren die sechs Wahlbereiche."""
    valid_city = city.valid_votes if city and city.valid_votes is not None else None
    if valid_city is None and area_rows:
        s = sum(r.valid_votes or 0 for r in area_rows.values())
        valid_city = s or None
    votes: dict[str, int | None] = {}
    for p in reg.parties:
        lr = city.lists.get(p.index) if city else None
        v = lr.total if lr and lr.total is not None else None
        if v is None and area_rows:
            per_area = [r.lists.get(p.index) for r in area_rows.values()]
            if any(x is not None and x.total is not None for x in per_area):
                v = sum(x.total or 0 for x in per_area if x)
        votes[p.slug] = v
    return votes, valid_city


def _district_lists(reg: Register, area_rows: dict[int, AreaRow]) -> tuple[list[DistrictList], bool]:
    """Die Wahlvorschläge je Wahlbereich als Eingabe der Zuteilung — und ob
    irgendwo schon Personenstimmen vorliegen."""
    lists: list[DistrictList] = []
    persons = False
    for a in reg.areas:
        row = area_rows.get(a.number)
        for p in reg.parties:
            cands_reg = p.candidates(a.number)
            if not cands_reg:
                continue  # tritt in diesem Wahlbereich nicht an
            lr = row.lists.get(p.index) if row else None
            counted = lr is not None and lr.total is not None
            total = lr.total if lr and lr.total is not None else 0
            if p.kind == "einzelbewerber":
                lists.append(DistrictList(p.slug, a.number, total, 0, {1: total} if counted else None, 1))
                continue
            # Personenstimmen gelten erst als da, wenn die KANDIDATENSPALTEN
            # gefüllt sind. Listenstimmen allein reichen nicht: Alle
            # Bewerber*innen stünden dann bei 0, und die Sitze gingen nach
            # § 36 Abs. 6 der Reihe nach an die Liste — das sähe aus wie ein
            # Ergebnis und wäre keins. Fehlen umgekehrt nur die Listenstimmen,
            # ergeben sie sich aus Gesamt − Σ Personen.
            has_persons = lr is not None and lr.candidates is not None
            cands: dict[int, int] | None = None
            list_votes: int | None = None
            n_candidates = len(cands_reg)
            if has_persons and lr is not None:
                persons = True
                cands = {c.position: (lr.candidates or {}).get(c.position, 0) for c in cands_reg}
                # Spalten, die das Register nicht kennt, zählen trotzdem mit —
                # sonst fehlten ihre Stimmen in der Personensumme und die
                # Aufteilung Liste/Personen (§ 36 Abs. 4) kippte still.
                for k, v in (lr.candidates or {}).items():
                    if k not in cands:
                        cands[k] = v
                n_candidates = max(n_candidates, max(cands, default=0))
                list_votes = lr.list_votes if lr.list_votes is not None else max(total - sum(cands.values()), 0)
            lists.append(DistrictList(p.slug, a.number, total, list_votes, cands, n_candidates))
    return lists, persons


def _official_check(reg: Register, alloc: Allocation, official: dict[str, int] | None) -> list[str]:
    """Die eigene Zuteilung gegen die Sitzverteilung des Votemanagers.

    Er rechnet dasselbe Verfahren; weichen die Sitze je Liste ab, ist entweder
    eine Spalte vertauscht oder ein Absatz anders gelesen — beides gehört
    sichtbar auf die Seite, nicht erst in die Zeitung am Montag. Nur am Ende
    der Auszählung: Zwischenstände holen beide zu verschiedenen Minuten."""
    if not official:
        return []
    diffs = []
    for p in reg.parties:
        theirs = official.get(p.slug)
        if theirs is None:
            continue
        ours = alloc.seats_by_party.get(p.slug, 0)
        if ours != theirs:
            diffs.append(f"{p.short} {theirs} statt {ours}")
    if not diffs:
        return []
    return ["Die Sitzverteilung des Votemanagers weicht von der eigenen Zuteilung ab: " + ", ".join(diffs)
            + " — Zuordnung prüfen!"]


def _scaled(lists: Iterable[DistrictList], projection: Projection, reg: Register) -> list[DistrictList]:
    """Die Listen auf die Hochrechnung skaliert — Personen- und Listenstimmen
    im selben Verhältnis wie die Summe."""
    out: list[DistrictList] = []
    for dl in lists:
        party = reg.by_slug(dl.party)
        pl = projection.lists.get(dl.district, {}).get(party.index) if party else None
        if pl is None:
            out.append(dl)
            continue
        total = _round(pl.projected)
        if total is None:  # keine Zahl herausgekommen: lieber der gezählte Stand
            out.append(dl)
            continue
        if pl.counted > 0 and dl.candidates is not None and dl.list_votes is not None:
            f = pl.factor
            cands = {k: _round(v * f) or 0 for k, v in dl.candidates.items()}
            out.append(DistrictList(dl.party, dl.district, total, _round(dl.list_votes * f) or 0, cands, dl.n_candidates))
        else:
            out.append(DistrictList(dl.party, dl.district, total, None, None, dl.n_candidates))
    return out


def _mandates(alloc: Allocation | None, reg: Register) -> list[ElectionMandate]:
    if alloc is None:
        return []
    out: list[ElectionMandate] = []
    for m in alloc.mandates:
        party = reg.by_slug(m.party)
        name = None
        if party and m.position is not None:
            c = next((c for c in party.candidates(m.district) if c.position == m.position), None)
            name = c.name if c else f"Listenplatz {m.position} (nicht im Register)"
        out.append(ElectionMandate(slug=m.party, area=m.district, position=m.position, name=name, votes=m.votes, kind=m.kind))
    order = {p.slug: i for i, p in enumerate(reg.parties)}
    out.sort(key=lambda m: (order.get(m["slug"], 99), m["area"], m["position"] or 0))
    return out


def _kind(alloc: Allocation | None, slug: str, area: int, position: int) -> str | None:
    if alloc is None:
        return None
    for m in alloc.mandates:
        if m.party == slug and m.district == area and m.position == position:
            return m.kind
    return None


def _fill_areas(reg: Register, area_rows: dict[int, AreaRow], districts: list[AreaRow],
                notes: list[str]) -> dict[int, AreaRow]:
    """Wahlbereiche aus ihren Bezirken summieren, solange die
    Wahlbereichsdatei nachhinkt.

    Die drei CSVs entstehen beim Votemanager nacheinander; zwischen zwei
    Abrufen kann die Bezirksdatei voraus sein. Ohne diesen Schritt stünde ein
    Wahlbereich minutenlang auf null, obwohl seine Zahlen längst da sind — und
    das sähe nach einem Wahlbereich aus, in dem niemand gewählt hat."""
    by_area: dict[int, list[AreaRow]] = {}
    for row in districts:
        n = votemanager.district_number(row.name, None)
        a = votemanager.area_of_district(n) if n is not None else None
        if a is not None:
            by_area.setdefault(a, []).append(row)
    out = dict(area_rows)
    for area in reg.areas:
        row = out.get(area.number)
        if row is not None and row.valid_votes is not None:
            continue
        mine = by_area.get(area.number, [])
        if not any(d.counted for d in mine):
            continue
        agg = _aggregate(row.name if row else f"{area.roman} - {area.name}", area.number, mine)
        if row is not None and row.reports_expected > agg.reports_expected:
            # Wie viele Bezirke es GIBT, weiß die Wahlbereichsdatei besser als
            # eine Bezirksdatei, die noch nicht alle Zeilen trägt.
            agg = replace(agg, reports_expected=row.reports_expected)
        out[area.number] = agg
        notes.append(f"Wahlbereich {area.roman} aus den Bezirken summiert — die Wahlbereichsdatei hinkt nach.")
    return out


def _fill_city(city: AreaRow | None, area_rows: dict[int, AreaRow], notes: list[str]) -> AreaRow | None:
    """Dasselbe eine Ebene höher. Die Stimmen je Liste holt sich
    ``_votes_by_party`` ohnehin aus den Wahlbereichen; hier geht es um
    Wahlberechtigte, Wähler*innen und die gültigen Stimmen der Stadt."""
    if city is not None and city.valid_votes is not None:
        return city
    if not any(r.counted for r in area_rows.values()):
        return city
    agg = _aggregate(city.name if city else "Stadt Oldenburg", None, list(area_rows.values()))
    if city is not None and city.reports_expected > agg.reports_expected:
        agg = replace(agg, reports_expected=city.reports_expected)
    notes.append("Die Stadtzeile ist noch leer — die Summen stammen aus den Wahlbereichen.")
    return agg


# ------------------------------------------------------------------ Zusammensetzen

def compose(reg: Register, ref: Reference, snap: Snapshot, dataset: str, *,
            margins: bool = True, projection: bool = True) -> ElectionNight:
    """Ein Stand als fertige Antwort.

    ``margins=False`` lässt die Abstände weg (``votes_to_seat``,
    ``party_seat_margins`` — je eine Binärsuche über die ganze Zuteilung),
    ``projection=False`` die Hochrechnung. Beides zusammen ist die abgespeckte
    Stufe aus ``build_live``: lieber die ausgezählten Zahlen ohne Zugaben als
    gar keine Antwort."""
    notes: list[str] = []
    area_rows = _fill_areas(reg, {r.number: r for r in snap.areas if r.number is not None},
                            snap.districts, notes)
    city = _fill_city(snap.city[0] if snap.city else None, area_rows, notes)
    # Negative Meldungszahlen gibt es nicht; eine gäbe „complete" bei leerem Stand.
    expected = max(sum(r.reports_expected for r in area_rows.values()) or len(snap.districts), 0)
    received = max(sum(r.reports_received for r in area_rows.values()), 0)
    phase = "before" if received == 0 else ("complete" if received >= expected else "counting")

    # Warnungen des Abrufs (Spaltenreihenfolge, Kopfzeile) gehören sichtbar auf die Seite.
    notes += [w for w in getattr(snap, "warnings", []) if w not in notes]
    lists, persons = _district_lists(reg, area_rows)
    # Ohne eine einzige Stimme gibt es keine Zuteilung: Hare/Niemeyer verteilt
    # dann NICHTS, und „0 Sitze für alle" sähe aus wie ein Ergebnis. Der Fall
    # ist echt — eine Schnellmeldung ist gezählt, die Stimmspalten sind leer.
    has_votes = any(dl.total > 0 for dl in lists)
    alloc = allocate(lists, reg.seats) if phase != "before" and has_votes else None
    if alloc:
        notes += alloc.ties
        if alloc.vacant:
            notes.append(f"{alloc.vacant} Sitz(e) bleiben unbesetzt (§ 36 Abs. 7 NKWG).")
        if phase == "complete":
            notes += _official_check(reg, alloc, getattr(snap, "official_seats", None))
    if phase != "before" and not has_votes:
        notes.append("Es sind Wahlbezirke ausgezählt, aber noch keine Stimmen gemeldet — die Sitze folgen.")
    elif phase != "before" and not persons:
        notes.append("Die Personenstimmen liegen noch nicht vor — Sitze je Liste und Wahlbereich ja, Namen noch nicht.")

    proj: Projection | None = None
    proj_alloc: Allocation | None = None
    proj_lists: list[DistrictList] = lists
    if phase == "counting" and alloc and projection:
        ref_districts = [ref.remap(r, reg) for r in ref.districts]
        proj = project(area_rows, snap.districts, ref_districts, [p.index for p in reg.parties])
        if proj is not None:
            scaled = _scaled(lists, proj, reg)
            if any(dl.total > 0 for dl in scaled):
                proj_lists, proj_alloc = scaled, allocate(scaled, reg.seats)
            if proj.unmatched:
                notes.append(f"{len(proj.unmatched)} ausgezählte Wahlbezirke haben kein Gegenstück von 2021.")
    elif phase == "complete":
        proj_alloc = alloc
    proj_by_list = {(dl.party, dl.district): dl for dl in proj_lists}

    votes_by_party, valid_city = _votes_by_party(reg, city, area_rows)

    parties: list[ElectionParty] = []
    for p in reg.parties:
        votes = votes_by_party.get(p.slug)
        gain, loss = party_seat_margins(lists, reg.seats, p.slug, CAP_PARTY) if alloc and margins else (None, None)
        parties.append(ElectionParty(
            index=p.index, slug=p.slug, short=p.short, name=p.official, kind=p.kind,
            color=p.color, color_dark=p.color_dark, candidates_total=p.candidates_total,
            votes=votes, share_pct=_pct(votes, valid_city),
            seats=alloc.seats_by_party.get(p.slug, 0) if alloc else None,
            projected_seats=proj_alloc.seats_by_party.get(p.slug, 0) if proj_alloc else None,
            seats_2021=ref.seats_by_slug.get(p.slug),
            share_2021_pct=ref.share_by_slug.get(p.slug),
            votes_to_next_seat=gain, votes_to_lose_seat=loss,
        ))

    areas: list[ElectionArea] = []
    for a in reg.areas:
        row = area_rows.get(a.number)
        valid_area = row.valid_votes if row and row.valid_votes is not None else None
        area_parties: list[ElectionAreaParty] = []
        for p in reg.parties:
            cands_reg = p.candidates(a.number)
            if not cands_reg:
                continue
            lr = row.lists.get(p.index) if row else None
            dl_proj = proj_by_list.get((p.slug, a.number))
            cands: list[ElectionCandidate] = []
            for c in cands_reg:
                v = (lr.candidates or {}).get(c.position) if lr and lr.candidates is not None else None
                if p.kind == "einzelbewerber" and lr and lr.total is not None:
                    v = lr.total
                pv = None
                if dl_proj and dl_proj.candidates is not None:
                    pv = dl_proj.candidates.get(c.position)
                vts = None
                if alloc and margins and persons and v is not None:
                    vts = votes_to_seat(lists, reg.seats, p.slug, a.number, c.position, CAP_CANDIDATE)
                cands.append(ElectionCandidate(
                    position=c.position, name=c.name, occupation=c.occupation, born=c.born,
                    votes=v, elected=_kind(alloc, p.slug, a.number, c.position),
                    projected_votes=pv, projected_elected=_kind(proj_alloc, p.slug, a.number, c.position),
                    votes_to_seat=vts,
                ))
            # Listenplätze, die nur die CSV kennt: als namenlose Zeile zeigen und
            # melden — das Register stimmt dann nicht mehr mit dem Stimmzettel.
            bekannt = {c.position for c in cands_reg}
            csv_cands: dict[int, int] = dict(lr.candidates) if lr and lr.candidates else {}
            for k in sorted(k for k in csv_cands if k not in bekannt):
                v = csv_cands.get(k)
                cands.append(ElectionCandidate(
                    position=k, name=f"Listenplatz {k} (nicht im Register)", occupation=None, born=None,
                    votes=v, elected=_kind(alloc, p.slug, a.number, k),
                    projected_votes=None, projected_elected=_kind(proj_alloc, p.slug, a.number, k),
                    votes_to_seat=None,
                ))
                hinweis = f"{p.short} in Wahlbereich {a.roman}: Die CSV trägt Listenplatz {k}, das Register nicht — Register prüfen."
                if hinweis not in notes:
                    notes.append(hinweis)
            area_parties.append(ElectionAreaParty(
                slug=p.slug,
                votes=lr.total if lr else None,
                list_votes=lr.list_votes if lr else None,
                candidate_votes=lr.candidate_sum if lr else None,
                share_pct=_pct(lr.total if lr else None, valid_area),
                seats=alloc.seats_by_list.get((p.slug, a.number), 0) if alloc else None,
                projected_seats=proj_alloc.seats_by_list.get((p.slug, a.number), 0) if proj_alloc else None,
                candidates=cands,
            ))
        areas.append(ElectionArea(
            number=a.number, roman=a.roman, name=a.name,
            districts_total=row.reports_expected if row else 0,
            districts_counted=row.reports_received if row else 0,
            totals=_totals(row), parties=area_parties,
        ))

    return ElectionNight(
        dataset=dataset, phase=phase, person_votes_available=persons,
        election={"date": reg.date, "seats": reg.seats, "title": reg.title, "presentation_url": votemanager.presentation_url()},
        source={
            "fetched_at": snap.fetched_at.isoformat(timespec="seconds"),
            "last_modified": snap.last_modified, "ok": snap.ok, "error": snap.error,
        },
        progress={"districts_total": expected, "districts_counted": received},
        totals=_totals(city),
        parties=parties, areas=areas,
        mandates=_mandates(alloc, reg), projected_mandates=_mandates(proj_alloc, reg),
        notes=notes, computed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        history=[],
    )


# ------------------------------------------------------------------ Generalprobe

def _aggregate(name: str, number: int | None, rows: list[AreaRow]) -> AreaRow:
    def add(values: list[int | None]) -> int | None:
        known = [v for v in values if v is not None]
        return sum(known) if known else None

    indices = sorted({i for r in rows for i in r.lists})
    lists: dict[int, ListRow] = {}
    for i in indices:
        lrs = [r.lists[i] for r in rows if i in r.lists]
        cands: dict[int, int] = {}
        any_cands = False
        for lr in lrs:
            if lr.candidates is not None:
                any_cands = True
                for k, v in lr.candidates.items():
                    cands[k] = cands.get(k, 0) + v
        lists[i] = ListRow(i, add([lr.total for lr in lrs]), add([lr.list_votes for lr in lrs]),
                           add([lr.candidate_sum for lr in lrs]), cands if any_cands else None)
    return AreaRow(
        name=name, number=number,
        reports_expected=sum(r.reports_expected for r in rows),
        reports_received=sum(r.reports_received for r in rows),
        eligible=add([r.eligible for r in rows]), voters=add([r.voters for r in rows]),
        invalid_ballots=add([r.invalid_ballots for r in rows]), valid_ballots=add([r.valid_ballots for r in rows]),
        valid_votes=add([r.valid_votes for r in rows]), lists=lists,
    )


def _blank(row: AreaRow) -> AreaRow:
    lists = {i: ListRow(i, None, None, None, None) for i in row.lists}
    return AreaRow(row.name, row.number, row.reports_expected, 0, None, None, None, None, None, lists)


def probe_snapshot(reg: Register, ref: Reference, counted: int | None) -> Snapshot:
    districts = [ref.remap(r, reg) for r in ref.districts]
    if counted is not None:
        districts = [d if i < counted else _blank(d) for i, d in enumerate(districts)]
    areas = []
    for a in reg.areas:
        mine = [d for d in districts if (n := votemanager.district_number(d.name, None)) is not None
                and votemanager.area_of_district(n) == a.number]
        areas.append(_aggregate(f"{a.roman} - {a.name}", a.number, mine))
    city = _aggregate("Stadt Oldenburg", None, areas)
    return Snapshot([city], areas, districts, datetime.now(timezone.utc), None, True, None)


# ------------------------------------------------------------------ Verlauf

#: Die Generalprobe tut so, als begänne die Auszählung um 18:00 Uhr.
PROBE_START = datetime(2026, 9, 13, 18, 0, tzinfo=ZoneInfo("Europe/Berlin"))
PROBE_STEP = timedelta(minutes=15)


def summary(reg: Register, snap: Snapshot, at: str) -> ElectionHistoryPoint | None:
    """Ein Stand in Kurzform: Anteile je Liste und die Sitzzuteilung.

    ``compose`` ist dafür zu teuer — der Abstand „wie viele Stimmen bis zum
    Sitz" ist je Kandidat*in eine Binärsuche über die ganze Zuteilung. Ein
    Verlaufspunkt braucht davon nichts. ``None``, solange nichts ausgezählt
    ist: Ein Nullstand ist kein Punkt."""
    area_rows = {r.number: r for r in snap.areas if r.number is not None}
    counted = sum(r.reports_received for r in area_rows.values())
    if counted == 0:
        return None
    votes, valid_city = _votes_by_party(reg, snap.city[0] if snap.city else None, area_rows)
    lists, _ = _district_lists(reg, area_rows)
    alloc = allocate(lists, reg.seats)
    shares: dict[str, float] = {}
    for slug, v in votes.items():
        share = _pct(v, valid_city)
        if v and v > 0 and share is not None:
            shares[slug] = share
    return ElectionHistoryPoint(
        at=at, districts_counted=counted, shares=shares,
        seats={slug: n for slug, n in alloc.seats_by_party.items() if n > 0},
    )


def probe_history(reg: Register, ref: Reference, counted: int | None) -> list[ElectionHistoryPoint]:
    """Der Verlauf der Generalprobe: Stände in Zehnerschritten bis ``counted``
    (ohne Angabe bis zum letzten Wahlbezirk), ab 18:00 Uhr alle 15 Minuten."""
    target = counted if counted is not None else len(ref.districts)
    stops = list(range(10, target + 1, 10))
    if target > 0 and (not stops or stops[-1] != target):
        stops.append(target)
    out: list[ElectionHistoryPoint] = []
    for i, n in enumerate(stops):
        at = (PROBE_START + i * PROBE_STEP).astimezone(timezone.utc).isoformat(timespec="seconds")
        point = summary(reg, probe_snapshot(reg, ref, n), at)
        if point is not None:
            out.append(point)
    return out


# ------------------------------------------------------------------ Einstiege
#
# Vier Stufen, von oben nach unten, und keine wirft:
#
#   (a) das volle Bild — Zahlen, Hochrechnung, Abstände
#   (b) dasselbe ohne Hochrechnung und ohne Abstände (``compose`` abgespeckt)
#   (c) der letzte gute Stand, mit ``source.error`` und einem Vermerk in ``notes``
#   (d) ein Bild der Phase „before" mit ``source.ok=False`` und dem Fehlertext
#
# Gebaut wird immer nur EINMAL gleichzeitig: ``_cond`` lässt genau einen bauen,
# alle anderen warten auf dessen Ergebnis (``BUILD_WAIT_SECONDS``). Ohne das
# bauen beim ersten Aufruf — Cache leer, Schalter frisch umgelegt, viele
# Zuschauer — alle gleichzeitig dasselbe.

#: Sperre UND Wartezimmer. Sie schützt ``_live``, ``_building``, ``_probes``.
_cond = threading.Condition()
_live: tuple[float, ElectionNight] | None = None
_building = False
#: Woran der letzte Versuch gescheitert ist — für Stufe (d).
_last_error: str | None = None
_probes: dict[int | None, ElectionNight] = {}


def build_live() -> ElectionNight:
    """Stufe (a), und wenn dabei etwas bricht, Stufe (b)."""
    snap = votemanager.fetch()
    reg, ref = load_register(), load_reference()
    try:
        night = compose(reg, ref, snap, "live")
    except Exception:
        _log.exception("Wahlabend: das volle Bild ist gescheitert — es geht abgespeckt weiter.")
        night = compose(reg, ref, snap, "live", margins=False, projection=False)
        night["notes"].append(NOTE_REDUCED)
    try:
        night["history"] = history.record(night)
    except Exception:
        # Der Verlauf ist Zugabe; er darf den Abend nicht mitnehmen.
        _log.exception("Wahlabend: der Verlauf ließ sich nicht fortschreiben.")
        night["history"] = []
    return night


def _bare(error: str) -> ElectionNight:
    """Die letzte Reißleine: eine gültige Antwort, auch wenn nicht einmal das
    Register lesbar ist. Leere Listen sind wenig — ein 500er wäre weniger."""
    return ElectionNight(
        dataset="live", phase="before", person_votes_available=False,
        election={"date": "2026-09-13", "seats": 52,
                  "title": "Wahl des Rates der Stadt Oldenburg (Oldb)",
                  "presentation_url": votemanager.presentation_url()},
        source={"fetched_at": None, "last_modified": None, "ok": False, "error": error},
        progress={"districts_total": 0, "districts_counted": 0},
        totals=_totals(None), parties=[], areas=[], mandates=[], projected_mandates=[],
        notes=[NOTE_EMPTY], computed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        history=[],
    )


def _empty(error: str) -> ElectionNight:
    """Stufe (d): das Bild vor der Auszählung, mit dem Fehler im Kopf. Listen,
    Namen und Farben stehen im Register — die Seite kann also zeigen, wer
    antritt, und dazusagen, dass die Zahlen gerade nicht kommen."""
    snap = Snapshot([], [], [], datetime.now(timezone.utc), None, False, error)
    try:
        night = compose(load_register(), load_reference(), snap, "live", margins=False, projection=False)
    except Exception:
        _log.exception("Wahlabend: auch das leere Bild ist gescheitert.")
        return _bare(error)
    night["notes"].append(NOTE_EMPTY)
    return night


def _stale(night: ElectionNight, error: str | None) -> ElectionNight:
    """Stufe (c): derselbe Stand, aber mit Vermerk. Ohne ihn sähe ein
    eingefrorener Stand aus wie einer, der sich nur nicht mehr ändert."""
    out = cast(ElectionNight, dict(night))
    out["source"] = ElectionSource(
        fetched_at=night["source"]["fetched_at"], last_modified=night["source"]["last_modified"],
        ok=False, error=error,
    )
    out["notes"] = [n for n in night["notes"] if n != NOTE_STALE] + [NOTE_STALE]
    return out


def _refresh() -> None:
    """Erneuern — und niemals sterben, ohne dass der Cache es vermerkt."""
    global _live, _building, _last_error
    result: ElectionNight | None = None
    error: str | None = None
    try:
        result = build_live()
    except Exception as exc:
        _log.exception("Wahlabend: der Stand ließ sich nicht erneuern.")
        error = f"{type(exc).__name__}: {exc}"[:200]
    with _cond:
        if result is not None:
            _live, _last_error = (time.monotonic(), result), None
        else:
            _last_error = error
            if _live is not None:
                _live = (time.monotonic(), _stale(_live[1], error))
        _building = False
        _cond.notify_all()


def live() -> ElectionNight:
    """Das aktuelle Bild; nach Ablauf wird im Hintergrund erneuert.

    Wirft nicht. Was hier nicht zu bauen ist, wird zum letzten guten Stand mit
    Vermerk — und wenn es keinen gibt, zu einem leeren Bild mit Fehlertext."""
    global _building
    with _cond:
        cached = _live
        if cached and time.monotonic() - cached[0] < votemanager.ttl_seconds():
            return cached[1]
        if cached:
            # Der alte Stand geht sofort raus, erneuert wird nebenher.
            if not _building:
                _building = True
                try:
                    threading.Thread(target=_refresh, name="wahlabend-refresh", daemon=True).start()
                except RuntimeError:
                    _building = False
                    _log.exception("Wahlabend: kein Thread fürs Erneuern zu bekommen.")
            return cached[1]
        if _building:
            # Es gibt noch nichts, und jemand baut schon: warten ist billiger,
            # als dasselbe ein zweites Mal zu bauen.
            deadline = time.monotonic() + BUILD_WAIT_SECONDS
            while _building and _live is None:
                if not _cond.wait(timeout=max(0.0, deadline - time.monotonic())):
                    break
            if _live is not None:
                return _live[1]
            return _empty(_last_error or "Der erste Abruf dauert zu lange.")
        _building = True
    _refresh()  # außerhalb der Sperre: alle anderen warten derweil
    with _cond:
        if _live is not None:
            return _live[1]
        return _empty(_last_error or "Der Stand ist gerade nicht abrufbar.")


def probe(counted: int | None) -> ElectionNight:
    with _cond:
        if counted in _probes:
            return _probes[counted]
    reg, ref = load_register(), load_reference()
    result = compose(reg, ref, probe_snapshot(reg, ref, counted), "probe")
    result["history"] = probe_history(reg, ref, counted)
    with _cond:
        _probes[counted] = result
    return result


def reset() -> None:
    global _live, _building, _last_error
    with _cond:
        _live = None
        _building = False
        _last_error = None
        _probes.clear()
        _cond.notify_all()
    history.reset()
    votemanager.reset_cache()
