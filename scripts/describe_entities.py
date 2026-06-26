#!/usr/bin/env python3
"""Generate a short, grounded description for each entity ("Themen-") page via LLM.

For every entity that lacks a description, the LLM writes 2–4 factual sentences (what
it is + why the council deals with it), grounded in that entity's decisions. Stored in
``council_entity_meta`` (keyed by slug, so it survives the full rebuild of
``council_entities`` by extract_entities.py). Idempotent — only fills what's missing.

    python scripts/describe_entities.py                # describe all missing
    python scripts/describe_entities.py --limit 20     # smoke test
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

from council import entities  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"


def process(council_db: Path, workers: int = 8, limit: int | None = None) -> dict:
    store = CouncilStore(council_db)
    ents = store.entities_without_description()
    if limit:
        ents = ents[:limit]
    # Read all decisions up front in the main thread — the sqlite connection is not
    # shared across threads; the workers only do the (pure) LLM call.
    work = [(e, store.entity_decisions_brief(e["slug"])) for e in ents]
    print(f"{len(work)} entit(y/ies) to describe, up to {workers} workers.", flush=True)

    def _describe(item: tuple) -> tuple:
        e, decs = item
        return (e["slug"], entities.describe(e["name"], e["kind"], decs))

    rows: list[tuple] = []
    done = failed = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_describe, item) for item in work]
        for fut in as_completed(futures):
            slug, text = fut.result()
            done += 1
            if text:
                rows.append((slug, text))
            else:
                failed += 1
            if done % 25 == 0 or done == len(work):
                print(f"  [{done}/{len(work)}] {len(rows)} described", flush=True)

    store.set_entity_descriptions(rows)
    store.close()
    return {"described": len(rows), "failed": failed}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    st = process(args.db, args.workers, args.limit)
    print(f"\n=== done: {st['described']} described, {st['failed']} failed/empty ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
