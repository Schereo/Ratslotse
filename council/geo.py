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
