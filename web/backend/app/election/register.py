"""Das Kandidatenregister: wer auf welcher Liste in welchem Wahlbereich steht.

Quelle ist ``kommunalwahl/kandidaten.json`` (aus der amtlichen Bekanntmachung,
s. ``kommunalwahl/kandidaten.py``), dazu die Farben aus
``kommunalwahl/parteien-meta.json``. Der Index einer Liste (1…16) ist die
Spaltennummer ``D<n>`` in den Open-Data-CSVs des Votemanagers.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# Repo-Wurzel: web/backend/app/election/ -> vier Ebenen hoch.
KOMMUNALWAHL = Path(__file__).resolve().parents[4] / "kommunalwahl"


@dataclass(frozen=True)
class Candidate:
    position: int
    name: str
    occupation: str | None
    born: int | None


@dataclass(frozen=True)
class Party:
    index: int
    slug: str
    short: str
    official: str
    kind: str
    color: str
    color_dark: str
    #: Wahlbereich -> Bewerber*innen in Listenreihenfolge.
    areas: dict[int, tuple[Candidate, ...]]

    def candidates(self, area: int) -> tuple[Candidate, ...]:
        return self.areas.get(area, ())

    @property
    def candidates_total(self) -> int:
        return sum(len(c) for c in self.areas.values())


@dataclass(frozen=True)
class Area:
    number: int
    roman: str
    name: str


@dataclass(frozen=True)
class Register:
    date: str
    seats: int
    title: str
    areas: tuple[Area, ...]
    parties: tuple[Party, ...]

    def party(self, index: int) -> Party | None:
        return next((p for p in self.parties if p.index == index), None)

    def by_slug(self, slug: str) -> Party | None:
        return next((p for p in self.parties if p.slug == slug), None)


def _colors() -> dict[str, tuple[str, str]]:
    meta = json.loads((KOMMUNALWAHL / "parteien-meta.json").read_text(encoding="utf-8"))
    return {k: (v["farbe"], v["farbe_dunkel"]) for k, v in meta.items() if isinstance(v, dict) and "farbe" in v}


@lru_cache(maxsize=1)
def load(path: Path | None = None) -> Register:
    raw = json.loads(((path or KOMMUNALWAHL / "kandidaten.json")).read_text(encoding="utf-8"))
    colors = _colors()
    parties = []
    for l in raw["lists"]:
        color, color_dark = colors.get(l["slug"], ("#6b7a8c", "#a3b1c2"))
        areas = {
            int(a): tuple(Candidate(c["position"], c["name"], c.get("occupation"), c.get("born")) for c in cs)
            for a, cs in l["areas"].items()
        }
        parties.append(Party(l["index"], l["slug"], l["short"], l["official"], l["kind"], color, color_dark, areas))
    return Register(
        date=raw["election"]["date"],
        seats=int(raw["election"]["seats"]),
        title=raw["election"]["title"],
        areas=tuple(Area(a["number"], a["roman"], a["name"]) for a in raw["areas"]),
        parties=tuple(parties),
    )
