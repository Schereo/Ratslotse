"""Offline-Tests für die Gold-Suite des KI-Frage-Routings."""
import json
from pathlib import Path

from council import qa
from eval.run_qa_routing import evaluate_routing


CASES_PATH = Path(__file__).resolve().parents[1] / "eval" / "cases_qa_routing.json"


def _cases():
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def _gold_analysis(case):
    channels = case.get("required_channels") or ["decisions"]
    needs = []
    for channel, need in (("debates", "statements"), ("documents", "documents"),
                          ("press", "official_updates"),
                          ("future_agenda", "future_dates")):
        if channel in channels:
            needs.append(need)
    return {
        "frage": case["question"],
        "typ": case["allowed_types"][0],
        "rechercheplan": qa._research_plan({"rechercheplan": {
            "intent": "fact", "channels": channels, "sort": "relevance",
            "needs": needs,
        }}),
    }


def test_gold_cases_sind_eindeutig_und_facetten_stimmen():
    cases = _cases()
    assert len(cases) >= 20
    assert len({c["id"] for c in cases}) == len(cases)
    for case in cases:
        assert case["allowed_types"]
        assert set(case.get("required_channels", [])) <= set(qa.RESEARCH_CHANNELS)
        assert set(case.get("forbidden_channels", [])) <= set(qa.RESEARCH_CHANNELS)
        assert not (set(case.get("required_channels", []))
                    & set(case.get("forbidden_channels", [])))
        typ = case["allowed_types"][0]
        assert qa.geld_facetten(case["question"], typ) == set(
            case.get("expected_facets", [])), case["id"]


def test_routing_eval_gold_prediction_erreicht_hundert_prozent():
    by_question = {c["question"]: c for c in _cases()}
    result = evaluate_routing(
        list(by_question.values()), lambda question: _gold_analysis(by_question[question]))
    assert result["pass_rates"] == {
        "type": 1.0, "valid_plan": 1.0, "channels": 1.0,
        "facets": 1.0, "all": 1.0,
    }
    assert result["mistakes"] == []
    assert result["precision"] == 1.0 and result["recall"] == 1.0


def test_routing_eval_meldet_zu_viele_und_fehlende_kanaele():
    case = {
        "id": "x", "question": "Was steht im Gutachten zum Lärm?",
        "allowed_types": ["thema"], "expected_facets": [],
        "required_channels": ["decisions", "documents"],
        "forbidden_channels": ["debates"],
    }
    analysis = {
        "frage": case["question"], "typ": "verlauf",
        "rechercheplan": qa._research_plan({"rechercheplan": {
            "intent": "timeline", "channels": ["decisions", "debates"],
            "needs": ["statements"],
        }}),
    }
    result = evaluate_routing([case], lambda _question: analysis)
    detail = result["details"][0]
    assert not detail["type_ok"] and not detail["all_ok"]
    assert detail["missing_channels"] == ["documents"]
    assert detail["forbidden_channels"] == ["debates"]
    assert result["pass_rates"]["all"] == 0.0
