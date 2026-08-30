"""Offline-Tests für die QA-Eval-Suite (eval/run_qa.py).

Die Metrik-Logik läuft mit injizierten Funktionen — kein API-Key, keine DB.
"""
import pytest

from eval.run_qa import aggregate_latency, evaluate, resolve_expected

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


# --------------------------------------------------------------------------- #
# Portable Gold-Cases: Auflösung natürlicher Schlüssel → ids der offenen DB
# --------------------------------------------------------------------------- #

_FAKE_DB = {
    ("template_number", "25/0100"): [7, 8],
    ("template_number", "25/0200"): [8, 9],  # 8 überschneidet — Dedupe-Probe
    ("title_like", "Wechloy"): [3],
}


def _find_ids(**spec):
    key = next(iter(sorted(spec.items())))
    return list(_FAKE_DB.get(key, []))


def test_resolve_expected_prefers_keys_and_dedupes():
    case = {"id": "x", "expected_ids": [999],
            "expected_keys": [{"template_number": "25/0100"}, {"template_number": "25/0200"}]}
    # Schlüssel schlagen die prod-ids; Reihenfolge der Specs bleibt, Duplikate raus.
    assert resolve_expected(_find_ids, case) == [7, 8, 9]


def test_resolve_expected_falls_back_to_ids():
    assert resolve_expected(_find_ids, {"id": "y", "expected_ids": [1, 2]}) == [1, 2]


def test_resolve_expected_empty_when_unresolvable():
    case = {"id": "z", "expected_ids": [999], "expected_keys": [{"template_number": "26/9999"}]}
    assert resolve_expected(_find_ids, case) == []


def test_resolve_expected_rejects_unknown_key():
    case = {"id": "tippfehler", "expected_keys": [{"vorlagen_nr": "25/0100"}]}
    with pytest.raises(ValueError, match="tippfehler"):
        resolve_expected(_find_ids, case)


def test_aggregate_latency_kosten_behalten_nachkommastellen():
    agg = aggregate_latency([{"antwort_ct": 0.14}, {"antwort_ct": 0.22}])
    # Ganzzahl-Rundung würde hier 0 liefern — Kosten je Frage sind Cent-Bruchteile.
    assert agg["antwort_ct"]["mean"] == 0.18


def test_aggregate_latency_percentiles_and_missing_keys():
    agg = aggregate_latency([
        {"expand_ms": 100, "rerank_ms": 10},
        {"expand_ms": 200, "rerank_ms": 20},
        {"expand_ms": 300},  # rerank fehlt (z. B. Keyword-Fallback) → ignoriert
        {"expand_ms": 400, "rerank_ms": 40},
    ])
    assert agg["expand_ms"]["mean"] == 250
    assert agg["expand_ms"]["p50"] == 300  # obere Mitte bei gerader Anzahl
    assert agg["expand_ms"]["p95"] == 400
    assert agg["rerank_ms"]["mean"] == 23  # nur die drei vorhandenen Werte
    assert "total_ms" not in agg


# ---- Debatten-Erwartung (Gold-Case „fliegerhorst-sondermuell-debatte") ----

DEBATTEN = [
    {"id": 1, "sprecher": "Jaekel", "session_date": "2026-02-12",
     "text": "Vinylchlorid im Grundwasser stammt aus der militärischen Nutzung.", "antwort": None},
    {"id": 2, "sprecher": "Müller", "session_date": "2025-06-12",
     "text": "Durch die Verfüllung können keine Schadstoffe austreten.", "antwort": None},
]


def test_debatten_treffer_matcht_ueber_natuerliche_schluessel():
    from eval.run_qa import debatten_treffer
    assert debatten_treffer([{"sprecher": "jaekel"}], DEBATTEN) == [True]
    assert debatten_treffer([{"text_like": "Vinylchlorid"}], DEBATTEN) == [True]
    # Alle Felder eines Specs müssen zusammen passen — nicht irgendeins.
    assert debatten_treffer([{"sprecher": "Müller", "text_like": "Vinylchlorid"}], DEBATTEN) == [False]
    assert debatten_treffer([{"session_date": "2026-02-12"}, {"session_date": "1999-01-01"}],
                            DEBATTEN) == [True, False]


def test_debatten_treffer_prueft_auch_die_verwaltungsantwort():
    from eval.run_qa import debatten_treffer
    rows = [{"sprecher": "Finke", "text": "Frage zu Messpunkten",
             "antwort": "Die Werte liegen unter dem Prüfwert."}]
    assert debatten_treffer([{"text_like": "Prüfwert"}], rows) == [True]


def test_debatten_treffer_meldet_tippfehler_im_case():
    from eval.run_qa import debatten_treffer
    with pytest.raises(ValueError):
        debatten_treffer([{"sprecherin": "Jaekel"}], DEBATTEN)


def test_evaluate_zaehlt_debatten_nur_bei_faellen_mit_erwartung():
    cases = [
        {"id": "a", "question": "?", "expected_ids": [10],
         "expected_debatten": [{"text_like": "Vinylchlorid"}, {"text_like": "Fehlt"}]},
        {"id": "b", "question": "?", "expected_ids": [20]},
    ]
    res = evaluate(
        cases,
        retrieve=lambda c: [10] if c["id"] == "a" else [20],
        answer=lambda c, with_impact: [],
        impact_of=lambda c: {},
        debatten_of=lambda c: DEBATTEN,
    )
    assert res["debatten"] == {"cases": 1, "erwartet": 2, "gefunden": 1, "recall": 0.5}
    a = next(d for d in res["details"] if d["id"] == "a")
    assert a["debatten"]["fehlend"] == [{"text_like": "Fehlt"}]
    assert "debatten" not in next(d for d in res["details"] if d["id"] == "b")
