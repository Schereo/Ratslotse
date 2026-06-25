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


def search(store, query: str, top_k: int = 20) -> list[tuple]:
    """Semantic search over stored decision vectors → ``[(decision_id, score)]``,
    best first. Raises ImportError if fastembed is unavailable (caller falls back)."""
    import numpy as np

    ids, mat = _matrix(store)
    if not ids:
        return []
    qv = embed([query])[0]  # lazy-imports fastembed
    scores = mat @ qv
    k = min(top_k, len(ids))
    idx = np.argpartition(-scores, k - 1)[:k]
    idx = idx[np.argsort(-scores[idx])]
    return [(ids[i], float(scores[i])) for i in idx]
