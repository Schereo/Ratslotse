"""„Mein Viertel": Register, Richter-Regeln, Endpunkte und Meldungen.

Das Sprachmodell wird gestubbt — geprüft wird, was UM den Aufruf herum
entscheidet: Cache über den Eingabe-Hash, Verwerfen unbekannter Werte, die
Namensvetter-Regel, die stadtweit-Regel aus dem Titel, stabile Vorhaben-ids
über Läufe, dass Meldungen erst nach einer Entscheidung der Redaktion
ausblenden, und dass die Endpunkte ein Konto verlangen.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_BACKEND = Path(__file__).resolve().parents[1] / "web" / "backend"
sys.path.insert(0, str(_BACKEND))
# Wegwerf-Datenbanken und die übrigen Testwerte kommen aus
# `tests/conftest.py` — dort EINMAL je Prozess gesetzt, damit sie nicht an
# der Import-Reihenfolge der Module hängen (siehe die Begründung dort).

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from council import viertel  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from council.store_viertel import PROJECT_MIN_CONFIDENCE  # noqa: E402

COUNCIL_DB = os.environ["COUNCIL_DB"]
RATSLOTSE_DB = os.environ["RATSLOTSE_DB"]


@pytest.fixture(autouse=True)
def fresh_dbs():
    for base in (RATSLOTSE_DB, COUNCIL_DB):
        for suffix in ("", "-wal", "-shm"):
            Path(base + suffix).unlink(missing_ok=True)
    yield


def _store() -> CouncilStore:
    return CouncilStore(COUNCIL_DB)


def _seed(store: CouncilStore) -> None:
    """Zwei Beschlüsse in Kreyenbrück, einer davon mit Namensvetter anderswo."""
    c = store._conn
    with c:
        c.execute("INSERT INTO council_sessions (ksinr, committee, session_date, session_time, location, fetched_at) "
                  "VALUES (1, 'Rat', '2026-05-04', '18:00', 'Rathaus', '2026-05-01')")
        c.executemany(
            "INSERT INTO council_decisions (id, ksinr, position, title, summary, official_text, outcome, kind) "
            "VALUES (?, 1, ?, ?, ?, ?, 'angenommen', 'decision')",
            [(10, 1, "Bebauungsplan 81 (Sandkruger Straße) - Aufstellungsbeschluss",
              "70 Wohnungen an der Sandkruger Straße.", "Der Rat beschließt die Aufstellung."),
             (11, 2, "Abfallablagerung auf dem Schießstand", "Untersuchung der Ablagerungen.", "Die Verwaltung prüft."),
             (12, 3, "Haushaltssatzung 2027 der Stadt Oldenburg", "Stadtweit.", "Beschluss.")])
        c.executemany(
            "INSERT INTO council_locations (slug, name, kind, district, local_area_id, updated_at) "
            "VALUES (?, ?, ?, ?, ?, '2026-01-01')",
            [("sandkruger-strasse", "Sandkruger Straße", "street", "Kreyenbrück", "kreyenbrueck"),
             ("schiessstand", "Schießstand", "area", "Kreyenbrück", "kreyenbrueck"),
             ("schiessstand-fliegerhorst", "Schießstand/Fliegerhorst", "area", "Fliegerhorst", "fliegerhorst"),
             ("stadt", "Stadt Oldenburg", "other", "Kreyenbrück", "kreyenbrueck")])
        c.executemany(
            "INSERT INTO council_location_districts (location_slug, district, place_id, share) VALUES (?, ?, ?, ?)",
            [("sandkruger-strasse", "Kreyenbrück", "kreyenbrueck", 0.6),
             ("sandkruger-strasse", "Bümmerstede", "buemmerstede", 0.4),
             ("schiessstand", "Kreyenbrück", "kreyenbrueck", 1.0),
             ("schiessstand-fliegerhorst", "Fliegerhorst", "fliegerhorst", 1.0),
             ("stadt", "Kreyenbrück", "kreyenbrueck", 1.0)])
        c.executemany(
            "INSERT INTO council_decision_locations (decision_id, location_slug, source, evidence, method, "
            "confidence, updated_at) VALUES (?, ?, 'title', ?, 'regex', 0.9, '2026-01-01')",
            [(10, "sandkruger-strasse", "Sandkruger Straße"), (11, "schiessstand", "Schießstand"),
             (12, "stadt", "Stadt Oldenburg")])


class _Antwort:
    def __init__(self, payload: dict):
        self.choices = [SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]


def test_kandidaten_tragen_namensvetter_und_nachbarn():
    store = _store()
    _seed(store)
    place = store.resolve_place("kreyenbrueck")
    kand = {k["id"]: k for k in store.district_candidates(place, since="2026-01-01")}
    assert set(kand) == {10, 11, 12}
    # Die Sandkruger Straße läuft weiter nach Bümmerstede — das ist derselbe
    # Ort, kein Namensvetter; aber der Nachbar steht dabei.
    assert kand[10]["namesakes"] == []
    assert "Bümmerstede" not in kand[10]["other_districts"]  # Anteil 0,4 < Schwelle
    # Der Schießstand hat einen echten Namensvetter auf dem Fliegerhorst.
    assert kand[11]["namesakes"] == [{"name": "Schießstand/Fliegerhorst", "district": "Fliegerhorst"}]
    assert kand[10]["strict"] is True
    store.close()


def test_richter_cache_und_regeln(monkeypatch):
    store = _store()
    _seed(store)
    place = store.resolve_place("kreyenbrueck")
    aufrufe: list[list[int]] = []

    def fake_review(**kwargs):
        user = kwargs["messages"][1]["content"]
        ids = [int(z.split()[1].rstrip(":")) for z in user.splitlines() if z.startswith("id ")]
        aufrufe.append(ids)
        return _Antwort({"reviews": [
            {"id": 10, "relation": "district", "changes": True, "what": "70 Wohnungen entstehen.",
             "when": "2028", "stage": "planning", "category": "housing", "confidence": 96, "reason": "B-Plan"},
            {"id": 11, "relation": "district", "changes": True, "what": "Ablagerungen werden entfernt.",
             "when": None, "stage": "decided", "category": "green", "confidence": 95, "reason": "Beschluss"},
            {"id": 12, "relation": "citywide", "changes": False, "what": "Haushalt.", "when": None,
             "stage": "decided", "category": "other", "confidence": 99, "reason": "stadtweit"},
            {"id": 999, "relation": "district", "changes": True, "what": "halluziniert", "confidence": 100},
            {"id": 10, "relation": "irgendwas"},
        ]})

    monkeypatch.setattr(viertel.llm, "chat_complete", fake_review)
    kand = store.district_candidates(place, since="2026-01-01")
    urteile = viertel.review_candidates(store, place, kand)
    assert set(urteile) == {10, 11, 12}
    assert urteile[10]["when"] == "2028" and urteile[10]["relation"] == "district"
    assert len(aufrufe) == 1

    # Zweiter Lauf: alles im Cache, kein Aufruf.
    urteile2 = viertel.review_candidates(store, place, store.district_candidates(place, since="2026-01-01"))
    assert len(aufrufe) == 1
    assert urteile2[10]["what"] == "70 Wohnungen entstehen."

    # Der Text eines Beschlusses ändert sich → nur der geht neu ans Modell.
    with store._conn:
        store._conn.execute("UPDATE council_decisions SET summary = 'Jetzt 90 Wohnungen.' WHERE id = 10")
    viertel.review_candidates(store, place, store.district_candidates(place, since="2026-01-01"))
    assert aufrufe[-1] == [10]
    store.close()


def test_buendelung_namensvetter_und_stadtweit_regel(monkeypatch):
    store = _store()
    _seed(store)
    place = store.resolve_place("kreyenbrueck")
    with store._conn:
        # 12 trägt einen stadtweiten Titel — der Richter mag sagen, was er
        # will, die Regel aus council.locations siebt ihn vorher aus.
        store._conn.execute("UPDATE council_decisions SET title = 'Haushaltssatzung 2027 der Stadt Oldenburg' WHERE id = 12")

    def fake(**kwargs):
        system = kwargs["messages"][0]["content"]
        if "VORHABEN" in system:
            return _Antwort({"projects": [
                {"name": "Wohnungen Sandkruger Straße", "what": "70 Wohnungen.", "stage": "planning",
                 "when": "2028", "category": "housing", "decision_ids": [10], "confidence": 97},
                {"name": "Schießstand aufräumen", "what": "Ablagerungen weg.", "stage": "decided",
                 "when": None, "category": "green", "decision_ids": [11, 12, 999], "confidence": 95},
                {"name": "ohne ids", "decision_ids": [], "confidence": 99},
            ]})
        return _Antwort({"reviews": [
            {"id": i, "relation": "district", "changes": True, "what": "x", "stage": "decided",
             "category": "other", "confidence": 95} for i in (10, 11, 12)]})

    monkeypatch.setattr(viertel.llm, "chat_complete", fake)
    stats = viertel.build_place(store, place)
    assert stats["candidates"] == 3 and stats["hits"] == 2  # 12 fällt an der Titel-Regel
    projekte = store.district_projects(place.id, min_confidence=0)
    by_name = {p["name"]: p for p in projekte}
    assert set(by_name) == {"Wohnungen Sandkruger Straße", "Schießstand aufräumen"}
    assert by_name["Wohnungen Sandkruger Straße"]["confidence"] == 97
    # Namensvetter ohne Vorlagenbeleg: unter der Tafel-Schwelle, und die
    # halluzinierte 999 sowie die ausgesiebte 12 hängen nicht dran.
    schiess = by_name["Schießstand aufräumen"]
    assert schiess["confidence"] == PROJECT_MIN_CONFIDENCE - 1
    assert [d["id"] for d in schiess["decisions"]] == [11]
    assert [p["name"] for p in store.district_projects(place.id)] == ["Wohnungen Sandkruger Straße"]
    assert by_name["Wohnungen Sandkruger Straße"]["project_key"] == "kreyenbrueck:10"
    assert stats["visible"] == 1
    store.close()


def _register(client, email="tester@example.org"):
    r = client.post("/api/auth/register", json={"display_name": "Testkonto", "email": email, "password": "password123"})
    assert r.status_code == 201, r.text
    from kern.store import Store
    s = Store(RATSLOTSE_DB)
    with s._conn:
        s._conn.execute("UPDATE web_users SET status = 'active' WHERE email = ?", (email,))
    s.close()
    # Wie die App: X-Client=app liefert ein Bearer-Token statt eines Cookies —
    # so lassen sich zwei Konten in einem Test auseinanderhalten.
    r = client.post("/api/auth/login", json={"email": email, "password": "password123"},
                    headers={"X-Client": "app"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_endpunkte_mit_konto_und_melden():
    store = _store()
    _seed(store)
    store.replace_district_projects("kreyenbrueck", [
        {"name": "Wohnungen Sandkruger Straße", "what": "70 Wohnungen.", "stage": "planning", "when": "2028",
         "category": "housing", "decision_ids": [10], "confidence": 97},
    ])
    store.close()
    client = TestClient(app)
    # Seit dem Umzug auf die Stadtkarte (Schritt 5) verlangen alle drei
    # Lese-Endpunkte ein Konto — ohne eins: 401, nicht 200 mit leerer Liste.
    assert client.get("/api/districts/projects").status_code == 401
    assert client.get("/api/districts/lookup", params={"q": "krey"}).status_code == 401
    assert client.get("/api/districts/kreyenbrueck/projects").status_code == 401
    client.headers["Authorization"] = f"Bearer {_register(client, 'leserin@example.org')}"

    r = client.get("/api/districts/projects")
    assert r.status_code == 200
    uebersicht = r.json()
    zeile = next(d for d in uebersicht["districts"] if d["place_id"] == "kreyenbrueck")
    assert zeile["count"] == 1 and zeile["name"] == "Kreyenbrück"
    assert zeile["stages"] == {"planning": 1}
    # Die Stadtzahlen und Highlights der Auswahl-Seite: hier ein Vorhaben, also eins.
    assert uebersicht["total"] == 1 and uebersicht["stages"] == {"planning": 1}
    assert [(h["place_id"], h["name"], h["when"]) for h in uebersicht["highlights"]] == [
        ("kreyenbrueck", "Wohnungen Sandkruger Straße", "2028")]

    # „Ich wohne in der …": Stadtteil (auch über den Alias) und Straße führen zum Ortsbereich.
    assert client.get("/api/districts/lookup", params={"q": "k"}).json() == {"matches": []}
    treffer = client.get("/api/districts/lookup", params={"q": "krey"}).json()["matches"]
    assert treffer[0] == {"name": "Kreyenbrück", "kind": "district", "place_id": "kreyenbrueck",
                          "place_name": "Kreyenbrück", "count": 1}
    treffer = client.get("/api/districts/lookup", params={"q": "sandkrug"}).json()["matches"]
    assert [(t["name"], t["place_id"], t["kind"]) for t in treffer] == [("Sandkruger Straße", "kreyenbrueck", "street")]

    r = client.get("/api/districts/kreyenbrueck/projects")
    assert r.status_code == 200
    tafel = r.json()
    assert tafel["place"]["id"] == "kreyenbrueck"
    assert [p["name"] for p in tafel["projects"]] == ["Wohnungen Sandkruger Straße"]
    assert tafel["projects"][0]["decisions"][0]["id"] == 10
    assert tafel["projects"][0]["reported"] is False
    assert len(tafel["neighbours"]) == 3
    # Eine laufende Beteiligung zum Plan bekommt den Umring als Fläche (Schritt 4
    # des Stadtkarte-Plans): Plannummer aus dem Beteiligungs-Titel, Umring aus dem
    # Geoportal-Spiegel. Ohne Umring bleibt sie ohne Fläche, aber in der Tafel.
    from council import bplan
    from council import geo as _geo
    store = _store()
    lat, lon = _geo.ortsbereich_center("Kreyenbrück")
    store.replace_bplan_outlines([bplan.normiere({"properties": {"Planverfahren": "81"}, "geometry": {
        "type": "Polygon", "coordinates": [[[lon - 0.002, lat - 0.002], [lon + 0.002, lat - 0.002],
                                            [lon + 0.002, lat + 0.002], [lon - 0.002, lat + 0.002], [lon - 0.002, lat - 0.002]]]}},
        "in_procedure")])
    store.save_beteiligungen([
        {"title": "Bebauungsplan 81 (Sandkruger Straße)", "ort": "Kreyenbrück", "schritt": "Frühzeitige Beteiligung",
         "valid_from": "2026-09-01", "valid_until": "2026-09-30", "url": "https://example.org/b/81", "plan_nrs": ["bp-81"]},
        {"title": "Bebauungsplan 999 (Sandkruger Straße)", "ort": "Kreyenbrück", "schritt": "Auslegung",
         "valid_from": None, "valid_until": None, "url": "https://example.org/b/999", "plan_nrs": ["bp-999"]},
    ])
    store.close()
    bet = {b["title"]: b for b in client.get("/api/districts/kreyenbrueck/projects").json()["participations"]}
    assert bet["Bebauungsplan 81 (Sandkruger Straße)"]["geometry"]["type"] == "Polygon"
    assert bet["Bebauungsplan 81 (Sandkruger Straße)"]["plan_nr"] == "81"
    assert bet["Bebauungsplan 81 (Sandkruger Straße)"]["plan_status"] == "in_procedure"
    assert bet["Bebauungsplan 999 (Sandkruger Straße)"]["geometry"] is None
    assert client.get("/api/districts/nirgendwo/projects").status_code == 404

    pid = tafel["projects"][0]["id"]
    # Ohne Konto: 401 — ein frischer Client, der Lese-Client oben trägt ja schon eins.
    assert TestClient(app).post(f"/api/districts/projects/{pid}/report", json={}).status_code == 401

    kopf = {"Authorization": f"Bearer {_register(client)}"}
    r = client.post(f"/api/districts/projects/{pid}/report", json={"reason": "liegt in Bümmerstede"}, headers=kopf)
    assert r.status_code == 201
    assert r.json() == {"ok": True, "report_count": 1, "hidden": False, "reported": True}
    # Zweimal vom selben Konto zählt einmal.
    r = client.post(f"/api/districts/projects/{pid}/report", json={}, headers=kopf)
    assert r.json()["report_count"] == 1
    assert client.get("/api/districts/kreyenbrueck/projects", headers=kopf).json()["projects"][0]["reported"] is True
    assert client.post("/api/districts/projects/424242/report", json={}, headers=kopf).status_code == 404


def _tafel_mit_vorhaben() -> int:
    store = _store()
    _seed(store)
    store.replace_district_projects("kreyenbrueck", [
        {"name": "Wohnungen Sandkruger Straße", "what": "70 Wohnungen.", "stage": "planning", "when": "2028",
         "category": "housing", "decision_ids": [10], "confidence": 97},
    ])
    pid = store.district_projects("kreyenbrueck")[0]["id"]
    store.close()
    return pid


def _admin_kopf(client) -> dict:
    from scripts.grant_admin import grant_admin
    token = _register(client, "chefin@example.org")
    grant_admin("chefin@example.org", RATSLOTSE_DB)
    return {"Authorization": f"Bearer {token}"}


def test_meldungen_blenden_nichts_aus_erst_die_redaktion(monkeypatch):
    """Tims Linie: Zwei Konten dürfen kein Vorhaben dauerhaft löschen. Eine
    Meldung landet in der Admin-Liste (die erste je Vorhaben als Mail), und
    ausgeblendet wird erst, wenn ein Admin bestätigt — umkehrbar."""
    from kern import alerts
    mails: list[tuple[str, str]] = []
    monkeypatch.setattr(alerts, "notify_admin", lambda text, betreff="", fusszeile="": mails.append((betreff, text)))
    pid = _tafel_mit_vorhaben()
    client = TestClient(app)
    kopf1 = {"Authorization": f"Bearer {_register(client, 'eins@example.org')}"}
    kopf2 = {"Authorization": f"Bearer {_register(client, 'zwei@example.org')}"}
    kopf3 = {"Authorization": f"Bearer {_register(client, 'drei@example.org')}"}

    for kopf in (kopf1, kopf2, kopf3):
        r = client.post(f"/api/districts/projects/{pid}/report", json={"reason": "liegt <b>woanders</b>"}, headers=kopf)
        assert r.status_code == 201 and r.json()["hidden"] is False
    # Drei Meldungen — und das Vorhaben steht weiter auf der Tafel.
    tafel = client.get("/api/districts/kreyenbrueck/projects", headers=kopf1).json()
    assert [p["id"] for p in tafel["projects"]] == [pid]
    # Genau EINE Mail, mit Namen und maskiertem Grund.
    assert len(mails) == 1
    assert "Mein Viertel" in mails[0][0]
    assert "Wohnungen Sandkruger Straße" in mails[0][1] and "&lt;b&gt;woanders" in mails[0][1]

    # Rücknahme der eigenen Meldung.
    r = client.delete(f"/api/districts/projects/{pid}/report", headers=kopf3)
    assert r.json() == {"ok": True, "report_count": 2, "hidden": False, "reported": False}

    # Die Admin-Liste: ohne Admin 403, mit Admin die gebündelten Meldungen ohne Konten.
    assert client.get("/api/admin/district-reports", headers=kopf1).status_code == 403
    admin = _admin_kopf(client)
    liste = client.get("/api/admin/district-reports", headers=admin).json()
    assert liste["open_count"] == 1
    gruppe = liste["groups"][0]
    assert gruppe["project_key"] == "kreyenbrueck:10" and gruppe["count"] == 2
    assert gruppe["place_name"] == "Kreyenbrück" and gruppe["project"]["id"] == pid
    assert all(set(m) == {"reason", "created_at"} for m in gruppe["reports"])

    # „Passt doch": bleibt stehen, verlässt die offene Liste.
    key = "kreyenbrueck:10"
    assert client.put(f"/api/admin/district-reports/{key}", json={"verdict": "kept"}, headers=admin).status_code == 200
    assert client.get("/api/admin/district-reports", headers=admin).json()["groups"] == []
    assert client.get("/api/admin/district-reports?status=decided", headers=admin).json()["groups"][0]["verdict"] == "kept"
    assert len(client.get("/api/districts/kreyenbrueck/projects", headers=kopf1).json()["projects"]) == 1

    # Bestätigt: ausgeblendet, auch in den Highlights.
    client.put(f"/api/admin/district-reports/{key}", json={"verdict": "hidden", "note": "liegt in Bümmerstede"},
               headers=admin)
    assert client.get("/api/districts/kreyenbrueck/projects", headers=kopf1).json()["projects"] == []
    assert client.get("/api/districts/projects", headers=kopf1).json()["highlights"] == []
    # Zurückgenommen: wieder sichtbar, die Meldungen wieder offen.
    client.put(f"/api/admin/district-reports/{key}", json={"verdict": None}, headers=admin)
    assert len(client.get("/api/districts/kreyenbrueck/projects", headers=kopf1).json()["projects"]) == 1
    assert client.get("/api/admin/district-reports", headers=admin).json()["open_count"] == 1
    # Entschieden wird nur, was es gibt.
    assert client.put("/api/admin/district-reports/nirgendwo:1", json={"verdict": "hidden"},
                      headers=admin).status_code == 404


def test_melden_ist_gebremst(monkeypatch):
    pid = _tafel_mit_vorhaben()
    client = TestClient(app)
    kopf = {"Authorization": f"Bearer {_register(client, 'eilig@example.org')}"}
    from app import ratelimit
    monkeypatch.delenv("DISABLE_RATE_LIMIT")
    monkeypatch.setattr(ratelimit.district_report_limiter, "_calls", __import__("collections").defaultdict(list))
    codes = [client.post(f"/api/districts/projects/{pid}/report", json={}, headers=kopf).status_code
             for _ in range(ratelimit.district_report_limiter.max_calls + 1)]
    assert codes[-1] == 429 and set(codes[:-1]) == {201}


def test_kontoloeschung_nimmt_meldungen_mit():
    pid = _tafel_mit_vorhaben()
    client = TestClient(app)
    kopf = {"Authorization": f"Bearer {_register(client, 'geht@example.org')}"}
    client.post(f"/api/districts/projects/{pid}/report", json={"reason": "privat"}, headers=kopf)
    r = client.request("DELETE", "/api/account", headers=kopf, json={"current_password": "password123"})
    assert r.status_code in (200, 204), r.text
    store = _store()
    assert store.district_project_report_count("kreyenbrueck:10") == 0
    store.close()


def test_vorhaben_behalten_ihre_id_ueber_laeufe():
    """Jeder Sonntag schrieb alle Vorhaben neu (ids bis 769 bei 199 Zeilen) —
    jeder ``?v=``-Link lief danach ins Leere. Jetzt erbt ein Vorhaben id und
    Schlüssel des bisherigen, mit dem es die meisten Beschlüsse teilt."""
    store = _store()
    _seed(store)
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_decisions (id, ksinr, position, title, outcome, kind) "
            "VALUES (13, 1, 4, 'Bebauungsplan 81 - Satzungsbeschluss', 'angenommen', 'decision')")

    def lauf(*projekte):
        store.replace_district_projects("kreyenbrueck", [
            {"name": n, "what": "x", "stage": "planning", "category": "housing", "decision_ids": ids,
             "confidence": 95} for n, ids in projekte])
        return {p["name"]: p for p in store.district_projects("kreyenbrueck", min_confidence=0)}

    erst = lauf(("Wohnungen", [10]), ("Schießstand", [11]))
    wohn_id, schiess_id = erst["Wohnungen"]["id"], erst["Schießstand"]["id"]
    # Derselbe Lauf noch einmal, mit neuem Namen: dieselben ids.
    zweit = lauf(("Wohnungen an der Sandkruger Straße", [10]), ("Schießstand", [11]))
    assert zweit["Wohnungen an der Sandkruger Straße"]["id"] == wohn_id
    assert zweit["Schießstand"]["id"] == schiess_id

    # Meldung und Entscheidung am Wohnungs-Vorhaben ...
    store.save_district_project_report("kreyenbrueck:10", "kreyenbrueck", 7, "falsch", "Wohnungen")
    store.set_district_project_verdict("kreyenbrueck:10", "kept")
    # ... überleben, dass der ÄLTESTE Beschluss herausfällt (der Befund
    # „Meldung verwaist, weil sie am ältesten Beschluss hängt").
    dritt = lauf(("Wohnungen", [10, 13]), ("Schießstand", [11]))
    viert = lauf(("Wohnungen", [13]), ("Schießstand", [11]))
    assert dritt["Wohnungen"]["id"] == viert["Wohnungen"]["id"] == wohn_id
    assert viert["Wohnungen"]["project_key"] == "kreyenbrueck:10"
    assert viert["Wohnungen"]["report_count"] == 1

    # Zusammengelegt: Das Schießstand-Vorhaben geht im Wohnungs-Vorhaben auf —
    # seine Meldung zieht mit um, statt still zu verwaisen.
    store.save_district_project_report("kreyenbrueck:11", "kreyenbrueck", 8, "auch falsch", "Schießstand")
    store.save_district_project_report("kreyenbrueck:11", "kreyenbrueck", 7, "doppelt", "Schießstand")
    fuenft = lauf(("Alles", [11, 13]))
    assert list(fuenft) == ["Alles"]
    alles = fuenft["Alles"]
    assert alles["project_key"] in ("kreyenbrueck:10", "kreyenbrueck:11")
    assert alles["report_count"] == 2  # Konto 7 und 8, die Doppelmeldung von 7 zählt einmal
    gruppen = {g["project_key"]: g for g in store.district_report_groups("all")}
    assert list(gruppen) == [alles["project_key"]]

    # Ganz verschwunden: Die Meldung bleibt und die Admin-Liste sagt es.
    lauf(("Neu", [12]))
    gruppe = store.district_report_groups("all")[0]
    assert gruppe["project"] is None and gruppe["count"] == 2
    store.close()


def test_match_projects_teilt_und_neu():
    from council.store_viertel import _match_projects
    alt = {1: {10, 11, 12}, 2: {20}}
    # Geteilt: die größere Hälfte erbt, die kleinere ist neu; 2 bleibt 2.
    assert _match_projects(alt, [{10}, {11, 12}, {20}, {30}]) == [None, 1, 2, None]


def test_linie_wird_auf_den_ortsbereich_beschnitten():
    """Die Cloppenburger Straße läuft vom Stadtrand bis zur Innenstadt; auf der
    Tafel von Kreyenbrück bleibt nur ihr Stück im Viertel, und der Pin sitzt
    darauf statt auf der Mitte der ganzen Straße."""
    from council import geo
    kreyenbrueck = geo.ortsbereich_center("Kreyenbrück")
    innenstadt = geo.ortsbereich_center("Innenstadt")
    assert kreyenbrueck and innenstadt
    # Eine Linie von der Kreyenbrücker Mitte in die Innenstadt, mit Zwischenpunkten.
    n = 40
    punkte = [[kreyenbrueck[1] + (innenstadt[1] - kreyenbrueck[1]) * i / n,
               kreyenbrueck[0] + (innenstadt[0] - kreyenbrueck[0]) * i / n] for i in range(n + 1)]
    linie = {"type": "LineString", "coordinates": punkte}
    stueck = geo.auf_ortsbereich_beschneiden(linie, "Kreyenbrück")
    assert stueck and stueck["type"] == "LineString"
    assert 1 < len(stueck["coordinates"]) < len(punkte)
    assert all(geo.ortsbereich_for(p[1], p[0]) == "Kreyenbrück" for p in stueck["coordinates"])
    mitte = geo.linien_mittelpunkt(stueck)
    assert mitte and geo.ortsbereich_for(*mitte) == "Kreyenbrück"
    # Nichts im Viertel → None; Flächen bleiben unangetastet.
    assert geo.auf_ortsbereich_beschneiden(linie, "Nordmoslesfehn") is None
    flaeche = {"type": "Polygon", "coordinates": [punkte[:3] + [punkte[0]]]}
    assert geo.auf_ortsbereich_beschneiden(flaeche, "Kreyenbrück") == flaeche


def test_lauf_ueberlebt_einen_scheiternden_ortsbereich(monkeypatch):
    """Ein Rate-Limit in der Bündelung eines Viertels darf nicht die übrigen
    30 mitreißen — auf dev starb der erste Stadtlauf nach vier von 31."""
    store = _store()
    _seed(store)
    monkeypatch.setattr(viertel.llm, "GEDULD_PAUSEN", ())  # nicht wirklich warten
    aufrufe: list[str] = []

    def fake(**kwargs):
        system = kwargs["messages"][0]["content"]
        user = kwargs["messages"][1]["content"]
        if "VORHABEN" in system:
            aufrufe.append("bündeln")
            if "Kreyenbrück" in user:
                raise RuntimeError("429 temporarily rate-limited upstream")
            return _Antwort({"projects": []})
        aufrufe.append("richten")
        return _Antwort({"reviews": [
            {"id": i, "relation": "district", "changes": True, "what": "x", "stage": "decided",
             "category": "other", "confidence": 95} for i in (10, 11, 12)]})

    monkeypatch.setattr(viertel.llm, "chat_complete", fake)
    stats = viertel.build_all(store, ["kreyenbrueck", "eversten"])
    by_place = {s["place_id"]: s for s in stats}
    assert by_place["kreyenbrueck"].get("failed") is True
    assert by_place["eversten"].get("failed") is None
    # Die Urteile von Kreyenbrück sind trotzdem im Cache — der nächste Lauf
    # holt nur die Bündelung nach.
    assert set(store.district_reviews("kreyenbrueck")) == {10, 11, 12}
    store.close()


def test_abschnittsgrenzen_sind_kein_gegenstand():
    """„Tweelbäker Tredde (Am Schmeel bis Brahmweg)" baut die Tredde aus — die
    beiden Grenzen bleiben, wie sie sind (Tims Befund 06.09.2026)."""
    from council.store_viertel import ortsrollen
    strassen = {n: "street" for n in ("Tweelbäker Tredde", "Am Schmeel", "Brahmweg", "Dießelweg", "Scharfgabenweg")}
    rollen = ortsrollen(["Tweelbäker Tredde", "Am Schmeel", "Brahmweg", "Dießelweg", "Scharfgabenweg"], [
        "Tweelbäker Tredde (Am Schmeel bis Brahmweg) – Straßenausbau",
        "Die Tweelbäker Tredde soll zwischen Am Schmeel und Brahmweg ausgebaut werden.",
        "",
        # Die echte Vorlage erzählt das Straßennetz drumherum — das darf die
        # Rolle aus dem Titel nicht kippen, und die Nebenstraßen darin sind
        # kein Gegenstand.
        "Die Tweelbäker Tredde ist eine Wohnsammelstraße und bindet unter anderem die Straßen\n"
        "Dießelweg, Scharfgabenweg und Brahmweg an die Straße Am Schmeel an. Der Ausbau der "
        "Tweelbäker Tredde erfolgt zwischen Am Schmeel und Brahmweg.",
    ], kinds=strassen)
    assert rollen == {"Tweelbäker Tredde": "subject", "Am Schmeel": "boundary", "Brahmweg": "boundary",
                      "Dießelweg": "boundary", "Scharfgabenweg": "boundary"}
    # Die erste Stufe entscheidet: Steht ein Name im Titel frei, macht ihn
    # kein „zwischen" in der Vorlage zur Grenze.
    assert ortsrollen(["Hauptstraße"], ["Sanierung der Hauptstraße", "zwischen Hauptstraße und Bahn"],
                      kinds={"Hauptstraße": "street"}) == {"Hauptstraße": "subject"}
    # Das Wohnquartier: Die drei Straßen stehen in jedem Titel, gebaut wird
    # auf den Flächen dahinter — Straßen ohne Bauwort sind Bezug, die Fläche
    # bleibt Gegenstand. Titel sind durch Leerzeilen getrennte Sätze.
    assert ortsrollen(["Am Schmeel", "Brahmweg", "Quartier am Krusenbusch"], [
        "Entwicklungsabsichten Quartier Am Schmeel/Krusenbusch - Bericht\n\n"
        "Bebauungsplan 865 (Quartier am Krusenbusch) - Aufstellungsbeschluss\n\n"
        "Geplantes Wohnquartier Krusenbusch (Am Schmeel, Tweelbäker Tredde, Brahmweg) - Bericht",
        "Zudem ist beabsichtigt, die vorhandene Hofstelle am Brahmweg zu sanieren.",
    ], kinds={"Am Schmeel": "street", "Brahmweg": "street", "Quartier am Krusenbusch": "area"}) == {
        "Am Schmeel": "context", "Brahmweg": "context", "Quartier am Krusenbusch": "subject"}
    # Eine Kreuzung ist Gegenstand, beide Straßen sind betroffen.
    assert ortsrollen(["Schützenhofstraße", "Bremer Straße"],
                      ["Straßenbaumaßnahme Kreuzung Schützenhofstraße/Bremer Straße"],
                      kinds={"Schützenhofstraße": "street", "Bremer Straße": "street"}) == {
        "Schützenhofstraße": "subject", "Bremer Straße": "subject"}
    # Nur Grenzen: die Fläche dazwischen ist das Vorhaben — Rolle bleibt Grenze.
    assert ortsrollen(["Rüschenweg"], ["Flächen zwischen der A 29 und dem Rüschenweg"]) == {"Rüschenweg": "boundary"}
    # Nicht im Text (Katalog-Variante) → Gegenstand, nie still weg.
    assert ortsrollen(["Huntemannstr"], ["Kita an der Huntemannstraße"]) == {"Huntemannstr": "subject"}
