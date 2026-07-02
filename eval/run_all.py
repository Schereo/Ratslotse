#!/usr/bin/env python3
"""Run every evaluation suite and print an aggregate scoreboard.

Usage:
    python eval/run_all.py [--save] [--compare]

Runs verify, digest, watcher and committee suites in turn. Needs
OPENROUTER_API_KEY. A failing suite (e.g. missing key) is reported but does not
abort the others.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from eval import harness, run, run_digest, run_watcher, run_committee  # noqa: E402


def _run_one(name: str) -> dict | None:
    try:
        if name == "verify":
            cases = harness.load_cases("cases.json")
            return harness.run_binary_suite(name, cases, run.build_predict())
        if name == "digest":
            cases = harness.load_cases("cases_digest.json")
            return harness.run_labelset_suite(
                name, cases, run_digest.build_predict(), run_digest.expected_of,
                label_str=run_digest.label_str)
        if name == "watcher":
            cases = harness.load_cases("cases_watcher.json")
            return harness.run_labelset_suite(
                name, cases, run_watcher.build_predict(), run_watcher.expected_of,
                label_str=run_watcher.label_str)
        if name == "committee":
            cases = harness.load_cases("cases_committee.json")
            return harness.run_binary_suite(name, cases, run_committee.build_predict())
    except Exception as e:  # noqa: BLE001 — report and continue with other suites
        print(f"  ⚠ suite {name!r} failed: {type(e).__name__}: {e}")
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run all evaluation suites")
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args()

    suites = ["verify", "digest", "watcher", "committee"]
    results: list[dict] = []
    for name in suites:
        print(f"\n=== {name} ===")
        result = _run_one(name)
        if result is None:
            continue
        results.append(result)
        harness.print_report(result)
        if args.compare:
            prev, prev_path = harness.load_last(name)
            if prev is not None:
                harness.print_compare(result, prev, prev_path)
        if args.save:
            out = harness.save_result(result)
            print(f"  saved → {out.relative_to(Path(__file__).parent.parent)}")

    print(f"\n{'='*52}\n  SCOREBOARD")
    print(f"  {'suite':10} {'cases':>5} {'prec':>7} {'recall':>7} {'f1':>7}")
    for r in results:
        print(f"  {r['suite']:10} {r['cases']:>5} {r['precision']:>7.1%} {r['recall']:>7.1%} {r['f1']:>7.1%}")


if __name__ == "__main__":
    main()
