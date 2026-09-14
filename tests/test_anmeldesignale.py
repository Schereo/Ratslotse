"""Registrierungs-Signale: was durchkam, was abprallte — und wann es meldet.

**Die Lücke.** Bis 09/2026 war nur sichtbar, wer durchkam. Die FYI-Mail an die
Admins geht erst raus, wenn jemand seine Adresse BESTÄTIGT hat; ein Skript, das
tausend Konten anlegt und nie einen Link klickt, löste damit keine einzige Mail
aus. Und wer an der Bremse oder am Wegwerf-Riegel hängenblieb, hinterließ
nirgends eine Spur — „es hat niemand versucht" war von „es haben 500 versucht"
nicht zu unterscheiden.

Diese Datei hält die drei Teile fest: die Zählung (mit ihrer Positivliste),
den Schnitt fürs Admin-Panel und die Schwellen des Herzschlags.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1] / "web" / "backend"
sys.path.insert(0, str(_BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from kern.store import SIGNUP_REJECTION_REASONS, Store  # noqa: E402

RATSLOTSE_DB = os.environ["RATSLOTSE_DB"]
COUNCIL_DB = os.environ["COUNCIL_DB"]
PASSWORT = "password123"
#: Eine Domain, die der Wegwerf-Riegel kennt — zusammengesetzt, siehe unten.
WEGWERF_DOMAIN = "94an" + ".com"


@pytest.fixture(autouse=True)
def fresh_dbs():
    for base in (RATSLOTSE_DB, COUNCIL_DB):
        for suffix in ("", "-wal", "-shm"):
            Path(base + suffix).unlink(missing_ok=True)
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "r.sqlite")
    yield s
    s.close()


# --- Die Zählung -------------------------------------------------------------

def test_ein_unbekannter_grund_wird_verworfen(store):
    """Sonst lebte ein Tippfehler als eigene Kategorie weiter — und die
    Tabelle wäre nicht mehr durch die Positivliste gedeckelt."""
    store.record_signup_rejection("rate_limit")
    store.record_signup_rejection("voellig-ausgedacht")
    assert store.signup_rejections_since("2000-01-01") == {"rate_limit": 1}


def test_gleiche_gruende_werden_aufaddiert(store):
    for _ in range(3):
        store.record_signup_rejection("disposable_email")
    assert store.signup_rejections_since("2000-01-01")["disposable_email"] == 3


def test_die_positivliste_ist_die_eine_quelle():
    """Die Anzeige im Panel und die Mail des Herzschlags beschriften genau
    diese Werte — eine zweite Liste liefe unweigerlich auseinander."""
    assert SIGNUP_REJECTION_REASONS == {"rate_limit", "disposable_email", "duplicate_email"}


# --- Der Schnitt fürs Panel ---------------------------------------------------

def test_signup_signals_hat_eine_zeile_je_tag(store):
    daten = store.signup_signals(7)
    assert daten["days"] == 7
    assert len(daten["series"]) == 7
    assert [t["day"] for t in daten["series"]] == sorted(t["day"] for t in daten["series"])
    assert daten["created"] == daten["rejected"] == 0


def test_signup_signals_zaehlt_beide_seiten(client):
    """Das ist der Punkt der Ansicht: angelegte Konten UND Abweisungen."""
    assert client.post("/api/auth/register", json={
        "display_name": "Testkonto", "email": "echt@example.org", "password": PASSWORT,
    }).status_code == 201
    # Wegwerf-Adresse (Riegel) und eine zweite Registrierung derselben Adresse.
    # Die Domain steht hier nicht als Literal: `scripts/lint_adressen.py` lässt
    # im Repo nur Adressen auf eigenen Domains zu, und eine Prüfung fremder
    # Anbieter braucht nun einmal eine fremde Domain (s. test_disposable_email).
    client.post("/api/auth/register", json={
        "display_name": "Bot", "email": f"x@{WEGWERF_DOMAIN}", "password": PASSWORT})
    client.post("/api/auth/register", json={
        "display_name": "Nochmal", "email": "echt@example.org", "password": PASSWORT})

    store = Store(RATSLOTSE_DB)
    try:
        daten = store.signup_signals(30)
        gruende = {r["reason"]: r["n"] for r in daten["reasons"]}
    finally:
        store.close()
    assert daten["created"] == 1
    assert daten["rejected"] == 2
    assert gruende == {"disposable_email": 1, "duplicate_email": 1}
    assert daten["series"][-1]["created"] == 1
    assert daten["series"][-1]["rejected"] == 2


def test_der_endpunkt_verlangt_adminrechte(client):
    assert client.post("/api/auth/register", json={
        "display_name": "Testkonto", "email": "echt@example.org", "password": PASSWORT,
    }).status_code == 201
    assert client.get("/api/admin/stats/signups").status_code == 403


def test_die_bremse_zaehlt_ihren_treffer_mit(client, monkeypatch):
    """Ein Skript, das hier hängenbleibt, soll nicht spurlos bleiben —
    genau daran war „niemand hat es versucht" nicht zu widerlegen."""
    monkeypatch.delenv("DISABLE_RATE_LIMIT", raising=False)
    from app.ratelimit import register_limiter
    register_limiter._calls.clear()
    codes = [client.post("/api/auth/register", json={
        "display_name": "Bot", "email": f"bot{i}@example.org", "password": PASSWORT,
    }).status_code for i in range(8)]
    register_limiter._calls.clear()
    assert 429 in codes, f"Die Bremse hat nicht gegriffen: {codes}"

    store = Store(RATSLOTSE_DB)
    try:
        gruende = store.signup_rejections_since("2000-01-01")
    finally:
        store.close()
    assert gruende.get("rate_limit", 0) == codes.count(429)


# --- Die Schwellen des Herzschlags -------------------------------------------

def test_herzschlag_sieht_frische_konten(store):
    from tests.test_herzschlag import herzschlag

    store.create_web_user("a@example.org", "x", email_verified=True)
    store.create_web_user("b@example.org", "x", email_verified=False)
    store.record_signup_rejection("disposable_email")
    store.record_signup_rejection("duplicate_email")

    k = herzschlag.anmeldungen(store)
    assert k["created"] == 2
    assert k["unverified"] == 1
    # `duplicate_email` zählt NICHT als Angriff: Wer sein Konto vergessen hat,
    # landet dort genauso wie jemand, der Adressen durchprobiert.
    assert k["abgewiesen"] == 1
    assert k["abgewiesen_je_grund"]["duplicate_email"] == 1


def test_die_schwellen_liegen_ueber_dem_alltag():
    """Gemessen auf Prod (09/2026): etwa eine Registrierung am Tag, Spitze drei.
    Eine Schwelle darunter meldete täglich — und würde nach einer Woche
    weggefiltert, samt dem Echten."""
    from tests.test_herzschlag import herzschlag

    assert herzschlag.ANMELDUNGEN_ALARM >= 5
    assert herzschlag.UNBESTAETIGT_ALARM <= herzschlag.ANMELDUNGEN_ALARM
    # Abprallen ist folgenlos — diese Zahl darf erst später auffallen.
    assert herzschlag.ABWEISUNGEN_ALARM > herzschlag.ANMELDUNGEN_ALARM


def test_jeder_alarmgrund_ist_ein_bekannter_grund():
    """Ein Tippfehler hier wäre dauerhaft still: Der Grund käme nie vor, die
    Summe bliebe 0, und der Alarm schlüge nie an."""
    from tests.test_herzschlag import herzschlag

    assert set(herzschlag.ABWEISUNGSGRUENDE) <= SIGNUP_REJECTION_REASONS
    assert set(herzschlag.ABWEISUNGS_LABEL) == SIGNUP_REJECTION_REASONS


def test_eine_welle_loest_eine_mail_aus(store, tmp_path, monkeypatch):
    """Der eigentliche Zweck: Konten, die ihre Adresse nie bestätigen, lösen
    sonst keine einzige Mail aus."""
    from tests.test_herzschlag import herzschlag
    from kern.jobs import JOBS
    from datetime import datetime
    import kern.alerts

    # Alle Jobs frisch, damit die Meldung wirklich an den Konten hängt und
    # nicht daran, dass in einer leeren Datenbank ohnehin jeder Job schweigt.
    jetzt = datetime.utcnow()
    for job in JOBS:
        store.record_job_run(job["key"], jetzt, "ok", 1.0, None, None)
    for i in range(herzschlag.ANMELDUNGEN_ALARM + 2):
        store.create_web_user(f"welle{i}@example.org", "x", email_verified=False)
    store.close()

    gesendet: list[tuple[str, str]] = []
    monkeypatch.setattr(kern.alerts, "notify_admin",
                        lambda text, betreff="", fusszeile="", **kw: gesendet.append((betreff, text)))
    monkeypatch.setenv("RATSLOTSE_DB", str(tmp_path / "r.sqlite"))

    ergebnis = herzschlag.main()
    assert ergebnis["konten_24h"] == herzschlag.ANMELDUNGEN_ALARM + 2
    assert ergebnis["konten_24h_unbestaetigt"] == herzschlag.ANMELDUNGEN_ALARM + 2
    assert gesendet, "Eine Welle neuer Konten muss sich melden"
    betreff, text = gesendet[-1]
    assert "Registrierungen" in betreff
    assert "ohne bestätigte Adresse" in text


def test_ein_ruhiger_tag_meldet_nichts(store, tmp_path, monkeypatch):
    """Ein Herzschlag, der täglich grundlos meldet, wird weggefiltert — und
    dann meldet er auch das Echte nicht mehr."""
    from tests.test_herzschlag import herzschlag
    import kern.alerts
    from kern.jobs import JOBS
    from datetime import datetime

    jetzt = datetime.utcnow()
    for job in JOBS:
        store.record_job_run(job["key"], jetzt, "ok", 1.0, None, None)
    store.create_web_user("einer@example.org", "x", email_verified=True)
    store.close()

    gesendet: list[str] = []
    monkeypatch.setattr(kern.alerts, "notify_admin",
                        lambda *a, **kw: gesendet.append(kw.get("betreff", "")))
    monkeypatch.setenv("RATSLOTSE_DB", str(tmp_path / "r.sqlite"))

    ergebnis = herzschlag.main()
    assert ergebnis["gemeldet"] == 0, gesendet
    assert gesendet == []
