"""Grundakten (council/matters.py, Plan „Akte“ Phase 1).

Was hier festgehalten wird, ist die Regel, nach der Zeilen zusammengehören —
nicht eine Messung. Gemessen wird am echten Bestand mit
``python eval/run_akten.py --methode grundakte``.
"""
import pytest

from council import matters
from council.store import CouncilStore


@pytest.fixture
def store(tmp_path):
    st = CouncilStore(tmp_path / "council.sqlite")
    c = st._conn
    c.executemany(
        "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, location, "
        "fetched_at) VALUES (?, ?, ?, '', '', '')", [
            (1, "Ausschuss für Stadtgrün, Umwelt und Klima", "2026-04-16"),
            (2, "Rat", "2026-05-04"),
            (3, "Ausschuss für Stadtgrün, Umwelt und Klima", "2026-09-10"),
        ])
    c.executemany(
        "INSERT INTO council_decisions (id, ksinr, position, item_number, title, template_number, "
        "kind, parent_item) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [
            # Dieselbe Vorlage in Ausschuss und Rat, einmal mit /1
            (10, 1, 1, "7", "Spielleitplanung - Beschluss", "26/0100", "decision", None),
            (11, 2, 1, "5", "Spielleitplanung", "26/0100/1", "decision", None),
            # Teilabstimmung zum Rats-TOP 5
            (12, 2, 2, "5.1", "Änderungsantrag der SPD-Fraktion", None, "subvote", "5"),
            # Antrag ohne Nummer — Antrag und Bericht tragen denselben Kern
            (13, 1, 3, "11.1", "Trinkwasserspender im Außenbereich (SPD-Fraktion vom "
             "17.03.2026) - Antrag", None, "decision", None),
            (14, 3, 1, "4", "Trinkwasserspender im Außenbereich (SPD-Fraktion vom "
             "17.03.2026) - Bericht der Verwaltung", None, "decision", None),
            # Zu allgemein für einen Schlüssel
            (15, 3, 2, "9", "Bericht der Verwaltung", None, "decision", None),
        ])
    c.executemany(
        "INSERT INTO council_templates (kvonr, template_number, title, raw_text, fetched_at) "
        "VALUES (?, ?, ?, ?, '')", [
            (500, "26/0100", "Spielleitplanung", "Bezug: Vorlage 25/0999 zum Schlossplatz."),
            (501, "26/0200", "Heidbrook", "Ohne Verweis."),
        ])
    c.executemany(
        "INSERT INTO council_deliberations (id, kvonr, date, committee, result, fetched_at) "
        "VALUES (?, ?, ?, ?, ?, '')", [
            (900, 500, "2026-04-16", "Ausschuss", "Vorberatung"),
            (901, 501, "2026-10-20", "Rat", "Entscheidung"),   # noch nicht protokolliert
        ])
    c.executemany(
        "INSERT INTO council_agenda_items (id, ksinr, item_number, title, template_number, kvonr) "
        "VALUES (?, ?, ?, ?, ?, ?)", [
            (700, 1, "Ö 7", "Spielleitplanung", "26/0100", 500),
            (701, 1, "Ö 1", "Feststellung der Beschlussfähigkeit", None, None),
            (702, 3, "Ö 4", "Trinkwasserspender im Außenbereich (SPD-Fraktion vom 17.03.2026)",
             None, None),
        ])
    c.executemany(
        "INSERT INTO council_speeches (id, ksinr, position, kind, top, speaker, text, extracted_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, '')", [
            # Steht unter TOP 7 „Spielleitplanung“, redet aber vom Schlossplatz
            (800, 1, 1, "speech", "7 Spielleitplanung", "Verwaltung",
             "Auf dem Schlossplatz ist kein Platz für einen Spielplatz."),
            (801, 1, 2, "pledge", "11.1 Trinkwasserspender im Außenbereich", "Verwaltung (Protokollnotiz)",
             "Klärung bis zum Abschluss des KLAK 2027, danach Bau."),
            (802, 1, 3, "inquiry", "Anfragen und Anregungen", "Behrens", "Wann kommt der Radweg?"),
        ])
    c.commit()
    return st


def _akte(store, art, iid):
    m = store.matter_of(art, iid)
    return m["key"] if m else None


def test_eine_vorlage_eine_akte_ueber_alle_gremien(store):
    matters.build(store)
    akte = _akte(store, "decision", 10)
    assert akte == "v:26/0100"
    # Rat mit /1, Beratungsfolge, Tagesordnung, Vorlagen-Text: dieselbe Akte
    assert {_akte(store, "decision", 11), _akte(store, "deliberation", 900),
            _akte(store, "agenda_item", 700), _akte(store, "template", 500)} == {akte}


def test_wortbeitrag_folgt_seinem_top(store):
    matters.build(store)
    assert _akte(store, "speech", 800) == "v:26/0100"           # klingt nach Schlossplatz
    assert _akte(store, "speech", 801) == _akte(store, "decision", 13)


def test_sammel_top_und_formalie_bekommen_keine_akte(store):
    matters.build(store)
    assert _akte(store, "speech", 802) is None                   # Anfragen und Anregungen
    assert _akte(store, "agenda_item", 701) is None             # Beschlussfähigkeit


def test_antrag_und_bericht_teilen_den_titelkern(store):
    matters.build(store)
    assert _akte(store, "decision", 13) == _akte(store, "decision", 14)
    assert _akte(store, "agenda_item", 702) == _akte(store, "decision", 13)
    assert _akte(store, "decision", 13).startswith("t:")


def test_teilabstimmung_gehoert_zum_beschluss_ihres_tops(store):
    matters.build(store)
    assert _akte(store, "decision", 12) == _akte(store, "decision", 11)


def test_allgemeiner_titel_wird_keine_sammelakte(store):
    matters.build(store)
    assert _akte(store, "decision", 15) == "d:15"


def test_angekuendigte_station_steht_schon_in_der_akte(store):
    matters.build(store)
    assert _akte(store, "deliberation", 901) == _akte(store, "template", 501) == "v:26/0200"


def test_verweis_wird_kante_nicht_zusammenlegung(store):
    store._conn.execute(
        "INSERT INTO council_decisions (id, ksinr, position, item_number, title, template_number, "
        "kind) VALUES (16, 3, 3, '10', 'Schlossplatz', '25/0999', 'decision')")
    matters.build(store)
    a, b = store.matter_of("decision", 10), store.matter_of("decision", 16)
    assert a["id"] != b["id"]
    assert [n["key"] for n in store.matter_neighbours(a["id"])] == ["v:25/0999"]


def test_jeder_beschluss_genau_eine_akte_und_neuaufbau_ist_stabil(store):
    erst = matters.build(store)
    ids = {r[0]: r[1] for r in store._conn.execute("SELECT key, id FROM council_matters")}
    zweit = matters.build(store)
    assert {k: v for k, v in erst.items() if k != "sekunden"} == \
        {k: v for k, v in zweit.items() if k != "sekunden"}
    assert ids == {r[0]: r[1] for r in store._conn.execute("SELECT key, id FROM council_matters")}
    ohne = store._conn.execute(
        "SELECT count(*) FROM council_decisions d WHERE NOT EXISTS (SELECT 1 FROM "
        "council_matter_items i WHERE i.item_type = 'decision' AND i.item_id = d.id)").fetchone()[0]
    assert ohne == 0


@pytest.mark.parametrize("titel,kern", [
    ("Spielleitplanung - Beschluss", "spielleitplanung"),
    ("Trinkwasserspender (SPD-Fraktion vom 17.03.2026) - Antrag mit Bericht der Verwaltung",
     "trinkwasserspender|spd fraktion|2026-03-17"),
    ("Antrag der Fraktion BSW: Einführung eines Schulfachs Gesundheit",
     "einführung eines schulfachs gesundheit|antrag der fraktion bsw"),
    ("Bericht der Verwaltung", ""),
    ("Sachstandsbericht Stadionplanung", "sachstandsbericht stadionplanung"),
])
def test_titelkern(titel, kern):
    assert matters.titelkern(titel) == kern


def test_vorlagenbasen_und_top_nummer():
    assert matters.vorlagen_basen("26/0001, 26/0002/1") == ["26/0001", "26/0002"]
    assert matters.top_nummer("Ö 7.5") == "7.5"
    assert matters.top_nummer("11.1 Trinkwasser") == "11.1"
