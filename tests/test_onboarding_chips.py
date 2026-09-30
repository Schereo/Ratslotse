"""Der Zähler des Einrichtungs-Assistenten: was angeboten und was gewählt wird.

Die Zusagen, die hier gehalten werden: Es landet nur auf der Positivliste in
der Tabelle (kein Stadtteil-, Straßen- oder selbst getippter Themenname), es
wird je Tag und Chip gezählt, und ein Konto ist dafür nötig.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web" / "backend"))

from kern.store import Store  # noqa: E402
from tests.test_backend_api import _register, app  # noqa: E402
from tests.test_stadtteil_vorschlaege import _pfade  # noqa: E402
from scripts.onboarding_chips import bericht  # noqa: E402


@pytest.fixture(autouse=True)
def frische_dbs():
    for basis in _pfade():
        for endung in ("", "-wal", "-shm"):
            Path(basis + endung).unlink(missing_ok=True)
    yield


@pytest.fixture
def client():
    return TestClient(app)


def _stand(tage: str = "2000-01-01") -> dict[str, tuple[int, int]]:
    store = Store(Path(_pfade()[0]))
    try:
        return {z["chip"]: (z["shown"], z["picked"]) for z in store.onboarding_chip_stats_since(tage)}
    finally:
        store.close()


def test_zaehlt_anzeigen_und_wahlen(client):
    _register(client)
    r = client.post("/api/onboarding/chips", json={
        "gezeigt": ["city_topic:cycling", "city_topic:pools", "district"],
        "gewaehlt": ["city_topic:cycling"]})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}
    client.post("/api/onboarding/chips", json={"gezeigt": ["city_topic:cycling"], "gewaehlt": []})
    assert _stand() == {
        "city_topic:cycling": (2, 1),
        "city_topic:pools": (1, 0),
        "district": (1, 0),
    }


def test_namen_und_unbekanntes_kommen_nicht_in_die_tabelle(client):
    """Die Tabelle darf weder erweitert noch mit Namen gefüllt werden."""
    _register(client)
    client.post("/api/onboarding/chips", json={
        "gezeigt": ["Eversten", "city_topic:gibt-es-nicht", "<script>", "city_topic:roads"],
        "gewaehlt": ["Kreyenbrück", "city_topic:roads"]})
    assert _stand() == {"city_topic:roads": (1, 1)}


def test_jeder_chip_zaehlt_je_aufruf_einmal(client):
    _register(client)
    client.post("/api/onboarding/chips", json={
        "gezeigt": ["district", "district", "district"], "gewaehlt": []})
    assert _stand() == {"district": (1, 0)}


def test_ohne_konto_nichts(client):
    r = client.post("/api/onboarding/chips", json={"gezeigt": ["district"], "gewaehlt": []})
    assert r.status_code in (401, 403)
    assert _stand() == {}


def test_jedes_stadtthema_ist_zaehlbar(client):
    """Ein neues Thema in ``CITY_TOPICS`` braucht keinen zweiten Eintrag."""
    from council.city_topics import CITY_TOPICS
    _register(client)
    keys = [f"city_topic:{t.key}" for t in CITY_TOPICS]
    client.post("/api/onboarding/chips", json={"gezeigt": keys[:60], "gewaehlt": []})
    assert set(_stand()) == set(keys)


def test_bericht_rechnet_die_quote():
    zeilen = bericht([
        {"chip": "city_topic:pools", "shown": 10, "picked": 4},
        {"chip": "district", "shown": 4, "picked": 10},
        {"chip": "eigen", "shown": 0, "picked": 0},
    ])
    assert zeilen[1].split() == ["district", "4", "10", "2.5×"]   # gewählt je Besuch, keine Quote über 100 %
    assert zeilen[2].split() == ["city_topic:pools", "10", "4", "40", "%"]
    assert zeilen[3].split()[-1] == "—"
