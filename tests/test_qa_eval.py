"""Offline-Tests für die QA-Eval-Suite (eval/run_qa.py).

Die Metrik-Logik läuft mit injizierten Funktionen — kein API-Key, keine DB.
"""
from eval.run_qa import evaluate

CASES = [
    {"id": "a", "question": "?", "expected_ids": [10, 11]},
    {"id": "b", "question": "?", "expected_ids": [20]},
    {"id": "c", "question": "?", "expected_ids": [30]},
]

RETRIEVED = {"a": [10, 99], "b": [98, 97, 20], "c": [96]}  # c findet nichts Erwartetes
CITED = {
    ("a", True): [10], ("a", False): [99],       # mit Tragweite trifft, ohne zitiert die Formalie
    ("b", True): [20, 98], ("b", False): [98, 20],  # ohne führt mit der Formalie an
    ("c", True): [], ("c", False): [],
}
IMPACT = {10: 80, 99: 5, 98: 0, 97: None, 20: 60, 96: None}


def _run():
    return evaluate(
        CASES,
        retrieve=lambda c: RETRIEVED[c["id"]],
        answer=lambda c, with_impact: CITED[(c["id"], with_impact)],
        impact_of=lambda c: {i: IMPACT.get(i) for i in RETRIEVED[c["id"]]},
    )


def test_qa_eval_retrieval_metrics():
    r = _run()["retrieval"]
    # a: Rang 1, b: Rang 3, c: Miss → Trefferquote 2/3, MRR (1 + 1/3) / 3
    assert r["hit_rate"] == round(2 / 3, 4)
    assert r["mrr"] == round((1 + 1 / 3) / 3, 4)


def test_qa_eval_arm_comparison():
    arms = _run()["arms"]
    mit, ohne = arms["mit_tragweite"], arms["ohne_tragweite"]
    assert mit["cite_expected_rate"] == round(2 / 3, 4)   # a + b zitieren Erwartetes
    assert ohne["cite_expected_rate"] == round(1 / 3, 4)  # nur b
    # impact 0 (id 98) zählt als Formalie — kein Falsy-Ausrutscher.
    assert mit["formality_citations"] == 1                # 98 in b
    assert ohne["formality_citations"] == 2               # 99 in a + 98 in b
    assert mit["lead_formality_cases"] == 0
    assert ohne["lead_formality_cases"] == 2              # a führt mit 99, b mit 98
    assert mit["citations"] == 3 and ohne["citations"] == 3


def test_qa_eval_details_have_no_impact_map():
    result = _run()
    assert result["cases"] == 3
    assert all("impact_of" not in d for d in result["details"])
    assert result["details"][2]["first_expected_rank"] is None
