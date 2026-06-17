#!/usr/bin/env python3
"""Evaluate the full NWZ digest matcher (build_digest: pass 1 + verification).

Each case gives a set of topics and a set of articles; the ground truth is the
set of (topic_id, refid) pairs that *should* match. The matcher is scored as a
retrieval task (precision = no spurious matches, recall = nothing missed).

Usage:
    python eval/run_digest.py [--save] [--compare]

Needs OPENROUTER_API_KEY (calls gpt-4o + gpt-4o-mini). The scoring/runner
logic is offline-testable via tests/test_eval_harness.py with a mock predictor.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from eval import harness  # noqa: E402

SUITE = "digest"


def expected_of(case: dict) -> set[tuple[int, str]]:
    return {(int(tid), refid) for tid, refid in case.get("expected_matches", [])}


def label_str(label: tuple[int, str]) -> str:
    tid, refid = label
    return f"t{tid}:{refid}"


def build_predict():
    """Real predictor: run build_digest and collect (topic_id, refid) matches."""
    from nwz.classify import build_digest

    def predict(case: dict) -> set[tuple[int, str]]:
        _msg, raw_matches = build_digest(case["articles"], case["topics"], case["pub_date"])
        return {(int(m["topic_id"]), m["refid"]) for m in raw_matches}

    return predict


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the NWZ digest matcher")
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args()

    cases = harness.load_cases("cases_digest.json")
    print(f"Running {len(cases)} digest cases against build_digest()…\n")

    result = harness.run_labelset_suite(
        SUITE, cases, build_predict(), expected_of,
        label_str=label_str,
        on_case=lambda status, cid: print(f"  [{status:5}] {cid}"),
    )
    harness.print_report(result)

    if args.compare:
        prev, prev_path = harness.load_last(SUITE)
        if prev is None:
            print("\n(No previous result to compare — use --save first)")
        else:
            harness.print_compare(result, prev, prev_path)
    if args.save:
        out = harness.save_result(result)
        print(f"\nSaved → {out.relative_to(Path(__file__).parent.parent)}")


if __name__ == "__main__":
    main()
