"""Die Ideen-Seite: was andere Städte haben und Oldenburg fehlt.

Der wichtigste Fall ist wieder der **leere**: Ohne Städte-Datenbank — auf
einem frischen Checkout, in der CI, bei den Browsertests — muss der Endpunkt
mit 200 und leeren Listen antworten, sonst zeigt die Seite einen Fehler statt
„noch nichts geprüft".

Der zweitwichtigste ist die **Sortierung**. Sie beantwortet „was soll ich
lesen" und entsteht im SQL, nicht im Frontend; ein Test hält sie fest, weil
ein umsortiertes CASE sonst niemandem auffiele.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from council.cities.model import Batch, Body, Paper
from council.cities.store import CitiesStore
from council.store import CouncilStore
from web.backend.app.deps import get_cities_store, get_council_store
from web.backend.app.main import app


def _urteil(status: str, worth: str, confidence: str = "high",
            evidence: list[str] | None = None) -> dict:
    return {"status": status, "worth": worth, "confidence": confidence,
            "evidence": evidence or [], "reason": "Begründung.",
            "why_worth": "Warum es sich lohnt.", "obstacles": None}


@pytest.fixture()
def rats_db(tmp_path):
    """Ein Oldenburger Beschluss, auf den ein Beleg zeigen kann."""
    store = CouncilStore(tmp_path / "council.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, "
            "location, fetched_at) VALUES (7, 'Rat', '2025-11-20', '16:00', 'PFL', '2025-11-21')")
        store._conn.execute(
            "INSERT INTO council_decisions (id, ksinr, position, kind, item_number, title, "
            "  outcome, kvonr) VALUES (1, 7, 1, 'decision', '4', 'Kommunale Wärmeplanung', "
            "  'accepted', 4711)")
        store._conn.execute(
            "INSERT INTO council_templates (kvonr, template_number, title, fetched_at, "
            "  status, attachments_scanned) VALUES (4711, '25/0001', 'Wärmeplanung', "
            "  '2025-11-21', 'ok', 0)")
    yield store
    store.close()


@pytest.fixture()
def cities_db(tmp_path):
    s = CitiesStore(tmp_path / "cities.sqlite")
    s.upsert_body(Body("osnabrueck", "Stadt Osnabrück", "NI", "allris4"))
    s.upsert_batch(Batch(papers=[
        Paper("oldenburg:paper:4711", "oldenburg", "Kommunale Wärmeplanung"),
        # Absteigend nach dem, was die Sortierung vorn haben will.
        Paper("os:p:1", "osnabrueck", "Hitzeaktionsplan aufstellen", date="2026-05-01",
              kind="motion", web="https://example.org/vo/1"),
        Paper("os:p:2", "osnabrueck", "Wärmenetz erweitern", date="2026-04-01",
              kind="proposal"),
        Paper("os:p:3", "osnabrueck", "Wärmeplan beschließen", date="2026-03-01",
              kind="proposal"),
        Paper("os:p:9", "osnabrueck", "Ganz andere Sache", date="2026-02-01"),
    ]))
    for pid, feld, transfer in (("os:p:1", "klima_umwelt", "adaptable"),
                                ("os:p:2", "klima_umwelt", "direct"),
                                ("os:p:3", "klima_umwelt", "direct"),
                                ("os:p:9", "verkehr", "adaptable")):
        s.put_annotation("paper", pid, "classify", "2",
                         {"field": feld, "transfer": transfer, "competence": "council",
                          "instrument": "Instrument", "summary": "Zusammenfassung.",
                          "originator": "SPD-Fraktion"}, "h" + pid)
    s.put_annotation("paper", "os:p:1", "fit", "1", _urteil("missing", "yes"), "f1")
    s.put_annotation("paper", "os:p:2", "fit", "1", _urteil("partial", "yes"), "f2")
    s.put_annotation("paper", "os:p:3", "fit", "1",
                     _urteil("present", "no", evidence=["oldenburg:paper:4711"]), "f3")
    s.put_annotation("paper", "os:p:9", "fit", "1", _urteil("missing", "maybe"), "f9")
    yield s
    s.close()


@pytest.fixture()
def client(rats_db, cities_db):
    app.dependency_overrides[get_council_store] = lambda: rats_db
    app.dependency_overrides[get_cities_store] = lambda: cities_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# ------------------------------------------------------------- Übersicht

def test_die_uebersicht_zaehlt_je_themenfeld(client):
    felder = {f["field"]: f for f in client.get(
        "/api/council/cities/ideas/fields").json()["fields"]}
    assert felder["klima_umwelt"]["total"] == 3
    assert felder["klima_umwelt"]["missing"] == 1
    assert felder["klima_umwelt"]["partial"] == 1
    assert felder["klima_umwelt"]["present"] == 1
    assert felder["klima_umwelt"]["worth_yes"] == 2
    assert felder["verkehr"]["total"] == 1


def test_die_uebersicht_stellt_das_ergiebigste_feld_nach_vorn(client):
    """Sie soll sagen, wo etwas liegt — nicht alphabetisch sortieren."""
    felder = [f["field"] for f in client.get(
        "/api/council/cities/ideas/fields").json()["fields"]]
    assert felder[0] == "klima_umwelt"


# -------------------------------------------------------------- Ein Feld

def test_die_reihenfolge_beantwortet_was_soll_ich_lesen(client):
    """Erst was sich lohnt, dann was fehlt, dann das Neueste. Ohne Filter
    kommt auch das Vorhandene mit — aber zuletzt."""
    daten = client.get("/api/council/cities/ideas?field=klima_umwelt&status=&worth=").json()
    assert [i["paper_id"] for i in daten["items"]] == ["os:p:1", "os:p:2", "os:p:3"]


def test_die_vorgabe_zeigt_nur_was_fehlt_und_sich_lohnt(client):
    daten = client.get("/api/council/cities/ideas?field=klima_umwelt").json()
    assert [i["paper_id"] for i in daten["items"]] == ["os:p:1", "os:p:2"]
    assert daten["total"] == 2
    # Die Zähler gehören zur Antwort, nicht ins Frontend — sonst müsste es
    # durch alles blättern, um eine Zahl zu zeigen.
    assert daten["counts"] == {"missing": 1, "partial": 1}


def test_ein_feld_ist_pflicht(client):
    """Eine Liste über alle zwölf Felder wäre ein Fließband ohne Anfang."""
    assert client.get("/api/council/cities/ideas").status_code == 422


def test_der_anzeigename_kommt_aus_der_registry(client):
    """Die Osnabrücker Schnittstelle nennt sich selbst „Stadt Osnabrück"."""
    daten = client.get("/api/council/cities/ideas?field=klima_umwelt").json()
    assert daten["items"][0]["body_name"] == "Osnabrück"


def test_das_urteil_kommt_mit_allem_was_die_karte_braucht(client):
    (erste, _) = client.get("/api/council/cities/ideas?field=klima_umwelt").json()["items"]
    assert erste["status"] == "missing" and erste["worth"] == "yes"
    assert erste["reason"] and erste["why_worth"]
    assert erste["confidence"] == "high"
    assert erste["originator"] == "SPD-Fraktion"
    assert erste["web"] == "https://example.org/vo/1"


def test_belege_werden_auf_beschluesse_aufgeloest(client):
    """Das Urteil nennt `oldenburg:paper:4711`; die Karte soll auf die
    Beschluss-Seite führen. Die Übersetzung braucht die Rats-Datenbank."""
    daten = client.get(
        "/api/council/cities/ideas?field=klima_umwelt&status=present&worth=no").json()
    (eintrag,) = daten["items"]
    (beleg,) = eintrag["evidence"]
    assert beleg["decision_id"] == 1
    assert beleg["kvonr"] == 4711
    assert beleg["title"] == "Kommunale Wärmeplanung"
    assert beleg["outcome"] == "accepted"


def test_ein_beleg_ohne_beschluss_faellt_weg(client, cities_db):
    """Anträge aus Anlagen und der Themenfeld-Rückblick tragen keine
    Vorlagen-Id. Auf der Karte stünde sonst eine Zeile ohne Ziel."""
    cities_db.put_annotation(
        "paper", "os:p:2", "fit", "1",
        _urteil("partial", "yes", evidence=["recap:klima_umwelt",
                                            "oldenburg:paper:att:99"]), "f2b")
    daten = client.get("/api/council/cities/ideas?field=klima_umwelt").json()
    zweite = next(i for i in daten["items"] if i["paper_id"] == "os:p:2")
    assert zweite["evidence"] == []


def test_nach_stadt_filtern(client):
    leer = client.get(
        "/api/council/cities/ideas?field=klima_umwelt&body=muenster").json()
    assert leer["items"] == [] and leer["total"] == 0


def test_blaettern_bleibt_stabil(client):
    erste = client.get(
        "/api/council/cities/ideas?field=klima_umwelt&status=&worth=&per_page=2").json()
    zweite = client.get(
        "/api/council/cities/ideas?field=klima_umwelt&status=&worth=&per_page=2&page=2").json()
    assert len(erste["items"]) == 2 and len(zweite["items"]) == 1
    assert erste["total"] == zweite["total"] == 3
    assert not ({i["paper_id"] for i in erste["items"]}
                & {i["paper_id"] for i in zweite["items"]})


# ------------------------------------------------------------------ Leer

def test_ohne_staedte_datenbank_antwortet_er_trotzdem(rats_db, tmp_path):
    """Der Normalzustand vor dem ersten Cron-Lauf — und in jeder CI."""
    leer = CitiesStore(tmp_path / "leer.sqlite")
    app.dependency_overrides[get_council_store] = lambda: rats_db
    app.dependency_overrides[get_cities_store] = lambda: leer
    try:
        c = TestClient(app)
        assert c.get("/api/council/cities/ideas/fields").json() == {"fields": []}
        daten = c.get("/api/council/cities/ideas?field=verkehr").json()
        assert daten["items"] == [] and daten["total"] == 0
    finally:
        app.dependency_overrides.clear()
        leer.close()


def test_die_endpunkte_sind_oeffentlich(client):
    """Wie die Beschluss-Seiten: Es stehen nur Ratsdokumente anderer Städte
    darin und ein Urteil darüber, ob Oldenburg dasselbe schon hat."""
    assert client.get("/api/council/cities/ideas/fields").status_code == 200
    assert client.get("/api/council/cities/ideas?field=verkehr").status_code == 200


def test_oldenburg_taucht_nicht_als_idee_auf(client, cities_db):
    """Es ist die Stadt, gegen die verglichen wird — nicht eine unter ihnen."""
    cities_db.put_annotation("paper", "oldenburg:paper:4711", "classify", "2",
                             {"field": "klima_umwelt", "transfer": "direct"}, "hol")
    cities_db.put_annotation("paper", "oldenburg:paper:4711", "fit", "1",
                             _urteil("missing", "yes"), "fol")
    daten = client.get(
        "/api/council/cities/ideas?field=klima_umwelt&status=&worth=").json()
    assert all(not i["paper_id"].startswith("oldenburg:") for i in daten["items"])
