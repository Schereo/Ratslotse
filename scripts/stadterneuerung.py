#!/usr/bin/env python3
"""Stadterneuerungsgebiete aus dem Geoportal der Stadt einlesen.

Holt die Ebene 34 („Bauen und Wohnen – Stadterneuerungsgebiete“) des GeoPortal-Dienstes,
rechnet je Gebiet den Anteil seiner Fläche in jedem Ortsbereich (Polygone aus
``web/frontend/public/geo/stadtteile-oldenburg.json``) und schreibt ``council/stadterneuerung.json``.
Höflich: ein Abruf, eigener User-Agent. Der Dienst sperrt Hetzner-Adressen — das Skript läuft auf
einem Entwicklungsrechner, das Ergebnis ist eingecheckt.

    python scripts/stadterneuerung.py            # holen und schreiben
    python scripts/stadterneuerung.py --pruefen  # Datei prüfen, ohne Netz
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from council import geo, places, stadterneuerung  # noqa: E402

LAYER = "https://gisportal4ol.oldenburg.de/server/rest/services/GeoPortal/GeoPortal/MapServer/34"
USER_AGENT = "Ratslotse (+https://ratslotse.de)"


def euro(text: str) -> int:
    """„22,5 Millionen Euro“ → 22500000 — genau so, wie die Stadt es schreibt."""
    m = re.fullmatch(r"\s*([\d.,]+)\s*Millionen\s+Euro\s*", text or "")
    if not m:
        raise SystemExit(f"Betrag nicht lesbar: {text!r}")
    return round(float(m.group(1).replace(".", "").replace(",", ".")) * 1_000_000)


def hectares(text: str) -> float:
    m = re.fullmatch(r"\s*([\d,]+)\s*ha\s*", text or "")
    if not m:
        raise SystemExit(f"Größe nicht lesbar: {text!r}")
    return float(m.group(1).replace(",", "."))


def districts(geometry: dict) -> dict[str, float]:
    """Anteil der Gebietsfläche je Ortsbereich, auf zwei Stellen."""
    from shapely.geometry import shape
    area = shape(geometry)
    out = {}
    for place in places.primary_places():
        poly = geo.ortsbereich_polygon(place.name)
        if not poly:
            continue
        share = area.intersection(shape(poly)).area / area.area
        if share >= 0.01:
            out[place.id] = round(share, 2)
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def fetch() -> list[dict]:
    import requests
    params = {"where": "1=1", "outFields": "*", "returnGeometry": "true", "outSR": "4326",
              "geometryPrecision": "5", "maxAllowableOffset": "0.00005", "f": "geojson"}
    r = requests.get(f"{LAYER}/query", params=params, headers={"User-Agent": USER_AGENT}, timeout=60)
    r.raise_for_status()
    out = []
    for f in r.json()["features"]:
        p = f["properties"]
        start, end = (int(x) for x in p["Zeitraum"].split("-"))
        out.append({"name": p["Name"], "start_year": start, "end_year": end, "size_ha": hectares(p["Groesse"]),
                    "funding_eur": euro(p["Foerdermittel"]), "own_funds_eur": euro(p["Eigenmittel_StOL"]),
                    "as_written": {"Zeitraum": p["Zeitraum"], "Groesse": p["Groesse"],
                                   "Foerdermittel": p["Foerdermittel"], "Eigenmittel_StOL": p["Eigenmittel_StOL"]},
                    "districts": districts(f["geometry"]), "geometry": f["geometry"]})
    return sorted(out, key=lambda a: a["name"])


def check(data: dict) -> list[str]:
    problems = []
    primary = {p.id for p in places.primary_places()}
    for a in data["areas"]:
        if not a["districts"] or not set(a["districts"]) <= primary:
            problems.append(f"{a['name']}: Ortsbereiche fehlen oder sind unbekannt")
        if not 0.95 <= sum(a["districts"].values()) <= 1.05:
            problems.append(f"{a['name']}: Anteile ergeben {sum(a['districts'].values()):.2f} statt 1")
        if a["start_year"] > a["end_year"]:
            problems.append(f"{a['name']}: Laufzeit verkehrt")
        if euro(a["as_written"]["Foerdermittel"]) != a["funding_eur"] or euro(a["as_written"]["Eigenmittel_StOL"]) != a["own_funds_eur"]:
            problems.append(f"{a['name']}: Betrag passt nicht zum Wortlaut")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--pruefen", action="store_true")
    args = ap.parse_args(argv)
    if args.pruefen:
        problems = check(stadterneuerung.data())
        print("\n".join(problems) or f"✓ {len(stadterneuerung.data()['areas'])} Gebiete passen")
        return 1 if problems else 0
    data = {"source": LAYER, "label": stadterneuerung.SOURCE_LABEL, "fetched": dt.date.today().isoformat(),
            "areas": fetch()}
    problems = check(data)
    if problems:
        print("\n".join(problems))
        return 1
    stadterneuerung.FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"geschrieben: {stadterneuerung.FILE.relative_to(WURZEL)} ({len(data['areas'])} Gebiete)")
    for a in data["areas"]:
        print(f"   {a['name']:35s} {a['start_year']}–{a['end_year']}  {a['districts']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
