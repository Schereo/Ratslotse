#!/usr/bin/env python3
"""Umrisse aus den Kartenbildern eines Plans nachzeichnen — als Geometrie, die man benutzen kann.

Die Karten im Abschlussbericht der Wärmeplanung (Anlage 306748 zu 26/0236) sind Rasterbilder,
keine Vektoren. Der Weg zur Geometrie, ohne Sprachmodell:

1. **Übersicht verorten** (Abbildung 34, S. 78): Die Karte zeigt die Stadtgrenze als dunkle Linie.
   Unsere Stadtgrenze (Vereinigung der Ortsbereiche) wird so lange verschoben und skaliert, bis sie
   auf dieser Linie liegt (Web-Mercator, Norden oben) — danach entspricht ein Pixel rund 9,5 m.
2. **Detailkarte verorten** (Abbildungen 35–45, je Gebiet): Die rosa Flächen der Detailkarte werden
   gegen die der Übersicht gelegt (Kreuzkorrelation über Maßstab und Lage), dann an den Straßen des
   Ortskatalogs (OpenStreetMap) nachgerichtet. Stimmt der so gefundene Maßstab nicht auf 3 % mit dem
   Maßstabsbalken der Karte (von Hand abgelesen, ``BARS``), gilt der Balken und die Lage kommt aus
   der Übersicht — bei kleinen Ausschnitten gibt es zu wenige Katalogstraßen.
3. **Umriss füllen**: Was die türkise Linie einschließt, wird zum Polygon (Linienmitte, geglättet).

Geprüft wird gegen die Flächen, die der Plan selbst nennt (sechs von elf Gebieten), und an Orten, die
im Umriss liegen müssen (``PROBES``). Ergebnis: ``council/plan_shapes/waermeplan.geojson``
(eingecheckt) — je Gebiet ein Polygon in WGS84 mit Kennung, Seite, Fläche und Ortsbereichen.

Braucht numpy, Pillow, shapely und PyMuPDF (alle im venv) und den Ortskatalog in ``data/``.

    python scripts/plan_umrisse.py            # nachzeichnen und schreiben (~10 s)
    python scripts/plan_umrisse.py --pruefen  # Datei prüfen, ohne PDF und ohne Katalog
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sqlite3
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))
sys.path.insert(0, str(WURZEL / "scripts"))

from council import geo, places, plan_state  # noqa: E402

R = 6378137.0
COS = math.cos(math.radians(53.14))
DOCUMENT = {"document_id": 306748, "template": "26/0236", "label": "Abschlussbericht Kommunale Wärmeplanung"}
OVERVIEW_PAGE = 78
#: Kennung → (Seite der Detailkarte, Abbildung).
DETAILS: dict[str, tuple[int, int]] = {
    "WNG 1": (82, 35), "WNG 2": (84, 36), "WNG 3": (86, 37), "WNG 4": (89, 38), "WNG 5": (91, 39), "WNG 6": (93, 40),
    "WNG 7": (95, 41), "WNG 8": (98, 42), "WNG 9": (101, 43), "WNG 10": (103, 44), "WNG 11": (105, 45),
}
#: Maßstabsbalken, von Hand abgelesen: (Meter, Pixel). WNG 9 hat keinen (Karte unten beschnitten).
BARS: dict[str, tuple[int, int]] = {
    "WNG 1": (200, 73), "WNG 2": (200, 81), "WNG 3": (200, 96), "WNG 4": (100, 78), "WNG 5": (100, 73),
    "WNG 6": (50, 63), "WNG 7": (100, 66), "WNG 8": (50, 72), "WNG 10": (100, 56), "WNG 11": (30, 76),
}
#: Fläche laut Text des Plans (ha), wo er eine nennt.
STATED_HA: dict[str, float] = {"WNG 6": 11.72, "WNG 7": 43.4, "WNG 8": 6.35, "WNG 9": 167.0, "WNG 10": 124.67,
                               "WNG 11": 2.98}
#: Orte, die im Umriss liegen müssen (Name im Ortskatalog) — die Gegenprobe der Lage.
PROBES: dict[str, tuple[str, ...]] = {
    "WNG 1": ("Lambertikirche", "Hauptbahnhof"), "WNG 2": ("Universität",), "WNG 4": ("Alte Fleiwa",),
    "WNG 5": ("Melkbrink",), "WNG 7": ("Kennedystraße",), "WNG 8": ("Sodenstich",), "WNG 9": ("Kaufpark Kreyenbrück",),
    "WNG 10": ("Schlachthof Oldenburg",),
}
#: Abweichung von der Fläche laut Plan, ab der etwas nicht stimmt.
AREA_TOLERANCE = 0.05
#: Für die Seite genügt ein gröberer Umriss (Grad; rund 4 m) — die Treppen der Pixel fallen weg, die Antwort
#: schrumpft von 75 auf 20 KB, die Fläche ändert sich um höchstens 1,5 %.
DISPLAY_SIMPLIFY = 0.00004
LEGEND = (420, 240)  # Legende oben links: Zeilen, Spalten


def _merc(lon: float, lat: float) -> tuple[float, float]:
    return R * math.radians(lon), R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def _lonlat(x: float, y: float) -> tuple[float, float]:
    return math.degrees(x / R), math.degrees(2 * math.atan(math.exp(y / R)) - math.pi / 2)


def _image(doc, page: int):
    import numpy as np
    import pymupdf
    from PIL import Image
    xref = max(doc[page - 1].get_images(full=True), key=lambda i: i[2] * i[3])[0]
    pix = pymupdf.Pixmap(doc, xref)
    if pix.n - pix.alpha >= 4:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    img = Image.frombytes("RGB" if pix.n == 3 else "RGBA", (pix.width, pix.height), pix.samples).convert("RGB")
    return np.asarray(img).astype(int)


def _parts(geometry) -> list:
    """Die Polygone einer Fläche — ein Polygon oder die Teile eines MultiPolygons."""
    return list(getattr(geometry, "geoms", [geometry]))


def _map_coords(geometry: dict, fn) -> dict:
    """GeoJSON-Geometrie mit umgerechneten Koordinaten (``fn(x, y) -> (x, y)``)."""
    def walk(c):
        return list(fn(c[0], c[1])) if isinstance(c[0], (int, float)) else [walk(x) for x in c]
    return {"type": geometry["type"], "coordinates": walk(geometry["coordinates"])}


def _pink(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return ((r - g) > 25) & ((b - g) > 15)


def _distance(mask, cap: float):
    """Abstand jedes Pixels zur nächsten Maske (Manhattan, zwei Durchgänge), gekappt."""
    import numpy as np
    h, w = mask.shape
    d = np.where(mask, 0.0, 1e6)
    for y in range(h):
        if y:
            d[y] = np.minimum(d[y], d[y - 1] + 1)
        row = d[y]
        for x in range(1, w):
            if row[x - 1] + 1 < row[x]:
                row[x] = row[x - 1] + 1
        for x in range(w - 2, -1, -1):
            if row[x + 1] + 1 < row[x]:
                row[x] = row[x + 1] + 1
    for y in range(h - 2, -1, -1):
        d[y] = np.minimum(d[y], d[y + 1] + 1)
    return np.minimum(d, cap)


def _search(cost, start: tuple[float, float, float], steps, scale_free: bool = True):
    """Schrittweise Suche über (Maßstab, x, y) — vom Groben ins Feine."""
    best = (cost(*start), *start)
    for ds, dt_ in steps:
        better = True
        while better:
            better = False
            _, s, x0, y0 = best
            for fs in ((-ds, 0, ds) if scale_free else (0,)):
                for fx in (-dt_, 0, dt_):
                    for fy in (-dt_, 0, dt_):
                        c = cost(s * (1 + fs), x0 + fx * s, y0 + fy * s)
                        if c < best[0] - 1e-9:
                            best = (c, s * (1 + fs), x0 + fx * s, y0 + fy * s)
                            better = True
    return best


def georef_overview(a) -> dict:
    """Übersicht auf die Stadtgrenze legen: Pixel → Mercator (``s`` m/px, Ursprung ``tx``/``ty``)."""
    import numpy as np
    from shapely.geometry import shape
    from shapely.ops import unary_union
    dark = a.max(axis=2) < 90
    dark[:200, :380] = False   # Legende
    dark[1370:, :260] = False  # Maßstab, Nordpfeil
    city = unary_union([shape(f["geometry"]) for f in geo._features()]).buffer(0)
    city = max(_parts(city), key=lambda g: g.area)
    ring = [_merc(x, y) for x, y in city.exterior.coords]
    pts = np.array([(x1 + (x2 - x1) * i / n, y1 + (y2 - y1) * i / n)
                    for (x1, y1), (x2, y2) in zip(ring, ring[1:])
                    for n in [max(1, int(math.hypot(x2 - x1, y2 - y1) / 20))] for i in range(n)])
    dist = _distance(dark, 30.0)
    h, w = dark.shape

    def cost(s, tx, ty):
        px, py = (pts[:, 0] - tx) / s, (ty - pts[:, 1]) / s
        ok = (px >= 0) & (px < w - 1) & (py >= 0) & (py < h - 1)
        return 1e9 if ok.mean() < 0.98 else float(np.mean(dist[py[ok].astype(int), px[ok].astype(int)]))
    ys, xs = np.nonzero(dark)
    bx0, bx1, by0, by1 = (np.percentile(xs, 0.5), np.percentile(xs, 99.5), np.percentile(ys, 0.5), np.percentile(ys, 99.5))
    s = max((pts[:, 0].max() - pts[:, 0].min()) / (bx1 - bx0), (pts[:, 1].max() - pts[:, 1].min()) / (by1 - by0))
    c, s, tx, ty = _search(lambda s_, x_, y_: cost(s_, x_, y_), (s, pts[:, 0].min() - bx0 * s, pts[:, 1].max() + by0 * s),
                           [(0.04, 25), (0.02, 12), (0.01, 6), (0.005, 3), (0.002, 1.2), (0.001, 0.5), (0.0005, 0.2)])
    return {"s": s, "tx": tx, "ty": ty, "fit_px": c, "pink": _pink(a)}


def _correlate(overview_pink, detail_pink, k: float) -> tuple[float, int, int]:
    import numpy as np
    from PIL import Image
    Hd, Wd = detail_pink.shape
    H, W = overview_pink.shape
    w, h = max(4, int(Wd * k)), max(4, int(Hd * k))
    small = np.asarray(Image.fromarray((detail_pink * 255).astype(np.uint8)).resize((w, h), Image.Resampling.BILINEAR)) / 255.0
    A = np.fft.rfft2(overview_pink - overview_pink.mean(), s=(H + h, W + w))
    B = np.fft.rfft2((small - small.mean())[::-1, ::-1], s=(H + h, W + w))
    c = np.fft.irfft2(A * B, s=(H + h, W + w))[h - 1:H, w - 1:W]
    iy, ix = np.unravel_index(np.argmax(c), c.shape)
    return float(c[iy, ix] / (small.std() * small.size + 1e-9)), int(ix), int(iy)


def _catalog_points(conn, lon0, lat0, lon1, lat1):
    import numpy as np
    pts = []
    for (raw,) in conn.execute("""SELECT geojson FROM council_locations WHERE kind IN ('street','square')
                                  AND geojson IS NOT NULL AND lon BETWEEN ? AND ? AND lat BETWEEN ? AND ?""",
                               (lon0, lon1, lat0, lat1)):
        shape_ = json.loads(raw)
        lines = ([shape_["coordinates"]] if shape_["type"] == "LineString"
                 else shape_["coordinates"] if shape_["type"] == "MultiLineString" else [])
        for line in lines:
            for p, q in zip(line, line[1:]):
                (x1, y1), (x2, y2) = _merc(p[0], p[1]), _merc(q[0], q[1])
                n = max(1, int(math.hypot(x2 - x1, y2 - y1) / 4))
                pts += [(x1 + (x2 - x1) * i / n, y1 + (y2 - y1) * i / n) for i in range(n)]
    return np.array(pts) if pts else np.zeros((0, 2))


def register_detail(a, ov: dict, conn, code: str) -> dict:
    """Detailkarte → Mercator: Maßstab ``s`` (m/px Mercator), Ursprung ``x0``/``y0`` und wie gefunden."""
    import numpy as np
    pink = _pink(a)
    pink[:LEGEND[0], :LEGEND[1]] = False
    O = ov["pink"].astype(float)
    O[:200, :380] = 0
    best = max((_correlate(O, pink, k) + (k,) for k in np.arange(0.03, 0.40, 0.005)), key=lambda t: t[0])
    best = max((_correlate(O, pink, k) + (k,) for k in np.arange(best[3] - 0.006, best[3] + 0.006, 0.0005)),
               key=lambda t: t[0])
    _, ox, oy, k = best
    s0, X0, Y0 = ov["s"] * k, ov["tx"] + ox * ov["s"], ov["ty"] - oy * ov["s"]
    Hd, Wd, _ = a.shape
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    cyan = (r < 140) & (g > 170) & (b > 170) & (g - r > 60)
    road = ((a.max(axis=2) - a.min(axis=2)) > 80) & (b <= g + 10) & ~cyan
    road[:LEGEND[0], :LEGEND[1]] = False
    road[Hd - 40:, :300] = False
    dist = _distance(road, 25.0)
    lo0, la1 = _lonlat(X0, Y0)
    lo1, la0 = _lonlat(X0 + Wd * s0, Y0 - Hd * s0)
    P = _catalog_points(conn, lo0 - 0.003, la0 - 0.002, lo1 + 0.003, la1 + 0.002)

    def cost(s, x0, y0):
        if len(P) == 0:
            return 1e9
        u, v = (P[:, 0] - x0) / s, (y0 - P[:, 1]) / s
        ok = (u >= 0) & (u < Wd - 1) & (v >= 0) & (v < Hd - 1)
        return 1e9 if ok.sum() < 300 else float(np.mean(dist[v[ok].astype(int), u[ok].astype(int)]))
    c, s, x0, y0 = _search(cost, (s0, X0, Y0), [(0.04, 40), (0.02, 20), (0.01, 10), (0.005, 5), (0.0025, 2.5),
                                                (0.001, 1), (0.0005, 0.5)])
    how = "Straßen"
    if code in BARS:
        s_bar = BARS[code][0] / BARS[code][1] / COS
        if c >= 1e8 or abs(s / s_bar - 1) > 0.03:
            _, ox, oy = _correlate(O, pink, s_bar / ov["s"])
            c, s, x0, y0 = None, s_bar, ov["tx"] + ox * ov["s"], ov["ty"] - oy * ov["s"]
            how = "Maßstabsbalken und Übersicht"
    return {"s": s, "x0": x0, "y0": y0, "fit_px": c, "how": how, "cyan": cyan}


def outline(cyan, grow: int = 2, half: float = 1.75):
    """Was die türkise Linie einschließt — Lücken (Beschriftung) geschlossen, zur Linienmitte gewachsen."""
    import numpy as np
    from PIL import Image, ImageDraw
    from shapely.geometry import box
    from shapely.ops import unary_union
    g = cyan.copy()
    g[:LEGEND[0], :LEGEND[1]] = False
    for _ in range(grow):
        g2 = g.copy()
        g2[1:] |= g[:-1]
        g2[:-1] |= g[1:]
        g2[:, 1:] |= g[:, :-1]
        g2[:, :-1] |= g[:, 1:]
        g = g2
    h, w = g.shape
    img = Image.fromarray(np.where(g, 255, 0).astype(np.uint8)).copy()
    for x in range(w):
        for y in (0, h - 1):
            if img.getpixel((x, y)) == 0:
                ImageDraw.floodfill(img, (x, y), 128)
    for y in range(h):
        for x in (0, w - 1):
            if img.getpixel((x, y)) == 0:
                ImageDraw.floodfill(img, (x, y), 128)
    inside = np.asarray(img) == 0
    rects = []
    for y in range(h):
        d = np.diff(np.concatenate([[0], inside[y].astype(int), [0]]))
        rects += [box(float(x0), y, float(x1), y + 1) for x0, x1 in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0])]
    poly = unary_union(rects)
    parts = [p for p in _parts(poly) if p.area > 400]
    return unary_union(parts).buffer(grow + half, join_style="mitre").simplify(0.8)


def districts(polygon) -> dict[str, float]:
    """Anteil der Fläche je Ortsbereich, auf zwei Stellen."""
    from shapely.geometry import shape
    out = {}
    for place in places.primary_places():
        poly = geo.ortsbereich_polygon(place.name)
        if poly:
            share = polygon.intersection(shape(poly)).area / polygon.area
            if share >= 0.01:
                out[place.id] = round(share, 2)
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def _rings(geometry: dict) -> list[list[list[list[float]]]]:
    """Polygon oder MultiPolygon → Liste von Polygonen (je Liste von Ringen)."""
    return [geometry["coordinates"]] if geometry["type"] == "Polygon" else list(geometry["coordinates"])


def _ring_area(ring) -> float:
    pts = [(x * 111_320 * COS, y * 110_540) for x, y, *_ in ring]
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))) / 2


def area_ha(geometry: dict) -> float:
    """Fläche auf der Erde (örtliche Ebene um Oldenburg), ohne shapely — Löcher abgezogen."""
    return sum(_ring_area(poly[0]) - sum(_ring_area(h) for h in poly[1:]) for poly in _rings(geometry)) / 10_000


def contains(geometry: dict, lon: float, lat: float) -> bool:
    def inside(ring) -> bool:
        hit = False
        for (x1, y1, *_), (x2, y2, *_) in zip(ring, ring[1:] + ring[:1]):
            if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
                hit = not hit
        return hit
    return any(inside(poly[0]) and not any(inside(h) for h in poly[1:]) for poly in _rings(geometry))


def _area_ha(polygon) -> float:
    from shapely.geometry import mapping
    return area_ha(json.loads(json.dumps(mapping(polygon))))


def build(db: str) -> dict:
    import pymupdf
    from plan_massnahmen import holen
    from shapely.geometry import mapping, shape
    doc = pymupdf.open(holen(DOCUMENT["document_id"]))
    ov = georef_overview(_image(doc, OVERVIEW_PAGE))
    rows = {r["cells"][0]: r["cells"] for lst in (plan_state.plan_lists("waermeplan") or {}).get("lists", [])
            for r in lst["rows"]}
    names = {code: cells[2] for code, cells in rows.items()}
    import plan_angaben
    details = plan_angaben.waermeplan(rows)
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    features = []
    for code, (page, figure) in DETAILS.items():
        a = _image(doc, page)
        reg = register_detail(a, ov, conn, code)
        px_poly = outline(reg["cyan"])
        s, x0, y0 = reg["s"], reg["x0"], reg["y0"]
        poly = shape(_map_coords(dict(mapping(px_poly)),
                                 lambda u, v, x0=x0, y0=y0, s=s: tuple(round(c, 6) for c in _lonlat(x0 + u * s, y0 - v * s))))
        point = poly.representative_point()
        display = json.loads(json.dumps(mapping(poly.simplify(DISPLAY_SIMPLIFY, preserve_topology=True))),
                             parse_float=lambda f: round(float(f), 5))
        features.append({"type": "Feature", "geometry": mapping(poly), "properties": {
            "code": code, "name": names.get(code), "page": page, "figure": figure, **details.get(code, {}),
            "area_ha": round(_area_ha(poly), 2), "area_ha_plan": STATED_HA.get(code),
            "metres_per_pixel": round(s * COS, 3), "placed_by": reg["how"],
            "street_fit_m": round(reg["fit_px"] * s * COS, 1) if reg["fit_px"] is not None else None,
            "districts": districts(poly),
            # Für die Seite (der Server rechnet ohne shapely): Beschriftungspunkt und vereinfachter Umriss.
            "label_point": [round(point.x, 5), round(point.y, 5)], "display_geometry": display}})
    conn.close()
    return {"type": "FeatureCollection", "name": "Wärmenetzeignungsgebiete Oldenburg",
            "plan": "waermeplan", "document": DOCUMENT, "generated": dt.date.today().isoformat(),
            # So liest plan_pages die Gebiete: „Eignungsgebiet „WNG 7 Kennedyviertel““.
            "group": "Eignungsgebiet", "code_in_name": True,
            "groups": plan_angaben.groups("waermeplan", DOCUMENT["document_id"]),
            "method": "Nachgezeichnet aus den Kartenbildern des Abschlussberichts (Abbildungen 35–45), verortet über "
                      "die Übersichtskarte (Abbildung 34) und die Straßen des Ortskatalogs; scripts/plan_umrisse.py",
            "attribution": "Stadt Oldenburg, Kommunale Wärmeplanung (26/0236); Straßen © OpenStreetMap-Mitwirkende, ODbL",
            "overview_metres_per_pixel": round(ov["s"] * COS, 2), "features": features}


def check(data: dict, conn=None) -> list[str]:
    """Ohne PDF und ohne shapely: Anzahl, Ringe, Stadtgebiet, Fläche gegen den Plan, Ortsbereiche;
    mit ``conn`` die Gegenprobe an Orten, die im Umriss liegen müssen."""
    problems = []
    primary = {p.id for p in places.primary_places()}
    codes = [f["properties"]["code"] for f in data["features"]]
    if codes != list(DETAILS):
        problems.append(f"Gebiete {codes} statt {list(DETAILS)}")
    for f in data["features"]:
        props, geometry = f["properties"], f["geometry"]
        where = props["code"]
        if geometry.get("type") not in ("Polygon", "MultiPolygon") or any(
                len(ring) < 4 or ring[0] != ring[-1] for poly in _rings(geometry) for ring in poly):
            problems.append(f"{where}: kein geschlossenes Polygon")
            continue
        lon, lat = props["label_point"]
        if not contains(geometry, lon, lat) or not geo.ortsbereich_for(lat, lon):
            problems.append(f"{where}: Beschriftungspunkt liegt nicht im Umriss oder nicht in Oldenburg")
        if abs(area_ha(geometry) - props["area_ha"]) > 0.1:
            problems.append(f"{where}: Fläche passt nicht zum Polygon")
        if abs(area_ha(props["display_geometry"]) / props["area_ha"] - 1) > 0.02:
            problems.append(f"{where}: Der vereinfachte Umriss weicht zu weit ab")
        stated = props.get("area_ha_plan")
        if stated and abs(props["area_ha"] / stated - 1) > AREA_TOLERANCE:
            problems.append(f"{where}: {props['area_ha']} ha statt {stated} ha laut Plan")
        if not props["districts"] or not set(props["districts"]) <= primary:
            problems.append(f"{where}: Ortsbereiche fehlen oder sind unbekannt")
        if conn is not None:
            for name in PROBES.get(where, ()):
                row = conn.execute("SELECT lat, lon FROM council_locations WHERE name = ? AND lat IS NOT NULL",
                                   (name,)).fetchone()
                if row and not contains(geometry, row[1], row[0]):
                    problems.append(f"{where}: {name} liegt nicht im Umriss")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--db", default=str(WURZEL / "data" / "council.sqlite"))
    ap.add_argument("--pruefen", action="store_true")
    args = ap.parse_args(argv)
    path = plan_state.SHAPES_DIR / "waermeplan.geojson"
    if args.pruefen:
        data = plan_state.plan_shapes("waermeplan")
        if data is None:
            print("keine Datei")
            return 1
        conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True) if Path(args.db).exists() else None
        problems = check(data, conn)
        print("\n".join(problems) or f"✓ {len(data['features'])} Umrisse passen")
        return 1 if problems else 0
    data = build(args.db)
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    problems = check(data, conn)
    for f in data["features"]:
        p = f["properties"]
        print(f"{p['code']:7s} {p['area_ha']:7.2f} ha" + (f" (Plan {p['area_ha_plan']})" if p["area_ha_plan"] else "")
              + f"  {p['metres_per_pixel']} m/px, {p['placed_by']}"
              + (f", Straßenabstand {p['street_fit_m']} m" if p["street_fit_m"] is not None else ""))
    if problems:
        print("\n".join(problems))
        return 1
    plan_state.SHAPES_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"geschrieben: {path.relative_to(WURZEL)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
