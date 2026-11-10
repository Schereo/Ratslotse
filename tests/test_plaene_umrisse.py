"""Umrisse aus den Kartenbildern des Wärmeplans (``council/plan_shapes/``, ``scripts/plan_umrisse.py``).

Nachgezeichnet wird lokal (PDF, numpy, Pillow, shapely); hier wird ohne all das gehalten, dass die
Datei in Form ist, dass sie zu den Flächen im Plan passt und dass Seite und Download sie so ausgeben,
wie sie dasteht — gegen eine leere Ratsdatenbank.
"""
from __future__ import annotations

import copy

import pytest

from council import plan_pages, plan_state, plans
from council.store import CouncilStore
from scripts import plan_umrisse


@pytest.fixture
def store(tmp_path):
    s = CouncilStore(tmp_path / "council.sqlite")
    yield s
    s.close()


def test_die_datei_ist_in_form():
    data = plan_state.plan_shapes("waermeplan")
    assert data is not None and plan_umrisse.check(data) == [], "python scripts/plan_umrisse.py --pruefen"
    assert plan_state.shape_keys() == ["waermeplan"]


def test_die_flaechen_passen_zum_plan():
    data = plan_state.plan_shapes("waermeplan")
    stated = {f["properties"]["code"]: f["properties"] for f in data["features"] if f["properties"]["area_ha_plan"]}
    assert set(stated) == set(plan_umrisse.STATED_HA)
    for code, p in stated.items():
        assert abs(p["area_ha"] / p["area_ha_plan"] - 1) <= plan_umrisse.AREA_TOLERANCE, code


def test_die_pruefung_schlaegt_an():
    data = copy.deepcopy(plan_state.plan_shapes("waermeplan"))
    data["features"][5]["properties"]["area_ha_plan"] = 20.0
    ring = data["features"][2]["geometry"]["coordinates"][0]
    ring.pop()  # Ring nicht mehr geschlossen
    data["features"][7]["properties"]["label_point"] = [8.40, 53.30]
    problems = plan_umrisse.check(data)
    assert any("statt 20.0 ha laut Plan" in p for p in problems)
    assert any("kein geschlossenes Polygon" in p for p in problems)
    assert any("Beschriftungspunkt" in p for p in problems)


def test_punkt_im_polygon_ohne_shapely():
    square = {"type": "Polygon", "coordinates": [[[8.0, 53.0], [8.1, 53.0], [8.1, 53.1], [8.0, 53.1], [8.0, 53.0]]]}
    assert plan_umrisse.contains(square, 8.05, 53.05) and not plan_umrisse.contains(square, 8.2, 53.05)
    assert 7300 < plan_umrisse.area_ha(square) < 7450  # gut 74 km² bei 53° Breite (6,7 km × 11,1 km)


def test_gebiete_stehen_als_flaeche_auf_der_karte(store):
    block = plan_pages.places_block(store, plans.PLANS["waermeplan"])
    assert block is not None and block["area_places"] == 11 and block["geojson"] is True
    assert block["note"] == plan_pages.AREAS_NOTE
    first = block["items"][0]
    assert first["slug"] == "gebiet-wng-1" and first["kind"] == "area" and first["geometry"]["type"] == "Polygon"
    assert first["areas"][0]["source_url"].endswith("id=306748&type=do#page=82")
    assert all("districts" not in p for p in block["items"])


def test_download_enthaelt_abschnitte_und_gebiete(store):
    heat = plan_pages.geojson_export(store, plans.PLANS["waermeplan"])
    assert heat["type"] == "FeatureCollection" and len(heat["features"]) == 11
    assert heat["features"][0]["geometry"] == plan_state.plan_shapes("waermeplan")["features"][0]["geometry"]
    noise = plan_pages.geojson_export(store, plans.PLANS["laermaktionsplan"])
    assert [f["properties"]["kind"] for f in noise["features"]] == ["section"] * 9
    assert "OpenStreetMap" in noise["attribution"]
    assert plan_pages.geojson_export(store, plans.PLANS["kita_ausbau"]) is None


def test_download_braucht_ein_konto():
    from tests.test_endpunkt_schutz import _endpunkte
    found = {path: names for _method, path, names in _endpunkte()}
    assert "require_active" in found["/api/council/plan/{key}/geojson"]
