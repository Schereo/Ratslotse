#!/usr/bin/env python3
"""Erstfüllung und Nachläufe für den Städte-Speicher.

**Bericht ist der Default**, nicht Ausführung (``scripts/CLAUDE.md``):

```bash
python scripts/cities_backfill.py                      # was fehlt je Stadt und Stufe
python scripts/cities_backfill.py --run                # alle aktiven Städte, alle Stufen
python scripts/cities_backfill.py --run --body osnabrueck --stage fetch --since 2025-09-01
python scripts/cities_backfill.py --run --parallel     # Ernte je Stadt als eigener Prozess
```

**Warum die Ernte in Prozesse und nicht in Threads geht.** Fünf Threads auf
einer SQLite-Datei haben im Probelauf einen Faden still sterben lassen
(``database is locked``, ohne Log-Zeile — das Schreiben des Fehlers scheiterte
an derselben Sperre). Jede Stadt erntet deshalb in ihre eigene Rohdatei; das
Zusammenführen läuft danach sequenziell mit genau einem Schreiber.
"""
from __future__ import annotations

import argparse
import logging
import multiprocessing as mp
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council.cities import default_paths  # noqa: E402
from council.cities import pipeline  # noqa: E402
from council.cities.registry import BODIES, BodySpec, active_bodies  # noqa: E402
from council.cities.store import CitiesStore  # noqa: E402


def _fetch_one(args: tuple) -> tuple[str, dict | str]:
    """Ein Prozess je Stadt — deshalb als Funktion auf Modulebene."""
    spec, raw_dir, files_dir, since, max_files = args
    try:
        return spec.id, pipeline.fetch(spec, raw_dir, files_dir, since, max_files=max_files)
    except Exception as e:  # noqa: BLE001 — eine Stadt darf den Lauf nicht kippen
        return spec.id, f"{type(e).__name__}: {e}"


def bericht(main: CitiesStore, specs: list[BodySpec]) -> None:
    print(f"{'Stadt':16} {'Dialekt':9} {'Papiere':>8} {'mit Text':>9} {'TOPs':>7} "
          f"{'mit Ergebnis':>13} {'zuletzt geholt':>17}")
    print("-" * 84)
    stand = {z["id"]: z for z in main.stats()}
    for spec in specs:
        z = stand.get(spec.id)
        if not z:
            print(f"{spec.name:16} {spec.dialect:9} {'—':>8} {'—':>9} {'—':>7} {'—':>13} "
                  f"{'noch nie':>17}")
            continue
        print(f"{z['name'][:15]:16} {spec.dialect:9} {z['papers']:8} {z['papers_with_text']:9} "
              f"{z['agenda_items']:7} {z['agenda_items_with_outcome']:13} "
              f"{(z['last_fetched'] or '')[:16]:>17}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run", action="store_true", help="wirklich ernten (sonst nur Bericht)")
    p.add_argument("--body", action="append", help="nur diese Stadt (mehrfach möglich)")
    p.add_argument("--stage", action="append", choices=("fetch", "normalize", "extract"),
                   help="nur diese Stufe (mehrfach möglich)")
    p.add_argument("--since", help="ab welchem Datum geerntet wird (Vorgabe: aus der Registry)")
    p.add_argument("--parallel", action="store_true",
                   help="Ernte je Stadt als eigener Prozess (verschiedene Hosts)")
    p.add_argument("--max-files", type=int, help="Deckel für PDF-Abrufe je Stadt")
    p.add_argument("--verbose", action="store_true")
    a = p.parse_args()

    logging.basicConfig(level=logging.INFO if a.verbose else logging.WARNING,
                        format="%(asctime)s %(name)s %(message)s")

    db, files_dir, raw_dir = default_paths()
    specs = [BODIES[b] for b in a.body] if a.body else active_bodies()
    stages = tuple(a.stage) if a.stage else ("fetch", "normalize", "extract")

    main_store = CitiesStore(db)
    try:
        if not a.run:
            bericht(main_store, specs)
            print(f"\nDatenbank: {db}\nDateien:   {files_dir}\nRohernte:  {raw_dir}")
            print("\n--run führt aus.")
            return 0

        t0 = time.time()
        ergebnisse: dict[str, dict] = {}

        if "fetch" in stages:
            auftraege = [(s, raw_dir, files_dir, a.since, a.max_files) for s in specs]
            if a.parallel and len(auftraege) > 1:
                with mp.Pool(min(len(auftraege), 5)) as pool:
                    for stadt, zahlen in pool.imap_unordered(_fetch_one, auftraege):
                        ergebnisse.setdefault(stadt, {})["fetch"] = zahlen
                        print(f"  {stadt}: {zahlen}", flush=True)
            else:
                for auftrag in auftraege:
                    stadt, zahlen = _fetch_one(auftrag)
                    ergebnisse.setdefault(stadt, {})["fetch"] = zahlen
                    print(f"  {stadt}: {zahlen}", flush=True)

        # Ab hier genau EIN Schreiber auf der Hauptdatenbank.
        # Eine Stadt, die stolpert, darf die übrigen nicht mitnehmen — sonst
        # kostet ein einzelner kaputter Endpunkt den ganzen Wochenlauf.
        for spec in specs:
            try:
                if "normalize" in stages:
                    zahlen = pipeline.normalize(spec, raw_dir, main_store)
                    ergebnisse.setdefault(spec.id, {})["normalize"] = zahlen
                    inline = pipeline.extract_inline(main_store, spec, raw_dir)
                    if inline:
                        ergebnisse[spec.id]["inline_texts"] = inline
                    print(f"  {spec.id} normalisiert: {zahlen}", flush=True)
                if "extract" in stages:
                    zahlen = pipeline.extract(main_store, files_dir, spec.id)
                    ergebnisse.setdefault(spec.id, {})["extract"] = zahlen
                    print(f"  {spec.id} Text: {zahlen}", flush=True)
            except Exception as e:  # noqa: BLE001
                ergebnisse.setdefault(spec.id, {})["fehler"] = f"{type(e).__name__}: {e}"
                print(f"  {spec.id} FEHLER: {type(e).__name__}: {e}", flush=True)

        print(f"\nFertig in {time.time() - t0:.0f}s.\n")
        bericht(main_store, specs)
        fehler = {s: z.get("fehler") or z.get("fetch") for s, z in ergebnisse.items()
                  if z.get("fehler") or isinstance(z.get("fetch"), str)}
        if fehler:
            print(f"\nFEHLER bei: {', '.join(fehler)}")
            for stadt, text in fehler.items():
                print(f"  {stadt}: {text}")
            return 1
        return 0
    finally:
        main_store.close()


if __name__ == "__main__":
    raise SystemExit(main())
