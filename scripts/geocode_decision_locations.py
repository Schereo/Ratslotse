#!/usr/bin/env python3
"""Neue Beschluss-Orte geokodieren und daraus den Ortsbereich ableiten.

Bereits vorhandene Entitäts-Geocodes werden zuerst kostenlos übernommen. Für
Ratslotse-Ortsbereiche nutzen wir die lokalen Polygone; nur übrige Orte gehen mit
höchstens einem Request pro Sekunde an Nominatim/Overpass.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import geo, places  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from kern.alerts import notify_admin  # noqa: E402
from scripts.geocode_entities import geocode, overpass_ausfaelle  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"


def process(council_db: Path, *, limit: int | None = None, sleep: float = 1.1,
            erneut: bool = False, strassen_neu: bool = False) -> dict:
    store = CouncilStore(council_db)
    curated = store.apply_curated_location_geocodes()
    reused = store.hydrate_location_geo_from_entities()
    districts = store.backfill_location_districts()
    # Der Rest, den kein Geocoder je findet: Orte, die ihren Stadtteil im
    # eigenen Namen tragen („GS Drielake", „Bürgerhaus Ofenerdiek").
    aus_namen = store.backfill_location_districts_from_name()
    catalog_links = store.backfill_location_place_ids()
    rows = store.locations_to_geocode(limit=limit, retry_failed=erneut)
    nachzuholen: set[str] = set()
    if strassen_neu:
        # Bestands-Reparatur: Straßen, von denen nur ein Nominatim-Segment
        # gespeichert ist, noch einmal ganz holen. Sie haben Koordinaten, sind
        # also für die normale Warteschlange „erledigt" — genau deshalb braucht
        # es den eigenen Schalter.
        bekannt = {r["slug"] for r in rows}
        nachgeholt = [r for r in store.street_locations_to_refine(limit=limit)
                      if r["slug"] not in bekannt]
        nachzuholen = {r["slug"] for r in nachgeholt}
        print(f"Straßen neu zu holen: {len(nachgeholt)}", flush=True)
        rows = rows + nachgeholt
    print(f"Orts-Geocoding: reused={reused}, pending={len(rows)}", flush=True)
    located = missed = failed = 0
    for index, row in enumerate(rows, start=1):
        local = False
        try:
            catalog_place = places.resolve(row["name"])
            if catalog_place and catalog_place.lat is not None and catalog_place.lon is not None:
                result = (catalog_place.lat, catalog_place.lon, None)
                local = True
            elif row["kind"] == "district" and geo.ortsbereich_center(row["name"]):
                lat, lon = geo.ortsbereich_center(row["name"])
                shape = geo.ortsbereich_polygon(row["name"])
                result = (lat, lon, json.dumps(shape, separators=(",", ":")))
                local = True
            else:
                # Die Ortsart mitgeben: Was als Straße erkannt wurde, wird bei
                # Overpass ganz geholt — sonst bliebe es bei dem einen Segment,
                # das Nominatim zurückgibt, und die halbe Straße samt ihren
                # Ortsbereichen fehlte.
                result = geocode(row["name"], row["kind"])
        except Exception as exc:  # noqa: BLE001 — Netzwerkfehler beim nächsten Lauf erneut versuchen
            failed += 1
            print(f"! {row['name']}: {exc!r}", flush=True)
            continue
        if result:
            store.set_location_geo(row["slug"], result[0], result[1], result[2])
            located += 1
        elif row["slug"] in nachzuholen:
            # Eine Reparatur, die nichts findet, darf das Vorhandene nicht
            # löschen: Ein Segment ist weniger als die ganze Straße, aber viel
            # mehr als keine Geometrie.
            missed += 1
        else:
            store.set_location_geo(row["slug"], None, None, None)
            missed += 1
        if sleep and not local:
            time.sleep(sleep)
        if index % 20 == 0 or index == len(rows):
            print(
                f"Fortschritt: {index}/{len(rows)}, located={located}, "
                f"missed={missed}, failed={failed}",
                flush=True,
            )
    # Nach dem Geocoden noch einmal ableiten: Was gerade Koordinaten bekommen
    # hat, hat noch keinen Stadtteil — und ohne diesen zweiten Durchgang wären
    # die frisch geocodierten Straßen sofort wieder Waisen.
    store.merge_location_variants()
    districts += store.backfill_location_districts()
    korrigiert = (store.fix_contradicting_districts()
                  + store.fix_eponymous_districts()
                  + store.clear_code_only_districts())
    store.rebuild_location_districts()
    offen_danach = len(store.street_locations_to_refine())
    _melde_overpass_ausfall(offen_danach)
    store.close()
    return {"curated": curated, "reused": reused, "districts": districts,
            "districts_from_name": aus_namen, "korrigiert": korrigiert,
            "catalog_links": catalog_links,
            "pending": len(rows), "located": located,
            "missed": missed, "failed": failed,
            # Gehört in die Kennzahlen, nicht ins Log: „located=513" bei 498
            # Overpass-Ausfällen heißt, dass fast jede Straße nur ihr
            # Nominatim-Einzelsegment bekam (s. geocode_entities.geocode).
            "overpass_fehler": overpass_ausfaelle["fehler"],
            "overpass_ohne_treffer": overpass_ausfaelle["ohne_treffer"],
            "overpass_nicht_erreichbar": overpass_ausfaelle["nicht_erreichbar"],
            # Der Gesundheitswert des Bestands: Straßen, von denen weiter nur
            # ein Teilstück gespeichert ist. Er gehört in die Kennzahlen, weil
            # er nicht von selbst sinkt — steigt oder klebt er, hat der
            # Straßen-Weg ein Problem, ohne dass ein Lauf scheitert.
            "strassen_ohne_vollgeometrie": offen_danach}


def _melde_overpass_ausfall(offen: int) -> None:
    """Einen ausgefallenen Straßen-Dienst melden — nicht nur loggen.

    **Der Fall, gegen den das steht.** Am 03.09.2026 lief der Reparaturlauf
    über 513 Straßen und meldete ``located=513, missed=2, failed=0``. Overpass
    war von beiden VPS aus nicht erreichbar, der Rückfall auf Nominatim stumm,
    und 498 Straßen bekamen ein Einzelsegment statt der ganzen Straße. Ein
    Lauf, der das nicht sagt, ist ein Lauf, der lügt.

    Gemeldet wird nur, wenn es wirklich Straßen zu holen GAB und **alle**
    scheiterten. Damit kommt die Mail an dem Tag, an dem etwas verdorben wurde,
    und nicht jeden Tag, an dem gar keine neue Straße dazukam.
    """
    versucht = overpass_ausfaelle["strassen_versucht"]
    verloren = overpass_ausfaelle["nicht_erreichbar"] + overpass_ausfaelle["fehler"]
    if not versucht or verloren < versucht:
        return
    notify_admin(
        f"<b>Overpass nicht erreichbar</b> — {verloren} von {versucht} Straßen "
        f"haben in diesem Lauf nur ein <i>einzelnes</i> Nominatim-Segment "
        f"bekommen statt der ganzen Straße. Sie kennen damit nur einen Teil "
        f"der Ortsbereiche, durch die sie führen; im Einrichtungs-Assistenten "
        f"landen sie unter „direkt nebenan\", obwohl sie durch den eigenen "
        f"Stadtteil laufen.<br><br>"
        f"Aktuell {offen} Straßen ohne vollständige Geometrie. Reparatur: "
        f"Workflow <code>Ops: Straßen vollständig nachtragen</code> "
        f"(<code>scripts/strassen_snapshot.py</code>) — der holt den ganzen "
        f"Bestand in einem Aufruf von einer Maschine mit Zugang.",
        betreff="Ratslotse – Straßen-Geokodierung eingeschränkt",
        fusszeile="Hinweis eines Cron-Jobs — der Lauf selbst ist nicht "
                  "gescheitert, sein Ergebnis aber unvollständig.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--erneut", action="store_true",
                    help="auch Orte erneut versuchen, bei denen das Geocoding schon "
                         "einmal misslungen ist (Overpass/Nominatim antworten nicht "
                         "jeden Tag gleich)")
    ap.add_argument("--strassen-neu", action="store_true",
                    help="Straßen, von denen nur ein einzelnes Segment gespeichert "
                         "ist, noch einmal vollständig holen (Bestands-Reparatur)")
    ap.add_argument("--sleep", type=float, default=1.1)
    args = ap.parse_args()
    stats = process(args.db, limit=args.limit, sleep=args.sleep, erneut=args.erneut,
                    strassen_neu=args.strassen_neu)
    print("Orts-Geocoding: " + ", ".join(f"{key}={value}" for key, value in stats.items()))
    return 1 if stats["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
