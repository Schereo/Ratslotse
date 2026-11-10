"""Ausbau der Pläne-Seiten: Kernpunkte nach Art, Zahlen als Kacheln, Termine im Zeitband,
Sprungleiste, Ansichten der Übersicht.

Was hier feststeht:

- Die Zahl einer Kachel und der Termin fürs Zeitband sind von Hand gesetzt — und kommen nur auf
  die Seite, wenn sie im Zitat des Kernpunkts stehen (``plan_judge.check_extras``).
- Jeder Kernpunkt steht in genau einer Gruppe, die Gruppen in fester Reihenfolge.
- Ein Termin ist eine Angabe aus dem Plan: Er liegt auf der Achse oder gar nicht, und er
  verdoppelt nicht das Laufzeitende.
- Die Ansichten der Übersicht reihen nach Datum, nie nach gut oder schlecht (Plan § 3.4), und
  nennen keine Verweis-Pläne.
- Die Sprungleiste nennt nur Abschnitte, die es auf dem Plan gibt.

Alles gegen eine leere Ratsdatenbank: Register und Kernpunkte sind Dateien im Repo.
"""
from __future__ import annotations

import pytest

from council import plan_judge, plan_pages, plan_state, plans
from council.store import CouncilStore
from scripts import plan_kernpunkte

TODAY = "2026-11-10"
QUOTE = "Als Zwischenziel ist eine Reduktion um 62,5 Prozent bis 2030 gegenüber dem Ausgangsjahr 2023 festgelegt."


@pytest.fixture
def store(tmp_path):
    s = CouncilStore(tmp_path / "council.sqlite")
    yield s
    s.close()


# ── Von Hand gesetzt, ohne Modell geprüft ──────────────────────────────────

def point(**extra) -> dict:
    return {"text": "Bis 2030 sollen die Emissionen um 62,5 Prozent sinken.", "kind": "figure", "quote": QUOTE, **extra}


def test_kachel_nennt_nur_zahlen_aus_dem_zitat():
    assert plan_judge.check_extras(point(figure={"value": "62,5 %", "label": "weniger Emissionen bis 2030 als 2023"})) == []
    wrong = plan_judge.check_extras(point(figure={"value": "65 %", "label": "weniger Emissionen"}))
    assert wrong and "65" in wrong[0]
    assert plan_judge.check_extras(point(figure={"value": "62,5 %", "label": "weniger Emissionen bis 2040"}))


def test_kachel_darf_ein_ausgeschriebenes_zahlwort_als_ziffer_setzen():
    quote = "Innerhalb Oldenburgs wurden mindestens drei Standorte entwickelt."
    ok = {"text": "Mindestens drei Standorte.", "quote": quote, "figure": {"value": "mind. 3", "label": "Standorte"}}
    assert plan_judge.check_extras(ok) == []
    assert plan_judge.check_extras({**ok, "figure": {"value": "mind. 4", "label": "Standorte"}})


def test_kachel_braucht_zahl_und_kurzes_wort():
    assert plan_judge.check_extras(point(figure={"value": "", "label": "Emissionen"}))
    assert plan_judge.check_extras(point(figure={"value": "62,5 %", "label": "x" * (plan_judge.FIGURE_LABEL_MAX + 1)}))
    assert plan_judge.check_extras(point(figure={"value": "62,5 Prozent weniger", "label": "Emissionen"}))


def test_termin_nennt_nur_jahre_aus_dem_zitat():
    assert plan_judge.check_extras(point(due={"date": "2030", "at": "end", "label": "bis 2030"})) == []
    assert plan_judge.check_extras(point(due={"date": "2031", "at": "end", "label": "bis 2031"}))
    # Das Jahr des Datums steht im Text des Termins — sonst zeigte die Marke woanders hin, als sie sagt.
    assert plan_judge.check_extras(point(due={"date": "2030", "at": "end", "label": "bald"}))
    # Ohne Tag muss feststehen, ob der Anfang oder das Ende des Zeitraums gemeint ist.
    assert plan_judge.check_extras(point(due={"date": "2030", "label": "bis 2030"}))
    assert plan_judge.check_extras(point(due={"date": "30.06.2030", "label": "bis 2030"}))


def test_neuer_lauf_behaelt_zusaetze_nur_am_selben_zitat():
    """``scripts/plan_kernpunkte.py`` schreibt die Datei neu. Was von Hand daran hängt, bleibt — aber
    nur, solange das Zitat dasselbe ist: An einer anderen Stelle ist die Zahl nicht mehr belegt."""
    previous = {"points": [point(figure={"value": "62,5 %", "label": "weniger"}, due={"date": "2030", "at": "end", "label": "bis 2030"})]}
    same = {"points": [{"text": "Neu formuliert.", "kind": "figure", "quote": QUOTE.replace(" ", "  ")}]}
    plan_kernpunkte.carry_extras(same, previous)
    assert same["points"][0]["figure"]["value"] == "62,5 %" and same["points"][0]["due"]["date"] == "2030"
    other = {"points": [{"text": "Neu.", "kind": "figure", "quote": "Eine andere Stelle im Plan mit 62,5 Prozent."}]}
    plan_kernpunkte.carry_extras(other, previous)
    assert "figure" not in other["points"][0] and "due" not in other["points"][0]
    plan_kernpunkte.carry_extras(other, None)


# ── Kernpunkte nach Art ────────────────────────────────────────────────────

@pytest.mark.parametrize("key", plan_state.key_point_keys())
def test_jeder_kernpunkt_steht_in_genau_einer_gruppe(store, key):
    data = plan_state.key_points(key)
    block = plan_pages.content_block(store, plans.PLANS[key])
    order = [g["key"] for g in block["groups"]]
    assert order == [k for k, _kinds in plan_pages.CONTENT_GROUPS if k in order], "Reihenfolge der Gruppen"
    seen = sorted(p["index"] for g in block["groups"] for p in g["points"])
    assert seen == list(range(len(data["points"]))) and block["count"] == len(seen)
    for group in block["groups"]:
        assert group["points"] and group["label"]
        tiles = group["key"] == "figures"
        assert group["layout"] == ("tiles" if tiles else "list")
        for p in group["points"]:
            assert (p["figure"] is not None) == tiles, "eine Kachel braucht ihre Zahl — und nur sie hat eine"
            assert p["text"] == data["points"][p["index"]]["text"]
        kinds = {p["kind"] for p in group["points"]}
        # Das Wort an der Zeile steht nur, wo die Gruppe zwei Arten mischt.
        assert all(p["tag"] is None for p in group["points"]) or (len(kinds) > 1 and not tiles)


def test_ueberschrift_einer_gruppe_nennt_was_darin_steht():
    assert plan_pages._group_label("goals", ["goal"]) == "Ziel"
    assert plan_pages._group_label("goals", ["goal", "goal"]) == "Ziele"
    assert plan_pages._group_label("figures", ["standard"]) == "Zahl"
    assert plan_pages._group_label("figures", ["figure", "goal"]) == "Zahlen"
    assert plan_pages._group_label("rules", ["responsibility", "standard"]) == "Regeln und Zuständigkeiten"
    assert plan_pages._group_label("steps", ["deadline", "measure"]) == "Vorhaben und Termine"
    assert plan_pages._group_label("steps", ["deadline"]) == "Termin"


def test_schulverpflegung_zeigt_die_bio_vorgabe_als_kachel(store):
    block = plan_pages.content_block(store, plans.PLANS["schulverpflegung"])
    tiles = next(g for g in block["groups"] if g["key"] == "figures")
    assert [p["figure"]["value"] for p in tiles["points"]] == ["100 %"]
    assert tiles["points"][0]["amended"], "der heutige Stand, nicht der von 2019"
    assert block["purpose"]["index"] is None and block["purpose"]["figure"] is None


def test_kurzfassung_fuer_die_uebersicht(store):
    cards = {p["key"]: p for g in plan_pages.overview(store, TODAY)["groups"] for p in g["plans"]}
    brief = cards["schulverpflegung"]["brief"]
    block = plan_pages.content_block(store, plans.PLANS["schulverpflegung"])
    assert brief["purpose"] == block["purpose"]["text"] and brief["heading"] == block["heading"]
    assert brief["points"] == [p["text"] for g in block["groups"] for p in g["points"]][:2] and brief["count"] == block["count"]
    assert cards["kai_2015"]["brief"] is None, "ohne Plantext keine Kurzfassung"


# ── Termine im Zeitband ────────────────────────────────────────────────────

def test_termin_liegt_an_seinem_tag(store):
    runway = plan_pages.detail(store, "schulverpflegung", TODAY)["runway"]
    dues = {d["label"]: d for d in runway["dues"]}
    assert dues["Käse ab Schuljahr 2026/2027"]["date"] == "2026-08-01"
    assert dues["ab Schuljahr 2025/2026"]["date"] == "2025-08-01"
    assert all(0 <= d["x"] <= 1 for d in runway["dues"])
    points = plan_state.key_points("schulverpflegung")["points"]
    assert all(points[d["point"]]["text"] == d["text"] for d in runway["dues"])


def test_termin_zieht_die_achse_eines_laufenden_plans_mit(store):
    """Die Ernährungsstrategie hat kein Enddatum; ihr Band liefe bis 2029 aus. „Bis 2030“ steht im
    Plan — die Achse reicht deshalb bis 2030."""
    runway = plan_pages.detail(store, "ernaehrungsstrategie", TODAY)["runway"]
    assert runway["end"] == "2030-12-31" and [d["label"] for d in runway["dues"]] == ["bis 2030"]


def test_termin_weit_hinter_dem_horizont_staucht_die_achse_nicht(store):
    """„Im Jahr 2050“ (ISEK) liegt weiter vorn, als die Übersicht schaut: keine Marke, und die Achse
    endet weiter mit der Laufzeit."""
    runway = plan_pages.detail(store, "isek_2035", TODAY)["runway"]
    assert runway["end"] == "2035-12-31" and not any("2050" in d["label"] for d in runway["dues"])


def test_termin_im_jahr_des_laufzeitendes_steht_nicht_doppelt():
    plan = plans.PLANS["thg_neutrale_verwaltung"]
    assert plan.end == "2035"
    labels = [d["label"] for d in plan_pages.due_marks(plan, "2025-01-01", "2035-12-31")]
    assert "bis 2030" in labels and not any("2035" in label for label in labels)


def test_abgelaufener_plan_bekommt_keine_laengere_achse(store):
    runway = plan_pages.detail(store, "smv2025", TODAY)["runway"]
    assert runway["end"] < "2030-01-01" and runway["dues"] == []


# ── Ansichten der Übersicht ────────────────────────────────────────────────

def card(key: str, **over) -> dict:
    base = {"key": key, "title": key, "kind": "action_plan", "status": "running", "latest_report": None,
            "ends_on": None, "adopted_on": "2020-01-01"}
    return {**base, **over}


def test_ansichten_reihen_nach_datum():
    cards = [
        card("alt", latest_report={"date": "2023-05-01"}, ends_on="2030-12-31"),
        card("frisch", latest_report={"date": "2026-09-01"}, ends_on="2027-12-31"),
        card("still", adopted_on="2019-03-01"),
        card("jung", adopted_on="2026-06-01"),
        card("vorbei", status="expired", latest_report={"date": "2026-01-01"}),
        card("fremd", kind="reference", latest_report={"date": "2026-10-01"}, ends_on="2026-12-31"),
    ]
    views = {v["key"]: v for v in plan_pages.views(cards, TODAY)}
    assert views["recent"]["plans"] == ["frisch", "vorbei", "alt"]
    assert views["ending"]["plans"] == ["frisch", "alt"]
    # Am längsten Stillen zuerst: ohne Bericht zählt der Beschluss. Ein Plan, der jünger als ein Jahr
    # ist oder im letzten Jahr berichtet hat, steht nicht darin; ein abgelaufener auch nicht.
    assert views["silent"]["plans"] == ["still", "alt"]
    assert all("fremd" not in v["plans"] for v in views.values())


def test_ansichten_der_echten_uebersicht_kennen_nur_plaene_der_liste(store):
    overview = plan_pages.overview(store, TODAY)
    listed = {p["key"] for g in overview["groups"] for p in g["plans"]}
    assert [v["key"] for v in overview["views"]] == ["recent", "ending", "silent"]
    for view in overview["views"]:
        assert set(view["plans"]) <= listed and len(view["plans"]) == len(set(view["plans"])) and view["hint"]
    ending = [p for g in overview["groups"] for p in g["plans"] if p["ends_on"]]
    assert ending and all(p["ends_in"] and p["status"] == "running" for p in ending)


# ── Sprungleiste ───────────────────────────────────────────────────────────

def test_sprungleiste_nennt_nur_was_es_gibt(store):
    full = {s["key"]: s for s in plan_pages.detail(store, "klimaschutzplan_2035", TODAY)["sections"]}
    # Gegen die leere Datenbank: keine Beschlüsse, also kein Punkt dafür.
    assert list(full) == ["content", "reports", "status", "indicators", "measures"]
    assert full["measures"]["count"] == 90 and full["content"]["count"] == 5 and full["status"]["count"] is None
    assert full["indicators"]["label"] == "Kennzahl"
    bare = plan_pages.detail(store, "kai_2015", TODAY)["sections"]
    assert [s["key"] for s in bare] == ["review", "reports"] or [s["key"] for s in bare] == ["reports"]


def test_stand_laut_stadt_traegt_die_bewegung_je_jahr(store):
    series = plan_pages.detail(store, "klimaschutzplan_2035", TODAY)["city_status"]["series"]
    assert series[0]["movement"] is None and all(s["movement"] for s in series[1:])
    last = series[-1]["movement"]
    assert last["since_label"] == series[-2]["as_of_label"] and last["total_delta"] == series[-1]["total"] - series[-2]["total"]
