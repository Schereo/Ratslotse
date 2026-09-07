"""Chunks, Embeddings, Volltextindex und Nachbarschaften über Städte hinweg.

**Was hier entsteht, ist der eigentliche Vergleich.** Erst wenn ein
Oldenburger Beschluss und ein Osnabrücker Antrag im selben Vektorraum liegen,
kann der eine den anderen finden — und zwar in beide Richtungen: „Was haben
andere zu unserer Sache gemacht?" und „Was haben wir, was andere nicht haben?"
sind dieselbe Nachbarschaftsabfrage mit vertauschten Rollen.

**Das Modell steht im Schlüssel.** ``chunk_embeddings`` und
``object_embeddings`` sind auf ``(…, model)`` eindeutig, ``neighbors``
ebenfalls. So liegt ein besseres Modell neben dem heutigen, und ein Eval
vergleicht beide, bevor eins gewinnt — statt dass ein Wechsel den alten Index
löscht.

**fastembed ist bewusst keine Web-Abhängigkeit** (Wurzel-``CLAUDE.md``): Der
Import steht in den Funktionen, und nur Cron und Ops-Skripte rufen sie. Der
Web-Dienst liest ausschließlich die fertigen Tabellen.
"""
from __future__ import annotations

import logging
import os
import time

from typing import TYPE_CHECKING

from council.cities.store import CitiesStore, text_hash

if TYPE_CHECKING:      # numpy ist zur Laufzeit erst im Cron da, nicht im Web
    import numpy as np

logger = logging.getLogger("council.cities.index")

#: Dasselbe Modell wie für die Oldenburger Beschlüsse — sonst lägen die beiden
#: Bestände in verschiedenen Räumen und könnten einander nicht finden.
EMBED_MODEL = os.environ.get("COUNCIL_EMBED_MODEL",
                             "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

CHUNK_SIZE = 1100
CHUNK_OVERLAP = 120
MAX_CHUNKS = 8
#: Kürzer als das ist ein Fenster nur Score-Verwässerung — außer es ist das
#: einzige (dieselbe Überlegung wie in ``council/embeddings.py``).
MIN_CHUNK_CHARS = 200

#: Ab dieser Ähnlichkeit gilt ein Papier als Nachbar. Der Median der
#: Ähnlichkeit zweier beliebiger deutscher Verwaltungstexte liegt bei 0,70
#: (Probelauf, gemessen) — die Schwelle trennt also nicht Themen, sondern nur
#: offensichtlich Unverwandtes ab. Was wirklich zusammengehört, entscheidet die
#: Reihenfolge, nicht die Schwelle.
NEIGHBOR_MIN_SCORE = 0.55
NEIGHBOR_TOP_K = 8


def chunk(text: str) -> list[tuple[int, str, int, int]]:
    """``(index, text, start, ende)`` — überlappende Fenster über den Volltext."""
    sauber = (text or "").strip()
    if not sauber:
        return []
    out: list[tuple[int, str, int, int]] = []
    schritt = CHUNK_SIZE - CHUNK_OVERLAP
    for start in range(0, len(sauber), schritt):
        stueck = sauber[start:start + CHUNK_SIZE]
        beschnitten = stueck.strip()
        if beschnitten and (len(beschnitten) >= MIN_CHUNK_CHARS or start == 0):
            out.append((len(out), beschnitten, start, start + len(stueck)))
        if len(out) >= MAX_CHUNKS:
            break
    return out


def object_text(paper: dict, annotation: dict | None, text: str | None) -> str:
    """Der Text, aus dem der Objektvektor entsteht.

    Titel plus die Zusammenfassung des Modells plus das Instrument — dieselbe
    Form wie im Probelauf, damit die dort gemessenen Nachbarschaften
    vergleichbar bleiben. Ohne Annotation tritt der Textanfang an ihre Stelle.
    """
    teile = [paper.get("name") or ""]
    if annotation:
        teile += [annotation.get("summary") or "", annotation.get("instrument") or ""]
    elif text:
        teile.append(text[:400])
    return " ".join(t for t in teile if t).strip()[:600]


def _embed(texte: list[str]) -> np.ndarray:
    """L2-normierte Vektoren — Skalarprodukt ist damit der Kosinus."""
    from council.embeddings import embed  # lazy: fastembed ist keine Web-Abhängigkeit
    return embed(texte)


def build_chunks(main: CitiesStore, body_id: str | None = None,
                 limit: int | None = None) -> int:
    """Volltexte in Fenster schneiden — für alles, was noch keine hat."""
    n = 0
    with main.transaction():
        for datei in main.files_with_text(body_id=body_id, limit=limit):
            text = main.text_for_file_any(datei["id"])
            if not text:
                continue
            stuecke = chunk(text)
            if not stuecke:
                continue
            vorhandene = {c["chunk_idx"]: c["text_hash"] for c in main.chunks_for_file(datei["id"])}
            if all(vorhandene.get(i) == text_hash(t) for i, t, _s, _e in stuecke) \
                    and len(vorhandene) == len(stuecke):
                continue
            main.put_chunks(datei["id"], stuecke)
            n += len(stuecke)
    return n


def embed_chunks(main: CitiesStore, model: str = EMBED_MODEL,
                 batch: int = 256, limit: int | None = None) -> int:
    """Vektoren für alle Chunks, denen dieses Modell noch fehlt."""
    offen = main.chunks_without_embedding(model, limit)
    if not offen:
        return 0
    logger.info("%s Chunks einzubetten", len(offen))
    n = 0
    for start in range(0, len(offen), batch):
        block = offen[start:start + batch]
        vektoren = _embed([c["chunk_text"] for c in block])
        main.put_chunk_embeddings([
            (c["file_id"], c["chunk_idx"], model, c["text_hash"], vektoren[i].tobytes())
            for i, c in enumerate(block)])
        n += len(block)
        if start and start % (batch * 8) == 0:
            logger.info("  %s/%s", n, len(offen))
    return n


def embed_objects(main: CitiesStore, model: str = EMBED_MODEL,
                  body_id: str | None = None, batch: int = 256) -> int:
    """Ein Vektor je Papier — die Ebene, auf der Nachbarschaften entstehen."""
    from council.cities.annotators import get as get_annotator

    ann = get_annotator("classify")
    papiere = main.papers(body_id=body_id)
    annotationen = main.annotations_for(ann.key, ann.version)
    bekannt = main.object_embedding_hashes(model)

    offen: list[tuple[str, str, str]] = []   # (id, text, hash)
    for p in papiere:
        text = object_text(p, annotationen.get(p["id"]), main.text_for_paper(p["id"]))
        if not text:
            continue
        h = text_hash(text)
        if bekannt.get(p["id"]) != h:
            offen.append((p["id"], text, h))
    if not offen:
        return 0

    logger.info("%s Objektvektoren", len(offen))
    for start in range(0, len(offen), batch):
        block = offen[start:start + batch]
        vektoren = _embed([t for _i, t, _h in block])
        with main.transaction():
            for i, (kennung, _t, h) in enumerate(block):
                main.put_object_embedding("paper", kennung, model, h, vektoren[i].tobytes())
    return len(offen)


def build_fts(main: CitiesStore, body_id: str | None = None) -> int:
    """Volltextindex über Titel, Aktenzeichen, Text und Zusammenfassung."""
    from council.cities.annotators import get as get_annotator

    ann = get_annotator("classify")
    annotationen = main.annotations_for(ann.key, ann.version)
    n = 0
    for p in main.papers(body_id=body_id):
        a = annotationen.get(p["id"]) or {}
        main.fts_upsert(p["id"], p["body_id"], p["name"], p.get("reference"),
                        main.text_for_paper(p["id"]), a.get("summary"))
        n += 1
    return n


def build_neighbors(main: CitiesStore, model: str = EMBED_MODEL,
                    top_k: int = NEIGHBOR_TOP_K,
                    min_score: float = NEIGHBOR_MIN_SCORE,
                    cross_body_only: bool = True) -> int:
    """Für jedes Papier die nächsten Papiere ANDERER Städte.

    **Warum nur fremde.** Diese Tabelle beantwortet genau eine Frage: „Was
    haben andere zu dieser Sache gemacht?" Nachbarn in derselben Stadt
    beantworten sie nicht — und sie verdrängen die fremden aus den besten
    acht: Gemessen am Bestand zeigten 3.830 von 5.596 Oldenburger Kanten auf
    Oldenburg selbst, sodass manche Vorlage gar keinen fremden Nachbarn
    behielt. Ähnlichkeit innerhalb Oldenburgs rechnet ohnehin
    ``scripts/embed_decisions.py`` in die Rats-Datenbank.

    Rechnet in Blöcken wie ``scripts/embed_decisions.py``: Bei 30.000 Papieren
    sind das 900 Millionen Skalarprodukte, in Blöcken von 256 Zeilen aber
    Sekunden, nicht Minuten.
    """
    import numpy as np

    ids, bodies, puffer = main.object_embeddings(model)
    if len(ids) < 2:
        return 0
    matrix = np.frombuffer(puffer, dtype="float32").reshape(len(ids), -1)
    stadt = np.array(bodies)
    logger.info("Nachbarschaften über %s Papiere aus %s Städten%s",
                len(ids), len(set(bodies)), " (nur stadtübergreifend)" if cross_body_only else "")

    n = 0
    t0 = time.time()
    for start in range(0, len(ids), 256):
        block = matrix[start:start + 256] @ matrix.T
        zeilen: list[tuple[str, list[tuple[str, str, float]]]] = []
        for zeile_idx, zeile in enumerate(block):
            i = start + zeile_idx
            zeile = zeile.copy()
            zeile[i] = -1.0                       # sich selbst nie
            if cross_body_only:
                zeile[stadt == stadt[i]] = -1.0   # und niemanden aus derselben Stadt
            moeglich = int((zeile > -1.0).sum())
            if not moeglich:
                zeilen.append((ids[i], []))
                continue
            k = min(top_k, moeglich)
            idx = np.argpartition(-zeile, k - 1)[:k] if k < len(zeile) else np.arange(len(zeile))
            idx = idx[np.argsort(-zeile[idx])]
            treffer = [("paper", ids[j], float(zeile[j])) for j in idx
                       if zeile[j] >= min_score]
            zeilen.append((ids[i], treffer))
        with main.transaction():
            for a_id, treffer in zeilen:
                main.replace_neighbors(model, "paper", a_id, treffer)
                n += len(treffer)
    logger.info("%s Kanten in %.0fs", n, time.time() - t0)
    return n


def run(main: CitiesStore, body_id: str | None = None,
        model: str = EMBED_MODEL) -> dict:
    """Alle vier Schritte — in der Reihenfolge, in der sie aufeinander bauen."""
    zahlen = {
        "chunks": build_chunks(main, body_id),
        "chunk_vectors": embed_chunks(main, model),
        "object_vectors": embed_objects(main, model, body_id),
        "fts": build_fts(main, body_id),
    }
    # Nachbarschaften gehen IMMER über alle Städte — eine Stadt für sich
    # allein hat keine Nachbarn im Sinne dieses Speichers.
    zahlen["neighbors"] = build_neighbors(main, model)
    return zahlen
