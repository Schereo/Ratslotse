"""Oldenburger Ratslotse-Ortsbereiche & Wahlbereiche im Backend.

Der gemeinsame Katalog in :mod:`council.places` liefert Namen, stabile IDs,
Aliase und die Ortsbereich→Wahlbereich-Zuordnung. Die vereinfachten Polygone
(``web/frontend/public/geo/…``) liefern nur die Geometrie für die
Punkt-in-Polygon-Zuordnung. Damit lassen sich verortete Ratsentitäten
(``council_entity_meta.lat/lon``) einem Ortsbereich und darüber einem
Wahlbereich zuordnen — die Grundlage der gebietsbezogenen Quizfragen.

Die historischen ``stadtteil_*``-Funktionen bleiben als kompatible Aliase für
DB-Spalten und API-Verträge bestehen. Fachlich heißt die Ebene Ortsbereich:
Oldenburg besitzt keine amtlich festgelegten Stadtteile.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from . import places

_ROOT = Path(__file__).resolve().parent.parent
_GEOJSON = _ROOT / "web" / "frontend" / "public" / "geo" / "stadtteile-oldenburg.json"

# Ortsbereich → Wahlbereich(e) (1–6). Manche Gebiete liegen über einer
# Wahlbereichs-Grenze und gehören zu MEHREREN Bereichen — die werden in allen
# gelistet. Ermittelt aus der flächenmäßigen Überlappung der Ortsbereich-Polygone
# (OSM) mit den offiziellen Wahlbereich-Polygonen (openGEOdata Stadt Oldenburg,
# FeatureServer „Wahlen", Layer 1; Stand 2026-07): ein Ortsbereich zählt zu jedem
# Bereich, der ≥10 % seiner Fläche abdeckt (darunter ist es Grenz-/Simplify-
# Rauschen). Erster Eintrag = überwiegender Bereich. Ausschließlich im zentralen
# Ortskatalog pflegen; Frontend und Backend beziehen daraus dieselben Werte.
WAHLBEREICH: dict[str, list[int]] = {
    place.name: list(place.wahlbereiche) for place in places.primary_places()
}

WAHLBEREICHE = sorted({w for ws in WAHLBEREICH.values() for w in ws})


# Bezeichnungen, die die GANZE Stadt meinen — ein Punkt-Marker dafür (mitten in
# die Innenstadt gepinnt) trägt keine Information und wirkt wie ein Fehler.
_CITY_NAMES = frozenset({
    "oldenburg", "oldenburg (oldb)", "oldenburg (oldenburg)",
    "stadt oldenburg", "oldenburg (oldbg)",
})


def is_city_generic(name: str | None) -> bool:
    """True, wenn `name` nur „Oldenburg" als Ganzes bezeichnet (kein konkreter
    Ort) — solche Karten-Pins werden unterdrückt."""
    return (name or "").strip().lower() in _CITY_NAMES


def ortsbereiche() -> list[str]:
    """Alle kanonischen Ratslotse-Ortsbereichsnamen (alphabetisch)."""
    return sorted(place.name for place in places.primary_places())


def stadtteile() -> list[str]:
    """Kompatibler Altname für :func:`ortsbereiche`."""
    return ortsbereiche()


def ortsbereiche_im_wahlbereich(wb: int) -> list[str]:
    """Ortsbereiche eines Wahlbereichs (1–6) — inkl. Grenzgebiete, die auch
    zu anderen Bereichen gehören."""
    return sorted(n for n, ws in WAHLBEREICH.items() if wb in ws)


def stadtteile_im_wahlbereich(wb: int) -> list[str]:
    """Kompatibler Altname für :func:`ortsbereiche_im_wahlbereich`."""
    return ortsbereiche_im_wahlbereich(wb)


def wahlbereiche_of(stadtteil: str) -> list[int]:
    """Wahlbereich(e) eines Ortsbereichs (überwiegender zuerst) — leer, wenn
    unbekannt."""
    place = places.resolve(stadtteil)
    return list(place.wahlbereiche) if place else []


@lru_cache(maxsize=1)
def _features() -> list[dict]:
    """Geladene Ortsbereichs-Polygone; leer, wenn die Datei fehlt (Backend läuft
    dann ohne Geo-Zuordnung weiter — die Quizfragen stützen sich primär auf
    Wikipedia je Gebietsname)."""
    try:
        return json.loads(_GEOJSON.read_text(encoding="utf-8")).get("features", [])
    except (OSError, ValueError):
        return []


@lru_cache(maxsize=1)
def _by_name() -> dict[str, dict]:
    """Ortsbereichsname → GeoJSON-Feature (für die Polygon-Ausgabe)."""
    return {n: f for f in _features()
            if (n := (f.get("properties") or {}).get("name"))}


def is_stadtteil(name: str) -> bool:
    """Kompatibler Altname für :func:`is_ortsbereich`."""
    return is_ortsbereich(name)


def is_ortsbereich(name: str) -> bool:
    """True, wenn ``name`` im Katalog steht und ein Polygon besitzt."""
    place = places.resolve(name)
    return bool(place and place.name in _by_name())


def stadtteil_polygon(name: str) -> dict | None:
    """Kompatibler Altname für :func:`ortsbereich_polygon`."""
    return ortsbereich_polygon(name)


def ortsbereich_polygon(name: str) -> dict | None:
    """GeoJSON-Geometrie (Polygon/MultiPolygon) eines Ortsbereichs, oder None.
    Für die Quiz-Auflösungskarte, wenn kein Punkt/keine Straße vorliegt: das
    ganze Gebiet wird eingezeichnet. Wir besitzen die Polygone selbst → das ist
    immer verlässlich (nie eine falsche Stelle, anders als bei geratenen Pins)."""
    place = places.resolve(name)
    geom = (_by_name().get(place.name if place else "") or {}).get("geometry") or {}
    if geom.get("type") in ("Polygon", "MultiPolygon") and geom.get("coordinates"):
        return {"type": geom["type"], "coordinates": geom["coordinates"]}
    return None


def stadtteil_center(name: str) -> tuple[float, float] | None:
    """Kompatibler Altname für :func:`ortsbereich_center`."""
    return ortsbereich_center(name)


def ortsbereich_center(name: str) -> tuple[float, float] | None:
    """Grober Mittelpunkt (Bounding-Box-Zentrum) eines Ortsbereichs → (lat, lon),
    für Initial-View/Label der Karte. None, wenn unbekannt."""
    geom = ortsbereich_polygon(name)
    if not geom:
        return None
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    lons = [pt[0] for poly in polys for ring in poly for pt in ring]
    lats = [pt[1] for poly in polys for ring in poly for pt in ring]
    if not lons:
        return None
    return ((min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2)


def nachbar_ortsbereiche(name: str, anzahl: int = 3) -> list[str]:
    """Die ``anzahl`` nächstgelegenen Ortsbereiche — „direkt nebenan".

    Über den Abstand der Mittelpunkte statt über gemeinsame Grenzpunkte: Die
    Polygone sind per Douglas-Peucker auf ~25 m vereinfacht, gemeinsame Ecken
    überleben das nicht zuverlässig. Für „welche liegen nah?" reicht der
    Abstand, und er kann nicht ins Leere laufen.

    Der ``cos(φ)``-Faktor muss sein: Auf 53° Nord ist ein Längengrad nur gut
    0,6 Breitengrade breit, ohne ihn würde die Nachbarschaft in Ost-West-
    Richtung systematisch zu weit gerechnet.
    """
    import math

    hier = ortsbereich_center(name)
    if not hier:
        return []
    kos = math.cos(math.radians(hier[0]))
    entfernt = []
    for place in places.primary_places():
        if place.name == name:
            continue
        dort = ortsbereich_center(place.name)
        if not dort:
            continue
        dlat = dort[0] - hier[0]
        dlon = (dort[1] - hier[1]) * kos
        entfernt.append((math.hypot(dlat, dlon), place.name))
    entfernt.sort()
    return [n for _, n in entfernt[:anzahl]]


def _in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def stadtteil_for(lat: float, lon: float) -> str | None:
    """Kompatibler Altname für :func:`ortsbereich_for`."""
    return ortsbereich_for(lat, lon)


def ortsbereich_for(lat: float, lon: float) -> str | None:
    """Ortsbereich für einen Punkt, oder None (außerhalb Oldenburgs).
    Nur der Außenring zählt — die vereinfachten Grenzen haben keine Löcher."""
    for f in _features():
        geom = f.get("geometry") or {}
        polys = geom.get("coordinates") or []
        if geom.get("type") == "Polygon":
            polys = [polys]
        for poly in polys:
            if poly and _in_ring(lon, lat, poly[0]):
                return (f.get("properties") or {}).get("name")
    return None
