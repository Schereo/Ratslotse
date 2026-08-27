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
        "(id,ksinr,position,kind,item_number,title,beschluss) "
        "VALUES (7,1,0,'decision','1','Bau an der Junkerstraße','Beschlossen')"
    )
    store._conn.commit()

    store.save_decision_locations(7, [{
        "name": "Junkerstraße", "kind": "strasse", "source": "title",
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
        "name": "Hochheider Weg", "kind": "strasse", "source": "vorlage",
        "evidence": "nördlich Hochheider Weg", "method": "llm", "confidence": 0.9,
    }], source_hash="hash-2")
    assert [r["name"] for r in store.decision_locations(7)] == ["Hochheider Weg"]
    assert store.location_scan_hashes()[7] == "hash-2"


def test_llm_locations_require_a_real_fundstelle(monkeypatch):
    payload = {"results": [{"id": 7, "locations": [
        {"name": "GS Röwekamp", "kind": "gebaeude", "source": "title",
         "evidence": "GS Röwekamp, Umbau und Erweiterung", "confidence": "high"},
        {"name": "Eversten", "kind": "stadtteil", "source": "title",
         "evidence": "frei erfunden", "confidence": "high"},
    ]}]}
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=10),
    )
    monkeypatch.setattr(locations.llm, "chat_complete", lambda **_kwargs: response)
    got, _usage = locations.extract_batch([{
        "id": 7, "title": "GS Röwekamp, Umbau und Erweiterung",
        "beschluss": "Die Baumaßnahme wird umgesetzt.", "vorlage_text": "",
    }, {
        "id": 8, "title": "Stadtweiter Bericht", "beschluss": "Zur Kenntnis genommen.",
        "vorlage_text": "",
    }])
    assert [row["name"] for row in got[7]] == ["GS Röwekamp"]
    assert got[8] == []


def test_llm_locations_accept_top_level_array(monkeypatch):
    payload = [{"id": 7, "locations": [{
        "name": "GS Röwekamp", "kind": "gebaeude", "source": "title",
        "evidence": "GS Röwekamp", "confidence": "high",
    }]}]
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=10),
    )
    monkeypatch.setattr(locations.llm, "chat_complete", lambda **_kwargs: response)
    got, _usage = locations.extract_batch([{
        "id": 7, "title": "GS Röwekamp, Umbau und Erweiterung",
        "beschluss": "Die Baumaßnahme wird umgesetzt.", "vorlage_text": "",
    }])
    assert [row["name"] for row in got[7]] == ["GS Röwekamp"]


def test_llm_locations_reject_organizations_foreign_districts_and_unrelated_evidence(monkeypatch):
    payload = {"results": [{"id": 7, "locations": [
        {"name": "Verkehr und Wasser GmbH", "kind": "sonstiges", "source": "title",
         "evidence": "Verkehr und Wasser GmbH", "confidence": "high"},
        {"name": "Bremen", "kind": "stadtteil", "source": "vorlage",
         "evidence": "bis Bremen", "confidence": "high"},
        {"name": "VOSS", "kind": "sonstiges", "source": "beschluss",
         "evidence": "Das Jahresergebnis wird vorgetragen", "confidence": "high"},
        {"name": "Eversten", "kind": "stadtteil", "source": "vorlage",
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
        "beschluss": "Das Jahresergebnis wird vorgetragen.",
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
    assert locations.valid_llm_location(name, "strasse", evidence)


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
        "(id,ksinr,position,kind,item_number,title,beschluss) "
        "VALUES (?,1,0,'decision','1',?,'Beschlossen')",
        [(7, "Bau an der Junkerstraße"), (8, "Stadtweiter Jahresbericht")],
    )
    store._conn.execute(
        "UPDATE council_decisions SET vorlage_nr='26/0001' WHERE id=8")
    store._conn.commit()
    store.close()

    first = process(db, use_llm=False)
    assert first == {"candidates": 2, "scanned": 2, "assigned": 1,
                     "links": 1, "failed_batches": 0}
    assert process(db, use_llm=False)["candidates"] == 0

    store = CouncilStore(db)
    store._conn.execute(
        "INSERT INTO council_decisions "
        "(id,ksinr,position,kind,item_number,title,beschluss) "
        "VALUES (9,1,0,'decision','2','Bau am Hochheider Weg','Beschlossen')")
    store._conn.commit()
    store.close()
    new = process(db, use_llm=False)
    assert new["candidates"] == 1 and new["assigned"] == 1

    # Eine erst später geladene Vorlage macht auch einen bereits gescannten
    # Beschluss wieder zum Kandidaten (im echten Lauf wertet sie das LLM aus).
    store = CouncilStore(db)
    store._conn.execute(
        "INSERT INTO council_vorlagen "
        "(kvonr,vorlage_nr,title,raw_text,fetched_at,status) "
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
        "(id,ksinr,position,kind,item_number,title,beschluss) "
        "VALUES (7,1,0,'decision','1','Vorhaben in Kreyenbrück','Beschlossen')"
    )
    store._conn.commit()
    store.save_decision_locations(7, [{
        "name": "Kreyenbrück", "kind": "stadtteil", "source": "title",
        "evidence": "Kreyenbrück", "method": "stadtteilliste", "confidence": 0.99,
    }], "hash")
    store.close()

    # Der externe Geocoder darf für bekannte Stadtteile nie gebraucht werden.
    monkeypatch.setattr("scripts.geocode_decision_locations.geocode",
                        lambda _name: pytest.fail("unerwarteter Netz-Geocoder"))
    stats = geocode_process(db, sleep=0)
    assert stats["located"] == 1 and stats["failed"] == 0
    store = CouncilStore(db)
    row = store.decision_locations(7)[0]
    assert row["lat"] is not None and row["stadtteil"] == "Kreyenbrück"


def test_ortskatalog_alias_is_extracted_as_canonical_name():
    got = locations.extract_explicit_locations(
        "Die Verwaltung berichtet aus dem Drielaker Moor.", source="title")
    assert got == [{
        "name": "Drielaker-Moor", "kind": "stadtteil", "source": "title",
        "evidence": "Drielaker Moor", "method": "ortskatalog", "confidence": 0.99,
    }]


def test_secondary_place_alias_is_extracted_with_canonical_id_ready_name():
    got = locations.extract_explicit_locations(
        "Die Verbindung zur ehemaligen Donnerschwee-Kaserne wird gebaut.", source="title")
    assert got == [{
        "name": "Neu-Donnerschwee", "kind": "gebiet", "source": "title",
        "evidence": "ehemaligen Donnerschwee-Kaserne", "method": "ortskatalog",
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
    assert store.backfill_location_stadtteile() == 1
    row = store._conn.execute(
        "SELECT stadtteil FROM council_locations WHERE slug='alt'").fetchone()
    assert row[0] == "Kreyenbrück"
    assert store.backfill_location_stadtteile() == 0
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
        "(id,ksinr,position,kind,item_number,title,beschluss) "
        "VALUES (7,1,0,'decision','1','Jahresabschluss VOSS','Feststellung')"
    )
    store._conn.commit()
    store.save_decision_locations(7, [{
        "name": "VOSS", "kind": "sonstiges", "source": "beschluss",
        "evidence": "Das Jahresergebnis wird vorgetragen", "method": "llm",
        "confidence": 0.9,
    }, {
        "name": "Eversten", "kind": "stadtteil", "source": "title",
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
        "(id,ksinr,position,kind,item_number,title,beschluss) "
        "VALUES (8,1,0,'decision','1','Straßenbenennung Alan-Turing-Straße','')"
    )
    store._conn.commit()
    store.save_decision_locations(8, [{
        "name": "Alan-Turing", "kind": "strasse", "source": "title",
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
        "(id,ksinr,position,kind,item_number,title,beschluss) "
        "VALUES (9,1,0,'decision','1','Sanierung Alan-Turing-Straße','')"
    )
    store._conn.commit()
    store.save_decision_locations(9, [{
        "name": "Alan-Turing-Straße", "kind": "strasse", "source": "title",
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
        "(id,ksinr,position,kind,item_number,title,beschluss) "
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
        "(id,ksinr,position,kind,item_number,title,beschluss) "
        "VALUES (?,1,?,'decision',?,'Planung am Testquartier','Beschlossen')",
        [(i, i, str(i)) for i in range(1, 4)],
    )
    store._conn.commit()
    for decision_id in range(1, 4):
        store.save_decision_locations(decision_id, [{
            "name": "Testquartier", "kind": "gebiet", "source": "title",
            "evidence": "am Testquartier", "method": "llm", "confidence": 0.91,
        }], f"hash-{decision_id}")
    store._conn.execute(
        "UPDATE council_locations SET lat=53.16,lon=8.22,geo_tried=1,"
        "stadtteil='Nadorst',ortsbereich_id='nadorst' WHERE slug='testquartier'"
    )
    store._conn.commit()

    # Unscharfe Gebietsbegriffe kommen nicht allein wegen Häufigkeit auf die Karte.
    assert not any(p["slug"] == "testquartier" for p in store.decision_location_map_points())
    candidate = next(c for c in store.location_candidates() if c["slug"] == "testquartier")
    assert candidate["decision_count"] == 3 and len(candidate["evidence"]) == 3

    store.review_location_candidate(
        "testquartier", status="approved", place_id="testquartier",
        name="Testquartier", kind="quartier", parent_id="nadorst",
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
        "(id,ksinr,position,kind,item_number,title,beschluss) "
        "VALUES (1,1,1,'decision','1','Nadorster Gebiet','Beschlossen')"
    )
    store._conn.commit()
    store.save_decision_locations(1, [{
        "name": "Nadorster Gebiet", "kind": "gebiet", "source": "title",
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
