"""Themen-Vorschläge aus dem eigenen Stadtteil (Onboarding-Schritt 3).

„Was ist bei mir um die Ecke los?" ist eine andere Frage als „was läuft gerade
in der Stadt?" — der Endpunkt beantwortet beide getrennt, sobald ein
Ortsbereich mitgegeben wird.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web" / "backend"))

from tests.test_backend_api import (  # noqa: E402
    CouncilSession,
    CouncilStore,
    _register,
    app,
)
from app.config import get_settings  # noqa: E402


def _pfade() -> tuple[str, str]:
    """Die Datenbanken, die der ENDPUNKT liest — nicht die, die ein
    Nachbarmodul in die Umgebung geschrieben hat.

    ``get_settings()`` ist gecacht und hält den Pfad fest, der beim ersten
    Aufruf galt. In der vollen Suite setzt ein früher importiertes Modul
    ``COUNCIL_DB`` auf ein eigenes Temp-Verzeichnis; wer stattdessen die
    Konstante aus ``test_backend_api`` nimmt, seedet dann an der App vorbei.
    Genau so waren diese Tests einzeln grün und in der Suite rot — mit leerer
    Vorschlagsliste, obwohl die Entitäten nachweislich in *einer* Datenbank
    standen.
    """
    s = get_settings()
    return str(s.ratslotse_db), str(s.council_db)


@pytest.fixture(autouse=True)
def frische_dbs():
    """Vor jedem Test leere Datenbanken.

    Bewusst hier definiert und NICHT aus ``test_backend_api`` importiert: Eine
    ``autouse``-Fixture wirkt zuverlässig nur in dem Modul, in dem sie steht.
    Importiert man sie, hängt es an der Sammelreihenfolge, ob sie greift —
    paarweise lief alles grün, in der vollen Suite kamen die Konten des
    Vorgänger-Tests durch (Registrierung → 409 → kein Cookie → 401) und die
    Entitäts-IDs kollidierten, was den ganzen Seed zurückrollte.
    """
    for basis in _pfade():
        for endung in ("", "-wal", "-shm"):
            Path(basis + endung).unlink(missing_ok=True)
    yield


@pytest.fixture
def client():
    return TestClient(app)


#: Entität → Ortsbereich, in dem ihre Beschlüsse liegen.
IM_ORT = {
    "Alte Fleiwa": "osternburg",
    "Cäcilienbrücke": "osternburg",
    "Weser-Ems-Hallen": "ziegelhof",
}


def _saat() -> None:
    """Drei Entitäten, zwei davon in Osternburg — je zwei Beschlüsse (das
    Minimum, das ``suggested_entity_topics`` verlangt)."""
    council = CouncilStore(Path(_pfade()[1]))
    jung = (date.today() - timedelta(days=20)).isoformat()
    jetzt = datetime.now(timezone.utc).isoformat(timespec="seconds")
    council.save_session(CouncilSession(1, "Rat", jung, "17:00", "Ratssaal"))
    with council._conn:
        for i in range(6):
            council._insert_decision(1, i, "decision", None, f"Ö {i}", f"Beschluss {i}", "B",
                                     "accepted", None, None, None, [], None, None, None)
        ids = [r[0] for r in council._conn.execute(
            "SELECT id FROM council_decisions ORDER BY id").fetchall()]
        for eid, (name, ort) in enumerate(IM_ORT.items(), start=1):
            slug = name.lower().replace(" ", "-")
            council._conn.execute(
                "INSERT INTO council_entities (id, slug, name, kind, n) VALUES (?,?,?,'ort',3)",
                (eid, slug, name))
            meine = ids[(eid - 1) * 2:(eid - 1) * 2 + 2]
            for did in meine:
                council._conn.execute("INSERT INTO council_entity_links VALUES (?, ?)", (eid, did))
            # Der Ortsbezug hängt am BESCHLUSS, nicht an der Entität — sie erbt
            # ihn von den Beschlüssen, in denen sie vorkommt.
            place = council.resolve_place(ort)
            assert place, ort
            ortslug = f"ort-{place.id}"
            council._conn.execute(
                "INSERT OR REPLACE INTO council_locations "
                "(slug, name, kind, place_id, ortsbereich_id, updated_at) VALUES (?,?,?,?,?,?)",
                (ortslug, place.name, "stadtteil", place.id, place.id, jetzt))
            for did in meine:
                council._conn.execute(
                    "INSERT OR REPLACE INTO council_decision_locations "
                    "(decision_id, location_slug, source, evidence, method, confidence, updated_at) "
                    "VALUES (?,?,?,?,?,?,?)", (did, ortslug, "llm", place.name, "llm", 0.9, jetzt))
    # Vagheits-Urteil vorbelegen. Ohne das ruft der Endpunkt für jeden Namen ein
    # LLM — dessen Ausgang hängt davon ab, ob gerade ein Schlüssel gesetzt ist,
    # und genau daran hingen diese Tests: einzeln grün, in der vollen Suite mit
    # LEERER Vorschlagsliste rot. Geprüft wird hier die Ortsaufteilung, nicht
    # die Vagheitsprüfung — die hat ihre eigenen Tests.
    for name in IM_ORT:
        council.save_topic_vagueness(name.lower().replace(" ", "-"), name,
                                     {"vague": False, "hint": "", "suggestion": ""})
    council.close()


def test_ohne_stadtteil_bleibt_es_bei_einer_liste(client):
    """Der bisherige Vertrag gilt weiter — die App fragt ohne Ortsbereich."""
    _register(client)
    _saat()
    antwort = client.get("/api/topics/suggestions").json()
    assert antwort["districts"] == []
    assert {s["name"] for s in antwort["suggestions"]} == set(IM_ORT)


def test_stadtteil_bekommt_eine_eigene_liste(client):
    _register(client)
    _saat()
    antwort = client.get("/api/topics/suggestions?district=osternburg").json()
    assert [g["name"] for g in antwort["districts"]] == ["Osternburg"]
    assert {s["name"] for s in antwort["districts"][0]["suggestions"]} == {"Alte Fleiwa", "Cäcilienbrücke"}


def test_mehrere_stadtteile_je_eine_gruppe(client):
    """Mehrfachauswahl: Wer im Dobbenviertel wohnt und die Baustelle in
    Osternburg verfolgt, gibt beides an — und bekommt beides getrennt."""
    _register(client)
    _saat()
    antwort = client.get(
        "/api/topics/suggestions?district=osternburg&district=ziegelhof").json()
    # Reihenfolge wie gefragt — sonst springt die Anzeige zwischen zwei Aufrufen.
    assert [g["name"] for g in antwort["districts"]] == ["Osternburg", "Ziegelhof"]
    assert {s["name"] for s in antwort["districts"][1]["suggestions"]} == {"Weser-Ems-Hallen"}
    # Alles Lokale ist vergeben, stadtweit bleibt nichts übrig.
    assert antwort["suggestions"] == []


def test_derselbe_stadtteil_zweimal_zaehlt_einmal(client):
    _register(client)
    _saat()
    antwort = client.get(
        "/api/topics/suggestions?district=osternburg&district=osternburg").json()
    assert [g["name"] for g in antwort["districts"]] == ["Osternburg"]


def test_die_listen_ueberschneiden_sich_nicht(client):
    """Der Grund für das gemeinsame Gedächtnis in ``_vorschlaege_bauen``:
    Ohne es stünde dieselbe Baustelle zweimal untereinander — einmal unter
    einem Stadtteil, einmal unter „stadtweit"."""
    _register(client)
    _saat()
    antwort = client.get("/api/topics/suggestions?district=osternburg").json()
    lokal = {s["name"] for s in antwort["districts"][0]["suggestions"]}
    stadtweit = {s["name"] for s in antwort["suggestions"]}
    assert not (lokal & stadtweit)
    assert stadtweit == {"Weser-Ems-Hallen"}


def test_leerer_stadtteil_antwortet_trotzdem(client):
    """„Hier war zuletzt nichts" ist eine Auskunft. Fehlte der Block ganz,
    sähe es aus, als hätte der Schritt etwas verschluckt."""
    _register(client)
    _saat()
    antwort = client.get("/api/topics/suggestions?district=eversten").json()
    assert antwort["districts"][0]["name"] == "Eversten"
    assert antwort["districts"][0]["suggestions"] == []
    # Und die stadtweite Liste bleibt vollständig.
    assert {s["name"] for s in antwort["suggestions"]} == set(IM_ORT)


def test_unbekannter_ortsbereich_faellt_still_zurueck(client):
    """Ein geratener oder veralteter Ort darf keinen 500 auslösen — der Wert
    kommt aus einer Adresszeile."""
    _register(client)
    _saat()
    antwort = client.get("/api/topics/suggestions?district=gibtesnicht")
    assert antwort.status_code == 200
    assert antwort.json()["districts"] == []
