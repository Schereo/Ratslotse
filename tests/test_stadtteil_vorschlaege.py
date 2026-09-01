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

#: Genug für die vollen sechs in Osternburg (für ``_saat(viele=True)``).
IM_ORT_VIELE = {
    **IM_ORT,
    "Hafenbahn": "osternburg", "Bürgerbusch": "osternburg",
    "Klingenbergplatz": "osternburg", "Sportpark Osternburg": "osternburg",
}


def _saat(viele: bool = False) -> None:
    """Drei Entitäten, zwei davon in Osternburg — je zwei Beschlüsse (das
    Minimum, das ``suggested_entity_topics`` verlangt).

    ``viele=True`` legt in Osternburg genug an, dass der Stadtteil die sechs
    aus eigener Kraft schafft und keine Nachbarschaft braucht."""
    orte = IM_ORT_VIELE if viele else IM_ORT
    council = CouncilStore(Path(_pfade()[1]))
    jung = (date.today() - timedelta(days=20)).isoformat()
    jetzt = datetime.now(timezone.utc).isoformat(timespec="seconds")
    council.save_session(CouncilSession(1, "Rat", jung, "17:00", "Ratssaal"))
    with council._conn:
        for i in range(2 * len(orte)):
            council._insert_decision(1, i, "decision", None, f"Ö {i}", f"Beschluss {i}", "B",
                                     "accepted", None, None, None, [], None, None, None)
        ids = [r[0] for r in council._conn.execute(
            "SELECT id FROM council_decisions ORDER BY id").fetchall()]
        for eid, (name, ort) in enumerate(orte.items(), start=1):
            slug = name.lower().replace(" ", "-")
            council._conn.execute(
                "INSERT INTO council_entities (id, slug, name, kind, n) VALUES (?,?,?,'place',3)",
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
    for name in orte:
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
    """Der Grund für das gemeinsame Gedächtnis in ``_build_suggestions``:
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


def test_duenner_stadtteil_wird_von_nebenan_aufgefuellt(client):
    """Der Grund, warum es „nebenan" überhaupt gibt.

    Am Prod-Bestand nachgemessen (01.09.2026): 15 der 31 Ortsbereiche kommen
    selbst über drei Jahre nicht auf sechs Vorschläge, zwei auf gar keinen. Ein
    dauerhaft leerer Block wäre dort das Ergebnis. Hier hat Drielake nichts
    Eigenes; seine drei nächsten Ortsbereiche sind Drielaker-Moor, Osternburg
    und Gerichtsviertel — aus Osternburg muss es also auffüllen.
    """
    _register(client)
    _saat()
    antwort = client.get("/api/topics/suggestions?district=drielake").json()
    gruppe = antwort["districts"][0]
    assert gruppe["name"] == "Drielake"
    assert gruppe["suggestions"] == []             # in Eversten selbst nichts
    assert gruppe["nearby"], "dünner Stadtteil bekam keine Nachbarschaft"
    # Jeder Nachbar-Vorschlag sagt, WOHER er kommt — ohne das wäre er unter der
    # Überschrift des eigenen Stadtteils eine Falschauskunft.
    assert all(v.get("place") for v in gruppe["nearby"])
    assert {v["place"] for v in gruppe["nearby"]} == {"Osternburg"}


def test_voller_stadtteil_braucht_kein_nebenan(client):
    """Wer selbst genug hat, bekommt keine fremden Vorschläge untergemischt."""
    _register(client)
    _saat(viele=True)
    antwort = client.get("/api/topics/suggestions?district=osternburg").json()
    gruppe = antwort["districts"][0]
    assert len(gruppe["suggestions"]) >= 6
    assert gruppe["nearby"] == []


def test_zeitfenster_wird_mitgeliefert(client):
    """Die Oberfläche schreibt den Zeitraum dazu, sobald er über ein Jahr geht —
    stumm zu weiten hieße, Aktualität zu behaupten."""
    _register(client)
    _saat()
    gruppe = client.get("/api/topics/suggestions?district=osternburg").json()["districts"][0]
    assert gruppe["months"] in (12, 24, 36)


def test_unbekannter_ortsbereich_faellt_still_zurueck(client):
    """Ein geratener oder veralteter Ort darf keinen 500 auslösen — der Wert
    kommt aus einer Adresszeile."""
    _register(client)
    _saat()
    antwort = client.get("/api/topics/suggestions?district=gibtesnicht")
    assert antwort.status_code == 200
    assert antwort.json()["districts"] == []


def test_zusammengeschriebene_dublette_erscheint_nur_einmal():
    """Am Prod-Bestand gefunden: „Alte Fleiwa" und „AlteFleiwa" standen als
    zwei Entitäten nebeneinander im Vorschlagsblock für Ziegelhof — die
    einzige Dublette unter 186 Vorschlägen, aber im Onboarding sieht man sie
    sofort. Namen, die sich nur in der Zusammenschreibung unterscheiden, sind
    dieselbe Sache; Großschreibung ohne Fuge („OLantis", „IQON") nicht.
    """
    from app.routers.topics import _name_tokens, _similar_names

    assert _similar_names(_name_tokens("AlteFleiwa"), _name_tokens("Alte Fleiwa"))
    assert not _similar_names(_name_tokens("OLantis Huntebad"), _name_tokens("IQON"))
    assert not _similar_names(_name_tokens("Veloroute 4"), _name_tokens("Veloroute 2"))


def test_lange_strasse_schleppt_keine_fremden_themen_ein(client):
    """Die Mehrfach-Zugehörigkeit gilt für BESCHLÜSSE, nicht für Vorschläge.

    Die Alexanderstraße läuft durch fünf Ortsbereiche. Ein Beschluss über sie
    gehört in alle fünf Filter — aber eine Entität, die nur zufällig im selben
    Beschluss steht, ist deshalb kein Thema für alle fünf. Mit der weiten
    Bedingung schlug das Ehnernviertel „Hallensichel-Ost" vor, ein
    Fliegerhorst-Thema, und verdrängte damit die richtigen Vorschläge.
    """
    from council.store import CouncilStore as CS

    _register(client)
    _saat()
    council = CS(Path(_pfade()[1]))
    try:
        # Der Ort in Osternburg gehört zusätzlich zu Ziegelhof — wie es eine
        # lange Straße täte.
        with council._conn:
            council._conn.execute(
                "INSERT OR REPLACE INTO council_location_districts "
                "(location_slug,district,place_id,share) VALUES "
                "('ort-osternburg','Ziegelhof','ziegelhof',0.2)")
    finally:
        council.close()
    gruppe = client.get("/api/topics/suggestions?district=ziegelhof").json()["districts"][0]
    eigene = {s["name"] for s in gruppe["suggestions"]}
    assert "Alte Fleiwa" not in eigene and "Cäcilienbrücke" not in eigene, eigene


def test_enges_fenster_gewinnt_nicht_mit_lauter_adressen(client):
    """Das Zeitfenster hört auf, wenn genug TRAGENDE Vorschläge da sind.

    Vorher reichte „sechs Einträge". Seit auch Straßen ihren Stadtteil sicher
    kennen, füllen sie die sechs mühelos — und das enge Fenster gewann mit
    einer Liste aus lauter Adressen: In Osternburg verdrängte die
    „Cloppenburger Straße" die Amalienbrücke, im Ziegelhof die
    „Industriestraße" das IQON. Ein Jahr jünger ist kein Vorteil, wenn dafür
    das Interessante wegfällt.
    """
    from app.routers.topics import _tragende

    assert _tragende([{"name": "Cäcilienbrücke"}, {"name": "Amalienbrücke"}]) == 2
    # Straßennamen zählen nicht als tragend — vorne wie hinten erkannt.
    assert _tragende([{"name": "Cloppenburger Straße"}, {"name": "Am Rundtörn"},
                      {"name": "Pophankenweg"}, {"name": "Bahnhofsallee"}]) == 0
    # Ein Vorhaben, das zufällig auf „-weg" endet, bleibt eine Adresse; ein
    # benanntes Vorhaben nicht.
    assert _tragende([{"name": "Bebauungsplan 851"}, {"name": "OLantis Huntebad"}]) == 2
