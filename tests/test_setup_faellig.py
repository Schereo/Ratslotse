"""Wer bekommt den Einrichtungs-Assistenten zu sehen? (`setup.pending`)

Die Regel steht im Backend, nicht im Frontend — Web und App sollen dieselbe
Antwort bekommen, und sie hängt an Daten (Themen, Abos), die ein Frontend erst
in zwei zusätzlichen Requests holen müsste, bevor es weiß, ob es überhaupt
etwas anzeigen soll.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web" / "backend"))

# `fresh_dbs` muss mit — die autouse-Fixture wirkt nur in ihrem eigenen Modul.
from tests.test_backend_api import _register, app, fresh_dbs  # noqa: E402,F401


@pytest.fixture
def client():
    return TestClient(app)


def _stand(client) -> dict:
    return client.get("/api/onboarding/setup").json()


def test_frisches_konto_ist_faellig(client):
    _register(client)
    assert _stand(client)["pending"] is True


def test_abgeschlossen_kommt_nie_wieder(client):
    """„Überspringen" zählt als abgeschlossen — ein weggeklickter Assistent,
    der wiederkommt, wäre keiner."""
    _register(client)
    client.post("/api/onboarding/setup", json={"step": 3, "done": True})
    assert _stand(client)["pending"] is False


def test_abgebrochen_wird_fortgesetzt(client):
    _register(client)
    client.post("/api/onboarding/setup", json={"step": 2, "done": False})
    stand = _stand(client)
    assert stand["pending"] is True and stand["step"] == 2


def test_abgebrochen_bleibt_faellig_trotz_thema(client):
    """Wer mitten im Assistenten ein Thema anlegt, ist deshalb nicht fertig.

    Der Assistent LEGT Themen an — würde ein vorhandenes Thema ihn beenden,
    verschwände er nach dem ersten Anlegen mitten im Ablauf.
    """
    _register(client)
    client.post("/api/onboarding/setup", json={"step": 2, "done": False})
    r = client.post("/api/topics", json={"name": "Cäcilienbrücke", "description": "Brücke"})
    assert r.status_code in (200, 201), r.text
    assert _stand(client)["pending"] is True


def test_eingerichtetes_bestandskonto_bleibt_verschont(client):
    """Wer nie im Assistenten war, aber längst Themen hat, hat sich erkennbar
    selbst eingerichtet — der wird nicht nachträglich durchgeschickt."""
    _register(client)
    assert _stand(client)["pending"] is True          # noch leer → fällig
    client.post("/api/topics", json={"name": "Fliegerhorst", "description": "Konversion"})
    assert _stand(client)["pending"] is False         # jetzt nicht mehr


def test_ein_abo_allein_reicht_auch(client):
    """Abo statt Thema — dieselbe Aussage: hier hat sich jemand eingerichtet."""
    _register(client)
    r = client.post("/api/subscriptions", json={"committee_name": "Verkehrsausschuss"})
    assert r.status_code in (200, 201, 204), r.text
    assert _stand(client)["pending"] is False


def test_faelligkeit_gilt_je_konto(client):
    """Zwei Konten, zwei Antworten — sonst risse ein eingerichtetes Konto den
    Assistenten für alle anderen mit weg."""
    _register(client)
    client.post("/api/topics", json={"name": "Hafen", "description": "Hafenentwicklung"})
    assert _stand(client)["pending"] is False

    zweiter = TestClient(app)
    _register(zweiter, email="bob@example.org")
    assert _stand(zweiter)["pending"] is True
