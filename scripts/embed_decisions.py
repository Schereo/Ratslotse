#!/usr/bin/env python3
"""Compute semantic nearest-neighbour links between council decisions.

Embeds every decision (fastembed, offline) and stores each decision's top-K most
similar decisions in ``council_similar`` so the web app can show "Ähnliche
Beschlüsse". fastembed is intentionally NOT in requirements — install it just for
this run so the deploy pipeline stays untouched::

    pip install fastembed
    python scripts/embed_decisions.py
    python scripts/embed_decisions.py --top-k 6 --threshold 0.45
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import embeddings  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"


def process(db: Path, top_k: int = 6, threshold: float = 0.45, batch: int = 256) -> dict:
    import numpy as np

    store = CouncilStore(db)
    rows = store.decisions_for_embedding()
    ids = [r["id"] for r in rows]
    texts = [r["text"] for r in rows]
    n = len(ids)
    if n == 0:
        store.close()
        return {"decisions": 0, "links": 0}

    print(f"Embedding {n} decisions…", flush=True)
    vecs = embeddings.embed(texts)  # (n, dim), L2-normalised → dot = cosine

    out: list[tuple] = []
    for start in range(0, n, batch):
        block = vecs[start:start + batch] @ vecs.T  # (b, n)
        for bi, row in enumerate(block):
            i = start + bi
            row[i] = -1.0  # exclude self
            idx = np.argpartition(-row, top_k)[:top_k]
            idx = idx[np.argsort(-row[idx])]
            rank = 0
            for j in idx:
                s = float(row[j])
                if s < threshold:
                    break
                out.append((ids[i], int(ids[j]), rank, s))
                rank += 1
        print(f"  {min(start + batch, n)}/{n}", flush=True)

    store.set_similar(out)
    # Store the raw vectors too, for query-time semantic search (QA / goals).
    store.save_embeddings([(ids[i], vecs[i].tobytes()) for i in range(n)])
    store.close()
    return {"decisions": n, "links": len(out)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--top-k", type=int, default=6)
    ap.add_argument("--threshold", type=float, default=0.45)
    args = ap.parse_args()

    stats = process(args.db, args.top_k, args.threshold)
    print(f"\n=== done: {stats['links']} links for {stats['decisions']} decisions ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
