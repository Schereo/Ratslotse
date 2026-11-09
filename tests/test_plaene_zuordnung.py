"""Pläne der Stadt, Phase 1: Tagesordnungspunkte ihren Plänen zuordnen.

Festgehalten wird die Regel, nicht eine Messung am Bestand. Die Messziele aus
dem Plan (Aktionsplan Gewalt: alle 24 Tagesordnungspunkte 2018–2026,
Klimaschutzplan: alle 15 Berichte) prüft der Messtest am Ende gegen den
lokalen Abzug.

Die wichtigsten Fälle:

- **Ketten teilen ein Muster** — ein Bericht gehört dem Glied, das zu seinem
  Datum galt; die Vorlage im Register schlägt das Datum.
- **„Zur Kenntnis“ bleibt Kenntnis**, und ein Plan ohne Bericht sagt das,
  statt leer zu bleiben.
- **Leer ist kein Fehler**: Ohne zugeordnete Zeilen antworten beide Endpunkte
  mit 200 (in der CI ist die Ratsdatenbank leer).
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from council import plan_pages, plan_tracking, plans
from council.plan_tracking import AgendaRow
from council.store import CouncilStore
from web.backend.app.deps import get_council_store, get_current_user
from web.backend.app.main import app


def _row(i: int, date: str, title: str, template: str | None = None, *, committee: str = "Rat",
         kind: str | None = None, decision_id: int | None = None) -> AgendaRow:
    return AgendaRow(agenda_item_id=i, ksinr=100 + i, item_number=f"Ö {i}", date=date,
                     committee=committee, title=title, template_number=template, kvonr=None,
                     template_kind=kind, decision_id=decision_id, outcome=None)


def _rollen(items: list[dict], key: str) -> dict[int, str]:
    return {i["agenda_item_id"]: i["role"] for i in items if i["plan_key"] == key}


# ── Rollen ────────────────────────────────────────────────────────────────

def test_rollen_eines_plans():
    rows = [
        _row(1, "2022-02-10", "Klimaschutz-Aktivitäten 1/2022 - Bericht Beschluss: zur Kenntnis genommen",
             "22/0037", kind="Berichtsvorlage (bis 31.12.2022)"),
        _row(2, "2022-12-19", "Klimaschutzplan Oldenburg 2035 - Beschluss", "22/0910"),
        _row(3, "2021-04-26", "Klimaziel für Oldenburg - Beschluss", "21/0249/2"),
        _row(4, "2026-10-08", "Klimaschutz-Aktivitäten 3/2026 - Bericht", "26/0750", kind="Berichtsvorlage"),
    ]
    rollen = _rollen(plan_tracking.build_items(rows), "klimaschutzplan_2035")
    assert rollen == {1: "preparation", 2: "adoption", 3: "amendment", 4: "report"}


def test_antrag_einer_fraktion_ist_kein_bericht():
    rows = [_row(1, "2018-01-30", 'Aktionsplan "gegen Gewalt an Frauen" (Fraktionen im Rat vom 15.01.2018)'),
            _row(2, "2020-09-10", "Umsetzung einer kommunalen Ernährungsstrategie für Oldenburg; "
                                  "Bündnis 90/Die Grünen, 27.08.2020")]
    items = plan_tracking.build_items(rows)
    assert _rollen(items, "aktionsplan_gewalt_2020") == {1: "motion"}
    assert _rollen(items, "ernaehrungsstrategie") == {2: "motion"}


def test_bericht_der_verwaltung_auf_einen_antrag_bleibt_bericht():
    rows = [_row(1, "2021-02-23", 'Sachstandsbericht zum "Gesamtkonzept niedrigschwellige Wohnungslosen- '
                                  'und Suchthilfe in Oldenburg" (Bündnis 90/Die Grünen vom 01.02.2021)',
                 "21/0121", kind="Berichtsvorlage (bis 31.12.2022)")]
    assert _rollen(plan_tracking.build_items(rows), "wohnungslosen_suchthilfe") == {1: "report"}


def test_muendlicher_bericht_ohne_vorlage():
    rows = [_row(1, "2023-10-10", "Umsetzungsstand Kommunaler Aktionsplan Gewalt gegen Frauen - "
                                  "mündlicher Bericht Beschluss: zur Kenntnis genommen")]
    (item,) = plan_tracking.build_items(rows)
    assert item["role"] == "report" and item["oral"] == 1
    assert item["title"].endswith("mündlicher Bericht"), "das Ergebnis gehört nicht in den Titel"


def test_umsetzungsreihe():
    rows = [_row(1, "2024-08-21", "Maßnahmenplanung für den weiteren Ausbau der Kindertagesbetreuung – "
                                  "Kindertagesstätte Deelweg - Beschluss", "24/0064")]
    assert _rollen(plan_tracking.build_items(rows), "kita_ausbau") == {1: "implementation"}


def test_ausschluss_muster():
    rows = [_row(1, "2018-02-28", "Lärmaktionsplanung des Eisenbahn-Bundesamtes - Bericht", "18/0114")]
    assert not _rollen(plan_tracking.build_items(rows), "laermaktionsplan")


# ── Ketten ────────────────────────────────────────────────────────────────

def test_kette_bericht_gehoert_dem_glied_seiner_zeit():
    rows = [
        _row(1, "2022-09-13", "Zwischenbericht zur Umsetzung des Kommunalen Aktionsplans gegen Gewalt",
             "22/0494", kind="Berichtsvorlage"),
        _row(2, "2026-09-28", "Evaluation und Fortschreibung des kommunalen Aktionsplans gegen Gewalt "
                              "an Frauen* und Häusliche Gewalt - Beschluss", "26/0681/1"),
        _row(3, "2027-03-01", "Umsetzungsstand Aktionsplan gegen Gewalt - mündlicher Bericht"),
    ]
    items = plan_tracking.build_items(rows)
    alt, neu = _rollen(items, "aktionsplan_gewalt_2020"), _rollen(items, "aktionsplan_gewalt_2026")
    assert alt == {1: "report", 2: "evaluation"}
    assert neu == {2: "adoption", 3: "report"}


def test_kette_die_vorlage_schlaegt_das_datum():
    # Der alte Gleichstellungsplan wird im neuen ausgewertet: Die Vorlage 21/0399
    # ist für 2018 die Auswertung, für 2021 der Plan — nicht „Bericht von 2021“.
    rows = [_row(1, "2021-06-28", "Gleichstellungsplan -Bericht-", "21/0399")]
    items = plan_tracking.build_items(rows)
    assert _rollen(items, "gleichstellungsplan_2018") == {1: "evaluation"}
    assert _rollen(items, "gleichstellungsplan_2021") == {1: "adoption"}
    assert not _rollen(items, "gleichstellungsplan_2024")


# ── Verweis über die Nummer ───────────────────────────────────────────────

def test_verweis_ueber_die_nummer():
    links = plan_tracking.build_mentions(
        [("26/0311", "… Ziele des Klimaschutzplans (Vorlage 22/0910) …"),
         ("22/0910", "Der Klimaschutzplan 22/0910 selbst"),
         ("26/0400", "Bebauungsplan 220/0910 und 122/09101")],
        {"26/0311": [5, 6], "22/0910": [7], "26/0400": [8]}, items=[])
    assert {(link["plan_key"], link["decision_id"]) for link in links} == {
        ("klimaschutzplan_2035", 5), ("klimaschutzplan_2035", 6)}
    assert plan_tracking.cited_numbers("Vorlage 23/0211/2 und 24/0216") == {"23/0211", "24/0216"}


# ── Seiten ────────────────────────────────────────────────────────────────

def test_status_und_gruppe():
    p = plans.PLANS
    heute = "2026-11-09"
    assert plan_pages.status(p["klimaschutzplan_2035"], heute) == "running"
    assert plan_pages.status(p["klimaanpassungskonzept"], heute) == "preparing"
    assert plan_pages.status(p["aktionsplan_gewalt_2020"], heute) == "superseded"
    assert plan_pages.status(p["schulentwicklungsplan_2018"], heute) == "concluded"
    assert plan_pages.status(p["inklusion_stadt_fuer_alle"], heute) == "expired"
    assert plan_pages.status(p["gleichstellungsplan_2024"], heute) == "running"
    assert plan_pages.status(p["gleichstellungsplan_2024"], "2027-01-01") == "expired"


def test_kicker_sagt_kenntnis_statt_beschluss():
    assert plan_pages.kicker(plans.PLANS["demografiestrategie"], []) == "Soziales · zur Kenntnis 09/2020"
    assert plan_pages.kicker(plans.PLANS["klimaschutzplan_2035"], []) == (
        "Klima & Umwelt · beschlossen 12/2022 · bis 2035")


def test_der_satz_wenn_der_bestand_schweigt():
    p = plans.PLANS
    assert plan_pages.report_note(p["masterplan_stadtgruen"], None, "running", "2026-11-09") == (
        "Kein Umsetzungsbericht im Rat seit dem Beschluss.")
    assert plan_pages.report_note(p["waermeplan"], None, "running", "2026-11-09") == (
        "Seit dem Beschluss 06/2026 noch kein Bericht im Rat.")
    alt = {"date": "2022-03-21"}
    assert plan_pages.report_note(p["rad_fussverkehrsprogramm"], alt, "running", "2026-11-09") == (
        "Seit 03/2022 kein Bericht im Rat.")
    assert plan_pages.report_note(p["aktionsplan_gewalt_2020"], None, "superseded", "2026-11-09") is None


# ── Endpunkte ─────────────────────────────────────────────────────────────

@pytest.fixture()
def rats_db(tmp_path):
    store = CouncilStore(tmp_path / "council.sqlite")
    with store._conn:
        store._conn.executemany(
            "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, location, fetched_at) "
            "VALUES (?, ?, ?, '16:00', 'PFL', '2026-01-01')",
            [(1, "Rat", "2022-12-19"), (2, "Ausschuss für Stadtgrün, Umwelt und Klima", "2026-10-08")])
        store._conn.execute(
            "INSERT INTO council_templates (kvonr, template_number, title, kind, fetched_at, status, "
            "attachments_scanned, raw_text) VALUES (10, '22/0910', 'Klimaschutzplan Oldenburg 2035 - Beschluss', "
            "'Beschlussvorlage', '2026-01-01', 'ok', 0, '')")
        store._conn.executemany(
            "INSERT INTO council_agenda_items (id, ksinr, item_number, title, template_number, kvonr, is_public) "
            "VALUES (?, ?, ?, ?, ?, ?, 1)",
            [(1, 1, "Ö 5", "Klimaschutzplan Oldenburg 2035 - Beschluss Beschluss: ungeändert beschlossen",
              "22/0910", 10),
             (2, 2, "Ö 7", "Klimaschutz-Aktivitäten 3/2026 - Bericht", "26/0750", None)])
        store._conn.execute(
            "INSERT INTO council_decisions (id, ksinr, position, kind, item_number, title, outcome, "
            "template_number, kvonr) VALUES (55, 1, 1, 'decision', '5', 'Klimaschutzplan Oldenburg 2035', "
            "'accepted', '22/0910', 10)")
    yield store
    store.close()


@pytest.fixture()
def client(rats_db):
    app.dependency_overrides[get_council_store] = lambda: rats_db
    app.dependency_overrides[get_current_user] = lambda: {"id": 7, "status": "active"}
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_leer_ist_kein_fehler(client):
    r = client.get("/api/council/plans")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == sum(len(g["plans"]) for g in body["groups"])
    assert [g["key"] for g in body["groups"]] == ["running", "preparing", "ended"]
    assert client.get("/api/council/plan/klimaschutzplan_2035").status_code == 200


def test_uebersicht_und_detail_nach_dem_aufbau(client, rats_db):
    plan_tracking.build(rats_db)
    karten = {c["key"]: c for g in client.get("/api/council/plans").json()["groups"] for c in g["plans"]}
    ksp = karten["klimaschutzplan_2035"]
    assert ksp["latest_report"]["template_number"] == "26/0750"
    assert ksp["report_note"] is None
    d = client.get("/api/council/plan/klimaschutzplan_2035").json()
    assert d["adoption"]["decision_id"] == 55 and d["adoption"]["kvonr"] == 10
    assert [s["kind"] for s in d["timeline"]["stations"]] == ["adoption", "report"]
    assert d["decision_groups"][0]["key"] == "plan"
    # Das Zeitband kommt durch den Vertrag (tests/test_plan_time_band.py hält, was es sagt).
    assert [m["kind"] for m in ksp["lane"]["marks"]] == ["adoption", "report"]
    assert [m["station"] for m in d["runway"]["marks"]] == [0, 1]
    assert d["timeline"]["stations"][0]["mode"] == "adopted"
    assert [e["kind"] for e in d["timeline"]["log"]][-1] == "year"


def test_unbekannter_plan_ist_404(client):
    assert client.get("/api/council/plan/gibt_es_nicht").status_code == 404


def test_endpunkte_verlangen_ein_konto(rats_db):
    app.dependency_overrides[get_council_store] = lambda: rats_db
    try:
        c = TestClient(app)
        assert c.get("/api/council/plans").status_code == 401
        assert c.get("/api/council/plan/waermeplan").status_code == 401
    finally:
        app.dependency_overrides.clear()


# ── Messziele gegen den Abzug ─────────────────────────────────────────────

#: EIGENE Variable, nicht COUNCIL_DB (tests/CLAUDE.md).
ECHTE_DB = Path(os.environ.get("RATSLOTSE_MESS_DB")
                or Path(__file__).resolve().parents[1] / "data" / "council.sqlite")


@pytest.mark.skipif(not ECHTE_DB.exists(), reason="kein lokaler Abzug")
def test_messziele_phase_1():
    conn = sqlite3.connect(f"file:{ECHTE_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        if not conn.execute("SELECT COUNT(*) FROM council_agenda_items").fetchone()[0]:
            pytest.skip("Abzug ist leer")
        from council.store_plaene import PlaeneMixin

        class _Leser(PlaeneMixin):
            def __init__(self, c):
                self._conn = c
        rows = [AgendaRow(**r) for r in _Leser(conn).plan_tracking_rows()]
    finally:
        conn.close()
    items = plan_tracking.build_items(rows)
    gewalt = [i for i in items if i["plan_key"] == "aktionsplan_gewalt_2020"]
    assert len(gewalt) == 24, "Plan § 5 Phase 1: alle 24 Tagesordnungspunkte 2018–2026"
    ksp = {i["template_number"] for i in items if i["plan_key"] == "klimaschutzplan_2035"
           and "Klimaschutz-Aktivit" in i["title"]}
    assert len(ksp) == 15, "Plan § 5 Phase 1: alle 15 Berichte „Klimaschutz-Aktivitäten“"


def test_kennung_ordnet_den_beschluss_der_massnahme_zu():
    """Phase 4: Eine Vorlage nennt eine Maßnahme bei ihrer Kennung. Kurze Kennungen („K1“,
    „A12“) zählen nur mit Plannamen und Anrede; Übersichten mit vielen Kennungen zählen nicht."""
    by_stem = {"23/0419": [11, 12], "26/0238": [13], "24/0001": [14], "25/0002": [15], "25/0003": [16]}
    overview = " ".join(f"Maßnahme {c}" for c in ("PV_01", "PV_02", "PV_03", "PV_04", "PV_05", "PV_06"))
    templates = [
        ("23/0419", "Die Richtlinie setzt die Maßnahme pv_05 des Klimaschutzplans um."),  # Schreibweise der Stadt schwankt
        ("26/0238/1", "Der Beirat ist die Wärmeplan-Maßnahme O7; siehe Wärmeplan."),
        ("24/0001", "Der Raum K1 im Rathaus wird saniert."),          # kurze Kennung ohne Plan und Anrede
        ("25/0002", "Im Wärmeplan steht nichts zum Raum K1."),         # Plan genannt, Kennung nicht als Maßnahme
        ("25/0003", overview),                                          # Übersicht, kein Beschluss zu EINER Maßnahme
    ]
    links = plan_tracking.build_measure_links(templates, by_stem, items=[])
    got = sorted((link["plan_key"], link["decision_id"], link["measure_code"]) for link in links)
    assert got == [("klimaschutzplan_2035", 11, "PV_05"), ("klimaschutzplan_2035", 12, "PV_05"),
                   ("waermeplan", 13, "O7")]
    assert {link["relation"] for link in links} == {"names_measure"}
    # Was schon als Bericht zum Plan gehört, wird nicht noch einmal Maßnahmen-Beschluss.
    known = [{"plan_key": "klimaschutzplan_2035", "template_number": "23/0419"}]
    assert not [link for link in plan_tracking.build_measure_links(templates[:1], by_stem, items=known)]
