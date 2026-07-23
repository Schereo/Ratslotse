"""Verwandte Themen — Nachbarschaften zwischen Entitäten (``council_entity_related``).

Zwei Quellen, die bewusst NICHT vermischt werden:

``belegt``
    Entitäten, die gemeinsam in denselben Beschlüssen vorkommen (Co-Occurrence).
    Das ist der Sachzusammenhang: Fliegerhorst ── Entlastungsstraße.

``aehnlich``
    Semantische Nachbarn aus den vorhandenen Beschluss-Embeddings, nur zum
    Auffüllen auf ``top_k``. Findet "die gleiche Art Sache", nicht denselben
    Vorgang: Schramperweg ── Schützenweg. Deutlich schwächer, deshalb eigener Typ.

Die Konstanten unten stammen aus fünf Messläufen gegen die Produktionsdaten
(23.07.2026), nicht aus Plausibilität — gemessen wurde jeweils gegen Signale, die
das bewertete Verfahren selbst nicht benutzt (Themenfeld-Profile, Embedding-Zentroide)
mit einer Baseline aus 4.000 zufälligen Entitätspaaren:

* Ob roh gezählt, Jaccard, PMI oder gedämpft normiert wird, ändert das Ergebnis
  praktisch nicht (Themenfeld-Lift 4,1× überall) — die LLM-Extraktion liefert
  höchstens 4 Entitäten je Beschluss, da gibt es nichts zu normieren. Deshalb die
  einfachste Variante: zählen, Mindestevidenz, Jaccard nur zum Sortieren.
* Nur 11 % aller Beschlüsse nennen überhaupt zwei Entitäten. Der Textabgleich
  (:func:`text_matches`) hebt die Abdeckung von 43 % auf 61 %, ohne LLM-Aufruf.
* Er zieht dabei Gremien herein (Sozialausschuss +184 Nennungen), die als Naben
  mit allem verbunden wären — :func:`is_structural` hält sie draußen.
* Und er erzeugt Alias-Kanten ("Hallensichel-Ost" ── "Hallensichel"), die es in den
  LLM-Links kein einziges Mal gab — :func:`is_alias` unterdrückt sie.

numpy wird wie in :mod:`council.embeddings` erst *innerhalb* der Funktionen
importiert: der Web-Service liest nur die fertige Tabelle und soll ohne numpy
laufen. Gerechnet wird ausschließlich im Backfill
(``scripts/build_entity_relations.py``).
"""
from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict

logger = logging.getLogger("council.related")

TOP_K = 5              # so viele Nachbarn hält die UI je Thema vor
MIN_EVIDENCE = 2       # gemeinsame Beschlüsse für eine belegte Kante
FIT_THRESHOLD = 0.45   # thematische Passung neuer Textfundstellen (Embedding-Nähe)
MIN_NAME_LEN = 6       # kürzere Namen matchen zu viel Beiläufiges
ALIAS_JACCARD = 0.30   # ab hier gilt ein Namens-Teilstring-Paar als dieselbe Sache

# Gremien und Verfahrensstationen. Sie stehen in fast jedem Beschlusstext, sind aber
# kein Thema — im Graph würden sie zu Naben, die mit allem verbunden sind.
_STRUCTURAL = re.compile(
    r"(ausschuss|beirat|rat der stadt|stadtrat|ortsrat|verwaltungsvorstand"
    r"|kommission|fraktion|gremium|ratsversammlung)",
    re.I,
)


def is_structural(name: str, committee_names: set[str] | None = None) -> bool:
    """True für Gremien/Verfahrensstationen, die keine inhaltlichen Themen sind."""
    if _STRUCTURAL.search(name or ""):
        return True
    return bool(committee_names) and (name or "").strip().lower() in committee_names


def is_alias(name_a: str, name_b: str, jaccard: float) -> bool:
    """True, wenn zwei Entitäten derselbe Gegenstand unter zwei Namen sind.

    Erkennungsmerkmal: ein Name ist Teilstring des anderen UND die Beschlussmengen
    überlappen stark. Die Schwelle stammt aus der Durchsicht aller 121
    Teilstring-Paare — sie trennt zwei Gruppen sauber:

    * ab Jaccard 0,30 praktisch nur Dubletten der Entitäten-Extraktion:
      "Untere Nadorster Straße"/"Nadorster Straße", "Hafen"/"Hafen der Stadt
      Oldenburg", "Eigenbetrieb Gebäudewirtschaft und Hochbau"/"Gebäudewirtschaft
      und Hochbau" — als Nachbarschaft angezeigt wäre das nur redundant;
    * darunter überwiegend echte Information: "Fliegerhorst"/"Grundschule
      Fliegerhorst", "Stadtmuseum"/"Tiefgarage Am Stadtmuseum",
      "Kreyenbrück"/"IGS Kreyenbrück" — die gehören in die Liste.

    Unterdrückt wird nur die *Kante*. Die Dubletten selbst bleiben bestehen; sie
    sind ein Problem der Entitäten-Extraktion und wären dort zu beheben.
    """
    if jaccard < ALIAS_JACCARD:
        return False
    a = re.sub(r"[^a-zäöüß0-9]", "", (name_a or "").lower())
    b = re.sub(r"[^a-zäöüß0-9]", "", (name_b or "").lower())
    if not a or not b:
        return False
    return a in b or b in a


def text_matches(entities: list[dict], decisions: list[dict],
                 committee_names: set[str] | None = None) -> dict[int, set[int]]:
    """Entitäten, die im Beschlusstext stehen, aber nicht verlinkt sind.

    ``entities`` = [{id, name, …}], ``decisions`` = [{id, text}]. Liefert
    ``decision_id -> {entity_id}``. Gremien werden übersprungen; die Wortgrenzen
    verhindern, dass "Eversten" in "Everstenholz" trifft.
    """
    cands = {
        e["id"]: e["name"] for e in entities
        if len(e["name"] or "") >= MIN_NAME_LEN and not is_structural(e["name"], committee_names)
    }
    patterns = {
        i: re.compile(r"(?<![\wäöüß])" + re.escape(n) + r"(?![\wäöüß])", re.I)
        for i, n in cands.items()
    }
    lowered = {i: n.lower() for i, n in cands.items()}

    out: dict[int, set[int]] = defaultdict(set)
    for d in decisions:
        text = d.get("text") or ""
        if not text.strip():
            continue
        low = text.lower()
        for i, needle in lowered.items():
            # billiger Substring-Vorfilter, dann erst die teure Wortgrenzen-Prüfung
            if needle in low and patterns[i].search(text):
                out[d["id"]].add(i)
    return out


def _entity_centroids(ent_decs: dict[int, set[int]], vectors: dict[int, "object"]):
    """Semantischer Schwerpunkt je Entität (Mittel ihrer Beschlussvektoren)."""
    import numpy as np

    out = {}
    for e, decs in ent_decs.items():
        vs = [vectors[d] for d in decs if d in vectors]
        if not vs:
            continue
        v = np.mean(vs, axis=0)
        norm = float(np.linalg.norm(v))
        if norm > 0:
            out[e] = v / norm
    return out


def load_vectors(rows) -> dict[int, "object"]:
    """(decision_id, blob) → {decision_id: L2-normalisierter float32-Vektor}."""
    import numpy as np

    return {r[0]: np.frombuffer(r[1], dtype="float32") for r in rows}


def cooccurrence(dec_ents: dict[int, set[int]]) -> Counter:
    """Zählt, wie oft je zwei Entitäten gemeinsam in einem Beschluss stehen."""
    pairs: Counter = Counter()
    for ents in dec_ents.values():
        ordered = sorted(ents)
        for i in range(len(ordered)):
            for j in range(i + 1, len(ordered)):
                pairs[(ordered[i], ordered[j])] += 1
    return pairs


def build(entities: list[dict], links: list[tuple], decisions: list[dict],
          vectors: dict, committee_names: set[str] | None = None,
          top_k: int = TOP_K, min_evidence: int = MIN_EVIDENCE,
          fit_threshold: float = FIT_THRESHOLD, use_text_match: bool = True) -> tuple[list[tuple], dict]:
    """Berechnet die Nachbarschaften.

    Gibt ``(rows, stats)`` zurück; ``rows`` = (slug, neighbor_slug, rel_type, rank,
    score, evidence) — beidseitig, damit die Themen-Seite ohne OR-Join auskommt.
    """
    by_id = {e["id"]: e for e in entities}
    name = {i: e["name"] for i, e in by_id.items()}
    slug = {i: e["slug"] for i, e in by_id.items()}
    structural = {i: is_structural(e["name"], committee_names) for i, e in by_id.items()}

    dec_ents: dict[int, set[int]] = defaultdict(set)
    ent_decs: dict[int, set[int]] = defaultdict(set)
    for entity_id, decision_id in links:
        if entity_id in by_id and not structural[entity_id]:
            dec_ents[decision_id].add(entity_id)
            ent_decs[entity_id].add(decision_id)

    stats = {"llm_links": sum(len(v) for v in dec_ents.values()), "text_added": 0,
             "text_rejected": 0, "alias_suppressed": 0}

    centroids = _entity_centroids(ent_decs, vectors) if vectors else {}

    # --- Textabgleich: verpasste Nennungen ergänzen, thematisch geprüft ---------
    if use_text_match:
        found = text_matches(entities, decisions, committee_names)
        for decision_id, ent_ids in found.items():
            for entity_id in ent_ids:
                if entity_id in dec_ents.get(decision_id, ()):
                    continue
                if structural.get(entity_id, False):
                    continue
                vec = vectors.get(decision_id)
                centroid = centroids.get(entity_id)
                if vec is not None and centroid is not None:
                    if float(vec @ centroid) < fit_threshold:
                        stats["text_rejected"] += 1
                        continue
                elif centroids:
                    # Ohne Vektor lässt sich die Passung nicht prüfen — nicht raten.
                    stats["text_rejected"] += 1
                    continue
                dec_ents[decision_id].add(entity_id)
                ent_decs[entity_id].add(decision_id)
                stats["text_added"] += 1

    # --- belegte Kanten --------------------------------------------------------
    pairs = cooccurrence(dec_ents)
    stats["pairs_raw"] = len(pairs)

    proven: dict[int, list[tuple]] = defaultdict(list)
    kept_pairs = 0
    for (a, b), w in pairs.items():
        if w < min_evidence:
            continue
        union = len(ent_decs[a]) + len(ent_decs[b]) - w
        jaccard = w / union if union else 0.0
        if is_alias(name[a], name[b], jaccard):
            stats["alias_suppressed"] += 1
            continue
        proven[a].append((jaccard, w, b))
        proven[b].append((jaccard, w, a))
        kept_pairs += 1
    stats["pairs_proven"] = kept_pairs

    # --- Auffüllung aus den Embeddings ----------------------------------------
    similar: dict[int, list[tuple]] = defaultdict(list)
    if centroids and top_k > 0:
        import numpy as np

        ids = sorted(centroids)
        matrix = np.stack([centroids[i] for i in ids])
        sims = matrix @ matrix.T
        np.fill_diagonal(sims, -1.0)
        for row, entity_id in enumerate(ids):
            if structural.get(entity_id, False):
                continue
            order = np.argsort(-sims[row])[: top_k * 3]
            for col in order:
                other = ids[int(col)]
                if structural.get(other, False):
                    continue
                # Dubletten auch hier fernhalten: eine als Alias verworfene Kante
                # darf nicht über die Auffüllung zurückkommen (semantisch sind
                # Namensvarianten naturgemäß die nächsten Nachbarn).
                shared = len(ent_decs[entity_id] & ent_decs[other])
                union = len(ent_decs[entity_id] | ent_decs[other])
                if shared and is_alias(name[entity_id], name[other], shared / union):
                    stats["alias_suppressed"] += 1
                    continue
                similar[entity_id].append((float(sims[row, int(col)]), other))

    # --- zusammenführen: belegt zuerst, dann auffüllen -------------------------
    rows: list[tuple] = []
    covered_proven = 0
    for entity_id in by_id:
        if structural.get(entity_id, False):
            continue
        chosen: list[tuple] = []
        seen: set[int] = set()
        for jaccard, w, other in sorted(proven.get(entity_id, []), key=lambda x: (-x[0], -x[1])):
            if len(chosen) >= top_k:
                break
            chosen.append(("belegt", round(jaccard, 4), w, other))
            seen.add(other)
        if chosen:
            covered_proven += 1
        for score, other in sorted(similar.get(entity_id, []), reverse=True):
            if len(chosen) >= top_k:
                break
            if other in seen:
                continue
            chosen.append(("aehnlich", round(score, 4), 0, other))
            seen.add(other)
        for rank, (rel_type, score, evidence, other) in enumerate(chosen):
            rows.append((slug[entity_id], slug[other], rel_type, rank, score, evidence))

    inhaltlich = sum(1 for i in by_id if not structural[i])
    stats["entities"] = inhaltlich
    stats["structural"] = len(by_id) - inhaltlich
    stats["with_proven"] = covered_proven
    stats["coverage_proven"] = round(covered_proven / inhaltlich, 3) if inhaltlich else 0.0
    stats["rows"] = len(rows)
    return rows, stats
