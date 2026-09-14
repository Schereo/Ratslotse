"""Eine frühere Wahl als Referenz: Vergleichswerte und Basis der Hochrechnung.

Ein Referenzordner (heute ``kommunalwahl/referenz-2021/``, seit 09/2026 auch
``referenz-2026/``) trägt die drei Open-Data-CSVs jener Wahl und eine
Meta-Datei mit der Sitzverteilung und der Zuordnung Spalte -> Liste der
FOLGENDEN Wahl. Woran der Ordner erkannt wird: Die Meta-Datei heißt
``<name>-<jahr>.json`` (``ratswahl-2021.json``), und die CSVs tragen deren
Namen als Präfix (``ratswahl-2021-stadt.csv``). Mehr Konvention braucht es
nicht — angelegt werden beide von ``scripts/wahl_einfrieren.py``.

Die Wahlbezirke waren 2026 genauso geschnitten und nummeriert wie 2021 (133,
gleiche Wahllokale). Deshalb kann die Hochrechnung für einen noch nicht
ausgezählten Bezirk sein Ergebnis der Vorwahl nehmen und mit dem Swing
skalieren, den die schon ausgezählten Bezirke desselben Wahlbereichs zeigen.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .register import KOMMUNALWAHL, Register
from .votemanager import AreaRow, ListRow, parse

REFERENZ = KOMMUNALWAHL / "referenz-2021"
#: So heißt die Meta-Datei eines Referenzordners — und nur sie.
META_NAME = re.compile(r"[a-z]+-\d{4}\.json")


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


def meta_path(folder: Path) -> Path:
    """Die Meta-Datei des Ordners — ``<name>-<jahr>.json``.

    Der Ausdruck ist absichtlich eng, und die Nachbardateien sind es auch:
    Neben der Meta-Datei liegen ``termin.json``, ``verlauf.json`` und
    ``praesentation-*.json`` — keine davon trägt eine Jahreszahl, genau damit
    hier eindeutig bleibt, welche die Meta-Datei ist.
    """
    treffer = sorted(p for p in folder.glob("*.json") if META_NAME.fullmatch(p.name))
    if len(treffer) != 1:
        raise FileNotFoundError(
            f"{folder}: erwartet genau EINE Meta-Datei <name>-<jahr>.json, gefunden: "
            + (", ".join(p.name for p in treffer) or "keine"))
    return treffer[0]


def load(folder: Path | None = None) -> Reference:
    """Der Referenzordner der aktiven Wahl — oder ein genannter.

    Welcher die Vorgabe ist, sagt die Wahl (``reference`` in
    ``kommunalwahl/wahlen/``): 2026 ist es ``referenz-2021``, bei der nächsten
    Kommunalwahl ``referenz-2026``.
    """
    from . import elections
    return _load(folder or elections.active().reference_folder or REFERENZ)


@lru_cache(maxsize=4)
def _load(folder: Path) -> Reference:
    datei = meta_path(folder)
    praefix = datei.stem
    meta = json.loads(_read(datei))
    slug_by_index = {int(p["index"]): p.get("slug") for p in meta["parteien"]}
    label_to_slug = {p["label"]: p.get("slug") for p in meta["parteien"]}
    seats: dict[str, int] = {}
    for s in meta["sitzverteilung"]:
        slug = label_to_slug.get(s["party"])
        if slug:
            seats[slug] = seats.get(slug, 0) + 1
    city = parse(_read(folder / f"{praefix}-stadt.csv"))[0]
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
        areas=parse(_read(folder / f"{praefix}-wahlbereiche.csv")),
        districts=parse(_read(folder / f"{praefix}-wahlbezirke.csv")),
    )


def reset() -> None:
    """Zwischenspeicher leeren — dieselbe Rolle wie ``presentation.reset``.

    Bis 09/2026 riefen Tests dafür ``load.cache_clear()``; seit ``load`` die
    Vorgabe VOR dem Zwischenspeicher auflöst, hängt der am inneren ``_load``.
    Ein eigener Name ist ohnehin der bessere Vertrag.
    """
    _load.cache_clear()
