"""Eine Karte, deren Features aus sind, lässt sich nicht verschicken.

Ansehen ja (Testzustellung an sich selbst), ankündigen nein. Gegenstück zur
Regel in ``kern/releases.py::pending_for`` — dort sieht niemand die Karte,
hier geht sie nicht als Mail und Push hinaus.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from kern import releases  # noqa: E402
from kern.store import Store  # noqa: E402

RATSLOTSE_DB = os.environ["RATSLOTSE_DB"]


@pytest.fixture(autouse=True)
def frisch():
    for suffix in ("", "-wal", "-shm"):
        Path(RATSLOTSE_DB + suffix).unlink(missing_ok=True)
    yield


def _admin(client: TestClient) -> None:
    email = "admin@example.org"
    r = client.post("/api/auth/register", json={"display_name": "Admin", "email": email,
                                                 "password": "password123"})
    assert r.status_code == 201, r.text
    store = Store(RATSLOTSE_DB)
    try:
        store.set_web_user_roles(store.get_web_user_by_email(email)["id"], ["admin"])
    finally:
        store.close()
    client.post("/api/auth/login", json={"email": email, "password": "password123"})


def test_gesperrte_karte_wird_nicht_verschickt(monkeypatch):
    karte = next(r for r in releases.RELEASES if r.schalter)
    client = TestClient(app)
    _admin(client)
    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    r = client.post(f"/api/admin/news/{karte.version}/send")
    assert r.status_code == 409, r.text
    assert karte.schalter[0] in r.json()["detail"]

    monkeypatch.setenv("FEATURE_FLAGS", ",".join(karte.schalter))
    r = client.post(f"/api/admin/news/{karte.version}/send")
    assert r.status_code == 200, r.text
