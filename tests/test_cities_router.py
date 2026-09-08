"""Der Endpunkt „Anderswo beschlossen".

Der wichtigste Fall ist der **leere**: Solange ``check_cities`` nicht gelaufen
ist — auf einem frischen Checkout, in der CI, bei den Browsertests — gibt es
keine Städte-Datenbank. Der Endpunkt muss dann mit 200 und einer leeren Liste
antworten, damit die Beschluss-Seite den Block ausblendet statt einen Fehler
zu zeigen.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from council.cities.index import EMBED_MODEL
from council.cities.model import Batch, Body, Paper
from council.cities.store import CitiesStore
from council.store import CouncilStore
from web.backend.app.deps import get_cities_store, get_council_store
from web.backend.app.main import app


@pytest.fixture()
def rats_db(tmp_path):
    """Vier Beschlüsse: mit kvonr, ganz ohne Vorlage, und zwei, die ihre
    Vorlage erst über die Nummer finden — der Normalfall im Bestand (274 von
    9.059 Beschlüssen tragen eine kvonr, 6.553 eine Vorlagennummer)."""
    store = CouncilStore(tmp_path / "council.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, "
            "location, fetched_at) VALUES (99, 'Rat', '2026-06-01', '16:00', 'Rathaus', '2026-06-02')")
        store._conn.execute(
            "INSERT INTO council_decisions (id, ksinr, position, kind, item_number, title, "
            "  outcome, kvonr) VALUES (1, 99, 1, 'decision', '5', 'Kommunale Wärmeplanung', "
            "  'accepted', 4711)")
        store._conn.execute(
            "INSERT INTO council_decisions (id, ksinr, position, kind, item_number, title, outcome) "
            "VALUES (2, 99, 2, 'decision', '6', 'Wahl der Schriftführung', 'accepted')")
        # Nur Vorlagennummer, keine kvonr — die Brücke muss sie auflösen.
        store._conn.execute(
            "INSERT INTO council_decisions (id, ksinr, position, kind, item_number, title, "
            "  outcome, template_number) VALUES (3, 99, 3, 'decision', '7', "
            "  'Kommunale Wärmeplanung — 2. Lesung', 'accepted', '26/0468')")
        # Die Fassung „/1"; die Tagesordnung führt sie unter der Grundnummer.
        store._conn.execute(
            "INSERT INTO council_decisions (id, ksinr, position, kind, item_number, title, "
            "  outcome, template_number) VALUES (4, 99, 4, 'decision', '8', "
            "  'Kommunale Wärmeplanung — Neufassung', 'accepted', '26/0468/1')")
        # Beides gesetzt und widersprüchlich: die kvonr am Beschluss gewinnt.
        store._conn.execute(
            "INSERT INTO council_decisions (id, ksinr, position, kind, item_number, title, "
            "  outcome, kvonr, template_number) VALUES (5, 99, 5, 'decision', '9', "
            "  'Kommunale Wärmeplanung — Bericht', 'noted', 4711, '26/0999')")
        for nr, kvonr in (("26/0468", 4711), ("26/0999", 9999)):
            store._conn.execute(
                "INSERT INTO council_templates (kvonr, template_number, title, fetched_at, "
                "  status, attachments_scanned) VALUES (?, ?, 'Kommunale Wärmeplanung', "
                "  '2026-06-02', 'ok', 0)", (kvonr, nr))
    yield store
    store.close()


@pytest.fixture()
def cities_db(tmp_path):
    store = CitiesStore(tmp_path / "cities.sqlite")
    store.upsert_body(Body("osnabrueck", "Osnabrück", "NI", "allris4"))
    store.upsert_batch(Batch(papers=[
        Paper("oldenburg:paper:4711", "oldenburg", "Kommunale Wärmeplanung"),
        Paper("os:p:1", "osnabrueck", "Kommunale Wärmeplanung", reference="VO/2026/1",
              date="2026-05-01", paper_type_raw="Beschlussvorlage", kind="proposal",
              web="https://example.org/vo/1"),
    ]))
    store.put_annotation("paper", "os:p:1", "classify", "2",
                         {"summary": "Der Wärmeplan wird beschlossen.",
                          "instrument": "Kommunale Wärmeplanung beschließen",
                          "transfer": "direct", "originator": "SPD-Fraktion"}, "h")
    store.replace_neighbors(EMBED_MODEL, "paper", "oldenburg:paper:4711",
                            [("paper", "os:p:1", 0.86)])
    yield store
    store.close()


@pytest.fixture()
def client(rats_db, cities_db):
    app.dependency_overrides[get_council_store] = lambda: rats_db
    app.dependency_overrides[get_cities_store] = lambda: cities_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_liefert_die_fremde_vorlage_mit_allem_was_die_karte_braucht(client):
    antwort = client.get("/api/council/decision/1/elsewhere")
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["decision_id"] == 1
    assert daten["bodies"] == ["Osnabrück"]
    (eintrag,) = daten["items"]
    assert eintrag["body_name"] == "Osnabrück"
    assert eintrag["name"] == "Kommunale Wärmeplanung"
    assert eintrag["web"] == "https://example.org/vo/1"
    assert eintrag["score"] == 0.86
    assert eintrag["summary"].startswith("Der Wärmeplan")
    assert eintrag["transfer"] == "direct"
    assert eintrag["originator"] == "SPD-Fraktion"
    # Ohne Sitzung dahinter gibt es kein Ergebnis — „none", nicht null.
    assert eintrag["outcome"] == "none"


def test_beschluss_ohne_vorlage_bekommt_eine_leere_liste(client):
    """Wahlen und Verfahrensfragen hängen an keiner Vorlage — für sie gibt es
    anderswo auch nichts zu holen."""
    daten = client.get("/api/council/decision/2/elsewhere").json()
    assert daten == {"decision_id": 2, "items": [], "bodies": []}


def test_unbekannter_beschluss_ist_ein_404(client):
    assert client.get("/api/council/decision/999/elsewhere").status_code == 404


def test_ohne_staedte_datenbank_antwortet_er_trotzdem(rats_db, tmp_path):
    """Der Normalzustand vor dem ersten Cron-Lauf — und in jeder CI."""
    leer = CitiesStore(tmp_path / "leer.sqlite")
    app.dependency_overrides[get_council_store] = lambda: rats_db
    app.dependency_overrides[get_cities_store] = lambda: leer
    try:
        antwort = TestClient(app).get("/api/council/decision/1/elsewhere")
        assert antwort.status_code == 200
        assert antwort.json()["items"] == []
    finally:
        app.dependency_overrides.clear()
        leer.close()


def test_der_endpunkt_ist_oeffentlich(client):
    """Wie die Beschluss-Seite selbst — ohne Anmeldung lesbar."""
    antwort = client.get("/api/council/decision/1/elsewhere")
    assert antwort.status_code == 200


def test_formalvorgaenge_fliegen_raus(client, cities_db):
    """Ein Vorgang, den die Einordnung selbst als `one_off` führt, teilt mit
    dem Beschluss nur das Vokabular. Gemessen am Klimakonzept-Beschluss stand
    „Bestellung der Schriftführung für den Ausschuss für Umweltschutz" so als
    sechster Treffer in der Liste."""
    cities_db.upsert_batch(Batch(papers=[
        Paper("os:p:2", "osnabrueck", "Bestellung der Schriftführung für den "
              "Ausschuss für Umwelt und Klima", web="https://example.org/vo/2")]))
    cities_db.put_annotation("paper", "os:p:2", "classify", "2",
                             {"summary": "Schriftführung wird bestellt.",
                              "transfer": "one_off"}, "h2")
    cities_db.replace_neighbors(EMBED_MODEL, "paper", "oldenburg:paper:4711",
                                [("paper", "os:p:1", 0.86), ("paper", "os:p:2", 0.74)])
    daten = client.get("/api/council/decision/1/elsewhere").json()
    assert [i["paper_id"] for i in daten["items"]] == ["os:p:1"]


def test_ohne_ergebnis_bleibt_das_feld_none(client, cities_db):
    """Die meisten fremden Vorlagen tragen keine Beratungsstation mit Ergebnis.
    Der Block zeigt dann keine Ergebnis-Marke statt einer leeren."""
    daten = client.get("/api/council/decision/1/elsewhere").json()
    assert all(i["outcome"] == "none" for i in daten["items"])


def test_zufallsnahe_treffer_werden_nicht_gezeigt(client, cities_db):
    """Der Median der Ähnlichkeit zweier BELIEBIGER Verwaltungstexte liegt bei
    0,70. Darunter ist ein Treffer nicht besser als Zufall — er sieht nur so
    aus, weil er auf einer Liste steht. Gemessen: „Verschwiegenheitspflicht
    kommunaler Aufsichtsräte" stand bei 0,570 unter dem Klimakonzept."""
    cities_db.upsert_batch(Batch(papers=[
        Paper("os:p:3", "osnabrueck", "Verschwiegenheitspflicht kommunaler Aufsichtsräte")]))
    # Übertragbar eingeordnet — es scheitert allein an der Nähe.
    cities_db.put_annotation("paper", "os:p:3", "classify", "2",
                             {"summary": "Aufsichtsräte werden belehrt.",
                              "transfer": "adaptable"}, "h3")
    cities_db.replace_neighbors(EMBED_MODEL, "paper", "oldenburg:paper:4711",
                                [("paper", "os:p:1", 0.86), ("paper", "os:p:3", 0.57)])
    daten = client.get("/api/council/decision/1/elsewhere").json()
    assert [i["paper_id"] for i in daten["items"]] == ["os:p:1"]


def test_dieselbe_sache_zweimal_kostet_nur_einen_platz(client, cities_db):
    """Magdeburg führt „Projekt Nachtengel" als Antrag UND als Vorlage. Zwei
    Zeilen mit demselben Titel sagen nicht mehr als eine."""
    cities_db.upsert_batch(Batch(papers=[
        Paper("os:p:4", "osnabrueck", "Kommunale Wärmeplanung", date="2026-04-01"),
        Paper("bs:p:1", "braunschweig", "Kommunale Wärmeplanung", date="2026-03-01")]))
    cities_db.upsert_body(Body("braunschweig", "Braunschweig", "NI", "allris4"))
    for pid in ("os:p:4", "bs:p:1"):
        cities_db.put_annotation("paper", pid, "classify", "2",
                                 {"summary": "Wärmeplan.", "transfer": "adaptable"}, "h" + pid)
    cities_db.replace_neighbors(EMBED_MODEL, "paper", "oldenburg:paper:4711",
                                [("paper", "os:p:1", 0.86), ("paper", "os:p:4", 0.84),
                                 ("paper", "bs:p:1", 0.82)])
    daten = client.get("/api/council/decision/1/elsewhere").json()
    # Osnabrück nur einmal — Braunschweig bleibt, es ist eine andere Stadt.
    assert [i["paper_id"] for i in daten["items"]] == ["os:p:1", "bs:p:1"]
    assert daten["bodies"] == ["Braunschweig", "Osnabrück"]


def test_ratsmitglieder_stehen_mit_namen_da(client, cities_db):
    """Wer einen Antrag stellt, tut das als Mandatsträgerin in einem
    öffentlichen Verfahren — der Name gehört zur Sache (Tim, 08.09.2026)."""
    cities_db.put_annotation(
        "paper", "os:p:1", "classify", "2",
        {"summary": "Der Wärmeplan wird beschlossen.", "transfer": "direct",
         "originator": "Stadtverordnete Kapp, Kogge und Fraktion DIE aNDERE"}, "h")
    (eintrag,) = client.get("/api/council/decision/1/elsewhere").json()["items"]
    assert eintrag["originator"] == "Stadtverordnete Kapp, Kogge und Fraktion DIE aNDERE"


def test_bei_einer_eingabe_bleibt_der_urheber_weg(client, cities_db):
    """Einwohneranträge kommen von Privatpersonen. Deren Namen stehen im
    Ratsinformationssystem der jeweiligen Stadt — sie von dort auf eine
    Oldenburger Beschlussseite zu heben, ist etwas anderes."""
    cities_db.upsert_batch(Batch(papers=[
        Paper("os:p:9", "osnabrueck", "Einwohnerantrag Wärmenetz", kind="petition",
              paper_type_raw="Einwohnerantrag", web="https://example.org/vo/9")]))
    cities_db.put_annotation("paper", "os:p:9", "classify", "2",
                             {"summary": "Ein Wärmenetz wird gefordert.",
                              "transfer": "adaptable", "originator": "Anna Beispiel"}, "h9")
    cities_db.replace_neighbors(EMBED_MODEL, "paper", "oldenburg:paper:4711",
                                [("paper", "os:p:9", 0.84)])
    (eintrag,) = client.get("/api/council/decision/1/elsewhere").json()["items"]
    assert eintrag["paper_id"] == "os:p:9"
    assert eintrag["originator"] is None


# ------------------------------------------------------- Brücke zur Vorlage

def test_brücke_über_die_vorlagennummer(client):
    """Der Regelfall: Der Beschluss trägt keine `kvonr`, aber eine
    Vorlagennummer — und `council_templates` übersetzt sie. Ohne diesen Umweg
    erschien der Block auf 50 von 9.059 Beschluss-Seiten, mit ihm auf 486."""
    daten = client.get("/api/council/decision/3/elsewhere").json()
    assert [i["paper_id"] for i in daten["items"]] == ["os:p:1"]
    assert daten["decision_id"] == 3


def test_die_fassung_findet_die_grundnummer(client):
    """„26/0468/1" steht im Protokoll, „26/0468" in der Tagesordnung.
    `get_vorlage_by_nr` fällt auf die Grundnummer zurück."""
    daten = client.get("/api/council/decision/4/elsewhere").json()
    assert [i["paper_id"] for i in daten["items"]] == ["os:p:1"]


def test_die_kvonr_am_beschluss_gewinnt(client):
    """Beides gesetzt, und die Nummer zeigt auf eine andere Vorlage: Die
    `kvonr` am Beschluss ist die genauere Angabe, die Nummer der Rückfall."""
    daten = client.get("/api/council/decision/5/elsewhere").json()
    assert [i["paper_id"] for i in daten["items"]] == ["os:p:1"]


def test_wahl_hat_weder_kvonr_noch_nummer(client):
    """Wahlen und Verfahrensfragen hängen an gar keiner Vorlage — auch die
    Brücke findet dort nichts."""
    assert client.get("/api/council/decision/2/elsewhere").json()["items"] == []


# ------------------------------------------------ Nur übertragbare Treffer

def test_nur_übertragbare_treffer_werden_gezeigt(client, cities_db):
    """Das Einbettungsmodell misst die Textsorte, nicht das Thema: Ein
    Bebauungsplan findet Bebauungspläne bei 0,84. Eine Schwelle trennt das
    nicht — die Einordnung schon."""
    cities_db.upsert_batch(Batch(papers=[
        Paper("os:p:5", "osnabrueck", "Bebauungsplan Nr. 674"),
        Paper("os:p:6", "osnabrueck", "Wärmenetz-Ausbau beschließen"),
        Paper("os:p:7", "osnabrueck", "Noch nicht eingeordnet")]))
    cities_db.put_annotation("paper", "os:p:5", "classify", "2",
                             {"summary": "Satzungsbeschluss.", "transfer": "local"}, "h5")
    cities_db.put_annotation("paper", "os:p:6", "classify", "2",
                             {"summary": "Wärmenetz.", "transfer": "adaptable"}, "h6")
    cities_db.replace_neighbors(EMBED_MODEL, "paper", "oldenburg:paper:4711",
                                [("paper", "os:p:5", 0.84), ("paper", "os:p:6", 0.79),
                                 ("paper", "os:p:7", 0.77)])
    daten = client.get("/api/council/decision/1/elsewhere").json()
    # `local` fliegt trotz höchster Nähe raus; das noch nicht eingeordnete
    # Papier ebenfalls — der nächste Cron holt es nach.
    assert [i["paper_id"] for i in daten["items"]] == ["os:p:6"]
