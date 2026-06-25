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
