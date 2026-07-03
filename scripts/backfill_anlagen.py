#!/usr/bin/env python3
"""Backfill/refresh Anlagen (attachments) for ingested Vorlagen.

Every Anlage is recorded with label + link; motion-like Anlagen (Fraktions-
Anträge, Änderungsanträge, Anfragen) additionally get their PDF text and the
recognised Antragsteller parties. Pure network + pypdf — no LLM, no cost.

Two passes, both idempotent:
- catch-up: Vorlagen never scanned for Anlagen (historical bulk after the
  feature landed; new Vorlagen are covered inline by backfill_vorlagen)
- rescan:  Vorlagen on recent/upcoming agendas — Änderungsanträge often appear
  on the page days after the Vorlage itself; known documents are not refetched

Usage::

    python scripts/backfill_anlagen.py                 # catch-up alles Fehlende
    python scripts/backfill_anlagen.py --rescan-days 45
"""
from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import vorlagen  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"


def _fetch_one(kvonr: int, known_ids: frozenset) -> dict:
    """Network work for one Vorlage page — runs in a worker thread, no DB access."""
    try:
        rows = vorlagen.fetch_anlagen(kvonr, known_ids)
        return {"status": "ok", "kvonr": kvonr, "rows": rows or []}
    except Exception as exc:  # noqa: BLE001 — surface per-page failures, keep going
        return {"status": "failed", "kvonr": kvonr, "error": repr(exc)}


def _run(store: CouncilStore, jobs: list[tuple[int, frozenset]], workers: int) -> dict:
    scanned = new_docs = antraege = failed = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_fetch_one, k, known): k for k, known in jobs}
        for i, fut in enumerate(as_completed(futures), 1):
            r = fut.result()
            if r["status"] == "failed":
                failed += 1
                print(f"  [{i}/{len(jobs)}] kvonr={r['kvonr']} FAILED: {r['error']}", flush=True)
                continue
            store.save_anlagen(r["kvonr"], r["rows"])
            scanned += 1
            new_docs += len(r["rows"])
            antraege += sum(1 for x in r["rows"] if x.get("is_antrag"))
            if i % 100 == 0 or i == len(jobs):
                print(f"  [{i}/{len(jobs)}] … {new_docs} Anlagen, davon {antraege} Anträge", flush=True)
    return {"scanned": scanned, "anlagen": new_docs, "antraege": antraege, "failed": failed}


def process_missing(council_db: Path, limit: int | None = None, workers: int = 6) -> dict:
    """Catch-up: scan Vorlagen whose page was never checked for Anlagen."""
    store = CouncilStore(council_db)
    kvonrs = store.kvonrs_without_anlagen_scan(limit)
    print(f"{len(kvonrs)} Vorlage(n) ohne Anlagen-Scan.", flush=True)
    stats = _run(store, [(k, frozenset()) for k in kvonrs], workers)
    store.close()
    return stats


def rescan_recent(council_db: Path, days_back: int = 45, workers: int = 6) -> dict:
    """Re-scan recent/upcoming Vorlagen for late-arriving Anlagen."""
    store = CouncilStore(council_db)
    jobs = [(j["kvonr"], frozenset(j["known_ids"])) for j in store.kvonrs_for_anlagen_rescan(days_back)]
    print(f"{len(jobs)} aktuelle Vorlage(n) für den Anlagen-Rescan.", flush=True)
    stats = _run(store, jobs, workers)
    store.close()
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--rescan-days", type=int, default=None,
                    help="statt Catch-up: aktuelle Vorlagen der letzten N Tage neu scannen")
    args = ap.parse_args()

    if args.rescan_days:
        stats = rescan_recent(args.db, args.rescan_days, args.workers)
    else:
        stats = process_missing(args.db, args.limit, args.workers)
    print(f"\n=== done: {stats['scanned']} Seiten, {stats['anlagen']} neue Anlagen "
          f"({stats['antraege']} Anträge), {stats['failed']} Fehler ===")
    return 1 if stats["failed"] and not stats["scanned"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
