"""Pläne der Stadt, Paket 3: Karte zum Plan, Pläne im Viertel, Haushalt zum Plan.

Was hier feststeht:

- Auf die Karte kommen nur konkrete Orte mit Koordinaten — aus einem Maßnahmentitel (von Hand
  durchgesehen, ``council/plan_places/``) oder aus der Ortszuordnung der Umsetzungs- und
  Berichtsbeschlüsse. Keine Stadtteile als Punkt, keine Gattungswörter („Car-Sharing“), keine
  unsichere Zuordnung; nennt ein Beschluss eine Adresse, steht die Straße nicht noch einmal da.
  Den Verlauf zeichnet nur eine Straße aus der Maßnahmenliste.
- Im Viertel zählt eine Straße aus der Maßnahmenliste überall, wo ein nennenswerter Teil liegt;
  eine Straße aus einem Beschluss nur in ihrem Hauptbereich.
- Im Haushalt steht nur, was den Plan beim Namen nennt; von zwei Stufen einer Änderung zählt die
  spätere; Beträge ungerundet.

Gegen leere Datenbanken mit wenigen, von Hand gesetzten Zeilen.
"""
from __future__ import annotations

import json

import pytest

from council import plan_pages, plan_state, plans
from council.store import CouncilStore
from scripts import plan_haushalt, plan_orte

NOW = "2026-11-10T00:00:00"
LINE = json.dumps({"type": "LineString", "coordinates": [[8.2, 53.14], [8.20001, 53.14001], [8.201, 53.141], [8.202, 53.142]]})


@pytest.fixture
def store(tmp_path):
    s = CouncilStore(tmp_path / "council.sqlite")
    yield s
    s.close()


def location(store, slug, name, kind, lat=53.14, lon=8.2, geojson=None, areas=(("kreyenbrueck", 1.0),)):
    store._conn.execute(
        "INSERT INTO council_locations (slug, name, kind, lat, lon, geojson, local_area_id, updated_at) VALUES (?,?,?,?,?,?,?,?)",
        (slug, name, kind, lat, lon, geojson, "la-1", NOW))
    for place_id, share in areas:
        store._conn.execute("INSERT INTO council_location_districts (location_slug, district, place_id, share) VALUES (?,?,?,?)",
                            (slug, place_id, place_id, share))


def decision(store, plan_key, n, date, role="implementation", places=(), title="Umsetzung"):
    store._conn.execute("INSERT INTO council_sessions (ksinr, committee, session_date, session_time, location, fetched_at) "
                        "VALUES (?,?,?,?,?,?)", (n, "Rat", date, "17:00", "Rathaus", NOW))
    store._conn.execute("INSERT INTO council_decisions (id, ksinr, position, title) VALUES (?,?,?,?)", (n, n, 1, title))
    store._conn.execute("INSERT INTO council_plan_items (plan_key, agenda_item_id, ksinr, date, title, role, decision_id) "
                        "VALUES (?,?,?,?,?,?,?)", (plan_key, n, n, date, title, role, n))
    for slug, confidence in places:
        store._conn.execute("INSERT INTO council_decision_locations (decision_id, location_slug, source, evidence, method, "
                            "confidence, updated_at) VALUES (?,?,?,?,?,?,?)", (n, slug, "text", "…", "test", confidence, NOW))


# ── Karte ──────────────────────────────────────────────────────────────────

def test_orte_aus_beschluessen_nur_konkret_sicher_und_ohne_doppelte_strasse(store):
    location(store, "dedestrasse", "Dedestraße", "street")
    location(store, "dedestrasse-5", "Dedestraße 5", "building")
    location(store, "car-sharing", "Car-Sharing", "street")
    location(store, "kreyenbrueck", "Kreyenbrück", "district")
    location(store, "bahnweg", "Bahnweg", "street", geojson=LINE)
    location(store, "unsicher", "Unsicherweg", "street")
    decision(store, "kita_ausbau", 1, "2025-11-19", places=[("dedestrasse", 0.9), ("dedestrasse-5", 0.9), ("car-sharing", 0.98),
                                                           ("kreyenbrueck", 0.99), ("unsicher", 0.75)])
    decision(store, "kita_ausbau", 2, "2024-09-18", places=[("bahnweg", 0.94)])
    decision(store, "kita_ausbau", 3, "2024-01-01", role="motion", places=[("bahnweg", 0.94)])
    names = {p["name"]: p for p in plan_pages.plan_places(store, plans.PLANS["kita_ausbau"])}
    assert set(names) == {"Dedestraße 5", "Bahnweg"}
    # Ein Beschluss meint nicht die ganze Straße: kein Verlauf, nur der Punkt. Ein Antrag zählt nicht.
    assert names["Bahnweg"]["geometry"] is None and names["Bahnweg"]["decision_count"] == 1
    assert names["Dedestraße 5"]["decisions"][0] == {"id": 1, "title": "Umsetzung", "date": "2025-11-19"}


def test_strassen_aus_der_massnahmenliste_tragen_ihren_verlauf(store):
    named = plan_state.measure_places("mobilitaetsplan_2030")["measures"][:3]
    for entry in named:
        place = entry["places"][0]
        location(store, place["slug"], place["name"], "street", geojson=LINE)
    block = plan_pages.places_block(store, plans.PLANS["mobilitaetsplan_2030"])
    assert block and len(block["items"]) == 3 and block["measures_named"] == 3 and block["measures_total"] == 33
    for item in block["items"]:
        assert item["measures"] and item["geometry"]["type"] == "MultiLineString"
        line = item["geometry"]["coordinates"][0]
        # Anfang und Ende bleiben, dichte Stützpunkte fallen, gerundet auf fünf Stellen.
        assert line[0] == [8.2, 53.14] and line[-1] == [8.202, 53.142] and len(line) == 3


def test_unter_drei_orten_keine_karte(store):
    location(store, "dedestrasse-5", "Dedestraße 5", "building")
    decision(store, "kita_ausbau", 1, "2025-11-19", places=[("dedestrasse-5", 0.9)])
    assert plan_pages.places_block(store, plans.PLANS["kita_ausbau"]) is None
    assert plan_pages.places_block(store, plans.PLANS["spielleitplanung"]) is None


def test_massnahmen_orte_stehen_im_titel_und_sind_nicht_verworfen():
    for key in plan_state.measure_place_keys():
        assert plan_orte.check(None, key) == [], key
    for (plan, code, name), why in plan_orte.REJECTED.items():
        listed = plans.measures(plan)
        assert listed and any(m["code"] == code and name.lower() in m["title"].lower() for m in listed["measures"]), (plan, code)
        assert why.strip()
    assert plan_orte.GENERIC is plan_pages.PLACE_GENERIC, "eine Liste der Gattungswörter, nicht zwei"


# ── Pläne im Viertel ───────────────────────────────────────────────────────

def test_viertel_zaehlt_massnahmenstrassen_breit_und_beschlussstrassen_nur_im_hauptbereich(store):
    entry = plan_state.measure_places("mobilitaetsplan_2030")["measures"][0]
    street = entry["places"][0]
    location(store, street["slug"], street["name"], "street", geojson=LINE, areas=(("bloherfelde", 1.0), ("haarentor", 0.44)))
    location(store, "alexanderstrasse", "Alexanderstraße", "street", areas=(("buergerfelde", 1.0), ("ziegelhof", 0.18)))
    location(store, "bahnweg", "Bahnweg", "street", areas=(("buergerfelde", 1.0),))
    location(store, "bahnweg-84", "Bahnweg 84", "building", areas=(("buergerfelde", 1.0),))
    decision(store, "wohnungslosen_suchthilfe", 1, "2024-04-23", role="report", places=[("alexanderstrasse", 0.9)])
    decision(store, "kita_ausbau", 2, "2025-11-19", places=[("bahnweg", 0.9)])
    decision(store, "kita_ausbau", 3, "2024-11-19", places=[("bahnweg-84", 0.9)])

    def keys(place_id):
        return {p["key"]: p for p in plan_pages.district_plans(store, place_id, "2026-11-10")}

    assert set(keys("haarentor")) == {"mobilitaetsplan_2030"}, "ein nennenswerter Teil der Fahrradstraße liegt dort"
    assert set(keys("ziegelhof")) == set(), "die Alexanderstraße aus einem Bericht zählt nur in Bürgerfelde"
    here = keys("buergerfelde")
    assert set(here) == {"wohnungslosen_suchthilfe", "kita_ausbau"}
    assert here["kita_ausbau"]["places"] == ["Bahnweg 84"], "die Straße fällt, wo eine Adresse an ihr steht"
    assert here["kita_ausbau"]["via_measures"] is False and here["kita_ausbau"]["status_label"] == "läuft"


def test_abgelaufene_plaene_stehen_nicht_im_viertel(store):
    entry = plan_state.measure_places("smv2025")["measures"][0]
    street = entry["places"][0]
    location(store, street["slug"], street["name"], "street", areas=(("innenstadt", 1.0),))
    assert plan_pages.status(plans.PLANS["smv2025"], "2026-11-10") != "running"
    assert plan_pages.district_plans(store, "innenstadt", "2026-11-10") == []


# ── Haushalt ───────────────────────────────────────────────────────────────

def test_haushalt_zeigt_nur_posten_die_den_plan_nennen(store):
    for year in (2023, 2024, 2025, 2026):
        basis = "Ratsbeschluss Klimaschutzplan Oldenburg 2035 (19.12.2022)" if year >= 2024 else "Klimaschutzgesetz"
        store._conn.execute("INSERT INTO council_products (year, product_no, product_name, sub_budget_name, expenses, revenues, "
                            "legal_basis, fetched_at) VALUES (?,?,?,?,?,?,?,?)",
                            (year, "P10.561100", "Klimaschutz", "Klima", 3_000_000.0 + year, 400_000.4, basis, NOW))
    for seq, year in ((8, 2024), (3, 2025), (4, 2026)):
        store._conn.execute("INSERT INTO council_budget_amendments_cash (budget_year, list_key, year, seq, label, outflow, "
                            "explanation, document_id, fetched_at) VALUES (?,?,?,?,?,?,?,?,?)",
                            (2024, "administration_1", year, seq, f"Fahrradstation {year}", 450_000.0,
                             "Bestandteil des vom Rat der Stadt beschlossenen Klimaschutzplans Oldenburg 2035.", 7, NOW))
    block = plan_pages.budget_block(store, plans.PLANS["klimaschutzplan_2035"])
    product = next(i for i in block["items"] if i["kind"] == "product")
    assert product["since"] == 2024 and product["amounts"][0] == {"label": "Aufwand 2026 (Ansatz)", "value": 3_002_026.0}
    assert product["amounts"][1]["value"] == 400_000.4, "ungerundet; gerundet wird in der Anzeige"
    assert "Klimaschutzplan" in product["quote"]
    changes = [i for i in block["items"] if i["kind"] == "change"]
    assert len(changes) == 3 and all(c["context"] == "Änderungsliste der Verwaltung I, Haushalt 2024" for c in changes)
    assert changes[0]["source_url"].endswith("id=7&type=do")
    assert "kostet" in block["note"]


def test_von_zwei_stufen_einer_aenderung_zaehlt_die_spaetere(store):
    text = "Die Umgestaltung des Wallrings ist eine Maßnahme aus dem vom Rat beschlossenen Mobilitätsplan."
    for list_key, seq in (("administration_1", 12), ("fc_decided", 16)):
        store._conn.execute("INSERT INTO council_budget_amendments_cash (budget_year, list_key, year, seq, label, outflow, "
                            "explanation, document_id, fetched_at) VALUES (?,?,?,?,?,?,?,?,?)",
                            (2026, list_key, 2026, seq, "Umgestaltung des Wallrings", 200_000.0, text, 9, NOW))
    changes = [i for i in plan_pages.budget_block(store, plans.PLANS["mobilitaetsplan_2030"])["items"] if i["kind"] == "change"]
    assert len(changes) == 1
    assert changes[0]["context"] == "Beschlossene Änderungen (Finanzausschuss), Haushalt 2026"
    assert changes[0]["amounts"] == [{"label": "Auszahlung 2026", "value": 200_000.0}]


def test_ohne_verweis_kein_haushalt(store):
    assert plan_pages.budget_block(store, plans.PLANS["spielleitplanung"])["items"] == []


def test_stelle_im_haushaltstext_wird_sauber_geschnitten():
    text = ("Erster Satz ohne Bezug. " + "Füllwort " * 30 + "Ratsbeschluss Klimaschutzplan Oldenburg 2035 vom 19.12.2022. "
            "Danach kommt noch viel anderes.")
    quote = plan_pages._budget_quote(text, r"Klimaschutzplan")
    assert "Klimaschutzplan" in quote and quote.startswith("…") and not quote.startswith("… ")
    assert quote.endswith("19.12.2022.") and "Danach" not in quote
    assert plan_pages._budget_quote("Kurz: Klimaschutzplan.", r"Klimaschutzplan") == "Kurz: Klimaschutzplan."


def test_verweise_passen_zu_den_mustern():
    refs, patterns = plan_state.budget_refs(), plan_state.budget_patterns()
    assert refs and set(refs) == set(patterns) and set(refs) <= set(plans.PLANS)
    assert all(patterns[k] == plan_haushalt.PATTERNS[k] for k in patterns)
    for key, entries in refs.items():
        for ref in entries:
            assert ref["table"] in CouncilStore.PLAN_BUDGET_TABLES and ref["field"] in plan_haushalt.TEXT_FIELDS
            if ref["table"].startswith("amendments"):
                assert {"budget_year", "list_key", "year", "seq"} <= set(ref), "eine Änderung braucht ihren vollen Schlüssel"
            else:
                assert ref["years"] == sorted(set(ref["years"])), ref
    for (plan, table, _number), why in plan_haushalt.REJECTED.items():
        assert plan in plans.PLANS and table in CouncilStore.PLAN_BUDGET_TABLES and why.strip()


def test_haushalts_route_liegt_unter_budget():
    """Die Sperre hängt am Recht ``budget`` — tests/test_rollen.py verlangt es von jeder Route unter
    /api/council/budget und verbietet es überall sonst."""
    from tests.test_endpunkt_schutz import _endpunkte

    found = {path: names for _method, path, names in _endpunkte()}
    assert "require_permission_budget" in found["/api/council/budget/plan/{key}"]
    assert not any(p.startswith("/api/council/plan/") and p.endswith("/budget") for p in found)
