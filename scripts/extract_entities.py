#!/usr/bin/env python3
"""Extract named entities (projects/places/organizations) from decisions via LLM.

Incremental by default: runs the NER only over decisions not yet scanned, appends the
raw observations to ``council_entity_obs`` and re-derives the ``council_entities`` /
``council_entity_links`` tables (keeping entities referenced by at least ``--min-n``
distinct decisions). Raw observations are retained, so an entity seen once now and
again later still crosses the threshold. The basis for the entity ("Themen-") pages.

Usage::

    python scripts/extract_entities.py                  # incremental (only new decisions)
    python scripts/extract_entities.py --full           # clear + re-scan every decision
    python scripts/extract_entities.py --limit 60       # smoke test (cap new decisions)
    python scripts/extract_entities.py --min-n 3
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
            workers: int = 8, limit: int | None = None, full: bool = False) -> dict:
    store = CouncilStore(council_db)
    if full:
        store.reset_entity_obs()
    decs = store.decisions_for_entities()
    scanned = store.scanned_entity_decision_ids()
    new_decs = [d for d in decs if d["id"] not in scanned]
    if limit:
        new_decs = new_decs[:limit]

    obs_rows: list[tuple] = []
    tok_in = tok_out = failed = 0
    if new_decs:
        batches = list(_chunk(new_decs, batch_size))
        print(f"{len(new_decs)} new decision(s) of {len(decs)} total in {len(batches)} "
              f"batch(es), up to {workers} workers.", flush=True)
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
                        obs_rows.append((did, sl, e["name"], e["kind"]))
                tok_in += r["usage"].prompt_tokens
                tok_out += r["usage"].completion_tokens
                if done % 10 == 0 or done == len(batches):
                    print(f"  [{done}/{len(batches)}] {len(obs_rows)} observations", flush=True)
        store.add_entity_observations(obs_rows, [d["id"] for d in new_decs])
    else:
        print(f"No new decisions to scan (of {len(decs)} total) — re-deriving entities.", flush=True)

    ent_n, link_n = store.rebuild_entities_from_obs(min_n)
    store.close()
    cost = tok_in / 1e6 * PRICE_IN + tok_out / 1e6 * PRICE_OUT
    return {"entities": ent_n, "links": link_n, "new": len(new_decs),
            "obs": len(obs_rows), "failed": failed, "cost": cost}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--min-n", type=int, default=2)
    ap.add_argument("--batch-size", type=int, default=20)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--full", action="store_true",
                    help="clear observations and re-scan every decision from scratch")
    args = ap.parse_args()
    st = process(args.db, args.min_n, args.batch_size, args.workers, args.limit, args.full)
    print(f"\n=== done: {st['entities']} entities (≥{args.min_n} decisions), {st['links']} links; "
          f"scanned {st['new']} new decision(s) → {st['obs']} new observations, "
          f"{st['failed']} batch(es) failed → ${st['cost']:.4f} ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
