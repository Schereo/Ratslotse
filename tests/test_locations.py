"""Ortszuordnung: hohe Präzision, mehrere Orte und inkrementelle Persistenz."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from council import locations
from council.locations import extract_explicit_locations
from council.store import CouncilStore
from scripts.extract_decision_locations import process
from scripts.geocode_decision_locations import process as geocode_process
from scripts.revalidate_decision_locations import process as revalidate_process
from scripts.review_location_candidates_2026_08 import review_manifest


def test_full_location_review_manifest_is_complete_and_valid():
    from collections import Counter
    from council.store import CONCRETE_LOCATION_KINDS

    manifest = review_manifest()
    assert len(manifest) == 123
    assert Counter(row["status"] for row in manifest.values()) == {
        "concrete": 55, "approved": 33, "alias": 8, "rejected": 27,
    }
    assert all(row["kind"] in CONCRETE_LOCATION_KINDS
               for row in manifest.values() if row["status"] == "concrete")
    assert all(row["source_url"].startswith("https://")
               for row in manifest.values() if row["status"] == "approved")


def test_curated_location_geocodes_are_complete_valid_and_idempotent(tmp_path):
    geocodes = locations.curated_location_geocodes()
    assert len(geocodes) == 44
    assert "hafen-iprump" not in geocodes
    assert all(point["source_url"].startswith("https://") for point in geocodes.values())

    store = CouncilStore(tmp_path / "council.sqlite")
    store._conn.execute(
        "INSERT INTO council_locations "
        "(slug,name,kind,lat,lon,geo_tried,updated_at) "
        "VALUES ('skateanlage-eversten','Skateanlage Eversten','sonstiges',NULL,NULL,1,'')"
    )
    store._conn.commit()
    assert store.apply_curated_location_geocodes() == 1
    row = store.location_by_slug("skateanlage-eversten")
    assert (row["lat"], row["lon"], row["ortsbereich_id"]) == (
        53.1379232, 8.1719987, "eversten")
    assert store.apply_curated_location_geocodes() == 0
    store.close()


@pytest.mark.parametrize(
    ("text", "expected", "excluded"),
    [
        (
            "Vorhabenbezogener Bebauungsplan 61 (südlich Rennplatzstraße/"
            "nördlich Hochheider Weg) – Satzungsbeschluss",
            {"Rennplatzstraße", "Hochheider Weg"},
            set(),
        ),
        (
            "Bebauungsplan 851 (östlich Schützenweg/nördlich Hamelmannstraße)",
            {"Schützenweg", "Hamelmannstraße"},
            set(),
        ),
        (
            "Stadionneubau Maastrichter Straße – Beschluss",
            {"Maastrichter Straße"},
            set(),
        ),
        (
            "Ausnahmegenehmigungen im Schulstraßenpilotprojekt Junkerstraße",
            {"Junkerstraße"},
            {"Schulstraßen"},
        ),
        (
            "Umbau der Grundschule in Kreyenbrück",
            {"Kreyenbrück"},
            set(),
        ),
        (
            "GS Röwekamp, Umbau und Erweiterung",
            {"GS Röwekamp"},
            set(),
        ),
        (
            "Sanierung der Cäcilienbrücke",
            {"Cäcilienbrücke"},
            set(),
        ),
        (
            "Oldenburger Leitfaden für die Einrichtung von Fahrradstraßen",
            set(),
            {"Fahrradstraßen"},
        ),
        (
            "Sondervermögen Straßensanierung",
            set(),
            {"Straßensanierung"},
        ),
        (
            "Brücken bauen zwischen Zivilgesellschaft und Polizei",
            set(),
            {"Brücken"},
        ),
        (
            'Straßenbenennung "Alan-Turing-Straße"',
            {"Alan-Turing-Straße"},
            {"Alan-Turing"},
        ),
        (
            "Sport für Alle auf dem Sportplatz Schlieffenstraße",
            {"Schlieffenstraße"},
            {"Sportplatz"},
        ),
    ],
)
def test_extract_explicit_locations(text, expected, excluded):
    names = {row["name"] for row in extract_explicit_locations(text, source="title")}
    assert expected <= names
    assert not (excluded & names)


def test_location_storage_replaces_per_decision_and_keeps_one_off_places(tmp_path):
    store = CouncilStore(tmp_path / "council.sqlite")
    store._conn.execute(
        "INSERT INTO council_sessions "
        "(ksinr,committee,session_date,session_time,location,fetched_at) "
        "VALUES (1,'Rat','2026-01-01','18:00','Rathaus','')"
    )
    store._conn.execute(
        "INSERT INTO council_decisions "
        "(id,ksinr,position,kind,item_number,title,official_text) "
        "VALUES (7,1,0,'decision','1','Bau an der Junkerstraße','Beschlossen')"
    )
    store._conn.commit()

    store.save_decision_locations(7, [{
        "name": "Junkerstraße", "kind": "street", "source": "title",
        "evidence": "Bau an der Junkerstraße", "method": "regex", "confidence": 0.98,
    }], source_hash="hash-1")

    rows = store.decision_locations(7)
    assert len(rows) == 1 and rows[0]["name"] == "Junkerstraße"
    assert store.location_scan_hashes()[7] == "hash-1"
    assert [r["name"] for r in store.locations_to_geocode()] == ["Junkerstraße"]

    store.set_location_geo("junkerstrasse", 53.14, 8.21, None)
    pin = store.orte_fuer_decisions([7])[7]
    assert pin == {"ort_name": "Junkerstraße", "lat": 53.14, "lon": 8.21}

    # Ein externer Vergleichsort darf trotz Koordinaten nicht auf der
    # Oldenburg-Karte erscheinen.
    store.set_location_geo("junkerstrasse", 52.3759, 9.7320, None)
    assert 7 not in store.orte_fuer_decisions([7])
    store.set_location_geo("junkerstrasse", 53.14, 8.21, None)

    # Ein neuer Lauf ersetzt die Zuordnungen dieses Beschlusses atomar; der Ort
    # muss nicht wie bei Themen-Entitäten in mindestens zwei Beschlüssen vorkommen.
    store.save_decision_locations(7, [{
        "name": "Hochheider Weg", "kind": "street", "source": "vorlage",
        "evidence": "nördlich Hochheider Weg", "method": "llm", "confidence": 0.9,
    }], source_hash="hash-2")
    assert [r["name"] for r in store.decision_locations(7)] == ["Hochheider Weg"]
    assert store.location_scan_hashes()[7] == "hash-2"


def test_llm_locations_require_a_real_fundstelle(monkeypatch):
    payload = {"results": [{"id": 7, "locations": [
        {"name": "GS Röwekamp", "kind": "building", "source": "title",
         "evidence": "GS Röwekamp, Umbau und Erweiterung", "confidence": "high"},
        {"name": "Eversten", "kind": "district", "source": "title",
         "evidence": "frei erfunden", "confidence": "high"},
    ]}]}
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=10),
    )
    monkeypatch.setattr(locations.llm, "chat_complete", lambda **_kwargs: response)
    got, _usage = locations.extract_batch([{
        "id": 7, "title": "GS Röwekamp, Umbau und Erweiterung",
        "official_text": "Die Baumaßnahme wird umgesetzt.", "vorlage_text": "",
    }, {
        "id": 8, "title": "Stadtweiter Bericht", "official_text": "Zur Kenntnis genommen.",
        "vorlage_text": "",
    }])
    assert [row["name"] for row in got[7]] == ["GS Röwekamp"]
    assert got[8] == []


def test_llm_locations_accept_top_level_array(monkeypatch):
    payload = [{"id": 7, "locations": [{
        "name": "GS Röwekamp", "kind": "building", "source": "title",
        "evidence": "GS Röwekamp", "confidence": "high",
    }]}]
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=10),
    )
    monkeypatch.setattr(locations.llm, "chat_complete", lambda **_kwargs: response)
    got, _usage = locations.extract_batch([{
        "id": 7, "title": "GS Röwekamp, Umbau und Erweiterung",
        "official_text": "Die Baumaßnahme wird umgesetzt.", "vorlage_text": "",
    }])
    assert [row["name"] for row in got[7]] == ["GS Röwekamp"]


def test_llm_locations_reject_organizations_foreign_districts_and_unrelated_evidence(monkeypatch):
    payload = {"results": [{"id": 7, "locations": [
        {"name": "Verkehr und Wasser GmbH", "kind": "other", "source": "title",
         "evidence": "Verkehr und Wasser GmbH", "confidence": "high"},
        {"name": "Bremen", "kind": "district", "source": "vorlage",
         "evidence": "bis Bremen", "confidence": "high"},
        {"name": "VOSS", "kind": "other", "source": "official_text",
         "evidence": "Das Jahresergebnis wird vorgetragen", "confidence": "high"},
        {"name": "Eversten", "kind": "district", "source": "vorlage",
         "evidence": "Stadtteil Eversten", "confidence": "high"},
    ]}]}
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=10),
    )
    monkeypatch.setattr(locations.llm, "chat_complete", lambda **_kwargs: response)
    got, _usage = locations.extract_batch([{
        "id": 7,
        "title": "Verkehr und Wasser GmbH – Jahresabschluss VOSS",
        "official_text": "Das Jahresergebnis wird vorgetragen.",
        "vorlage_text": "Ein Vergleich führt bis Bremen; ein Vorhaben liegt im Stadtteil Eversten.",
    }])
    assert [row["name"] for row in got[7]] == ["Eversten"]


@pytest.mark.parametrize(("name", "evidence"), [
    ("Nadorster Straße", "Ortsbegehung der unteren Nadorster Str."),
    ("Hallensichel-Ost", "Fliegerhorst/Hallensichel Ost/Entlastungsstraße"),
    ("Weser-Ems-Halle", "südöstlich der Weser-Ems-Hallen"),
    ("Maastrichter Straße", "Haltestelle an der Maastricher Straße"),
    ("Tweelbäker Tredde", "Flächen an der Tweekbäker Tredde"),
])
def test_llm_fundstelle_allows_abbreviation_hyphen_and_inflection(name, evidence):
    assert locations.valid_llm_location(name, "street", evidence)


def test_incremental_process_picks_up_only_new_decisions(tmp_path):
    db = tmp_path / "council.sqlite"
    store = CouncilStore(db)
    store._conn.execute(
        "INSERT INTO council_sessions "
        "(ksinr,committee,session_date,session_time,location,fetched_at) "
        "VALUES (1,'Rat','2026-01-01','18:00','Rathaus','')"
    )
    store._conn.executemany(
        "INSERT INTO council_decisions "
        "(id,ksinr,position,kind,item_number,title,official_text) "
        "VALUES (?,1,0,'decision','1',?,'Beschlossen')",
        [(7, "Bau an der Junkerstraße"), (8, "Stadtweiter Jahresbericht")],
    )
    store._conn.execute(
        "UPDATE council_decisions SET template_number='26/0001' WHERE id=8")
    store._conn.commit()
    store.close()

    first = process(db, use_llm=False)
    assert first == {"candidates": 2, "scanned": 2, "assigned": 1,
                     "links": 1, "beiwerk_verworfen": 0, "failed_batches": 0}
    assert process(db, use_llm=False)["candidates"] == 0

    store = CouncilStore(db)
    store._conn.execute(
        "INSERT INTO council_decisions "
        "(id,ksinr,position,kind,item_number,title,official_text) "
        "VALUES (9,1,0,'decision','2','Bau am Hochheider Weg','Beschlossen')")
    store._conn.commit()
    store.close()
    new = process(db, use_llm=False)
    assert new["candidates"] == 1 and new["assigned"] == 1

    # Eine erst später geladene Vorlage macht auch einen bereits gescannten
    # Beschluss wieder zum Kandidaten (im echten Lauf wertet sie das LLM aus).
    store = CouncilStore(db)
    store._conn.execute(
        "INSERT INTO council_templates "
        "(kvonr,template_number,title,raw_text,fetched_at,status) "
        "VALUES (1,'26/0001','Jahresbericht','Ort im späteren Volltext',"
        "'9999-01-01T00:00:00','ok')")
    store._conn.commit()
    store.close()
    assert process(db, use_llm=False)["candidates"] == 1


def test_known_stadtteil_is_geocoded_without_network(tmp_path, monkeypatch):
    db = tmp_path / "council.sqlite"
    store = CouncilStore(db)
    store._conn.execute(
        "INSERT INTO council_sessions "
        "(ksinr,committee,session_date,session_time,location,fetched_at) "
        "VALUES (1,'Rat','2026-01-01','18:00','Rathaus','')"
    )
    store._conn.execute(
        "INSERT INTO council_decisions "
        "(id,ksinr,position,kind,item_number,title,official_text) "
        "VALUES (7,1,0,'decision','1','Vorhaben in Kreyenbrück','Beschlossen')"
    )
    store._conn.commit()
    store.save_decision_locations(7, [{
        "name": "Kreyenbrück", "kind": "district", "source": "title",
        "evidence": "Kreyenbrück", "method": "district_list", "confidence": 0.99,
    }], "hash")
    store.close()

    # Der externe Geocoder darf für bekannte Stadtteile nie gebraucht werden.
    monkeypatch.setattr("scripts.geocode_decision_locations.geocode",
                        lambda _name: pytest.fail("unerwarteter Netz-Geocoder"))
    stats = geocode_process(db, sleep=0)
    assert stats["located"] == 1 and stats["failed"] == 0
    store = CouncilStore(db)
    row = store.decision_locations(7)[0]
    assert row["lat"] is not None and row["district"] == "Kreyenbrück"


def test_ortskatalog_alias_is_extracted_as_canonical_name():
    got = locations.extract_explicit_locations(
        "Die Verwaltung berichtet aus dem Drielaker Moor.", source="title")
    assert got == [{
        "name": "Drielaker-Moor", "kind": "district", "source": "title",
        "evidence": "Drielaker Moor", "method": "place_catalog", "confidence": 0.99,
    }]


def test_secondary_place_alias_is_extracted_with_canonical_id_ready_name():
    got = locations.extract_explicit_locations(
        "Die Verbindung zur ehemaligen Donnerschwee-Kaserne wird gebaut.", source="title")
    assert got == [{
        "name": "Neu-Donnerschwee", "kind": "area", "source": "title",
        "evidence": "ehemaligen Donnerschwee-Kaserne", "method": "place_catalog",
        "confidence": 0.99,
    }]


def test_existing_location_coordinates_get_a_district(tmp_path):
    db = tmp_path / "council.sqlite"
    store = CouncilStore(db)
    from council import geo
    lat, lon = geo.ortsbereich_center("Kreyenbrück")
    store._conn.execute(
        "INSERT INTO council_locations "
        "(slug,name,kind,lat,lon,geo_tried,updated_at) "
        "VALUES ('alt','Alt','gebiet',?,?,1,'')",
        (lat, lon),
    )
    store._conn.commit()
    assert store.backfill_location_districts() == 1
    row = store._conn.execute(
        "SELECT district FROM council_locations WHERE slug='alt'").fetchone()
    assert row[0] == "Kreyenbrück"
    assert store.backfill_location_districts() == 0
    store.close()


def test_revalidation_removes_only_invalid_llm_links(tmp_path):
    db = tmp_path / "council.sqlite"
    store = CouncilStore(db)
    store._conn.execute(
        "INSERT INTO council_sessions "
        "(ksinr,committee,session_date,session_time,location,fetched_at) "
        "VALUES (1,'Rat','2026-01-01','18:00','Rathaus','')"
    )
    store._conn.execute(
        "INSERT INTO council_decisions "
        "(id,ksinr,position,kind,item_number,title,official_text) "
        "VALUES (7,1,0,'decision','1','Jahresabschluss VOSS','Feststellung')"
    )
    store._conn.commit()
    store.save_decision_locations(7, [{
        "name": "VOSS", "kind": "other", "source": "official_text",
        "evidence": "Das Jahresergebnis wird vorgetragen", "method": "llm",
        "confidence": 0.9,
    }, {
        "name": "Eversten", "kind": "district", "source": "title",
        "evidence": "Vorhaben in Eversten", "method": "llm", "confidence": 0.9,
    }], "hash")
    store.close()

    assert revalidate_process(db)["invalid_llm"] == 1
    assert revalidate_process(db, apply=True)["removed"] == 1
    store = CouncilStore(db)
    assert [row["name"] for row in store.decision_locations(7)] == ["Eversten"]
    store.close()


def test_revalidation_repairs_changed_regex_matches(tmp_path):
    db = tmp_path / "council.sqlite"
    store = CouncilStore(db)
    store._conn.execute(
        "INSERT INTO council_sessions "
        "(ksinr,committee,session_date,session_time,location,fetched_at) "
        "VALUES (1,'Rat','2026-01-01','18:00','Rathaus','')"
    )
    store._conn.execute(
        "INSERT INTO council_decisions "
        "(id,ksinr,position,kind,item_number,title,official_text) "
        "VALUES (8,1,0,'decision','1','Straßenbenennung Alan-Turing-Straße','')"
    )
    store._conn.commit()
    store.save_decision_locations(8, [{
        "name": "Alan-Turing", "kind": "street", "source": "title",
        "evidence": "Alan-Turing", "method": "regex", "confidence": 0.98,
    }], "hash")
    store.close()

    dry = revalidate_process(db)
    assert dry["invalid_deterministic"] == 1 and dry["additions"] == 1
    revalidate_process(db, apply=True)
    store = CouncilStore(db)
    assert [row["name"] for row in store.decision_locations(8)] == ["Alan-Turing-Straße"]
    store.close()


def test_revalidation_replaces_invalid_llm_link_with_regex_in_one_run(tmp_path):
    db = tmp_path / "council.sqlite"
    store = CouncilStore(db)
    store._conn.execute(
        "INSERT INTO council_sessions "
        "(ksinr,committee,session_date,session_time,location,fetched_at) "
        "VALUES (1,'Rat','2026-01-01','18:00','Rathaus','')"
    )
    store._conn.execute(
        "INSERT INTO council_decisions "
        "(id,ksinr,position,kind,item_number,title,official_text) "
        "VALUES (9,1,0,'decision','1','Sanierung Alan-Turing-Straße','')"
    )
    store._conn.commit()
    store.save_decision_locations(9, [{
        "name": "Alan-Turing-Straße", "kind": "street", "source": "title",
        "evidence": "unbelegte Fundstelle", "method": "llm", "confidence": 0.9,
    }], "hash")
    store.close()

    dry = revalidate_process(db)
    assert dry["invalid_llm"] == 1 and dry["additions"] == 1
    revalidate_process(db, apply=True)
    assert revalidate_process(db)["invalid_llm"] == 0
    assert revalidate_process(db)["additions"] == 0
    store = CouncilStore(db)
    rows = store.decision_locations(9)
    assert len(rows) == 1 and rows[0]["method"] == "regex"
    store.close()


def test_backfill_streams_across_multiple_batches(tmp_path):
    db = tmp_path / "council.sqlite"
    store = CouncilStore(db)
    store._conn.execute(
        "INSERT INTO council_sessions "
        "(ksinr,committee,session_date,session_time,location,fetched_at) "
        "VALUES (1,'Rat','2026-01-01','18:00','Rathaus','')"
    )
    store._conn.executemany(
        "INSERT INTO council_decisions "
        "(id,ksinr,position,kind,item_number,title,official_text) "
        "VALUES (?,1,?,'decision',?,'Stadtweiter Bericht','Beschlossen')",
        [(i, i, str(i)) for i in range(1, 26)],
    )
    store._conn.commit()
    store.close()

    stats = process(db, use_llm=False, batch_size=4)
    assert stats["candidates"] == stats["scanned"] == 25
    assert process(db, use_llm=False, batch_size=4)["candidates"] == 0


def test_reviewed_place_joins_catalog_extraction_search_and_map(tmp_path):
    store = CouncilStore(tmp_path / "council.sqlite")
    store._conn.execute(
        "INSERT INTO council_sessions "
        "(ksinr,committee,session_date,session_time,location,fetched_at) "
        "VALUES (1,'Rat','2026-05-01','18:00','Rathaus','')"
    )
    store._conn.executemany(
        "INSERT INTO council_decisions "
        "(id,ksinr,position,kind,item_number,title,official_text) "
        "VALUES (?,1,?,'decision',?,'Planung am Testquartier','Beschlossen')",
        [(i, i, str(i)) for i in range(1, 4)],
    )
    store._conn.commit()
    for decision_id in range(1, 4):
        store.save_decision_locations(decision_id, [{
            "name": "Testquartier", "kind": "area", "source": "title",
            "evidence": "am Testquartier", "method": "llm", "confidence": 0.91,
        }], f"hash-{decision_id}")
    store._conn.execute(
        "UPDATE council_locations SET lat=53.16,lon=8.22,geo_tried=1,"
        "district='Nadorst',ortsbereich_id='nadorst' WHERE slug='testquartier'"
    )
    store._conn.commit()

    # Unscharfe Gebietsbegriffe kommen nicht allein wegen Häufigkeit auf die Karte.
    assert not any(p["slug"] == "testquartier" for p in store.decision_location_map_points())
    candidate = next(c for c in store.location_candidates() if c["slug"] == "testquartier")
    assert candidate["decision_count"] == 3 and len(candidate["evidence"]) == 3

    with pytest.raises(ValueError, match="gültigen Ortstyp"):
        store.review_location_candidate(
            "testquartier", status="concrete", kind="neighborhood")
    concrete = store.review_location_candidate(
        "testquartier", status="concrete", kind="building", updated_by="admin@test.de")
    assert concrete["status"] == "concrete" and concrete["review_kind"] == "building"
    assert not store.resolve_place("Testquartier")
    point = next(p for p in store.decision_location_map_points() if p["slug"] == "testquartier")
    assert point["target"] == "location" and point["place_id"] is None
    assert store.location_candidates("concrete")[0]["slug"] == "testquartier"
    assert store.delete_location_review("testquartier")
    assert not any(p["slug"] == "testquartier" for p in store.decision_location_map_points())

    store.review_location_candidate(
        "testquartier", status="approved", place_id="testquartier",
        name="Testquartier", kind="neighborhood", parent_id="nadorst",
        aliases=["Test-Quartier"], description="Ein Testgebiet.",
        source_url="https://example.test/ort", updated_by="admin@test.de",
    )
    place = store.resolve_place("Test-Quartier")
    assert place and place.id == "testquartier" and place.parent_ids == ("nadorst",)
    assert store.count_decisions(district="testquartier") == 3
    assert store.count_decisions(location_slug="testquartier") == 3
    assert extract_explicit_locations(
        "Vorhaben im Test-Quartier", source="title", catalog_places=store.all_places()
    )[0]["name"] == "Testquartier"
    point = next(p for p in store.decision_location_map_points() if p["slug"] == "testquartier")
    assert point["target"] == "ort" and point["place_id"] == "testquartier"

    # Eine schon vor der Freigabe vorhandene Schreibvariante wird beim
    # Backfill auf den neuen Katalogort aufgelöst und bleibt nicht als offener
    # Kandidat stehen.
    store._conn.execute(
        "INSERT INTO council_locations(slug,name,kind,place_id,updated_at) "
        "VALUES ('test-quartier','Test-Quartier','gebiet',NULL,'2026-05-01')")
    store._conn.execute(
        "INSERT INTO council_decision_locations(decision_id,location_slug,source,evidence,"
        "method,confidence,updated_at) "
        "VALUES (1,'test-quartier','title','Test-Quartier','llm',0.9,'2026-05-01')")
    store._conn.commit()
    assert store.backfill_location_place_ids() == 1
    assert not any(c["slug"] == "test-quartier" for c in
                   store.location_candidates("pending", min_decisions=1))

    store.review_location_candidate("testquartier", status="rejected")
    assert not any(p["slug"] == "testquartier" for p in store.decision_location_map_points())
    store.close()


def test_reviewed_alias_resolves_to_existing_catalog_place(tmp_path):
    store = CouncilStore(tmp_path / "council.sqlite")
    store._conn.execute(
        "INSERT INTO council_sessions "
        "(ksinr,committee,session_date,session_time,location,fetched_at) "
        "VALUES (1,'Rat','2026-05-01','18:00','Rathaus','')"
    )
    store._conn.execute(
        "INSERT INTO council_decisions "
        "(id,ksinr,position,kind,item_number,title,official_text) "
        "VALUES (1,1,1,'decision','1','Nadorster Gebiet','Beschlossen')"
    )
    store._conn.commit()
    store.save_decision_locations(1, [{
        "name": "Nadorster Gebiet", "kind": "area", "source": "title",
        "evidence": "Nadorster Gebiet", "method": "llm", "confidence": 0.9,
    }], "hash")
    store.review_location_candidate(
        "nadorster-gebiet", status="alias", canonical_place_id="nadorst")
    assert store.resolve_place("Nadorster Gebiet").id == "nadorst"
    assert store.count_decisions(district="nadorst") == 1
    extracted = extract_explicit_locations(
        "Neue Planung im Nadorster Gebiet", source="title", catalog_places=store.all_places())
    assert extracted[0]["name"] == "Nadorst"
    # Geprüfte Einträge bleiben trotz der Drei-Beschlüsse-Schwelle sichtbar.
    assert store.location_candidates("alias")[0]["slug"] == "nadorster-gebiet"
    store.close()


def test_migration_schreibt_deutsche_gebietstypen_und_ortsarten_um(tmp_path):
    """Der Umbau auf Englisch betrifft hier nicht nur Spalten, sondern WERTE.

    `area_type` und `council_locations.kind` tragen die Begriffe als Daten in
    den Zeilen — ein Schema-Wechsel allein ließe sie deutsch. Der Test legt
    eine Datenbank im alten Zustand an und prüft, dass ein Öffnen sie
    umschreibt, ohne Zeilen zu verlieren, und dass ein zweites Öffnen nichts
    mehr tut.
    """
    import sqlite3

    from council.store import CouncilStore

    pfad = tmp_path / "council.sqlite"
    store = CouncilStore(pfad)          # legt das Schema an (schon englisch)
    store.close()

    conn = sqlite3.connect(pfad)
    conn.execute("ALTER TABLE council_locations RENAME COLUMN district TO stadtteil")
    conn.execute(
        "INSERT INTO council_locations (slug, name, kind, stadtteil, updated_at) "
        "VALUES ('kreyenbrueck', 'Kreyenbrück', 'stadtteil', 'Kreyenbrück', '2026-01-01')")
    spalten = [r[1] for r in conn.execute("PRAGMA table_info(council_quiz_questions)")]
    werte = {"area_type": "stadtteil", "area_key": "Kreyenbrück", "category": "places",
             "difficulty": "medium", "question": "Wo liegt das?", "options": '["a","b"]',
             "correct_index": 0, "status": "active", "content_hash": "h-alt",
             "generated_at": "2026-01-01T00:00:00"}
    nutzbar = {k: v for k, v in werte.items() if k in spalten}
    conn.execute(
        f"INSERT INTO council_quiz_questions ({','.join(nutzbar)}) "
        f"VALUES ({','.join('?' * len(nutzbar))})", list(nutzbar.values()))
    conn.commit()
    conn.close()

    store = CouncilStore(pfad)
    try:
        assert [r[1] for r in store._conn.execute("PRAGMA table_info(council_locations)")
                if r[1] in ("stadtteil", "district")] == ["district"]
        assert store._conn.execute(
            "SELECT kind FROM council_locations WHERE slug='kreyenbrueck'").fetchone()[0] == "district"
        assert store._conn.execute(
            "SELECT district FROM council_locations WHERE slug='kreyenbrueck'").fetchone()[0] == "Kreyenbrück"
        assert store._conn.execute(
            "SELECT area_type FROM council_quiz_questions").fetchone()[0] == "district"
        assert store._conn.execute("SELECT COUNT(*) FROM council_locations").fetchone()[0] == 1
    finally:
        store.close()

    # Zweiter Lauf: nichts mehr zu tun, nichts kaputt.
    store = CouncilStore(pfad)
    try:
        assert store._conn.execute(
            "SELECT area_type FROM council_quiz_questions").fetchone()[0] == "district"
        assert store._conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        store.close()
