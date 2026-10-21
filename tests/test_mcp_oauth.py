"""OAuth für den MCP-Server (``routers/mcp_oauth.py``).

Festgehalten wird der ganze Weg, den ChatGPT geht — Metadaten, Registrierung,
Freigabe, Code gegen Token, Werkzeugaufruf, Erneuerung — und vor allem die
Stellen, an denen er scheitern MUSS: fremde Rücksprungadresse, falsches
PKCE, fremde Ressource, Code oder Erneuerungs-Token zum zweiten Mal, Konto
ohne Recht, abgemeldetes Konto, getrennte Verbindung.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import mcp as mcp_router  # noqa: E402
from app.routers import mcp_oauth  # noqa: E402
from council.scraper import AgendaItem, CouncilSession  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from kern.store import USER_OWNED_TABLES, Store  # noqa: E402

RATSLOTSE_DB = os.environ["RATSLOTSE_DB"]
COUNCIL_DB = os.environ["COUNCIL_DB"]

REDIRECT = "https://chatgpt.com/connector/oauth/abc123"
VERIFIER = "v" * 43 + "-erfunden_und_lang_genug"
CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b"=").decode()


@pytest.fixture(autouse=True)
def frische_dbs(monkeypatch):
    for base in (RATSLOTSE_DB, COUNCIL_DB):
        for suffix in ("", "-wal", "-shm"):
            Path(base + suffix).unlink(missing_ok=True)
    monkeypatch.setenv("FEATURE_FLAGS", "mcp-server")
    mcp_router.zaehler_vergessen()
    # Kein Test geht ins Netz: Wer CIMD braucht, setzt den Abruf selbst.
    monkeypatch.setattr(mcp_oauth, "cimd_abrufen", lambda url: "kein Netz im Test")
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


def _registrieren(redirect=REDIRECT, name="ChatGPT") -> str:
    r = TestClient(app).post("/api/oauth/register", json={
        "client_name": name, "redirect_uris": [redirect],
        "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"],
        "token_endpoint_auth_method": "none"})
    assert r.status_code == 201, r.text
    assert r.json()["token_endpoint_auth_method"] == "none"
    return r.json()["client_id"]


def _anfrage(client_id: str, **anders) -> dict:
    p = {"response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT,
         "code_challenge": CHALLENGE, "code_challenge_method": "S256", "state": "zustand-1",
         "scope": "ratsdaten:lesen", "resource": mcp_oauth.resource()}
    p.update(anders)
    return {k: v for k, v in p.items() if v is not None}


def _code(client, client_id: str, **anders) -> str:
    r = client.post("/api/oauth/authorize", json={**_anfrage(client_id, **anders), "approve": True})
    assert r.status_code == 200, r.text
    ziel = urlsplit(r.json()["redirect"])
    assert f"{ziel.scheme}://{ziel.netloc}{ziel.path}" == anders.get("redirect_uri", REDIRECT)
    q = parse_qs(ziel.query)
    assert q["state"] == ["zustand-1"]
    assert q["iss"] == [mcp_oauth.issuer()]
    return q["code"][0]


def _tauschen(code: str, client_id: str, verifier: str = VERIFIER, **anders):
    daten = {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT,
             "client_id": client_id, "code_verifier": verifier,
             "resource": mcp_oauth.resource()}
    daten.update(anders)
    return TestClient(app).post("/api/oauth/token", data={k: v for k, v in daten.items()
                                                          if v is not None})


def _erneuern(refresh: str, client_id: str):
    return TestClient(app).post("/api/oauth/token", data={
        "grant_type": "refresh_token", "refresh_token": refresh, "client_id": client_id})


def _rpc(token: str | None, methode: str = "ping", params: dict | None = None):
    kopf = {"Authorization": f"Bearer {token}"} if token else {}
    return TestClient(app).post("/api/mcp", headers=kopf, json={
        "jsonrpc": "2.0", "id": 1, "method": methode, "params": params or {}})


def _verbinden(client) -> tuple[str, dict]:
    cid = _registrieren()
    r = _tauschen(_code(client, cid), cid)
    assert r.status_code == 200, r.text
    return cid, r.json()


# ---- Metadaten --------------------------------------------------------------

def test_metadaten_nennen_was_chatgpt_braucht():
    c = TestClient(app)
    pr = c.get("/.well-known/oauth-protected-resource").json()
    assert pr["resource"] == mcp_oauth.resource() and pr["resource"].endswith("/api/mcp")
    assert pr["authorization_servers"] == [mcp_oauth.issuer()]
    assert c.get("/.well-known/oauth-protected-resource/api/mcp").json() == pr
    asm = c.get("/.well-known/oauth-authorization-server").json()
    assert asm["issuer"] == mcp_oauth.issuer()
    # Ohne S256 hier bricht ChatGPT ab, bevor es überhaupt fragt.
    assert asm["code_challenge_methods_supported"] == ["S256"]
    assert asm["client_id_metadata_document_supported"] is True
    assert asm["registration_endpoint"].endswith("/api/oauth/register")
    assert asm["authorization_endpoint"].endswith("/oauth/freigeben")
    assert asm["authorization_response_iss_parameter_supported"] is True


def test_401_vom_server_zeigt_den_weg_zur_anmeldung():
    r = _rpc(None)
    assert r.status_code == 401
    kopf = r.headers["WWW-Authenticate"]
    assert f'resource_metadata="{mcp_oauth.resource_metadata_url()}"' in kopf
    assert 'scope="ratsdaten:lesen"' in kopf


def test_ohne_schalter_gibt_es_nichts(client, monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "")
    c = TestClient(app)
    assert c.get("/.well-known/oauth-protected-resource").status_code == 404
    assert c.get("/.well-known/oauth-authorization-server").status_code == 404
    assert c.post("/api/oauth/register", json={"redirect_uris": [REDIRECT]}).status_code == 404
    assert c.post("/api/oauth/token", data={"grant_type": "x"}).status_code == 404
    assert c.get("/api/oauth/authorize").status_code == 404


# ---- Der ganze Weg ----------------------------------------------------------

def test_chatgpt_weg_bis_zum_werkzeug(client):
    _konto(client)
    cid = _registrieren()

    # Ohne Sitzung: Die Seite schickt zur Anmeldung.
    ohne = TestClient(app).get("/api/oauth/authorize", params=_anfrage(cid)).json()
    assert ohne["status"] == "login"
    assert ohne["client_name"] == "ChatGPT" and ohne["redirect_host"] == "chatgpt.com"
    assert ohne["redirect_kind"] == "web"

    mit = client.get("/api/oauth/authorize", params=_anfrage(cid)).json()
    assert mit["status"] == "ready" and not mit["already_connected"] and not mit["at_limit"]

    r = _tauschen(_code(client, cid), cid)
    assert r.status_code == 200, r.text
    t = r.json()
    assert t["token_type"] == "Bearer" and t["expires_in"] == 3600
    assert t["access_token"].startswith("rloat_") and t["refresh_token"].startswith("rlort_")
    assert r.headers["Cache-Control"] == "no-store"

    cs = CouncilStore(COUNCIL_DB)
    cs.save_session(CouncilSession(4711, "Rat", "2026-06-29", "18:00", "PFL",
                                   agenda_items=[AgendaItem("Ö 5", "Radweg Ammerländer Heerstraße")]))
    cs._insert_decision(4711, 0, "decision", None, "Ö 5", "Radweg Ammerländer Heerstraße",
                        "Der Rat beschließt den Ausbau.", "accepted", None, None, None,
                        ["SPD"], "26/0101", None, None)
    cs._conn.commit()
    cs.close()
    a = _rpc(t["access_token"], "tools/call",
             {"name": "search_decisions", "arguments": {"committee": "Rat"}})
    assert a.status_code == 200, a.text
    ergebnis = a.json()["result"]
    assert ergebnis["isError"] is False
    assert "Ammerländer" in ergebnis["content"][0]["text"]

    # In den Einstellungen steht er als verbundener Agent.
    liste = client.get("/api/account/mcp-grants").json()
    assert [g["client_name"] for g in liste["grants"]] == ["ChatGPT"]
    assert liste["grants"][0]["redirect_host"] == "chatgpt.com"


def test_erneuern_rotiert_und_altes_token_kippt_die_freigabe(client):
    _konto(client)
    cid, t = _verbinden(client)
    r = _erneuern(t["refresh_token"], cid)
    assert r.status_code == 200, r.text
    neu = r.json()
    assert neu["refresh_token"] != t["refresh_token"]
    assert _rpc(t["access_token"]).status_code == 401      # das alte Zugangs-Token ist weg
    assert _rpc(neu["access_token"]).status_code == 200

    # Das abgelöste Erneuerungs-Token taucht wieder auf: Diebstahl angenommen.
    assert _erneuern(t["refresh_token"], cid).status_code == 400
    assert _rpc(neu["access_token"]).status_code == 401
    assert _erneuern(neu["refresh_token"], cid).status_code == 400


def test_code_zweimal_widerruft_alles(client):
    _konto(client)
    cid = _registrieren()
    code = _code(client, cid)
    t = _tauschen(code, cid).json()
    zweiter = _tauschen(code, cid)
    assert zweiter.status_code == 400 and zweiter.json()["error"] == "invalid_grant"
    assert _rpc(t["access_token"]).status_code == 401


def test_falsches_pkce_verbrennt_den_code(client):
    _konto(client)
    cid = _registrieren()
    code = _code(client, cid)
    assert _tauschen(code, cid, verifier="x" * 43).status_code == 400
    # Auch mit dem richtigen Verifier ist er danach nichts mehr wert.
    assert _tauschen(code, cid).status_code == 400


def test_code_gilt_nur_kurz(client, monkeypatch):
    _konto(client)
    cid = _registrieren()
    monkeypatch.setattr(mcp_oauth, "CODE_TTL", timedelta(seconds=-1))
    r = _tauschen(_code(client, cid), cid)
    assert r.status_code == 400 and r.json()["error_description"] == "code expired"


def test_code_gehoert_zu_client_und_rueckweg(client):
    _konto(client)
    cid = _registrieren()
    fremd = _registrieren(name="Anderer")
    assert _tauschen(_code(client, cid), fremd).status_code == 400
    r = _tauschen(_code(client, cid), cid, redirect_uri="https://chatgpt.com/anders")
    assert r.status_code == 400


def test_abgelaufenes_zugangs_token(client):
    _konto(client)
    _, t = _verbinden(client)
    store = Store(RATSLOTSE_DB)
    store._conn.execute("UPDATE mcp_oauth_grants SET access_expires = '2020-01-01T00:00:00+00:00'")
    store._conn.commit()
    store.close()
    r = _rpc(t["access_token"])
    assert r.status_code == 401 and 'error="invalid_token"' in r.headers["WWW-Authenticate"]


# ---- Was nie durchgehen darf ------------------------------------------------

def test_fremde_ruecksprungadresse_wird_nie_angesteuert(client):
    _konto(client)
    cid = _registrieren()
    boese = "https://angreifer.example.org/fang"
    pruef = client.get("/api/oauth/authorize", params=_anfrage(cid, redirect_uri=boese)).json()
    assert pruef["status"] == "error" and pruef["cancel_url"] is None
    r = client.post("/api/oauth/authorize",
                    json={**_anfrage(cid, redirect_uri=boese), "approve": True})
    assert r.status_code == 400
    # Auch ein Anhängsel an die echte Adresse ist eine andere Adresse.
    r = client.post("/api/oauth/authorize",
                    json={**_anfrage(cid, redirect_uri=REDIRECT + "/../x"), "approve": True})
    assert r.status_code == 400


def test_ohne_pkce_oder_mit_plain_geht_es_zurueck_mit_fehler(client):
    _konto(client)
    cid = _registrieren()
    for anders in ({"code_challenge": None}, {"code_challenge_method": "plain"}):
        r = client.post("/api/oauth/authorize", json={**_anfrage(cid, **anders), "approve": True})
        assert r.status_code == 200
        q = parse_qs(urlsplit(r.json()["redirect"]).query)
        assert q["error"] == ["invalid_request"] and "code" not in q


def test_fremde_ressource_wird_abgewiesen(client):
    _konto(client)
    cid = _registrieren()
    r = client.post("/api/oauth/authorize",
                    json={**_anfrage(cid, resource="https://anderer.example.org/mcp"),
                          "approve": True})
    assert parse_qs(urlsplit(r.json()["redirect"]).query)["error"] == ["invalid_target"]
    code = _code(client, cid)
    assert _tauschen(code, cid, resource="https://anderer.example.org/mcp").status_code == 400


def test_ablehnen_schickt_access_denied(client):
    _konto(client)
    cid = _registrieren()
    r = client.post("/api/oauth/authorize", json={**_anfrage(cid), "approve": False})
    q = parse_qs(urlsplit(r.json()["redirect"]).query)
    assert q["error"] == ["access_denied"] and q["state"] == ["zustand-1"]


def test_ohne_recht_keine_freigabe(client):
    _konto(client, rollen=())
    cid = _registrieren()
    pruef = client.get("/api/oauth/authorize", params=_anfrage(cid)).json()
    assert pruef["status"] == "forbidden"
    assert parse_qs(urlsplit(pruef["cancel_url"]).query)["error"] == ["access_denied"]
    assert client.post("/api/oauth/authorize",
                       json={**_anfrage(cid), "approve": True}).status_code == 403


def test_rolle_weg_heisst_kein_zugang_mehr(client):
    uid = _konto(client)
    cid, t = _verbinden(client)
    store = Store(RATSLOTSE_DB)
    store.set_web_user_roles(uid, [])
    store.close()
    assert _rpc(t["access_token"]).status_code == 403
    assert _erneuern(t["refresh_token"], cid).status_code == 400


def test_ueberall_abmelden_beendet_die_freigabe(client):
    uid = _konto(client)
    cid, t = _verbinden(client)
    store = Store(RATSLOTSE_DB)
    store.increment_token_version(uid)
    store.close()
    assert _rpc(t["access_token"]).status_code == 401
    assert _erneuern(t["refresh_token"], cid).status_code == 400


def test_trennen_in_den_einstellungen(client):
    _konto(client)
    cid, t = _verbinden(client)
    gid = client.get("/api/account/mcp-grants").json()["grants"][0]["id"]
    assert client.delete(f"/api/account/mcp-grants/{gid}").json() == {"ok": True}
    assert _rpc(t["access_token"]).status_code == 401
    assert _erneuern(t["refresh_token"], cid).status_code == 400
    assert client.get("/api/account/mcp-grants").json()["grants"] == []


def test_fremde_freigabe_laesst_sich_nicht_trennen(client):
    _konto(client)
    _verbinden(client)
    gid = client.get("/api/account/mcp-grants").json()["grants"][0]["id"]
    andere = TestClient(app)
    _konto(andere, email="zweite@example.org")
    assert andere.delete(f"/api/account/mcp-grants/{gid}").status_code == 404


def test_widerruf_durch_den_agenten(client):
    _konto(client)
    _, t = _verbinden(client)
    assert TestClient(app).post("/api/oauth/revoke", data={"token": t["refresh_token"]}).json() == {"ok": True}
    assert _rpc(t["access_token"]).status_code == 401
    # Unbekanntes Token: auch 200, ohne etwas zu verraten.
    assert TestClient(app).post("/api/oauth/revoke", data={"token": "rlort_nix"}).status_code == 200


def test_neu_verbinden_ersetzt_die_alte_freigabe(client):
    _konto(client)
    cid, alt = _verbinden(client)
    assert client.get("/api/oauth/authorize", params=_anfrage(cid)).json()["already_connected"]
    _tauschen(_code(client, cid), cid)
    assert len(client.get("/api/account/mcp-grants").json()["grants"]) == 1
    assert _rpc(alt["access_token"]).status_code == 401


def test_hoechstens_zehn_verbundene_agenten(client):
    _konto(client)
    for i in range(Store.MCP_GRANTS_MAX):
        cid = _registrieren(name=f"Agent {i}")
        _tauschen(_code(client, cid), cid)
    neu = _registrieren(name="Elfter")
    assert client.get("/api/oauth/authorize", params=_anfrage(neu)).json()["at_limit"]
    r = client.post("/api/oauth/authorize", json={**_anfrage(neu), "approve": True})
    assert r.status_code == 409


def test_persoenliche_schluessel_gehen_weiter(client):
    _konto(client)
    _verbinden(client)
    geheim = client.post("/api/account/mcp-tokens", json={"label": "Claude Code"}).json()["secret"]
    assert _rpc(geheim).status_code == 200


def test_sitzungs_cookie_oeffnet_den_server_auch_jetzt_nicht(client):
    _konto(client)
    _verbinden(client)
    assert client.post("/api/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"}).status_code == 401


# ---- Registrierung ----------------------------------------------------------

@pytest.mark.parametrize("uri, art", [
    ("https://chatgpt.com/connector/oauth/x", "web"),
    ("https://claude.ai/api/mcp/auth_callback", "web"),
    ("http://localhost:6274/oauth/callback", "local"),
    ("http://127.0.0.1:33418/callback", "local"),
    ("cursor://anysphere.cursor-mcp/oauth/callback", "app"),
    ("com.example.agent:/callback", "app"),
    ("http://agent.example.org/callback", None),       # http nur auf die eigene Maschine
    ("https://agent.example.org/cb#frag", None),
    ("https://nutzer@example.org/cb", None),
    ("javascript:alert(1)", None),
    ("data:text/html,hallo", None),
    ("file:///etc/passwd", None),
    ("https:///ohne-host", None),
    ("https://agent.example.org/c b", None),
])
def test_ruecksprungadressen(uri, art):
    assert mcp_oauth.redirect_art(uri) == art
    r = TestClient(app).post("/api/oauth/register", json={"redirect_uris": [uri]})
    assert r.status_code == (201 if art else 400), r.text


def test_ziel_auf_der_freigabe_seite():
    assert mcp_oauth.redirect_host("https://ChatGPT.com/connector/oauth/x") == "chatgpt.com"
    assert mcp_oauth.redirect_host("http://127.0.0.1:6274/oauth/callback") == "127.0.0.1:6274"
    assert mcp_oauth.redirect_host("cursor://anysphere.cursor-mcp/oauth/callback") == "cursor://"


def test_registrierung_verlangt_sinnvolles():
    c = TestClient(app)
    assert c.post("/api/oauth/register", json={"redirect_uris": []}).status_code == 400
    assert c.post("/api/oauth/register", json={"redirect_uris": [REDIRECT] * 6}).status_code == 400
    assert c.post("/api/oauth/register", json={"redirect_uris": [REDIRECT],
                                                "grant_types": ["client_credentials"]}).status_code == 400
    assert c.post("/api/oauth/register", json=[1, 2]).status_code == 400
    lang = c.post("/api/oauth/register", json={"redirect_uris": [REDIRECT],
                                                "client_name": "A\u0000" + "x" * 200}).json()
    assert len(lang["client_name"]) == 80 and "\u0000" not in lang["client_name"]


def test_registrierung_hat_eine_obergrenze(monkeypatch):
    monkeypatch.setattr(mcp_oauth, "REGISTRIERUNGEN_JE_STUNDE", 2)
    _registrieren()
    _registrieren()
    r = TestClient(app).post("/api/oauth/register", json={"redirect_uris": [REDIRECT]})
    assert r.status_code == 429


def test_unbenutzte_clients_werden_aufgeraeumt():
    cid = _registrieren()
    store = Store(RATSLOTSE_DB)
    store._conn.execute("UPDATE mcp_oauth_clients SET created = '2020-01-01T00:00:00+00:00'")
    store._conn.commit()
    store.purge_mcp_oauth()
    assert store.get_mcp_oauth_client(cid) is None
    store.close()


def test_token_endpunkt_bremst_nach_fehlversuchen(monkeypatch):
    monkeypatch.delenv("DISABLE_RATE_LIMIT", raising=False)
    monkeypatch.setattr(mcp_oauth, "_token_fehler", mcp_oauth.RateLimiter(3, 600))
    c = TestClient(app)
    for _ in range(3):
        assert c.post("/api/oauth/token", data={"grant_type": "authorization_code",
                                                 "code": "falsch"}).status_code == 400
    r = c.post("/api/oauth/token", data={"grant_type": "authorization_code", "code": "falsch"})
    assert r.status_code == 429


# ---- Client ID Metadata Document --------------------------------------------

CIMD = "https://chatgpt.com/.well-known/oauth-client.json"


def _steckbrief(monkeypatch, doc):
    aufrufe = []

    def abrufen(url):
        aufrufe.append(url)
        return json.dumps(doc).encode()
    monkeypatch.setattr(mcp_oauth, "cimd_abrufen", abrufen)
    return aufrufe


def test_cimd_client_ohne_registrierung(client, monkeypatch):
    aufrufe = _steckbrief(monkeypatch, {"client_id": CIMD, "client_name": "ChatGPT",
                                        "redirect_uris": [REDIRECT]})
    _konto(client)
    pruef = client.get("/api/oauth/authorize", params=_anfrage(CIMD)).json()
    assert pruef["status"] == "ready" and pruef["client_id_host"] == "chatgpt.com"
    r = _tauschen(_code(client, CIMD), CIMD)
    assert r.status_code == 200, r.text
    assert _rpc(r.json()["access_token"]).status_code == 200
    assert len(aufrufe) == 1  # zwischengespeichert, nicht je Anfrage geholt


def test_cimd_muss_zu_seiner_adresse_passen(client, monkeypatch):
    _steckbrief(monkeypatch, {"client_id": "https://anders.example.org/c.json",
                              "redirect_uris": [REDIRECT]})
    _konto(client)
    pruef = client.get("/api/oauth/authorize", params=_anfrage(CIMD)).json()
    assert pruef["status"] == "error" and pruef["cancel_url"] is None


def test_cimd_redirect_aus_dem_steckbrief(client, monkeypatch):
    _steckbrief(monkeypatch, {"client_id": CIMD, "redirect_uris": ["https://chatgpt.com/anders"]})
    _konto(client)
    assert client.get("/api/oauth/authorize", params=_anfrage(CIMD)).json()["status"] == "error"


@pytest.mark.parametrize("cid", [
    "http://chatgpt.com/client.json",
    "https://chatgpt.com/",
    "https://chatgpt.com",
    "https://chatgpt.com:8443/client.json",
    "https://nutzer@example.org/client.json",
    "https://chatgpt.com/c.json#x",
])
def test_cimd_adressen(cid):
    assert not mcp_oauth.cimd_adresse_ok(cid)


def test_cimd_holt_nichts_aus_dem_eigenen_netz():
    for host in ("127.0.0.1", "10.10.10.14", "100.118.52.13", "169.254.169.254", "::1", "localhost"):
        assert not mcp_oauth._oeffentlich(host), host


# ---- Konto löschen ----------------------------------------------------------

def test_freigaben_gehen_mit_dem_konto():
    namen = {t for t, _ in USER_OWNED_TABLES}
    assert {"mcp_oauth_grants", "mcp_oauth_codes", "mcp_oauth_retired"} <= namen
