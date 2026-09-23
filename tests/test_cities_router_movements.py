"""Die Endpunkte für Bewegungen (Plan PR 50).

Vier Zusagen: Der leere Bestand antwortet 200. Die Zeitachse hängt am ganzen
Bestand, nicht an der Seite — sonst verschöbe sie sich beim Blättern. Eine
Idee ohne Urteil trägt ``oldenburg: None`` statt eines erfundenen Status.
Und die Belege kommen aufgelöst, auch wenn sie auf einen Beschluss zeigen.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from council.cities import clusters
from council.cities.index import EMBED_MODEL
from council.cities.model import Batch, Body, Paper
from council.cities.store import CitiesStore
from council.store import CouncilStore
from web.backend.app.deps import get_cities_store, get_council_store
from web.backend.app.main import app


@pytest.fixture()
def rats_db(tmp_path):
    store = CouncilStore(tmp_path / "council.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, "
            "location, fetched_at) VALUES (7, 'Rat', '2023-06-13', '16:00', 'PFL', '2023-06-14')")
        store._conn.execute(
            "INSERT INTO council_decisions (id, ksinr, position, kind, item_number, title, "
            "  outcome, kvonr) VALUES (1, 7, 1, 'decision', '4', 'Hitze-Informationen', "
            "  'noted', 4711)")
    yield store
    store.close()


def _classify(s, pid, inst, feld="klima_umwelt"):
    s.put_annotation("paper", pid, "classify", "2",
                     {"field": feld, "transfer": "direct", "competence": "council",
                      "instrument": inst, "summary": inst + ".",
                      "originator": "SPD-Fraktion"}, "h" + pid)


@pytest.fixture()
def cities_db(tmp_path):
    s = CitiesStore(tmp_path / "cities.sqlite")
    s.upsert_body(Body("osnabrueck", "Stadt Osnabrück", "NI", "allris4"))
    s.upsert_batch(Batch(papers=[
        Paper("os:p:1", "osnabrueck", "Hitzeaktionsplan", date="2023-06-01", kind="motion"),
        Paper("ms:p:1", "muenster", "Hitzeaktionsplan Münster", date="2024-02-01", kind="motion"),
        Paper("po:p:1", "potsdam", "Hitzeschutz Potsdam", date="2025-09-01", kind="motion"),
        Paper("oldenburg:paper:4711", "oldenburg", "Hitze-Informationen", date="2023-06-01",
              kind="motion"),
        Paper("os:p:2", "osnabrueck", "Radschnellweg", date="2021-03-01", kind="motion"),
        Paper("ms:p:2", "muenster", "Radschnellweg Münster", date="2022-03-01", kind="motion"),
    ]))
    for pid, inst in (("os:p:1", "Hitzeaktionsplan aufstellen"),
                      ("ms:p:1", "Hitzeaktionsplan aufstellen"),
                      ("po:p:1", "Hitzeschutzkonzept"),
                      ("oldenburg:paper:4711", "Hitzeinformation")):
        _classify(s, pid, inst)
    _classify(s, "os:p:2", "Radschnellweg bauen", "verkehr")
    # Die Übersicht zählt nur Felder mit Einzelurteilen (`idea_fields`).
    for pid in ("os:p:1", "ms:p:1", "po:p:1"):
        s.put_annotation("paper", pid, *CitiesStore.IDEEN_FIT,
                         {"status": "missing", "evidence": [], "reason": "…",
                          "confidence": "low"}, "f" + pid)
    _classify(s, "ms:p:2", "Radschnellweg planen", "verkehr")
    s.replace_idea_clusters(EMBED_MODEL, "1", [
        (EMBED_MODEL, "1", 1, "os:p:1", 0.9), (EMBED_MODEL, "1", 1, "ms:p:1", 0.95),
        (EMBED_MODEL, "1", 1, "po:p:1", 0.8), (EMBED_MODEL, "1", 1, "oldenburg:paper:4711", 0.7),
        (EMBED_MODEL, "1", 2, "os:p:2", 0.9), (EMBED_MODEL, "1", 2, "ms:p:2", 0.9)])
    clusters.rebuild_idea_groups(s)
    s.put_annotation("cluster", "1:1", "idea_fit", "1",
                     {"status": "partial", "situation": "Oldenburg hat 2023 informiert.",
                      "evidence": ["oldenburg:decision:1"],
                      "related": ["oldenburg:paper:4711"], "confidence": "medium"}, "h")
    yield s
    s.close()


@pytest.fixture()
def client(rats_db, cities_db):
    app.dependency_overrides[get_council_store] = lambda: rats_db
    app.dependency_overrides[get_cities_store] = lambda: cities_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_der_leere_bestand_antwortet(tmp_path, rats_db):
    leer = CitiesStore(tmp_path / "leer.sqlite")
    app.dependency_overrides[get_council_store] = lambda: rats_db
    app.dependency_overrides[get_cities_store] = lambda: leer
    try:
        daten = TestClient(app).get("/api/council/cities/movements").json()
        assert daten["items"] == [] and daten["total"] == 0
        assert daten["axis"] == {"start": None, "end": None}
    finally:
        app.dependency_overrides.clear()
        leer.close()


def test_die_vorgabe_zeigt_was_fehlt_oder_halb_da_ist(client):
    daten = client.get("/api/council/cities/movements").json()
    assert daten["total"] == 1, "die Radweg-Idee hat kein Urteil und fällt unter der Vorgabe raus"
    b = daten["items"][0]
    assert b["label"] == "Hitzeaktionsplan aufstellen"
    assert [c["city"] for c in b["cities"]][0] == "Osnabrück", "Namen aus der Registry"
    assert len(b["cities"]) == 3 and b["members"] == 3 and b["oldenburg_members"] == 1
    assert all(p["body_id"] != "oldenburg" for p in b["timeline"])
    assert b["oldenburg"]["status"] == "partial"
    assert daten["counts"] == {"partial": 1, "unjudged": 1}


def test_belege_und_verwandtes_kommen_aufgeloest(client):
    b = client.get("/api/council/cities/movements").json()["items"][0]
    beleg = b["oldenburg"]["evidence"][0]
    assert beleg["decision_id"] == 1 and beleg["title"] == "Hitze-Informationen", \
        "ein Beschluss als Beleg fiel früher still weg"
    assert b["oldenburg"]["related"][0]["kvonr"] == 4711


def test_ohne_urteil_steht_none_da(client):
    daten = client.get("/api/council/cities/movements?oldenburg=&field=verkehr").json()
    assert daten["total"] == 1 and daten["items"][0]["oldenburg"] is None


def test_die_achse_haengt_am_bestand_nicht_an_der_seite(client):
    eine = client.get("/api/council/cities/movements?oldenburg=&per_page=1").json()
    zwei = client.get("/api/council/cities/movements?oldenburg=&per_page=1&page=2").json()
    assert eine["axis"] == zwei["axis"] == {"start": "2021-01-01", "end": "2026-01-01"}
    assert eine["items"][0]["cluster_id"] != zwei["items"][0]["cluster_id"]


def test_min_cities_und_sortierung(client):
    assert client.get("/api/council/cities/movements?oldenburg=&min_cities=3").json()["total"] == 1
    zuletzt = client.get("/api/council/cities/movements?oldenburg=&sort=zuletzt").json()
    assert [i["label"] for i in zuletzt["items"]][0] == "Hitzeaktionsplan aufstellen"
    assert client.get("/api/council/cities/movements?sort=quatsch").status_code == 400


def test_die_ideen_seite(client):
    d = client.get("/api/council/cities/movements/detail?id=1").json()
    assert d["movement"]["cluster_id"] == 1
    assert [x["paper_id"] for x in d["documents"]] == ["os:p:1", "ms:p:1", "po:p:1"]
    assert d["documents"][0]["protocol_source"] in ("available", "none", "withheld")
    assert [x["kvonr"] for x in d["oldenburg_documents"]] == [4711]
    assert d["axis"]["start"] == "2021-01-01"
    assert client.get("/api/council/cities/movements/detail?id=999").status_code == 404


def test_die_uebersicht_zaehlt_bewegungen(client):
    felder = {f["field"]: f for f in client.get(
        "/api/council/cities/ideas/fields").json()["fields"]}
    assert felder["klima_umwelt"]["movements"] == 1


def test_rueckmeldung_zum_urteil_je_idee(client, cities_db):
    from web.backend.app.deps import get_current_user
    app.dependency_overrides[get_current_user] = lambda: {"id": 7}
    try:
        r = client.post("/api/council/cities/movements/feedback?id=1&verdict=wrong")
        assert r.status_code == 200 and r.json() == {"paper_id": "1:1", "verdict": "wrong"}
        zeile = cities_db._conn.execute(
            "SELECT object_kind, annotator, verdict FROM feedback").fetchone()
        assert tuple(zeile) == ("cluster", "idea_fit", "wrong")
        assert client.post("/api/council/cities/movements/feedback?id=999&verdict=wrong").status_code == 404
        assert client.post("/api/council/cities/movements/feedback?id=1&verdict=hm").status_code == 400
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_derselbe_vorgang_steht_nur_einmal_unter_den_belegen():
    """Vorlage und ihr Beschluss sind EIN Beleg, nicht zwei (Wärmeplan, 22.09.2026)."""
    from web.backend.app.routers.council import _ohne_doppelte

    belege = [
        {"decision_id": 8683, "kvonr": None, "title": "Oldenburger Wärmeplan", "date": None, "outcome": None},
        {"decision_id": 8683, "kvonr": 29685, "title": "Oldenburger Wärmeplan", "date": None, "outcome": None},
        {"decision_id": None, "kvonr": 29685, "title": "Oldenburger Wärmeplan - Beschluss", "date": None, "outcome": None},
        {"decision_id": 8549, "kvonr": None, "title": "Wärmeplan im Ausschuss", "date": None, "outcome": None},
    ]
    assert [b["decision_id"] for b in _ohne_doppelte(belege)] == [8683, 8549]
