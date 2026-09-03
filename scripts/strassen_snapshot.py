#!/usr/bin/env python3
"""Alle benannten Wege Oldenburgs in EINEM Overpass-Aufruf holen — und den
Bestand daraus verorten.

**Warum es dieses Skript gibt.** Die Straßen-Geometrie kam bisher je Name
einzeln von Overpass (``geocode_entities.overpass_street``). Am 03.09.2026
gemessen: **overpass-api.de ist von beiden VPS aus gar nicht erreichbar**
(Errno 101, „Network is unreachable", über das NAT-Gateway; dev genauso wie
Prod), und die erreichbaren Spiegel antworten auf ``/api/interpreter`` nicht.
Der Rückfall auf Nominatim war stumm — ein Reparaturlauf über 513 Straßen
meldete ``located=513, missed=2, failed=0`` und hatte trotzdem nur **15** von
ihnen wirklich vollständig geholt. Alles andere trägt weiter ein einzelnes
Segment, und damit nur einen Teil der Ortsbereiche, durch die die Straße
läuft.

**Der Ausweg.** Ein einziger Overpass-Aufruf liefert alle benannten Wege im
Oldenburger Rechteck: 6.534 Wege, 1.950 verschiedene Namen, 5,9 MB, 6,9 s
(03.09.2026 gemessen). Diesen Schnappschuss holt eine Maschine MIT Zugang
(GitHub-Läufer, Notebook), der Server gleicht ihn nur noch lokal ab. Damit
braucht die Verortung überhaupt kein Overpass mehr — und die API bekommt
einen Aufruf statt fünfhundert.

::

    # auf einer Maschine mit Overpass-Zugang
    python scripts/strassen_snapshot.py holen --datei data/strassen-snapshot.json

    # auf dem Server (kein Netz nötig)
    python scripts/strassen_snapshot.py anwenden --datei data/strassen-snapshot.json
    python scripts/strassen_snapshot.py anwenden --datei … --trocken   # nur zählen

Der Abgleich ist **idempotent**: Wo die gebaute Geometrie der gespeicherten
gleicht, wird nicht geschrieben. Ein zweiter Lauf meldet deshalb lauter
„unverändert".
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Die Store-Importe stehen ABSICHTLICH in den Funktionen: `holen` läuft auf
# einer Maschine, die nur `requests` hat (dem GitHub-Läufer), und
# `council/__init__` zieht den ganzen Scraper samt BeautifulSoup herein.
COUNCIL_DB = ROOT / "data" / "council.sqlite"
SCHNAPPSCHUSS = ROOT / "data" / "strassen-snapshot.json"
OVERPASS = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "Ratslotse/1.0 (https://ratslotse.de; civic info, street geometry)"}
#: Dasselbe Rechteck wie im Einzel-Geocoder — größer als die Stadt, deshalb
#: wird jede Geometrie hinterher auf das Stadtgebiet beschnitten.
BBOX = (53.08, 8.10, 53.22, 8.30)

#: Wie viele benannte Wege der Schnappschuss mindestens enthalten muss.
#: Gemessen am 03.09.2026: 6.534. Deutlich weniger heißt, dass die Antwort
#: abgeschnitten oder aus dem falschen Ausschnitt kam — und ein zu kleiner
#: Schnappschuss darf gute Geometrien nicht überschreiben. Der Wert liegt
#: bewusst weit unter dem gemessenen: Er soll einen Ausfall fangen, nicht
#: jedes Auf und Ab in OSM.
MINDESTENS_WEGE = 3000


def holen(url: str = OVERPASS, timeout: int = 300) -> dict:
    """Alle benannten Wege im Rechteck — ein Aufruf, rohe Overpass-Antwort."""
    lat_min, lon_min, lat_max, lon_max = BBOX
    query = (f"[out:json][timeout:180];"
             f'way["highway"]["name"]({lat_min},{lon_min},{lat_max},{lon_max});'
             f"out geom;")
    start = time.time()
    antwort = requests.post(url, data={"data": query}, headers=HEADERS, timeout=timeout)
    antwort.raise_for_status()
    daten = antwort.json()
    wege = [e for e in daten.get("elements", []) if e.get("geometry")]
    print(f"Schnappschuss: {len(wege)} benannte Wege, "
          f"{round(len(antwort.content) / 1e6, 1)} MB, {round(time.time() - start, 1)} s",
          flush=True)
    if len(wege) < MINDESTENS_WEGE:
        # Lieber gar kein Schnappschuss als ein halber: Ein abgeschnittenes
        # Ergebnis (Overpass unter Last liefert das) sähe für den Abgleich aus
        # wie „diese Straßen gibt es nicht mehr".
        raise SystemExit(
            f"Nur {len(wege)} benannte Wege — erwartet sind über {MINDESTENS_WEGE} "
            f"(gemessen: 6.534). Die Antwort ist unvollständig oder kam aus dem "
            f"falschen Ausschnitt; nichts geschrieben.")
    return daten


def _nach_namen(daten: dict) -> dict[str, list[list[list[float]]]]:
    """Name (klein geschrieben) → alle Linien dieses Namens.

    Zusammengefasst wird über den **exakten** Namen, nur die Groß-/
    Kleinschreibung ist gleichgültig: „Sandweg" und „Am Sandweg" sind zwei
    Straßen, und ein unscharfer Abgleich hängte ihre Segmente aneinander.
    """
    nach_namen: dict[str, list[list[list[float]]]] = {}
    for element in daten.get("elements", []):
        name = ((element.get("tags") or {}).get("name") or "").strip()
        punkte = element.get("geometry") or []
        if not name or len(punkte) < 2:
            continue
        linie = [[p["lon"], p["lat"]] for p in punkte if "lon" in p and "lat" in p]
        if len(linie) >= 2:
            nach_namen.setdefault(name.casefold(), []).append(linie)
    return nach_namen


def _geometrie(linien: list[list[list[float]]]) -> tuple | None:
    """``(lat, lon, geojson)`` aus den Segmenten eines Namens — auf die Stadt
    beschnitten, Mittelpunkt aus dem beschnittenen Teil.

    Der Mittelpunkt MUSS aus dem beschnittenen Teil kommen: Bei einem Namen,
    den es auch in der Nachbargemeinde gibt, lag er sonst irgendwo dazwischen
    und damit in keinem Ortsbereich — dieselbe Falle wie beim „Alten Postweg".
    """
    from council import geo

    beschnitten = geo.auf_stadtgebiet_beschneiden(
        {"type": "MultiLineString", "coordinates": linien})
    if not beschnitten:
        return None
    punkte = geo._geometrie_punkte(beschnitten)
    if not punkte:
        return None
    lat = (min(p[0] for p in punkte) + max(p[0] for p in punkte)) / 2
    lon = (min(p[1] for p in punkte) + max(p[1] for p in punkte)) / 2
    return lat, lon, json.dumps(beschnitten, separators=(",", ":"))


def anwenden(council_db: Path, datei: Path, *, trocken: bool = False) -> dict:
    """Den Schnappschuss auf Orte und Entitäten anwenden.

    Geschrieben wird nur, wo die gebaute Geometrie eine ANDERE ist als die
    gespeicherte. Damit kostet ein zweiter Lauf nichts und die Kennzahlen
    sagen die Wahrheit: „unveraendert" heißt, dass der Bestand schon stimmte.
    """
    from council.store import CouncilStore

    daten = json.loads(datei.read_text(encoding="utf-8"))
    nach_namen = _nach_namen(daten)
    store = CouncilStore(council_db)
    stand = {"namen": len(nach_namen), "orte_offen": 0, "orte_neu": 0,
             "orte_unveraendert": 0, "orte_ohne_treffer": 0, "orte_ausserhalb": 0,
             "entitaeten_neu": 0}
    try:
        offen = store.street_locations_to_refine()
        stand["orte_offen"] = len(offen)
        for row in offen:
            ergebnis = _treffer(nach_namen, row["name"], stand, "orte")
            if not ergebnis:
                continue
            if ergebnis[2] == row["geojson"]:
                stand["orte_unveraendert"] += 1
                continue
            if not trocken:
                store.set_location_geo(row["slug"], *ergebnis)
            stand["orte_neu"] += 1
        # Entitäten, die dieselbe Straße SIND: Ihr Punkt ist der Rückfall der
        # Stadtteil-Zuordnung und der Pin auf der Stadtkarte.
        for ent in store.street_entities_to_refine():
            ergebnis = _treffer(nach_namen, ent["name"], stand, "entitaeten")
            if not ergebnis or ergebnis[2] == ent["geojson"]:
                continue
            if not trocken:
                store.set_entity_geo(ent["slug"], *ergebnis)
            stand["entitaeten_neu"] += 1
        if not trocken:
            # Erst jetzt neu ableiten: Die Zugehörigkeiten hängen an der
            # Geometrie, und die ist gerade erst vollständig geworden.
            stand["korrigiert"] = (store.fix_contradicting_districts()
                                   + store.fix_eponymous_districts())
            stand["zugehoerigkeiten"] = store.rebuild_location_districts()
    finally:
        store.close()
    return stand


def _treffer(nach_namen: dict, name: str | None, stand: dict, was: str) -> tuple | None:
    """Die Geometrie zu einem Namen — oder None, samt Grund in ``stand``."""
    linien = nach_namen.get((name or "").strip().casefold())
    if not linien:
        stand[f"{was}_ohne_treffer"] = stand.get(f"{was}_ohne_treffer", 0) + 1
        return None
    ergebnis = _geometrie(linien)
    if not ergebnis:
        # Den Namen gibt es, er liegt aber ganz außerhalb Oldenburgs. Dann ist
        # das Vorhandene nicht schlechter — nichts anfassen.
        stand[f"{was}_ausserhalb"] = stand.get(f"{was}_ausserhalb", 0) + 1
        return None
    return ergebnis


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    unter = ap.add_subparsers(dest="befehl", required=True)

    hol = unter.add_parser("holen", help="Schnappschuss von Overpass holen")
    hol.add_argument("--datei", type=Path, default=SCHNAPPSCHUSS)
    hol.add_argument("--url", default=OVERPASS)

    anw = unter.add_parser("anwenden", help="Schnappschuss auf die Datenbank anwenden")
    anw.add_argument("--datei", type=Path, default=SCHNAPPSCHUSS)
    anw.add_argument("--db", type=Path, default=COUNCIL_DB)
    anw.add_argument("--trocken", action="store_true", help="nur zählen, nichts schreiben")

    args = ap.parse_args()
    if args.befehl == "holen":
        daten = holen(args.url)
        args.datei.parent.mkdir(parents=True, exist_ok=True)
        args.datei.write_text(json.dumps(daten, separators=(",", ":")), encoding="utf-8")
        print(f"geschrieben: {args.datei} "
              f"({round(args.datei.stat().st_size / 1e6, 1)} MB)")
        return 0
    stand = anwenden(args.db, args.datei, trocken=args.trocken)
    print(("TROCKEN: " if args.trocken else "")
          + "Straßen-Schnappschuss: "
          + ", ".join(f"{k}={v}" for k, v in stand.items()))
    # Ein Lauf, der auf 687 offene Orte keinen einzigen Treffer hat, hat nicht
    # „nichts zu tun" — er hat die falsche Datei gelesen. Das muss der
    # Rückgabewert sagen, sonst steht der Workflow grün und niemand sieht es.
    if stand["orte_offen"] and not (stand["orte_neu"] + stand["orte_unveraendert"]):
        print(f"FEHLER: {stand['orte_offen']} Straßen offen, aber KEIN Namenstreffer "
              f"im Schnappschuss ({stand['namen']} Namen). Falsche oder leere Datei?",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
