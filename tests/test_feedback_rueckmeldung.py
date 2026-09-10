"""Rückmeldung an die absendende Person: „Dein Vorschlag ist umgesetzt".

Der Anlass ist Tims Wunsch (10.09.2026): Wer etwas vorschlägt, soll erfahren,
dass es umgesetzt wurde — mit einer optionalen Zeile von uns dazu.

Der heikle Teil ist nicht das Verschicken, sondern **wann nicht**. Eine Mail
geht an eine fremde Person, auf unsere Kosten und mit unserer Absenderdomain.
Diese Datei hält die vier Riegel fest:

* Eine gemeldete Share-Verletzung (`qa_share`) löst nie Post aus — sie ist
  eine Meldung ÜBER fremde Inhalte, keine Anregung. Eine Rückmeldung wäre
  eine Empfangsbestätigung an jemanden, der das nicht wissen soll.
* Ohne hinterlegte Adresse geht nichts, und das sagt der Endpunkt auch.
* Ein zweites Mal gibt es nicht — „Wieder öffnen" und erneut „Erledigt" ist
  ein üblicher Handgriff im Panel.
* Scheitert der Versand, wird `notified_at` NICHT gesetzt. Ein Vermerk ohne
  Mail nähme der Person die Antwort und uns den zweiten Versuch.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

_BACKEND = Path(__file__).resolve().parents[1] / "web" / "backend"
sys.path.insert(0, str(_BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from kern.store import Store  # noqa: E402
from scripts.grant_admin import grant_admin  # noqa: E402

RATSLOTSE_DB = os.environ["RATSLOTSE_DB"]
COUNCIL_DB = os.environ["COUNCIL_DB"]
PASSWORT = "password123"


@pytest.fixture(autouse=True)
def fresh_dbs():
    for base in (RATSLOTSE_DB, COUNCIL_DB):
        for suffix in ("", "-wal", "-shm"):
            Path(base + suffix).unlink(missing_ok=True)
    yield


@pytest.fixture
def admin_client():
    c = TestClient(app)
    r = c.post("/api/auth/register",
              json={"display_name": "Testkonto", "email": "admin@test.de", "password": PASSWORT})
    assert r.status_code == 201, r.text
    grant_admin("admin@test.de", RATSLOTSE_DB)
    return c


@pytest.fixture
def postfach():
    return []


def _mit_versand(postfach):
    """Mailversand vortäuschen und einen Resend-Key vorgaukeln."""
    def fake_send(to, subject, html, **kw):
        postfach.append({"to": to, "subject": subject, "html": html,
                         "text": kw.get("text", "")})
        return "id"

    einstellungen = SimpleNamespace(
        resend_api_key="x", app_base_url="https://ratslotse.de",
        email_from="Ratslotse <f@example.org>", feedback_email="", web_admin_email="",
    )
    return (patch("app.routers.admin.send_email", side_effect=fake_send),
            patch("app.routers.admin.get_settings", return_value=einstellungen))


def _feedback_anlegen(kind="feature", email="vorschlag@example.org",
                      text="Bitte die E-Mail-Adresse änderbar machen.") -> int:
    store = Store(RATSLOTSE_DB)
    try:
        return store.add_feedback(0, email, kind, text)
    finally:
        store.close()


def _eintrag(fid: int) -> dict:
    store = Store(RATSLOTSE_DB)
    try:
        return store.get_feedback(fid) or {}
    finally:
        store.close()


# --- Der Normalfall ---------------------------------------------------------

def test_rueckmeldung_geht_raus_und_hakt_ab(admin_client, postfach):
    fid = _feedback_anlegen()
    versand, einstellungen = _mit_versand(postfach)
    with versand, einstellungen:
        r = admin_client.post(f"/api/admin/feedback/{fid}/notify",
                              json={"message": "Seit heute unter „Mein Konto“."})
    assert r.status_code == 200, r.text
    assert r.json()["recipient"] == "vorschlag@example.org"
    assert r.json()["notified_at"]

    assert len(postfach) == 1
    mail = postfach[0]
    assert mail["to"] == "vorschlag@example.org"
    assert "vorschlag" in mail["subject"].lower()
    # Die optionale Zeile steht drin — und die ursprüngliche Nachricht als Zitat,
    # damit klar ist, worauf geantwortet wird.
    assert "Mein Konto" in mail["html"]
    assert "E-Mail-Adresse änderbar" in mail["html"]

    # Abgehakt ist es damit auch: zwei Handgriffe wären einer zu viel.
    eintrag = _eintrag(fid)
    assert eintrag["notified_at"] and eintrag["read_at"]


def test_die_nachricht_ist_wirklich_optional(admin_client, postfach):
    fid = _feedback_anlegen()
    versand, einstellungen = _mit_versand(postfach)
    with versand, einstellungen:
        r = admin_client.post(f"/api/admin/feedback/{fid}/notify", json={"message": ""})
    assert r.status_code == 200, r.text
    assert "umgesetzt" in postfach[0]["html"]


@pytest.mark.parametrize("kind,erwartet", [
    ("feature", "vorschlag"),
    ("bug", "fehler"),
    ("konto", "anfrage"),
    ("other", "nachricht"),
])
def test_je_art_ein_eigener_kernsatz(admin_client, postfach, kind, erwartet):
    """Ein „Vorschlag umgesetzt" auf eine Fehlermeldung liest sich falsch."""
    fid = _feedback_anlegen(kind=kind)
    versand, einstellungen = _mit_versand(postfach)
    with versand, einstellungen:
        r = admin_client.post(f"/api/admin/feedback/{fid}/notify", json={"message": ""})
    assert r.status_code == 200, r.text
    assert erwartet in postfach[0]["subject"].lower()


# --- Die vier Riegel --------------------------------------------------------

def test_gemeldete_inhalte_loesen_nie_post_aus(admin_client, postfach):
    """`qa_share` ist eine Meldung ÜBER fremde Inhalte. Eine Rückmeldung wäre
    eine Empfangsbestätigung an jemanden, der das nicht wissen soll."""
    fid = _feedback_anlegen(kind="qa_share", text="Share-Token: abc123")
    versand, einstellungen = _mit_versand(postfach)
    with versand, einstellungen:
        r = admin_client.post(f"/api/admin/feedback/{fid}/notify", json={"message": ""})
    assert r.status_code == 400
    assert not postfach
    assert not _eintrag(fid)["notified_at"]


def test_ohne_adresse_geht_nichts(admin_client, postfach):
    fid = _feedback_anlegen(email=None)
    versand, einstellungen = _mit_versand(postfach)
    with versand, einstellungen:
        r = admin_client.post(f"/api/admin/feedback/{fid}/notify", json={"message": ""})
    assert r.status_code == 400
    assert "Adresse" in r.json()["detail"]
    assert not postfach


def test_local_adressen_bekommen_keine_post(admin_client, postfach):
    """Der Telegram-Altbestand trägt synthetische `…@local`-Adressen ohne
    Postfach."""
    fid = _feedback_anlegen(email="tg-42@local")
    versand, einstellungen = _mit_versand(postfach)
    with versand, einstellungen:
        r = admin_client.post(f"/api/admin/feedback/{fid}/notify", json={"message": ""})
    assert r.status_code == 400
    assert not postfach


def test_kein_zweites_mal(admin_client, postfach):
    """„Wieder öffnen" und erneut „Erledigt" ist ein üblicher Handgriff — er
    darf niemandem dieselbe Mail nachschicken."""
    fid = _feedback_anlegen()
    versand, einstellungen = _mit_versand(postfach)
    with versand, einstellungen:
        assert admin_client.post(f"/api/admin/feedback/{fid}/notify",
                                 json={"message": ""}).status_code == 200
    admin_client.post(f"/api/admin/feedback/{fid}/read?read=false")
    versand, einstellungen = _mit_versand(postfach)
    with versand, einstellungen:
        r = admin_client.post(f"/api/admin/feedback/{fid}/notify", json={"message": ""})
    assert r.status_code == 409
    assert len(postfach) == 1


def test_ein_fehlgeschlagener_versand_setzt_keinen_vermerk(admin_client):
    """Ein Vermerk ohne Mail nähme der Person die Antwort und uns den zweiten
    Versuch."""
    fid = _feedback_anlegen()
    einstellungen = SimpleNamespace(
        resend_api_key="x", app_base_url="https://ratslotse.de",
        email_from="Ratslotse <f@example.org>", feedback_email="", web_admin_email="")
    with patch("app.routers.admin.send_email", side_effect=RuntimeError("Resend down")), \
         patch("app.routers.admin.get_settings", return_value=einstellungen):
        r = admin_client.post(f"/api/admin/feedback/{fid}/notify", json={"message": ""})
    assert r.status_code == 502
    eintrag = _eintrag(fid)
    assert not eintrag["notified_at"]
    assert not eintrag["read_at"], "ohne Mail auch nicht abhaken"


def test_ohne_mailversand_sagt_der_endpunkt_das(admin_client):
    fid = _feedback_anlegen()
    r = admin_client.post(f"/api/admin/feedback/{fid}/notify", json={"message": ""})
    assert r.status_code == 503


def test_nur_admins(admin_client):
    fid = _feedback_anlegen()
    fremd = TestClient(app)
    fremd.post("/api/auth/register",
               json={"display_name": "Testkonto", "email": "fremd@example.org", "password": PASSWORT})
    r = fremd.post(f"/api/admin/feedback/{fid}/notify", json={"message": ""})
    assert r.status_code == 403


def test_unbekannte_id(admin_client):
    r = admin_client.post("/api/admin/feedback/99999/notify", json={"message": ""})
    assert r.status_code == 404


# --- Was die Liste zeigt ----------------------------------------------------

def test_die_liste_traegt_den_vermerk(admin_client, postfach):
    """Ohne das Feld könnte die Oberfläche „schon benachrichtigt" nicht
    anzeigen und böte die Mail ein zweites Mal an."""
    fid = _feedback_anlegen()
    zeilen = admin_client.get("/api/admin/feedback").json()["items"]
    assert [z for z in zeilen if z["id"] == fid][0]["notified_at"] is None

    versand, einstellungen = _mit_versand(postfach)
    with versand, einstellungen:
        admin_client.post(f"/api/admin/feedback/{fid}/notify", json={"message": ""})

    zeilen = admin_client.get("/api/admin/feedback").json()["items"]
    assert [z for z in zeilen if z["id"] == fid][0]["notified_at"]
