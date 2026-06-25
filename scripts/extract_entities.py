#!/usr/bin/env python3
"""Extract named entities (projects/places/organizations) from all decisions via LLM.

Runs the NER over every main decision in batches (thread pool), groups the results by
slug, keeps entities referenced by at least ``--min-n`` decisions and rebuilds the
``council_entities`` / ``council_entity_links`` tables. The basis for the entity
("Themen-") pages.

Usage::

    python scripts/extract_entities.py                  # full rebuild
    python scripts/extract_entities.py --limit 60       # smoke test
    python scripts/extract_entities.py --min-n 3
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import entities  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"
PRICE_IN, PRICE_OUT = 0.435, 0.87  # deepseek-v4-pro $/1M


def _chunk(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _extract(batch: list[dict]) -> dict:
    try:
        results, usage = entities.extract_batch(batch)
        return {"ok": True, "results": results, "usage": usage}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": repr(exc)}


def process(council_db: Path, min_n: int = 2, batch_size: int = 20,
            workers: int = 8, limit: int | None = None) -> dict:
    store = CouncilStore(council_db)
    decs = store.decisions_for_entities()
    if limit:
        decs = decs[:limit]
    batches = list(_chunk(decs, batch_size))
    print(f"{len(decs)} decision(s) in {len(batches)} batch(es), up to {workers} workers.", flush=True)

    names: dict = defaultdict(Counter)
    kinds: dict = defaultdict(Counter)
    dec_ids: dict = defaultdict(set)
    tok_in = tok_out = failed = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_extract, b) for b in batches]
        for done, fut in enumerate(as_completed(futures), 1):
            r = fut.result()
            if not r["ok"]:
                failed += 1
                continue
            for did, ents in r["results"].items():
                for e in ents:
                    sl = entities.slug(e["name"])
                    if not sl:
                        continue
                    names[sl][e["name"]] += 1
                    kinds[sl][e["kind"]] += 1
                    dec_ids[sl].add(did)
            tok_in += r["usage"].prompt_tokens
            tok_out += r["usage"].completion_tokens
            if done % 10 == 0 or done == len(batches):
                print(f"  [{done}/{len(batches)}] {len(dec_ids)} raw entities", flush=True)

    ent_rows, link_rows = [], []
    for sl, ids in dec_ids.items():
        if len(ids) < min_n:
            continue
        ent_rows.append((sl, names[sl].most_common(1)[0][0], kinds[sl].most_common(1)[0][0], len(ids)))
        link_rows.extend((sl, did) for did in ids)
    store.save_entities(ent_rows, link_rows)
    store.close()
    cost = tok_in / 1e6 * PRICE_IN + tok_out / 1e6 * PRICE_OUT
    return {"entities": len(ent_rows), "links": len(link_rows), "raw": len(dec_ids),
            "failed": failed, "cost": cost}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--min-n", type=int, default=2)
    ap.add_argument("--batch-size", type=int, default=20)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    st = process(args.db, args.min_n, args.batch_size, args.workers, args.limit)
    print(f"\n=== done: {st['entities']} entities (≥{args.min_n} decisions), {st['links']} links, "
          f"from {st['raw']} raw, {st['failed']} batch(es) failed → ${st['cost']:.4f} ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
