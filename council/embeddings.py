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
import time

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


# Decision-vector matrix, cached per process and keyed an einer billigen
# Versionsabfrage (Anzahl + höchste id): Nach einem Re-Embedding lädt der
# nächste Aufruf die Matrix selbst neu — der Service-Neustart, den der alte
# Einmal-Cache erzwang, entfällt.
_matrix_cache: tuple | None = None  # (version, ids, mat)


def _matrix(store):
    global _matrix_cache
    version = store.embeddings_version()
    if _matrix_cache is None or _matrix_cache[0] != version:
        import numpy as np

        rows = store.get_embeddings()
        ids = [r["decision_id"] for r in rows]
        if rows:
            buf = b"".join(bytes(r["vector"]) for r in rows)
            mat = np.frombuffer(buf, dtype="float32").reshape(len(ids), -1)
        else:
            mat = np.zeros((0, 0), dtype="float32")
        _matrix_cache = (version, ids, mat)
    return _matrix_cache[1], _matrix_cache[2]


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


# Zeichen-Deckel je Rerank-Paar: Die Cross-Encoder-Zeit skaliert mit der
# Tokenlänge — ungekürzt gingen bis zu ~700 Zeichen je Paar hinein. 260
# Zeichen tragen Titel + Kern der Fundstelle und halten die Trefferquote
# (Eval-geprüft); Env-Schalter für Vergleichsläufe.
PAIR_MAX_CHARS = int(os.environ.get("COUNCIL_PAIR_MAX_CHARS", "260"))


def rerank(query: str, docs: list[tuple]) -> list[tuple]:
    """Reorder ``(id, text)`` candidates by cross-encoder relevance to ``query``.
    Returns ``[(id, score)]`` best first. Raises ImportError if fastembed is missing."""
    if not docs:
        return []
    scores = list(_get_reranker().rerank(query, [d[1][:PAIR_MAX_CHARS] for d in docs]))
    ranked = sorted(zip((d[0] for d in docs), scores), key=lambda x: -x[1])
    return [(i, float(s)) for i, s in ranked]


# Wie viele Vorlagen-Treffer der Chunk-Suche in den Kandidaten-Pool einfließen
# und wie viele (jüngste) Beratungsstationen je getroffener Vorlage.
VORLAGE_POOL = 12
# Not-Deckel für die Cross-Encoder-Paare (0 = aus, der Default): Der Eval hat
# gezeigt, dass JEDER Kandidaten-Schnitt Trefferquote kostet (32 → −14, 48 →
# −10 Punkte) — der Reranker lebt davon, tief-rangige BM25-/Vorlagen-Treffer
# nach oben zu holen. Der schnellere Hebel ohne Qualitätsverlust ist der
# Zeichen-Deckel PAIR_MAX_CHARS. Dieser Schalter bleibt nur für Notfälle.
RERANK_MAX = int(os.environ.get("COUNCIL_RERANK_MAX", "0"))
VORLAGE_STATIONS = 4


def hybrid_search(store, query: str, expanded: str, top_k: int = 25, pool: int = 45,
                  timings: dict | None = None) -> list[tuple]:
    """Hybrid retrieval (RAG-SOTA): vector candidates (on the expanded query) ∪
    Vorlagen-Chunk-Treffer (Sachverhalt/Begründung, auf Beschlüsse abgebildet) ∪
    BM25 candidates (FTS), reranked by a cross-encoder against the *original*
    question. Returns ``[(decision_id, score)]``. Degrades gracefully: no
    reranker → vector order plus BM25-only extras; no fastembed at all →
    caller's keyword fallback via search().

    Die Rerank-Paare enthalten neben Titel+Summary auch Beschlusstext und
    Vorlagen-Auszug — vorher bewertete der Cross-Encoder BM25-Treffer blind,
    deren Match allein im Vorlagentext lag.

    ``timings`` (optional) wird mit Millisekunden je Teilschritt befüllt
    (vektor_ms, bm25_ms, rerank_ms, paare) — die Eval-Suite und der /ask-Endpoint
    messen damit, welcher Schritt die Antwortzeit treibt."""
    # Notausschalter (und Baseline-Arm der Eval): "1" stellt das Retrieval von
    # vor diesem Ausbau nach — keine Vorlagen-Chunk-Treffer, Rerank-Paare nur
    # aus Titel+Summary. Zur Laufzeit gelesen, wirkt also ohne Neustart.
    klassisch = os.environ.get("COUNCIL_RETRIEVAL_KLASSISCH") == "1"
    t0 = time.perf_counter()
    qv = embed([expanded])[0]  # may raise ImportError → caller falls back
    vec = _search_vec(store, qv, top_k=pool, min_score=0.2)
    vor_ids: list[int] = []
    vor_chunk: dict[int, str] = {}  # decision_id → Fundstellen-Chunk der Vorlage
    if not klassisch:
        try:
            vor = search_vorlagen(store, qv, top_k=VORLAGE_POOL)
            if vor:
                by_nr = store.decision_ids_for_vorlagen([nr for nr, _, _ in vor])
                for nr, _, chunk in vor:
                    for did in by_nr.get(nr, [])[:VORLAGE_STATIONS]:
                        vor_ids.append(did)
                        vor_chunk.setdefault(did, chunk)
        except Exception:  # noqa: BLE001 — Chunk-Index (noch) nicht aufgebaut → ohne weiter
            pass
    t1 = time.perf_counter()
    bm = store.search_decisions_fts(f"{query} {expanded}", limit=pool)
    t2 = time.perf_counter()
    bm_snippet = {i: s for i, _, s in bm if s}
    cand_ids = list(dict.fromkeys([i for i, _ in vec] + vor_ids + [i for i, _, _ in bm]))
    if RERANK_MAX and len(cand_ids) > RERANK_MAX:
        # Reihum aus den drei Quellen (je score-sortiert) ziehen — so behalten
        # alle Kanäle ihre besten Kandidaten, statt dass der Zufall der
        # Union-Reihenfolge entscheidet, wer den Cross-Encoder sieht.
        quellen = [[i for i, _ in vec], list(vor_ids), [i for i, _, _ in bm]]
        gedeckelt: list[int] = []
        gesehen: set[int] = set()
        while len(gedeckelt) < RERANK_MAX and any(quellen):
            for q in quellen:
                while q:
                    i = q.pop(0)
                    if i not in gesehen:
                        gesehen.add(i)
                        gedeckelt.append(i)
                        break
                if len(gedeckelt) >= RERANK_MAX:
                    break
        cand_ids = gedeckelt
    if timings is not None:
        timings["vektor_ms"] = round((t1 - t0) * 1000)
        timings["bm25_ms"] = round((t2 - t1) * 1000)
        timings["paare"] = len(cand_ids)
    if not cand_ids:
        return []
    docs = store.get_decisions_by_ids(cand_ids)
    if klassisch:
        pairs = [(d["id"], f"{d.get('title') or ''}. {d.get('summary') or ''}") for d in docs]
    else:
        excerpts = _vorlage_excerpts(store, [d.get("vorlage_nr") or ""
                                             for d in docs if d["id"] not in vor_chunk])
        pairs = [(d["id"], _pair_text(d, excerpts, vor_chunk, bm_snippet)) for d in docs]
    try:
        ranked = rerank(query, pairs)[:top_k]
        if timings is not None:
            timings["rerank_ms"] = round((time.perf_counter() - t2) * 1000)
        return ranked
    except Exception:  # noqa: BLE001 — reranker model/dep missing → keep vector order
        seen = {i for i, _ in vec}
        order = [i for i, _ in vec] + [i for i in cand_ids if i not in seen]
        sc = dict(vec)
        return [(i, sc.get(i, 0.0)) for i in order[:top_k]]


_pair_excerpts: dict[str, str] = {}  # vorlage_nr → excerpt; Vorlagentexte sind stabil


def _vorlage_excerpts(store, vorlage_nrs: list[str]) -> dict[str, str]:
    """Sachverhalts-Auszüge für die Rerank-Paare, prozessweit gecacht und je
    Suchlauf in EINER Batch-Abfrage nachgeladen (statt ~100 Einzelqueries)."""
    todo = sorted({(n or "").strip() for n in vorlage_nrs
                   if n and str(n).strip() and (n or "").strip() not in _pair_excerpts})
    if todo:
        from council.vorlagen import excerpt  # lazy: kein Modul-Import im Web-Pfad
        try:
            texts = store.vorlage_texts_for(todo)
        except Exception:  # noqa: BLE001
            texts = {}
        if len(_pair_excerpts) > 8192:  # simpler Deckel statt LRU — reicht hier
            _pair_excerpts.clear()
        for nr in todo:
            text = texts.get(nr) or ""
            _pair_excerpts[nr] = excerpt(text, 220) if text else ""
    return _pair_excerpts


def _pair_text(d: dict, excerpts: dict[str, str],
               vor_chunk: dict[int, str], bm_snippet: dict[int, str]) -> str:
    """Text, den der Cross-Encoder je Kandidat sieht: Titel + Summary/Beschluss
    + die aussagekräftigste Textstelle der Vorlage. Priorität: das FTS-Snippet
    (die FUNDSTELLE der Suchbegriffe), dann der semantisch getroffene
    Vorlagen-Chunk, dann der Sachverhalts-Anfang. Die Reihenfolge ist bewusst:
    Ohne Fundstelle verwarf der Reranker Kandidaten, deren Match tief im
    Volltext lag (Pumptrack-Fall der Eval) — und der best-cosine-Chunk ist ihr
    unterlegen, weil er den Suchbegriff hinter seiner 300-Zeichen-Kappung
    verlieren kann und bei Verwaltungs-Boilerplate gern gleichauf rankt
    (Märchen-Straßen-Regress der Eval). Bewusst ~500 Zeichen — mehr Text macht
    das Reranking langsamer, ohne die Relevanzentscheidung zu verbessern."""
    base = f"{d.get('title') or ''}. {(d.get('summary') or d.get('beschluss') or '')[:280]}".strip()
    extra = (bm_snippet.get(d["id"], "")[:300]
             or vor_chunk.get(d["id"], "")[:300]
             or excerpts.get((d.get("vorlage_nr") or "").strip(), ""))
    return f"{base} — {extra}" if extra else base


def search(store, query: str, top_k: int = 20, min_score: float = 0.0) -> list[tuple]:
    """Semantic search over stored decision vectors → ``[(decision_id, score)]``,
    best first, keeping only scores ≥ ``min_score``. Raises ImportError if fastembed
    is unavailable (caller falls back)."""
    qv = embed([query])[0]  # lazy-imports fastembed
    return _search_vec(store, qv, top_k=top_k, min_score=min_score)


def _search_vec(store, qv, top_k: int = 20, min_score: float = 0.0) -> list[tuple]:
    """search() mit bereits berechnetem Query-Vektor — hybrid_search embeddet die
    Anfrage nur einmal und sucht damit in Beschluss- UND Vorlagen-Vektoren."""
    import numpy as np

    ids, mat = _matrix(store)
    if not ids:
        return []
    scores = mat @ qv
    k = min(top_k, len(ids))
    idx = np.argpartition(-scores, k - 1)[:k]
    idx = idx[np.argsort(-scores[idx])]
    return [(ids[i], float(scores[i])) for i in idx if scores[i] >= min_score]


# --- Vorlagen-Chunk-Index (Sachverhalt/Begründung semantisch auffindbar) -----

# Chunk-Geometrie: excerpt() säubert den Text (Rauschzeilen weg, Start beim
# Sachverhalt), davon die ersten ~4 Fenster à ~1100 Zeichen. Das deckt
# Sachverhalt + Begründung ab, ohne den Vektorbestand aufzublähen (Karten- und
# Tabellen-Anhänge am Ende der PDFs tragen ohnehin keine Suchbegriffe).
CHUNK_SIZE = 1100
CHUNK_OVERLAP = 120
MAX_CHUNKS = 4


def vorlage_chunks(raw_text: str) -> list[str]:
    """Embedding-taugliche Textstücke einer Vorlage (siehe Chunk-Geometrie oben)."""
    from council.vorlagen import excerpt  # lazy — Web-Service importiert das nie

    cleaned = excerpt(raw_text, MAX_CHUNKS * CHUNK_SIZE + CHUNK_OVERLAP)
    cleaned = cleaned[:-2].rstrip() if cleaned.endswith(" …") else cleaned
    if not cleaned:
        return []
    out: list[str] = []
    step = CHUNK_SIZE - CHUNK_OVERLAP
    for start in range(0, len(cleaned), step):
        piece = cleaned[start:start + CHUNK_SIZE].strip()
        # Winzige Restfenster (< 200 Zeichen) sind reine Score-Verwässerer —
        # außer die ganze Vorlage ist so kurz.
        if piece and (len(piece) >= 200 or start == 0):
            out.append(piece)
        if len(out) >= MAX_CHUNKS:
            break
    return out


_vorlage_matrix_cache: tuple | None = None  # (version, nrs, texts, mat)


def _vorlage_matrix(store):
    global _vorlage_matrix_cache
    version = store.vorlage_embeddings_version()
    if _vorlage_matrix_cache is None or _vorlage_matrix_cache[0] != version:
        import numpy as np

        rows = store.get_vorlage_embeddings()
        nrs = [r["vorlage_nr"] for r in rows]
        texts = [r["chunk_text"] for r in rows]
        if rows:
            buf = b"".join(bytes(r["vector"]) for r in rows)
            mat = np.frombuffer(buf, dtype="float32").reshape(len(nrs), -1)
        else:
            mat = np.zeros((0, 0), dtype="float32")
        _vorlage_matrix_cache = (version, nrs, texts, mat)
    return _vorlage_matrix_cache[1], _vorlage_matrix_cache[2], _vorlage_matrix_cache[3]


# --- Pressemitteilungs-Index (eigener Kanal neben den Beschlüssen) -----------

PRESSE_CHUNK_SIZE = 1100
PRESSE_MAX_CHUNKS = 3


def presse_chunks(text: str) -> list[str]:
    """PM-Text in Fenster — PMs sind kurz und sauber, kein excerpt() nötig."""
    text = (text or "").strip()
    if not text:
        return []
    out, step = [], PRESSE_CHUNK_SIZE - CHUNK_OVERLAP
    for start in range(0, len(text), step):
        piece = text[start:start + PRESSE_CHUNK_SIZE].strip()
        if piece and (len(piece) >= 200 or start == 0):
            out.append(piece)
        if len(out) >= PRESSE_MAX_CHUNKS:
            break
    return out


_presse_matrix_cache: tuple | None = None  # (version, ids, texts, mat)


def _presse_matrix(store):
    global _presse_matrix_cache
    version = store.presse_embeddings_version()
    if _presse_matrix_cache is None or _presse_matrix_cache[0] != version:
        import numpy as np

        rows = store.get_presse_embeddings()
        ids = [r["presse_id"] for r in rows]
        texts = [r["chunk_text"] for r in rows]
        if rows:
            buf = b"".join(bytes(r["vector"]) for r in rows)
            mat = np.frombuffer(buf, dtype="float32").reshape(len(ids), -1)
        else:
            mat = np.zeros((0, 0), dtype="float32")
        _presse_matrix_cache = (version, ids, texts, mat)
    return _presse_matrix_cache[1], _presse_matrix_cache[2], _presse_matrix_cache[3]


def search_presse(store, query: str, expanded: str, top_k: int = 3,
                  min_score: float = 0.45) -> list[tuple]:
    """Beste Pressemitteilungen zur Frage → ``[(presse_id, score)]``.
    Vektor-Kanal (bester Chunk je PM) ∪ BM25 — bewusst mit strenger Schwelle:
    der Block „Aktuelles von der Stadt" soll nur auftauchen, wenn es wirklich
    Einschlägiges gibt. Leer, solange kein PM-Index aufgebaut ist."""
    best: dict[int, float] = {}
    try:
        ids, _texts, mat = _presse_matrix(store)
        if ids:
            qv = embed([expanded])[0]
            scores = mat @ qv
            for pid, s in zip(ids, scores):
                if s >= min_score and s > best.get(pid, -1.0):
                    best[pid] = float(s)
    except Exception:  # noqa: BLE001 — ohne fastembed bleibt BM25
        pass
    for pid, score, _snip in store.search_presse_fts(f"{query} {expanded}", limit=top_k * 3):
        # BM25-Scores sind nicht cosine-vergleichbar — nur als Auffüller hinter
        # den Vektor-Treffern (kleiner Sockel-Score).
        best.setdefault(pid, 0.01 + min(score, 50) / 1000)
    return sorted(best.items(), key=lambda x: -x[1])[:top_k]


def embed_presse_missing(store) -> int:
    """Chunk-Vektoren für neue/geänderte PMs schreiben (hash-idempotent).
    Wird vom täglichen check_presse best-effort gerufen (fastembed nötig) und
    von embed_decisions.py im Wochenlauf als Backstop."""
    todo = store.presse_missing_embeddings()
    n = 0
    for p in todo:
        chunks = presse_chunks(p["text"])
        if not chunks:
            store.replace_presse_embeddings(p["id"], p["text_hash"], [])
            continue
        vecs = embed(chunks)
        store.replace_presse_embeddings(
            p["id"], p["text_hash"],
            [(chunks[i], vecs[i].tobytes()) for i in range(len(chunks))])
        n += len(chunks)
    return n


def search_vorlagen(store, qv, top_k: int = 12, min_score: float = 0.35) -> list[tuple]:
    """Beste Vorlagen zu einem Query-Vektor → ``[(vorlage_nr, score, chunk_text)]``,
    je Vorlage zählt ihr bester Chunk (dessen Text wandert in das Rerank-Paar).
    Leer, solange der Chunk-Index nicht gebaut ist (embed_decisions.py)."""
    nrs, texts, mat = _vorlage_matrix(store)
    if not nrs:
        return []
    scores = mat @ qv
    best: dict[str, tuple[float, str]] = {}
    for nr, text, s in zip(nrs, texts, scores):
        if s >= min_score and s > best.get(nr, (-1.0, ""))[0]:
            best[nr] = (float(s), text)
    ranked = sorted(best.items(), key=lambda x: -x[1][0])[:top_k]
    return [(nr, s, text) for nr, (s, text) in ranked]
