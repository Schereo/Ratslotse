#!/usr/bin/env python3
"""Assess council decisions against the city's overarching goals (council.goals).

For each goal: retrieve keyword candidates, ask the LLM (batched, in parallel)
whether each decision concerns the goal and whether it advances / hinders / is
neutral, and store the links. Re-running rebuilds a goal's links from scratch
(idempotent). DB writes stay on the main thread.

Usage::

    python scripts/track_goals.py                  # all goals
    python scripts/track_goals.py --only klima_2035 --workers 12
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

from council import goals  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"
PRICE_IN, PRICE_OUT = 0.435, 0.87  # deepseek-v4-pro $/1M


def _assess_chunk(goal_key: str, batch: list[dict]) -> dict:
    try:
        results, usage = goals.assess_batch(goal_key, batch)
        return {"status": "ok", "results": results, "usage": usage}
    except Exception as exc:  # noqa: BLE001
        return {"status": "failed", "error": repr(exc)}


def _candidates(store, goal_key: str, goal: dict, incremental: bool) -> list[dict]:
    """Keyword candidates ∪ semantic neighbours of the goal description.
    Semantic recall catches decisions that don't use the keywords (esp. 'bremst').
    Falls back to keyword-only if fastembed/embeddings aren't available."""
    exclude = goal_key if incremental else None
    cands = store.get_goal_candidates(goal["keywords"], exclude_goal=exclude)
    seen = {c["id"] for c in cands}
    try:
        from council import embeddings
        skip = store.linked_decision_ids(goal_key) if incremental else set()
        query = f"{goal['label']}. {goal['description']}"
        sem_ids = [i for i, _ in embeddings.search(store, query, top_k=150, min_score=0.3)
                   if i not in seen and i not in skip]
        cands += store.get_decisions_by_ids(sem_ids)
    except Exception:  # noqa: BLE001 — no embeddings → keyword-only
        pass
    return cands


def process(council_db: Path, batch_size: int = 12, workers: int = 8,
            only: str | None = None, incremental: bool = False) -> dict:
    store = CouncilStore(council_db)
    links = tok_in = tok_out = 0
    for goal_key, goal in goals.GOALS.items():
        if only and goal_key != only:
            continue
        # Incremental (daily cron): only assess decisions not yet linked to this goal,
        # and keep existing links. Full run: rebuild the goal from scratch.
        cands = _candidates(store, goal_key, goal, incremental)
        if not incremental:
            store.clear_goal_links(goal_key)
        if incremental and not cands:
            continue
        batches = [cands[i:i + batch_size] for i in range(0, len(cands), batch_size)]
        print(f"{goal_key}: {len(cands)} candidates in {len(batches)} batch(es)", flush=True)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(_assess_chunk, goal_key, b) for b in batches]
            for fut in as_completed(futures):
                r = fut.result()
                if r["status"] == "failed":
                    print(f"  batch FAILED: {r['error']}", flush=True)
                    continue
                links += store.save_goal_links(goal_key, r["results"])
                tok_in += r["usage"].prompt_tokens
                tok_out += r["usage"].completion_tokens
        s = store.goal_summary().get(goal_key, {})
        print(f"  -> relevant {s.get('total', 0)} (voran {s.get('voran', 0)}, "
              f"bremst {s.get('bremst', 0)}, neutral {s.get('neutral', 0)})", flush=True)
    store.close()
    cost = tok_in / 1e6 * PRICE_IN + tok_out / 1e6 * PRICE_OUT
    return {"links": links, "tokens_in": tok_in, "tokens_out": tok_out, "cost": cost}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--batch-size", type=int, default=12)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--only", default=None, help="restrict to one goal key")
    ap.add_argument("--incremental", action="store_true", help="only assess newly unlinked decisions")
    args = ap.parse_args()

    stats = process(args.db, args.batch_size, args.workers, args.only, args.incremental)
    print(f"\n=== done: {stats['links']} links ===")
    print(f"Tokens: {stats['tokens_in']:,} in + {stats['tokens_out']:,} out → ${stats['cost']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
