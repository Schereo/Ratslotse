#!/usr/bin/env python3
"""Gold-Suite für Analyse, Recherchekanäle und Haushalts-Facetten der KI-Frage.

Der Lauf braucht einen API-Key, aber weder Council-Datenbank noch Embeddings.
Die Auswertung ist injizierbar und wird deshalb in der CI vollständig offline
getestet; nur die Modellantworten entstehen beim manuellen/Dev-Lauf.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from council import qa
from eval import harness


def evaluate_routing(cases: list[dict], analyse_fn=qa.analyse_query) -> dict:
    """Bewerte Typ, Plan-Konsistenz, Kanäle und exakte Geld-Facetten."""
    tp = fp = fn = 0
    details: list[dict] = []
    mistakes: list[dict] = []
    rates = {"type": 0, "valid_plan": 0, "channels": 0, "facets": 0, "all": 0}

    for case in cases:
        analysed = analyse_fn(case["question"])
        typ = analysed.get("kind", "topic")
        signal = case.get("signals") or {}
        plan = qa.research_plan_with_mandatory(
            analysed.get("rechercheplan") or {}, typ=typ,
            question=analysed.get("question") or case["question"],
            person=bool(signal.get("person")), place=bool(signal.get("place")),
            sessions=bool(signal.get("sessions")),
            latest_decision=bool(signal.get("latest_decision")),
        )
        channels = set(plan.get("channels") or [])
        required = set(case.get("required_channels") or [])
        forbidden = set(case.get("forbidden_channels") or [])
        expected_facets = set(case.get("expected_facets") or [])
        actual_facets = qa.geld_facetten(
            analysed.get("question") or case["question"], typ)

        type_ok = typ in set(case["allowed_types"])
        valid_ok = bool(plan.get("valid"))
        missing_channels = required - channels
        forbidden_channels = forbidden & channels
        channel_ok = not missing_channels and not forbidden_channels
        missing_facets = expected_facets - actual_facets
        extra_facets = actual_facets - expected_facets
        facet_ok = not missing_facets and not extra_facets

        # Typ und strukturell valider Plan sind je ein Gold-Kriterium.
        tp += int(type_ok) + int(valid_ok)
        fn += int(not type_ok) + int(not valid_ok)
        # Positive Kanal- und Facettenlabels bilden Recall ab; unerwünschte
        # Kanäle bzw. zusätzliche Facetten sind echte False Positives.
        tp += len(required & channels) + len(expected_facets & actual_facets)
        fn += len(missing_channels) + len(missing_facets)
        fp += len(forbidden_channels) + len(extra_facets)

        rates["type"] += int(type_ok)
        rates["valid_plan"] += int(valid_ok)
        rates["channels"] += int(channel_ok)
        rates["facets"] += int(facet_ok)
        all_ok = type_ok and valid_ok and channel_ok and facet_ok
        rates["all"] += int(all_ok)

        detail = {
            "id": case["id"], "type": typ, "type_ok": type_ok,
            "plan_valid": valid_ok, "channels": sorted(channels),
            "facets": sorted(actual_facets), "all_ok": all_ok,
            "missing_channels": sorted(missing_channels),
            "forbidden_channels": sorted(forbidden_channels),
            "missing_facets": sorted(missing_facets),
            "extra_facets": sorted(extra_facets),
        }
        details.append(detail)
        if not all_ok:
            missed = (["valid_plan"] if not valid_ok else [])
            missed += ([f"type∈{case['allowed_types']}"] if not type_ok else [])
            missed += [f"channel:{x}" for x in sorted(missing_channels)]
            missed += [f"facet:{x}" for x in sorted(missing_facets)]
            spurious = [f"channel:{x}" for x in sorted(forbidden_channels)]
            spurious += [f"facet:{x}" for x in sorted(extra_facets)]
            mistakes.append({"id": case["id"], "note": case.get("note", ""),
                              "missed": missed, "spurious": spurious})

    precision, recall, f1 = harness._prf(tp, fp, fn)
    n = len(cases) or 1
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "suite": "qa_routing", "cases": len(cases),
        "tp": tp, "fp": fp, "tn": None, "fn": fn,
        "precision": round(precision, 4), "recall": round(recall, 4),
        "f1": round(f1, 4),
        "pass_rates": {k: round(v / n, 4) for k, v in rates.items()},
        "mistakes": mistakes, "details": details,
    }


def print_routing_report(result: dict) -> None:
    harness.print_report(result)
    rates = result["pass_rates"]
    print("  Case-Passraten: " + ", ".join(
        f"{k}={rates[k]:.1%}" for k in ("type", "valid_plan", "channels", "facets", "all")))


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate QA routing and finance sources")
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args()
    cases = harness.load_cases("cases_qa_routing.json")
    result = evaluate_routing(cases)
    print_routing_report(result)
    if args.compare:
        previous, path = harness.load_last("qa_routing")
        if previous is not None:
            harness.print_compare(result, previous, path)
    if args.save:
        print(f"  saved → {harness.save_result(result)}")


if __name__ == "__main__":
    main()
