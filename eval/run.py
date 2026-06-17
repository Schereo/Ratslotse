#!/usr/bin/env python3
"""Evaluate the second-pass verifier (_verify_match) against labeled cases.

Usage:
    python eval/run.py             # run all cases, print results
    python eval/run.py --save      # also save result to eval/results/verify/
    python eval/run.py --compare   # compare to the last saved result
    python eval/run.py --save --compare

This is the precision guard of the NWZ pipeline (drops keyword-only / off-topic
matches). See eval/README.md for the other suites (digest, watcher, committee).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from eval import harness  # noqa: E402

SUITE = "verify"


def build_predict():
    """Construct the real predictor (needs OPENROUTER_API_KEY)."""
    from nwz.classify import _verify_match
    return lambda case: _verify_match(case["topic"], case["article"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the NWZ verifier against labeled cases")
    parser.add_argument("--save", action="store_true", help="Save result to eval/results/verify/")
    parser.add_argument("--compare", action="store_true", help="Compare to last saved result")
    args = parser.parse_args()

    cases = harness.load_cases("cases.json")
    print(f"Running {len(cases)} cases against _verify_match()…\n")

    predict = build_predict()
    result = harness.run_binary_suite(
        SUITE, cases, predict,
        on_case=lambda label, cid: print(f"  [{label:5}] {cid}"),
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
