#!/usr/bin/env python3
"""Evaluate the committee-summary routine filter (summarize_agenda).

Binary check: given an agenda, does the summarizer correctly decide whether
there is substantive content (True) or only routine/Fragestunde items (False)?
This guards against both spamming users with empty summaries and dropping real
content.

Usage:
    python eval/run_committee.py [--save] [--compare]

Needs OPENROUTER_API_KEY (calls gpt-4o-mini, except for the pure-Fragestunde
case which short-circuits in code). Offline-testable via the harness tests.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from eval import harness  # noqa: E402

SUITE = "committee"


def build_predict():
    """Real predictor: summarize_agenda returns '' iff no substantive content."""
    from council.scraper import AgendaItem
    from council.committee_summary import summarize_agenda

    def predict(case: dict) -> bool:
        items = [
            AgendaItem(
                item_number=i["item_number"],
                title=i["title"],
                vorlage_nr=i.get("vorlage_nr", ""),
                is_public=bool(i.get("is_public", True)),
            )
            for i in case["agenda_items"]
        ]
        summary = summarize_agenda(
            case["committee"], case["session_date"], case.get("session_time", ""),
            case.get("location", ""), items, session_url="https://example.invalid",
        )
        return bool(summary)

    return predict


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the committee summary filter")
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args()

    cases = harness.load_cases("cases_committee.json")
    print(f"Running {len(cases)} committee cases against summarize_agenda()…\n")

    result = harness.run_binary_suite(
        SUITE, cases, build_predict(),
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
