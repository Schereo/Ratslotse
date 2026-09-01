#!/usr/bin/env python3
"""Ortszuordnung gegen feste positive und negative Goldfälle messen.

Ohne Parameter läuft die kostenlose Regex-/Stadtteillisten-Baseline. ``--llm``
ergänzt Gebäude und komplexe Gebiete über denselben Kanal wie der Backfill.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import locations  # noqa: E402

CASES = ROOT / "eval" / "cases_locations.json"


def evaluate(cases: list[dict], *, use_llm: bool = False) -> dict:
    rows = [{"id": pos + 1, "title": case.get("title", ""),
             "official_text": case.get("official_text", ""),
             "vorlage_text": case.get("vorlage_text", "")}
            for pos, case in enumerate(cases)]
    llm_results: dict[int, list[dict]] = {}
    if use_llm:
        for start in range(0, len(rows), 12):
            got, _usage = locations.extract_batch(rows[start:start + 12])
            llm_results.update(got)

    tp = fp = fn = 0
    misses = []
    for pos, (case, row) in enumerate(zip(cases, rows), 1):
        predicted = locations.merge_candidates(
            locations.extract_explicit_locations(row["title"], source="title"),
            locations.extract_explicit_locations(row["official_text"], source="official_text"),
            llm_results.get(pos, []),
        )
        pred = {locations.location_slug(item["name"]) for item in predicted}
        gold = {locations.location_slug(name) for name in case["expected_locations"]}
        tp += len(pred & gold)
        fp += len(pred - gold)
        fn += len(gold - pred)
        if pred != gold:
            misses.append({"id": case["id"], "expected": sorted(gold), "predicted": sorted(pred)})
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"cases": len(cases), "tp": tp, "fp": fp, "fn": fn,
            "precision": precision, "recall": recall, "f1": f1, "misses": misses}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    result = evaluate(cases, use_llm=args.llm)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Orts-Eval: {result['cases']} Fälle — Precision {result['precision']:.1%}, "
              f"Recall {result['recall']:.1%}, F1 {result['f1']:.1%}")
        for miss in result["misses"]:
            print(f"  ✗ {miss['id']}: erwartet {miss['expected']}, gefunden {miss['predicted']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
