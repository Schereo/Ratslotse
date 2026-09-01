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
import logging
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
    Wikipedia je Gebietsname).

    Das Fehlen wird ausdrücklich **geloggt**. Ohne Polygone liefert jede
    Ortsbereichs-Ableitung still ``None``, und ein Lauf sieht dann erfolgreich
    aus, während er nichts zuordnet — genau so lief ein Prüflauf am 01.09.2026
    ins Leere, weil das Verzeichnis der Datei nicht mitkopiert worden war.
    """
    try:
        return json.loads(_GEOJSON.read_text(encoding="utf-8")).get("features", [])
    except (OSError, ValueError) as fehler:
        logging.getLogger(__name__).warning(
            "Ortsbereichs-Polygone nicht lesbar (%s: %s) — jede Geo-Zuordnung "
            "liefert jetzt None, ohne dass ein Lauf scheitert.", _GEOJSON, fehler)
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


def _geometrie_punkte(geometrie: dict) -> list[tuple[float, float]]:
    """(lat, lon) aus beliebiger GeoJSON-Geometrie — ohne Fremdbibliothek."""
    art = geometrie.get("type")
    koord = geometrie.get("coordinates") or []
    if art == "Point":
        return [(koord[1], koord[0])] if len(koord) >= 2 else []
    if art in ("LineString", "MultiPoint"):
        return [(p[1], p[0]) for p in koord if len(p) >= 2]
    if art in ("MultiLineString", "Polygon"):
        return [(p[1], p[0]) for teil in koord for p in teil if len(p) >= 2]
    if art == "MultiPolygon":
        return [(p[1], p[0]) for poly in koord for ring in poly for p in ring if len(p) >= 2]
    return []


#: So viele Stützpunkte werden je Geometrie geprüft. Eine lange Straße hat
#: tausende; alle zu testen kostet Zeit und ändert am Mehrheitsverhältnis nichts.
GEOMETRIE_STUETZPUNKTE = 60


def ortsbereiche_der_geometrie(geometrie: dict | str | None) -> dict[str, int]:
    """Welche Ortsbereiche eine Geometrie berührt → ``{Name: Stützpunkte}``.

    **Warum das nötig ist.** Bis 09/2026 wurde der Ortsbereich eines Ortes aus
    einem einzigen Punkt abgeleitet — dem Mittelpunkt seiner Bounding-Box. Bei
    Flächen geht das; bei Straßen nicht: Eine Straße, die um eine Ecke geht, hat
    ihren Bounding-Box-Mittelpunkt NEBEN sich. Auf dem Prod-Bestand
    (01.09.2026 gemessen) lag „Alter Postweg" damit in keinem Ortsbereich,
    obwohl die Straße vollständig in Kreyenbrück verläuft; dasselbe bei
    Ziegelweg, Haaren und Tweelbäker See.

    Zurückgegeben werden ALLE berührten Bereiche mit ihrem Gewicht — eine
    Straße kann durch mehrere laufen, und das ist keine Ungenauigkeit, sondern
    die Wahrheit (die Haaren fließt durch sechs).
    """
    if not geometrie:
        return {}
    if isinstance(geometrie, str):
        import json
        try:
            geometrie = json.loads(geometrie)
        except (ValueError, TypeError):
            return {}
    if not isinstance(geometrie, dict):
        return {}
    punkte = _geometrie_punkte(geometrie)
    if not punkte:
        return {}
    schritt = max(1, len(punkte) // GEOMETRIE_STUETZPUNKTE)
    stimmen: dict[str, int] = {}
    for lat, lon in punkte[::schritt]:
        name = ortsbereich_for(lat, lon)
        if name:
            stimmen[name] = stimmen.get(name, 0) + 1
    return stimmen


def auf_stadtgebiet_beschneiden(geometrie: dict | str | None) -> dict | None:
    """Nur die Teile einer Geometrie behalten, die in Oldenburg liegen.

    **Warum das nötig ist.** Der Straßen-Geocoder fragt Overpass nach allen
    Wegen eines Namens in einem RECHTECK um Oldenburg — und das Rechteck ist
    größer als die Stadt. Bei häufigen Namen kommt damit der gleichnamige Weg
    der Nachbargemeinde mit ins Ergebnis, alle Segmente werden zu einer
    Geometrie verschmolzen, und deren Mittelpunkt liegt irgendwo dazwischen.
    Auf dem Prod-Snapshot (01.09.2026) lieferte „Alter Postweg" so eine
    Geometrie, die bei 53.0999 südlich der Stadt beginnt; der gespeicherte
    Punkt (53.173) lag in keinem Ortsbereich und die Straße war für den
    Stadtteil-Filter verloren — obwohl der Oldenburger Teil sauber in
    Kreyenbrück liegt.

    Die Polygone gehören uns und sind verlässlich; das Rechteck ist nur eine
    Vorauswahl. Deshalb wird hier nachgeschnitten. ``None``, wenn nichts von
    der Geometrie in der Stadt liegt — dann ist der Treffer keiner.
    """
    if isinstance(geometrie, str):
        import json
        try:
            geometrie = json.loads(geometrie)
        except (ValueError, TypeError):
            return None
    if not isinstance(geometrie, dict):
        return None
    art = geometrie.get("type")
    koord = geometrie.get("coordinates") or []

    def drin(linie) -> bool:
        # Ein Segment gehört zur Stadt, wenn IRGENDEIN Punkt darin liegt —
        # eine Straße darf am Rand aus dem Polygon herauslaufen.
        return any(ortsbereich_for(p[1], p[0]) for p in linie if len(p) >= 2)

    if art == "MultiLineString":
        behalten = [linie for linie in koord if drin(linie)]
        if not behalten:
            return None
        return {"type": "MultiLineString", "coordinates": behalten}
    if art == "LineString":
        return geometrie if drin(koord) else None
    # Flächen und Punkte bleiben unangetastet: Sie stammen aus Nominatim, das
    # seinerseits schon auf den Ausschnitt begrenzt ist.
    return geometrie


def ortsbereich_der_geometrie(geometrie: dict | str | None) -> str | None:
    """Der Ortsbereich, in dem eine Geometrie überwiegend liegt — oder None.

    Bei Gleichstand entscheidet der Name, damit zwei Läufe dasselbe Ergebnis
    liefern; ein zufällig wechselnder Stadtteil wäre schlimmer als ein
    willkürlich, aber stabil gewählter.
    """
    stimmen = ortsbereiche_der_geometrie(geometrie)
    if not stimmen:
        return None
    return sorted(stimmen.items(), key=lambda t: (-t[1], t[0]))[0][0]


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
