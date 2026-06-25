#!/usr/bin/env python3
"""Score the AI features against the fixed gold set in ``tests/eval/*.jsonl``.

A regression guard for the LLM/retrieval features — re-run after any prompt, model
or retrieval change to catch silent quality drops. Needs the council DB and
``OPENROUTER_API_KEY`` (run on prod or against a copy of the DB)::

    python scripts/eval_ai.py            # full report
    python scripts/eval_ai.py --json     # machine-readable summary (for CI)
    python scripts/eval_ai.py --only qa  # one section
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import goals, qa, topics  # noqa: E402
from council.store import CouncilStore  # noqa: E402

EVAL = ROOT / "tests" / "eval"
COUNCIL_DB = ROOT / "data" / "council.sqlite"


def _load(name: str) -> list[dict]:
    return [json.loads(ln) for ln in (EVAL / name).read_text(encoding="utf-8").splitlines() if ln.strip()]


def eval_topics(store: CouncilStore) -> dict:
    gold = _load("topics.jsonl")
    decs = [d for d in (store.get_decision(g["id"]) for g in gold) if d]
    results: dict = {}
    for i in range(0, len(decs), 25):  # batch so a large gold set doesn't overflow one prompt
        batch_res, _ = topics.classify_batch(decs[i:i + 25])
        results.update(batch_res)
    miss, ok = [], 0
    for g in gold:
        pred = (results.get(g["id"]) or {}).get("field")
        if pred == g["field"]:
            ok += 1
        else:
            miss.append({"id": g["id"], "gold": g["field"], "pred": pred, "note": g.get("note", "")})
    return {"name": "Themenfeld", "n": len(gold), "correct": ok, "miss": miss}


def eval_stance(store: CouncilStore) -> dict:
    gold = _load("stance.jsonl")
    by_goal: dict[str, list] = defaultdict(list)
    for g in gold:
        by_goal[g["goal"]].append(g)
    miss, ok = [], 0
    for goal_key, items in by_goal.items():
        decs = [d for d in (store.get_decision(i["decision_id"]) for i in items) if d]
        results: dict = {}
        for j in range(0, len(decs), 25):
            r, _ = goals.assess_batch(goal_key, decs[j:j + 25])
            results.update(r)
        for i in items:
            pred = (results.get(i["decision_id"]) or {}).get("stance")
            if pred == i["stance"]:
                ok += 1
            else:
                miss.append({"id": i["decision_id"], "goal": goal_key, "gold": i["stance"], "pred": pred})
    return {"name": "Ziel-Stance", "n": len(gold), "correct": ok, "miss": miss}


def eval_qa(store: CouncilStore) -> dict:
    from council import embeddings as emb

    gold = _load("qa.jsonl")
    miss, ok = [], 0
    for g in gold:
        q = g["question"]
        hits = emb.hybrid_search(store, q, qa.expand_query(q), top_k=10)
        srcs = store.get_decisions_by_ids([h[0] for h in hits])
        if g.get("expect_refuse"):
            ans = qa.answer_question(q, srcs)
            text = (ans[0] if isinstance(ans, (list, tuple)) else ans) or ""
            hit = any(neg in text.lower()[:200] for neg in ("nein", "nicht", "keine", "kein "))
        else:
            blob = " ".join((s.get("title") or "") + " " + (s.get("summary") or "") for s in srcs).lower()
            hit = any(kw.lower() in blob for kw in g["expect_any"])
        if hit:
            ok += 1
        else:
            miss.append({"q": q[:50], "type": "refuse" if g.get("expect_refuse") else "retrieval"})
    return {"name": "Frag-den-Rat", "n": len(gold), "correct": ok, "miss": miss}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--only", choices=["topics", "stance", "qa"])
    args = ap.parse_args()

    store = CouncilStore(args.db)
    runners = {"topics": eval_topics, "stance": eval_stance, "qa": eval_qa}
    sections = [fn(store) for key, fn in runners.items() if args.only in (None, key)]
    store.close()

    if args.json:
        print(json.dumps([{k: v for k, v in s.items() if k != "miss"} for s in sections], ensure_ascii=False))
        return 0

    print("=== KI-Eval gegen Gold-Set ===")
    for s in sections:
        acc = s["correct"] / s["n"] * 100 if s["n"] else 0
        print(f"\n{s['name']}: {s['correct']}/{s['n']} = {acc:.0f}%")
        for m in s["miss"]:
            print("   ✗", m)
    c = sum(s["correct"] for s in sections)
    n = sum(s["n"] for s in sections)
    print(f"\nGesamt: {c}/{n} = {c / n * 100:.0f}%" if n else "\nkeine Fälle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
