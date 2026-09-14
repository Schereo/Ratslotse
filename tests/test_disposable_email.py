"""Wegwerf-Adressen bei Registrierung und Adresswechsel abweisen.

Anlass (12./13.09.2026, Prod): zwei Konten mit Tastatur-Namen auf 94an.com
und airhemp.com, beide mit bestätigter Adresse — die Bestätigungs-Mail hält
Wegwerf-Postfächer nicht ab. Diese Datei hält fest:

* die Erkennung samt Eltern-Domains und Schreibweise,
* dass echte Anbieter (und Apples „E-Mail verbergen") nie erwischt werden —
  auch nicht, wenn ein Nachziehen der Liste sie hereinschwemmen sollte,
* dass die Liste im Repo sauber ist (Form, Dubletten, Umfang),
* die beiden Endpunkte: Registrierung und Adresswechsel weisen mit demselben
  deutschen Satz ab, und es entsteht kein Konto.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1] / "web" / "backend"
sys.path.insert(0, str(_BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from kern import disposable_email as de  # noqa: E402

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
def client():
    return TestClient(app)


# --- Erkennung ---------------------------------------------------------------
#
# Die Tests nennen nur DOMAINS und setzen die Adresse zur Laufzeit zusammen:
# `scripts/lint_adressen.py` lässt im Repo nur Adressen auf eigenen Domains
# zu, und eine Prüfung fremder Anbieter braucht nun einmal fremde Domains.

def _adresse(domain: str, lokal: str = "x") -> str:
    return f"{lokal}@{domain}"


@pytest.mark.parametrize("domain", [
    "94an.com",                     # die beiden Konten vom 12./13.09.2026
    "airhemp.com",
    "mail.94an.com",                # Eltern-Domain zählt
    "mailinator.com",
])
def test_wegwerf_adressen_werden_erkannt(domain):
    assert de.is_disposable(_adresse(domain))
    assert de.is_disposable(f"  {_adresse(domain.upper(), 'X')}  ")   # Schreibweise und Rand egal


@pytest.mark.parametrize("domain", [
    "example.org",
    "ratslotse.de",
    "privaterelay.appleid.com",     # Apples „E-Mail verbergen"
    "web.de", "gmx.de", "t-online.de", "hotmail.de", "gmail.com",
    "stadt.oldenburg.de",           # Unter-Domain eines geschützten Anbieters
])
def test_echte_anbieter_bleiben_frei(domain):
    assert not de.is_disposable(_adresse(domain))


@pytest.mark.parametrize("kaputt", ["kein-at", "", "@", "x@"])
def test_ohne_domain_keine_wegwerf_adresse(kaputt):
    """Die Formprüfung ist Sache von ``EmailStr`` — hier nur nicht stolpern."""
    assert not de.is_disposable(kaputt)


def test_geschuetzte_anbieter_gewinnen_gegen_die_liste(monkeypatch):
    """Sollte ein Nachziehen einen echten Anbieter hereinschwemmen, gewinnt
    ``PROTECTED_DOMAINS`` — der Riegel darf nie ganze Postfach-Anbieter sperren."""
    monkeypatch.setattr(de, "blocked_domains", lambda: frozenset({"gmail.com", "94an.com"}))
    assert not de.is_disposable(_adresse("gmail.com"))
    assert de.is_disposable(_adresse("94an.com"))


def test_domain_of():
    assert de.domain_of("A@Example.ORG") == "example.org"
    assert de.domain_of("a@b@example.org") == "example.org"
    assert de.domain_of("ohne") == ""


# --- Die Liste im Repo ---------------------------------------------------------

def test_liste_ist_sauber():
    zeilen = [z for z in de.LIST_PATH.read_text(encoding="utf-8").splitlines()
              if z.strip() and not z.startswith("#")]
    domain = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$")
    kaputt = [z for z in zeilen if not domain.match(z)]
    assert not kaputt, kaputt[:5]
    assert len(zeilen) == len(set(zeilen)), "Dubletten in der Liste"
    assert len(zeilen) > 5000, "Liste unerwartet klein — Nachziehen schiefgegangen?"
    assert de.LIST_PATH.read_text(encoding="utf-8").startswith("# "), "Kopf mit Quelle/Lizenz fehlt"


def test_kein_geschuetzter_anbieter_steht_in_der_liste():
    """Nicht, weil er dann gesperrt wäre (die Menge gewinnt) — sondern weil ein
    solcher Eintrag heißt, dass die Liste jemanden Echtes erwischt hat."""
    assert not (de.blocked_domains() & de.PROTECTED_DOMAINS)


def test_liste_wird_nur_einmal_gelesen():
    assert de.blocked_domains() is de.blocked_domains()


# --- Die Endpunkte -----------------------------------------------------------

def _register(client, email, name="Testkonto"):
    return client.post("/api/auth/register",
                       json={"display_name": name, "email": email, "password": PASSWORT})


def test_registrierung_weist_wegwerf_adresse_ab(client):
    wegwerf = _adresse("94an.com")
    r = _register(client, wegwerf)
    assert r.status_code == 422, r.text
    assert r.json()["detail"] == de.DISPOSABLE_EMAIL_MESSAGE
    # Es ist kein Konto entstanden: Die Anmeldung mit denselben Daten scheitert.
    login = client.post("/api/auth/login", json={"email": wegwerf, "password": PASSWORT})
    assert login.status_code == 401


def test_registrierung_mit_dauerhafter_adresse_geht_weiter(client):
    r = _register(client, "echt@example.org")
    assert r.status_code == 201, r.text
    assert r.json()["email"] == "echt@example.org"


def test_adresswechsel_auf_wegwerf_adresse_scheitert(client):
    """Sonst wäre der Wechsel der Umweg um den Riegel."""
    assert _register(client, "echt@example.org").status_code == 201
    r = client.post("/api/account/change-email",
                    json={"new_email": _adresse("airhemp.com"), "current_password": PASSWORT})
    assert r.status_code == 422, r.text
    assert r.json()["detail"] == de.DISPOSABLE_EMAIL_MESSAGE
    assert client.get("/api/auth/me").json()["email"] == "echt@example.org"
