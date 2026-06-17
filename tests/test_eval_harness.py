"""Offline tests for the evaluation framework.

These exercise the metric math, the generic runners, the case files, and the
LLM-glue in each suite's build_predict() — all without an API key or network,
using injected mock predictors and a fake OpenAI client.
"""
from __future__ import annotations

import json

import pytest

from eval import harness, run, run_digest, run_watcher, run_committee


# --------------------------------------------------------------------------- #
# Metric math
# --------------------------------------------------------------------------- #

def test_prf_perfect():
    assert harness._prf(tp=5, fp=0, fn=0) == (1.0, 1.0, 1.0)


def test_prf_zero_when_no_predictions():
    assert harness._prf(tp=0, fp=0, fn=3) == (0.0, 0.0, 0.0)


def test_prf_partial():
    # 3 TP, 1 FP, 1 FN → P=0.75, R=0.75, F1=0.75
    p, r, f1 = harness._prf(tp=3, fp=1, fn=1)
    assert round(p, 4) == 0.75 and round(r, 4) == 0.75 and round(f1, 4) == 0.75


def test_binary_suite_counts_tp_fp_tn_fn():
    cases = [
        {"id": "a", "expected": True},
        {"id": "b", "expected": True},
        {"id": "c", "expected": False},
        {"id": "d", "expected": False},
    ]
    # predict: a→T (TP), b→F (FN), c→T (FP), d→F (TN)
    preds = {"a": True, "b": False, "c": True, "d": False}
    res = harness.run_binary_suite("t", cases, lambda c: preds[c["id"]])
    assert (res["tp"], res["fp"], res["tn"], res["fn"]) == (1, 1, 1, 1)
    assert res["precision"] == 0.5 and res["recall"] == 0.5
    assert {m["id"] for m in res["mistakes"]} == {"b", "c"}


def test_labelset_suite_aggregates_over_cases():
    cases = [
        {"id": "x", "exp": {("t1", "a"), ("t1", "b")}},
        {"id": "y", "exp": {("t2", "c")}},
    ]
    # x: predict {a (TP), z (FP)} miss b (FN); y: predict {c} (TP)
    preds = {"x": {("t1", "a"), ("t1", "z")}, "y": {("t2", "c")}}
    res = harness.run_labelset_suite(
        "t", cases, lambda c: preds[c["id"]], lambda c: c["exp"],
    )
    assert (res["tp"], res["fp"], res["fn"]) == (2, 1, 1)
    assert res["tn"] is None
    mistake = next(m for m in res["mistakes"] if m["id"] == "x")
    assert mistake["spurious"] == ["('t1', 'z')"]
    assert mistake["missed"] == ["('t1', 'b')"]


def test_labelset_perfect_predictor_scores_100():
    cases = [{"id": "x", "exp": {("t1", "a")}}]
    res = harness.run_labelset_suite(
        "t", cases, lambda c: c["exp"], lambda c: c["exp"],
    )
    assert res["precision"] == 1.0 and res["recall"] == 1.0 and res["f1"] == 1.0
    assert res["mistakes"] == []


# --------------------------------------------------------------------------- #
# Baseline save / load / compare round-trip
# --------------------------------------------------------------------------- #

def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(harness, "RESULTS_DIR", tmp_path)
    result = harness._result("verify", 4, tp=3, fp=0, tn=1, fn=0, mistakes=[])
    out = harness.save_result(result)
    assert out.exists()
    loaded, path = harness.load_last("verify")
    assert loaded["f1"] == result["f1"]
    assert path == out


def test_load_last_missing_suite_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(harness, "RESULTS_DIR", tmp_path)
    assert harness.load_last("nope") == (None, None)


# --------------------------------------------------------------------------- #
# Case files are well-formed and internally consistent
# --------------------------------------------------------------------------- #

def test_verify_cases_shape():
    cases = harness.load_cases("cases.json")
    assert len(cases) >= 10
    for c in cases:
        assert {"id", "topic", "article", "expected"} <= c.keys()
        assert isinstance(c["expected"], bool)


def test_digest_cases_expected_refer_to_real_topics_and_articles():
    cases = harness.load_cases("cases_digest.json")
    assert len(cases) >= 3
    for c in cases:
        topic_ids = {t["id"] for t in c["topics"]}
        refids = {a["refid"] for a in c["articles"]}
        for tid, refid in c["expected_matches"]:
            assert tid in topic_ids, f"{c['id']}: unknown topic id {tid}"
            assert refid in refids, f"{c['id']}: unknown refid {refid}"
        # every article carries the fields build_digest reads
        for a in c["articles"]:
            assert {"refid", "catalog", "content_text", "title"} <= a.keys()


def test_watcher_cases_expected_refer_to_public_items_and_real_topics():
    cases = harness.load_cases("cases_watcher.json")
    assert len(cases) >= 3
    for c in cases:
        topic_ids = {t["id"] for t in c["topics"]}
        public_items = {i["item_number"] for i in c["session"]["agenda_items"] if i.get("is_public", True)}
        for tid, num in c["expected_matches"]:
            assert tid in topic_ids, f"{c['id']}: unknown topic id {tid}"
            assert num in public_items, f"{c['id']}: {num} not a public agenda item"


def test_committee_cases_shape():
    cases = harness.load_cases("cases_committee.json")
    assert len(cases) >= 3
    for c in cases:
        assert isinstance(c["expected"], bool)
        assert c["agenda_items"]


# --------------------------------------------------------------------------- #
# Suite helpers (expected_of / label_str)
# --------------------------------------------------------------------------- #

def test_digest_expected_of_and_label_str():
    cases = harness.load_cases("cases_digest.json")
    case = next(c for c in cases if c["id"] == "digest_radverkehr")
    assert run_digest.expected_of(case) == {(10, "d2/5/1"), (10, "d2/5/2")}
    assert run_digest.label_str((10, "d2/5/1")) == "t10:d2/5/1"


def test_watcher_expected_of_and_label_str():
    cases = harness.load_cases("cases_watcher.json")
    case = next(c for c in cases if c["id"] == "watcher_bauausschuss")
    assert run_watcher.expected_of(case) == {(10, "Ö 3"), (30, "Ö 2")}
    assert run_watcher.label_str((30, "Ö 2")) == "t30:Ö 2"


# --------------------------------------------------------------------------- #
# build_predict() glue, exercised against a fake OpenAI client (offline)
# --------------------------------------------------------------------------- #

class _Msg:
    def __init__(self, content): self.content = content


class _Choice:
    def __init__(self, content): self.message = _Msg(content)


class _Resp:
    def __init__(self, content): self.choices = [_Choice(content)]


class FakeClient:
    """Returns canned JSON based on the model named in the request."""
    def __init__(self, handler):
        self._handler = handler
        self.chat = self  # so client.chat.completions works

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        return _Resp(self._handler(kwargs))


def test_digest_build_predict_extracts_topic_refid_pairs(monkeypatch):
    cases = harness.load_cases("cases_digest.json")
    case = next(c for c in cases if c["id"] == "digest_radverkehr")

    def handler(kwargs):
        model = kwargs["model"]
        if model == "openai/gpt-4o":  # pass-1 digest
            return json.dumps({"digest": [
                {"topic": "Radverkehr Oldenburg", "articles": [
                    {"refid": "d2/5/1", "title": "x", "summary": "s", "is_continuation": False},
                    {"refid": "d2/5/2", "title": "y", "summary": "s", "is_continuation": False},
                ]},
            ]})
        return json.dumps({"relevant": True})  # pass-2 verify keeps both

    import nwz.classify as classify
    monkeypatch.setattr(classify, "_get_client", lambda: FakeClient(handler))

    predict = run_digest.build_predict()
    assert predict(case) == {(10, "d2/5/1"), (10, "d2/5/2")}


def test_digest_verifier_can_drop_a_pass1_match(monkeypatch):
    cases = harness.load_cases("cases_digest.json")
    case = next(c for c in cases if c["id"] == "digest_radverkehr")

    def handler(kwargs):
        if kwargs["model"] == "openai/gpt-4o":
            return json.dumps({"digest": [
                {"topic": "Radverkehr Oldenburg", "articles": [
                    {"refid": "d2/5/1", "title": "x", "summary": "s", "is_continuation": False},
                    {"refid": "d2/9/3", "title": "trees", "summary": "s", "is_continuation": False},
                ]},
            ]})
        # verifier rejects the tree-planting article (off-topic), keeps the bike
        # lane. Key on "Bäume" (only in the tree article) — the topic DESCRIPTION
        # also contains "Radweg"/"Radverkehr", so we can't key on those.
        user = kwargs["messages"][1]["content"]
        return json.dumps({"relevant": "Bäume" not in user})

    import nwz.classify as classify
    monkeypatch.setattr(classify, "_get_client", lambda: FakeClient(handler))

    predict = run_digest.build_predict()
    # d2/9/3 (Bäume) should be dropped by the verifier → only the bike lane remains
    assert predict(case) == {(10, "d2/5/1")}


def test_watcher_build_predict_maps_index_to_topic_id(monkeypatch):
    cases = harness.load_cases("cases_watcher.json")
    case = next(c for c in cases if c["id"] == "watcher_bauausschuss")

    def handler(kwargs):
        # topic_index is 1-based; 1→Radverkehr(id10)/Ö3, 2→Bauprojekte(id30)/Ö2
        return json.dumps({"matches": [
            {"topic_index": 1, "item_numbers": ["Ö 3"]},
            {"topic_index": 2, "item_numbers": ["Ö 2"]},
        ]})

    import council.watcher as watcher
    monkeypatch.setattr(watcher, "_get_client", lambda: FakeClient(handler))

    predict = run_watcher.build_predict()
    assert predict(case) == {(10, "Ö 3"), (30, "Ö 2")}


def test_watcher_end_to_end_scores_perfect_with_oracle(monkeypatch):
    """Full runner + real _classify_agenda + fake LLM that answers each case
    correctly → precision/recall/F1 must be 100%."""
    cases = harness.load_cases("cases_watcher.json")

    # Oracle: parse the expected answer from the case via the agenda text. We
    # instead drive responses per session committee for determinism.
    answers = {
        "Bauausschuss": {"matches": [
            {"topic_index": 1, "item_numbers": ["Ö 3"]},
            {"topic_index": 2, "item_numbers": ["Ö 2"]},
        ]},
        "Stadtentwicklungsausschuss": {"matches": [
            {"topic_index": 1, "item_numbers": ["Ö 2"]},
        ]},
        "Finanzausschuss": {"matches": []},
    }

    def handler(kwargs):
        user = kwargs["messages"][1]["content"]
        for committee, ans in answers.items():
            if committee in user:
                return json.dumps(ans)
        return json.dumps({"matches": []})

    import council.watcher as watcher
    monkeypatch.setattr(watcher, "_get_client", lambda: FakeClient(handler))

    res = harness.run_labelset_suite(
        "watcher", cases, run_watcher.build_predict(), run_watcher.expected_of,
        label_str=run_watcher.label_str,
    )
    assert res["precision"] == 1.0 and res["recall"] == 1.0 and res["f1"] == 1.0
    assert res["mistakes"] == []


def test_committee_build_predict_truthiness(monkeypatch):
    cases = harness.load_cases("cases_committee.json")
    content_case = next(c for c in cases if c["id"] == "committee_has_content")
    routine_case = next(c for c in cases if c["id"] == "committee_routine_only")
    fragestunde_case = next(c for c in cases if c["id"] == "committee_fragestunde_only")

    def handler(kwargs):
        items = kwargs["messages"][1]["content"]
        has = "Bebauungsplan" in items or "Radwegekonzept" in items
        return json.dumps({"has_content": has, "items": [{"number": "Ö 2", "summary": "s"}] if has else []})

    import council.committee_summary as cs
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")  # read as an arg before our mock runs
    monkeypatch.setattr(cs, "OpenAI", lambda **kw: FakeClient(handler))

    predict = run_committee.build_predict()
    assert predict(content_case) is True
    assert predict(routine_case) is False
    # pure Fragestunde short-circuits in code (no LLM call needed)
    assert predict(fragestunde_case) is False
