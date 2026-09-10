#!/usr/bin/env python3
"""Erstfüllung und Nachläufe für den Städte-Speicher.

**Bericht ist der Default**, nicht Ausführung (``scripts/CLAUDE.md``):

```bash
python scripts/cities_backfill.py                      # was fehlt je Stadt und Stufe
python scripts/cities_backfill.py --run                # alle aktiven Städte, alle Stufen
python scripts/cities_backfill.py --run --body osnabrueck --stage fetch --since 2025-09-01
python scripts/cities_backfill.py --run --parallel     # Ernte je Stadt als eigener Prozess
python scripts/cities_backfill.py --run --stage annotate --stage index   # Rückstand aufholen
```

**`annotate` und `index` stehen NICHT in der Vorgabe.** Die Ernte ist
wiederholbar und kostet Abrufe; das Einordnen kostet Geld (0,26 $ je 1.000
Vorlagen) und das Indizieren Stunden CPU. Beide laufen sonst im Wochen-Cron
mit Deckel — der reicht für den laufenden Betrieb und nie für einen
Backfill der Historie. Genau daran ist der Bestand am 08.09.2026 auf 19 %
Einordnung stehen geblieben.

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
from council.cities import pruefung  # noqa: E402
from council.cities.index import EMBED_MODEL  # noqa: E402
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
    """Was da ist — und was fehlt.

    ``Protokolle`` ist „mit Text / vorhanden": Die Niederschrift je Sitzung
    ist das Einzige, worin steht, WARUM ein Rat so entschieden hat. Steht dort
    ``0/606``, nennt die Stadt Adressen, die sie nicht ausliefert (Magdeburg).

    Die beiden mittleren Rückstands-Spalten sind der Rückstand: Ein Papier ohne Einordnung
    ist für den Vergleich unsichtbar, eines ohne Vektor hat keine Nachbarn.
    Sie stehen hier, weil sie sonst nirgends stehen — und weil ein Backfill
    der Historie sie um eine Größenordnung wachsen lässt, ohne dass der
    Wochen-Cron das je aufholt.
    """
    print(f"{'Stadt':15} {'Dialekt':9} {'Papiere':>8} {'m. Text':>8} {'m. Ergebnis':>12} "
          f"{'o. Einordn.':>12} {'o. Vektor':>10} {'Protokolle':>13} {'zuletzt geholt':>17}")
    print("-" * 112)
    stand = {z["id"]: z for z in main.stats(EMBED_MODEL)}
    for spec in specs:
        z = stand.get(spec.id)
        if not z:
            print(f"{spec.name[:14]:15} {spec.dialect:9} {'—':>8} {'—':>8} {'—':>12} "
                  f"{'—':>12} {'—':>10} {'—':>13} {'noch nie':>17}")
            continue
        protokolle = f"{z['protocols_with_text']}/{z['protocols']}" if z["protocols"] else "—"
        print(f"{z['name'][:14]:15} {spec.dialect:9} {z['papers']:8} {z['papers_with_text']:8} "
              f"{z['papers_with_outcome']:12} {z['papers_unclassified']:12} "
              f"{z['papers_unembedded']:10} {protokolle:>13} "
              f"{(z['last_fetched'] or '')[:16]:>17}")


def pruefbericht(main: CitiesStore, specs: list[BodySpec]) -> int:
    """Plausibilität je Stadt — der Wächter für stumme Ernte-Fehler.

    Am 08.09.2026 lagen vier Fehler gleichzeitig im Bestand, und keiner hat
    sich gemeldet (``council/cities/pruefung.py`` zählt sie auf). Wer eine
    neue Stadt anschließt, ruft das hier, bevor er ihre Daten benutzt.
    """
    befunde = pruefung.pruefe(main, EMBED_MODEL)
    gewaehlt = {s.id for s in specs}
    befunde = [b for b in befunde if b.body_id in gewaehlt]
    if befunde:
        print(f"{len(befunde)} Befund(e):\n")
        for b in befunde:
            print(f"  ⚠ {b}")
    else:
        print("Keine Befunde — alle geprüften Städte liegen in ihren Bändern.")

    print("\nErgebnistexte, die die Zuordnung NICHT kennt (häufigste zuerst).")
    print("Was hier oft vorkommt, gehört vermutlich in `council.cities.model.outcome`:")
    for spec in specs:
        unbekannt = pruefung.unbekanntes_vokabular(main, spec.id, limit=5)
        if not unbekannt:
            continue
        print(f"\n  {spec.name}:")
        for text, n in unbekannt:
            print(f"    {n:6}  {text[:78]}")
    return 1 if befunde else 0


def unterbau_pruefen(main: CitiesStore) -> list[str]:
    """Was vor der Stufe `fit` wahr sein muss — sonst urteilt das Modell blind.

    **Der teuerste Fehler dieses Projekts steht hinter dieser Funktion.** Am
    09.09.2026 lief `fit` über 9.688 Vorlagen, während 21.700 fremde Vorlagen
    keinen Vektor hatten und die Cluster-Schicht 16 % der Ideen kannte. Zwei
    der fünf Beleg-Arme waren damit leer; das Modell urteilte „fehlt", weil
    ihm nichts vorlag. 72 Minuten, $15,40, Ergebnis unbrauchbar — und kein
    Absturz, kein roter Test, keine auffällige Kennzahl.

    Der Wochen-Cron (`scripts/check_cities.py`) macht es richtig, weil er die
    Stufen fest in der Reihenfolge ruft. Wer hier `--stage` benutzt, hatte
    bis heute keine Sicherung. Die Reihenfolge ist:

        classify  →  index  →  cluster  →  fit
    """
    befunde = []
    luecken = main.substrate_gaps(EMBED_MODEL)
    if luecken["papers_unembedded"]:
        befunde.append(
            f"{luecken['papers_unembedded']} Vorlagen ohne Vektor "
            f"(davon {luecken['oldenburg_unembedded']} Oldenburger) — "
            "ohne sie ist der Nachbar-Arm leer. Erst: --stage index")
    if luecken["ideas_unembedded"]:
        befunde.append(
            f"{luecken['ideas_unembedded']} übertragbare Vorlagen ohne "
            "Ideen-Vektor — sie können in keiner Gruppe liegen, der "
            "Cluster-Arm ist für sie leer. Erst: --stage cluster")
    return befunde


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run", action="store_true", help="wirklich ernten (sonst nur Bericht)")
    p.add_argument("--body", action="append", help="nur diese Stadt (mehrfach möglich)")
    p.add_argument("--stage", action="append",
                   choices=("fetch", "normalize", "extract", "annotate", "index",
                            "cluster", "fit"),
                   help="nur diese Stufe (mehrfach möglich). `annotate`, `index`, "
                        "`cluster` und `fit` sind NICHT in der Vorgabe: Sie kosten "
                        "Geld bzw. Stunden CPU und laufen sonst im Wochen-Cron mit "
                        "Deckel. `fit` prüft vorher den Unterbau (s. "
                        "`unterbau_pruefen`).")
    p.add_argument("--annotate-max", type=int, default=None,
                   help="Deckel für die Stufe `annotate` (Vorgabe: keiner — das ist "
                        "der Backfill; der Cron deckelt bei CITIES_ANNOTATE_MAX)")
    p.add_argument("--since", help="ab welchem Datum geerntet wird (Vorgabe: aus der Registry)")
    p.add_argument("--parallel", action="store_true",
                   help="Ernte je Stadt als eigener Prozess (verschiedene Hosts)")
    p.add_argument("--max-files", type=int, help="Deckel für PDF-Abrufe je Stadt")
    p.add_argument("--pruefen", action="store_true",
                   help="Plausibilität je Stadt prüfen und das unbekannte "
                        "Ergebnis-Vokabular zeigen (für neue Städte)")
    p.add_argument("--trotzdem", action="store_true",
                   help="`fit` auch starten, wenn der Unterbau Lücken hat. Der "
                        "Grund gehört ins Log — ein Lauf mit totem Beleg-Arm "
                        "kostet Geld und liefert Urteile, die niemand benutzen kann.")
    p.add_argument("--verbose", action="store_true")
    a = p.parse_args()

    logging.basicConfig(level=logging.INFO if a.verbose else logging.WARNING,
                        format="%(asctime)s %(name)s %(message)s")

    db, files_dir, raw_dir = default_paths()
    specs = [BODIES[b] for b in a.body] if a.body else active_bodies()
    stages = tuple(a.stage) if a.stage else ("fetch", "normalize", "extract")

    main_store = CitiesStore(db)
    try:
        if a.pruefen:
            return pruefbericht(main_store, specs)
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

        # Einordnung und Index laufen über ALLE gewählten Städte zusammen, nicht
        # je Stadt: Der Index rechnet Nachbarschaften über Stadtgrenzen, und
        # eine Einordnung je Stadt würde die Batches unnötig zerschneiden.
        # `--body` wirkt auch hier: Wer eine Stadt nachzieht, will nicht den
        # ganzen Bestand neu bezahlen. Ohne `--body` läuft beides über alles,
        # denn der Index rechnet Nachbarschaften ÜBER Stadtgrenzen.
        auswahl = [s.id for s in specs] if a.body else [None]
        if "annotate" in stages:
            for stadt in auswahl:
                for schluessel, zahlen in pipeline.annotate(
                        main_store, body_id=stadt, limit=a.annotate_max).items():
                    ergebnisse.setdefault(stadt or "(alle)", {})[schluessel] = zahlen
                    print(f"  {stadt or 'alle'} {schluessel}: {zahlen}", flush=True)
        if "index" in stages:
            zahlen = pipeline.index_all(main_store)
            ergebnisse.setdefault("(alle)", {})["index"] = zahlen
            print(f"  Index: {zahlen}", flush=True)
        if "cluster" in stages:
            zahlen = pipeline.cluster_all(main_store)
            ergebnisse.setdefault("(alle)", {})["cluster"] = zahlen
            print(f"  Cluster: {zahlen}", flush=True)
        if "fit" in stages:
            befunde = unterbau_pruefen(main_store)
            if befunde and not a.trotzdem:
                print("\nDer Unterbau ist unvollständig — `fit` würde mit toten "
                      "Beleg-Armen urteilen:", file=sys.stderr)
                for b in befunde:
                    print(f"  ⚠ {b}", file=sys.stderr)
                print("\n--trotzdem überstimmt das.", file=sys.stderr)
                return 1
            if befunde:
                print(f"  Unterbau unvollständig, --trotzdem: {'; '.join(befunde)}",
                      flush=True)
            for stadt in auswahl:
                for schluessel, zahlen in pipeline.annotate(
                        main_store, body_id=stadt, nach_index=True).items():
                    ergebnisse.setdefault(stadt or "(alle)", {})[schluessel] = zahlen
                    print(f"  {stadt or 'alle'} {schluessel}: {zahlen}", flush=True)

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
