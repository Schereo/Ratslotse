"""Oldenburg als Stadt Nummer null — aus der Rats-Datenbank, ohne Netz.

Der Adapter ist die Voraussetzung dafür, dass der Vergleich symmetrisch ist:
Erst wenn Oldenburg im selben Speicher liegt, sind „was fehlt uns?" und „was
haben wir, was andere nicht haben?" dieselbe Rechnung mit vertauschten Rollen.
"""
from __future__ import annotations

import pytest

from council.cities.adapters.oldenburg import (
    OldenburgAdapter, agenda_id, faction_id, meeting_id, motion_id, paper_id,
)
from council.cities.model import FileRole, Outcome, PaperKind
from council.cities.oparl import OParlClient
from council.cities.registry import BODIES
from council.cities.store import CitiesStore
from council.store import CouncilStore


@pytest.fixture()
def rats_db(tmp_path, monkeypatch):
    """Eine kleine, aber echte Rats-Datenbank: Schema aus ``CouncilStore``."""
    pfad = tmp_path / "council.sqlite"
    store = CouncilStore(pfad)
    conn = store._conn
    with conn:
        conn.execute("INSERT INTO committees (kgrnr, name) VALUES (22, 'Rat')")
        conn.execute("INSERT INTO committees (kgrnr, name) VALUES (35, 'Verkehrsausschuss')")
        conn.execute(
            "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, location, fetched_at) "
            "VALUES (2852, 'Rat', '2026-06-01', '16:00', 'Rathaus', '2026-06-02')")
        conn.execute(
            "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, location, fetched_at) "
            "VALUES (2853, 'Verkehrsausschuss', '2019-01-15', '17:00', 'Rathaus', '2019-01-16')")
        conn.execute(
            "INSERT INTO council_decisions (ksinr, position, kind, item_number, title, official_text, "
            "  outcome, raw_result, template_number, kvonr) "
            "VALUES (2852, 5, 'decision', '5', 'Kommunale Wärmeplanung', "
            "        'Der Wärmeplan wird beschlossen.', 'accepted', 'einstimmig beschlossen', '26/0396', 4711)")
        conn.execute(
            "INSERT INTO council_decisions (ksinr, position, kind, item_number, title, outcome, raw_result) "
            "VALUES (2852, 6, 'decision', '6', 'Bericht zur Lage', 'noted', 'zur Kenntnis genommen')")
        # Teilabstimmungen zählen nicht als eigener Tagesordnungspunkt.
        conn.execute(
            "INSERT INTO council_decisions (ksinr, position, kind, parent_item, item_number, title, outcome) "
            "VALUES (2852, 5, 'subvote', '5', '5.1', 'Änderungsantrag der SPD', 'rejected')")
        conn.execute(
            "INSERT INTO council_templates (kvonr, template_number, title, kind, document_id, "
            "  document_url, raw_text, n_pages, fetched_at, status) "
            "VALUES (4711, '26/0396', 'Kommunale Wärmeplanung', 'Beschlussvorlage', 180907, "
            "        'https://buergerinfo.oldenburg.de/getfile.php?id=180907&type=do', "
            "        'Sachverhalt: Die Stadt stellt einen Wärmeplan auf.', 12, '2026-05-01', 'ok')")
        conn.execute(
            "INSERT INTO council_deliberations (kvonr, date, committee, top, is_public, result, ksinr, fetched_at) "
            "VALUES (4711, '2026-06-01', 'Rat', '5', 1, 'Entscheidung', 2852, '2026-06-02')")
        conn.execute(
            "INSERT INTO council_attachments (document_id, kvonr, label, url, is_motion, applicants, "
            "  raw_text, n_pages, fetched_at, status) "
            "VALUES (183885, 4711, 'Antrag der SPD-Fraktion vom 10.03.2026', "
            "        'https://buergerinfo.oldenburg.de/getfile.php?id=183885&type=do', 1, "
            "        '[\"SPD\"]', 'Der Rat möge beschließen …', 2, '2026-05-01', 'ok')")
    store.close()
    monkeypatch.setenv("COUNCIL_DB", str(pfad))
    return pfad


@pytest.fixture()
def geerntet(tmp_path, rats_db):
    """Der Adapter hat gelaufen; die Rohablage ist gefüllt."""
    raw = CitiesStore(tmp_path / "raw.sqlite")
    client = OParlClient(raw, "oldenburg", tmp_path / "files")
    adapter = OldenburgAdapter()
    body = adapter.discover(client, BODIES["oldenburg"])["body"]
    list(adapter.iter_organizations(client, body))
    list(adapter.iter_meetings(client, body, "2020-01-01"))
    list(adapter.iter_papers(client, body, "2020-01-01"))
    yield raw, adapter
    raw.close()


def test_adapter_braucht_kein_netz(geerntet):
    raw, _ = geerntet
    assert raw.raw_count("oldenburg", "paper") == 2       # Vorlage + Antrag
    assert raw.raw_count("oldenburg", "meeting") == 1     # nur die im Fenster


def test_kennungen_sind_sprechend_und_stabil():
    assert paper_id(4711) == "oldenburg:paper:4711"
    assert motion_id(183885) == "oldenburg:paper:att:183885"
    assert meeting_id(2852) == "oldenburg:meeting:2852"
    assert agenda_id(2852, "5") == "oldenburg:agenda:2852:5"
    assert faction_id("Bündnis 90/Die Grünen") == "oldenburg:faction:b-ndnis-90-die-gr-nen"


def test_normalisiert_zu_papieren_sitzungen_und_ergebnis(geerntet):
    raw, adapter = geerntet
    batch = adapter.normalize("oldenburg", raw)

    vorlage = next(p for p in batch.papers if p.id == paper_id(4711))
    assert vorlage.reference == "26/0396"
    assert vorlage.kind is PaperKind.PROPOSAL
    assert vorlage.date == "2026-06-01"
    assert vorlage.web.endswith("__kvonr=4711")

    # Der Antrag hängt in Oldenburg als ANLAGE an der Vorlage — es gibt keine
    # Vorlagenart „Antrag". Er bekommt trotzdem ein eigenes Papier, weil er
    # der interessanteste Teil des Bestands ist.
    antrag = next(p for p in batch.papers if p.id == motion_id(183885))
    assert antrag.kind is PaperKind.MOTION
    assert antrag.originator_org_id == faction_id("SPD")

    punkt = next(a for a in batch.agenda_items if a.id == agenda_id(2852, "5"))
    assert punkt.outcome is Outcome.ACCEPTED
    assert punkt.resolution_text == "Der Wärmeplan wird beschlossen."
    assert punkt.result_raw == "einstimmig beschlossen"


def test_teilabstimmungen_sind_keine_eigenen_punkte(geerntet):
    raw, adapter = geerntet
    batch = adapter.normalize("oldenburg", raw)
    assert len(batch.agenda_items) == 2
    assert not [a for a in batch.agenda_items if "Änderungsantrag" in a.name]


def test_das_kanonische_ergebnis_wird_nicht_neu_geraten(geerntet):
    """Oldenburgs ``outcome`` steht schon fest — aus dem Protokoll, per LLM.

    Den Freitext daneben noch einmal zu deuten wäre ein Rückschritt: Der
    Rohwert „zur Kenntnis genommen" träfe zwar auch, aber ein Wert wie
    „- Der Bericht wird zur Kenntnis genommen -" nicht mehr zuverlässig.
    """
    raw, adapter = geerntet
    batch = adapter.normalize("oldenburg", raw)
    punkt = next(a for a in batch.agenda_items if a.id == agenda_id(2852, "6"))
    assert punkt.outcome is Outcome.NOTED


def test_der_text_wandert_mit_statt_neu_geholt_zu_werden(geerntet):
    raw, adapter = geerntet
    texte = dict(adapter.inline_texts(raw, "oldenburg"))
    assert texte["oldenburg:file:180907"].startswith("Sachverhalt:")
    assert texte["oldenburg:file:183885"].startswith("Der Rat möge")


def test_dateien_zeigen_auf_das_ratsinformationssystem(geerntet):
    raw, adapter = geerntet
    batch = adapter.normalize("oldenburg", raw)
    haupt = [f for f in batch.files if f.role == FileRole.MAIN]
    assert len(haupt) == 2
    for f in haupt:
        assert f.access_url.startswith("https://buergerinfo.oldenburg.de/getfile.php")


def test_oldenburg_holt_keine_pdfs(geerntet):
    """Der Text liegt vor; dieselben Dateien noch einmal zu ziehen, belastet
    nur das eigene Ratsinformationssystem (gemessen: 706 Abrufe, zwölf Minuten)."""
    assert BODIES["oldenburg"].fetch_files is False


def test_gremien_und_fraktionen_werden_getrennt(geerntet):
    raw, adapter = geerntet
    batch = adapter.normalize("oldenburg", raw)
    nach_art = {}
    for o in batch.organizations:
        nach_art.setdefault(str(o.kind), []).append(o.name)
    assert "Rat" in nach_art["council"]
    assert "Verkehrsausschuss" in nach_art["committee"]
    assert "SPD-Fraktion" in nach_art["faction"]


def test_zweiter_lauf_aendert_nichts(tmp_path, rats_db):
    raw = CitiesStore(tmp_path / "raw2.sqlite")
    try:
        client = OParlClient(raw, "oldenburg", tmp_path / "files")
        adapter = OldenburgAdapter()
        body = adapter.discover(client, BODIES["oldenburg"])["body"]
        for _ in range(2):
            list(adapter.iter_organizations(client, body))
            list(adapter.iter_meetings(client, body, "2020-01-01"))
            list(adapter.iter_papers(client, body, "2020-01-01"))
        assert raw.raw_count("oldenburg", "paper") == 2
        assert client.requests_made == 0, "der Adapter spricht kein Netz an"
    finally:
        raw.close()
