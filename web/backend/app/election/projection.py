"""Hochrechnung: Was die noch nicht ausgezählten Wahlbezirke beitragen dürften.

Kein Modell mit Anspruch, sondern das, was man am Wahlabend im Kopf tut:
Für jeden offenen Bezirk sein Ergebnis von 2021, skaliert mit dem Swing, den
die schon ausgezählten Bezirke desselben Wahlbereichs für diese Liste zeigen
(``Stimmen 2026 / Stimmen 2021`` über die ausgezählten Bezirke). Eine Liste
ohne 2021er Vergleich (BSW, PGM, …) bekommt ihren bisherigen Stimmenanteil
auf die geschätzten gültigen Stimmen der offenen Bezirke.

Ist im Wahlbereich noch nichts ausgezählt, gilt der stadtweite Swing; ist
stadtweit noch nichts ausgezählt, gibt es keine Hochrechnung.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .votemanager import AreaRow, area_of_district, district_number


@dataclass(frozen=True)
class ProjectedList:
    counted: int
    projected: float

    @property
    def factor(self) -> float:
        return self.projected / self.counted if self.counted > 0 else 0.0


@dataclass
class Projection:
    #: Wahlbereich -> Listenindex -> (ausgezählt, hochgerechnet)
    lists: dict[int, dict[int, ProjectedList]]
    #: Wahlbezirke 2026 ohne Gegenstück 2021 (Nummern) — Hinweis, kein Fehler.
    unmatched: list[int]


def _by_number(rows: Iterable[AreaRow]) -> dict[int, AreaRow]:
    out: dict[int, AreaRow] = {}
    for r in rows:
        n = district_number(r.name, None)
        if n is not None:
            out[n] = r
    return out


def _valid(row: AreaRow) -> int:
    return sum(lr.total or 0 for lr in row.lists.values())


def project(
    areas: dict[int, AreaRow],
    districts: list[AreaRow],
    reference_districts: list[AreaRow],
    indices: Iterable[int],
) -> Projection | None:
    """``areas`` sind die Wahlbereichszeilen (Stand), ``districts`` die
    Bezirkszeilen 2026, ``reference_districts`` die von 2021 — beide schon auf
    2026-Listenindizes geschlüsselt."""
    indices = list(indices)
    now = _by_number(districts)
    ref = _by_number(reference_districts)
    counted = {n: r for n, r in now.items() if r.counted}
    if not counted:
        return None
    unmatched = sorted(n for n in counted if n not in ref)

    def sums(numbers: Iterable[int], rows: dict[int, AreaRow]) -> tuple[dict[int, int], int]:
        per: dict[int, int] = {i: 0 for i in indices}
        valid = 0
        for n in numbers:
            r = rows.get(n)
            if r is None:
                continue
            for i in indices:
                lr = r.lists.get(i)
                per[i] += (lr.total or 0) if lr else 0
            valid += _valid(r)
        return per, valid

    city_now, city_valid_now = sums(counted, now)
    city_ref, city_valid_ref = sums(counted, ref)
    out: dict[int, dict[int, ProjectedList]] = {}
    for a in sorted(areas):
        in_area_now = [n for n in counted if area_of_district(n) == a]
        open_ref = [n for n in ref if area_of_district(n) == a and n not in counted]
        v_now, valid_now = sums(in_area_now, now)
        v_ref, valid_ref = sums(in_area_now, ref)
        v_open, valid_open = sums(open_ref, ref)
        # Ohne ausgezählten Bezirk im Wahlbereich: stadtweiter Swing.
        base_now, base_ref, base_valid_now, base_valid_ref = (
            (v_now, v_ref, valid_now, valid_ref) if in_area_now else (city_now, city_ref, city_valid_now, city_valid_ref)
        )
        turnout = base_valid_now / base_valid_ref if base_valid_ref > 0 else 1.0
        out[a] = {}
        for i in indices:
            official = areas[a].lists.get(i) if a in areas else None
            counted_votes = official.total if official and official.total is not None else v_now[i]
            if base_ref[i] > 0:
                est = v_open[i] * (base_now[i] / base_ref[i])
            elif base_valid_now > 0:
                est = (base_now[i] / base_valid_now) * valid_open * turnout
            else:
                est = 0.0
            out[a][i] = ProjectedList(counted_votes, counted_votes + est)
    return Projection(out, unmatched)
