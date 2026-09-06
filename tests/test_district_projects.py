"""„Mein Viertel": Register, Richter-Regeln und die öffentlichen Endpunkte.

Das Sprachmodell wird gestubbt — geprüft wird, was UM den Aufruf herum
entscheidet: Cache über den Eingabe-Hash, Verwerfen unbekannter Werte, die
Namensvetter-Regel, die stadtweit-Regel aus dem Titel, die Ausblend-Schwelle
der Meldungen und dass die Endpunkte ohne Konto lesbar sind.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

_BACKEND = Path(__file__).resolve().parents[1] / "web" / "backend"
sys.path.insert(0, str(_BACKEND))
# setdefault, nicht setzen: Läuft ein anderes Backend-Testmodul vorher, hat es
# die App schon mit SEINEN Pfaden importiert — ein zweiter Wert hier würde den
# Store an einer anderen Datei ansetzen als die App (gemessen 06.09.2026:
# allein grün, in der Suite rot).
_TMP = tempfile.mkdtemp()
os.environ.setdefault("RATSLOTSE_DB", str(Path(_TMP) / "ratslotse.sqlite"))
os.environ.setdefault("COUNCIL_DB", str(Path(_TMP) / "council.sqlite"))
os.environ.setdefault("WEB_JWT_SECRET", "test-secret")
os.environ.setdefault("WEB_ADMIN_EMAIL", "admin@example.org")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("DISABLE_RATE_LIMIT", "1")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from council import viertel  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from council.store_viertel import PROJECT_HIDE_REPORTS, PROJECT_MIN_CONFIDENCE  # noqa: E402

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
    r = client.post("/api/auth/register", json={"email": email, "password": "password123"})
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


def test_endpunkte_oeffentlich_und_melden():
    store = _store()
    _seed(store)
    store.replace_district_projects("kreyenbrueck", [
        {"name": "Wohnungen Sandkruger Straße", "what": "70 Wohnungen.", "stage": "planning", "when": "2028",
         "category": "housing", "decision_ids": [10], "confidence": 97},
    ])
    store.close()
    client = TestClient(app)

    r = client.get("/api/districts/projects")
    assert r.status_code == 200
    zeile = next(d for d in r.json()["districts"] if d["place_id"] == "kreyenbrueck")
    assert zeile["count"] == 1 and zeile["name"] == "Kreyenbrück"

    r = client.get("/api/districts/kreyenbrueck/projects")
    assert r.status_code == 200
    tafel = r.json()
    assert tafel["place"]["id"] == "kreyenbrueck"
    assert [p["name"] for p in tafel["projects"]] == ["Wohnungen Sandkruger Straße"]
    assert tafel["projects"][0]["decisions"][0]["id"] == 10
    assert tafel["projects"][0]["reported"] is False
    assert len(tafel["neighbours"]) == 3
    assert client.get("/api/districts/nirgendwo/projects").status_code == 404

    pid = tafel["projects"][0]["id"]
    assert client.post(f"/api/districts/projects/{pid}/report", json={}).status_code == 401

    kopf = {"Authorization": f"Bearer {_register(client)}"}
    r = client.post(f"/api/districts/projects/{pid}/report", json={"reason": "liegt in Bümmerstede"}, headers=kopf)
    assert r.status_code == 201 and r.json() == {"ok": True, "report_count": 1, "hidden": False}
    # Zweimal vom selben Konto zählt einmal.
    r = client.post(f"/api/districts/projects/{pid}/report", json={}, headers=kopf)
    assert r.json()["report_count"] == 1
    assert client.get("/api/districts/kreyenbrueck/projects", headers=kopf).json()["projects"][0]["reported"] is True

    kopf2 = {"Authorization": f"Bearer {_register(client, 'zweite@example.org')}"}
    r = client.post(f"/api/districts/projects/{pid}/report", json={}, headers=kopf2)
    assert r.json()["hidden"] is True and r.json()["report_count"] == PROJECT_HIDE_REPORTS
    assert client.get("/api/districts/kreyenbrueck/projects").json()["projects"] == []
    assert client.post("/api/districts/projects/424242/report", json={}, headers=kopf).status_code == 404


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
    monkeypatch.setattr(viertel, "GEDULD_SEKUNDEN", ())  # nicht wirklich warten
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


def test_geduld_versucht_es_wieder(monkeypatch):
    monkeypatch.setattr(viertel, "GEDULD_SEKUNDEN", (0, 0))
    versuche = []

    def wackelig():
        versuche.append(1)
        if len(versuche) < 3:
            raise RuntimeError("429")
        return "ok"

    assert viertel._mit_geduld(wackelig, was="Probe") == "ok"
    assert len(versuche) == 3
    with pytest.raises(RuntimeError):
        viertel._mit_geduld(lambda: (_ for _ in ()).throw(RuntimeError("immer")), was="Probe")


def test_abschnittsgrenzen_sind_kein_gegenstand():
    """„Tweelbäker Tredde (Am Schmeel bis Brahmweg)" baut die Tredde aus — die
    beiden Grenzen bleiben, wie sie sind (Tims Befund 06.09.2026)."""
    from council.store_viertel import ortsrollen
    rollen = ortsrollen(["Tweelbäker Tredde", "Am Schmeel", "Brahmweg", "Dießelweg"], [
        "Tweelbäker Tredde (Am Schmeel bis Brahmweg) – Straßenausbau",
        "Der erste Bauabschnitt umfasst den Bereich zwischen Dießelweg und Am Schmeel.",
    ])
    assert rollen == {"Tweelbäker Tredde": "subject", "Am Schmeel": "boundary",
                      "Brahmweg": "boundary", "Dießelweg": "boundary"}
    # Eine Kreuzung ist Gegenstand, beide Straßen sind betroffen.
    assert ortsrollen(["Schützenhofstraße", "Bremer Straße"],
                      ["Straßenbaumaßnahme Kreuzung Schützenhofstraße/Bremer Straße"]) == {
        "Schützenhofstraße": "subject", "Bremer Straße": "subject"}
    # Nur Grenzen: die Fläche dazwischen ist das Vorhaben — Rolle bleibt Grenze.
    assert ortsrollen(["Rüschenweg"], ["Flächen zwischen der A 29 und dem Rüschenweg"]) == {"Rüschenweg": "boundary"}
    # Nicht im Text (Katalog-Variante) → Gegenstand, nie still weg.
    assert ortsrollen(["Huntemannstr"], ["Kita an der Huntemannstraße"]) == {"Huntemannstr": "subject"}
