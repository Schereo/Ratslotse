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
"""
from __future__ import annotations

import threading
import time
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ..antworten import (
    ElectionArea,
    ElectionAreaParty,
    ElectionCandidate,
    ElectionHistoryPoint,
    ElectionMandate,
    ElectionNight,
    ElectionParty,
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


# ------------------------------------------------------------------ Bausteine

def _pct(part: int | None, whole: int | None) -> float | None:
    if part is None or not whole:
        return None
    return round(100 * part / whole, 2)


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
            has_persons = lr is not None and (lr.list_votes is not None or lr.candidates is not None)
            cands: dict[int, int] | None = None
            list_votes: int | None = None
            if has_persons and lr is not None:
                persons = True
                cands = {c.position: (lr.candidates or {}).get(c.position, 0) for c in cands_reg}
                list_votes = lr.list_votes if lr.list_votes is not None else max(total - sum(cands.values()), 0)
            lists.append(DistrictList(p.slug, a.number, total, list_votes, cands, len(cands_reg)))
    return lists, persons


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
        total = round(pl.projected)
        if pl.counted > 0 and dl.candidates is not None and dl.list_votes is not None:
            f = pl.factor
            cands = {k: round(v * f) for k, v in dl.candidates.items()}
            out.append(DistrictList(dl.party, dl.district, total, round(dl.list_votes * f), cands, dl.n_candidates))
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
            name = c.name if c else None
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


# ------------------------------------------------------------------ Zusammensetzen

def compose(reg: Register, ref: Reference, snap: Snapshot, dataset: str) -> ElectionNight:
    area_rows = {r.number: r for r in snap.areas if r.number is not None}
    city = snap.city[0] if snap.city else None
    expected = sum(r.reports_expected for r in area_rows.values()) or len(snap.districts)
    received = sum(r.reports_received for r in area_rows.values())
    phase = "before" if received == 0 else ("complete" if received >= expected else "counting")
    notes: list[str] = []

    lists, persons = _district_lists(reg, area_rows)
    alloc = allocate(lists, reg.seats) if phase != "before" else None
    if alloc:
        notes += alloc.ties
        if alloc.vacant:
            notes.append(f"{alloc.vacant} Sitz(e) bleiben unbesetzt (§ 36 Abs. 7 NKWG).")
    if phase != "before" and not persons:
        notes.append("Die Personenstimmen liegen noch nicht vor — Sitze je Liste und Wahlbereich ja, Namen noch nicht.")

    projection: Projection | None = None
    proj_alloc: Allocation | None = None
    proj_lists: list[DistrictList] = lists
    if phase == "counting":
        ref_districts = [ref.remap(r, reg) for r in ref.districts]
        projection = project(area_rows, snap.districts, ref_districts, [p.index for p in reg.parties])
        if projection is not None:
            proj_lists = _scaled(lists, projection, reg)
            proj_alloc = allocate(proj_lists, reg.seats)
            if projection.unmatched:
                notes.append(f"{len(projection.unmatched)} ausgezählte Wahlbezirke haben kein Gegenstück von 2021.")
    elif phase == "complete":
        proj_alloc = alloc
    proj_by_list = {(dl.party, dl.district): dl for dl in proj_lists}

    votes_by_party, valid_city = _votes_by_party(reg, city, area_rows)

    parties: list[ElectionParty] = []
    for p in reg.parties:
        votes = votes_by_party.get(p.slug)
        gain, loss = party_seat_margins(lists, reg.seats, p.slug, CAP_PARTY) if alloc else (None, None)
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
                if alloc and persons and v is not None:
                    vts = votes_to_seat(lists, reg.seats, p.slug, a.number, c.position, CAP_CANDIDATE)
                cands.append(ElectionCandidate(
                    position=c.position, name=c.name, occupation=c.occupation, born=c.born,
                    votes=v, elected=_kind(alloc, p.slug, a.number, c.position),
                    projected_votes=pv, projected_elected=_kind(proj_alloc, p.slug, a.number, c.position),
                    votes_to_seat=vts,
                ))
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

_lock = threading.Lock()
_live: tuple[float, ElectionNight] | None = None
_building = False
_probes: dict[int | None, ElectionNight] = {}


def build_live() -> ElectionNight:
    snap = votemanager.fetch()
    night = compose(load_register(), load_reference(), snap, "live")
    night["history"] = history.record(night)
    return night


def _refresh() -> None:
    global _live, _building
    try:
        result = build_live()
        with _lock:
            _live = (time.monotonic(), result)
    finally:
        with _lock:
            _building = False


def live() -> ElectionNight:
    """Das aktuelle Bild; nach Ablauf wird im Hintergrund erneuert."""
    global _live, _building
    with _lock:
        cached = _live
        if cached and time.monotonic() - cached[0] < TTL_SECONDS:
            return cached[1]
        if cached and not _building:
            _building = True
            threading.Thread(target=_refresh, name="wahlabend-refresh", daemon=True).start()
        if cached:
            return cached[1]
        _building = True
    _refresh()
    with _lock:
        assert _live is not None
        return _live[1]


def probe(counted: int | None) -> ElectionNight:
    with _lock:
        if counted in _probes:
            return _probes[counted]
    reg, ref = load_register(), load_reference()
    result = compose(reg, ref, probe_snapshot(reg, ref, counted), "probe")
    result["history"] = probe_history(reg, ref, counted)
    with _lock:
        _probes[counted] = result
    return result


def reset() -> None:
    global _live, _building
    with _lock:
        _live = None
        _building = False
        _probes.clear()
    history.reset()
    votemanager.reset_cache()
