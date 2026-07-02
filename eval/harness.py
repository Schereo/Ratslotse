"""Shared evaluation harness for the extraction pipeline.

The pipeline's value depends on matching quality, so every matching component
should be measurable against labeled ground truth. This module provides the
reusable machinery — metrics, a generic runner, reporting and baseline
save/compare — so each suite (verify, digest, council watcher, committee
summary) only has to supply its cases and a ``predict`` function.

Two scoring models:

* **binary** — one true/false decision per case (verifier, committee
  has-content). Yields TP/FP/TN/FN and precision/recall/F1.
* **label sets** — each case predicts a *set* of labels (e.g. the
  ``(topic, article)`` pairs the digest matched, or the ``(topic, TOP)`` pairs
  the watcher matched). Scored as a retrieval task: TP = predicted ∩ expected,
  FP = predicted − expected, FN = expected − predicted, aggregated over all
  cases. There is no TN (the label space is open-ended).

All ``predict`` functions are injected, so the runner and metrics are fully
testable offline with a mock predictor — no API key or network required.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Hashable, Iterable

RESULTS_DIR = Path(__file__).parent / "results"

Label = Hashable
Case = dict[str, Any]


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #

def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def _result(suite: str, n_cases: int, tp: int, fp: int, tn: int | None, fn: int,
            mistakes: list[dict]) -> dict:
    precision, recall, f1 = _prf(tp, fp, fn)
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "suite": suite,
        "cases": n_cases,
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "mistakes": mistakes,
    }


# --------------------------------------------------------------------------- #
# Runners (predict is injected → offline-testable)
# --------------------------------------------------------------------------- #

def run_binary_suite(
    suite: str,
    cases: list[Case],
    predict: Callable[[Case], bool],
    *,
    on_case: Callable[[str, str], None] | None = None,
) -> dict:
    """Score a suite where each case has a boolean ``expected`` and predict→bool."""
    tp = fp = tn = fn = 0
    mistakes: list[dict] = []
    for case in cases:
        expected = bool(case["expected"])
        got = bool(predict(case))
        if expected and got:
            tp += 1; label = "TP"
        elif not expected and not got:
            tn += 1; label = "TN"
        elif not expected and got:
            fp += 1; label = "FP"
            mistakes.append({"id": case["id"], "status": "FP", "note": case.get("note", "")})
        else:
            fn += 1; label = "FN"
            mistakes.append({"id": case["id"], "status": "FN", "note": case.get("note", "")})
        if on_case:
            on_case(label, case["id"])
    return _result(suite, len(cases), tp, fp, tn, fn, mistakes)


def run_labelset_suite(
    suite: str,
    cases: list[Case],
    predict: Callable[[Case], Iterable[Label]],
    expected_of: Callable[[Case], Iterable[Label]],
    *,
    label_str: Callable[[Label], str] = str,
    on_case: Callable[[str, str], None] | None = None,
) -> dict:
    """Score a suite where each case predicts a *set* of labels.

    ``predict`` returns the predicted labels; ``expected_of`` returns the
    ground-truth labels for a case. Both are compared as sets per case and the
    TP/FP/FN counts are aggregated across all cases.
    """
    tp = fp = fn = 0
    mistakes: list[dict] = []
    for case in cases:
        expected = set(expected_of(case))
        predicted = set(predict(case))
        case_tp = expected & predicted
        case_fp = predicted - expected
        case_fn = expected - predicted
        tp += len(case_tp); fp += len(case_fp); fn += len(case_fn)
        if case_fp or case_fn:
            mistakes.append({
                "id": case["id"],
                "note": case.get("note", ""),
                "spurious": sorted(label_str(x) for x in case_fp),  # false positives
                "missed": sorted(label_str(x) for x in case_fn),    # false negatives
            })
            status = "FP/FN"
        else:
            status = "OK"
        if on_case:
            on_case(status, case["id"])
    return _result(suite, len(cases), tp, fp, None, fn, mistakes)


# --------------------------------------------------------------------------- #
# Reporting + baselines
# --------------------------------------------------------------------------- #

def print_report(result: dict) -> None:
    line = "─" * 52
    print(f"\n{line}")
    print(f"  Suite     : {result['suite']}  ({result['cases']} cases)")
    pp = result["tp"] + result["fp"]
    ap = result["tp"] + result["fn"]
    print(f"  Precision : {result['precision']:.1%}  ({result['tp']} TP / {pp} predicted positive)")
    print(f"  Recall    : {result['recall']:.1%}  ({result['tp']} TP / {ap} actual positive)")
    print(f"  F1        : {result['f1']:.1%}")
    if result["tn"] is not None:
        print(f"  TN        : {result['tn']}")
    print(line)
    if result["mistakes"]:
        print(f"\n  Misclassified ({len(result['mistakes'])}):")
        for m in result["mistakes"]:
            if "status" in m:  # binary
                print(f"    {m['status']}: {m['id']}  {m.get('note','')}")
            else:  # labelset
                bits = []
                if m["missed"]:
                    bits.append(f"missed={m['missed']}")
                if m["spurious"]:
                    bits.append(f"spurious={m['spurious']}")
                print(f"    {m['id']}: {'; '.join(bits)}")


def _suite_dir(suite: str) -> Path:
    return RESULTS_DIR / suite


def save_result(result: dict) -> Path:
    d = _suite_dir(result["suite"])
    d.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out = d / f"{ts}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return out


def load_last(suite: str) -> tuple[dict, Path] | tuple[None, None]:
    d = _suite_dir(suite)
    if not d.exists():
        return None, None
    files = sorted(d.glob("*.json"))
    if not files:
        return None, None
    return json.loads(files[-1].read_text()), files[-1]


def print_compare(result: dict, prev: dict, prev_path: Path) -> None:
    print(f"\n  Delta vs. {prev_path.name}:")
    for key in ("precision", "recall", "f1"):
        delta = result[key] - prev[key]
        arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
        sign = "+" if delta >= 0 else ""
        print(f"    {key:10}: {prev[key]:.1%} {arrow} {result[key]:.1%}  ({sign}{delta:.1%})")


def load_cases(filename: str) -> list[Case]:
    return json.loads((Path(__file__).parent / filename).read_text())
