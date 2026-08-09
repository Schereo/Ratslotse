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
        return {"decisions": 0, "links": 0, "vorlagen_chunks": 0}

    interest_by_id = {
        r[0]: r[1]
        for r in store._conn.execute(
            "SELECT id, interest FROM council_decisions WHERE interest IS NOT NULL"
        ).fetchall()
    }
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
            # RL-U15: bei praktisch gleicher Ähnlichkeit (±0.01) gewinnt der
            # interessantere Nachbar — reine Zweitsortierung, Cosine bleibt Chef.
            idx = sorted(idx, key=lambda j: (-round(float(row[j]), 2),
                                             -(interest_by_id.get(int(ids[j])) or 0)))
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

    # Vorlagen-Chunk-Index für die Hybrid-Suche: Sachverhalt/Begründung je
    # Vorlage in ~4 Fenstern embedden. Hash-idempotent — nach dem ersten
    # Volllauf embeddet jeder weitere nur neue/geänderte Vorlagen.
    todo = store.vorlagen_missing_embeddings()
    n_chunks = 0
    if todo:
        print(f"Embedding Vorlagen-Chunks für {len(todo)} Vorlagen…", flush=True)
        for start in range(0, len(todo), batch):
            block = todo[start:start + batch]
            chunk_lists = [embeddings.vorlage_chunks(v["raw_text"]) for v in block]
            flat = [c for chunks in chunk_lists for c in chunks]
            if not flat:
                continue
            cvecs = embeddings.embed(flat)
            pos = 0
            for v, chunks in zip(block, chunk_lists):
                if not chunks:
                    continue
                rows_v = [(chunks[j], cvecs[pos + j].tobytes()) for j in range(len(chunks))]
                pos += len(chunks)
                store.replace_vorlage_embeddings(v["vorlage_nr"], v["text_hash"], rows_v)
                n_chunks += len(chunks)
            print(f"  {min(start + batch, len(todo))}/{len(todo)}", flush=True)

    # Presse-Chunks als Wochen-Backstop (der tägliche check_presse embeddet
    # Neues sofort; hier wird nachgeholt, was dort ohne fastembed liegen blieb).
    n_presse = embeddings.embed_presse_missing(store)
    n_wb = embeddings.embed_wortbeitraege_missing(store)

    store.close()
    return {"decisions": n, "links": len(out), "vorlagen_chunks": n_chunks,
            "presse_chunks": n_presse, "wortbeitraege": n_wb}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--top-k", type=int, default=6)
    ap.add_argument("--threshold", type=float, default=0.45)
    args = ap.parse_args()

    stats = process(args.db, args.top_k, args.threshold)
    print(f"\n=== done: {stats['links']} links for {stats['decisions']} decisions, "
          f"{stats['vorlagen_chunks']} neue Vorlagen-Chunks ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
