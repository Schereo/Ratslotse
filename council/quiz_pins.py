"""„Wo liegt das?" — Orte auf der Karte setzen (Plan Q7).

Ein Ort mit Namen, man setzt einen Pin; gewertet wird die Entfernung zur
**Geometrie** des Orts, nicht zu einem Mittelpunkt: Wer den Pin irgendwo auf
die Nadorster Straße setzt, liegt richtig, auch wenn die Straße drei Kilometer
lang ist. Auf einer Fläche (Fliegerhorst, Schlossgarten) ist die Entfernung 0.

Die Kandidaten sind verortete Themen (``council_entities``, Art ``place``) mit
mindestens :data:`MIN_DECISIONS` Beschlüssen — gemessen am Abzug vom
23.09.2026 sind das 55 mit Geometrie (42 Straßen, 12 Flächen, 1 Linie).
Bekanntheit leiht sich das Spiel also vom Rat: Was oft beraten wird, kennt man
eher.

Die Entfernung rechnet eine lokale äquirektanguläre Projektion — für ein
Stadtgebiet von 15 km genauer als nötig, und ohne shapely, das bewusst nicht in
den Requirements steht.
"""
from __future__ import annotations

import json
import math
import random

MIN_DECISIONS = 10
#: (bis Meter, Punkte) — darüber 0.
POINT_STEPS = ((150, 3), (500, 2), (1500, 1))

_M_PER_DEG_LAT = 110_540.0


def _project(lat0: float):
    k = 111_320.0 * math.cos(math.radians(lat0))
    return lambda lon, lat: ((lon) * k, (lat) * _M_PER_DEG_LAT)


def _seg_dist(p, a, b) -> float:
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _in_ring(p, ring) -> bool:
    x, y = p
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def distance_m(geometry: dict, lat: float, lon: float) -> float | None:
    """Meter vom Punkt zur Geometrie (Point, LineString, MultiLineString,
    Polygon, MultiPolygon). Innerhalb einer Fläche 0. ``None`` bei einer
    Geometrie, die hier nicht vorkommt."""
    proj = _project(lat)
    p = proj(lon, lat)
    t, coords = geometry.get("type"), geometry.get("coordinates")
    if t == "Point":
        return math.hypot(*(a - b for a, b in zip(p, proj(*coords))))
    lines: list[list] = []
    polygons: list[list] = []
    if t == "LineString":
        lines = [coords]
    elif t == "MultiLineString":
        lines = coords
    elif t == "Polygon":
        polygons = [coords]
    elif t == "MultiPolygon":
        polygons = coords
    else:
        return None
    for poly in polygons:
        outer = [proj(*c) for c in poly[0]]
        holes = [[proj(*c) for c in r] for r in poly[1:]]
        if _in_ring(p, outer) and not any(_in_ring(p, h) for h in holes):
            return 0.0
        lines.extend(poly)
    best = math.inf
    for line in lines:
        pts = [proj(*c) for c in line]
        for a, b in zip(pts, pts[1:]):
            best = min(best, _seg_dist(p, a, b))
    return best if best < math.inf else None


def points_for(distance: float) -> int:
    for limit, pts in POINT_STEPS:
        if distance <= limit:
            return pts
    return 0


def describe(distance: float) -> str:
    """„genau drauf", „380 m daneben", „1,4 km daneben"."""
    if distance < 20:
        return "genau drauf"
    if distance < 1000:
        return f"{int(round(distance, -1))} m daneben"
    return f"{distance / 1000:.1f} km daneben".replace(".", ",")


def candidates(store) -> list[dict]:
    """Alle spielbaren Orte: Name, Geometrie (entpackt), Mittelpunkt."""
    return candidates_from(store.quiz_pin_rows(MIN_DECISIONS))


def candidates_from(rows) -> list[dict]:
    out = []
    for r in rows:
        try:
            geometry = json.loads(r["geojson"])
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(geometry, dict) or geometry.get("type") not in (
                "Point", "LineString", "MultiLineString", "Polygon", "MultiPolygon"):
            continue
        kind = "Straße" if "Line" in geometry["type"] else "Ort"
        out.append({"slug": r["slug"], "name": r["name"], "kind_label": kind,
                    "lat": r["lat"], "lon": r["lon"], "geometry": geometry})
    return out


def round_(store, n: int) -> list[dict]:
    pool = candidates(store)
    random.shuffle(pool)
    return [{"slug": c["slug"], "name": c["name"], "kind_label": c["kind_label"]} for c in pool[:n]]
