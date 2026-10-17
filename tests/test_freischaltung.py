"""Manuelle Freischaltung neuer Konten (``SIGNUP_REQUIRES_APPROVAL``).

Anlass (17.10.2026): dev.ratslotse.de ist seitdem ohne Basic-Auth erreichbar,
verschickt aber keine Mail — ohne den Schalter wäre jedes neue Konto dort
sofort aktiv, auf dem Dev-Schlüssel fürs Sprachmodell. Diese Datei hält fest:

* ohne Schalter bleibt alles wie es war (kein Mailversand → sofort aktiv),
* mit Schalter beginnt ein Konto als ``disabled`` und kommt an die angemeldete
  Fläche erst nach der Freischaltung durch einen Admin — mit 403, nicht 401.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1] / "web" / "backend"
sys.path.insert(0, str(_BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from kern.store import Store  # noqa: E402

RATSLOTSE_DB = os.environ["RATSLOTSE_DB"]
COUNCIL_DB = os.environ["COUNCIL_DB"]


@pytest.fixture(autouse=True)
def fresh_dbs():
    for base in (RATSLOTSE_DB, COUNCIL_DB):
        for suffix in ("", "-wal", "-shm"):
            Path(base + suffix).unlink(missing_ok=True)
    yield


def _registrieren(client: TestClient, email: str):
    return client.post("/api/auth/register", json={
        "email": email, "password": "password123", "display_name": "Testperson"})


def test_ohne_schalter_sofort_aktiv():
    client = TestClient(app)
    r = _registrieren(client, "neu@example.org")
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "active"
    assert client.get("/api/topics").status_code == 200


def test_mit_schalter_wartet_das_konto(monkeypatch):
    monkeypatch.setattr(get_settings(), "signup_requires_approval", True)
    client = TestClient(app)
    r = _registrieren(client, "wartet@example.org")
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "disabled"
    gesperrt = client.get("/api/topics")
    assert gesperrt.status_code == 403
    assert gesperrt.json()["detail"] == "Dein Konto wartet auf Freischaltung."

    # Freischalten über denselben Weg wie das Admin-Panel.
    store = Store(RATSLOTSE_DB)
    store.set_web_user_status(r.json()["id"], "active")
    assert client.get("/api/topics").status_code == 200
