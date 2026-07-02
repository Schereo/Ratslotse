#!/usr/bin/env python3
"""Classify council decisions/reports into policy fields (Themenfelder).

Pulls decisions that have no policy field yet, classifies them in batches via the
LLM (one call per batch -> field + tags + one-line summary) and writes the result
back. The LLM calls run in a thread pool (``--workers``); all DB writes happen on
the main thread (SQLite isn't shared across threads). Idempotent — a re-run only
touches still-unclassified rows, so it doubles as the daily catch-up cron.

Usage::

    python scripts/classify_decisions.py                      # all unclassified
    python scripts/classify_decisions.py --workers 12 --batch-size 20
    python scripts/classify_decisions.py --limit 40           # smoke test
    python scripts/classify_decisions.py --force              # re-classify everything
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

from council import topics  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"
PRICE_IN, PRICE_OUT = 0.435, 0.87  # deepseek-v4-pro $/1M, for the printout


def _chunk(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _classify_chunk(batch: list[dict]) -> dict:
    """LLM work for one batch — runs in a worker thread, no DB access."""
    try:
        results, usage = topics.classify_batch(batch)
        return {"status": "ok", "results": results, "usage": usage}
    except Exception as exc:  # noqa: BLE001 — surface per-batch failures, keep going
        return {"status": "failed", "ids": [d["id"] for d in batch], "error": repr(exc)}


def process(council_db: Path, batch_size: int = 15, workers: int = 8,
            limit: int | None = None, force: bool = False) -> dict:
    store = CouncilStore(council_db)
    if force:
        store.reset_classifications()
    pending = store.get_unclassified_decisions(limit)
    batches = list(_chunk(pending, batch_size))
    print(f"{len(pending)} decision(s) in {len(batches)} batch(es), up to {workers} workers.", flush=True)

    classified = failed = 0
    tok_in = tok_out = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_classify_chunk, b) for b in batches]
        for done, fut in enumerate(as_completed(futures), 1):
            r = fut.result()
            if r["status"] == "failed":
                failed += len(r["ids"])
                print(f"  [{done}/{len(batches)}] FAILED: {r['error']}", flush=True)
                continue
            classified += store.set_classifications(r["results"])
            tok_in += r["usage"].prompt_tokens
            tok_out += r["usage"].completion_tokens
            print(f"  [{done}/{len(batches)}] {classified}/{len(pending)} classified", flush=True)

    store.close()
    cost = tok_in / 1e6 * PRICE_IN + tok_out / 1e6 * PRICE_OUT
    return {"classified": classified, "failed": failed,
            "tokens_in": tok_in, "tokens_out": tok_out, "cost": cost}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--batch-size", type=int, default=15)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--force", action="store_true", help="re-classify all decisions")
    args = ap.parse_args()

    stats = process(args.db, args.batch_size, args.workers, args.limit, args.force)
    print(f"\n=== done: {stats['classified']} classified, {stats['failed']} failed ===")
    print(f"Tokens: {stats['tokens_in']:,} in + {stats['tokens_out']:,} out → ${stats['cost']:.4f}")
    return 1 if stats["failed"] and not stats["classified"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
