"""Oldenburger Stadtteile & Wahlbereiche im Backend.

Python-Spiegel von ``web/frontend/lib/stadtteile.ts``: dieselbe
Stadtteil→Wahlbereich-Zuordnung (Kommunalwahl, 6 Bereiche) und dieselben
vereinfachten Stadtteil-Polygone (``web/frontend/public/geo/…``) für die
Punkt-in-Polygon-Zuordnung. Damit lassen sich verortete Ratsentitäten
(``council_entity_meta.lat/lon``) einem Stadtteil und darüber einem
Wahlbereich zuordnen — die Grundlage der gebietsbezogenen Quizfragen.

Die GeoJSON-Datei ist die **eine** kanonische Quelle (das Frontend serviert
sie unter ``/geo/…``); dieses Modul liest sie repo-relativ, damit es keine
zweite, driftende Kopie gibt.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_GEOJSON = _ROOT / "web" / "frontend" / "public" / "geo" / "stadtteile-oldenburg.json"

# Stadtteil → Wahlbereich(e) (1–6). Manche Stadtteile liegen über einer
# Wahlbereichs-Grenze und gehören zu MEHREREN Bereichen — die werden in allen
# gelistet. Ermittelt aus der flächenmäßigen Überlappung der Stadtteil-Polygone
# (OSM) mit den offiziellen Wahlbereich-Polygonen (openGEOdata Stadt Oldenburg,
# FeatureServer „Wahlen", Layer 1; Stand 2026-07): ein Stadtteil zählt zu jedem
# Bereich, der ≥10 % seiner Fläche abdeckt (darunter ist es Grenz-/Simplify-
# Rauschen). Erster Eintrag = überwiegender Bereich. BEIDE Stellen pflegen
# (auch web/frontend/lib/stadtteile.ts).
WAHLBEREICH: dict[str, list[int]] = {
    "Bürgeresch": [1], "Bürgerfelde": [1, 3], "Donnerschwee": [1, 4], "Ehnernviertel": [1], "Ziegelhof": [1],
    "Bahnhofsviertel": [2], "Dobbenviertel": [2], "Drielake": [2], "Gerichtsviertel": [2],
    "Haarenesch": [2], "Innenstadt": [2], "Neuenwege": [2],
    "Bloherfelde": [3], "Dietrichsfeld": [3], "Fliegerhorst": [3], "Haarentor": [3, 6], "Wechloy": [3],
    "Alexandersfeld": [4], "Bornhorst": [4], "Etzhorn": [4], "Nadorst": [4], "Ofenerdiek": [4], "Ohmstede": [4],
    "Bümmerstede": [5], "Drielaker-Moor": [5, 2], "Kreyenbrück": [5], "Krusenbusch": [5],
    "Osternburg": [5, 2], "Tweelbäke": [5, 2],
    "Eversten": [6], "Nordmoslesfehn": [6],
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


def stadtteile() -> list[str]:
    """Alle Stadtteilnamen (alphabetisch)."""
    return sorted(WAHLBEREICH)


def stadtteile_im_wahlbereich(wb: int) -> list[str]:
    """Stadtteilnamen eines Wahlbereichs (1–6) — inkl. Grenzstadtteile, die auch
    zu anderen Bereichen gehören."""
    return sorted(n for n, ws in WAHLBEREICH.items() if wb in ws)


def wahlbereiche_of(stadtteil: str) -> list[int]:
    """Wahlbereich(e) eines Stadtteils (überwiegender zuerst) — leer, wenn
    unbekannt."""
    return WAHLBEREICH.get(stadtteil, [])


@lru_cache(maxsize=1)
def _features() -> list[dict]:
    """Geladene Stadtteil-Polygone; leer, wenn die Datei fehlt (Backend läuft
    dann ohne Geo-Zuordnung weiter — die Quizfragen stützen sich primär auf
    Wikipedia je Stadtteilname)."""
    try:
        return json.loads(_GEOJSON.read_text(encoding="utf-8")).get("features", [])
    except (OSError, ValueError):
        return []


@lru_cache(maxsize=1)
def _by_name() -> dict[str, dict]:
    """Stadtteilname → GeoJSON-Feature (für die Polygon-Ausgabe)."""
    return {n: f for f in _features()
            if (n := (f.get("properties") or {}).get("name"))}


def is_stadtteil(name: str) -> bool:
    """True, wenn `name` ein bekannter Oldenburger Stadtteil ist (Polygon da)."""
    return bool(name) and name in _by_name()


def stadtteil_polygon(name: str) -> dict | None:
    """GeoJSON-Geometrie (Polygon/MultiPolygon) eines Stadtteils, oder None.
    Für die Quiz-Auflösungskarte, wenn kein Punkt/keine Straße vorliegt: das
    ganze Gebiet wird eingezeichnet. Wir besitzen die Polygone selbst → das ist
    immer verlässlich (nie eine falsche Stelle, anders als bei geratenen Pins)."""
    geom = (_by_name().get(name or "") or {}).get("geometry") or {}
    if geom.get("type") in ("Polygon", "MultiPolygon") and geom.get("coordinates"):
        return {"type": geom["type"], "coordinates": geom["coordinates"]}
    return None


def stadtteil_center(name: str) -> tuple[float, float] | None:
    """Grober Mittelpunkt (Bounding-Box-Zentrum) eines Stadtteils → (lat, lon),
    für Initial-View/Label der Karte. None, wenn unbekannt."""
    geom = stadtteil_polygon(name)
    if not geom:
        return None
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    lons = [pt[0] for poly in polys for ring in poly for pt in ring]
    lats = [pt[1] for poly in polys for ring in poly for pt in ring]
    if not lons:
        return None
    return ((min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2)


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
    """Stadtteil-Name für einen Punkt, oder None (außerhalb Oldenburgs).
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
