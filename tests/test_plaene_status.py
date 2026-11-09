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
    assert {p.stem for p in FILES} >= {"klimaschutzplan_2035", "waermeplan", "aktionsplan_gewalt_2020"}


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


def test_bloecke_der_planseite():
    """Was die Seiten bekommen: der Stand im Wortlaut der Stadt, mit Herkunft und Stichtag."""
    brief = plan_pages.status_brief("klimaschutzplan_2035")
    assert brief["as_of_label"] == "2026" and brief["origin_label"] == "Klimaportal der Stadt"
    assert brief["total"] == 97 and brief["complete"] and sum(c["count"] for c in brief["counts"]) == 97
    full = plan_pages.city_status_block("klimaschutzplan_2035")
    assert full["confirmed"] and full["template_number"] == "26/0750"
    assert full["movement"]["since_label"] == "2025" and len(full["series"]) == 5 and full["notes"]
    assert plan_pages.status_brief("masterplan_stadtgruen") is None
    assert plan_pages.city_status_block("masterplan_stadtgruen") is None

    waerme = plan_pages.city_status_block("waermeplan")
    assert waerme["origin_label"] == "Nach Angaben der Verwaltung" and waerme["as_of_label"] == "03/2026"
    assert not waerme["complete"] and waerme["movement"] is None and waerme["template_number"] == "26/0236"
    block = plan_pages.measures_block("waermeplan")
    with_state = [m["code"] for g in block["groups"] for m in g["measures"] if m["status_raw"]]
    assert sorted(with_state) == ["F2", "K1", "K2", "K3", "T2", "T5"] and block["status_count"] == 6
    assert block["status_as_of_label"] == "03/2026"
    ksp = plan_pages.measures_block("klimaschutzplan_2035")  # je Maßnahme meldet die Stadt nichts Verlässliches
    assert ksp["status_count"] == 0 and ksp["status_as_of_label"] is None


def test_berichtsstand_auf_der_karte():
    block = plan_pages.report_state_block(plans.PLANS["waermeplan"], [], "2026-11-09")
    assert block == {"state": "not_yet_due", "label": "Noch kein Bericht fällig",
                     "hint": "Überprüfung laut Plan 06/2031."}
    plain = dataclasses.replace(plans.PLANS["waermeplan"], review_due=None)
    assert plan_pages.report_state_block(plain, [], "2026-11-09")["hint"] == "Der Plan ist jünger als zwei Jahre."
    assert plan_pages.report_state_block(plain, [_item("report", "2026-10-01")], "2026-11-09")["hint"] is None


def test_aktionsplan_gewalt_2020_farben_und_text_passen_zusammen():
    """Die Verteilung zählt der Text der Evaluation, den Stand je Empfehlung trägt die
    Zellfarbe im Anhang. Die eine Abweichung (90 im Text, 91 Zeilen) steht als Hinweis da."""
    stand = plan_pages.city_status_block("aktionsplan_gewalt_2020")
    assert stand["total"] == 90 and stand["complete"] and stand["origin_label"] == "Nach Angaben der Verwaltung"
    assert [c["count"] for c in stand["counts"]] == [56, 3, 8, 14, 9]
    assert any("91 Zeilen" in n["text"] for n in stand["notes"])
    block = plan_pages.measures_block("aktionsplan_gewalt_2020")
    assert block["count"] == 91 and block["status_count"] == 91 and block["count_city"] is None
    assert [g["field"] for g in block["groups"]] == [
        "Übergreifende Handlungsempfehlungen", "Gewalt gegen Frauen*", "Häusliche Gewalt"]
    assert [len(g["measures"]) for g in block["groups"]] == [8, 58, 25]
    titles = [m["title"] for g in block["groups"] for m in g["measures"]]
    assert all(t[:1].isupper() and len(t) >= 20 for t in titles), [t for t in titles if not t[:1].isupper() or len(t) < 20]
    assert not any("ungsund " in t or "- und" in t.replace(" - und", "") and "-und" in t for t in titles)


def test_kennzahl_steht_neben_dem_plan():
    """§ 3.4 Nr. 4: Soll und Ist mit Quelle — und der Vorbehalt des Berichts dabei."""
    (ghg,) = plan_pages.indicator_blocks("klimaschutzplan_2035")
    assert ghg["baseline_year"] == 2020 and ghg["baseline_value"] == 1140000
    rows = {r["year"]: r for r in ghg["rows"]}
    assert rows[2023]["actual"] == 935792 and rows[2023]["target"] == 969000
    assert round(rows[2023]["actual_change"] * 100, 1) == -17.9  # so nennt es auch der Bericht 25/0866
    assert round(rows[2022]["actual_change"] * 100, 1) == -11.9 and rows[2022]["target"] is None
    assert rows[2023]["template_number"] == "25/0866"
    assert any("Strommix" in n["text"] for n in ghg["notes"])
    assert plan_pages.indicator_blocks("waermeplan") == []
    for path in plan_state.INDICATOR_DIR.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["plan"] == path.stem and data["plan"] in plans.PLANS
        for ind in data["indicators"]:
            assert plans.TEMPLATE_RE.match(ind["baseline"]["template"])
            for point in ind["points"]:
                assert point["kind"] in ("target", "actual") and plans.TEMPLATE_RE.match(point["template"])


def test_ernaehrungsstrategie_stufen_nie_gemittelt():
    """§ 3.4 Nr. 1: Die Stufen sind laut Stadt eine qualitative Einschätzung — fünf Zähler, kein Mittelwert."""
    stand = plan_pages.city_status_block("ernaehrungsstrategie")
    assert stand["total"] == 68 and stand["complete"] and stand["template_number"] == "26/0431"
    assert [c["count"] for c in stand["counts"]] == [10, 6, 11, 16, 25]
    assert all("Stufe" in c["status_raw"] for c in stand["counts"])
    assert any("qualitative Einschätzung" in n["text"] for n in stand["notes"])
    block = plan_pages.measures_block("ernaehrungsstrategie")
    assert block["status_count"] == 68


def test_wo_man_nachfragen_kann():
    """§ 3.5, Art 3: Tatsache mit Datum, nie eine Wertung — und nur Pläne ohne aktuellen Bericht."""
    card = lambda key, state, note, last: {  # noqa: E731
        "key": key, "title": key.title(), "kind": "action", "policy_field": "verkehr", "field_label": "Verkehr",
        "report_state": {"state": state, "label": plan_state.REPORT_STATE_LABELS[state], "hint": None},
        "report_note": note, "latest_report": {"date": last} if last else None}
    cards = [card("a", "reported", None, "2026-05-01"), card("b", "no_report_found", "Seit 03/2022 kein Bericht im Rat.", "2022-03-01"),
             card("c", "no_report_found", "Kein Umsetzungsbericht im Rat seit dem Beschluss.", None),
             card("d", "expired_no_evaluation", None, "2024-01-01"), card("e", "not_yet_due", None, None),
             {**card("f", "no_report_found", None, None), "kind": "reference"}]
    found = plan_pages.follow_ups(cards)
    assert [f["key"] for f in found] == ["c", "b", "d"]  # am längsten Stillen zuerst; ohne jeden Bericht ganz vorn
    assert found[2]["fact"] == "Laufzeit abgelaufen, keine Auswertung gefunden."
    assert all(f["question"].startswith("Was ist aus dem Plan") for f in found)
    for word in ("langsam", "säumig", "versäumt", "Verzug"):
        assert word not in " ".join(f["fact"] + f["question"] for f in found)
    assert "nicht gefunden" in plan_pages.FOLLOW_UP_CAVEAT.lower()
