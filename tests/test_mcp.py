"""Der MCP-Server (``/api/mcp``) und seine Schlüssel.

Was hier festgehalten wird, ist vor allem die **Tür**: Ohne Schalter gibt es
den Server nicht, ohne das Recht ``mcp`` keinen Schlüssel, und ein Schlüssel
gilt nur, solange das Konto aktiv ist und das Recht trägt. Das
Sitzungs-Cookie allein öffnet den Server nie — sonst könnte jede fremde Seite
im Namen der angemeldeten Person Anfragen stellen.

Dazu die zweite Grenze: Die Werkzeuge lesen öffentliche Ratsdaten, keinen
Haushalt und nichts, was an einem Konto hängt.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import mcp as mcp_router  # noqa: E402
from council import mcp_tools  # noqa: E402
from council.scraper import AgendaItem, CouncilSession  # noqa: E402
from council.store import COUNCIL_USER_OWNED_TABLES, CouncilStore  # noqa: E402
from kern.store import USER_OWNED_TABLES, Store  # noqa: E402

RATSLOTSE_DB = os.environ["RATSLOTSE_DB"]
COUNCIL_DB = os.environ["COUNCIL_DB"]
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def frische_dbs(monkeypatch):
    for base in (RATSLOTSE_DB, COUNCIL_DB):
        for suffix in ("", "-wal", "-shm"):
            Path(base + suffix).unlink(missing_ok=True)
    monkeypatch.setenv("FEATURE_FLAGS", "mcp-server")
    mcp_router.zaehler_vergessen()
    yield


@pytest.fixture
def client():
    return TestClient(app)


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


def _schluessel(client, label="Claude Desktop") -> str:
    r = client.post("/api/account/mcp-tokens", json={"label": label})
    assert r.status_code == 201, r.text
    return r.json()["secret"]


def _rpc(token: str | None, methode: str, params: dict | None = None, mid=1, **kw):
    """Eine Anfrage OHNE Cookie — so, wie ein Agent sie schickt."""
    kopf = {"Authorization": f"Bearer {token}"} if token else {}
    nachricht = {"jsonrpc": "2.0", "method": methode, "params": params or {}}
    if mid is not None:
        nachricht["id"] = mid
    return TestClient(app).post("/api/mcp", json=nachricht, headers=kopf, **kw)


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


# ---- Tür --------------------------------------------------------------------

def test_ohne_schalter_gibt_es_den_server_nicht(client, monkeypatch):
    _konto(client)
    token = _schluessel(client)
    monkeypatch.setenv("FEATURE_FLAGS", "")
    assert _rpc(token, "ping").status_code == 404
    assert client.get("/api/account/mcp-tokens").status_code == 404
    assert client.post("/api/account/mcp-tokens", json={"label": "x"}).status_code == 404


def test_ohne_rolle_kein_schluessel(client):
    _konto(client, rollen=())
    assert client.get("/api/account/mcp-tokens").status_code == 403
    assert client.post("/api/account/mcp-tokens", json={"label": "x"}).status_code == 403


def test_schluessel_ausstellen_auflisten_zurueckziehen(client):
    _konto(client)
    r = client.post("/api/account/mcp-tokens", json={"label": "Claude Desktop"})
    assert r.status_code == 201
    neu = r.json()
    assert neu["secret"].startswith("rlmcp_") and len(neu["secret"]) > 40
    assert neu["endpoint"].endswith("/api/mcp")
    assert neu["secret"].startswith(neu["token"]["prefix"])

    liste = client.get("/api/account/mcp-tokens").json()
    assert [t["label"] for t in liste["tokens"]] == ["Claude Desktop"]
    # Das Geheimnis steht nirgends mehr — weder in der Liste noch in der Datenbank.
    assert neu["secret"] not in str(liste)
    store = Store(RATSLOTSE_DB)
    try:
        assert neu["secret"] not in str([tuple(z) for z in store._conn.execute(
            "SELECT * FROM mcp_tokens")])
    finally:
        store.close()

    assert _rpc(neu["secret"], "ping").json() == {"jsonrpc": "2.0", "id": 1, "result": {}}
    assert client.delete(f"/api/account/mcp-tokens/{neu['token']['id']}").json() == {"ok": True}
    assert _rpc(neu["secret"], "ping").status_code == 401
    assert client.delete(f"/api/account/mcp-tokens/{neu['token']['id']}").status_code == 404


def test_hoechstens_fuenf_schluessel(client):
    _konto(client)
    for i in range(Store.MCP_TOKENS_MAX):
        _schluessel(client, f"Agent {i}")
    assert client.post("/api/account/mcp-tokens", json={"label": "zu viel"}).status_code == 409


def test_fremder_schluessel_ist_nicht_loeschbar(client):
    _konto(client, "eins@example.org")
    tid = client.post("/api/account/mcp-tokens", json={"label": "a"}).json()["token"]["id"]
    zwei = TestClient(app)
    _konto(zwei, "zwei@example.org")
    assert zwei.delete(f"/api/account/mcp-tokens/{tid}").status_code == 404


def test_ohne_gueltigen_schluessel_401(client):
    r = _rpc(None, "ping")
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"].startswith("Bearer")
    assert _rpc("rlmcp_erfunden", "ping").status_code == 401
    assert _rpc("kein-praefix", "ping").status_code == 401


def test_sitzungs_cookie_oeffnet_den_server_nicht(client):
    """Angemeldet im Browser, aber ohne Schlüssel: kein Zugang."""
    _konto(client)
    r = client.post("/api/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert r.status_code == 401


def test_rolle_entzogen_schluessel_gilt_nicht_mehr(client):
    uid = _konto(client)
    token = _schluessel(client)
    store = Store(RATSLOTSE_DB)
    try:
        store.set_web_user_roles(uid, [])
    finally:
        store.close()
    r = _rpc(token, "ping")
    assert r.status_code == 403
    assert "MCP-Zugang" in r.json()["detail"]


def test_admin_darf_ohne_eigene_rolle(client):
    """Admin erbt jedes Recht (``kern/roles.py``) — auch dieses."""
    _konto(client, rollen=("admin",))
    assert _rpc(_schluessel(client), "ping").status_code == 200


def test_konto_loeschen_nimmt_die_schluessel_mit():
    assert ("mcp_tokens", "owner_id") in USER_OWNED_TABLES


# ---- Protokoll --------------------------------------------------------------

def test_initialize_handelt_die_fassung_aus(client):
    _konto(client)
    token = _schluessel(client)
    r = _rpc(token, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                   "clientInfo": {"name": "test", "version": "0"}}).json()
    assert r["result"]["protocolVersion"] == "2025-06-18"
    assert r["result"]["capabilities"] == {"tools": {"listChanged": False}}
    assert r["result"]["serverInfo"]["name"] == "ratslotse"
    # Unbekannte Fassung: die neueste, der Client entscheidet.
    r = _rpc(token, "initialize", {"protocolVersion": "1999-01-01"}).json()
    assert r["result"]["protocolVersion"] == mcp_router.PROTOKOLLE[0]


def test_benachrichtigung_bekommt_202_ohne_koerper(client):
    _konto(client)
    r = _rpc(_schluessel(client), "notifications/initialized", mid=None)
    assert r.status_code == 202
    assert r.content == b""


def test_get_ist_nicht_erlaubt(client):
    """Kein Server-gesendeter Strom — die Spezifikation verlangt dann 405."""
    assert TestClient(app).get("/api/mcp").status_code == 405


def test_unbekannte_methode_und_werkzeug(client):
    _konto(client)
    token = _schluessel(client)
    assert _rpc(token, "resources/list").json()["error"]["code"] == -32601
    r = _rpc(token, "tools/call", {"name": "haushalt_nachschlagen", "arguments": {}}).json()
    assert r["error"]["code"] == -32602


def test_werkzeuge_lesen_beschluesse(client):
    _konto(client)
    token = _schluessel(client)
    did = _beschluss()
    werkzeuge = _rpc(token, "tools/list").json()["result"]["tools"]
    assert {w["name"] for w in werkzeuge} == set(mcp_tools.TOOLS)
    assert all(w["annotations"]["readOnlyHint"] for w in werkzeuge)

    r = _rpc(token, "tools/call", {"name": "get_decision",
                                   "arguments": {"decision_id": did}}).json()["result"]
    assert r["isError"] is False
    text = r["content"][0]["text"]
    assert "Radweg Ammerländer Heerstraße" in text
    assert f"/council/decision?id={did}" in text

    r = _rpc(token, "tools/call", {"name": "search_decisions",
                                   "arguments": {"committee": "Rat"}}).json()["result"]
    assert "Radweg" in r["content"][0]["text"]

    # Ein Fehler, den der Agent korrigieren kann, steht IM Ergebnis.
    r = _rpc(token, "tools/call", {"name": "get_decision",
                                   "arguments": {"decision_id": 999999}}).json()["result"]
    assert r["isError"] is True


def test_aufrufe_werden_gezaehlt(client):
    _konto(client)
    token = _schluessel(client)
    _rpc(token, "ping")
    zeile = client.get("/api/account/mcp-tokens").json()["tokens"][0]
    assert zeile["calls"] == 1 and zeile["last_used"]


# ---- Grenzen der Werkzeuge ---------------------------------------------------

def test_kein_haushalt_und_nichts_kontogebundenes():
    """Die Werkzeuge fassen weder den Haushalt noch eine Tabelle an, die an
    einem Konto hängt. Geprüft am Quelltext des Werkzeug-Moduls UND der von
    ihm benutzten Lotti-Werkzeuge — eine neue Abfrage auf ``bookmarks`` oder
    ``council_budget`` soll hier auffallen, nicht erst in einem Agenten."""
    from council import lotti_werkzeuge as lw

    quellen = (ROOT / "council" / "mcp_tools.py").read_text()
    benutzt = set(re.findall(r"lw\.(\w+)\(", quellen))
    assert benutzt <= {"sitzungen", "tagesordnung", "beratungsfolge", "beschluesse_zaehlen"}, (
        "council/mcp_tools.py benutzt ein weiteres Lotti-Werkzeug. Ist es frei von Haushalt "
        "und Kontodaten? Dann hier aufnehmen.")
    import inspect
    text = quellen + "".join(inspect.getsource(getattr(lw, n)) for n in benutzt)
    verboten = {t for t, _ in USER_OWNED_TABLES} | {t for t, _ in COUNCIL_USER_OWNED_TABLES}
    treffer = sorted(t for t in verboten if re.search(rf"\b{t}\b", text))
    assert not treffer, f"Die MCP-Werkzeuge lesen kontogebundene Tabellen: {treffer}"
    assert not re.search(r"\bcouncil_(budget|debt|taxes|liquidity|staff_plan)\b", text)
    assert not any("haushalt" in n or "budget" in n for n in mcp_tools.TOOLS)
