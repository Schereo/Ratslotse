"""Abschnitte und Tabellen aus den Plan-Dokumenten, Stadterneuerungsgebiete im Viertel.

Die Dateien (``council/plan_lists/``, ``council/stadterneuerung.json``) sind eingecheckt und von
Hand gesetzt; hier wird gehalten, dass sie in Form sind und dass die Seite sie so ausgibt, wie sie
dastehen — ohne PDF, ohne Netz, gegen eine leere Ratsdatenbank.
"""
from __future__ import annotations

import copy

import pytest

from council import plan_pages, plan_state, plans, stadterneuerung
from council.store import CouncilStore
from scripts import plan_listen
from scripts import stadterneuerung as erneuerung


@pytest.fixture
def store(tmp_path):
    s = CouncilStore(tmp_path / "council.sqlite")
    yield s
    s.close()


def test_die_dateien_sind_in_form():
    assert plan_state.list_keys() == ["laermaktionsplan", "waermeplan"]
    for key in plan_state.list_keys():
        assert plan_listen.check(key, plan_state.plan_lists(key) or {}) == [], \
            f"{key}: python scripts/plan_listen.py --pruefen"
    assert erneuerung.check(stadterneuerung.data()) == [], "python scripts/stadterneuerung.py --pruefen"


def test_die_pruefung_schlaegt_an():
    data = copy.deepcopy(plan_state.plan_lists("laermaktionsplan"))
    data["sections"][0]["length_m"] = 40
    data["sections"][1]["quote"] = "Die Nadorster Straße ist laut."
    data["lists"][0]["rows"].pop(3)
    # Ein gleichnamiges Stück der Nachbargemeinde (so kam die „Bremer Straße“ aus Hatten mit).
    data["sections"][4]["geometry"]["coordinates"].append([[8.3004, 53.0993], [8.3010, 53.0996]])
    problems = plan_listen.check("laermaktionsplan", data)
    assert any("außerhalb Oldenburgs" in p for p in problems)
    assert any("40 m lang" in p for p in problems)
    assert any("nicht der Vorschlag" in p for p in problems)
    assert any("Rangfolge lückenhaft" in p for p in problems)


def test_jeder_abschnitt_traegt_seinen_vorschlag_und_seine_seite():
    data = plan_state.plan_lists("laermaktionsplan")
    assert [s["code"] for s in data["sections"]] == [e["code"] for e in plan_listen.SECTIONS]
    for s, e in zip(data["sections"], plan_listen.SECTIONS):
        assert e["phrase"] in s["quote"] and s["page"] == e["page"]


def test_abschnitte_stehen_auf_der_karte(store):
    block = plan_pages.places_block(store, plans.PLANS["laermaktionsplan"])
    assert block is not None and block["section_places"] == 9
    # Dazu die Ruhigen Gebiete aus seinen Karten (scripts/plan_karten.py) — Abschnitte stehen vorn.
    assert block["area_places"] == 24 and block["note"] == plan_pages.SECTIONS_AREAS_NOTE
    first = block["items"][0]
    assert first["slug"] == "abschnitt-18.2.1" and first["geometry"]["type"] == "MultiLineString"
    assert first["sections"][0]["source_url"].endswith("id=280381&type=do#page=64")
    # Die Ortsbereiche rechnet das Skript mit; die Seite gibt sie nicht aus.
    assert all("districts" not in p for p in block["items"])


def test_ruhige_gebiete_stehen_alle_in_der_tabelle():
    """Nachgezeichnet sind nur die, die auf der Karte groß genug sind; die Tabellen tragen alle."""
    lists = {lst["key"]: lst for lst in plan_pages.lists_block(plans.PLANS["laermaktionsplan"])}
    assert list(lists) == ["hotspots", "quiet_areas", "quiet_cemeteries", "quiet_recreation"]
    quiet = lists["quiet_areas"]["rows"]
    assert len(quiet) == 18 and quiet[14]["cells"] == ["15", "Hausbäkenniederung-Everstenmoor", "353,5"]
    assert [len(lists[k]["rows"]) for k in ("quiet_cemeteries", "quiet_recreation")] == [11, 7]
    assert lists["quiet_cemeteries"]["rows"][0]["cells"] == ["101", "Waldfriedhof Ofenerdiek", "10,0", "1,3%"]


def test_tabellen_stehen_wie_im_dokument():
    lists = plan_pages.lists_block(plans.PLANS["waermeplan"])
    assert [lst["key"] for lst in lists] == ["heat_network_areas"]
    rows = lists[0]["rows"]
    assert len(rows) == 11 and rows[0]["cells"] == ["WNG 1", "Innenstadt", "Stadtkern", "131 GWh/a", "5,2 MWh/m*a"]
    assert rows[0]["source_url"].endswith("#page=80") and lists[0]["source_url"].endswith("#page=79")
    assert lists[0]["columns"][lists[0]["name_column"]] == "Gebiet"
    assert plan_pages.lists_block(plans.PLANS["kita_ausbau"]) == []


def test_viertel_kennt_abschnitte_und_gebiete(store):
    by_key = {p["key"]: p for p in plan_pages.district_plans(store, "eversten")}
    assert by_key["laermaktionsplan"]["places"][:2] == ["Hauptstraße", "Hundsmühler Straße"]
    assert by_key["waermeplan"]["places"] == ["Eignungsgebiet „WNG 7 Kennedyviertel“",
                                               "Eignungsgebiet „WNG 8 Wilhelm-Raabe-Str.“"]
    # Die nachgezeichnete Fläche entscheidet, nicht die Ortsteil-Spalte der Tabelle: „WNG Ohmstede“ steht dort
    # unter Donnerschwee, liegt aber ganz in Ohmstede.
    def heat(place_id):
        return {p["key"]: p["places"] for p in plan_pages.district_plans(store, place_id)}.get("waermeplan", [])
    assert heat("ohmstede") == ["Eignungsgebiet „WNG 3 Ohmstede“"]
    assert "Eignungsgebiet „WNG 3 Ohmstede“" not in heat("donnerschwee")
    # Ein kleiner Teil zählt, wenn er groß genug ist: 9 % von Kreyenbrück (15 ha) liegen in Osternburg.
    assert heat("osternburg") == ["Eignungsgebiet „WNG 9 Kreyenbrück“"]


def test_stadterneuerung_je_ortsbereich():
    assert [a["name"] for a in stadterneuerung.for_district("kreyenbrueck")] == ["Kreyenbrück-Nord"]
    osternburg = stadterneuerung.for_district("osternburg")
    assert [a["name"] for a in osternburg] == ["Kreyenbrück-Nord", "Alter Stadthafen"]
    assert osternburg[0]["funding_eur"] == 22_500_000 and osternburg[0]["own_funds_eur"] == 7_100_000
    # Unter einem Zehntel der Fläche gehört ein Gebiet nicht zum Ortsbereich.
    assert stadterneuerung.for_district("drielake") == []


def test_betraege_wie_die_stadt_sie_schreibt():
    assert erneuerung.euro("22,5 Millionen Euro") == 22_500_000
    assert erneuerung.euro("130 Millionen Euro") == 130_000_000
    with pytest.raises(SystemExit):
        erneuerung.euro("rund 5 Mio.")
