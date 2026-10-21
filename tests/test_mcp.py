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

import json
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
    mcp_tools.lade_kontingent_vergessen()
    monkeypatch.setattr(mcp_tools, "LADE_ABSTAND_S", 0)
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
    # Ein Konto ohne Haushaltsrecht sieht genau die Werkzeuge ohne Recht.
    assert {w["name"] for w in werkzeuge} == {t.name for t in mcp_tools.erlaubt(set())}
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


def _rufe(token: str, name: str, **arguments) -> dict:
    r = _rpc(token, "tools/call", {"name": name, "arguments": arguments}).json()["result"]
    assert r["isError"] is False, r
    return json.loads(r["content"][0]["text"])


def test_alle_werkzeuge_antworten_als_json(client):
    """Bis 10/2026 antworteten vier der acht Werkzeuge mit Lottis Fließtext.
    Ein Agent liest JSON zuverlässiger, und er soll nicht je Werkzeug raten,
    welche Form kommt."""
    _konto(client)
    token = _schluessel(client)
    _beschluss()
    lang = ("Zusammenführung des Bäderbetriebs der Stadt Oldenburg (BBO) und der "
            "Bäderbetriebsgesellschaft Oldenburg mbH (BBGO) in eine GmbH & Co. KG - "
            "Grundsatzbeschluss vorbehaltlich der Zustimmung")
    cs = CouncilStore(COUNCIL_DB)
    cs.save_session(CouncilSession(4712, "Rat", "2026-07-06", "18:00", "PFL", agenda_items=[
        AgendaItem("Ö 6", lang), AgendaItem("N 11", "gesperrte Information")]))
    cs.close()

    s = _rufe(token, "list_sessions", committee="Rat", date_from="2026-06-01",
              date_to="2026-07-31")
    assert [x["ksinr"] for x in s["sessions"]] == [4711, 4712]
    assert s["sessions"][0]["status"] == "past"
    assert s["sessions"][0]["url"].endswith("/council/sitzung?ksinr=4711")

    a = _rufe(token, "get_agenda", ksinr=4712)
    # Der Titel kommt GANZ — Lottis Tagesordnung schnitt bei 160 Zeichen
    # mitten im Wort („Grundsatzbeschluss vo“).
    assert a["items"][0]["title"] == lang
    assert [i["public"] for i in a["items"]] == [True, False]
    assert a["original_url"].endswith("si0057.php?__ksinr=4712")
    assert _rufe(token, "get_agenda", ksinr=4711)["items"][0]["outcome"] == "angenommen"

    h = _rufe(token, "get_template_history", template_number="26/0101")
    assert h["consultations"][0]["committee"] == "Rat"
    assert h["consultations"][0]["outcome"] == "angenommen"

    z = _rufe(token, "count_decisions", year=2026)
    assert z["total"] == 1 and z["by_outcome"] == {"angenommen": 1}

    r = _rpc(token, "tools/call", {"name": "get_template_history",
                                   "arguments": {"template_number": "Radweg"}}).json()["result"]
    assert r["isError"] is True


def test_lotti_kuerzt_lange_titel_sichtbar():
    """Lotti behält ihre Kürzung, aber mit „…“: Ohne Zeichen hält das Modell
    den Stummel für den ganzen Titel."""
    from council import lotti_werkzeuge as lw

    cs = CouncilStore(COUNCIL_DB)
    cs.save_session(CouncilSession(4713, "Rat", "2026-07-06", "18:00", "PFL",
                                   agenda_items=[AgendaItem("Ö 6", "Bäderbetrieb " * 20)]))
    try:
        zeile = lw.tagesordnung(cs, {"ksinr": 4713}).text.splitlines()[2]
    finally:
        cs.close()
    assert zeile.endswith("Bäderbetrieb …")
    assert len(zeile) < lw.TOP_TITEL_MAX + 20


def test_volltext_ohne_pdf_spuren():
    """Am Bestand gesehen (Vorlage 22/0195): Seitenköpfe mitten im Text,
    harte Zeilenumbrüche und die gesperrte Unterschrift."""
    roh = (" \n  Ausdruck vom: 10.03.2022 \n  Seite: 1/2 \n \n"
           "Die CDU-Fraktion möchte wissen, ob es Planungen gibt, den \n"
           "Radweg zu verlängern. Der nörd-\nliche Abschnitt ist Tempo 30. \n \n"
           "In Vertretung \n \nDr . S v e n U h r h a n \n \n"
           "  Ausdruck vom: 10.03.2022 \n  Seite: 2/2 \n")
    text = mcp_tools._volltext(roh)
    assert "Ausdruck vom" not in text and "Seite:" not in text
    assert "ob es Planungen gibt, den Radweg zu verlängern." in text
    assert "nördliche Abschnitt" in text
    assert "Dr. Sven Uhrhan" in text
    assert "\n\n" in text  # Absätze bleiben Absätze
    assert mcp_tools._entsperren("J ü r g e n  K r o g m a n n") == "Jürgen Krogmann"
    # Ein gewöhnlicher Satz bleibt, wie er ist.
    assert mcp_tools._entsperren("Der Rat tagt am 3. 4. um 18 Uhr") == \
        "Der Rat tagt am 3. 4. um 18 Uhr"


def _protokoll_und_anlagen() -> None:
    """Eine Sitzung mit Protokoll und eine Vorlage mit zwei Anlagen — eine
    schon gelesen, eine noch nicht geladen."""
    cs = CouncilStore(COUNCIL_DB)
    cs.save_session(CouncilSession(4720, "Rat", "2026-09-28", "18:00", "PFL", agenda_items=[
        AgendaItem("Ö 7.2", "Weiteres Vorgehen Schießbahn Fliegerhorst - Beschluss",
                   "26/0629"),
        AgendaItem("N 11", "gesperrte Information")]))
    cs._conn.execute(
        "INSERT INTO council_protocols (ksinr, document_url, raw_text, extracted_at) "
        "VALUES (4720, 'https://buergerinfo.oldenburg.de/getfile.php?id=1&type=do', ?, "
        "datetime('now'))",
        ("zu 7.1 Erster Punkt\nDer Bericht wird zur Kenntnis genommen.\n"
         "zu 7.2 Weiteres Vorgehen Schießbahn Fliegerhorst\n"
         "Ratsfrau Muster erläutert, die Altlasten müssten vor jeder Be-\nbauung weg. "
         "Rückfragen an buero@example.org oder Tel. 0441 235-2350.\n"
         "Der Beschlussvorschlag wird angenommen.\n"
         "zu 8 Nächster Punkt\nNichts.\n",))
    cs._conn.execute("INSERT INTO council_templates (kvonr, template_number, title, "
                     "fetched_at) VALUES (29999, '26/0629', 'Schießbahn', datetime('now'))")
    cs._conn.executemany(
        "INSERT INTO council_attachments (document_id, kvonr, label, url, raw_text, "
        "n_pages, status, fetched_at) VALUES (?, 29999, ?, ?, ?, ?, ?, datetime('now'))",
        [(501, "Anlage 1 Gutachten", "https://buergerinfo.oldenburg.de/getfile.php?id=501",
          "Das Gutachten stellt Blei im Boden fest. " * 10, 4, "ok"),
         (502, "Anlage 2 Lageplan", "https://buergerinfo.oldenburg.de/getfile.php?id=502",
          None, None, "listed")])
    cs._conn.commit()
    cs.close()


def test_vorlagennummer_je_tagesordnungspunkt(client):
    """Ohne sie endet „was steht am 26.10. an?“ beim Titel — die Vorlage
    dahinter war für einen Agenten nicht zu erreichen."""
    _konto(client)
    token = _schluessel(client)
    _protokoll_und_anlagen()
    a = _rufe(token, "get_agenda", ksinr=4720)
    assert [i["template_number"] for i in a["items"]] == ["26/0629", None]


def test_protokollabschnitt(client):
    _konto(client)
    token = _schluessel(client)
    _protokoll_und_anlagen()
    p = _rufe(token, "get_protocol_section", ksinr=4720, item_number="Ö 7.2")
    assert "Altlasten müssten vor jeder Bebauung weg" in p["text"]
    # Nur dieser Punkt — weder der vorige noch der nächste.
    assert "Erster Punkt" not in p["text"] and "Nächster Punkt" not in p["text"]
    # Telefon und E-Mail gehen nicht hinaus, wie beim Suchindex.
    assert "example.org" not in p["text"] and "2350" not in p["text"]
    assert p["protocol_url"].startswith("https://buergerinfo.oldenburg.de/")

    for argumente in ({"ksinr": 4720, "item_number": "N 11"}, {"ksinr": 4720}):
        r = _rpc(token, "tools/call", {"name": "get_protocol_section",
                                       "arguments": argumente}).json()["result"]
        assert r["isError"] is True
    # Eine Sitzung ohne Protokoll ist kein Fehler, sondern ein Hinweis.
    p = _rufe(token, "get_protocol_section", ksinr=4711, item_number="Ö 5")
    assert p["text"] is None and "noch kein Protokoll" in p["hint"]


def test_anlagen_auf_zuruf(client, monkeypatch):
    """Eine noch nicht geladene Anlage holt der Server beim ersten Abruf —
    genau einmal; danach steht sie im Bestand."""
    _konto(client)
    token = _schluessel(client)
    _protokoll_und_anlagen()
    geladen = []

    def pdf(url, extraktor=None):
        geladen.append(url)
        return ("Lageplan der Schießbahn mit Kontakt buero@example.org. " * 10, 2)

    monkeypatch.setattr(mcp_tools.vorlagen, "_pdf_text", pdf)
    t = _rufe(token, "get_template", template_number="26/0629")
    assert {x["attachment_id"]: x["text"] for x in t["attachments"]} == {
        501: "available", 502: "on_demand"}

    assert "Blei im Boden" in _rufe(token, "get_attachment", attachment_id=501)["text"]
    assert geladen == []

    a = _rufe(token, "get_attachment", attachment_id=502)
    assert a["loaded_now"] is True and "Lageplan der Schießbahn" in a["text"]
    assert "example.org" not in a["text"]
    a = _rufe(token, "get_attachment", attachment_id=502)
    assert "loaded_now" not in a and len(geladen) == 1
    # Im Bestand steht die Adresse noch (maskiert wird beim Hinausgehen).
    cs = CouncilStore(COUNCIL_DB)
    assert cs.anlage_text(502).count("example.org") == 10
    cs.close()


def test_anlage_ohne_textebene_wird_nicht_wieder_geladen(client, monkeypatch):
    _konto(client)
    token = _schluessel(client)
    _protokoll_und_anlagen()
    geladen = []
    monkeypatch.setattr(mcp_tools.vorlagen, "_pdf_text",
                        lambda url, extraktor=None: geladen.append(url) or ("  ", 3))
    for _ in range(2):
        a = _rufe(token, "get_attachment", attachment_id=502)
        assert a["text"] is None and "keine lesbare Textebene" in a["hint"]
    assert len(geladen) == 1


def test_nachladen_ist_gedeckelt(client, monkeypatch):
    """Über alle Agenten zusammen: Das Ratsinformationssystem ist die Quelle
    des ganzen Bestands; eine Sperre dort träfe den Ingest."""
    _konto(client)
    token = _schluessel(client)
    _protokoll_und_anlagen()
    monkeypatch.setattr(mcp_tools, "LADE_JE_STUNDE", 0)
    monkeypatch.setattr(mcp_tools.vorlagen, "_pdf_text", lambda url, extraktor=None: ("x" * 500, 1))
    r = _rpc(token, "tools/call", {"name": "get_attachment",
                                   "arguments": {"attachment_id": 502}}).json()["result"]
    assert r["isError"] is True and "später" in r["content"][0]["text"]
    # Was schon im Bestand steht, bleibt lesbar.
    assert _rufe(token, "get_attachment", attachment_id=501)["text"]


def _sitzung_mit_top_anlagen() -> CouncilSession:
    return CouncilSession(4730, "Rat", "2026-10-26", "18:00", "PFL", agenda_items=[
        AgendaItem("Ö 7.2", "Weiteres Vorgehen Schießbahn Fliegerhorst - Beschluss",
                   anlagen=[{"label": "Änderungsantrag CDU Fliegerhorst",
                             "url": "https://buergerinfo.oldenburg.de/getfile.php?id=777&type=do"}]),
        AgendaItem("N 11", "gesperrte Information",
                   anlagen=[{"label": "Vertraulich",
                             "url": "https://buergerinfo.oldenburg.de/getfile.php?id=778&type=do"}])])


def test_anlagen_am_tagesordnungspunkt(client, monkeypatch):
    """Ein Punkt ohne Vorlage (Ö 7.2 am 26.10.2026) war für einen Agenten eine
    Sackgasse: Seine Unterlagen hängen nur am Punkt selbst."""
    _konto(client)
    token = _schluessel(client)
    cs = CouncilStore(COUNCIL_DB)
    cs.save_session(_sitzung_mit_top_anlagen())
    cs.close()
    geladen = []
    monkeypatch.setattr(mcp_tools.vorlagen, "_pdf_text", lambda url, extraktor=None: geladen.append(url) or (
        "Die CDU beantragt, die Schießbahn vor einer Bebauung vollständig zu sanieren. " * 5, 2))

    a = _rufe(token, "get_agenda", ksinr=4730)
    oeffentlich, geheim = a["items"]
    assert oeffentlich["template_number"] is None
    assert oeffentlich["attachments"] == [{
        "attachment_id": 777, "label": "Änderungsantrag CDU Fliegerhorst",
        "text": "on_demand", "url": "https://buergerinfo.oldenburg.de/getfile.php?id=777&type=do"}]
    assert geheim["attachments"] == []

    t = _rufe(token, "get_attachment", attachment_id=777)
    assert t["loaded_now"] is True and "Schießbahn" in t["text"] and t["item_number"] == "Ö 7.2"
    # Das nächste Einlesen der Sitzung (jeder check_council-Lauf) behält den Text.
    cs = CouncilStore(COUNCIL_DB)
    cs.save_session(_sitzung_mit_top_anlagen())
    cs.close()
    t = _rufe(token, "get_attachment", attachment_id=777)
    assert "loaded_now" not in t and len(geladen) == 1
    assert _rufe(token, "get_agenda", ksinr=4730)["items"][0]["attachments"][0]["text"] == \
        "available"

    r = _rpc(token, "tools/call", {"name": "get_attachment",
                                   "arguments": {"attachment_id": 778}}).json()["result"]
    assert r["isError"] is True and geladen == [geladen[0]]


def test_seitengrenze_zerreisst_keinen_absatz():
    """Am Stadion-Protokoll gesehen (17.10.2026): „Zwischenzeitlich habe der
    VfB“ endete als Absatz, weil die Fußzeile „Seite: 10/34“ zwischen
    Leerzeilen stand. Gemessen an 600 Protokollabschnitten: 121 Absätze
    endeten so mitten im Satz, mit der Heilung 35 — der Rest ist Layout der
    Beschlusstexte, keine Seitengrenze."""
    h = mcp_tools._seitenwechsel_heilen
    assert h("habe der VfB \n  Seite: 10/34 \n \nden Aufstieg geschafft.") == \
        "habe der VfB \nden Aufstieg geschafft."
    # Ein Absatz, der wirklich am Seitenende aufhört, bleibt einer.
    assert h("Ende des Absatzes. \n  Seite: 11/34 \n \nNeuer Absatz.") == \
        "Ende des Absatzes. \n\nNeuer Absatz."
    # Satzzeichen davor, aber klein danach: Der Satz läuft weiter.
    assert h("vgl. Anlage 3. \n Seite: 2/5 \n\nwird beschlossen.") == \
        "vgl. Anlage 3. \nwird beschlossen."
    # Silbentrennung über die Seite und der Vorlagenkopf aus zwei Zeilen.
    assert mcp_tools._volltext("Die Auszah-\n Ausdruck vom: 10.03.2022 \n Seite: 2/2 \n \n"
                               "lung erfolgt.") == "Die Auszahlung erfolgt."
    assert h("Seite: 1/3\n\nKopf am Anfang.") == "Kopf am Anfang."


def test_protokollabschnitt_ueber_die_seitengrenze(client):
    _konto(client)
    token = _schluessel(client)
    cs = CouncilStore(COUNCIL_DB)
    cs.save_session(CouncilSession(4740, "Rat", "2026-06-01", "18:00", "PFL",
                                   agenda_items=[AgendaItem("Ö 6.1", "Stadion")]))
    cs._conn.execute(
        "INSERT INTO council_protocols (ksinr, raw_text, extracted_at) VALUES (4740, ?, "
        "datetime('now'))",
        ("zu 6.1 Stadion\nOberbürgermeister Krogmann sagt, zwischenzeitlich habe der VfB \n"
         "  Seite: 10/34 \n \nden Aufstieg in die 3. Liga geschafft.\n\n"
         "Ratsfrau Schilling widerspricht.\nzu 6.2 Weiter\n",))
    cs._conn.commit()
    cs.close()
    p = _rufe(token, "get_protocol_section", ksinr=4740, item_number="Ö 6.1")
    assert "habe der VfB den Aufstieg in die 3. Liga geschafft." in p["text"]
    assert "Seite" not in p["text"]
    assert "geschafft.\n\nRatsfrau Schilling" in p["text"]


def test_die_anleitung_nennt_jedes_werkzeug():
    """Die Anleitung ist das Erste, was ein Agent liest. Kennt sie ein Werkzeug
    nicht, findet der Agent es nur, wenn er zufällig die Beschreibung liest —
    so ging es bis 10/2026 dem Protokollabschnitt und den Anlagen."""
    anleitung = mcp_router.ANLEITUNG + mcp_router.ANLEITUNG_HAUSHALT
    fehlt = sorted(n for n in mcp_tools.TOOLS if n not in anleitung)
    assert not fehlt, (f"ANLEITUNG in web/backend/app/routers/mcp.py nennt {fehlt} nicht — "
                       "dort in einen der typischen Wege aufnehmen.")


def test_budget_document_liest_bestaende_mit_beleg(client, monkeypatch):
    """Bestände, die bis 10/2026 nur auf den Haushaltsseiten standen —
    hier die Verpflichtungsermächtigungen: Jahr wählbar, Zeilen mit Beleg,
    ein fehlendes Jahr nennt die vorhandenen, viele Zeilen kommen in Stücken."""
    cs = CouncilStore(COUNCIL_DB)
    cur = cs._conn.execute(
        "INSERT INTO council_provenance (key, kind, label, url, probe, as_of, fetched_at) "
        "VALUES ('t:ve', 'haushaltsplan', 'Haushaltsplan 2026', "
        "'https://buergerinfo.oldenburg.de/getfile.php?id=9&type=do', 'x', '2026', "
        "datetime('now'))")
    cs._conn.executemany(
        "INSERT INTO council_commitments (budget_year, plan_year, due_year, amount, herkunft_id, "
        "fetched_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
        [(2025, 2025, 2026, 1_000_000, cur.lastrowid),
         (2026, 2026, 2027, 27_419_000, cur.lastrowid),
         (2026, 2026, 2028, 5_000_000, cur.lastrowid)])
    cs._conn.commit()
    cs.close()
    _konto(client, email="rat@example.org", rollen=("mcp_access", "council_member"))
    token = _schluessel(client)

    d = _rufe(token, "budget_document", kind="commitments")
    assert d["year"] == 2026 and d["available_years"] == [2025, 2026]
    assert [r["amount"] for r in d["rows"]] == [27_419_000, 5_000_000]
    assert d["rows"][0]["source"] == 0 and "herkunft_id" not in d["rows"][0]
    assert d["sources"][0]["url"].endswith("id=9&type=do")

    r = _rpc(token, "tools/call", {"name": "budget_document",
                                   "arguments": {"kind": "commitments", "year": 2019}})
    assert r.json()["result"]["isError"] is True
    assert "2025, 2026" in r.json()["result"]["content"][0]["text"]

    monkeypatch.setattr(mcp_tools, "DOKUMENT_ZEICHEN", 10)
    teil = _rufe(token, "budget_document", kind="commitments")
    assert len(teil["rows"]) == 1 and teil["next_offset"] == 1
    rest = _rufe(token, "budget_document", kind="commitments", offset=1)
    assert len(rest["rows"]) == 1 and rest["next_offset"] is None


def test_aufrufe_werden_gezaehlt(client):
    _konto(client)
    token = _schluessel(client)
    _rpc(token, "ping")
    zeile = client.get("/api/account/mcp-tokens").json()["tokens"][0]
    assert zeile["calls"] == 1 and zeile["last_used"]


# ---- Grenzen der Werkzeuge ---------------------------------------------------

#: Lotti-Funktionen, die ein Werkzeug OHNE Recht benutzen darf — keine davon
#: fasst den Haushalt an.
LW_OHNE_HAUSHALT = {"sitzungen_daten", "tagesordnung_daten", "beratungsfolge_daten",
                    "beschluesse_zaehlen_daten", "VORLAGEN_NR"}
_HAUSHALT_RE = re.compile(
    r"\bcouncil_(budget|debt|taxes|tax_plan|tax_rates|liquidity|staff_plan|products|"
    r"business_plans|fees|income_statement|investments_actual|einwohner)\b|\bqa\.geld_")


def test_haushalt_nur_mit_budget_und_nichts_kontogebundenes():
    """Kein Werkzeug fasst eine Tabelle an, die an einem Konto hängt — und den
    Haushalt nur eines mit ``recht="budget"``. Geprüft am Quelltext jedes
    Werkzeugs UND der Lotti-Funktionen, die es benutzt: Eine neue Abfrage auf
    ``bookmarks`` oder ``council_debt`` in einem Werkzeug ohne Recht soll hier
    auffallen, nicht erst in einem fremden Agenten (bis 21.10.2026 galt
    „gar kein Haushalt“, seitdem „nur mit budget“)."""
    import inspect

    from council import lotti_werkzeuge as lw

    verboten = {t for t, _ in USER_OWNED_TABLES} | {t for t, _ in COUNCIL_USER_OWNED_TABLES}
    quellen = (ROOT / "council" / "mcp_tools.py").read_text()
    alle_lw = set(re.findall(r"lw\.(\w+)", quellen))
    text = quellen + "".join(inspect.getsource(getattr(lw, n)) for n in alle_lw
                             if callable(getattr(lw, n)))
    treffer = sorted(t for t in verboten if re.search(rf"\b{t}\b", text))
    assert not treffer, f"Die MCP-Werkzeuge lesen kontogebundene Tabellen: {treffer}"

    for tool in mcp_tools.TOOLS.values():
        if tool.recht == "budget":
            continue
        assert tool.recht is None, f"{tool.name}: unbekanntes Recht {tool.recht}"
        quelle = inspect.getsource(tool.run)
        benutzt = set(re.findall(r"lw\.(\w+)", quelle))
        assert benutzt <= LW_OHNE_HAUSHALT, (
            f"{tool.name} hat kein Recht, benutzt aber {benutzt - LW_OHNE_HAUSHALT}. "
            "Haushalt? Dann recht=\"budget\" setzen; sonst hier aufnehmen.")
        assert not _HAUSHALT_RE.search(quelle), (
            f"{tool.name} liest Haushaltsdaten ohne recht=\"budget\".")
    assert {t.name for t in mcp_tools.erlaubt(set())} == {
        t.name for t in mcp_tools.TOOLS.values() if t.recht is None}


def _schuldenstand() -> None:
    cs = CouncilStore(COUNCIL_DB)
    cur = cs._conn.execute(
        "INSERT INTO council_provenance (key, kind, label, url, citation, probe, as_of, "
        "fetched_at) VALUES ('t:schulden', 'jahrbuch', 'Jahrbuch Tabelle 1108', "
        "'https://www.oldenburg.de/jahrbuch.pdf', 'Tabelle 1108', 'x', 'Stand 31.12.2025', "
        "datetime('now'))")
    cs._conn.executemany(
        "INSERT INTO council_debt (year, total, per_capita, herkunft_id, fetched_at) "
        "VALUES (?, ?, ?, ?, datetime('now'))",
        [(2024, 290_000_000, 1700, cur.lastrowid), (2025, 310_000_000, 1800, cur.lastrowid)])
    cs._conn.commit()
    cs.close()


def test_haushaltswerkzeuge_nur_mit_budget(client):
    """Ohne ``budget`` stehen die Haushaltswerkzeuge nicht in der Liste und
    lassen sich nicht rufen — als gäbe es sie nicht. Mit dem Recht
    (Ratsmitglied) kommen Werte mit Beleg."""
    _schuldenstand()
    _konto(client, email="ohne@example.org")
    ohne = _schluessel(client)
    namen = {w["name"] for w in _rpc(ohne, "tools/list").json()["result"]["tools"]}
    assert not any(n.startswith(("budget_", "enterprise_", "fee_", "cash_")) for n in namen)
    r = _rpc(ohne, "tools/call", {"name": "budget_series",
                                  "arguments": {"series": "schulden"}}).json()
    assert r["error"]["code"] == -32602

    client.cookies.clear()
    _konto(client, email="rat@example.org", rollen=("mcp_access", "council_member"))
    mit = _schluessel(client)
    assert "budget_search" in _rpc(mit, "initialize", {}).json()["result"]["instructions"]
    assert "budget_search" not in _rpc(ohne, "initialize", {}).json()["result"]["instructions"]
    namen = {w["name"] for w in _rpc(mit, "tools/list").json()["result"]["tools"]}
    assert {"budget_search", "budget_series", "budget_product", "enterprise_plans",
            "fee_calculations", "cash_position", "budget_document"} <= namen
    s = _rufe(mit, "budget_series", series="schulden", year_from=2024, year_to=2025)
    assert [v["value"] for v in s["values"]] == [290_000_000, 310_000_000]
    assert s["unit"] == "EUR" and s["values"][0]["source"] == 0
    assert s["sources"][0]["url"] == "https://www.oldenburg.de/jahrbuch.pdf"

    r = _rpc(mit, "tools/call", {"name": "cash_position",
                                 "arguments": {"month_from": "2025", "month_to": "2025-03"}})
    assert r.json()["result"]["isError"] is True
