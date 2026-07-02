#!/usr/bin/env python3
"""Backfill Vorlagen full texts (Sachverhalt/Begründung) for all agenda items.

Every agenda item that links a Vorlage (kvonr) gets its vo0050 metadata and the
"Vorlage" PDF text ingested into ``council_vorlagen``. Pure network + pypdf — no
LLM, no cost. Idempotent: already-ingested kvonrs are skipped, 'failed' rows are
retried. Newest sessions first, so a --limit run always covers current business
(that is also how the daily cron uses this module).

Usage::

    python scripts/backfill_vorlagen.py                 # everything missing
    python scripts/backfill_vorlagen.py --limit 300     # newest 300 only
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


def _fetch_one(kvonr: int) -> dict:
    """Network work for one Vorlage — runs in a worker thread, no DB access."""
    try:
        row = vorlagen.fetch_vorlage(kvonr)
        if row is None:
            return {"status": "invalid", "kvonr": kvonr}
        return {"status": "row", "kvonr": kvonr, "row": row}
    except Exception as exc:  # noqa: BLE001 — surface per-doc failures, keep going
        return {"status": "failed", "kvonr": kvonr, "error": repr(exc)}


def process_missing(council_db: Path, limit: int | None = None, workers: int = 6) -> dict:
    """Fetch + store every missing Vorlage. Returns counters for the caller's log."""
    store = CouncilStore(council_db)
    kvonrs = store.missing_vorlage_kvonrs(limit)
    print(f"{len(kvonrs)} Vorlage(n) to fetch with up to {workers} workers.", flush=True)

    fetched = no_pdf = failed = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_fetch_one, k): k for k in kvonrs}
        for i, fut in enumerate(as_completed(futures), 1):
            r = fut.result()
            if r["status"] == "failed":
                store.mark_vorlage_failed(r["kvonr"])
                failed += 1
                print(f"  [{i}/{len(kvonrs)}] kvonr={r['kvonr']} FAILED: {r['error']}", flush=True)
                continue
            if r["status"] == "invalid":
                # Page without Vorlage content (withdrawn/private) — record as
                # no_pdf so it is not refetched every run.
                store.save_vorlage({"kvonr": r["kvonr"], "status": "no_pdf"})
                no_pdf += 1
                continue
            row = r["row"]
            store.save_vorlage(row)
            if row["status"] == "ok":
                fetched += 1
            else:
                no_pdf += 1
            if i % 25 == 0 or i == len(kvonrs):
                print(f"  [{i}/{len(kvonrs)}] … {fetched} mit Text, {no_pdf} ohne, {failed} Fehler", flush=True)

    store.close()
    return {"total": len(kvonrs), "fetched": fetched, "no_pdf": no_pdf, "failed": failed}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    stats = process_missing(args.db, args.limit, args.workers)
    print(f"\n=== done: {stats['fetched']} ingested, {stats['no_pdf']} without PDF/text, "
          f"{stats['failed']} failed ===")
    return 1 if stats["failed"] and not stats["fetched"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
