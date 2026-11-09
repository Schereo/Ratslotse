"""Der Rückblick abgelaufener Pläne (`council/plan_reviews/*.json`, Plan „Pläne“ § 3.3, Phase 5).

Ein fester Aufbau, keine Bewertung: was vorgesehen war, was die Verwaltung
meldet, welche Grenzen sie selbst nennt, was weiterläuft. Die Sätze sind
wörtlich aus der Auswertung; gegen den Bestand prüft das
``scripts/pruefe_plaene.py`` (hier gibt es keine Vorlagentexte).
"""
from __future__ import annotations

import json

from council import plan_pages, plan_state, plans


def test_form_der_rueckblick_dateien():
    files = sorted(plan_state.REVIEW_DIR.glob("*.json"))
    assert {p.stem for p in files} >= {"schulentwicklungsplan_2018", "step2025", "aktionsplan_gewalt_2020"}
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["plan"] == path.stem and data["plan"] in plans.PLANS
        for s in data["statements"]:
            assert s["kind"] in plan_state.REVIEW_KINDS and s["source_label"].strip()
            assert s["text"].strip().endswith(".") and plans.TEMPLATE_RE.match(s["template"])


def test_rueckblick_nur_fuer_abgelaufene_plaene():
    running = plans.PLANS["klimaschutzplan_2035"]
    assert plan_pages.review_block(running, "running", None) is None
    assert plan_pages.review_block(plans.PLANS["klimaanpassungskonzept"], "preparing", None) is None


def test_rueckblick_fester_aufbau():
    sep = plans.PLANS["schulentwicklungsplan_2018"]
    ref = {"template_number": "19/0942", "title": "Abschlussbericht", "kvonr": 1, "url": None, "date": "2019-12-16"}
    block = plan_pages.review_block(sep, "concluded", ref)
    assert block["evaluation"] == ref and block["no_evaluation_note"] is None
    assert [s["kind"] for s in block["statements"]] == ["result", "result"] and block["continued_by"] is None

    gewalt = plan_pages.review_block(plans.PLANS["aktionsplan_gewalt_2020"], "superseded", ref)
    assert gewalt["has_status"] and gewalt["continued_by"]["key"] == "aktionsplan_gewalt_2026"
    assert {"label": "Maßnahmen", "value": "91"} in gewalt["planned"]
    assert [s["kind"] for s in gewalt["statements"]] == ["limit"]


def test_ohne_auswertung_sagt_die_seite_genau_das():
    """„Nicht gefunden“ statt „gibt es nicht“ — Ratslotse sieht nur das Ratsinformationssystem."""
    block = plan_pages.review_block(plans.PLANS["smv2025"], "superseded", None)
    assert block["evaluation"] is None and "nicht gefunden" in block["no_evaluation_note"]
    assert block["statements"] == [] and block["continued_by"]["key"] == "mobilitaetsplan_2030"
    assert not block["has_status"]
