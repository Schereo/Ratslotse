#!/usr/bin/env python3
"""Evaluate the council watcher's agenda→topic matching (_classify_agenda).

Each case gives one session (with agenda items) and a set of topics; the ground
truth is the set of (topic_id, item_number) pairs that should match. Non-public
items are never classified (the watcher filters them), so they must not appear
in expected_matches.

Usage:
    python eval/run_watcher.py [--save] [--compare]

Needs OPENROUTER_API_KEY (calls gpt-4o-mini). Offline-testable via
tests/test_eval_harness.py with a mock predictor.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from eval import harness  # noqa: E402

SUITE = "watcher"


def _build_session(case: dict):
    from council.scraper import AgendaItem, CouncilSession
    s = case["session"]
    items = [
        AgendaItem(
            item_number=i["item_number"],
            title=i["title"],
            vorlage_nr=i.get("vorlage_nr", ""),
            is_public=bool(i.get("is_public", True)),
        )
        for i in s["agenda_items"]
    ]
    return CouncilSession(
        ksinr=s["ksinr"], committee=s["committee"], session_date=s["session_date"],
        session_time=s.get("session_time", ""), location=s.get("location", ""),
        agenda_items=items,
    )


def expected_of(case: dict) -> set[tuple[int, str]]:
    return {(int(tid), num) for tid, num in case.get("expected_matches", [])}


def label_str(label: tuple[int, str]) -> str:
    tid, num = label
    return f"t{tid}:{num}"


def build_predict():
    """Real predictor: run _classify_agenda, map topic index → topic id."""
    from council.watcher import _classify_agenda

    def predict(case: dict) -> set[tuple[int, str]]:
        session = _build_session(case)
        topics = case["topics"]
        matches = _classify_agenda(session, topics)  # {topic_idx: [item_numbers]}
        return {
            (int(topics[idx]["id"]), num)
            for idx, nums in matches.items()
            for num in nums
        }

    return predict


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the council watcher matcher")
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args()

    cases = harness.load_cases("cases_watcher.json")
    print(f"Running {len(cases)} watcher cases against _classify_agenda()…\n")

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
