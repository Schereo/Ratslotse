"""Beschluss-Seite und Personenverzeichnis: schlanker laden, gleich anzeigen.

Zwei Antworten, die das Web bis 11/2026 aus viel größeren zusammensuchte:

* die Nachbar-TOPs eines Beschlusses (vorher: die ganze Sitzung, 69 KB, eine
  eigene Wasserfall-Stufe) — jetzt ``neighbors`` am Beschluss selbst;
* die Verwaltungsleute mit Amt im Personenverzeichnis (vorher: das ganze
  Personen-Lexikon, 263 KB, für acht Einträge) — jetzt
  ``/people-directory?administration=true``.

Beide müssen GENAU das liefern, was der Browser vorher selbst ausrechnete;
sonst stünde auf derselben Seite eine andere Reihenfolge oder ein anderer
Personenkreis.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1] / "web" / "backend"
sys.path.insert(0, str(_BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import council as council_router  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from council.scraper import CouncilSession  # noqa: E402

COUNCIL_DB = os.environ["COUNCIL_DB"]


@pytest.fixture(autouse=True)
def fresh_dbs():
    for base in (os.environ["RATSLOTSE_DB"], COUNCIL_DB):
        for suffix in ("", "-wal", "-shm"):
            Path(base + suffix).unlink(missing_ok=True)
    yield


@pytest.fixture
def client():
    return TestClient(app)


def _beschluss(cs: CouncilStore, ksinr: int, position: int, nummer: str | None,
               kind: str = "decision") -> int:
    cs._insert_decision(ksinr, position, kind, None, nummer, f"Punkt {nummer}", "Text.",
                        "accepted", None, None, None, [], None, None, None)
    return cs._conn.execute(
        "SELECT id FROM council_decisions WHERE ksinr = ? AND position = ?",
        (ksinr, position)).fetchone()[0]


def test_nachbarn_in_der_reihenfolge_der_top_nummern(client):
    """Nach TOP-Nummer wie `localeCompare(…, {numeric: true})`, nicht nach
    Protokoll-Position und nicht lexikografisch: „4" vor „6.1", „6.2" vor
    „6.10". Subvotes zählen nicht mit und bekommen keine Leiste."""
    cs = CouncilStore(COUNCIL_DB)
    cs.save_session(CouncilSession(501, "Rat", "2026-06-01", "18:00", "Rathaus"))
    ids = {
        "6.1": _beschluss(cs, 501, 0, "6.1"),
        "6.10": _beschluss(cs, 501, 1, "6.10"),
        "4": _beschluss(cs, 501, 2, "4"),
        "6.2": _beschluss(cs, 501, 3, "6.2"),
    }
    sub = _beschluss(cs, 501, 4, "6.2", kind="subvote")
    cs._conn.commit()
    cs.close()

    n = client.get(f"/api/council/decision/{ids['6.2']}").json()["neighbors"]
    assert n["position"] == 3 and n["total"] == 4
    assert n["prev"] == {"id": ids["6.1"], "item_number": "6.1", "title": "Punkt 6.1"}
    assert n["next"] == {"id": ids["6.10"], "item_number": "6.10", "title": "Punkt 6.10"}

    erster = client.get(f"/api/council/decision/{ids['4']}").json()["neighbors"]
    assert erster["position"] == 1 and erster["prev"] is None
    assert erster["next"]["id"] == ids["6.1"]
    letzter = client.get(f"/api/council/decision/{ids['6.10']}").json()["neighbors"]
    assert letzter["position"] == 4 and letzter["next"] is None

    assert client.get(f"/api/council/decision/{sub}").json()["neighbors"] is None


def test_einzelner_beschluss_hat_keine_nachbarn(client):
    cs = CouncilStore(COUNCIL_DB)
    cs.save_session(CouncilSession(502, "Bauausschuss", "2026-06-02", "17:00", "Rathaus"))
    did = _beschluss(cs, 502, 0, None)
    cs._conn.commit()
    cs.close()
    n = client.get(f"/api/council/decision/{did}").json()["neighbors"]
    assert n == {"position": 1, "total": 1, "prev": None, "next": None}


def test_natuerliche_sortierung_kennt_alle_formen_des_bestands():
    """Die Formen aus dem Abzug (11/2026): „9", „9.9", „9.9.9", „9.9/9.9",
    „Ö9" und fehlende Nummern — Text und Zahl stehen im Schlüssel immer an
    derselben Stelle, der Vergleich wirft also nie ``TypeError``."""
    nummern = ["Ö9", "10.2/10.3", "10.2", "15.10", None, "15.9", "4", "13.1.1", "13.1"]
    ordnung = sorted(nummern, key=CouncilStore._natural_item_key)
    assert ordnung == [None, "4", "10.2", "10.2/10.3", "13.1", "13.1.1", "15.9", "15.10", "Ö9"]


def test_personenverzeichnis_nur_verwaltung_mit_amt(client, monkeypatch):
    """Dieselbe Bedingung, die vorher im Browser stand (`art === "city" &&
    role`) — und die zwischengespeicherte Liste bleibt dabei unangetastet."""
    lexikon = [
        {"slug": "a", "name": "Anna Amt", "art": "city", "role": "Stadtbaurätin"},
        {"slug": "b", "name": "Bert Ohne", "art": "city", "role": None},
        {"slug": "c", "name": "Cora Rat", "art": "council", "role": "Ratsfrau"},
        {"slug": "d", "name": "Dirk Dezernent", "art": "city", "role": "Dezernent"},
    ]
    monkeypatch.setitem(council_router._PERSONEN_LEXIKON_CACHE, "daten", lexikon)
    monkeypatch.setitem(council_router._PERSONEN_LEXIKON_CACHE, "as_of", time.time())

    voll = client.get("/api/council/people-directory")
    assert [p["slug"] for p in voll.json()["people"]] == ["a", "b", "c", "d"]

    schmal = client.get("/api/council/people-directory?administration=true")
    assert schmal.status_code == 200
    assert [p["slug"] for p in schmal.json()["people"]] == ["a", "d"]
    assert schmal.headers["cache-control"] == voll.headers["cache-control"]
    assert len(council_router._PERSONEN_LEXIKON_CACHE["daten"]) == 4
