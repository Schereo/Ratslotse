"""Auswertung des MCP-Servers: Was wird je Werkzeugaufruf vermerkt, und was
zeigt das Admin-Panel daraus?

Festgehalten wird vor allem, was NICHT hineingeht: Kontaktdaten im
Suchtext, Werte anderer Argumente, ein Suchtext älter als 90 Tage — und dass
die Zeilen mit dem Konto gehen.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import mcp as mcp_router  # noqa: E402
from council.scraper import AgendaItem, CouncilSession  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from kern.store import USER_OWNED_TABLES, Store  # noqa: E402

RATSLOTSE_DB = os.environ["RATSLOTSE_DB"]
COUNCIL_DB = os.environ["COUNCIL_DB"]


@pytest.fixture(autouse=True)
def frische_dbs(monkeypatch):
    for base in (RATSLOTSE_DB, COUNCIL_DB):
        for suffix in ("", "-wal", "-shm"):
            Path(base + suffix).unlink(missing_ok=True)
    monkeypatch.setenv("FEATURE_FLAGS", "mcp-server")
    mcp_router.zaehler_vergessen()
    yield
    mcp_router.zaehler_vergessen()


def _konto(client, email="agentin@example.org", rollen=("mcp_access",)) -> int:
    r = client.post("/api/auth/register", json={"display_name": "Agentin", "email": email,
                                                 "password": "password123"})
    assert r.status_code == 201, r.text
    store = Store(RATSLOTSE_DB)
    try:
        uid = store.get_web_user_by_email(email)["id"]
        store.set_web_user_roles(uid, list(rollen))
    finally:
        store.close()
    client.post("/api/auth/login", json={"email": email, "password": "password123"})
    return uid


def _schluessel(client, label="ChatGPT") -> str:
    return client.post("/api/account/mcp-tokens", json={"label": label}).json()["secret"]


def _werkzeug(token: str, name: str, arguments: dict):
    r = TestClient(app).post("/api/mcp", headers={"Authorization": f"Bearer {token}"}, json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": name, "arguments": arguments}})
    assert r.status_code == 200, r.text
    return r.json()["result"]


def _beschluss() -> int:
    cs = CouncilStore(COUNCIL_DB)
    cs.save_session(CouncilSession(4711, "Rat", "2026-06-29", "18:00", "PFL",
                                   agenda_items=[AgendaItem("Ö 5", "Radweg Ammerländer Heerstraße")]))
    cs._insert_decision(4711, 0, "decision", None, "Ö 5", "Radweg Ammerländer Heerstraße",
                        "Der Rat beschließt den Ausbau.", "accepted", None, None, None,
                        ["SPD"], "26/0101", None, None)
    cs._conn.commit()
    did = cs._conn.execute("SELECT id FROM council_decisions WHERE ksinr = 4711").fetchone()[0]
    cs.close()
    return did


def _zeilen() -> list[dict]:
    mcp_router.aufrufe_schreiben()
    store = Store(RATSLOTSE_DB)
    try:
        return [dict(r) for r in store._conn.execute("SELECT * FROM mcp_calls ORDER BY id")]
    finally:
        store.close()


def test_ein_aufruf_wird_vermerkt():
    c = TestClient(app)
    uid = _konto(c)
    token = _schluessel(c)
    _beschluss()
    _werkzeug(token, "search_decisions",
              {"query": "Radweg  Ammerländer  ruf an: 0441 235-1234", "committee": "Rat",
               "outcome": None})
    [z] = _zeilen()
    assert z["owner_id"] == uid and z["client"] == "ChatGPT" and z["tool"] == "search_decisions"
    assert z["source"].startswith("key:") and z["outcome"] == "ok"
    # Nur die NAMEN gesetzter Argumente, nie ihre Werte (außer dem Suchtext).
    assert json.loads(z["args"]) == ["committee", "query"]
    # Der Suchtext: Kontaktdaten maskiert, Leerraum zusammengezogen.
    assert "235-1234" not in z["query"] and "0441" not in z["query"]
    assert z["query"].startswith("Radweg Ammerländer")
    assert z["result_count"] == 0  # die Volltextsuche findet im Test nichts


def test_fehler_und_treffer():
    c = TestClient(app)
    _konto(c)
    token = _schluessel(c)
    did = _beschluss()
    _werkzeug(token, "get_decision", {"decision_id": 999999})
    _werkzeug(token, "get_decision", {"decision_id": did})
    _werkzeug(token, "search_decisions", {"committee": "Rat"})
    a, b, s = _zeilen()
    assert a["outcome"] == "tool_error" and a["result_count"] is None
    assert b["outcome"] == "ok" and b["query"] is None
    assert s["result_count"] == 1


def test_ohne_werkzeug_kein_vermerk():
    c = TestClient(app)
    _konto(c)
    token = _schluessel(c)
    for methode in ("initialize", "tools/list", "ping"):
        TestClient(app).post("/api/mcp", headers={"Authorization": f"Bearer {token}"},
                             json={"jsonrpc": "2.0", "id": 1, "method": methode, "params": {}})
    assert _zeilen() == []


def test_schreibsperre_verliert_nichts(monkeypatch):
    c = TestClient(app)
    _konto(c)
    token = _schluessel(c)
    monkeypatch.setattr(Store, "record_mcp_calls", lambda self, zeilen: False)
    _werkzeug(token, "list_committees", {})
    mcp_router.aufrufe_schreiben()
    assert len(mcp_router._puffer) == 1
    monkeypatch.undo()
    monkeypatch.setenv("FEATURE_FLAGS", "mcp-server")
    assert len(_zeilen()) == 1


def test_auswertung_im_admin_panel():
    c = TestClient(app)
    _konto(c)
    token = _schluessel(c, "Claude Desktop")
    did = _beschluss()
    _werkzeug(token, "search_decisions", {"query": "Radweg"})
    _werkzeug(token, "search_decisions", {"committee": "Rat"})
    _werkzeug(token, "get_decision", {"decision_id": did})
    _zeilen()

    assert c.get("/api/admin/stats/mcp").status_code == 403

    admin = TestClient(app)
    _konto(admin, email="chef@example.org", rollen=("admin",))
    d = admin.get("/api/admin/stats/mcp?days=30").json()
    assert d["calls"] == 3 and d["accounts"] == 1 and d["sessions"] == 1
    assert d["searches"] == 2 and d["empty_searches"] == 1
    assert d["clients"] == [{"key": "Claude Desktop", "n": 3}]
    assert {"key": "search_decisions → get_decision", "n": 1} in d["transitions"]
    assert d["entries"] == [{"key": "search_decisions", "n": 1}]
    assert d["queries"] == [{"query": "Radweg", "n": 1, "empty": 1}]
    assert d["empty_queries"][0]["query"] == "Radweg"
    assert d["accounts_list"][0]["email"] == "agentin@example.org"
    tools = {t["key"]: t for t in d["tools"]}
    assert tools["search_decisions"]["empty"] == 1


def test_pause_trennt_sitzungen():
    store = Store(RATSLOTSE_DB)
    try:
        jetzt = datetime.now(UTC)
        zeilen = []
        for minuten, tool in ((0, "search_decisions"), (5, "get_decision"),
                              (120, "list_committees")):
            zeilen.append({"ts": (jetzt - timedelta(minutes=200 - minuten)).isoformat(timespec="seconds"),
                           "owner_id": 1, "source": "oauth:1", "client": "ChatGPT", "tool": tool,
                           "outcome": "ok", "duration_ms": 10, "args": "[]", "query": None,
                           "result_count": None})
        assert store.record_mcp_calls(zeilen)
        d = store.mcp_auswertung(30)
        assert d["sessions"] == 2
        assert [t["key"] for t in d["transitions"]] == ["search_decisions → get_decision"]
    finally:
        store.close()


def test_suchtext_nach_90_tagen_weg_zeile_nach_einem_jahr():
    store = Store(RATSLOTSE_DB)
    try:
        jetzt = datetime.now(UTC)

        def zeile(tage: int) -> dict:
            return {"ts": (jetzt - timedelta(days=tage)).isoformat(timespec="seconds"),
                    "owner_id": 1, "source": "key:1", "client": "x", "tool": "search_decisions",
                    "outcome": "ok", "duration_ms": 1, "args": "[]", "query": f"vor {tage}",
                    "result_count": 0}
        store.record_mcp_calls([zeile(10), zeile(100), zeile(400)])
        store.purge_mcp_calls()
        rest = [tuple(r) for r in store._conn.execute(
            "SELECT query FROM mcp_calls ORDER BY ts DESC")]
        assert rest == [("vor 10",), (None,)]
    finally:
        store.close()


def test_aufrufe_gehen_mit_dem_konto():
    assert ("mcp_calls", "owner_id") in USER_OWNED_TABLES


@pytest.mark.parametrize("roh, erwartet", [
    ("ruf an: 0441 235-1234", "ruf an: [Kontaktdaten entfernt]"),
    ("+49 441 2351234", "[Kontaktdaten entfernt]"),
    ("schreib an max@example.org", "schreib an [Kontaktdaten entfernt]"),
    # Was in Ratsdaten Zahlen sind, bleibt stehen.
    ("Vorlage 24/0089", "Vorlage 24/0089"),
    ("Drucksache 26/0101 vom 12.03.2024", "Drucksache 26/0101 vom 12.03.2024"),
    ("Haushalt  2024\nFliegerhorst", "Haushalt 2024 Fliegerhorst"),
])
def test_suchtext(roh, erwartet):
    assert mcp_router._suchtext(roh) == erwartet


def test_suchtext_wird_gekuerzt():
    assert len(mcp_router._suchtext("Radweg " * 100)) == mcp_router.QUERY_LAENGE
