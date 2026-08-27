"""Zentraler Ratslotse-Katalog für Oldenburger Ortsbereiche.

Oldenburg hat keine amtlich festgelegten Stadtteile. Ratslotse verwendet daher
eine dokumentierte, flächendeckende Arbeitsebene aus 31 lokal gebräuchlichen
Gebieten. Suche, Karten, Quiz und KI-Pipeline müssen Namen, Aliase und stabile
IDs ausschließlich aus diesem Katalog beziehen.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

_CATALOG = Path(__file__).with_name("oldenburg_places.json")


@dataclass(frozen=True)
class Place:
    id: str
    name: str
    kind: str
    aliases: tuple[str, ...]
    wahlbereiche: tuple[int, ...]


def _lookup_key(value: str | None) -> str:
    value = (value or "").strip().casefold().replace("ß", "ss")
    value = value.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    return "-".join(re.findall(r"[a-z0-9]+", value))


@lru_cache(maxsize=1)
def catalog() -> dict:
    data = json.loads(_CATALOG.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("Unbekannte Ortskatalog-Version")
    rows = data.get("places") or []
    ids = [row.get("id") for row in rows]
    names = [row.get("name") for row in rows]
    if len(rows) != 31 or len(set(ids)) != len(ids) or len(set(names)) != len(names):
        raise ValueError("Ortskatalog muss 31 eindeutige IDs und Namen enthalten")
    if any(row.get("kind") != "ortsbereich" or not row.get("wahlbereiche") for row in rows):
        raise ValueError("Ungültiger Ortsbereich im Katalog")
    return data


@lru_cache(maxsize=1)
def all_places() -> tuple[Place, ...]:
    return tuple(Place(
        id=row["id"],
        name=row["name"],
        kind=row["kind"],
        aliases=tuple(row.get("aliases") or ()),
        wahlbereiche=tuple(row.get("wahlbereiche") or ()),
    ) for row in catalog()["places"])


@lru_cache(maxsize=1)
def _by_key() -> dict[str, Place]:
    out: dict[str, Place] = {}
    for place in all_places():
        for value in (place.id, place.name, *place.aliases):
            key = _lookup_key(value)
            if key in out and out[key] != place:
                raise ValueError(f"Mehrdeutiger Ortsalias: {value}")
            out[key] = place
    return out


def resolve(value: str | None) -> Place | None:
    """Kanonischen Ortsbereich zu ID, Anzeigename oder Alias liefern."""
    return _by_key().get(_lookup_key(value))


def canonical_name(value: str | None) -> str | None:
    place = resolve(value)
    return place.name if place else None


def public_catalog() -> dict:
    """Katalog ohne interne Dateipfade, direkt für die Web-API geeignet."""
    data = catalog()
    return {
        "schema_version": data["schema_version"],
        "id": data["id"],
        "label": data["label"],
        "singular": data["singular"],
        "plural": data["plural"],
        "definition": data["definition"],
        "sources": data["sources"],
        "places": [asdict(place) for place in all_places()],
    }
