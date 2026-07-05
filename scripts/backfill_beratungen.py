#!/usr/bin/env python3
"""Backfill/refresh der Beratungsfolge (vo0053) für eingelesene Vorlagen.

Je Vorlage werden alle offiziellen Beratungsstationen gespeichert: Datum,
Gremium, TOP, öffentlich/nichtöffentlich, Ergebnis und die verlinkte Sitzung —
inklusive erst geplanter künftiger Beratungen. Reines Netz-Parsing, kein LLM.

Zwei Läufe, beide idempotent (je kvonr wird komplett ersetzt):
- catch-up: Vorlagen, deren Beratungsfolge noch nie geholt wurde (historischer
  Bestand nach Feature-Start; neue Vorlagen deckt der tägliche Cron ab)
- rescan:  Vorlagen in Bewegung — auf aktuellen Tagesordnungen, mit geplanten
  Stationen oder noch ohne Ergebnis; dort werden Ergebnisse nachgetragen

Usage::

    python scripts/backfill_beratungen.py                 # catch-up alles Fehlende
    python scripts/backfill_beratungen.py --rescan
"""
from __future__ import annotations

import argparse
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import stammdaten  # noqa: E402
from council.scraper import CouncilScraper  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"
_tls = threading.local()


def _scraper(delay: float) -> CouncilScraper:
    # requests.Session ist nicht threadsicher — eine Session je Worker-Thread.
    if getattr(_tls, "scraper", None) is None:
        _tls.scraper = CouncilScraper(delay=delay)
    return _tls.scraper


def _fetch_one(kvonr: int, delay: float) -> dict:
    try:
        rows = stammdaten.fetch_beratungsfolge(_scraper(delay), kvonr)
        return {"status": "ok", "kvonr": kvonr, "rows": rows}
    except Exception as exc:  # noqa: BLE001 — Einzelfehler ausweisen, weiterlaufen
        return {"status": "failed", "kvonr": kvonr, "error": repr(exc)}


def _run(store: CouncilStore, kvonrs: list[int], workers: int, delay: float) -> dict:
    done = stationen = geplant = failed = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_fetch_one, k, delay): k for k in kvonrs}
        for i, fut in enumerate(as_completed(futures), 1):
            r = fut.result()
            if r["status"] == "failed":
                failed += 1
                print(f"  [{i}/{len(kvonrs)}] kvonr={r['kvonr']} FAILED: {r['error']}", flush=True)
                continue
            store.save_beratungen(r["kvonr"], r["rows"])
            done += 1
            stationen += len(r["rows"])
            geplant += sum(1 for b in r["rows"] if stammdaten.is_future(b.get("datum")))
            if i % 200 == 0 or i == len(kvonrs):
                print(f"  [{i}/{len(kvonrs)}] … {stationen} Stationen ({geplant} geplant)", flush=True)
    return {"vorlagen": done, "stationen": stationen, "geplant": geplant, "failed": failed}


def process_missing(council_db: Path, limit: int | None = None,
                    workers: int = 4, delay: float = 0.25) -> dict:
    """Catch-up: Vorlagen ohne gespeicherte Beratungsfolge, neueste zuerst."""
    store = CouncilStore(council_db)
    kvonrs = store.kvonrs_without_beratungen(limit)
    print(f"{len(kvonrs)} Vorlage(n) ohne Beratungsfolge.", flush=True)
    stats = _run(store, kvonrs, workers, delay)
    store.close()
    return stats


def rescan_recent(council_db: Path, days_back: int = 45,
                  workers: int = 4, delay: float = 0.25) -> dict:
    """Bewegliche Vorlagen aktualisieren (neue Stationen, nachgetragene Ergebnisse)."""
    store = CouncilStore(council_db)
    kvonrs = store.kvonrs_for_beratungen_rescan(days_back)
    print(f"{len(kvonrs)} Vorlage(n) für den Beratungsfolge-Rescan.", flush=True)
    stats = _run(store, kvonrs, workers, delay)
    store.close()
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--delay", type=float, default=0.25)
    ap.add_argument("--rescan", action="store_true",
                    help="statt Catch-up: bewegliche Vorlagen aktualisieren")
    args = ap.parse_args()

    if args.rescan:
        stats = rescan_recent(args.db, workers=args.workers, delay=args.delay)
    else:
        stats = process_missing(args.db, args.limit, args.workers, args.delay)
    print(f"\n=== done: {stats['vorlagen']} Vorlagen, {stats['stationen']} Stationen "
          f"({stats['geplant']} geplant), {stats['failed']} Fehler ===")
    return 1 if stats["failed"] and not stats["vorlagen"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
