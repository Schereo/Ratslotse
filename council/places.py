"""Zentraler Ratslotse-Katalog für Oldenburger Ortsbereiche.

Oldenburg hat keine amtlich festgelegten Stadtteile. Ratslotse verwendet daher
eine dokumentierte, flächendeckende Arbeitsebene aus 31 lokal gebräuchlichen
Gebieten. Dieses Modul liefert den versionierten Basiskatalog; im laufenden
Betrieb ergänzt ``CouncilStore.all_places()`` redaktionell geprüfte Kandidaten.
Suche, Karten, Quiz und KI-Pipeline beziehen Namen, Aliase und stabile IDs aus
diesem gemeinsamen Laufzeitkatalog.
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
    parent_ids: tuple[str, ...]
    description: str | None
    source_ids: tuple[str, ...]
    filterable: bool
    quiz_enabled: bool
    lat: float | None
    lon: float | None

    @property
    def is_primary(self) -> bool:
        return self.kind == "ortsbereich"


def _lookup_key(value: str | None) -> str:
    value = (value or "").strip().casefold().replace("ß", "ss")
    value = value.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    return "-".join(re.findall(r"[a-z0-9]+", value))


@lru_cache(maxsize=1)
def catalog() -> dict:
    data = json.loads(_CATALOG.read_text(encoding="utf-8"))
    if data.get("schema_version") != 2:
        raise ValueError("Unbekannte Ortskatalog-Version")
    rows = data.get("places") or []
    ids = [row.get("id") for row in rows]
    names = [row.get("name") for row in rows]
    primary = [row for row in rows if row.get("kind") == "ortsbereich"]
    if len(set(ids)) != len(ids) or len(set(names)) != len(names):
        raise ValueError("Ortskatalog muss eindeutige IDs und Namen enthalten")
    if len(primary) != 31 or any(not row.get("wahlbereiche") for row in primary):
        raise ValueError("Ortskatalog muss exact 31 flächendeckende Ortsbereiche enthalten")
    kinds = set(data.get("kinds") or {})
    source_ids = {source.get("id") for source in data.get("sources") or []}
    for row in rows:
        if row.get("kind") not in kinds:
            raise ValueError(f"Unbekannter Ortstyp: {row.get('kind')}")
        if any(parent not in ids for parent in row.get("parent_ids") or []):
            raise ValueError(f"Unbekannter Elternort bei {row.get('id')}")
        if any(source not in source_ids for source in row.get("source_ids") or []):
            raise ValueError(f"Unbekannte Quelle bei {row.get('id')}")
    return data


@lru_cache(maxsize=1)
def all_places() -> tuple[Place, ...]:
    return tuple(Place(
        id=row["id"],
        name=row["name"],
        kind=row["kind"],
        aliases=tuple(row.get("aliases") or ()),
        wahlbereiche=tuple(row.get("wahlbereiche") or ()),
        parent_ids=tuple(row.get("parent_ids") or ()),
        description=row.get("description"),
        source_ids=tuple(row.get("source_ids") or ()),
        filterable=bool(row.get("filterable", row.get("kind") == "ortsbereich")),
        quiz_enabled=bool(row.get("quiz_enabled", row.get("kind") == "ortsbereich")),
        lat=float(row["lat"]) if row.get("lat") is not None else None,
        lon=float(row["lon"]) if row.get("lon") is not None else None,
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


def primary_places() -> tuple[Place, ...]:
    """Die 31 flächendeckenden Ratslotse-Ortsbereiche."""
    return tuple(place for place in all_places() if place.is_primary)


def secondary_places() -> tuple[Place, ...]:
    """Kuratierte Quartiere, Schutzgebiete, Parks und andere Teilräume."""
    return tuple(place for place in all_places() if not place.is_primary)


def primary_parents(place: Place | str | None) -> tuple[Place, ...]:
    """Direkt zugeordnete flächendeckende Ortsbereiche eines Ortsobjekts."""
    resolved = resolve(place) if isinstance(place, str) else place
    if not resolved:
        return ()
    if resolved.is_primary:
        return (resolved,)
    return tuple(parent for parent_id in resolved.parent_ids
                 if (parent := resolve(parent_id)) and parent.is_primary)


def find_mentions(text: str, max_n: int = 3,
                  catalog_places: tuple[Place, ...] | list[Place] | None = None) -> list[Place]:
    """Explizit genannte Katalogorte, längste überlappungsfrei zuerst.

    So gewinnt ``Neu-Donnerschwee`` gegen das darin enthaltene
    ``Donnerschwee``. Die Erkennung ist deterministisch und akzeptiert dieselben
    Schreibvarianten wie :func:`resolve`.
    """
    folded = _lookup_key(text)
    candidates: list[tuple[int, int, Place]] = []
    for place in catalog_places if catalog_places is not None else all_places():
        for value in (place.name, *place.aliases):
            key = _lookup_key(value)
            if not key:
                continue
            match = re.search(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", folded)
            if match:
                candidates.append((match.start(), match.end(), place))
    chosen: list[tuple[int, int, Place]] = []
    seen: set[str] = set()
    for start, end, place in sorted(candidates, key=lambda item: (-(item[1] - item[0]), item[0])):
        if place.id in seen or any(start < old_end and end > old_start
                                   for old_start, old_end, _ in chosen):
            continue
        chosen.append((start, end, place))
        seen.add(place.id)
    return [item[2] for item in sorted(chosen, key=lambda item: item[0])[:max_n]]


def kind_label(kind: str) -> str:
    return str((catalog().get("kinds") or {}).get(kind) or kind)


def public_place(place: Place) -> dict:
    row = asdict(place)
    row["kind_label"] = kind_label(place.kind)
    row["parents"] = [
        {"id": parent.id, "name": parent.name, "kind": parent.kind}
        for parent_id in place.parent_ids if (parent := resolve(parent_id))
    ]
    sources = {source["id"]: source for source in catalog()["sources"]}
    row["sources"] = [sources[source_id] for source_id in place.source_ids
                      if source_id in sources]
    return row


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
        "kinds": data["kinds"],
        "sources": data["sources"],
        "places": [public_place(place) for place in all_places()],
    }
