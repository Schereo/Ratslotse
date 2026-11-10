#!/usr/bin/env python3
"""Gebiete aus den Kartenbildern weiterer Pläne nachzeichnen (Fortsetzung von ``plan_umrisse.py``).

Dasselbe Vorgehen wie beim Wärmeplan, ohne Sprachmodell: Eine Karte wird über die Stadtgrenze, die sie
selbst zeigt, auf unsere Stadtgrenze gelegt; dann wird herausgelöst, was die Legende als Gebiet
ausweist (Schraffur, Umrandung). Wo ein Gebiet in OpenStreetMap mit Namen steht und der Plan das ganze
Gebiet meint (ein Friedhof), gilt der OSM-Umriss — er ist genauer als jedes Kartenbild.

Jede Fläche wird gegen das gehalten, was der Plan selbst sagt (Hektar aus seinen Tabellen, die
Ortsbereiche seiner Namen, eine Straße, die hindurchführen muss). Was nicht passt, wird nicht gezeichnet.

Vier Karten: Ruhige Gebiete (Lärmaktionsplan), Maßnahmenbereiche (Masterplan Stadtgrün), Suchräume
(Spielleitplanung), Zentren und Versorgungsbereiche (Einzelhandelskonzept — die Detailkarten haben keine
Stadtgrenze; sie werden über die grauen Gebäude der Grundkarte gegen die OSM-Gebäude verortet).
Ergebnis: ``council/plan_shapes/<plan>.geojson`` (eingecheckt). Braucht numpy, Pillow, shapely, PyMuPDF
und den Ortskatalog in ``data/``; die OSM-Daten holt ``--osm`` einmal nach ``~/.cache``.

    python scripts/plan_karten.py --osm              # einmal: OSM-Daten holen (~15 Minuten)
    python scripts/plan_karten.py                    # alle Karten (~2 Minuten)
    python scripts/plan_karten.py --nur laermaktionsplan
    python scripts/plan_karten.py --pruefen          # Dateien prüfen, ohne PDF
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))
sys.path.insert(0, str(WURZEL / "scripts"))

from council import geo, places, plan_state  # noqa: E402

import plan_umrisse as U  # noqa: E402
from plan_angaben import SPL_PLANNED  # noqa: E402

OSM_DIR = Path.home() / ".cache" / "ratslotse" / "plan-quellen" / "osm"
DISPLAY_SIMPLIFY = 0.00004


# ── Bausteine ──────────────────────────────────────────────────────────────

def city_ring_points():
    """Unsere Stadtgrenze in Mercator, alle 20 m ein Punkt."""
    import numpy as np
    from shapely.geometry import shape
    from shapely.ops import unary_union
    city = unary_union([shape(f["geometry"]) for f in geo._features()]).buffer(0)
    city = max(U._parts(city), key=lambda g: g.area)
    ring = [U._merc(x, y) for x, y in city.exterior.coords]
    return np.array([(x1 + (x2 - x1) * i / n, y1 + (y2 - y1) * i / n)
                     for (x1, y1), (x2, y2) in zip(ring, ring[1:])
                     for n in [max(1, int(math.hypot(x2 - x1, y2 - y1) / 20))] for i in range(n)])


def fit_boundary(line_mask) -> dict:
    """Die Linie der Stadtgrenze im Bild (``line_mask``) mit unserer Grenze zur Deckung bringen:
    Pixel → Mercator mit Maßstab ``s`` und Ursprung ``tx``/``ty`` (Norden oben)."""
    import numpy as np
    pts = city_ring_points()
    dist = U._distance(line_mask, 30.0)
    h, w = line_mask.shape

    def cost(s, tx, ty):
        px, py = (pts[:, 0] - tx) / s, (ty - pts[:, 1]) / s
        ok = (px >= 0) & (px < w - 1) & (py >= 0) & (py < h - 1)
        return 1e9 if ok.mean() < 0.98 else float(np.mean(dist[py[ok].astype(int), px[ok].astype(int)]))
    ys, xs = np.nonzero(line_mask)
    bx0, bx1, by0, by1 = (np.percentile(xs, 0.5), np.percentile(xs, 99.5), np.percentile(ys, 0.5),
                          np.percentile(ys, 99.5))
    s = max((pts[:, 0].max() - pts[:, 0].min()) / (bx1 - bx0), (pts[:, 1].max() - pts[:, 1].min()) / (by1 - by0))
    c, s, tx, ty = U._search(cost, (s, pts[:, 0].min() - bx0 * s, pts[:, 1].max() + by0 * s),
                             [(0.04, 25), (0.02, 12), (0.01, 6), (0.005, 3), (0.002, 1.2), (0.001, 0.5), (0.0005, 0.2)])
    return {"s": s, "tx": tx, "ty": ty, "fit_px": c}


def density_regions(mask, window: int, threshold: float, frame=None, min_px: float = 30):
    """Schraffierte Flächen: wo im Fenster genug Strich ist. → Pixel-Polygone (Löcher gefüllt)."""
    import numpy as np
    from shapely.geometry import Polygon, box
    from shapely.ops import unary_union
    h, w = mask.shape
    cs = np.pad(mask.astype(float), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    k = window // 2
    y0 = np.clip(np.arange(h) - k, 0, h)
    y1 = np.clip(np.arange(h) + k + 1, 0, h)
    x0 = np.clip(np.arange(w) - k, 0, w)
    x1 = np.clip(np.arange(w) + k + 1, 0, w)
    dens = (cs[y1][:, x1] - cs[y0][:, x1] - cs[y1][:, x0] + cs[y0][:, x0]) / ((y1 - y0)[:, None] * (x1 - x0)[None, :])
    m = dens > threshold
    if frame is not None:
        m &= frame
    rects = []
    for y in range(h):
        d = np.diff(np.concatenate([[0], m[y].astype(int), [0]]))
        rects += [box(float(a), y, float(b), y + 1) for a, b in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0])]
    poly = unary_union(rects).simplify(0.8)
    return [Polygon(p.exterior) for p in U._parts(poly) if p.area >= min_px]


def to_lonlat(px_poly, t: dict) -> dict:
    """Pixel-Polygon → GeoJSON in WGS84 über die Verortung ``t`` (s, tx, ty)."""
    from shapely.geometry import mapping
    return U._map_coords(dict(mapping(px_poly)),
                         lambda u, v, t=t: tuple(round(c, 6) for c in U._lonlat(t["tx"] + u * t["s"], t["ty"] - v * t["s"])))


def osm_polygons(path: Path) -> list[tuple[dict, object]]:
    """(Tags, shapely-Fläche) je Weg oder Relation einer Overpass-Antwort mit ``out geom``."""
    from shapely.geometry import LineString, Polygon
    from shapely.ops import linemerge, polygonize, unary_union
    out = []
    for e in json.loads(path.read_text(encoding="utf-8"))["elements"]:
        g = None
        if e["type"] == "way" and len(e.get("geometry") or []) > 3:
            g = Polygon([(p["lon"], p["lat"]) for p in e["geometry"]])
        elif e["type"] == "relation":
            outers = [[(p["lon"], p["lat"]) for p in m.get("geometry", [])]
                      for m in e.get("members", []) if m.get("role") == "outer" and m.get("geometry")]
            polys = list(polygonize(linemerge([LineString(o) for o in outers if len(o) > 1])))
            g = unary_union(polys) if polys else None
        if g is not None:
            out.append((e.get("tags") or {}, g if g.is_valid else g.buffer(0)))
    return out


def feature(geometry: dict, props: dict, display_simplify: float = DISPLAY_SIMPLIFY) -> dict:
    """Ein Gebiet in der Form, die ``plan_pages`` liest: Fläche, Ortsbereiche, Beschriftungspunkt, Anzeige."""
    from shapely.geometry import mapping, shape
    poly = shape(geometry)
    point = poly.representative_point()
    display = json.loads(json.dumps(mapping(poly.simplify(display_simplify, preserve_topology=True))),
                         parse_float=lambda f: round(float(f), 5))
    return {"type": "Feature", "geometry": geometry, "properties": {
        **props, "area_ha": round(U.area_ha(geometry), 2), "districts": U.districts(poly),
        "label_point": [round(point.x, 5), round(point.y, 5)], "display_geometry": display}}


def round_geometry(g, digits: int = 6) -> dict:
    from shapely.geometry import mapping
    return json.loads(json.dumps(mapping(g)), parse_float=lambda f: round(float(f), digits))


# ── Lärmaktionsplan: Ruhige Gebiete ────────────────────────────────────────

LAP_DOC = {"document_id": 280381, "template": "24/0293/1", "label": "Fortschreibung des Lärmaktionsplans (2. Entwurf, Mai 2024)"}
#: Tabelle 27 (S. 153): Gebiete aus der Verschneidung — Nummer: (Name, Hektar). 3 und 9 nimmt der Plan aus
#: (möglicher Suchraum für Windenergie).
LAP_TABLE_27 = {
    1: ("Swarte Moor", 2.6), 2: ("Alexanderheide", 17.7), 4: ("Großer Bürgerbusch", 8.7), 5: ("Geestrand", 5.4),
    6: ("Flötenteich", 18.9), 7: ("Donnerschweer Wiesen", 73.1), 8: ("Huntewiesen", 149.4),
    10: ("Bloherfelder Teich N", 3.4), 11: ("Kennedyteich", 3.9), 12: ("Bloherfelder Teich S", 2.1),
    13: ("Bloherfelder Wasserzug-Teich", 2.5), 14: ("südl. Kaspersweg", 5.2),
    15: ("Hausbäkenniederung-Everstenmoor", 353.5), 16: ("Buschhagenniederung", 5.5), 17: ("Utkiek", 10.1),
    18: ("Bümmersteder Fleet", 60.9),
}
#: Tabelle 28 und 29 (S. 155): Friedhöfe und Erholungsflächen — Nummer: (Name, Hektar, Art, Name in OSM).
LAP_TABLE_28_29 = {
    101: ("Waldfriedhof Ofenerdiek", 10.0, "Friedhof", "Waldfriedhof"),
    105: ("Friedhof Ohmstede", 1.9, "Friedhof", "Friedhof Ohmstede"),
    106: ("Friedhof Donnerschwee", 2.4, "Friedhof", "Friedhof Donnerschwee"),
    107: ("Neuer Friedhof", 9.7, "Friedhof", "Neuer Friedhof"),
    109: ("Katholischer Friedhof", 2.9, "Friedhof", "Katholischer Friedhof"),
    111: ("Gertrudenfriedhof", 3.6, "Friedhof", "Gertrudenfriedhof"),
    112: ("Friedhof Eversten", 3.6, "Friedhof", "Friedhof Eversten"),
    115: ("Alter Friedhof Osternburg", 1.1, "Friedhof", "Alter Osternburger Friedhof"),
    116: ("Neuer Osternburger Friedhof", 0.8, "Friedhof", "Neuer Osternburger Friedhof"),
    117: ("Parkfriedhof Bümmerstede", 10.9, "Friedhof", "Parkfriedhof Bümmerstede"),
    118: ("Jüdischer Friedhof", 0.2, "Friedhof", "Alter jüdischer Friedhof"),
    102: ("Swarte Moor", 18.3, "Erholungsfläche", None),
    103: ("Kleiner Bürgerbusch", 8.6, "Erholungsfläche", "Kleiner Bürgerbusch"),
    104: ("Großer Bürgerbusch", 18.2, "Erholungsfläche", None),
    108: ("Haarenniederung", 52.8, "Erholungsfläche", None),
    110: ("Botanischer Garten", 3.7, "Erholungsfläche", "Botanischer Garten Oldenburg"),
    113: ("Eversten Holz", 22.7, "Erholungsfläche", "Eversten Holz"),
    114: ("Schlossgarten", 18.4, "Erholungsfläche", "Schlossgarten"),
}
#: Wo die Nummer eines Gebiets auf der Karte steht (Pixel im Bild, von Hand abgelesen). Abb. 53: 10, 11 und
#: 13 verdeckt ihre eigene Nummer — sie werden nicht gezeichnet. Abb. 54: nur, was OSM nicht kennt.
LAP_LABELS_53 = {1: (568, 160), 2: (365, 255), 4: (520, 333), 5: (726, 335), 6: (695, 380), 7: (798, 563),
                 8: (1087, 477), 12: (325, 680), 14: (274, 745), 15: (230, 866), 16: (516, 913), 17: (664, 908),
                 18: (502, 1125)}
LAP_LABELS_54 = {102: (780, 268), 104: (716, 505), 108: (276, 806)}
#: Abweichung von der Fläche laut Plan, bis zu der ein Umriss gilt — darüber steht das Gebiet nur in der Tabelle.
LAP_TOLERANCE_TRACED = 0.30
LAP_TOLERANCE_OSM = 0.20


def _assign(regions, labels: dict, max_px: float = 80) -> dict:
    """Jede Fläche gehört zur Beschriftung, die ihr am nächsten steht (bis ``max_px``); zerfällt ein Gebiet
    auf der Karte in Stücke (eine Straße, eine Nummer darüber), kommen die Stücke wieder zusammen."""
    from shapely.geometry import Point
    from shapely.ops import unary_union
    pieces: dict = {}
    for region in regions:
        d, code = min((region.distance(Point(x, y)), code) for code, (x, y) in labels.items())
        if d <= max_px:
            pieces.setdefault(code, []).append(region)
    return {code: unary_union(parts) for code, parts in pieces.items()}


def laermaktionsplan() -> tuple[dict, list[str]]:
    import pymupdf
    from plan_massnahmen import holen
    doc = pymupdf.open(holen(LAP_DOC["document_id"]))
    notes, features = [], []
    url = f"https://buergerinfo.oldenburg.de/getfile.php?id={LAP_DOC['document_id']}&type=do"

    def red_line(a, frame):
        r, g, b = a[..., 0], a[..., 1], a[..., 2]
        return (r > 170) & (r - g > 60) & (r - b > 60) & frame

    # Abb. 53, S. 152: dunkelgrüne Schraffur
    import numpy as np
    a = U._image(doc, 152)
    frame = np.zeros(a.shape[:2], bool)
    frame[18:1295, 15:1228] = True
    line = red_line(a, frame)
    line[:95, :205] = False  # Wappen
    t53 = fit_boundary(line)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    green = (g > r + 25) & (g > b + 15) & (g < 165) & frame
    found = _assign(density_regions(green, 13, 0.18, frame), LAP_LABELS_53)
    for code, (name, stated) in LAP_TABLE_27.items():
        if code not in found:
            notes.append(f"{code} {name}: auf der Karte nicht sicher herauszulösen (zu klein, Nummer darüber) — nur in der Tabelle")
            continue
        geometry = to_lonlat(found[code], t53)
        ha = U.area_ha(geometry)
        if abs(ha / stated - 1) > LAP_TOLERANCE_TRACED:
            notes.append(f"{code} {name}: {ha:.1f} ha nachgezeichnet statt {stated} ha — nur in der Tabelle")
            continue
        features.append(feature(geometry, {"code": str(code), "name": name, "group": "Ruhiges Gebiet", "page": 152,
                                           "figure": 53, "area_ha_plan": stated, "source": "Karte",
                                           "source_url": f"{url}#page=152"}))
    # Friedhöfe und Erholungsflächen: OSM, wo der Name steht; sonst Abb. 54, S. 154 (hellgrüne Schraffur)
    import plan_angaben as A
    shares = A.laerm_shares()
    osm = {tags.get("name"): g_ for tags, g_ in osm_polygons(OSM_DIR / "ruhige-gebiete.json") if tags.get("name")}
    a54 = U._image(doc, 154)
    frame54 = np.zeros(a54.shape[:2], bool)
    frame54[22:1739, 18:1642] = True
    line54 = red_line(a54, frame54)
    line54[:120, :280] = False
    t54 = fit_boundary(line54)
    r, g, b = a54[..., 0], a54[..., 1], a54[..., 2]
    light = (g > r + 30) & (g > b + 60) & (g < 205) & frame54
    found54 = _assign(density_regions(light, 15, 0.16, frame54), LAP_LABELS_54)
    for code, (name, stated, kind, osm_name) in LAP_TABLE_28_29.items():
        # Der Umriss aus OSM stützt sich auf die Tabelle (S. 155), der nachgezeichnete auf Abb. 54 (S. 154).
        props = {"code": str(code), "name": name, "group": kind, "area_ha_plan": stated,
                 "facts": [A.fact("Anteil der Fläche unter 60 dB(A)", shares[str(code)], 155)],
                 **({"page": 155, "figure": None, "source_url": f"{url}#page=155"} if osm_name
                    else {"page": 154, "figure": 54, "source_url": f"{url}#page=154"})}
        if osm_name:
            if osm_name not in osm:
                notes.append(f"{code} {name}: in OSM nicht gefunden — nur in der Tabelle")
                continue
            geometry = round_geometry(osm[osm_name])
            ha, source = U.area_ha(geometry), "OpenStreetMap"
            tolerance = LAP_TOLERANCE_OSM
        elif code in found54:
            geometry = to_lonlat(found54[code], t54)
            ha, source, tolerance = U.area_ha(geometry), "Karte", LAP_TOLERANCE_TRACED
        else:
            notes.append(f"{code} {name}: auf der Karte nicht gefunden — nur in der Tabelle")
            continue
        if abs(ha / stated - 1) > tolerance:
            notes.append(f"{code} {name}: {ha:.1f} ha ({source}) statt {stated} ha — nur in der Tabelle")
            continue
        features.append(feature(geometry, {**props, "source": source}))
    data = {"type": "FeatureCollection", "name": "Ruhige Gebiete (Lärmaktionsplan)", "plan": "laermaktionsplan",
            "document": LAP_DOC, "generated": dt.date.today().isoformat(),
            "groups": A.groups("laermaktionsplan", LAP_DOC["document_id"]),
            "method": "Abb. 53 und 54 über die rote Stadtgrenze verortet, Schraffur nach Dichte herausgelöst; "
                      "Friedhöfe und benannte Erholungsflächen aus OpenStreetMap. Jede Fläche gegen Tabelle 27–29 "
                      "gehalten; scripts/plan_karten.py",
            "attribution": "Stadt Oldenburg, Lärmaktionsplan (24/0293/1), Abb. 53–54, Tabellen 27–29; "
                           "Umrisse teils © OpenStreetMap-Mitwirkende, ODbL",
            "fit": {"abb53_px": round(t53["fit_px"], 2), "abb54_px": round(t54["fit_px"], 2),
                    "abb53_m_px": round(float(t53["s"]) * U.COS, 2), "abb54_m_px": round(float(t54["s"]) * U.COS, 2)},
            "omitted": notes, "features": features}
    return data, notes


# ── Masterplan Stadtgrün: Maßnahmenbereiche ────────────────────────────────

#: Die Übersichtskarte steht in der Baumerhalt- und Entwicklungsstrategie (Anlage 293180, S. 16, Abb. 8) —
#: dieselbe Karte wie im Masterplan, dort nur je Bereich einzeln.
MSG_DOC = {"document_id": 293180, "template": None, "label": "Baumerhalt- und Entwicklungsstrategie, Abb. 8: "
           "Übersichtskarte zu den Maßnahmen des Masterplans Stadtgrün"}
#: Nummer: (Name laut Legende, Pixel der Nummer, Ortsbereiche, in denen das Gebiet überwiegend liegen muss).
MSG_AREAS = {
    "1": ("Innenstadt", (580, 640), ("innenstadt",)),
    "2": ("Hafen/Bahnhofsumfeld", (645, 592), ("bahnhofsviertel", "osternburg", "donnerschwee")),
    "3": ("Ziegelhofviertel/Haareneschviertel", (527, 522), ("ziegelhof", "haarenesch")),
    # Unsere Ortsbereiche schneiden anders als die Namen des Masterplans: „Donnerschwee“ liegt bei uns
    # überwiegend in Bürgeresch, „Nadorst“ zur Hälfte im Ehnernviertel.
    "4": ("Donnerschwee", (683, 478), ("donnerschwee", "buergeresch")),
    "5": ("Nadorst", (604, 430), ("nadorst", "ehnernviertel", "buergeresch")),
    "6": ("Gerichtsviertel/Osternburg West", (607, 682), ("gerichtsviertel", "osternburg", "dobbenviertel")),
    "7": ("Osternburg", (686, 742), ("osternburg",)),
    "8": ("Kreyenbrück", (568, 918), ("kreyenbrueck",)),
    "9": ("Bloherfelder Straße", (405, 632), ("bloherfelde", "eversten", "haarentor")),
    "10": ("Eversten", (430, 697), ("eversten",)),
    "11": ("Alexandersfeld", (452, 193), ("alexandersfeld", "ofenerdiek")),
    "12": ("Bürgerfelde/Dietrichsfeld", (457, 405), ("buergerfelde", "dietrichsfeld")),
}
#: Die Gewerbegebiete („G“) stehen nur in der Übersicht, ohne Einzelkarte — dort ist die Umrandung nicht sauber
#: von der Bebauung zu trennen. Sie fehlen.


def _regions(walls):
    """Die Flächen, die die Linien ``walls`` einschließen — je Fläche eine Pixelmaske (ohne Außenraum)."""
    import numpy as np
    from PIL import Image, ImageDraw
    h, w = walls.shape
    img = Image.fromarray(np.where(walls, 255, 0).astype(np.uint8)).copy()
    for x in range(w):
        for y in (0, h - 1):
            if img.getpixel((x, y)) == 0:
                ImageDraw.floodfill(img, (x, y), 254)
    for y in range(h):
        for x in (0, w - 1):
            if img.getpixel((x, y)) == 0:
                ImageDraw.floodfill(img, (x, y), 254)
    out, value = [], 1
    arr = np.asarray(img)
    for y, x in zip(*np.nonzero(arr == 0)):
        if img.getpixel((int(x), int(y))) != 0:
            continue
        ImageDraw.floodfill(img, (int(x), int(y)), value)
        out.append(value)
        value += 1
        if value >= 250:
            break
    arr = np.asarray(img)
    return [arr == v for v in out]


def _mask_polygon(mask, grow: float):
    import numpy as np
    from shapely.geometry import box
    from shapely.ops import unary_union
    rects = []
    for y in range(mask.shape[0]):
        d = np.diff(np.concatenate([[0], mask[y].astype(int), [0]]))
        rects += [box(float(a), y, float(b), y + 1) for a, b in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0])]
    return unary_union(rects).buffer(grow, join_style="mitre").simplify(0.8)


#: Die Einzelkarten im Masterplan (Anlage 251236): Seite je Bereich. Der Maßstabsbalken (eigenes Bild, 308 px)
#: misst 139 px für 500 m; Karte und Balken stehen auf der Seite in Punkten, daraus der Maßstab je Karte.
MSG_PLAN_DOC = {"document_id": 251236, "template": None, "label": "Masterplan Stadtgrün"}
MSG_DETAIL_PAGES = {"1": 77, "2": 79, "3": 81, "4": 83, "5": 85, "6": 88, "7": 90, "8": 91, "9": 93, "10": 94,
                    "11": 95, "12": 96}
MSG_BAR_PX, MSG_BAR_M = 139, 500


def _orange_outline(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return (r > 185) & (g < 110) & (b < 60) & (r - g > 95)


def _filled(outline_mask, grow: int, half: float):
    """Was eine geschlossene Linie einschließt — wie ``plan_umrisse.outline``, aber ohne Legendenfeld."""
    walls = outline_mask.copy()
    for _ in range(grow):
        w2 = walls.copy()
        w2[1:] |= walls[:-1]; w2[:-1] |= walls[1:]; w2[:, 1:] |= walls[:, :-1]; w2[:, :-1] |= walls[:, 1:]
        walls = w2
    regions = [m for m in _regions(walls) if m.sum() > 400]
    if not regions:
        from shapely.geometry import Polygon
        return Polygon()
    biggest = max(regions, key=lambda m: m.sum())
    return _without_specks(_mask_polygon(biggest, grow + half))


def _without_specks(poly):
    """Löcher, die nur ein Symbol oder eine Beschriftung im Inneren gerissen hat (unter 2 % der Fläche), zu."""
    from shapely.geometry import MultiPolygon, Polygon
    parts = [Polygon(p.exterior, [h for h in p.interiors if Polygon(h).area >= 0.02 * p.area]) for p in U._parts(poly)]
    return parts[0] if len(parts) == 1 else MultiPolygon(parts)


#: Anteil des Randes, der in der Übersicht auf (bis 4 px neben) einer orangen Umrandung liegen muss.
MSG_MIN_COVER = 0.55


def _outline_cover(geometry: dict, t: dict, dist) -> float:
    """Wie viel vom Rand einer Fläche liegt in der Übersicht auf einer Umrandung? (Punkte alle ~1 px)"""
    import numpy as np
    pts = []
    rings = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    for poly in rings:
        ring = [((U._merc(x, y)[0] - t["tx"]) / t["s"], (t["ty"] - U._merc(x, y)[1]) / t["s"]) for x, y, *_ in poly[0]]
        for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
            n = max(1, int(math.hypot(x2 - x1, y2 - y1)))
            pts += [(x1 + (x2 - x1) * i / n, y1 + (y2 - y1) * i / n) for i in range(n)]
    p = np.array(pts)
    h, w = dist.shape
    ok = (p[:, 0] >= 0) & (p[:, 0] < w) & (p[:, 1] >= 0) & (p[:, 1] < h)
    return float(np.mean(dist[p[ok, 1].astype(int), p[ok, 0].astype(int)] <= 4)) if ok.any() else 0.0


def masterplan_stadtgruen() -> tuple[dict, list[str]]:
    """Je Maßnahmenbereich die Einzelkarte des Masterplans: Maßstab aus dem Balken, Lage über die Übersicht
    (Baumstrategie Abb. 8, über die gestrichelte Stadtgrenze verortet), Fläche aus der orangen Umrandung."""
    import numpy as np
    import pymupdf
    from plan_massnahmen import holen
    from shapely.geometry import mapping
    overview = pymupdf.open(holen(MSG_DOC["document_id"]))
    a = U._image(overview, 16)
    h, w, _ = a.shape
    frame = np.zeros((h, w), bool)
    frame[10:1190, 60:1225] = True
    frame[960:, :385] = False
    frame[:90, :60] = False
    t = fit_boundary((a.max(axis=2) < 80) & frame)
    O = _orange_outline(a).astype(float)
    O[960:, :385] = 0
    outline_dist = U._distance(O > 0, 30.0)
    doc = pymupdf.open(holen(MSG_PLAN_DOC["document_id"]))
    import plan_angaben as A
    details = A.masterplan()
    notes, features = [], []
    for code, page in MSG_DETAIL_PAGES.items():
        name, _label, expect = MSG_AREAS[code]
        pg = doc[page - 1]
        imgs = sorted(pg.get_images(full=True), key=lambda i: -i[2] * i[3])
        map_img, bar_img = imgs[0], imgs[1]
        map_rect, bar_rect = pg.get_image_rects(map_img[0])[0], pg.get_image_rects(bar_img[0])[0]
        m_per_pt = MSG_BAR_M / (MSG_BAR_PX * bar_rect.width / bar_img[2])
        m_px = m_per_pt * map_rect.width / map_img[2]
        d = U._image(doc, page)
        D = _orange_outline(d)
        k = (m_px / U.COS) / t["s"]
        # Nur um die Nummer des Bereichs suchen: Die Übersicht hat viele ähnliche Umrandungen.
        lx, ly = MSG_AREAS[code][1]
        win = int(max(d.shape) * k) + 160
        x0w, y0w = max(0, lx - win), max(0, ly - win)
        _score, ox, oy = U._correlate(O[y0w:ly + win, x0w:lx + win], D.astype(float), k)
        ox, oy = ox + x0w, oy + y0w
        # Alexandersfeld (11) grenzt an die Stadtgrenze und hat dort keine orange Linie — ein Lückenschluss
        # fasste nur das Band selbst (versucht 10.11.2026). Es fehlt.
        poly_px = _filled(D, grow=2, half=3.0)
        if poly_px.is_empty:
            notes.append(f"{code} {name}: Umrandung auf S. {page} nicht geschlossen — nicht gezeichnet")
            continue
        s_d = t["s"] * k
        x0, y0 = t["tx"] + ox * t["s"], t["ty"] - oy * t["s"]
        geometry = U._map_coords(dict(mapping(poly_px)), lambda u, v, x0=x0, y0=y0, s=s_d: tuple(
            round(c, 6) for c in U._lonlat(x0 + u * s, y0 - v * s)))
        f = feature(geometry, {"code": code, "name": name, "group": "Maßnahmenbereich", "page": page, "figure": None,
                               **details[code],
                               "area_ha_plan": None, "source": "Karte", "metres_per_pixel": round(m_px, 2),
                               "source_url": f"https://buergerinfo.oldenburg.de/getfile.php?id="
                                             f"{MSG_PLAN_DOC['document_id']}&type=do#page={page}"})
        share = sum(v for kk, v in f["properties"]["districts"].items() if kk in expect)
        cover = _outline_cover(geometry, t, outline_dist)
        if expect and share < 0.5:
            notes.append(f"{code} {name}: liegt nur zu {share:.0%} in {', '.join(expect)} ({f['properties']['districts']}, Rand {cover:.0%}) — nicht gezeichnet")
            continue
        if cover < MSG_MIN_COVER:
            notes.append(f"{code} {name}: Rand liegt nur zu {cover:.0%} auf der Umrandung der Übersicht — nicht gezeichnet")
            continue
        f["properties"]["outline_cover"] = round(cover, 2)
        features.append(f)
    data = {"type": "FeatureCollection", "name": "Maßnahmenbereiche (Masterplan Stadtgrün)",
            "plan": "masterplan_stadtgruen", "document": MSG_PLAN_DOC, "generated": dt.date.today().isoformat(),
            "groups": A.groups("masterplan_stadtgruen", MSG_PLAN_DOC["document_id"]),
            "method": "Je Bereich die Einzelkarte des Masterplans: Maßstab aus ihrem Balken, Lage über die "
                      "Übersichtskarte (Baumerhalt- und Entwicklungsstrategie, Abb. 8, über die gestrichelte "
                      "Stadtgrenze verortet), Fläche aus der orangen Umrandung; gegen die Ortsbereiche des Namens "
                      "gehalten; scripts/plan_karten.py",
            "attribution": "Stadt Oldenburg, Masterplan Stadtgrün (Einzelkarten der Maßnahmenbereiche); "
                           "Kartengrundlage LGLN",
            "fit": {"px": round(float(t["fit_px"]), 2), "m_px": round(float(t["s"]) * U.COS, 2)},
            "omitted": notes, "features": features}
    return data, notes


# ── Spielleitplanung: Suchräume ────────────────────────────────────────────

SPL_DOC = {"document_id": 306888, "template": None, "label": "Spielleitplanung 2026"}
#: Kleinere Stücke der Schraffur sind Reste neben einem Kreis oder unter einer Beschriftung.
SPL_MIN_HA = 3.0
SPL_SIMPLIFY = 0.00006  # Grad, rund 4–6 m


#: Strichfarbe der Einzugskreise je Spielplatztyp (Karten 7–9, Legende S. 38).
SPL_COLORS = {"Nachbarschaftsspielplatz": (20, 64, 176), "Quartiersspielplatz": (244, 180, 0),
              "Stadtviertelspielplatz": (176, 16, 136), "Stadtteilspielplatz": (48, 144, 128),
              "Ballspielfläche": (96, 176, 64)}
#: Ein Kreis zählt, wenn auf so viel seines Umfangs (90 Winkelstücke) Strich in seiner Farbe liegt. Gemessen
#: auf Karte 7: Bei 0,45 und 0,55 dieselben Zahlen (92/36/5/6/5, laut Text 92/37/5/6/5).
SPL_MIN_COVER = 0.45


def _spl_map(doc, page: int):
    """Karte 7, 8 oder 9: außerhalb der Stadt durchsichtig (schwarz) — ihre Kante ist die Stadtgrenze."""
    a = U._image(doc, page)
    city = a.max(axis=2) > 25
    inner = city.copy()
    inner[1:] &= city[:-1]; inner[:-1] &= city[1:]; inner[:, 1:] &= city[:, :-1]; inner[:, :-1] &= city[:, 1:]
    return a, city, fit_boundary(city & ~inner)


def _ring_cover(sx, sy, x: float, y: float, r: float, width: float = 2.0) -> float:
    """Anteil der 90 Winkelstücke eines Kreises um (x, y), auf denen ein Strichpixel nahe dem Radius liegt."""
    import numpy as np
    sel = (np.abs(sx - x) <= r + 3) & (np.abs(sy - y) <= r + 3)
    dx, dy = sx[sel] - x, sy[sel] - y
    on = np.abs(np.hypot(dx, dy) - r) <= width
    return len(np.unique(((np.arctan2(dy[on], dx[on]) + math.pi) / (2 * math.pi) * 90).astype(int) % 90)) / 90


def _circles(a, t: dict) -> dict[str, list[tuple[int, int, float]]]:
    """Die Einzugskreise der Spielplätze je Typ: Kandidaten aus einer Ring-Faltung (fester Radius je Typ),
    bestätigt über die Abdeckung des Umfangs — die Kreise sind an Barrieren abgeschnitten und überlappen."""
    import numpy as np
    from plan_angaben import SPL_TYPES
    H, W = a.shape[:2]
    mpx = t["s"] * U.COS
    out = {}
    for name, col in SPL_COLORS.items():
        stroke = np.sqrt(((a.astype(int) - np.array(col)) ** 2).sum(axis=2)) < 75
        r = SPL_TYPES[name][0] / mpx
        size = int(r + 4)
        yy, xx = np.mgrid[-size:size + 1, -size:size + 1]
        ring = (np.abs(np.hypot(xx, yy) - r) <= 2.0).astype(float)
        shape_ = (H + 2 * size, W + 2 * size)
        acc = np.fft.irfft2(np.fft.rfft2(stroke.astype(float), s=shape_) * np.fft.rfft2(ring, s=shape_),
                            s=shape_)[size:size + H, size:size + W] / ring.sum()
        sy, sx = np.nonzero(stroke)
        found: list[tuple[int, int, float]] = []
        for _ in range(400):
            y, x = np.unravel_index(np.argmax(acc), acc.shape)
            if acc[y, x] < 0.08:
                break
            acc[max(0, y - 3):y + 4, max(0, x - 3):x + 4] = 0
            cover = _ring_cover(sx, sy, float(x), float(y), r)
            if cover >= SPL_MIN_COVER and all(math.hypot(x - fx, y - fy) > r * 0.5 for fx, fy, _ in found):
                found.append((int(x), int(y), round(cover, 2)))
                acc[max(0, y - int(r * 0.5)):y + int(r * 0.5) + 1, max(0, x - int(r * 0.5)):x + int(r * 0.5) + 1] = 0
        out[name] = found
    return out


def _planned(a8, t8: dict, existing: dict, conn) -> list[dict]:
    """Die gestrichelten Kreise der geplanten Spielplätze auf Karte 8: Suche um den Anker aus
    ``plan_angaben.SPL_PLANNED``, nur dort, wo Karte 7 noch keinen Kreis desselben Typs hat."""
    import numpy as np
    from plan_angaben import SPL_PLANNED, SPL_TYPES
    mpx = t8["s"] * U.COS
    out = []
    for code, name, typ, _word, anchor, (ox, oy), win in SPL_PLANNED:
        row = conn.execute("SELECT lat, lon FROM council_locations WHERE name = ? AND lat IS NOT NULL", (anchor,)).fetchone()
        if not row:
            raise SystemExit(f"Spielleitplanung {code}: Anker „{anchor}“ fehlt im Ortskatalog")
        X, Y = U._merc(row[1], row[0])
        cx, cy = (X - t8["tx"]) / t8["s"] + ox, (t8["ty"] - Y) / t8["s"] + oy
        r = SPL_TYPES[typ][0] / mpx
        stroke = np.sqrt(((a8.astype(int) - np.array(SPL_COLORS[typ])) ** 2).sum(axis=2)) < 75
        sy, sx = np.nonzero(stroke)
        best = (0.0, cx, cy)
        for y in range(int(cy) - win, int(cy) + win + 1):
            for x in range(int(cx) - win, int(cx) + win + 1):
                if any(math.hypot(x - ex, y - ey) < 10 for ex, ey in existing.get(typ, [])):
                    continue
                cover = _ring_cover(sx, sy, x, y, r, 1.5)
                if cover > best[0]:
                    best = (cover, x, y)
        cover, x, y = best
        if cover < 0.3:
            raise SystemExit(f"Spielleitplanung {code}: kein gestrichelter Kreis am Anker (Abdeckung {cover:.2f})")
        lon, lat = U._lonlat(t8["tx"] + x * t8["s"], t8["ty"] - y * t8["s"])
        out.append({"code": code, "name": name, "type": typ, "lon": lon, "lat": lat, "cover": round(cover, 2)})
    return out


def spielleitplanung() -> tuple[dict, list[str]]:
    """Karte 9 (S. 48): rot schraffiert die Suchräume — bebaute Gebiete ohne Spielplatz in erreichbarer Nähe,
    je Ortsbereich geschnitten. Dazu je Stadtteil die Spielplätze nach Typ (Kreise auf Karte 7) und die
    Sätze des Plans zum Stadtteil; die geplanten Spielplätze (Karte 8) als eigene Einträge."""
    import sqlite3
    import pymupdf
    import plan_angaben as A
    from plan_massnahmen import holen
    from shapely.geometry import shape
    from shapely.ops import unary_union
    doc = pymupdf.open(holen(SPL_DOC["document_id"]))
    a, city, t = _spl_map(doc, 48)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    # Nur reines Rot: Die Schraffur liegt auch unter den halbdurchsichtigen Kreisen der Einzugsbereiche — dort
    # mischt sie sich mit deren Farbe, und dort ist ein Spielplatz erreichbar, also kein Suchraum.
    hatch = (r > 170) & (g < 60) & (b < 60)
    regions = density_regions(hatch, 11, 0.10, city, min_px=40)
    # Stücke, die nur ein Kreis oder eine Beschriftung trennt, wieder zusammenfügen — dann je Ortsbereich ein
    # Suchraum: Die Schraffur zieht sich über halbe Stadtteile, als ein Stück sagte sie nichts.
    merged = unary_union([q.buffer(3) for q in regions]).buffer(-3)
    whole = shape(to_lonlat(merged, t)).buffer(0)
    # Spielplätze je Stadtteil (Karte 7) — gegen die Zählung im Text gehalten
    a7, _city7, t7 = _spl_map(doc, 38)
    circles = _circles(a7, t7)
    for typ, (_radius, stated) in A.SPL_TYPES.items():
        if abs(len(circles[typ]) - stated) > 1:
            raise SystemExit(f"Spielleitplanung: {len(circles[typ])} {typ} auf Karte 7, laut Text {stated}")
    counts: dict[str, dict[str, int]] = {}
    for typ, found in circles.items():
        for x, y, _c in found:
            lon, lat = U._lonlat(t7["tx"] + x * t7["s"], t7["ty"] - y * t7["s"])
            district = geo.ortsbereich_for(lat, lon)
            place = places.resolve(district) if district else None
            if place:
                counts.setdefault(place.id, {}).setdefault(typ, 0)
                counts[place.id][typ] += 1
    quotes = A.spielleitplanung_quotes({pl.id: pl.name for pl in places.primary_places()})
    notes: list[str] = []
    features = []
    url = f"https://buergerinfo.oldenburg.de/getfile.php?id={SPL_DOC['document_id']}&type=do"
    for pl in places.primary_places():
        area_poly = geo.ortsbereich_polygon(pl.name)
        if not area_poly:
            continue
        # Auf Kartenauflösung (9 m je Pixel) vereinfachen: Die Schraffur kommt als Pixeltreppe, und die
        # Grenze des Ortsbereichs ist feiner gezeichnet, als die Karte es hergibt.
        part = whole.intersection(shape(area_poly)).simplify(SPL_SIMPLIFY, preserve_topology=True)
        if part.is_empty:
            continue
        geometry = round_geometry(part, 5)
        if geometry["type"] not in ("Polygon", "MultiPolygon"):
            continue
        if U.area_ha(geometry) < SPL_MIN_HA:
            continue
        by_page: dict[int, list[str]] = {}
        for q in quotes.get(pl.id, []):
            by_page.setdefault(q["page"], []).append(q["text"])
        f = feature(geometry, {
            "code": pl.id, "name": pl.name, "group": "Suchraum für Spielplätze", "label": "Suchraum für Spielplätze",
            "page": 48, "figure": 9, "area_ha_plan": None, "source": "Karte", "source_url": f"{url}#page=48",
            "facts": [A.fact("Spielplätze im Stadtteil (Karte 7)", A.playground_counts(counts.get(pl.id, {})), 38)],
            "notes": [A.note("Aus der Auswertung" if page == 37 else "Zu den Suchräumen", texts, page, "text")
                      for page, texts in sorted(by_page.items())]},
            display_simplify=SPL_SIMPLIFY * 2)
        f["properties"]["districts"] = {pl.id: 1.0}
        features.append(f)
    features.sort(key=lambda f: -f["properties"]["area_ha"])
    # Geplante Spielplätze (Karte 8)
    a8, _city8, t8 = _spl_map(doc, 46)
    existing = {typ: [((U._merc(*U._lonlat(t7["tx"] + x * t7["s"], t7["ty"] - y * t7["s"]))[0] - t8["tx"]) / t8["s"],
                       (t8["ty"] - U._merc(*U._lonlat(t7["tx"] + x * t7["s"], t7["ty"] - y * t7["s"]))[1]) / t8["s"])
                      for x, y, _c in found] for typ, found in circles.items()}
    conn = sqlite3.connect(f"file:{WURZEL / 'data' / 'council.sqlite'}?mode=ro", uri=True)
    planned = _planned(a8, t8, existing, conn)
    conn.close()
    words = {code: word for code, _n, _t, word, *_ in A.SPL_PLANNED}
    for p in planned:
        district = geo.ortsbereich_for(p["lat"], p["lon"])
        place = places.resolve(district) if district else None
        radius = A.SPL_TYPES[p["type"]][0]
        quote = A.spielleitplanung_planned_quote(words[p["code"]])
        lon, lat = round(p["lon"], 6), round(p["lat"], 6)
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": {
            "code": f"geplant-{p['code'].lower()}", "name": p["name"], "group": "Spielplatz in Planung",
            "page": 46, "figure": 8, "area_ha": None, "area_ha_plan": None, "source": "Karte",
            "source_url": f"{url}#page=46", "districts": {place.id: 1.0} if place else {},
            "label_point": [round(lon, 5), round(lat, 5)], "display_geometry": None,
            "summary": f"{p['type']} · Einzugsradius {radius:,} m".replace(",", "."), "radius_m": radius,
            "facts": [A.fact("Typ", f"{p['type']} (Einzugsradius {radius:,} m)".replace(",", "."), 46),
                      A.fact("Kennung auf Karte 8", p["code"], 46)],
            "notes": [A.note("Aus dem Plan", [quote["text"]], quote["page"], "text")] if quote else [],
            "circle_cover": p["cover"]}})
    data = {"type": "FeatureCollection", "name": "Suchräume für Spielplätze (Spielleitplanung)",
            "plan": "spielleitplanung", "document": SPL_DOC, "generated": dt.date.today().isoformat(),
            "figure_word": "Karte", "groups": A.groups("spielleitplanung", SPL_DOC["document_id"]),
            "method": "Karte 9 über ihre Kante (die Stadtgrenze) verortet, die rote Schraffur nach Dichte "
                      f"herausgelöst und je Ortsbereich geschnitten, Teile unter {SPL_MIN_HA:g} ha weggelassen; "
                      "je Stadtteil die Spielplätze nach Typ aus den Einzugskreisen auf Karte 7 (gegen die Zählung "
                      "im Text gehalten); geplante Spielplätze aus den gestrichelten Kreisen auf Karte 8; "
                      "scripts/plan_karten.py, scripts/plan_angaben.py",
            "attribution": "Stadt Oldenburg, Spielleitplanung 2026, Karten 7–9",
            "fit": {"px": round(float(t["fit_px"]), 2), "m_px": round(float(t["s"]) * U.COS, 2),
                    "karte7": {typ: len(found) for typ, found in circles.items()}},
            "omitted": notes, "features": features}
    return data, notes


# ── Einzelhandelsentwicklungskonzept: Zentren und zentrale Versorgungsbereiche ─────

EEK_DOC = {"document_id": 285989, "template": None, "label": "Einzelhandelsentwicklungskonzept (EEK)"}
#: Karte 33 (S. 187): die Standortstruktur 2023 — je Standort (Pixel des Symbols, Art). Die Karte ist in drei
#: Streifen gespeichert; gerendert wird der Ausschnitt mit 220 dpi.
EEK_K33_PAGE, EEK_K33_BAR = 187, (181, 2000)
EEK_CENTRES = {
    "innenstadt": ("Innenstadt", (540, 507), "Zentraler Versorgungsbereich Innenstadt"),
    "ofenerdiek": ("Ofenerdiek", (475, 47), "Nahversorgungszentrum"),
    "alexanderstrasse-nord": ("Alexanderstraße Nord", (450, 217), "Nahversorgungszentrum"),
    "scheideweg": ("Scheideweg/Eßkamp", (553, 225), "Nahversorgungszentrum"),
    "nadorster-strasse-nord": ("Nadorster Straße Nord", (588, 337), "Nahversorgungszentrum"),
    "nadorster-strasse-sued": ("Nadorster Straße Süd", (566, 392), "Nahversorgungszentrum"),
    "donnerschweer-strasse": ("Donnerschweer Straße", (681, 408), "Nahversorgungszentrum"),
    "westkreuz": ("Westkreuz", (416, 477), "Nahversorgungszentrum"),
    "hauptstrasse-eversten": ("Hauptstraße Eversten", (437, 578), "Nahversorgungszentrum"),
    "edewechter-landstrasse": ("Edewechter Landstraße", (351, 603), "Nahversorgungszentrum"),
    "osternburger-markt": ("Osternburger Markt", (605, 608), "Nahversorgungszentrum"),
    "cloppenburger-strasse": ("Cloppenburger Straße", (519, 802), "Nahversorgungszentrum"),
    "alexanderstrasse-sued": ("Alexanderstraße Süd", (515, 314), "Nahversorgungsstandort"),
    "bloherfelde-west": ("Bloherfelde West", (227, 492), "Nahversorgungsstandort"),
    "bloherfelde-ost": ("Bloherfelde Ost", (287, 494), "Nahversorgungsstandort"),
    "hundsmuehler-strasse-nord": ("Hundsmühler Straße Nord", (406, 667), "Nahversorgungsstandort"),
    "hundsmuehler-strasse-sued": ("Hundsmühler Straße Süd", (413, 704), "Nahversorgungsstandort"),
    "kreyen-centrum": ("Kreyen-Centrum", (640, 909), "Nahversorgungsstandort"),
    "stubbenweg": ("Stubbenweg", (638, 73), "Fachmarktzentrum"),
    "wechloy": ("Wechloy", (292, 313), "Fachmarktzentrum"),
    "emsstrasse": ("Emsstraße (Maco)/Stedinger Straße", (629, 546), "Fachmarktzentrum mit Nahversorgungsfunktion"),
    "kaufpark-kreyenbrueck": ("KaufPark Kreyenbrück", (519, 887), "Fachmarktzentrum mit Nahversorgungsfunktion"),
}
#: Die Abgrenzungen, die nach dem Konzept von 2023 gelten (S. 186–208): neu gezogen (Karten 34–39) oder aus
#: Kapitel 4 beibehalten. Zentrum: (Seite, Karte, Meter des Maßstabsbalkens, Straße, die hindurchführen muss —
#: die Gegenprobe zur Verortung).
EEK_BOUNDARIES = {
    "innenstadt": (200, 34, 300, "Lange Straße"),
    "nadorster-strasse-sued": (202, 35, 150, "Nadorster Straße"),
    "nadorster-strasse-nord": (203, 36, 200, "Nadorster Straße"),
    "osternburger-markt": (204, 37, 150, "Bremer Straße"),
    "ofenerdiek": (205, 38, 100, "Weißenmoorstraße"),
    "hauptstrasse-eversten": (83, 11, 150, "Hauptstraße"),
    "scheideweg": (94, 14, 150, None),  # Einkaufszentrum, keine Straße hindurch
    "cloppenburger-strasse": (97, 15, 300, "Cloppenburger Straße"),
    "westkreuz": (105, 17, 100, "Ammerländer Heerstraße"),
    "alexanderstrasse-nord": (109, 18, 150, "Alexanderstraße"),
    "donnerschweer-strasse": (115, 20, 100, "Donnerschweer Straße"),
    "edewechter-landstrasse": (122, 22, 150, "Edewechter Landstraße"),
    "emsstrasse": (208, 39, 100, "Hermannstraße"),
}


def _render_strips(doc, page: int, dpi: int = 220):
    """Eine Karte, die im PDF in Streifen liegt, als ein Bild."""
    import numpy as np
    from PIL import Image
    pg = doc[page - 1]
    rects = [pg.get_image_rects(x[0])[0] for x in pg.get_images(full=True) if x[2] > 800]
    clip = rects[0]
    for r in rects[1:]:
        clip |= r
    pix = pg.get_pixmap(clip=clip, dpi=dpi)
    return np.asarray(Image.frombytes("RGB", (pix.width, pix.height), pix.samples)).astype(int)


def _bar_px(a, x_from: int = 960) -> float:
    """Länge des Maßstabsbalkens unten rechts: die oberste durchgehend dunkle Zeile, bis zur ersten Lücke."""
    import numpy as np
    h = a.shape[0]
    for y in range(h - 90, h - 5):
        row = a[y, x_from:].max(axis=1) < 90
        xs = np.nonzero(row)[0]
        if len(xs) < 80:
            continue
        start, end = xs[0], xs[0]
        for x in xs[1:]:
            if x - end > 6:
                break
            end = x
        if end - start > 60:
            return float(end - start + 1)
    raise SystemExit("Maßstabsbalken nicht gefunden")


#: Wie weit die Lage einer Detailkarte vom Standort auf Karte 33 abweichen darf (Meter) — so weit reichen auch
#: die OSM-Gebäude, die ``--osm`` holt.
EEK_SEARCH_M = 700
#: Die beste Lage muss so viel deutlicher sein als die zweitbeste (außerhalb von 40 px), sonst gilt die Karte
#: als nicht verortet. Gemessen: 2,9 bis 9,1.
EEK_MIN_PEAK = 2.5


def _k33(doc, conn) -> tuple[dict, list[dict], float, float]:
    """Karte 33: Maßstab aus dem Balken, Lage über die Hauptstraßen der Grundkarte gegen die Katalogstraßen.
    → (Mercator je Standort, Punkt-Features, Restabstand in px, Meter je px)."""
    import numpy as np
    url = f"https://buergerinfo.oldenburg.de/getfile.php?id={EEK_DOC['document_id']}&type=do"
    a = _render_strips(doc, EEK_K33_PAGE)
    h, w, _ = a.shape
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    frame = np.zeros((h, w), bool)
    frame[5:950, 5:990] = True
    road = (r > 215) & (g > 150) & (g < 215) & (b < 185) & (r - b > 45) & frame
    dist = U._distance(road, 20.0)
    s33 = (EEK_K33_BAR[1] / EEK_K33_BAR[0]) / U.COS
    X, Y = U._merc(8.2146, 53.1394)  # Lambertikirche als Startpunkt für das Innenstadt-Symbol
    x0, y0 = X - EEK_CENTRES["innenstadt"][1][0] * s33, Y + EEK_CENTRES["innenstadt"][1][1] * s33
    lo0, la1 = U._lonlat(x0, y0)
    lo1, la0 = U._lonlat(x0 + w * s33, y0 - h * s33)
    P = U._catalog_points(conn, lo0, la0, lo1, la1)

    def cost33(s_, xx, yy):
        u, v = (P[:, 0] - xx) / s_, (yy - P[:, 1]) / s_
        ok = (u >= 0) & (u < w - 1) & (v >= 0) & (v < h - 1)
        return 1e9 if ok.sum() < 500 else float(np.mean(dist[v[ok].astype(int), u[ok].astype(int)]))
    c33, s33, x0, y0 = U._search(cost33, (s33, x0, y0), [(0.0, 40), (0.0, 20), (0.0, 10), (0.0, 5), (0.0, 2), (0.0, 1)],
                                 scale_free=False)
    centre_merc, features = {}, []
    for key, (name, (px, py), kind) in EEK_CENTRES.items():
        # Mitte des Symbols: Schwerpunkt der farbigen Pixel im Umkreis
        win = a[max(0, py - 16):py + 17, max(0, px - 16):px + 17]
        sat = (win.max(axis=2) - win.min(axis=2)) > 90
        ys, xs = np.nonzero(sat)
        if len(xs) > 10:
            px, py = px - 16 + xs.mean(), py - 16 + ys.mean()
        mx_, my_ = x0 + px * s33, y0 - py * s33
        centre_merc[key] = (mx_, my_)
        lon, lat = U._lonlat(mx_, my_)
        district = geo.ortsbereich_for(lat, lon)
        place = places.resolve(district) if district else None
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
                         "properties": {"code": key, "name": name, "group": kind, "page": EEK_K33_PAGE, "figure": 33,
                                        "area_ha": None, "area_ha_plan": None, "source": "Karte",
                                        "source_url": f"{url}#page={EEK_K33_PAGE}",
                                        "districts": {place.id: 1.0} if place else {},
                                        "label_point": [round(lon, 5), round(lat, 5)], "display_geometry": None}})
    return centre_merc, features, c33, s33 * U.COS


def _osm_buildings():
    """Die Gebäude aus ``--osm``: (Umrisse in Mercator, Schwerpunkte)."""
    import numpy as np
    path = OSM_DIR / "eek-gebaeude.json"
    if not path.exists():
        raise SystemExit(f"{path} fehlt — erst: python scripts/plan_karten.py --osm")
    outlines = [np.array([U._merc(p["lon"], p["lat"]) for p in e["geometry"]])
                for e in json.loads(path.read_text(encoding="utf-8"))["elements"] if len(e.get("geometry") or []) > 3]
    return outlines, np.array([o.mean(axis=0) for o in outlines])


def _raster_buildings(buildings, x0: float, y0: float, s: float, w: int, h: int):
    """Die OSM-Gebäude im Ausschnitt als Maske im Pixelraster der Karte (Ursprung ``x0``/``y0``, Maßstab ``s``)."""
    import numpy as np
    from PIL import Image, ImageDraw
    outlines, centres = buildings
    im = Image.new("L", (w, h), 0)
    dr = ImageDraw.Draw(im)
    sel = ((centres[:, 0] > x0 - 100) & (centres[:, 0] < x0 + w * s + 100)
           & (centres[:, 1] < y0 + 100) & (centres[:, 1] > y0 - h * s - 100))
    for i in np.nonzero(sel)[0]:
        dr.polygon([((x - x0) / s, (y0 - y) / s) for x, y in outlines[i]], fill=255)
    return np.asarray(im) / 255.0


def _georef_by_buildings(d, s: float, seed: tuple[float, float], map_w: int, buildings) -> tuple[float, float, float]:
    """Lage einer Detailkarte bei festem Maßstab ``s``: Die grauen Gebäude der Grundkarte werden mit den
    OSM-Gebäuden rund um den Standort kreuzkorreliert. → (x0, y0, Spitze gegen zweitbeste Lage)."""
    import numpy as np
    h = d.shape[0]
    mn, mx = d.min(axis=2), d.max(axis=2)
    T = ((mn > 150) & (mx < 216) & (mx - mn < 14)).astype(float)[:, :map_w]
    T[h - 70:, map_w - 260:] = 0  # Maßstab und Nordpfeil
    margin = EEK_SEARCH_M / U.COS
    X0, Y0 = seed[0] - map_w / 2 * s - margin, seed[1] + h / 2 * s + margin
    W, H = int(map_w + 2 * margin / s), int(h + 2 * margin / s)
    C = _raster_buildings(buildings, X0, Y0, s, W, H)
    A = np.fft.rfft2(C - C.mean(), s=(H + h, W + map_w))
    B = np.fft.rfft2((T - T.mean())[::-1, ::-1], s=(H + h, W + map_w))
    c = np.fft.irfft2(A * B, s=(H + h, W + map_w))[h - 1:H, map_w - 1:W]
    iy, ix = np.unravel_index(np.argmax(c), c.shape)
    peak = c[iy, ix]
    c[max(0, iy - 40):iy + 41, max(0, ix - 40):ix + 41] = -np.inf
    return float(X0 + ix * s), float(Y0 - iy * s), float(peak / max(c.max(), 1e-9))


def _grow(mask, n: int):
    for _ in range(n):
        m = mask.copy()
        m[1:] |= mask[:-1]; m[:-1] |= mask[1:]; m[:, 1:] |= mask[:, :-1]; m[:, :-1] |= mask[:, 1:]
        mask = m
    return mask


def _shrink(mask, n: int):
    return ~_grow(~mask, n)


def _exterior(walls):
    """Was vom Bildrand aus erreichbar ist, ohne eine Wand zu kreuzen."""
    import numpy as np
    from PIL import Image, ImageDraw
    img = Image.fromarray(np.where(walls, 255, 0).astype(np.uint8)).copy()
    h, w = walls.shape
    for x, y in [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]:
        if img.getpixel((x, y)) == 0:
            ImageDraw.floodfill(img, (x, y), 128)
    return np.asarray(img) == 128


#: Abgrenzungen des EEK: Lücken in der Linie bis zu so viel Pixel schließen (gestrichelte Linien, Bahnquerung),
#: dann außen Angeklebtes abschneiden (Symbole an der Linie), dann den Rand auf die Linienmitte zurücksetzen.
EEK_CLOSE_PX, EEK_OPEN_PX, EEK_LINE_HALF_PX = 5, 8, 3


def _enclosed(walls, close: int = EEK_CLOSE_PX, open_: int = EEK_OPEN_PX, inset: int = EEK_CLOSE_PX + EEK_LINE_HALF_PX):
    """Die größte Fläche, die die Linien ``walls`` umschließen — samt allem, was innen liegt (Symbole zählen
    mit, sie trennen nichts). Anders als ``_filled``: In der Innenstadt stehen die Symbole so dicht, dass sie
    als Wände die Fläche zerteilten."""
    w = _grow(walls, close)
    inside = ~_exterior(w)
    inside = _grow(_shrink(inside, open_), open_)
    inside = _shrink(inside, inset)
    regions = [m for m in _regions(~inside) if m.sum() > 400]
    if not regions:
        from shapely.geometry import Polygon
        return Polygon()
    return _mask_polygon(max(regions, key=lambda m: m.sum()), 0.5)


def einzelhandel() -> tuple[dict, list[str]]:
    import sqlite3
    import pymupdf
    from plan_massnahmen import holen
    from shapely.geometry import LineString, mapping, shape
    doc = pymupdf.open(holen(EEK_DOC["document_id"]))
    conn = sqlite3.connect(f"file:{WURZEL / 'data' / 'council.sqlite'}?mode=ro", uri=True)
    url = f"https://buergerinfo.oldenburg.de/getfile.php?id={EEK_DOC['document_id']}&type=do"
    notes: list[str] = []
    centre_merc, features, c33, m33 = _k33(doc, conn)
    buildings = _osm_buildings()
    streets = {row[0]: json.loads(row[1]) for row in conn.execute(
        "SELECT name, geojson FROM council_locations WHERE kind = 'street' AND geojson IS NOT NULL")}
    conn.close()
    # Je Standort ein Eintrag: die Abgrenzung, wo es eine gibt, sonst der Punkt aus Karte 33.
    boundaries = {}
    for key, (page, figure, metres, street) in EEK_BOUNDARIES.items():
        name = EEK_CENTRES[key][0]
        d = _render_strips(doc, page)
        map_w = 990 if d.shape[1] > 1320 else 975
        s_d = (metres / _bar_px(d)) / U.COS
        x0d, y0d, peak = _georef_by_buildings(d, s_d, centre_merc[key], map_w, buildings)
        if peak < EEK_MIN_PEAK:
            notes.append(f"{name}: Karte {figure} nicht eindeutig verortet (Spitze {peak:.1f}) — als Punkt")
            continue
        walls = (d.max(axis=2) - d.min(axis=2)) > 90
        walls[:, map_w:] = False
        poly_px = _enclosed(walls)
        if poly_px.is_empty:
            notes.append(f"{name}: Abgrenzung auf Karte {figure} nicht geschlossen — als Punkt")
            continue
        geometry = U._map_coords(dict(mapping(poly_px)), lambda u, v, x0=x0d, y0=y0d, s=s_d: tuple(
            round(c, 6) for c in U._lonlat(x0 + u * s, y0 - v * s)))
        poly = shape(geometry)
        line = streets.get(street)
        lines = ([line["coordinates"]] if line and line["type"] == "LineString"
                 else line["coordinates"] if line else [])
        if street and not any(poly.intersects(LineString(ln)) for ln in lines if len(ln) > 1):
            notes.append(f"{name}: die {street} läuft nicht durch die nachgezeichnete Fläche — als Punkt")
            continue
        boundaries[key] = feature(geometry, {
            "page": page, "figure": figure, "area_ha_plan": None, "source": "Karte",
            "source_url": f"{url}#page={page}", "metres_per_pixel": round(s_d * U.COS, 3), "peak_ratio": round(peak, 1)})
    import plan_angaben as A
    details = A.einzelhandel({k for k, (_p, figure, _m, _s) in EEK_BOUNDARIES.items() if figure >= 34})
    out = []
    for point in features:
        key = point["properties"]["code"]
        point["properties"].update(details[key])
        if key not in boundaries:
            out.append(point)
            continue
        f = boundaries[key]
        f["properties"] = {"code": key, "name": point["properties"]["name"], "group": point["properties"]["group"],
                           **details[key], **f["properties"]}
        out.append(f)
    features = out
    data = {"type": "FeatureCollection", "name": "Zentren und Versorgungsbereiche (Einzelhandelskonzept)",
            "plan": "eek", "document": EEK_DOC, "generated": dt.date.today().isoformat(),
            "groups": A.groups("eek", EEK_DOC["document_id"]),
            "figure_word": "Karte",
            "method": "Karte 33 über ihren Maßstab und die Hauptstraßen der Grundkarte verortet (Standorte als "
                      "Punkt); je zentralem Versorgungsbereich die gültige Detailkarte (neu gezogen: Karten 34–39, "
                      "sonst Kapitel 4): Maßstab aus ihrem Balken, Lage über die Gebäude der Grundkarte gegen die "
                      "OSM-Gebäude, Fläche aus der Umrandung; scripts/plan_karten.py",
            "attribution": "Stadt Oldenburg, Einzelhandelsentwicklungskonzept; Gebäude zur Verortung "
                           "© OpenStreetMap-Mitwirkende, ODbL",
            "fit": {"k33_px": round(c33, 2), "k33_m_px": round(m33, 2)},
            "omitted": notes, "features": features}
    return data, notes


BUILDERS = {"laermaktionsplan": laermaktionsplan, "masterplan_stadtgruen": masterplan_stadtgruen,
            "spielleitplanung": spielleitplanung, "eek": einzelhandel}


# ── Prüfung (ohne PDF, ohne numpy und shapely — läuft in der Testsuite und in pruefe_plaene) ──

#: Fällt ein Lauf unter so viele Einträge, ist beim Nachzeichnen etwas gerissen.
MIN_FEATURES = {"laermaktionsplan": 20, "masterplan_stadtgruen": 10, "spielleitplanung": 20, "eek": len(EEK_CENTRES)}
#: Der vereinfachte Umriss für die Seite darf in der Fläche so weit vom vollen abweichen.
DISPLAY_TOLERANCE = 0.03


def _known_codes(key: str) -> set[str]:
    return {"laermaktionsplan": {str(c) for c in (*LAP_TABLE_27, *LAP_TABLE_28_29)},
            "masterplan_stadtgruen": set(MSG_AREAS),
            "spielleitplanung": {pl.id for pl in places.primary_places()} | {f"geplant-{c.lower()}" for c, *_ in SPL_PLANNED},
            "eek": set(EEK_CENTRES)}[key]


def check(key: str, data: dict) -> list[str]:
    """Eine Datei aus ``council/plan_shapes/`` (außer dem Wärmeplan, s. ``plan_umrisse.check``): Anzahl,
    Kennungen, Quelle, Ringe, Stadtgebiet, Fläche gegen den Plan, Ortsbereiche."""
    problems: list[str] = []
    primary = {pl.id for pl in places.primary_places()}
    feats = data.get("features", [])
    if len(feats) < MIN_FEATURES[key]:
        problems.append(f"nur {len(feats)} Einträge (mindestens {MIN_FEATURES[key]})")
    codes = [f["properties"]["code"] for f in feats]
    if len(set(codes)) != len(codes):
        problems.append("Kennungen doppelt")
    if unknown := set(codes) - _known_codes(key):
        problems.append(f"unbekannte Kennungen {sorted(unknown)}")
    for f in feats:
        props, geometry = f["properties"], f["geometry"]
        where = f"{props['code']} {props.get('name') or ''}".strip()
        if not props.get("group") or not props.get("page") or \
                not str(props.get("source_url", "")).startswith("https://buergerinfo.oldenburg.de/"):
            problems.append(f"{where}: Art, Seite oder Quelle fehlt")
        lon, lat = props["label_point"]
        if not geo.ortsbereich_for(lat, lon):
            problems.append(f"{where}: Beschriftungspunkt liegt nicht in Oldenburg")
        if not props["districts"] or not set(props["districts"]) <= primary:
            problems.append(f"{where}: Ortsbereiche fehlen oder sind unbekannt")
        if geometry.get("type") == "Point":
            if props.get("area_ha") is not None or props.get("display_geometry") is not None:
                problems.append(f"{where}: Standort mit Fläche")
            if max(abs(a - b) for a, b in zip(geometry["coordinates"], props["label_point"])) > 1e-4:
                problems.append(f"{where}: Beschriftungspunkt ist nicht der Standort")
            continue
        if geometry.get("type") not in ("Polygon", "MultiPolygon") or any(not poly for poly in U._rings(geometry)) or any(
                len(ring) < 4 or ring[0] != ring[-1] for poly in U._rings(geometry) for ring in poly):
            problems.append(f"{where}: kein geschlossenes Polygon")
            continue
        if not U.contains(geometry, lon, lat):
            problems.append(f"{where}: Beschriftungspunkt liegt nicht im Umriss")
        ha = props["area_ha"]
        if abs(U.area_ha(geometry) - ha) > max(0.05, 0.005 * ha):
            problems.append(f"{where}: Fläche passt nicht zum Polygon")
        if abs(U.area_ha(props["display_geometry"]) / ha - 1) > DISPLAY_TOLERANCE:
            problems.append(f"{where}: Der vereinfachte Umriss weicht zu weit ab")
        stated = props.get("area_ha_plan")
        tolerance = LAP_TOLERANCE_OSM if props.get("source") == "OpenStreetMap" else LAP_TOLERANCE_TRACED
        if stated and abs(ha / stated - 1) > tolerance:
            problems.append(f"{where}: {ha} ha statt {stated} ha laut Plan")
        if key == "spielleitplanung" and ha < SPL_MIN_HA:
            problems.append(f"{where}: kleiner als {SPL_MIN_HA:g} ha")
    return problems


# ── OpenStreetMap: was die Builder außer den PDFs brauchen ──────────────────

OSM_UA = "Ratslotse/1.0 (https://ratslotse.de; civic info, one-time geocoding)"
OSM_BBOX = "53.07,8.13,53.21,8.33"
#: Friedhöfe, Parks, Wälder mit Namen — für Tabelle 28/29 des Lärmaktionsplans.
OSM_QUIET_QUERY = f"""[out:json][timeout:90];
(way["landuse"="cemetery"]({OSM_BBOX}); relation["landuse"="cemetery"]({OSM_BBOX});
 way["amenity"="grave_yard"]({OSM_BBOX});
 way["leisure"~"park|nature_reserve|garden"]["name"]({OSM_BBOX});
 relation["leisure"~"park|nature_reserve"]["name"]({OSM_BBOX});
 way["natural"="wood"]["name"]({OSM_BBOX}); relation["natural"="wood"]["name"]({OSM_BBOX});
 way["landuse"="forest"]["name"]({OSM_BBOX}); relation["boundary"="protected_area"]["name"]({OSM_BBOX}););
out geom;"""


def _overpass(query: str) -> dict:
    """Eine Overpass-Abfrage mit eigenem User-Agent; bei Überlast (502/504) mit wachsender Pause neu."""
    import time
    import urllib.parse
    import urllib.request
    req = urllib.request.Request("https://overpass-api.de/api/interpreter",
                                 data=urllib.parse.urlencode({"data": query}).encode(), headers={"User-Agent": OSM_UA})
    for pause in (20, 60, 120, None):
        try:
            with urllib.request.urlopen(req, timeout=150) as r:
                return json.loads(r.read())
        except OSError as e:
            print("   Overpass:", e, flush=True)
            if pause is None:
                raise
            time.sleep(pause)
    raise AssertionError("unerreichbar")


def osm_holen() -> None:
    """Holt einmal, was die Builder aus OSM lesen (``~/.cache/ratslotse/plan-quellen/osm/``, nicht im Repo):
    benannte Grünflächen für den Lärmaktionsplan und die Gebäude rund um jeden Versorgungsbereich des EEK
    (je ±``EEK_SEARCH_M`` um den Standort auf Karte 33). Zwischen den Abfragen drei Sekunden Pause."""
    import sqlite3
    import time
    import pymupdf
    from plan_massnahmen import holen
    OSM_DIR.mkdir(parents=True, exist_ok=True)
    quiet = _overpass(OSM_QUIET_QUERY)
    (OSM_DIR / "ruhige-gebiete.json").write_text(json.dumps(quiet, ensure_ascii=False), encoding="utf-8")
    print(f"ruhige-gebiete.json: {len(quiet['elements'])} Elemente")
    conn = sqlite3.connect(f"file:{WURZEL / 'data' / 'council.sqlite'}?mode=ro", uri=True)
    centre_merc, *_ = _k33(pymupdf.open(holen(EEK_DOC["document_id"])), conn)
    conn.close()
    elements, seen = [], set()
    r = EEK_SEARCH_M / U.COS
    for key in EEK_BOUNDARIES:
        time.sleep(3)
        cx, cy = centre_merc[key]
        (lon0, lat0), (lon1, lat1) = U._lonlat(cx - r, cy - r), U._lonlat(cx + r, cy + r)
        part = _overpass(f'[out:json][timeout:90];(way["building"]({lat0:.5f},{lon0:.5f},{lat1:.5f},{lon1:.5f}););out geom;')
        new = [e for e in part["elements"] if e["id"] not in seen]
        seen.update(e["id"] for e in new)
        elements += new
        print(f"   {key}: {len(new)} Gebäude", flush=True)
    (OSM_DIR / "eek-gebaeude.json").write_text(json.dumps({"elements": elements}), encoding="utf-8")
    print(f"eek-gebaeude.json: {len(elements)} Gebäude")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--nur", default="", help="nur diese Karten (kommagetrennt)")
    ap.add_argument("--out", default=str(plan_state.SHAPES_DIR))
    ap.add_argument("--osm", action="store_true", help="erst die OSM-Daten holen (einmal, ~15 Minuten)")
    ap.add_argument("--pruefen", action="store_true", help="die Dateien prüfen, ohne PDF")
    args = ap.parse_args(argv)
    keys = [k for k in BUILDERS if not args.nur or k in args.nur.split(",")]
    if args.pruefen:
        failed = False
        for key in keys:
            data = plan_state.plan_shapes(key)
            problems = check(key, data) if data else ["keine Datei"]
            failed |= bool(problems)
            print(f"{key}: " + ("; ".join(problems) or f"✓ {len((data or {})['features'])} Einträge"))
        return 1 if failed else 0
    if args.osm:
        osm_holen()
    for key in keys:
        data, notes = BUILDERS[key]()
        problems = check(key, data)
        print(f"{key}: {len(data['features'])} Einträge, Verortung {data.get('fit')}")
        for f in data["features"]:
            p = f["properties"]
            top = ", ".join(f"{k} {v:.0%}" for k, v in list(p["districts"].items())[:3])
            ha = f"{p['area_ha']:7.1f} ha" if p.get("area_ha") is not None else "  Punkt  "
            print(f"   {p['code']:>4} {p['name'][:32]:32s} {ha} (Plan {p['area_ha_plan']}) {p['source']}  [{top}]")
        for n in notes:
            print("   ·", n)
        if problems:
            print("   ✗ " + "\n   ✗ ".join(problems))
            return 1
        out = Path(args.out) / f"{key}.geojson"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(data, ensure_ascii=False, default=float) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
