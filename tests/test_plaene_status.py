"""Der Stand der Pläne (`council/plan_status/*.json`, `council/plan_state.py`; Plan „Pläne“, Phase 3).

Die Statusdateien sind geprüft und eingecheckt; gebaut hat sie
``scripts/plan_status.py`` aus den Quellen der Stadt. Fest steht hier die
Zusage einer Datei — sie gehört zu einem Plan, jede Zahl trägt Stichtag und
Quelle, die Verteilung geht in der Summe auf — und die Regel des
Berichtsstands (§ 3.3a): Ihre Reihenfolge ist die Regel, und sie bewertet
nicht.

Ob die Dateien noch zu den Quellen passen: ``python scripts/plan_status.py
--pruefen`` (braucht den Bestand und den Zwischenspeicher, darum nicht in der
Suite).
"""
from __future__ import annotations

import dataclasses
import json

import pytest

from council import plan_pages, plan_state, plans

FILES = sorted(plan_state.STATUS_DIR.glob("*.json"))


def test_es_gibt_statusdateien():
    assert {p.stem for p in FILES} >= {"klimaschutzplan_2035", "waermeplan"}


@pytest.mark.parametrize("path", FILES, ids=[p.stem for p in FILES])
def test_form_einer_statusdatei(path):
    d = json.loads(path.read_text(encoding="utf-8"))
    assert d["plan"] == path.stem and d["plan"] in plans.PLANS
    stamps = [s["as_of"] for s in d["snapshots"]]
    assert stamps and stamps == sorted(set(stamps)), f"{path.name}: Stichtage doppelt oder unsortiert"
    codes = {m["code"] for m in (plans.measures(d["plan"]) or {"measures": []})["measures"]}
    for s in d["snapshots"]:
        plan_state.period_end(s["as_of"])  # Jahr, Jahr-Monat oder Tag
        src = s["source"]
        assert src["kind"] in plan_state.SOURCE_KINDS and src["label"].strip()
        assert src.get("url") or src.get("template"), f"{path.name}: Momentaufnahme ohne Beleg"
        assert src.get("template") is None or plans.TEMPLATE_RE.match(src["template"])
        counted = sum(c["count"] for c in s["counts"])
        # Wo die Stadt nicht alles einordnet, sagt die Datei das — sonst geht die Summe auf.
        assert counted == s["total"] if s["complete"] else counted < s["total"], (path.name, s["as_of"])
        for c in s["counts"]:
            assert c["status_norm"] in plan_state.STATUS_NORM and c["status_raw"].strip() and c["count"] >= 0
        for m in s.get("measures") or []:
            assert m["code"] in codes, f"{path.name}: {m['code']} steht nicht in der Maßnahmenliste"
            assert m["status_norm"] in plan_state.STATUS_NORM
    for note in d.get("notes") or []:
        assert note["text"].strip()


def test_klimaschutzplan_reihe():
    """Die Reihe des Klimaportals; 2025 und 2026 sind Zahl für Zahl die Zählblöcke
    aus 26/0074 und 26/0750 (das Skript bricht ab, wenn sie auseinandergehen)."""
    stand = plan_state.city_status("klimaschutzplan_2035")
    assert [(s["as_of"], s["total"]) for s in stand["series"]] == [
        ("2022", 90), ("2023", 90), ("2024", 90), ("2025", 90), ("2026", 97)]
    snaps = {s["as_of"]: s for s in plan_state.load("klimaschutzplan_2035")["snapshots"]}
    assert snaps["2025"]["confirmed_by"] == {"template": "26/0074"}
    assert snaps["2026"]["confirmed_by"] == {"template": "26/0750"}
    move = {c["status_raw"]: (c["before"], c["count"]) for c in stand["movement"]["counts"]}
    # Der Grund gegen eine eigene Quote (§ 1.3): Die Basis wächst, „Realisiert“ sinkt.
    assert stand["movement"]["total_delta"] == 7
    assert move["Realisiert"] == (22, 20) and move["In Umsetzung"] == (25, 34)


def test_bewegung_bei_neuem_wortlaut():
    before = {"as_of": "2024", "total": 3, "counts": [
        {"status_raw": "In Planung", "status_norm": "started", "count": 3}]}
    after = {"as_of": "2025", "total": 4, "counts": [
        {"status_raw": "Planung", "status_norm": "started", "count": 4}]}
    move = plan_state.movement(before, after)
    assert move["total_delta"] == 1 and move["since"] == "2024"
    assert {(c["status_raw"], c["before"], c["count"]) for c in move["counts"]} == {
        ("Planung", 0, 4), ("In Planung", 3, 0)}


def _item(role: str, date: str) -> dict:
    return {"role": role, "date": date}


def test_berichtsstand_reihenfolge_ist_die_regel():
    base = plans.PLANS["waermeplan"]  # beschlossen 06/2026, Überprüfung laut Plan 06/2031
    state = lambda plan, items, today: plan_state.report_state(plan, items, today)["state"]  # noqa: E731

    # Die eigene Frist des Plans schlägt die zwei Jahre.
    assert state(base, [], "2026-11-09") == "not_yet_due"
    assert state(base, [], "2030-01-01") == "not_yet_due"
    assert state(base, [], "2031-07-01") == "no_report_found"
    assert plan_state.report_state(base, [], "2026-11-09")["due_from_plan"] is True
    # Ohne eigene Frist: zwei Jahre ab Beschluss.
    plain = dataclasses.replace(base, review_due=None)
    assert state(plain, [], "2028-05-30") == "not_yet_due"
    assert state(plain, [], "2028-06-02") == "no_report_found"
    # Ein Bericht zählt zwei Jahre lang.
    assert state(base, [_item("report", "2027-01-15")], "2028-12-31") == "reported"
    assert state(base, [_item("report", "2027-01-15")], "2029-02-01") == "no_report_found"
    # Vorbereitung und Beschluss sind kein Bericht.
    assert state(plain, [_item("adoption", "2026-06-01"), _item("preparation", "2026-03-01")],
                 "2028-06-02") == "no_report_found"
    # Vorrang: Nachfolger vor allem anderen; ohne Beschluss „in Arbeit“.
    assert state(dataclasses.replace(base, successor="klimaschutzplan_2035"),
                 [_item("report", "2027-01-15")], "2027-02-01") == "continued"
    assert state(dataclasses.replace(base, adopted=None), [], "2026-11-09") == "in_preparation"
    # Laufzeit vorbei: mit Auswertung „ausgewertet“, sonst sagt der Stand genau das.
    ended = dataclasses.replace(base, end="2027", review_due=None)
    assert state(ended, [_item("evaluation", "2027-11-01")], "2028-01-02") == "evaluated"
    assert state(ended, [_item("report", "2027-11-01")], "2028-01-02") == "expired_no_evaluation"
    assert state(ended, [_item("report", "2027-11-01")], "2027-12-31") == "reported"


def test_berichtsstand_bewertet_nicht():
    """§ 3.4: keine Note. Kein Wort der sieben Stände urteilt über die Arbeit."""
    labels = " ".join(label.lower() for _, label in plan_state.REPORT_STATES)
    for word in ("langsam", "verzug", "gescheitert", "säumig", "hinter", "schlecht", "gut"):
        assert word not in labels
    assert plan_state.STALE_DAYS == plan_pages.STALE_DAYS


def test_jeder_plan_im_register_bekommt_einen_stand():
    known = {key for key, _ in plan_state.REPORT_STATES}
    for plan in plans.PLANS.values():
        assert plan_state.report_state(plan, [], "2026-11-09")["state"] in known, plan.key


def test_eigene_termine_sind_tatsachen():
    ksp = plan_state.own_dates(plans.PLANS["klimaschutzplan_2035"], "2026-11-09")
    assert ksp["end"] == "2035" and ksp["end_passed"] is False and ksp["review_passed"] is False
    assert 0 < ksp["elapsed_months"] < ksp["total_months"]
    late = plan_state.own_dates(plans.PLANS["klimaschutzplan_2035"], "2036-02-01")
    assert late["end_passed"] and late["elapsed_months"] == late["total_months"]
    assert late["review_passed"] and late["months_to_review"] is None
    open_end = plan_state.own_dates(plans.PLANS["waermeplan"], "2026-11-09")
    assert open_end["total_months"] is None and open_end["months_to_review"] == 55
    assert plan_state.period_end("2031-06").isoformat() == "2031-06-30"
    assert plan_state.period_end("2028-02").isoformat() == "2028-02-29"
