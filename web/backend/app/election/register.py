"""Das Kandidatenregister: wer auf welcher Liste in welchem Wahlbereich steht.

Quelle ist ``kommunalwahl/kandidaten.json`` (aus der amtlichen Bekanntmachung,
s. ``kommunalwahl/kandidaten.py``), dazu die Farben aus
``kommunalwahl/parteien-meta.json``. Der Index einer Liste (1…16) ist die
Spaltennummer ``D<n>`` in den Open-Data-CSVs des Votemanagers.

**Der Notausgang ``WAHLABEND_COLUMNS``.** Diese Gleichsetzung — Reihenfolge
der Bekanntmachung = Spaltenreihenfolge der CSV — ist eine Annahme, keine
Zusage der Stadt. Stimmt sie am 13.09.2026 nicht, rechnet der Dienst weiter
und schreibt Volts Stimmen den PIRATEN gut; ``crosscheck.py`` merkt es und
schreibt es in ``Snapshot.warnings``, aber niemand kann es dann noch mergen,
testen und deployen. Also eine Umgebungsvariable::

    WAHLABEND_COLUMNS=gruene,spd,cdu,linke,fdp,afd,piraten,volt,…

Kommagetrennte Slugs in **Spaltenreihenfolge**; der erste wird ``D1``, der
zweite ``D2``. Wer auf welcher Liste steht, bleibt davon unberührt — die
Kandidatenlisten hängen am Slug, nicht am Index. In die ``.env``, Dienst neu
starten, fertig: kein Deploy, kein Merge, kein Nachtdienst.

Ein unbekannter Slug, eine Wiederholung oder die falsche Anzahl heißt: Die
Variable wird **ganz** verworfen (mit einer WARNING im Log) und die Vorgabe
aus ``kandidaten.json`` bleibt. Eine halb angewandte Reihenfolge wäre
schlimmer als gar keine.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

# Repo-Wurzel: web/backend/app/election/ -> vier Ebenen hoch.
KOMMUNALWAHL = Path(__file__).resolve().parents[4] / "kommunalwahl"

_log = logging.getLogger("ratslotse.web.wahlabend")


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


def _reordered(parties: list[Party]) -> list[Party]:
    """``WAHLABEND_COLUMNS`` angewandt — oder die Vorgabe, wenn etwas nicht passt.

    Der Notausgang für eine falsche Spaltenreihenfolge (s. Modul-Docstring).
    """
    raw = os.environ.get("WAHLABEND_COLUMNS", "").strip()
    if not raw:
        return parties
    wanted = [s.strip() for s in raw.split(",") if s.strip()]
    by_slug = {p.slug: p for p in parties}
    unknown = [s for s in wanted if s not in by_slug]
    if unknown:
        _log.warning("WAHLABEND_COLUMNS nennt unbekannte Listen (%s) — die Reihenfolge aus "
                     "kandidaten.json bleibt.", ", ".join(unknown))
        return parties
    if len(wanted) != len(parties) or len(set(wanted)) != len(wanted):
        _log.warning("WAHLABEND_COLUMNS nennt %d Listen (%d verschiedene), das Register hat %d — die "
                     "Reihenfolge aus kandidaten.json bleibt.", len(wanted), len(set(wanted)), len(parties))
        return parties
    _log.warning("WAHLABEND_COLUMNS setzt die Spaltenreihenfolge auf: %s", ", ".join(wanted))
    return [replace(by_slug[slug], index=i) for i, slug in enumerate(wanted, start=1)]


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
    parties = _reordered(parties)
    return Register(
        date=raw["election"]["date"],
        seats=int(raw["election"]["seats"]),
        title=raw["election"]["title"],
        areas=tuple(Area(a["number"], a["roman"], a["name"]) for a in raw["areas"]),
        parties=tuple(parties),
    )
