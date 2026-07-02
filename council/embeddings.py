"""Semantic embeddings for council decisions (offline / script-time only).

Uses fastembed (ONNX, no torch) with a small multilingual model. This module is
imported ONLY by the offline backfill (scripts/embed_decisions.py) — fastembed is
deliberately NOT a web-service or test dependency, so the deploy pipeline stays
untouched. The web service only ever reads the precomputed ``council_similar``
neighbours.

Install for the backfill: ``pip install fastembed``.
"""
from __future__ import annotations

import os

# Multilingual (incl. German), 384-dim, ~220 MB — good German similarity, light.
MODEL = os.environ.get("COUNCIL_EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

_model = None


def _get_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding  # lazy: only when actually embedding
        _model = TextEmbedding(MODEL)
    return _model


def embed(texts: list[str]):
    """Return L2-normalised embeddings (N, dim) as a float32 numpy array, so that a
    dot product equals cosine similarity."""
    import numpy as np

    vecs = np.array(list(_get_model().embed(texts)), dtype="float32")
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vecs / norms


# Decision-vector matrix, loaded once per process. Re-run embed_decisions.py +
# restart the service to refresh it.
_matrix_cache: tuple | None = None


def _matrix(store):
    global _matrix_cache
    if _matrix_cache is None:
        import numpy as np

        rows = store.get_embeddings()
        ids = [r["decision_id"] for r in rows]
        if rows:
            buf = b"".join(bytes(r["vector"]) for r in rows)
            mat = np.frombuffer(buf, dtype="float32").reshape(len(ids), -1)
        else:
            mat = np.zeros((0, 0), dtype="float32")
        _matrix_cache = (ids, mat)
    return _matrix_cache


# Multilingual cross-encoder reranker (incl. German). Lazy-loaded like the embedder;
# the web service falls back to pure vector order if fastembed/the model is missing.
RERANK_MODEL = os.environ.get("COUNCIL_RERANK_MODEL", "jinaai/jina-reranker-v2-base-multilingual")
_reranker = None


def _get_reranker():
    global _reranker
    if _reranker is None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder  # lazy
        _reranker = TextCrossEncoder(RERANK_MODEL)
    return _reranker


def rerank(query: str, docs: list[tuple]) -> list[tuple]:
    """Reorder ``(id, text)`` candidates by cross-encoder relevance to ``query``.
    Returns ``[(id, score)]`` best first. Raises ImportError if fastembed is missing."""
    if not docs:
        return []
    scores = list(_get_reranker().rerank(query, [d[1] for d in docs]))
    ranked = sorted(zip((d[0] for d in docs), scores), key=lambda x: -x[1])
    return [(i, float(s)) for i, s in ranked]


def hybrid_search(store, query: str, expanded: str, top_k: int = 25, pool: int = 45) -> list[tuple]:
    """Hybrid retrieval (RAG-SOTA): vector candidates (on the expanded query) ∪ BM25
    candidates (FTS), reranked by a cross-encoder against the *original* question.
    Returns ``[(decision_id, score)]``. Degrades gracefully: no reranker → vector order
    plus BM25-only extras; no fastembed at all → caller's keyword fallback via search()."""
    vec = search(store, expanded, top_k=pool, min_score=0.2)  # may raise ImportError → caller falls back
    bm = store.search_decisions_fts(f"{query} {expanded}", limit=pool)
    cand_ids = list(dict.fromkeys([i for i, _ in vec] + [i for i, _ in bm]))
    if not cand_ids:
        return []
    docs = store.get_decisions_by_ids(cand_ids)
    pairs = [(d["id"], f"{d.get('title') or ''}. {d.get('summary') or ''}") for d in docs]
    try:
        return rerank(query, pairs)[:top_k]
    except Exception:  # noqa: BLE001 — reranker model/dep missing → keep vector order
        seen = {i for i, _ in vec}
        order = [i for i, _ in vec] + [i for i in cand_ids if i not in seen]
        sc = dict(vec)
        return [(i, sc.get(i, 0.0)) for i in order[:top_k]]


def search(store, query: str, top_k: int = 20, min_score: float = 0.0) -> list[tuple]:
    """Semantic search over stored decision vectors → ``[(decision_id, score)]``,
    best first, keeping only scores ≥ ``min_score``. Raises ImportError if fastembed
    is unavailable (caller falls back)."""
    import numpy as np

    ids, mat = _matrix(store)
    if not ids:
        return []
    qv = embed([query])[0]  # lazy-imports fastembed
    scores = mat @ qv
    k = min(top_k, len(ids))
    idx = np.argpartition(-scores, k - 1)[:k]
    idx = idx[np.argsort(-scores[idx])]
    return [(ids[i], float(scores[i])) for i in idx if scores[i] >= min_score]
