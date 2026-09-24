#!/usr/bin/env python3
"""Die Wahlbereiche und Wahlbezirke der Stadt als Kartenflächen holen.

Tims Frage (14.09.2026): „Wo is eigentlich nochmal Wahlbereich 5?" — die
Wahlabend-Seite kannte die sechs Wahlbereiche bis dahin nur als römische
Ziffern.

**Die Stadt veröffentlicht sie.** Über das openGEOdata-Portal liegt ein
Feature Service ``Wahlen`` mit drei Ebenen; wir brauchen zwei davon:

    Ebene 0  Wahlbezirke    91 Flächen, Felder BezirksNr / Wahlbereiche /
                            Stadtbezirk / Wahllokal_ID
    Ebene 1  Wahlbereiche    6 Flächen, Feld Wahlbereiche
    (Ebene 2  Wahlkreise — Landtag, für uns ohne Belang)

Lizenz: Datenlizenz Deutschland – Zero – Version 2.0 (dl-zero-de/2.0), also
ohne Namensnennungspflicht. Wir nennen die Quelle trotzdem, im Dateikopf und
auf der Seite.

**Warum ein Skript und kein Cron.** Wahlbezirke ändern sich vor einer Wahl,
nicht dazwischen; der Stand des Dienstes ist von 09/2024. Vor der nächsten
Wahl einmal ``hol`` laufen lassen, den Diff ansehen, mitcommitten. Ein Cron
hätte nichts zu tun und würde eine fremde Schnittstelle wöchentlich anfassen.

**Warum vereinfacht.** Roh sind die 91 Wahlbezirke 439 KB GeoJSON — für eine
Übersichtskarte, auf der ein Bezirk 30 Pixel breit ist, ist das Auflösung, die
niemand sieht und jedes Handy lädt. Douglas-Peucker mit 25 m Toleranz, wie bei
den Ortsbereichen (``public/geo/stadtteile-oldenburg.json``, 18 KB).

    python scripts/wahl_geodaten.py hol          # holen, vereinfachen, schreiben
    python scripts/wahl_geodaten.py hol --roh    # ohne Vereinfachung (zum Vergleichen)
    python scripts/wahl_geodaten.py pruefe       # was liegt da, und passt es zur Wahl?
    python scripts/wahl_geodaten.py ueberlappung # welcher Bezirk liegt in welchem Ortsbereich?

**Wahlbezirke liegen nicht in den Ortsbereichen** (gemessen 23.09.2026): Bei
25 von 91 liegen weniger als 80 % der Fläche in einem einzigen, Innenstadt
und Drielake haben gar keinen Bezirk, der überwiegend in ihnen liegt. Die
Stadtkarte zeigt je Ortsbereich deshalb ALLE Bezirke, die ihn berühren —
und ``ueberlappung`` rechnet die Anteile dafür
(``kommunalwahl/geo/wahlbezirk-ortsbereiche.json``, gelesen von
``web/backend/app/election/district_map.py``). Ohne shapely: Die Fläche wird
über ein Raster gezählt, s. ``anteile``.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.request
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
ZIEL = WURZEL / "web" / "frontend" / "public" / "geo"
ORTSBEREICHE = ZIEL / "stadtteile-oldenburg.json"
UEBERLAPPUNG = WURZEL / "kommunalwahl" / "geo" / "wahlbezirk-ortsbereiche.json"
#: Rasterweite der Flächenzählung in Metern. Ein Bezirk ist Hunderte Meter
#: breit; bei 20 m liegt die Abweichung gegen eine exakte Verschneidung
#: (shapely, einmal gemessen) unter einem Prozentpunkt je Anteil.
RASTER_M = 20.0
#: Anteile darunter fallen weg — ein Zipfel an der Grenze ist kein „liegt in".
SCHWELLE = 0.05

DIENST = ("https://services5.arcgis.com/kqBnwL0FsBhsJf2P/arcgis/rest/services/"
          "Wahlen/FeatureServer")
#: Ebene → (Zieldatei, Beschriftung). Die Ebenennummern stehen im Dienst und
#: sind Teil des Vertrags mit der Stadt; ändern sie sich, meldet ``pruefe`` es.
EBENEN = {
    1: ("wahlbereiche-oldenburg.json", "Wahlbereiche"),
    0: ("wahlbezirke-oldenburg.json", "Wahlbezirke"),
}
#: Toleranz der Vereinfachung in Metern — dieselbe wie bei den Ortsbereichen.
TOLERANZ_M = 25.0
#: Nachkommastellen der Ausgabe. Fünf sind gut einen Meter; mehr zu schreiben
#: hieße, eine Genauigkeit zu behaupten, die die Vereinfachung gerade
#: weggenommen hat.
STELLEN = 5
LIZENZ = "dl-zero-de/2.0"
QUELLE = "Stadt Oldenburg, openGEOdata — Feature Service „Wahlen“"


def hole(ebene: int) -> dict:
    """Eine Ebene als GeoJSON in WGS 84. Der Dienst rechnet selbst um
    (``outSR=4326``) — seine Heimat ist EPSG 25832."""
    url = (f"{DIENST}/{ebene}/query?where=1%3D1&outFields=*"
           f"&f=geojson&outSR=4326")
    with urllib.request.urlopen(url, timeout=60) as r:  # noqa: S310 — feste Adresse
        return json.loads(r.read().decode("utf-8"))


# ------------------------------------------------------------------ vereinfachen

def _meter_je_grad(lat: float) -> tuple[float, float]:
    """Wie viele Meter ein Grad Länge und Breite hier sind.

    Douglas-Peucker rechnet mit Abständen, und in Grad gemessen wäre ein
    Abstand in Ost-West-Richtung auf Oldenburgs Breite um 40 % zu groß
    bewertet. Deshalb wird vor dem Vereinfachen in Meter skaliert.
    """
    return 111_320.0 * math.cos(math.radians(lat)), 110_574.0


def _abstand(p, a, b, mx: float, my: float) -> float:
    """Abstand des Punktes ``p`` von der Strecke ``a``–``b``, in Metern."""
    px, py = (p[0] - a[0]) * mx, (p[1] - a[1]) * my
    bx, by = (b[0] - a[0]) * mx, (b[1] - a[1]) * my
    laenge = bx * bx + by * by
    if laenge == 0:
        return math.hypot(px, py)
    t = max(0.0, min(1.0, (px * bx + py * by) / laenge))
    return math.hypot(px - t * bx, py - t * by)


def _douglas_peucker(punkte: list, toleranz: float, mx: float, my: float) -> list:
    if len(punkte) < 3:
        return punkte
    weit, i = 0.0, 0
    for k in range(1, len(punkte) - 1):
        d = _abstand(punkte[k], punkte[0], punkte[-1], mx, my)
        if d > weit:
            weit, i = d, k
    if weit <= toleranz:
        return [punkte[0], punkte[-1]]
    links = _douglas_peucker(punkte[: i + 1], toleranz, mx, my)
    rechts = _douglas_peucker(punkte[i:], toleranz, mx, my)
    return links[:-1] + rechts


def _ring(ring: list, toleranz: float) -> list:
    """Ein geschlossener Ring, vereinfacht — und geschlossen geblieben.

    Ein Ring mit weniger als vier Punkten ist keine Fläche mehr; solche
    bleiben unverändert, statt zu verschwinden.
    """
    if len(ring) < 5:
        return [[round(x, STELLEN), round(y, STELLEN)] for x, y in ring]
    mx, my = _meter_je_grad(ring[0][1])
    vereinfacht = _douglas_peucker(ring[:-1], toleranz, mx, my)
    if len(vereinfacht) < 3:
        vereinfacht = ring[:-1]
    vereinfacht = [[round(x, STELLEN), round(y, STELLEN)] for x, y in vereinfacht]
    return vereinfacht + [vereinfacht[0]]


def vereinfache(geometrie: dict, toleranz: float = TOLERANZ_M) -> dict:
    art = geometrie["type"]
    if art == "Polygon":
        return {"type": art, "coordinates": [_ring(r, toleranz) for r in geometrie["coordinates"]]}
    if art == "MultiPolygon":
        return {"type": art, "coordinates": [[_ring(r, toleranz) for r in teil]
                                             for teil in geometrie["coordinates"]]}
    raise ValueError(f"unerwartete Geometrie: {art}")


# ------------------------------------------------------------------ umformen

def _eigenschaften(ebene: int, roh: dict) -> dict:
    """Aus den Feldern der Stadt die, die wir zeichnen — kurz benannt und
    ohne Führung von OBJECTID, Fläche und Umfang."""
    if ebene == 1:
        return {"nr": int(roh["Wahlbereiche"])}
    return {
        "nr": int(roh["BezirksNr"]),
        "wb": int(roh["Wahlbereiche"]),
        "name": (roh.get("Stadtbezirk") or "").strip(),
        "lokal": roh.get("Wahllokal_ID"),
    }


def baue(ebene: int, roh: dict, *, toleranz: float | None) -> dict:
    features = []
    for f in roh.get("features", []):
        if not f.get("geometry"):
            continue
        geo = f["geometry"] if toleranz is None else vereinfache(f["geometry"], toleranz)
        features.append({"type": "Feature",
                         "properties": _eigenschaften(ebene, f.get("properties", {})),
                         "geometry": geo})
    features.sort(key=lambda f: f["properties"]["nr"])
    return {
        "type": "FeatureCollection",
        "attribution": f"{EBENEN[ebene][1]}: {QUELLE}, {LIZENZ}",
        "license": LIZENZ,
        "source": DIENST,
        "features": features,
    }


# ------------------------------------------------------------------ Befehle

def cmd_hol(a: argparse.Namespace) -> int:
    ZIEL.mkdir(parents=True, exist_ok=True)
    for ebene, (datei, label) in EBENEN.items():
        roh = hole(ebene)
        n = len(roh.get("features", []))
        fertig = baue(ebene, roh, toleranz=None if a.roh else a.toleranz)
        pfad = ZIEL / datei
        vorher = pfad.stat().st_size if pfad.exists() else 0
        pfad.write_text(json.dumps(fertig, ensure_ascii=False, separators=(",", ":")) + "\n",
                        encoding="utf-8")
        gross = pfad.stat().st_size
        punkte_roh = sum(_punkte(f["geometry"]) for f in roh["features"] if f.get("geometry"))
        punkte = sum(_punkte(f["geometry"]) for f in fertig["features"])
        print(f"{label}: {n} Flächen, {punkte_roh} → {punkte} Punkte, "
              f"{gross // 1024} KB" + (f" (vorher {vorher // 1024} KB)" if vorher else ""))
        print(f"  {pfad.relative_to(WURZEL)}")
    return 0


def _punkte(geo: dict) -> int:
    if geo["type"] == "Polygon":
        return sum(len(r) for r in geo["coordinates"])
    return sum(len(r) for teil in geo["coordinates"] for r in teil)


def cmd_pruefe(_: argparse.Namespace) -> int:
    """Liegt da, was wir erwarten — und passt es zur jüngsten Wahl?"""
    import csv

    fehler = 0
    bereiche = json.loads((ZIEL / EBENEN[1][0]).read_text(encoding="utf-8"))
    bezirke = json.loads((ZIEL / EBENEN[0][0]).read_text(encoding="utf-8"))
    print(f"Wahlbereiche: {len(bereiche['features'])}, Wahlbezirke: {len(bezirke['features'])}")

    nummern = {f["properties"]["nr"] for f in bezirke["features"]}
    zu_bereich = {f["properties"]["nr"] for f in bereiche["features"]}
    if zu_bereich != {f["properties"]["wb"] for f in bezirke["features"]}:
        print("  ✗ Die Wahlbereiche der Bezirke passen nicht zu den Wahlbereichs-Flächen")
        fehler += 1

    csv_datei = WURZEL / "kommunalwahl" / "referenz-2026" / "ratswahl-2026-wahlbezirke.csv"
    if csv_datei.exists():
        with csv_datei.open(encoding="utf-8-sig") as fh:
            gemeldet = {int(r["gebiet-nr"]) for r in csv.DictReader(fh, delimiter=";")
                        if r["gebiet-nr"].isdigit()}
        # Briefwahlbezirke haben keine Fläche und brauchen keine. Sie tragen
        # Nummern ab 900, ihr Wahlbereich steckt in der Zehnerstelle
        # (910…916 = I, 960…966 = VI) — s. votemanager._area_number.
        urne = {n for n in gemeldet if n < 900}
        fehlt = sorted(urne - nummern)
        zuviel = sorted(nummern - urne)
        print(f"  Ergebnisdatei 2026: {len(gemeldet)} Bezirke, davon {len(urne)} an der Urne")
        if fehlt or zuviel:
            print(f"  ✗ ohne Fläche: {fehlt} · ohne Ergebnis: {zuviel}")
            fehler += 1
        else:
            print("  ✓ jede Urne hat ihre Fläche und umgekehrt")
    return 1 if fehler else 0


# ------------------------------------------------------------------ Überlappung

def _im_ring(x: float, y: float, ring: list) -> bool:
    """Punkt-in-Polygon (Strahlverfahren) für einen Ring."""
    drin = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            drin = not drin
        j = i
    return drin


def _polygone(geo: dict) -> list[list]:
    """Je Teilfläche die Ringe (außen zuerst, danach Löcher)."""
    return [geo["coordinates"]] if geo["type"] == "Polygon" else list(geo["coordinates"])


def _enthaelt(polygone: list[list], x: float, y: float) -> bool:
    for ringe in polygone:
        if ringe and _im_ring(x, y, ringe[0]) and not any(_im_ring(x, y, r) for r in ringe[1:]):
            return True
    return False


def _box(polygone: list[list]) -> tuple[float, float, float, float]:
    xs = [p[0] for ringe in polygone for p in ringe[0]]
    ys = [p[1] for ringe in polygone for p in ringe[0]]
    return min(xs), min(ys), max(xs), max(ys)


def anteile(bezirke: list[dict], orte: list[dict], raster_m: float = RASTER_M,
            schwelle: float = SCHWELLE) -> dict[int, list[dict]]:
    """Je Wahlbezirk die Ortsbereiche, in denen er liegt, mit Flächenanteil.

    Gezählt wird auf einem Raster: jeder Rasterpunkt im Bezirk wird dem
    Ortsbereich zugeschlagen, in dem er liegt. Punkte, die in keinem liegen
    (die vereinfachten Grenzen schließen nicht ganz bündig), zählen nicht.
    Anteile unter ``schwelle`` fallen weg, der Rest wird auf 1 normiert.
    """
    ortsflaechen = []
    for o in orte:
        polys = _polygone(o["geometry"])
        ortsflaechen.append((o["properties"]["name"], polys, _box(polys)))
    out: dict[int, list[dict]] = {}
    for b in bezirke:
        polys = _polygone(b["geometry"])
        x0, y0, x1, y1 = _box(polys)
        mx, my = _meter_je_grad((y0 + y1) / 2)
        dx, dy = raster_m / mx, raster_m / my
        kandidaten = [(n, p) for n, p, (a, c, e, f) in ortsflaechen
                      if a <= x1 and e >= x0 and c <= y1 and f >= y0]
        zaehler: dict[str, int] = {}
        y = y0 + dy / 2
        while y < y1:
            x = x0 + dx / 2
            while x < x1:
                if _enthaelt(polys, x, y):
                    for name, op in kandidaten:
                        if _enthaelt(op, x, y):
                            zaehler[name] = zaehler.get(name, 0) + 1
                            break
                x += dx
            y += dy
        summe = sum(zaehler.values()) or 1
        behalten = {n: z / summe for n, z in zaehler.items() if z / summe >= schwelle}
        rest = sum(behalten.values()) or 1
        out[b["properties"]["nr"]] = [
            {"place": n, "share": round(a / rest, 3)}
            for n, a in sorted(behalten.items(), key=lambda t: (-t[1], t[0]))
        ]
    return out


def cmd_ueberlappung(_: argparse.Namespace) -> int:
    bezirke = json.loads((ZIEL / EBENEN[0][0]).read_text(encoding="utf-8"))["features"]
    orte = json.loads(ORTSBEREICHE.read_text(encoding="utf-8"))["features"]
    tabelle = anteile(bezirke, orte)
    UEBERLAPPUNG.parent.mkdir(parents=True, exist_ok=True)
    UEBERLAPPUNG.write_text(json.dumps({
        "about": ("Welcher Wahlbezirk (Urne) in welchen Ortsbereichen liegt, als "
                  "Flächenanteil. Gerechnet von scripts/wahl_geodaten.py ueberlappung "
                  f"auf einem {RASTER_M:g}-m-Raster aus public/geo/."),
        "threshold": SCHWELLE,
        "districts": {str(nr): orte_ for nr, orte_ in sorted(tabelle.items())},
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    geteilt = sum(1 for o in tabelle.values() if o and o[0]["share"] < 0.8)
    ohne = sorted({o["properties"]["name"] for o in orte}
                  - {e["place"] for o in tabelle.values() for e in o})
    print(f"{len(tabelle)} Bezirke, davon {geteilt} unter 80 % in einem Ortsbereich")
    print(f"Ortsbereiche ohne Bezirk: {ohne or 'keine'}")
    print(f"  {UEBERLAPPUNG.relative_to(WURZEL)}")
    return 1 if ohne else 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    unter = p.add_subparsers(dest="befehl", required=True)
    h = unter.add_parser("hol", help="holen, vereinfachen, nach public/geo schreiben")
    h.add_argument("--roh", action="store_true", help="nicht vereinfachen")
    h.add_argument("--toleranz", type=float, default=TOLERANZ_M, help="Douglas-Peucker in Metern")
    h.set_defaults(fn=cmd_hol)
    pr = unter.add_parser("pruefe", help="was liegt da, und passt es zur Wahl?")
    pr.set_defaults(fn=cmd_pruefe)
    ue = unter.add_parser("ueberlappung", help="Anteile Wahlbezirk × Ortsbereich rechnen")
    ue.set_defaults(fn=cmd_ueberlappung)
    a = p.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
