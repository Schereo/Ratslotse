"""Gemeinsame Notizen (``web/backend/app/routers/shared_notes.py``): einladen
per Link, beitreten, live schreiben — der Server hält nur Blobs.

Ver- und Entschlüsseln, das Verpacken mit dem Link-Geheimnis und das
Zusammenführen der Yjs-Änderungen prüft ``web/frontend/lib/shared-note-crypto.test.ts``.
"""
from __future__ import annotations

import base64
import hashlib
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))

from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402
from app.main import app  # noqa: E402
from kern.store import Store  # noqa: E402

RATSLOTSE_DB = os.environ["RATSLOTSE_DB"]
ZIEL = {"target_kind": "agenda_item", "target_key": "4654|Ö 11.1"}


def b64(n: int, fill: int = 7) -> str:
    return base64.b64encode(bytes([fill]) * n).decode()


SCHLUESSEL = {"key_iv": b64(12, 1), "key_ct": b64(48, 2), "key_version": 1}


def nachweis(fill: int = 9) -> tuple[str, str]:
    """(Nachweis, sein Hash) — wie ``inviteVerifier``/``makeInvite`` im Browser."""
    roh = bytes([fill]) * 32
    return base64.b64encode(roh).decode(), base64.b64encode(hashlib.sha256(roh).digest()).decode()


def _einladung(c: TestClient, note_id: str, fill: int = 9, iv: str | None = None, ct: str | None = None) -> dict:
    r = c.post(f"/api/shared-notes/{note_id}/invites",
               json={"iv": iv or b64(12), "ciphertext": ct or b64(48), "verifier_hash": nachweis(fill)[1]})
    assert r.status_code == 200, r.text
    return r.json()


def _annehmen(c: TestClient, invite_id: str, fill: int = 9):
    return c.post(f"/api/note-invites/{invite_id}/accept",
                  json={"key_iv": b64(12, 5), "key_ct": b64(48, 6), "key_version": 1, "verifier": nachweis(fill)[0]})


@pytest.fixture(autouse=True)
def frisch(monkeypatch):
    for suffix in ("", "-wal", "-shm"):
        Path(RATSLOTSE_DB + suffix).unlink(missing_ok=True)
    monkeypatch.setenv("FEATURE_FLAGS", "notizen,notizen-teilen")
    yield


def _konto(email: str, name: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/auth/register", json={"display_name": name, "email": email, "password": "password123"})
    assert r.status_code == 201, r.text
    c.post("/api/auth/login", json={"email": email, "password": "password123"})
    return c


def _ich(c: TestClient) -> int:
    return c.get("/api/auth/me").json()["id"]


def _anlegen(c: TestClient) -> dict:
    r = c.post("/api/shared-notes", json={**ZIEL, **SCHLUESSEL})
    assert r.status_code == 200, r.text
    return r.json()


def _einladen_und_beitreten(anna: TestClient, ben: TestClient, note_id: str) -> dict:
    inv = _einladung(anna, note_id, iv=b64(12, 3), ct=b64(48, 4))
    info = ben.get(f"/api/note-invites/{inv['id']}").json()
    assert (info["iv"], info["ciphertext"], info["already_member"]) == (b64(12, 3), b64(48, 4), False)
    assert info["inviter_name"] == "Anna"
    assert "verifier_hash" not in info, "der Hash geht nur an den, der ihn angelegt hat — an niemanden"
    r = _annehmen(ben, inv["id"])
    assert r.status_code == 200, r.text
    return r.json()


def test_ohne_schalter_und_ohne_konto_nichts(monkeypatch):
    anna = _konto("anna@example.org", "Anna")
    monkeypatch.setenv("FEATURE_FLAGS", "notizen")
    assert anna.get("/api/shared-notes").status_code == 404
    monkeypatch.setenv("FEATURE_FLAGS", "notizen,notizen-teilen")
    assert TestClient(app).get("/api/shared-notes").status_code == 401


def test_anlegen_einladen_beitreten_und_jeder_haelt_seinen_eigenen_schluessel():
    anna, ben = _konto("anna@example.org", "Anna"), _konto("ben@example.org", "Ben")
    note = _anlegen(anna)
    assert note["role"] == "owner" and [m["display_name"] for m in note["members"]] == ["Anna"]
    bei_ben = _einladen_und_beitreten(anna, ben, note["id"])
    assert bei_ben["role"] == "editor" and bei_ben["key_iv"] == b64(12, 5), "Ben hält SEINE Verpackung"
    assert [m["display_name"] for m in bei_ben["members"]] == ["Anna", "Ben"]
    bei_anna = anna.get("/api/shared-notes", params=ZIEL).json()["notes"][0]
    assert bei_anna["key_iv"] == b64(12, 1), "Annas Verpackung bleibt ihre"
    # Wer nicht dabei ist, erfährt nicht, dass es die Notiz gibt.
    carla = _konto("carla@example.org", "Carla")
    assert carla.get("/api/shared-notes", params=ZIEL).json()["notes"] == []
    assert carla.post(f"/api/shared-notes/{note['id']}/ticket").status_code == 404


def test_einladungen_laufen_ab_und_lassen_sich_zurueckziehen():
    anna, ben = _konto("anna@example.org", "Anna"), _konto("ben@example.org", "Ben")
    note = _anlegen(anna)
    inv = _einladung(anna, note["id"])
    assert [i["id"] for i in anna.get(f"/api/shared-notes/{note['id']}/invites").json()["invites"]] == [inv["id"]]
    assert anna.delete(f"/api/shared-notes/{note['id']}/invites/{inv['id']}").status_code == 204
    assert ben.get(f"/api/note-invites/{inv['id']}").status_code == 404
    inv2 = _einladung(anna, note["id"])
    store = Store(RATSLOTSE_DB)
    store._conn.execute("UPDATE shared_note_invites SET expires_at = '2000-01-01T00:00:00' WHERE id = ?", (inv2["id"],))
    store._conn.commit()
    store.close()
    assert ben.get(f"/api/note-invites/{inv2['id']}").status_code == 404


def test_beitreten_verlangt_den_nachweis_aus_dem_geheimnis():
    """Die Kennung steht im sichtbaren Teil des Links — sie allein reicht nicht."""
    anna, ben = _konto("anna@example.org", "Anna"), _konto("ben@example.org", "Ben")
    note = _anlegen(anna)
    inv = _einladung(anna, note["id"], fill=9)
    ohne = ben.post(f"/api/note-invites/{inv['id']}/accept", json=SCHLUESSEL)
    assert ohne.status_code == 422
    falsch = _annehmen(ben, inv["id"], fill=8)
    assert falsch.status_code == 403 and "Link" in falsch.json()["detail"]
    assert ben.get("/api/shared-notes").json()["notes"] == []
    assert _annehmen(ben, inv["id"], fill=9).status_code == 200
    # Ohne Hash legt niemand eine Einladung an.
    r = anna.post(f"/api/shared-notes/{note['id']}/invites", json={"iv": b64(12), "ciphertext": b64(48)})
    assert r.status_code == 422


def test_wer_geht_nimmt_alle_offenen_einladungen_mit():
    """Wer entfernt wird, kennt den alten Schlüssel und womöglich die Links der
    anderen — mit einem davon wäre er sonst gleich wieder drin."""
    anna, ben = _konto("anna@example.org", "Anna"), _konto("ben@example.org", "Ben")
    note = _anlegen(anna)
    _einladen_und_beitreten(anna, ben, note["id"])
    offen = _einladung(anna, note["id"], fill=4)
    assert anna.delete(f"/api/shared-notes/{note['id']}/members/{_ich(ben)}").status_code == 204
    assert anna.get(f"/api/shared-notes/{note['id']}/invites").json()["invites"] == []
    assert _annehmen(ben, offen["id"], fill=4).status_code == 404
    assert ben.get("/api/shared-notes").json()["notes"] == []


def test_einladungen_sieht_und_zieht_nur_zurueck_wer_sie_angelegt_hat_oder_leitet():
    anna, ben = _konto("anna@example.org", "Anna"), _konto("ben@example.org", "Ben")
    note = _anlegen(anna)
    _einladen_und_beitreten(anna, ben, note["id"])
    von_anna = _einladung(anna, note["id"], fill=1)
    von_ben = _einladung(ben, note["id"], fill=2)
    pfad = f"/api/shared-notes/{note['id']}/invites"
    # Die Leitung sieht alle (auch die, mit der Ben beitrat — ein Link darf mehrere einladen).
    assert {von_anna["id"], von_ben["id"]} <= {i["id"] for i in anna.get(pfad).json()["invites"]}
    assert [i["id"] for i in ben.get(pfad).json()["invites"]] == [von_ben["id"]]
    assert ben.delete(f"{pfad}/{von_anna['id']}").status_code == 404
    assert anna.delete(f"{pfad}/{von_ben['id']}").status_code == 204
    assert ben.delete(f"{pfad}/{von_anna['id']}").status_code == 404
    assert anna.delete(f"{pfad}/{von_anna['id']}").status_code == 204


def test_entfernen_gehen_und_loeschen():
    anna, ben = _konto("anna@example.org", "Anna"), _konto("ben@example.org", "Ben")
    note = _anlegen(anna)
    _einladen_und_beitreten(anna, ben, note["id"])
    ben_id = _ich(ben)
    # Ben darf Anna nicht entfernen und die Notiz nicht löschen …
    assert ben.delete(f"/api/shared-notes/{note['id']}/members/{_ich(anna)}").status_code == 403
    assert ben.delete(f"/api/shared-notes/{note['id']}").status_code == 403
    # … aber Anna darf Ben entfernen.
    assert anna.delete(f"/api/shared-notes/{note['id']}/members/{ben_id}").status_code == 204
    assert ben.get("/api/shared-notes").json()["notes"] == []
    assert anna.delete(f"/api/shared-notes/{note['id']}").status_code == 204
    assert anna.get("/api/shared-notes").json()["notes"] == []


def test_geht_die_leitung_uebernimmt_das_naechste_mitglied():
    anna, ben = _konto("anna@example.org", "Anna"), _konto("ben@example.org", "Ben")
    note = _anlegen(anna)
    _einladen_und_beitreten(anna, ben, note["id"])
    assert anna.delete(f"/api/shared-notes/{note['id']}/members/{_ich(anna)}").status_code == 204
    bei_ben = ben.get("/api/shared-notes").json()["notes"][0]
    assert bei_ben["role"] == "owner" and bei_ben["owner_id"] == _ich(ben)


def test_konto_loeschen_gibt_die_notiz_weiter_und_nimmt_den_urheber_mit():
    anna, ben = _konto("anna@example.org", "Anna"), _konto("ben@example.org", "Ben")
    note = _anlegen(anna)
    _einladen_und_beitreten(anna, ben, note["id"])
    store = Store(RATSLOTSE_DB)
    try:
        store.add_shared_note_update(note["id"], _ich(anna), b64(12), b64(30))
        store.delete_web_user(_ich(anna))
        n = store.get_shared_note(note["id"])
        assert n and n["owner_id"] == _ich(ben)
        assert store._conn.execute("SELECT author_id FROM shared_note_updates").fetchall()[0][0] is None
        store.delete_web_user(_ich(ben))
        assert store.get_shared_note(note["id"]) is None, "ohne Mitglied verschwindet die Notiz"
        assert store._conn.execute("SELECT COUNT(*) FROM shared_note_updates").fetchone()[0] == 0
    finally:
        store.close()


def test_blobs_werden_geprueft():
    anna = _konto("anna@example.org", "Anna")
    assert anna.post("/api/shared-notes", json={**ZIEL, **SCHLUESSEL, "key_iv": b64(8)}).status_code == 422
    assert anna.post("/api/shared-notes", json={**ZIEL, **SCHLUESSEL, "key_ct": "kein base64!"}).status_code == 422
    assert anna.post("/api/shared-notes", json={**SCHLUESSEL, "target_kind": "agenda_item",
                                                "target_key": "irgendwas"}).status_code == 422


# --- Live -------------------------------------------------------------------
# Alle Live-Verbindungen eines Tests laufen über EINEN TestClient (eine
# Ereignisschleife), wie auf dem Server über die eine Schleife von uvicorn.
# Mit je einem Client pro Konto lief jede Sitzung in eigener Schleife und
# eigenem Thread; das Verteilen von Annas Änderung in Bens Sitzung ging dann
# über Schleifengrenzen und blieb ab und zu hängen (gemessen 23.11.2026). Die
# Tickets holt weiter jedes Konto mit seinem Cookie — die Verbindung braucht keins.

@pytest.fixture
def leitung():
    with TestClient(app) as c:
        yield c


def _live(c: TestClient, leitung: TestClient, note_id: str):
    ticket = c.post(f"/api/shared-notes/{note_id}/ticket").json()["ticket"]
    return leitung.websocket_connect(f"/api/shared-notes/{note_id}/live?ticket={ticket}")


def _bis(ws, art: str) -> dict:
    for _ in range(20):
        m = ws.receive_json()
        if m["t"] == art:
            return m
    raise AssertionError(f"keine Nachricht {art}")


def test_live_aenderungen_kommen_beim_anderen_an_und_bleiben(leitung):
    anna, ben = _konto("anna@example.org", "Anna"), _konto("ben@example.org", "Ben")
    note = _anlegen(anna)
    _einladen_und_beitreten(anna, ben, note["id"])
    with _live(anna, leitung, note["id"]) as wa, _live(ben, leitung, note["id"]) as wb:
        assert _bis(wa, "hello")["you"] == _ich(anna)
        _bis(wb, "hello")
        assert sorted(_bis(wa, "presence")["online"]) in ([_ich(anna)], sorted([_ich(anna), _ich(ben)]))
        wa.send_json({"t": "update", "iv": b64(12, 1), "ct": b64(40, 9), "c": 1})
        assert _bis(wa, "ack") == {"t": "ack", "c": 1, "seq": 1}
        bei_ben = _bis(wb, "update")
        assert (bei_ben["seq"], bei_ben["ct"], bei_ben["from"]) == (1, b64(40, 9), _ich(anna))
        wb.send_json({"t": "awareness", "iv": b64(12), "ct": b64(20)})
        assert _bis(wa, "awareness")["from"] == _ich(ben)
    # Wer später kommt, holt alles nach.
    with _live(ben, leitung, note["id"]) as wb:
        _bis(wb, "hello")
        wb.send_json({"t": "sync", "since": 0})
        s = _bis(wb, "sync")
        assert s["snapshot"] is None and [u["seq"] for u in s["updates"]] == [1] and s["next_seq"] == 2


def test_ein_stand_ersetzt_die_aenderungen_davor(leitung):
    anna = _konto("anna@example.org", "Anna")
    note = _anlegen(anna)
    with _live(anna, leitung, note["id"]) as wa:
        _bis(wa, "hello")
        for i in range(3):
            wa.send_json({"t": "update", "iv": b64(12), "ct": b64(10, i), "c": i})
            _bis(wa, "ack")
        wa.send_json({"t": "snapshot", "upto": 2, "iv": b64(12, 8), "ct": b64(50, 8)})
        assert _bis(wa, "snapshot")["ok"] is True
        wa.send_json({"t": "snapshot", "upto": 1, "iv": b64(12), "ct": b64(10)})
        assert _bis(wa, "snapshot")["ok"] is False, "nur vorwärts"
        wa.send_json({"t": "sync", "since": 0})
        s = _bis(wa, "sync")
        assert s["snapshot"]["seq"] == 2 and [u["seq"] for u in s["updates"]] == [3]


def test_ohne_gueltiges_ticket_keine_verbindung(leitung):
    anna = _konto("anna@example.org", "Anna")
    note = _anlegen(anna)
    with pytest.raises(WebSocketDisconnect) as e:
        with leitung.websocket_connect(f"/api/shared-notes/{note['id']}/live?ticket=geraten") as ws:
            ws.receive_json()
    assert e.value.code == 4401
    # Ein Ticket gilt einmal und nur für seine Notiz.
    ticket = anna.post(f"/api/shared-notes/{note['id']}/ticket").json()["ticket"]
    with pytest.raises(WebSocketDisconnect):
        with leitung.websocket_connect(f"/api/shared-notes/andere/live?ticket={ticket}") as ws:
            ws.receive_json()


def test_wer_entfernt_wird_fliegt_aus_der_live_verbindung(leitung):
    anna, ben = _konto("anna@example.org", "Anna"), _konto("ben@example.org", "Ben")
    note = _anlegen(anna)
    _einladen_und_beitreten(anna, ben, note["id"])
    with _live(ben, leitung, note["id"]) as wb:
        _bis(wb, "hello")
        # Über dieselbe Schleife wie die Verbindung, mit Annas Cookie.
        leitung.cookies = anna.cookies
        assert leitung.delete(f"/api/shared-notes/{note['id']}/members/{_ich(ben)}").status_code == 204
        with pytest.raises(WebSocketDisconnect) as e:
            for _ in range(10):
                wb.receive_json()
        assert e.value.code == 4403


def _ohne_rauswurf_entfernen(note_id: str, user_id: int) -> None:
    """Mitgliedschaft endet auf einem Weg, der niemanden trennt (wie beim Löschen eines Kontos)."""
    store = Store(RATSLOTSE_DB)
    try:
        store.leave_shared_note(note_id, user_id)
    finally:
        store.close()


def test_ein_rauswurf_verwirft_auch_offene_tickets(leitung):
    anna, ben = _konto("anna@example.org", "Anna"), _konto("ben@example.org", "Ben")
    note = _anlegen(anna)
    _einladen_und_beitreten(anna, ben, note["id"])
    ticket = ben.post(f"/api/shared-notes/{note['id']}/ticket").json()["ticket"]
    leitung.cookies = anna.cookies
    assert leitung.delete(f"/api/shared-notes/{note['id']}/members/{_ich(ben)}").status_code == 204
    leitung.cookies.clear()
    with pytest.raises(WebSocketDisconnect) as e:
        with leitung.websocket_connect(f"/api/shared-notes/{note['id']}/live?ticket={ticket}") as ws:
            ws.receive_json()
    assert e.value.code == 4401


def test_ein_altes_ticket_hilft_nach_dem_ende_der_mitgliedschaft_nicht(leitung):
    anna, ben = _konto("anna@example.org", "Anna"), _konto("ben@example.org", "Ben")
    note = _anlegen(anna)
    _einladen_und_beitreten(anna, ben, note["id"])
    ticket = ben.post(f"/api/shared-notes/{note['id']}/ticket").json()["ticket"]
    _ohne_rauswurf_entfernen(note["id"], _ich(ben))
    with pytest.raises(WebSocketDisconnect) as e:
        with leitung.websocket_connect(f"/api/shared-notes/{note['id']}/live?ticket={ticket}") as ws:
            ws.receive_json()
    assert e.value.code == 4403


def test_nachholen_fragt_die_mitgliedschaft_noch_einmal(leitung):
    anna, ben = _konto("anna@example.org", "Anna"), _konto("ben@example.org", "Ben")
    note = _anlegen(anna)
    _einladen_und_beitreten(anna, ben, note["id"])
    with _live(ben, leitung, note["id"]) as wb:
        _bis(wb, "hello")
        _ohne_rauswurf_entfernen(note["id"], _ich(ben))
        wb.send_json({"t": "sync", "since": 0})
        with pytest.raises(WebSocketDisconnect) as e:
            for _ in range(10):
                wb.receive_json()
        assert e.value.code == 4403


def test_der_waechter_trennt_auch_ohne_rauswurf(leitung, monkeypatch):
    from app.routers import shared_notes

    monkeypatch.setattr(shared_notes, "MEMBERSHIP_CHECK_SECONDS", 0.05)
    anna, ben = _konto("anna@example.org", "Anna"), _konto("ben@example.org", "Ben")
    note = _anlegen(anna)
    _einladen_und_beitreten(anna, ben, note["id"])
    with _live(ben, leitung, note["id"]) as wb:
        _bis(wb, "hello")
        _ohne_rauswurf_entfernen(note["id"], _ich(ben))
        with pytest.raises(WebSocketDisconnect) as e:
            for _ in range(10):
                wb.receive_json()
        assert e.value.code == 4403
