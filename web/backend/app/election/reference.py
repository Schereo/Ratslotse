"""Die Ratswahl 2021 als Referenz: Vergleichswerte und Basis der Hochrechnung.

Die drei Open-Data-CSVs von 2021 liegen unter ``kommunalwahl/referenz-2021/``
(altes Spaltenschema, s. ``votemanager.py``), dazu ``ratswahl-2021.json`` mit
der amtlichen Sitzverteilung und der Zuordnung 2021-Spalte -> Liste 2026.

Die Wahlbezirke sind 2026 genauso geschnitten und nummeriert wie 2021 (133,
gleiche Wahllokale). Deshalb kann die Hochrechnung für einen noch nicht
ausgezählten Bezirk sein 2021er Ergebnis nehmen und mit dem Swing skalieren,
den die schon ausgezählten Bezirke desselben Wahlbereichs zeigen.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .register import KOMMUNALWAHL, Register
from .votemanager import AreaRow, ListRow, parse

REFERENZ = KOMMUNALWAHL / "referenz-2021"


@dataclass(frozen=True)
class Reference:
    seats_total: int
    #: 2021-Spaltenindex -> Slug der Liste (``None``: 2026 nicht mehr dabei).
    slug_by_index: dict[int, str | None]
    seats_by_slug: dict[str, int]
    share_by_slug: dict[str, float]
    city: AreaRow
    areas: list[AreaRow]
    districts: list[AreaRow]

    def remap(self, row: AreaRow, register: Register) -> AreaRow:
        """Dieselbe Zeile, die Listen nach 2026-Indizes umgeschlüsselt; Listen
        ohne Nachfolger 2026 fallen weg."""
        lists: dict[int, ListRow] = {}
        for idx, lr in row.lists.items():
            slug = self.slug_by_index.get(idx)
            party = register.by_slug(slug) if slug else None
            if party is None:
                continue
            lists[party.index] = ListRow(party.index, lr.total, lr.list_votes, lr.candidate_sum, lr.candidates)
        return AreaRow(row.name, row.number, row.reports_expected, row.reports_received, row.eligible,
                       row.voters, row.invalid_ballots, row.valid_ballots, row.valid_votes, lists)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


@lru_cache(maxsize=1)
def load(folder: Path = REFERENZ) -> Reference:
    meta = json.loads(_read(folder / "ratswahl-2021.json"))
    slug_by_index = {int(p["index"]): p.get("slug") for p in meta["parteien"]}
    label_to_slug = {p["label"]: p.get("slug") for p in meta["parteien"]}
    seats: dict[str, int] = {}
    for s in meta["sitzverteilung"]:
        slug = label_to_slug.get(s["party"])
        if slug:
            seats[slug] = seats.get(slug, 0) + 1
    city = parse(_read(folder / "ratswahl-2021-stadt.csv"))[0]
    share: dict[str, float] = {}
    valid = sum(lr.total or 0 for lr in city.lists.values())
    for idx, lr in city.lists.items():
        slug = slug_by_index.get(idx)
        if slug and valid:
            share[slug] = round(100 * (lr.total or 0) / valid, 2)
    return Reference(
        seats_total=int(meta["sitze_gesamt"]),
        slug_by_index=slug_by_index,
        seats_by_slug=seats,
        share_by_slug=share,
        city=city,
        areas=parse(_read(folder / "ratswahl-2021-wahlbereiche.csv")),
        districts=parse(_read(folder / "ratswahl-2021-wahlbezirke.csv")),
    )
