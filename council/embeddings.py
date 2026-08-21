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
import re
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


# Mini-Cache für Einzeltext-Embeddings: Ein /ask embeddet die expandierte
# Frage sonst DREIMAL (Beschlüsse, Presse, Wortbeiträge) — gleicher Text,
# gleicher Vektor. Bewusst winzig (die letzten 8 Queries), Batches (Chunks)
# laufen daran vorbei.
_single_cache: "dict[str, object]" = {}


def embed(texts: list[str]):
    """Return L2-normalised embeddings (N, dim) as a float32 numpy array, so that a
    dot product equals cosine similarity."""
    import numpy as np

    if len(texts) == 1 and texts[0] in _single_cache:
        return _single_cache[texts[0]]
    vecs = np.array(list(_get_model().embed(texts)), dtype="float32")
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    out = vecs / norms
    if len(texts) == 1:
        if len(_single_cache) >= 8:
            _single_cache.pop(next(iter(_single_cache)))
        _single_cache[texts[0]] = out
    return out


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


# Rerank-Cache: Der Cross-Encoder ist der mit Abstand teuerste Schritt der
# Suche — auf der Prod-VM gemessen 3,5 s für 119 Paare, also 86 % der
# Retrieval-Zeit (Vektor 21 ms, BM25 76 ms, Paar-Bau 2 ms). Mehr Threads
# helfen nicht: Der onnxruntime-Default nutzt bereits alle 8 Kerne (2,0 s;
# mit threads=4 wird es mit 3,1 s sogar langsamer), und Kandidaten zu
# streichen kostet nachweislich Trefferquote.
#
# Was bleibt, ist Wiederverwendung — und Fragen wiederholen sich wortgleich:
# Beispielfragen, Folgefragen-Chips, „nochmal versuchen", dieselbe Frage im
# zweiten Gespräch. Der Schlüssel enthält den Fingerabdruck des Paartextes;
# ändert sich der Vorlagen-Auszug eines Beschlusses, fällt sein Eintrag von
# selbst heraus, statt einen veralteten Wert zu liefern.
_RERANK_CACHE: dict[tuple, float] = {}
_RERANK_CACHE_MAX = 4000


def rerank(query: str, docs: list[tuple]) -> list[tuple]:
    """Reorder ``(id, text)`` candidates by cross-encoder relevance to ``query``.
    Returns ``[(id, score)]`` best first. Raises ImportError if fastembed is missing."""
    if not docs:
        return []
    # Doppelte ids wären im Ergebnis ohnehin bedeutungslos — und würden den
    # Cache-Abgleich verfälschen.
    gekappt: list[tuple] = []
    gesehen: set = set()
    for i, t in docs:
        if i in gesehen:
            continue
        gesehen.add(i)
        gekappt.append((i, (t or "")[:PAIR_MAX_CHARS]))

    werte: dict = {}
    offen: list[tuple] = []
    for i, t in gekappt:
        key = (query, i, hash(t))
        treffer = _RERANK_CACHE.get(key)
        if treffer is None:
            offen.append((key, i, t))
        else:
            werte[i] = treffer
    if offen:
        scores = list(_get_reranker().rerank(query, [t for _k, _i, t in offen]))
        for (key, i, _t), s in zip(offen, scores):
            werte[i] = float(s)
            if len(_RERANK_CACHE) >= _RERANK_CACHE_MAX:
                _RERANK_CACHE.pop(next(iter(_RERANK_CACHE)))
            _RERANK_CACHE[key] = float(s)
    return sorted(((i, werte[i]) for i, _ in gekappt), key=lambda x: -x[1])


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
                  timings: dict | None = None,
                  varianten: list[str] | None = None,
                  anker_ids: list[int] | None = None,
                  recency: bool = False) -> list[tuple]:
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
    # Multi-Query (Task 32): Perspektiv-Varianten der Analyse steuern bis zu
    # 12 ZUSÄTZLICHE Kandidaten bei, die Haupt-Expansion und BM25 verfehlt
    # haben — gezielte Lückenfüller statt Pool-Flutung, damit der Rerank
    # nahezu konstant bleibt (~+0,5 s statt +1,5 s bei voller Union).
    if varianten and not klassisch:
        bereits = set(cand_ids)
        neue: list[int] = []
        for var in varianten[:2]:
            try:
                vv = embed([var])[0]
                for did, _s in _search_vec(store, vv, top_k=pool // 2, min_score=0.25):
                    if did not in bereits:
                        bereits.add(did)
                        neue.append(did)
            except Exception:  # noqa: BLE001 — Varianten sind Zusatz, nie Blocker
                pass
        cand_ids += neue[:12]
        if timings is not None:
            timings["varianten_neu"] = min(len(neue), 12)
    # Entitäts-Anker (Akkuratheits-Paket): Beschlüsse, die DETERMINISTISCH an
    # einer in der Frage erkannten Entität hängen (council_entity_links), in
    # den Rerank-Pool — der Cross-Encoder entscheidet fair mit, ob sie es in
    # die Antwort schaffen. Heilt Fälle, in denen die Semantik ein benanntes
    # Objekt (Brücke, Schule, Gelände) verfehlt.
    if anker_ids and not klassisch:
        bereits = set(cand_ids)
        anker_neu = [i for i in anker_ids if i not in bereits][:12]
        cand_ids += anker_neu
        if timings is not None:
            timings["anker_neu"] = len(anker_neu)
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
        ranked = rerank(query, pairs)
        if recency:
            # Sachstands-Fragen („Stand", „aktuell", „zuletzt"): jüngere
            # Beschlüsse bekommen einen kleinen Logit-Bonus — kippt nahe
            # Duelle zugunsten des frischen Stands, überstimmt aber nie einen
            # klar besseren Alt-Treffer. VOR dem top_k-Schnitt, damit frische
            # Grenzfälle nicht schon ausgeschieden sind.
            try:
                ranked = recency_boost(
                    ranked, store.session_dates_fuer([i for i, _ in ranked]))
            except Exception:  # noqa: BLE001 — Bonus ist Zusatz, nie Blocker
                pass
        ranked = ranked[:top_k]
        if timings is not None:
            timings["rerank_ms"] = round((time.perf_counter() - t2) * 1000)
        return ranked
    except Exception:  # noqa: BLE001 — reranker model/dep missing → keep vector order
        seen = {i for i, _ in vec}
        order = [i for i, _ in vec] + [i for i in cand_ids if i not in seen]
        sc = dict(vec)
        return [(i, sc.get(i, 0.0)) for i in order[:top_k]]


def recency_boost(hits: list[tuple], dates: dict[int, str],
                  heute=None) -> list[tuple]:
    """Reranker-Logits um einen Frische-Bonus ergänzen und neu sortieren:
    +0,6 bei „gerade beschlossen", exponentiell abklingend (Halbwert ~10
    Monate). Die Skala ist bewusst klein gegen die Logit-Spanne des
    Rerankers (>2 Punkte zwischen relevant und fremd) — Aktualität bricht
    Nähe-Duelle, ersetzt aber keine Relevanz."""
    if not dates:
        return hits
    import math as _math
    from datetime import date as _date

    heute = heute or _date.today()
    out = []
    for did, score in hits:
        bonus = 0.0
        d = dates.get(did)
        if d:
            try:
                monate = max(0, (heute - _date.fromisoformat(str(d)[:10])).days) / 30.4
                bonus = 0.6 * _math.exp(-monate / 15.0)
            except ValueError:
                pass
        out.append((did, score + bonus))
    out.sort(key=lambda x: -x[1])
    return out


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


# Cross-Encoder-Cutoff für die Zusatzkanäle (Presse, Wortbeiträge): Bi-Encoder-
# Cosines trennen amtliche Kurztexte NICHT (Stadion-PM 0.466 < Ampelwartung
# 0.471 auf die Stadion-Frage!), der Reranker trennt mit >2 Punkten Abstand
# (gemessen 10.08.: echte Treffer −0.1…−0.5, Fremdthemen ≤ −2.5).
KONTEXT_RERANK_MIN = float(os.environ.get("COUNCIL_KONTEXT_RERANK_MIN", "-1.5"))
# Kürzerer Zeichen-Deckel NUR für die Zusatzkanal-Paare: 260 → 150 spart ~22 %
# der Kontext-Rerank-Zeit (gemessen 10.08.: 799 → 623 ms) bei unveränderter
# Trennschärfe (echte PM −0.12 vs. Ampelwartung −2.36 — weiter >2 Punkte).
KONTEXT_PAIR_MAX = int(os.environ.get("COUNCIL_KONTEXT_PAIR_MAX", "150"))


def _rerank_kontext(query: str, kandidaten: list[tuple], top_k: int,
                    min_rerank: float | None = None) -> list[tuple]:
    """``[(id, text)]``-Kandidaten der Zusatzkanäle per Cross-Encoder bestätigen —
    nur Paare über dem Cutoff überleben. Ohne Reranker (fastembed fehlt) lieber
    leer als Rauschen: die Zusatzblöcke sind optional."""
    try:
        ranked = rerank(query, [(i, (t or "")[:KONTEXT_PAIR_MAX]) for i, t in kandidaten])
    except Exception:  # noqa: BLE001
        return []
    grenze = KONTEXT_RERANK_MIN if min_rerank is None else min_rerank
    return [(i, s) for i, s in ranked if s >= grenze][:top_k]


def search_presse(store, query: str, expanded: str, top_k: int = 3,
                  min_score: float = 0.45) -> list[tuple]:
    """Beste Pressemitteilungen zur Frage → ``[(presse_id, score)]``.
    Vektor-Kanal (bester Chunk je PM) als Kandidaten-Lieferant, Cross-Encoder
    als Torwächter — der Block „Aktuelles von der Stadt" soll nur auftauchen,
    wenn es wirklich Einschlägiges gibt. BM25 nur als Fallback, solange kein
    PM-Index aufgebaut ist (als Auffüller daneben hob er thematisch fremde
    PMs in die UI — Tims Ampel-Wartungs-Befund 10.08.)."""
    best: dict[int, tuple[float, str]] = {}
    vektor_ok = False
    try:
        ids, texts, mat = _presse_matrix(store)
        if ids:
            vektor_ok = True
            qv = embed([expanded])[0]
            scores = mat @ qv
            for pid, text, s in zip(ids, texts, scores):
                if s >= min_score and s > best.get(pid, (-1.0, ""))[0]:
                    best[pid] = (float(s), text)
    except Exception:  # noqa: BLE001 — ohne fastembed bleibt BM25
        pass
    if not vektor_ok:
        fallback: dict[int, float] = {}
        for pid, score, _snip in store.search_presse_fts(f"{query} {expanded}", limit=top_k * 3):
            fallback.setdefault(pid, 0.01 + min(score, 50) / 1000)
        return sorted(fallback.items(), key=lambda x: -x[1])[:top_k]
    kandidaten = sorted(best.items(), key=lambda x: -x[1][0])[:max(top_k * 3, 9)]
    return _rerank_kontext(query, [(pid, t) for pid, (_s, t) in kandidaten], top_k)


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


# ---- Anlagen (Task 33): Gutachten, Konzepte, Stellungnahmen ----------------
# Kanal NUR der Gründlichen Recherche (RG-10): dort zählt Tiefe, nicht Latenz —
# die schnelle Frage lädt diese Matrix nie. Chunks größer gedeckelt als bei
# Vorlagen (Gutachten tragen ihre Substanz über viele Seiten).
ANLAGE_CHUNK_SIZE = 1100
ANLAGE_MAX_CHUNKS = 8

_anlage_matrix_cache: tuple | None = None  # (version, ids, texts, mat)


def anlage_chunks(raw_text: str) -> list[str]:
    """Anlagen-Text → überlappende Chunks (Muster vorlage_chunks, eigener Deckel)."""
    from council.vorlagen import excerpt  # lazy: kein Modul-Import im Web-Pfad

    cleaned = excerpt(raw_text, ANLAGE_MAX_CHUNKS * ANLAGE_CHUNK_SIZE + CHUNK_OVERLAP)
    if not cleaned:
        return []
    out = []
    step = ANLAGE_CHUNK_SIZE - CHUNK_OVERLAP
    for start in range(0, len(cleaned), step):
        piece = cleaned[start:start + ANLAGE_CHUNK_SIZE].strip()
        if len(piece) >= 80:
            out.append(piece)
        if len(out) >= ANLAGE_MAX_CHUNKS:
            break
    return out


def embed_anlagen_missing(store, limit: int | None = None) -> int:
    """Chunk-Vektoren für neue/geänderte Anlagen (hash-idempotent). Gerufen von
    scripts/embed_anlagen.py (Einmal-Batch) und weekly_enrich als Backstop."""
    todo = store.anlagen_missing_embeddings(limit=limit)
    n = 0
    for a in todo:
        # Label voranstellen: „Lärmgutachten — <Text>" macht den ersten Chunk
        # als Fundstelle und Rerank-Paar deutlich stärker.
        text = " — ".join(t for t in (a.get("label"), a.get("raw_text")) if t)
        chunks = anlage_chunks(text)
        if not chunks:
            store.replace_anlage_embeddings(a["document_id"], a["text_hash"], [])
            continue
        vecs = embed(chunks)
        store.replace_anlage_embeddings(
            a["document_id"], a["text_hash"],
            [(chunks[i], vecs[i].tobytes()) for i in range(len(chunks))])
        n += len(chunks)
    return n


def _anlage_matrix(store):
    global _anlage_matrix_cache
    version = store.anlage_embeddings_version()
    if _anlage_matrix_cache is None or _anlage_matrix_cache[0] != version:
        import numpy as np

        rows = store.get_anlage_embeddings()
        ids = [r["document_id"] for r in rows]
        texts = [r["chunk_text"] for r in rows]
        if rows:
            buf = b"".join(bytes(r["vector"]) for r in rows)
            mat = np.frombuffer(buf, dtype="float32").reshape(len(ids), -1)
        else:
            mat = np.zeros((0, 0), dtype="float32")
        _anlage_matrix_cache = (version, ids, texts, mat)
    return _anlage_matrix_cache[1], _anlage_matrix_cache[2], _anlage_matrix_cache[3]


def search_anlagen(store, query: str, expanded: str, top_k: int = 6,
                   min_score: float = 0.45) -> list[tuple]:
    """Beste Anlagen (Gutachten, Konzepte) zur Frage →
    ``[(document_id, score, fundstelle)]``. Vektor liefert Kandidaten (bester
    Chunk je Anlage), der Cross-Encoder bestätigt — kein BM25-Fallback: der
    Kanal existiert nur in der Gründlichen Recherche und darf leer sein."""
    try:
        ids, texts, mat = _anlage_matrix(store)
    except Exception:  # noqa: BLE001 — ohne fastembed keine Anlagen
        return []
    if not ids:
        return []
    qv = embed([expanded])[0]
    scores = mat @ qv
    best: dict[int, tuple[float, str]] = {}
    for did, text, s in zip(ids, texts, scores):
        if s >= min_score and s > best.get(did, (-1.0, ""))[0]:
            best[did] = (float(s), text)
    kandidaten = sorted(best.items(), key=lambda x: -x[1][0])[:max(top_k * 3, 12)]
    fundstellen = {did: t for did, (_s, t) in kandidaten}
    bestaetigt = _rerank_kontext(query, [(did, t) for did, (_s, t) in kandidaten], top_k)
    return [(did, s, fundstellen.get(did, "")) for did, s in bestaetigt]


_wb_matrix_cache: tuple | None = None  # (version, ids, mat)


def _wb_matrix(store):
    global _wb_matrix_cache
    version = store.wortbeitraege_embeddings_version()
    if _wb_matrix_cache is None or _wb_matrix_cache[0] != version:
        import numpy as np

        rows = store.wortbeitraege_embedding_rows()
        ids = [r[0] for r in rows]
        if rows:
            buf = b"".join(bytes(r[1]) for r in rows)
            mat = np.frombuffer(buf, dtype="float32").reshape(len(ids), -1)
        else:
            mat = np.zeros((0, 0), dtype="float32")
        _wb_matrix_cache = (version, ids, mat)
    return _wb_matrix_cache[1], _wb_matrix_cache[2]


def search_wortbeitraege(store, query: str, expanded: str, top_k: int = 4,
                         min_score: float = 0.45) -> list[tuple]:
    """Beste Wortbeiträge (Debatten, Anfragen, Einwohnerfragen) zur Frage →
    ``[(wb_id, score)]``. Wie search_presse: Vektor liefert Kandidaten, der
    Cross-Encoder bestätigt — der Debatten-Block soll nur bei echter
    Einschlägigkeit kommen. BM25 nur als Fallback ohne Index."""
    best: dict[int, float] = {}
    vektor_ok = False
    try:
        ids, mat = _wb_matrix(store)
        if ids:
            vektor_ok = True
            qv = embed([expanded])[0]
            scores = mat @ qv
            for wid, s in zip(ids, scores):
                if s >= min_score and s > best.get(wid, -1.0):
                    best[wid] = float(s)
    except Exception:  # noqa: BLE001 — ohne fastembed bleibt BM25
        pass
    if not vektor_ok:
        fallback: dict[int, float] = {}
        for wid, score in store.search_wortbeitraege_fts(f"{query} {expanded}", limit=top_k * 3):
            fallback.setdefault(wid, 0.01 + min(score, 50) / 1000)
        return sorted(fallback.items(), key=lambda x: -x[1])[:top_k]
    kandidaten = sorted(best.items(), key=lambda x: -x[1])[:max(top_k * 3, 12)]
    rows = store.wortbeitraege_by_ids([wid for wid, _ in kandidaten])
    texte = {r["id"]: " — ".join(t for t in (r.get("top"), r.get("text")) if t)
             for r in rows}
    return _rerank_kontext(query, [(wid, texte[wid]) for wid, _ in kandidaten if wid in texte],
                           top_k)


#: Zusagen ohne Inhalt: „Ich sichere eine Antwort zu Protokoll zu", „wird
#: mitgenommen". Das ist Verfahren, keine Selbstverpflichtung — als Beleg
#: unter einer Antwort wäre es Füllmaterial. Am Bestand gemessen betrifft das
#: rund ein Viertel der 1.437 Zusagen.
_HOHLE_ZUSAGE = re.compile(
    r"(zu\s+protokoll|schriftlich\w*\s+(beantwortung|antwort)|"
    r"beantwortung\s+(der|dieser)\s+frage|nach(zu)?reichen|nachgereicht|"
    r"mitgenommen|mitnehmen|werde\s+sich\s+informieren|"
    r"sich\s+\w*\s?informieren\s+werde|zur\s+kenntnis\s+geben)", re.IGNORECASE)

#: Strenger als die anderen Zusatzkanäle: Ein Kanal, der NUR Zusagen zeigt,
#: darf keine thematisch schiefen liefern — beim Ärztemangel rutschte sonst
#: eine Kita-Fachkräfte-Zusage durch (gemessen 12.08.).
ZUSAGE_RERANK_MIN = float(os.environ.get("COUNCIL_ZUSAGE_RERANK_MIN", "-0.5"))


def search_zusagen(store, query: str, expanded: str, top_k: int = 2,
                   min_score: float = 0.42) -> list[tuple]:
    """Zusagen der Verwaltung zum Thema → ``[(wb_id, score)]``.

    Eigener Kanal, weil sie im allgemeinen Debatten-Ranking untergehen: Über
    sechs Testfragen war genau EINER von 19 Belegen eine Zusage — und selbst
    auf „Was hat die Verwaltung zum Stadion zugesagt?" kam keine, obwohl
    einschlägige existieren („Die Stadt leistet einen Eigenkapitalzuschuss in
    Höhe von bis zu 15 Millionen Euro"). Grund: Zusagen sind kurz und nüchtern
    formuliert und verlieren jedes Duell gegen ausführliche Reden.

    Dabei sind sie der besondere Stoff: eine Selbstverpflichtung der
    Verwaltung, nachlesbar mit Datum. 1.437 stecken im Bestand.

    Gleiche Torwächter-Logik wie die anderen Kanäle — lieber leer als Rauschen.
    """
    ids_zusage = set(store.wortbeitrag_ids_nach_art("zusage"))
    if not ids_zusage:
        return []
    best: dict[int, float] = {}
    try:
        ids, mat = _wb_matrix(store)
        if not ids:
            return []
        qv = embed([expanded])[0]
        scores = mat @ qv
        for wid, s in zip(ids, scores):
            if wid in ids_zusage and s >= min_score:
                best[wid] = float(s)
    except Exception:  # noqa: BLE001 — ohne fastembed kein Zusagen-Kanal
        return []
    kandidaten = sorted(best.items(), key=lambda x: -x[1])[:max(top_k * 6, 16)]
    rows = store.wortbeitraege_by_ids([wid for wid, _ in kandidaten])
    texte = {r["id"]: " — ".join(t for t in (r.get("top"), r.get("text")) if t)
             for r in rows if not _HOHLE_ZUSAGE.search(r.get("text") or "")}
    return _rerank_kontext(query, [(wid, texte[wid]) for wid, _ in kandidaten if wid in texte],
                           top_k, min_rerank=ZUSAGE_RERANK_MIN)


def search_wortbeitraege_von_person(store, query: str, nachname: str,
                                    top_k: int = 10) -> list[dict]:
    """Personen-Fragetyp: die zur Frage passenden Wortbeiträge EINER Person.
    Alle Beiträge des Sprechers sind die Kandidaten (per Nachname, ≤120),
    der Cross-Encoder wählt die einschlägigen. Ist die Frage so allgemein,
    dass nichts den Cutoff schafft („Was sagt X?"), kommen die neuesten
    Beiträge — die Person wurde ausdrücklich gefragt, leer wäre falsch."""
    roh = store.wortbeitraege_von_sprecher(nachname)
    if not roh:
        return []
    paare = [(r["id"], " — ".join(t for t in (r.get("top"), r.get("text")) if t))
             for r in roh]
    bestaetigt = _rerank_kontext(query, paare, top_k)
    by_id = {r["id"]: r for r in roh}
    rows = [by_id[i] for i, _ in bestaetigt if i in by_id]
    if not rows:
        rows = roh[:min(6, top_k)]  # neueste zuerst (Store sortiert absteigend)
    return rows


#: Kandidatenfeld des Fraktions-Kanals — und der Grund, warum es groß sein muss:
#: Der frühere Deckel von 120 war ein GLOBALES Top-N, geschnitten VOR der
#: Fraktions-Auswahl. Genau dort verlieren die Beiträge zur Sache gegen das
#: bloße Wortfeld. Auf „Was ist die Baumschutzsatzung und wie kam es zu ihr?"
#: lagen 638 Beiträge über der Schwelle; die Reden aus den entscheidenden
#: Sitzungen (Behrens/SPD 0.507, Woltmann/CDU 0.505, Adler/BSW 0.504) standen
#: unter dem Schnitt, während Baum-Beiträge zu ganz anderen Tagesordnungspunkten
#: darüber lagen. Der Baustein zeigte danach je Fraktion EINEN Beitrag von
#: 2019/2021, CDU/BSW/FDP galten als „keine passenden Wortbeiträge" — obwohl
#: alle drei in der Satzungs-Debatte geredet hatten (Tims Befund 21.08.2026).
#: Deshalb: großes Feld, Auswahl je Fraktion, Torwächter entscheidet über die
#: Einschlägigkeit. Der Cross-Encoder kann das auch — er bewertete dieselben
#: 2025er-Reden mit −0.11 bis +0.35, deutlich über dem Cutoff.
WB_FRAKTION_POOL = int(os.environ.get("COUNCIL_WB_FRAKTION_POOL", "600"))
#: Deckel auf die Zahl der Fraktions-Töpfe (nach bestem Vektor-Score). Bremse
#: gegen die Rerank-Kosten: gemessen ~32 ms je Paar, also ~3 s bei 20 Töpfen ×
#: 5 Beiträgen. Wer hier hochgeht, bezahlt es in Latenz des Bausteins.
WB_FRAKTION_LABELS = int(os.environ.get("COUNCIL_WB_FRAKTION_LABELS", "20"))


def search_wortbeitraege_je_fraktion(store, query: str, expanded: str,
                                     je_partei: int = 5, min_score: float = 0.45) -> list[tuple]:
    """Kandidaten für den Parteien-Baustein: FRAKTIONS-BEWUSST gesammelt.
    Das globale Top-24 der normalen Suche bestand zur Hälfte aus Beiträgen
    ohne Fraktion (Verwaltungsantworten, Referenten) — übrig blieben 1–3
    Beiträge je Partei, die „Parteimeinung" war real eine Einzel-Paraphrase
    (Tims Befund 10.08.). Hier: Vektor-Scan → Beiträge ohne Fraktion raus →
    je Fraktion die besten ``je_partei`` → EIN Torwächter-Rerank über alle.

    Die Auswahl je Fraktion läuft über das GANZE Kandidatenfeld (siehe
    ``WB_FRAKTION_POOL``) — ein globaler Vorschnitt hätte die Beiträge zur
    Sache gegen das Wortfeld verloren."""
    from council.qa import _fraktions_label

    ids, mat = _wb_matrix(store)
    if not ids:
        return []
    qv = embed([expanded])[0]
    scores = mat @ qv
    kandidaten = sorted(
        ((wid, float(s)) for wid, s in zip(ids, scores) if s >= min_score),
        key=lambda x: -x[1])[:WB_FRAKTION_POOL]
    rows = store.wortbeitraege_by_ids([wid for wid, _ in kandidaten])
    text_von = {r["id"]: " — ".join(t for t in (r.get("top"), r.get("text")) if t) for r in rows}
    partei_von = {r["id"]: _fraktions_label(r.get("partei")) for r in rows}
    # Welche Fraktionen überhaupt antreten: die mit dem besten Einzeltreffer.
    bester: dict[str, float] = {}
    for wid, s in kandidaten:
        label = partei_von.get(wid)
        if label and s > bester.get(label, -1.0):
            bester[label] = s
    zugelassen = {label for label, _ in
                  sorted(bester.items(), key=lambda kv: -kv[1])[:WB_FRAKTION_LABELS]}
    je_gruppe: dict[str, int] = {}
    auswahl: list[tuple] = []
    for wid, s in kandidaten:
        label = partei_von.get(wid)
        if not label or label not in zugelassen:
            continue  # Verwaltung/Einwohner verstopfen keine Fraktions-Slots
        if je_gruppe.get(label, 0) >= je_partei:
            continue
        je_gruppe[label] = je_gruppe.get(label, 0) + 1
        auswahl.append((wid, s))
    # Meinungs-Framing für den Torwächter: Auf eine Sachstands-Frage („Wie ist
    # der Stand …?") bewertet der Cross-Encoder Meinungs-Reden als wenig
    # relevant und ließ kaum Fraktions-Beiträge durch (Tims Befund 10.08.) —
    # der Baustein fragt aber genau nach den Positionen.
    return _rerank_kontext(f"Positionen und Meinungen der Fraktionen zu: {query}",
                           [(wid, text_von[wid]) for wid, _ in auswahl],
                           top_k=len(auswahl))


def embed_wortbeitraege_missing(store) -> int:
    """Ein Vektor je neuem Wortbeitrag (Texte sind auf 2000 Zeichen gekappt,
    Chunking unnötig). Gerufen vom Extraktions-Skript und als Backstop von
    embed_decisions.py."""
    import hashlib

    todo = store.wortbeitraege_missing_embeddings()
    n = 0
    for batch_start in range(0, len(todo), 64):
        batch = todo[batch_start:batch_start + 64]
        texts = [" — ".join(t for t in (w["top"], w["text"]) if t)[:2000] for w in batch]
        vecs = embed(texts)
        for w, text, vec in zip(batch, texts, vecs):
            h = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
            store.replace_wortbeitrag_embedding(w["id"], h, vec.tobytes())
            n += 1
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
