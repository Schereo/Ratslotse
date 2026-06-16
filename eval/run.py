#!/usr/bin/env python3
"""
Evaluate _verify_match() against labeled test cases.

Usage:
    python eval/run.py             # run all cases, print results
    python eval/run.py --save      # also save result to eval/results/<timestamp>.json
    python eval/run.py --compare   # compare to the last saved result
    python eval/run.py --save --compare
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Make nwz importable when running from repo root or eval/
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from nwz.classify import _get_client, _verify_match  # noqa: E402

CASES_FILE = Path(__file__).parent / "cases.json"
RESULTS_DIR = Path(__file__).parent / "results"


def _run(cases: list[dict]) -> dict:
    client = _get_client()
    tp = fp = tn = fn = 0
    mistakes: list[dict] = []

    for case in cases:
        topic = case["topic"]
        article = case["article"]
        expected = case["expected"]
        got = _verify_match(client, topic, article)

        if expected and got:
            tp += 1
            label = "TP   "
        elif not expected and not got:
            tn += 1
            label = "TN   "
        elif not expected and got:
            fp += 1
            label = "FP ⚠"
            mistakes.append({"id": case["id"], "status": "FP", "topic": topic["name"], "title": article["title"]})
        else:
            fn += 1
            label = "FN ⚠"
            mistakes.append({"id": case["id"], "status": "FN", "topic": topic["name"], "title": article["title"]})

        print(f"  [{label}] {case['id']}: {article['title'][:55]}")

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "timestamp": datetime.now().isoformat(),
        "cases": len(cases),
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": round(precision, 4),
        "recall":    round(recall, 4),
        "f1":        round(f1, 4),
        "mistakes":  mistakes,
    }


def _last_result() -> tuple[dict, Path] | tuple[None, None]:
    if not RESULTS_DIR.exists():
        return None, None
    files = sorted(RESULTS_DIR.glob("*.json"))
    if not files:
        return None, None
    p = files[-1]
    return json.loads(p.read_text()), p


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate classifier against labeled cases")
    parser.add_argument("--save",    action="store_true", help="Save result to eval/results/")
    parser.add_argument("--compare", action="store_true", help="Compare to last saved result")
    args = parser.parse_args()

    cases = json.loads(CASES_FILE.read_text())
    print(f"Running {len(cases)} cases against _verify_match()…\n")

    result = _run(cases)

    print(f"\n{'─'*45}")
    print(f"  Precision : {result['precision']:.1%}  ({result['tp']} TP / {result['tp'] + result['fp']} predicted positive)")
    print(f"  Recall    : {result['recall']:.1%}  ({result['tp']} TP / {result['tp'] + result['fn']} actual positive)")
    print(f"  F1        : {result['f1']:.1%}")
    print(f"  TN        : {result['tn']}")
    print(f"{'─'*45}")

    if result["mistakes"]:
        print(f"\nMisclassified ({len(result['mistakes'])}):")
        for m in result["mistakes"]:
            print(f"  {m['status']}: [{m['topic']}] {m['title'][:55]}")

    if args.compare:
        prev, prev_path = _last_result()
        if prev is None:
            print("\n(No previous result to compare — use --save first)")
        else:
            print(f"\nDelta vs. {prev_path.name}:")
            for key in ("precision", "recall", "f1"):
                delta = result[key] - prev[key]
                arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
                sign  = "+" if delta >= 0 else ""
                print(f"  {key:10}: {prev[key]:.1%} {arrow} {result[key]:.1%}  ({sign}{delta:.1%})")

    if args.save:
        RESULTS_DIR.mkdir(exist_ok=True)
        ts  = datetime.now().strftime("%Y-%m-%d_%H-%M")
        out = RESULTS_DIR / f"{ts}.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"\nSaved → {out.relative_to(Path(__file__).parent.parent)}")


if __name__ == "__main__":
    main()
