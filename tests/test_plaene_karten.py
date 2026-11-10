"""Gebiete aus den Kartenbildern weiterer Pläne (``scripts/plan_karten.py``): Ruhige Gebiete, Maßnahmenbereiche
des Masterplans Stadtgrün, Suchräume der Spielleitplanung, Zentren des Einzelhandelskonzepts.

Nachgezeichnet wird lokal (PDF, numpy, Pillow, shapely, OSM); hier wird ohne all das gehalten, dass die
Dateien in Form sind und dass Karte, Viertel und Download sie so ausgeben, wie sie dastehen — gegen eine
leere Ratsdatenbank.
"""
from __future__ import annotations

import copy

import pytest

from council import plan_pages, plan_state, plans
from council.store import CouncilStore
from scripts import plan_karten


@pytest.fixture
def store(tmp_path):
    s = CouncilStore(tmp_path / "council.sqlite")
    yield s
    s.close()


def _block(store, key):
    block = plan_pages.places_block(store, plans.PLANS[key])
    assert block is not None
    return block


def test_die_dateien_sind_in_form():
    for key in plan_karten.BUILDERS:
        data = plan_state.plan_shapes(key)
        assert data is not None, f"{key}: python scripts/plan_karten.py --nur {key}"
        assert plan_karten.check(key, data) == [], "python scripts/plan_karten.py --pruefen"


def test_die_pruefung_schlaegt_an():
    data = copy.deepcopy(plan_state.plan_shapes("laermaktionsplan"))
    friedhof = next(f for f in data["features"] if f["properties"]["code"] == "107")
    friedhof["properties"]["area_ha_plan"] = 20.0
    first = data["features"][0]["geometry"]
    (first["coordinates"][0] if first["type"] == "Polygon" else first["coordinates"][0][0]).pop()  # offener Ring
    data["features"][3]["properties"]["label_point"] = [8.40, 53.30]
    data["features"][4]["properties"]["code"] = "99"
    problems = plan_karten.check("laermaktionsplan", data)
    assert any("statt 20.0 ha laut Plan" in p for p in problems)
    assert any("kein geschlossenes Polygon" in p for p in problems)
    assert any("nicht in Oldenburg" in p for p in problems)
    assert any("unbekannte Kennungen ['99']" in p for p in problems)
    eek = copy.deepcopy(plan_state.plan_shapes("eek"))
    point = next(f for f in eek["features"] if f["geometry"]["type"] == "Point")
    point["properties"]["area_ha"] = 3.0
    eek["features"] = eek["features"][:10] + [point]
    problems = plan_karten.check("eek", eek)
    assert any("Standort mit Fläche" in p for p in problems) and any("nur 11 Einträge" in p for p in problems)


def test_laermaktionsplan_zeigt_abschnitte_und_gebiete(store):
    block = _block(store, "laermaktionsplan")
    items = block["items"]
    # Abschnitte vorn, dann die Gebiete in der Reihenfolge der Datei.
    assert [bool(p["sections"]) for p in items[:10]] == [True] * 9 + [False]
    areas = [p for p in items if p["areas"]]
    assert len(areas) == 24 and {a["areas"][0]["group"] for a in areas} == {"Ruhiges Gebiet", "Friedhof",
                                                                             "Erholungsfläche"}
    first = areas[0]["areas"][0]
    assert first["label"] == f"Ruhiges Gebiet „{areas[0]['name']}“" and first["source_label"] == "Abb. 53, S. 152"
    # Die Gruppe steht nicht doppelt, wo der Name sie schon trägt.
    labels = {p["name"]: p["areas"][0]["label"] for p in areas}
    assert labels["Waldfriedhof Ofenerdiek"] == "Waldfriedhof Ofenerdiek"
    assert labels["Schlossgarten"] == "Erholungsfläche „Schlossgarten“"
    # Tabelle 28/29 steht auf S. 155, die Karte auf S. 154: Der Link zeigt auf die Zahlen.
    assert areas[-1]["areas"][0]["source_url"].endswith("#page=155")


def test_einzelhandel_mit_abgrenzungen_und_standorten(store):
    items = _block(store, "eek")["items"]
    assert len(items) == len(plan_karten.EEK_CENTRES)
    shapes = [p for p in items if p["geometry"]]
    sites = [p for p in items if not p["geometry"]]
    assert len(shapes) >= 10 and sites
    city = next(p for p in items if p["slug"] == "gebiet-innenstadt")
    a = city["areas"][0]
    assert a["group"] == "Zentraler Versorgungsbereich Innenstadt" and a["source_label"] == "Karte 34, S. 200"
    assert 25 < a["area_ha"] < 35 and city["geometry"]["type"] == "Polygon"
    site = sites[0]["areas"][0]
    assert site["area_ha"] is None and site["source_label"] == "Karte 33, S. 187"
    assert site["label"] == f"{site['group']} „{sites[0]['name']}“"


def test_masterplan_ohne_abbildungsnummer(store):
    a = _block(store, "masterplan_stadtgruen")["items"][0]["areas"][0]
    assert a["figure"] is None and a["source_label"] == "S. 77" and a["label"] == "Maßnahmenbereich „Innenstadt“"


def test_suchraeume_je_ortsbereich(store):
    items = _block(store, "spielleitplanung")["items"]
    assert len({p["slug"] for p in items}) == len(items)
    search = [p for p in items if p["areas"][0]["group"] == "Suchraum für Spielplätze"]
    assert {p["areas"][0]["label"] for p in search} == {"Suchraum für Spielplätze"}
    eversten = next(p for p in search if p["name"] == "Eversten")["areas"][0]
    # Spielplätze je Typ aus den Kreisen auf Karte 7, die Sätze des Plans zum Stadtteil mit Seite.
    assert eversten["facts"][0]["label"].startswith("Spielplätze im Stadtteil") and "Quartiers" in eversten["facts"][0]["value"]
    assert any("Eversten" in text for n in eversten["notes"] for text in n["items"])
    assert all(n["source_url"].endswith(f"#page={n['page']}") for n in eversten["notes"])
    planned = [p for p in items if p["areas"][0]["group"] == "Spielplatz in Planung"]
    assert len(planned) == 6 and all(p["geometry"] is None and p["areas"][0]["radius_m"] for p in planned)
    places_eversten = {p["key"]: p["places"] for p in plan_pages.district_plans(store, "eversten")}
    assert "Suchraum für Spielplätze" in places_eversten["spielleitplanung"]


def test_angaben_aus_dem_text_der_plaene(store):
    """Was die Pläne zu ihren Gebieten sagen — Kenndaten, Listen, Absätze —, je mit Seite."""
    eek = {p["slug"]: p["areas"][0] for p in _block(store, "eek")["items"]}
    eversten = eek["gebiet-hauptstrasse-eversten"]
    assert eversten["summary"] == "21 Betriebe · 2.000 m² Verkaufsfläche"
    assert {f["label"]: f["value"] for f in eversten["facts"]}["Leerstände 2021"] == "4 (2012: 2)"
    assert [n["title"] for n in eversten["notes"]] == ["Stärken", "Schwächen"]
    # Neu gezogene Abgrenzung: Die Zahlen gelten für die alte, und das steht dabei.
    assert any(f["label"] == "Bezug der Zahlen" for f in eek["gebiet-innenstadt"]["facts"])
    assert not any(f["label"] == "Bezug der Zahlen" for f in eversten["facts"])
    msg = _block(store, "masterplan_stadtgruen")["items"][0]["areas"][0]
    assert [n["title"] for n in msg["notes"]] == ["Defizite", "Handlungskonzept", "Maßnahmen"]
    assert msg["notes"][2]["kind"] == "text" and "Pocket Parks" in " ".join(msg["notes"][2]["items"])
    noise = {p["name"]: p["areas"][0] for p in _block(store, "laermaktionsplan")["items"] if p["areas"]}
    assert noise["Waldfriedhof Ofenerdiek"]["facts"][0]["value"] == "1,3 %"
    heat = {p["slug"]: p["areas"][0] for p in _block(store, "waermeplan")["items"]}
    wechloy = {f["label"]: f["value"] for f in heat["gebiet-wng-2"]["facts"]}
    assert wechloy["Versorgung laut Plan"] == "Luft-Großwärmepumpe und Biomasse" and wechloy["Gebäude"] == "588"
    # WNG 10: Der Plan schreibt „MWh“, wo Tabelle 4 GWh nennt — der Wert für 2035 fällt weg statt falsch dazustehen.
    assert "Wärmebedarf 2035" not in {f["label"] for f in heat["gebiet-wng-10"]["facts"]}


def test_arten_mit_erklaerung_und_randstil(store):
    groups = _block(store, "eek")["groups"]
    assert [g["name"] for g in groups][:2] == ["Zentraler Versorgungsbereich Innenstadt", "Nahversorgungszentrum"]
    assert all(g["description"] and g["source_url"].endswith(f"#page={g['page']}") for g in groups)
    assert [g["style"] for g in groups] == [0, 1, 2, 3, 0]
    assert {g["name"]: g["sites_only"] for g in groups}["Nahversorgungsstandort"] is True
    assert _block(store, "waermeplan")["groups"][0]["name"] == "Eignungsgebiet"
    assert plan_pages.places_block(store, plans.PLANS["kita_ausbau"]) is None


def test_viertel_kennt_die_neuen_gebiete(store):
    def places_in(place_id):
        return {p["key"]: p["places"] for p in plan_pages.district_plans(store, place_id)}
    eversten = places_in("eversten")
    assert "Maßnahmenbereich „Eversten“" in eversten["masterplan_stadtgruen"]
    # Das Einzelhandelskonzept ist ein Nachschlagewerk (kind="reference") — es steht nicht unter den Plänen
    # im Viertel, auch mit Gebieten nicht.
    assert "eek" not in eversten
    assert "Ruhiges Gebiet „Huntewiesen“" in places_in("bornhorst")["laermaktionsplan"]


def test_download_unterscheidet_gebiet_und_standort(store):
    data = plan_pages.geojson_export(store, plans.PLANS["eek"])
    assert data is not None
    kinds = {f["properties"]["kind"] for f in data["features"]}
    assert kinds == {"area", "site"}
    site = next(f for f in data["features"] if f["properties"]["kind"] == "site")
    assert site["geometry"]["type"] == "Point" and site["properties"]["area_ha"] is None
    assert "OpenStreetMap" in data["attribution"] and "Einzelhandelsentwicklungskonzept" in data["attribution"]
