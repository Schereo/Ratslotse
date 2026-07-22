#!/usr/bin/env python3
"""Eval-Suite fuer die KI-Frage ("Frag den Stadtrat").

Misst zwei Dinge gegen handgelabelte Fragen (``cases_qa.json``, Ground Truth
aus der echten Prod-Datenbank):

1. **Retrieval** — findet die Hybrid-Suche (Vektor + BM25 + Reranker) die
   erwarteten Beschluesse? Metriken: Trefferquote (>= 1 expected id in den
   Quellen) und MRR (mittlerer Kehrwert des Rangs des ersten Treffers).
2. **Antwort-A/B** — dieselben Kandidaten, zwei Antwort-Laeufe: einmal MIT
   Tragweite-Hinweis im Kontext (#258) und einmal OHNE (impact-Felder vor dem
   Prompt entfernt = Stand vor #258). Je Arm: zitiert die Antwort >= 1
   erwarteten Beschluss, wie oft zitiert sie Formalien (impact <= 15), und
   fuehrt sie mit einer Formalie an?

Braucht die echte ``council.sqlite`` (Embeddings + FTS + Reranker-Modell) und
``OPENROUTER_API_KEY`` — praktisch: auf dem Server laufen lassen::

    python eval/run_qa.py --rate-missing --save

``--rate-missing`` bewertet vorab die Tragweite der Antwort-Kandidaten ohne
Score (solange der grosse Backfill laeuft), damit der MIT-Arm echte Hinweise
sieht. Die Metrik-Logik ist offline testbar (``evaluate`` bekommt injizierte
Funktionen, siehe tests/test_eval_harness.py).
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from eval import harness  # noqa: E402

# Gleiche Groessen wie der /council/ask-Endpoint (web/backend/app/routers/council.py).
TOP_K = 40
ANSWER_N = 20
FORMALITY_MAX = 15  # deckungsgleich mit dem "Tragweite: gering"-Marker in council/qa.py


# --------------------------------------------------------------------------- #
# Metrik-Kern — pure Funktionen, offline testbar
# --------------------------------------------------------------------------- #

def _first_rank(retrieved: list[int], expected: set[int]) -> int | None:
    for i, rid in enumerate(retrieved, start=1):
        if rid in expected:
            return i
    return None


def _is_formality(impact_map: dict[int, int | None], rid: int) -> bool:
    v = impact_map.get(rid)  # impact 0 ist eine echte Formalie — kein `or`-Falsy!
    return v is not None and v <= FORMALITY_MAX


def _arm_stats(per_case: list[dict], arm: str) -> dict:
    cited_lists = [c[f"cited_{arm}"] for c in per_case]
    impacts = [c["impact_of"] for c in per_case]
    cite_expected = sum(1 for c, cl in zip(per_case, cited_lists)
                        if set(cl) & set(c["expected"]))
    formality = sum(1 for cl, imp in zip(cited_lists, impacts)
                    for rid in cl if _is_formality(imp, rid))
    lead_formality = sum(1 for cl, imp in zip(cited_lists, impacts)
                         if cl and _is_formality(imp, cl[0]))
    n_cited = sum(len(cl) for cl in cited_lists)
    return {
        "cite_expected_rate": round(cite_expected / len(per_case), 4) if per_case else 0.0,
        "citations": n_cited,
        "formality_citations": formality,
        "lead_formality_cases": lead_formality,
    }


def evaluate(
    cases: list[dict],
    retrieve: Callable[[dict], list[int]],
    answer: Callable[[dict, bool], list[int]],
    impact_of: Callable[[dict], dict[int, int | None]],
) -> dict:
    """Kern-Auswertung mit injizierten Funktionen.

    ``retrieve(case)``   -> Kandidaten-ids in Relevanz-Reihenfolge.
    ``answer(case, with_impact)`` -> zitierte ids in Zitier-Reihenfolge.
    ``impact_of(case)``  -> {id: impact | None} fuer die Kandidaten des Falls.
    """
    per_case: list[dict] = []
    for case in cases:
        expected = set(case["expected_ids"])
        retrieved = retrieve(case)
        rank = _first_rank(retrieved, expected)
        per_case.append({
            "id": case["id"],
            "expected": case["expected_ids"],
            "retrieved_n": len(retrieved),
            "first_expected_rank": rank,
            "cited_mit": answer(case, True),
            "cited_ohne": answer(case, False),
            "impact_of": impact_of(case),
        })

    hits = [c for c in per_case if c["first_expected_rank"] is not None]
    mrr = sum(1.0 / c["first_expected_rank"] for c in hits) / len(per_case) if per_case else 0.0
    result = {
        "suite": "qa",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "cases": len(per_case),
        "retrieval": {
            "hit_rate": round(len(hits) / len(per_case), 4) if per_case else 0.0,
            "mrr": round(mrr, 4),
        },
        "arms": {
            "mit_tragweite": _arm_stats(per_case, "mit"),
            "ohne_tragweite": _arm_stats(per_case, "ohne"),
        },
        "details": [
            {k: v for k, v in c.items() if k != "impact_of"} for c in per_case
        ],
    }
    return result


def print_qa_report(result: dict) -> None:
    line = "-" * 60
    r = result["retrieval"]
    print(f"\n{line}")
    print(f"  Suite     : qa  ({result['cases']} Fragen)")
    print(f"  Retrieval : Trefferquote {r['hit_rate']:.0%} · MRR {r['mrr']:.2f}")
    print(f"  {'Antwort-Arm':18} {'zitiert erwartet':>17} {'Zitate':>7} {'Formalie zitiert':>17} {'fuehrt m. Formalie':>19}")
    for name, a in result["arms"].items():
        print(f"  {name:18} {a['cite_expected_rate']:>16.0%} {a['citations']:>7} "
              f"{a['formality_citations']:>17} {a['lead_formality_cases']:>19}")
    print(line)
    for d in result["details"]:
        rank = d["first_expected_rank"]
        mark = "ok " if rank else "MISS"
        print(f"  [{mark}] {d['id']:22} rank={rank if rank else '-':>3}  "
              f"mit={d['cited_mit']}  ohne={d['cited_ohne']}")


# --------------------------------------------------------------------------- #
# Echte Verdrahtung (Server: council.sqlite + fastembed + API-Key)
# --------------------------------------------------------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser(description="KI-Frage gegen das QA-Golden-Set messen")
    ap.add_argument("--save", action="store_true", help="Ergebnis nach eval/results/qa/ schreiben")
    ap.add_argument("--rate-missing", action="store_true",
                    help="Tragweite der unbewerteten Antwort-Kandidaten vorab per LLM bewerten")
    ap.add_argument("--db", default=None, help="Pfad zur council.sqlite (Default: data/council.sqlite)")
    args = ap.parse_args()

    import os

    from council import qa
    from council import vorlagen as vorlagen_mod
    from council import embeddings as emb
    from council.store import CouncilStore

    root = Path(__file__).parent.parent
    store = CouncilStore(Path(args.db or os.environ.get("COUNCIL_DB") or root / "data" / "council.sqlite"))
    cases = harness.load_cases("cases_qa.json")

    # Ein Retrieval je Fall, von beiden Armen geteilt (identische Kandidaten,
    # nur der Kontext unterscheidet sich) — sonst misst man Retrieval-Rauschen.
    cache: dict[str, list[dict]] = {}

    def candidates_of(case: dict) -> list[dict]:
        if case["id"] not in cache:
            q = case["question"]
            expanded = qa.expand_query(q)
            hits = emb.hybrid_search(store, q, expanded, top_k=TOP_K, pool=55)
            cands = store.get_decisions_by_ids([h[0] for h in hits])
            ctx = cands[:ANSWER_N]
            try:  # Vorlagen-Auszuege wie im /ask-Endpoint
                texts = store.vorlage_texts_for([c.get("vorlage_nr") or "" for c in ctx])
                for c in ctx:
                    t = texts.get((c.get("vorlage_nr") or "").strip())
                    if t:
                        c["vorlage_excerpt"] = vorlagen_mod.excerpt(t, 350)
            except Exception:  # noqa: BLE001
                pass
            cache[case["id"]] = cands
            print(f"  · {case['id']}: {len(cands)} Kandidaten", flush=True)
        return cache[case["id"]]

    if args.rate_missing:
        from council.impact import rate_batch
        todo: set[int] = set()
        for case in cases:
            todo.update(c["id"] for c in candidates_of(case)[:ANSWER_N] if c.get("impact") is None)
        # Volle Zeilen laden — get_decisions_by_ids ist die schlanke QA-Query
        # ohne kind/amount_eur, das würde die Struktur-Signale der Rubrik schwächen.
        missing = [d for d in (store.get_decision(i) for i in sorted(todo)) if d]
        print(f"Tragweite vorab: {len(missing)} unbewertete Kandidaten", flush=True)
        for i in range(0, len(missing), 20):
            for did, score, reason in rate_batch(missing[i:i + 20]):
                store.save_impact(did, score, reason)
        for cands in cache.values():  # frische Werte in die gecachten Kandidaten ziehen
            fresh = {d["id"]: d for d in store.get_decisions_by_ids([c["id"] for c in cands])}
            for c in cands:
                c["impact"] = fresh[c["id"]].get("impact")
                c["impact_reason"] = fresh[c["id"]].get("impact_reason")

    def retrieve(case: dict) -> list[int]:
        return [c["id"] for c in candidates_of(case)]

    def answer(case: dict, with_impact: bool) -> list[int]:
        ctx = [dict(c) for c in candidates_of(case)[:ANSWER_N]]
        if not with_impact:
            for c in ctx:
                c.pop("impact", None)
                c.pop("impact_reason", None)
        _, cited = qa.answer_question(case["question"], ctx)
        return cited

    def impact_of(case: dict) -> dict[int, int | None]:
        return {c["id"]: c.get("impact") for c in candidates_of(case)}

    try:
        result = evaluate(cases, retrieve, answer, impact_of)
    finally:
        store.close()

    print_qa_report(result)
    if args.save:
        out = harness.save_result(result)
        print(f"\n  gespeichert -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
