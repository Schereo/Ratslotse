"""Die Befunde der Sicherheitsprüfung vom 07.10.2026 — je einer, der sie hält.

Die Prüfung lief über Backend, `kern`, Web und App und fand 26 Stellen. Die
großen (Bestätigungslink, Reset-Link) stehen in `test_backend_api.py` bei
ihren Geschwistern; hier steht der Rest, je Befund ein Test mit der Nummer
aus dem Bericht im Namen.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1] / "web" / "backend"
sys.path.insert(0, str(_BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from app import deepresearch  # noqa: E402
from app.main import app  # noqa: E402
from app.routers.council import (  # noqa: E402
    _grafik_pruefen,
    _share_text_is_objectionable,
    _stadt_link,
)
from council.store import CouncilStore  # noqa: E402
from council.store_viertel import PROJECT_REPORTS_PER_ACCOUNT  # noqa: E402
from kern.store import Store  # noqa: E402
from scripts.grant_admin import grant_admin  # noqa: E402

RATSLOTSE_DB = os.environ["RATSLOTSE_DB"]
COUNCIL_DB = os.environ["COUNCIL_DB"]


@pytest.fixture(autouse=True)
def fresh_dbs():
    for base in (RATSLOTSE_DB, COUNCIL_DB):
        for suffix in ("", "-wal", "-shm"):
            Path(base + suffix).unlink(missing_ok=True)
    yield


def _konto(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/auth/register", json={"display_name": "Test", "email": email,
                                           "password": "password123"})
    assert r.status_code == 201
    return c


# --- F2: Fehler-Mails --------------------------------------------------------

def test_f2_kaputtes_cookie_ist_kein_serverfehler():
    """Ein Oktal-Escape im Cookie ergab ein Nicht-ASCII-Zeichen, an dem
    `hmac.compare_digest` einen TypeError warf — vor jedem Router, als 500er
    samt Admin-Mail, deren Inhalt der Aufrufer über den Pfad bestimmte."""
    c = TestClient(app, raise_server_exceptions=False)
    r = c.get("/api/auth/me", headers={"Cookie": 'access_token="a.b.\\351"'})
    assert r.status_code == 401


# --- F9: gesperrte Admins -----------------------------------------------------

def test_f9_ein_gesperrtes_admin_konto_ist_gesperrt():
    """Die Ausnahme „Admins sind immer aktiv" galt auch für `disabled` — ein
    gesperrtes Admin-Konto arbeitete einfach weiter."""
    erster = _konto("admin@test.de")
    grant_admin("admin@test.de", RATSLOTSE_DB)
    zweiter = _konto("zweiter@test.de")
    grant_admin("zweiter@test.de", RATSLOTSE_DB)
    zweiter_id = next(u["id"] for u in erster.get("/api/admin/users").json()
                      if u["email"] == "zweiter@test.de")
    assert erster.put(f"/api/admin/users/{zweiter_id}/status",
                      json={"status": "disabled"}).status_code == 200

    r = zweiter.get("/api/admin/users")
    assert r.status_code == 403 and "deaktiviert" in r.json()["detail"]
    # Und kann sich nicht selbst wieder freischalten.
    assert zweiter.put(f"/api/admin/users/{zweiter_id}/status",
                       json={"status": "active"}).status_code == 403


# --- F14/F20/F21/F22: was ein Passwortwechsel beendet --------------------------

def test_f14_f20_f21_f22_reset_beendet_geraete_links_und_kalender():
    store = Store(RATSLOTSE_DB)
    try:
        uid = store.create_web_user("opfer@test.de", "x", "user", "active", email_verified=True)
        store.add_push_token(uid, "geraet-des-angreifers", "ios")
        alt = store.calendar_token(uid)
        exp = (datetime.utcnow() + timedelta(hours=1)).isoformat(timespec="seconds")
        store.create_password_reset(uid, "reset-hash", exp)

        store.increment_token_version(uid)

        assert store.get_push_tokens_for_owner(uid) == []
        assert store.user_by_calendar_token(alt) is None
        assert store.calendar_token(uid) not in (None, alt)  # neu angelegt
        now = datetime.utcnow().isoformat(timespec="seconds")
        assert store.consume_password_reset("reset-hash", now) is None
    finally:
        store.close()


def test_f22_adresswechsel_verwirft_offene_reset_links():
    store = Store(RATSLOTSE_DB)
    try:
        uid = store.create_web_user("alt@test.de", "x", "user", "active", email_verified=True)
        exp = (datetime.utcnow() + timedelta(hours=1)).isoformat(timespec="seconds")
        store.create_password_reset(uid, "reset-alt", exp)
        store.update_email(uid, "neu@test.de")
        now = datetime.utcnow().isoformat(timespec="seconds")
        assert store.peek_password_reset("reset-alt", now) is None
    finally:
        store.close()


def test_f22_ein_reset_link_greift_genau_einmal():
    store = Store(RATSLOTSE_DB)
    try:
        uid = store.create_web_user("einmal@test.de", "x", "user", "active", email_verified=True)
        exp = (datetime.utcnow() + timedelta(hours=1)).isoformat(timespec="seconds")
        store.create_password_reset(uid, "einmal", exp)
        now = datetime.utcnow().isoformat(timespec="seconds")
        assert store.consume_password_reset("einmal", now) == uid
        assert store.consume_password_reset("einmal", now) is None
    finally:
        store.close()


# --- F5/F17: Recherche-Plätze -----------------------------------------------

def test_f5_ein_konto_belegt_hoechstens_einen_platz():
    """Der Platz wird VOR dem langsamen Teil belegt — ein zweiter Start
    desselben Kontos sieht ihn, auch wenn noch kein Job registriert ist."""
    try:
        assert deepresearch.platz_reservieren(4711) is None
        assert deepresearch.platz_reservieren(4711) == "konto"
    finally:
        deepresearch.platz_freigeben(4711)
    assert deepresearch.platz_reservieren(4711) is None
    deepresearch.platz_freigeben(4711)


def test_f5_der_globale_deckel_zaehlt_reservierungen_mit():
    belegt = list(range(9000, 9000 + deepresearch.MAX_PARALLEL))
    try:
        for uid in belegt:
            assert deepresearch.platz_reservieren(uid) is None
        assert deepresearch.platz_reservieren(9999) == "voll"
    finally:
        for uid in belegt:
            deepresearch.platz_freigeben(uid)


def test_f17_ein_teilbericht_aus_vollem_material_ist_ein_bericht():
    job = deepresearch.DeepJob(id="x", user_id=1, question="Frage")
    job.facetten_gesamt, job.facetten_fertig = 5, 5
    assert deepresearch.material_vollstaendig(job)
    job.facetten_fertig = 4
    assert not deepresearch.material_vollstaendig(job)


# --- F7/F23: der Stadt-Link ---------------------------------------------------

@pytest.mark.parametrize("roh", [
    "https://phish.example\\.oldenburg.de/login",
    "https://evil.example\\@www.oldenburg.de/",
    "https://@www.oldenburg.de/",
    "https://www.oldenburg.de:8443/",
    "https://www.oldenburg.de/a b",
    "http://www.oldenburg.de/",
])
def test_f7_mehrdeutige_adressen_fliegen_raus(roh):
    assert _stadt_link(roh) is None


def test_f7_echte_adressen_kommen_aufgeloest_durch():
    assert _stadt_link("https://WWW.Oldenburg.de/presse/x?id=1") == \
        "https://www.oldenburg.de/presse/x?id=1"


# --- F4: Links im geteilten Text ----------------------------------------------

@pytest.mark.parametrize("text", [
    "[Vorlage (PDF)](https\\://buergerinfo-oldenburg.example/login)",
    "[Anrufen](tel:+491234)",
    "[x](https&#58;//evil.example)",
    "Mehr unter <sms:+491234>",
])
def test_f4_markdown_links_werden_nicht_geteilt(text):
    assert _share_text_is_objectionable(text)


def test_f4_belegnummern_bleiben_erlaubt():
    assert not _share_text_is_objectionable("Der Rat hat [123] (2024) zugestimmt, um 12:30 Uhr.")


# --- F10/F24: das Diagramm-Jahr -----------------------------------------------

def test_f10_ein_jahr_ausserhalb_jeder_vernunft_wird_verworfen():
    """`2^63` legte die iOS-App bei jedem Öffnen des geteilten Links lahm."""
    gross = {"series": [{"year": 9223372036854775807, "value": 1},
                        {"year": 2020, "value": 2}]}
    assert _grafik_pruefen(gross) is None
    unendlich = {"series": [{"year": 2020, "value": "inf"}, {"year": 2021, "value": 2}]}
    assert _grafik_pruefen(unendlich) is None
    gut = {"series": [{"year": 2020, "value": 1}, {"year": 2021, "value": 2}]}
    assert _grafik_pruefen(gut)["series"][0]["year"] == 2020


# --- F19: Massenmeldungen ------------------------------------------------------

def test_f19_wer_massenhaft_meldet_zaehlt_nicht_mehr():
    store = CouncilStore(COUNCIL_DB)
    try:
        for i in range(PROJECT_REPORTS_PER_ACCOUNT + 1):
            store.save_district_project_report(f"vorhaben-{i}", "kreyenbrueck", 1, None)
        assert store.district_project_report_count("vorhaben-0") == 0
        store.save_district_project_report("vorhaben-0", "kreyenbrueck", 2, None)
        assert store.district_project_report_count("vorhaben-0") == 1
    finally:
        store.close()


# --- F25: kein Zwischenspeicher für persönliche Antworten ----------------------

def test_f25_angemeldete_api_antworten_sind_no_store():
    c = _konto("cache@test.de")
    assert c.get("/api/auth/me").headers.get("cache-control") == "no-store"
    # Ohne Sitzung bleibt alles, wie es war.
    assert TestClient(app).get("/api/health").headers.get("cache-control") != "no-store"


# --- F26: Modelltext in der Tagesordnungs-Mail ---------------------------------

def test_f26_der_satz_unter_einem_top_ist_maskiert():
    from scripts.check_committees import top_block
    block = top_block("Ö 6", "Titel", '<a href="https://evil.example">Jetzt abstimmen</a>')
    assert "<a href" not in block and "&lt;a href" in block


def test_f26_vorabend_meldung_maskiert_gremium_und_ort():
    from council.abendmeldungen import _n5_text
    _, html = _n5_text({"committee": "<b>Rat</b>", "session_date": "2026-10-08",
                        "location": "<img src=x>"}, [])
    assert "<img" not in html and "<b>Rat" not in html
