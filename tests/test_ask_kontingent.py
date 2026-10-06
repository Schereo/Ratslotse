"""Kostenbremsen an Frag den Rat (Review 05.10.2026).

- ``/ask`` hat ein Tageskontingent je Konto (``qa.TAGES_KONTINGENT``) — bis
  dahin nur 10 Fragen in 10 Minuten, also 1.440 am Tag.
- ``party-meinungen`` und ``debates`` zählen je KONTO statt je Adresse.
- Eine überlange Frage wird gekappt, nicht abgewiesen und nicht ganz verarbeitet.
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
from app.ratelimit import debatten_limiter, partei_meinungen_limiter  # noqa: E402
from council import qa  # noqa: E402
from kern.store import Store  # noqa: E402

RATSLOTSE_DB = os.environ["RATSLOTSE_DB"]
COUNCIL_DB = os.environ["COUNCIL_DB"]


@pytest.fixture(autouse=True)
def fresh_dbs():
    for base in (RATSLOTSE_DB, COUNCIL_DB):
        for suffix in ("", "-wal", "-shm"):
            Path(base + suffix).unlink(missing_ok=True)
    yield


@pytest.fixture
def client():
    c = TestClient(app)
    r = c.post("/api/auth/register", json={"display_name": "Testkonto",
                                           "email": "frager@example.org",
                                           "password": "password123"})
    assert r.status_code == 201, r.text
    return c


def _konto_id() -> int:
    s = Store(RATSLOTSE_DB)
    try:
        return s._conn.execute("SELECT id FROM web_users WHERE email = ?",
                               ("frager@example.org",)).fetchone()[0]
    finally:
        s.close()


def _fragen_heute(n: int) -> None:
    s = Store(RATSLOTSE_DB)
    try:
        for _ in range(n):
            s.record_activity(_konto_id(), qa.KONTINGENT_MERKMAL, "web")
    finally:
        s.close()


def _antwort_ohne_modell(monkeypatch):
    from app.routers import council as council_router
    cand = [{"id": 5, "title": "Radverkehrsplan", "summary": "Ausbau", "outcome": "accepted",
             "session_date": "2026-07-02", "committee": "Rat", "score": 1.0}]
    monkeypatch.setattr(council_router, "_qa_retrieve", lambda *a, **k: (cand, "semantisch"))
    monkeypatch.setattr(qa, "analyse_query",
                        lambda q, **k: {"terms": q, "kind": "topic", "standalone": q})
    monkeypatch.setattr(qa, "answer_stream", lambda *a, **k: iter(["Antwort [5]."]))
    gesehen = {}
    echt = council_router.qa.verlauf_ohne_dieselbe_frage

    def merke(verlauf, frage):
        gesehen["frage"] = frage
        return echt(verlauf, frage)
    monkeypatch.setattr(qa, "verlauf_ohne_dieselbe_frage", merke)
    return gesehen


def test_das_tageskontingent_bremst_mit_einem_satz(client, monkeypatch):
    _antwort_ohne_modell(monkeypatch)
    _fragen_heute(qa.TAGES_KONTINGENT)
    r = client.post("/api/council/ask", json={"question": "Was ist mit Radwegen?"})
    assert r.status_code == 429
    detail = r.json()["detail"]
    # Der Satz ist für Menschen: Die ausgelieferte App zeigt `detail` wörtlich,
    # das Web erkennt das Kontingent an „Für heute" (lib/frage-limit.ts).
    assert detail == qa.KONTINGENT_TEXT and detail.startswith("Für heute")
    assert str(qa.TAGES_KONTINGENT) in detail
    # Kein Retry-After: Die App sperrte das Eingabefeld sonst bis Mitternacht.
    assert "retry-after" not in {k.lower() for k in r.headers}


def test_unter_dem_kontingent_geht_es_weiter(client, monkeypatch):
    _antwort_ohne_modell(monkeypatch)
    _fragen_heute(qa.TAGES_KONTINGENT - 1)
    with client.stream("POST", "/api/council/ask", json={"question": "Was ist mit Radwegen?"}) as r:
        assert r.status_code == 200
        "".join(r.iter_text())
    # Diese Frage zählt mit — die nächste ist die eine zu viel.
    assert client.post("/api/council/ask",
                       json={"question": "Und die Kosten?"}).status_code == 429


def test_ein_befreites_konto_hat_kein_tageskontingent(client, monkeypatch):
    _antwort_ohne_modell(monkeypatch)
    _fragen_heute(qa.TAGES_KONTINGENT + 5)
    s = Store(RATSLOTSE_DB)
    s._conn.execute("UPDATE web_users SET limits_unlocked = 1 WHERE id = ?", (_konto_id(),))
    s._conn.commit()
    s.close()
    with client.stream("POST", "/api/council/ask", json={"question": "Was ist mit Radwegen?"}) as r:
        assert r.status_code == 200


def test_eine_ueberlange_frage_wird_gekappt_nicht_abgewiesen(client, monkeypatch):
    """200 kB kosteten 8,6 s CPU; jetzt kommen 300 Zeichen an — und die
    ausgelieferte App, die evtl. länger schickt, bekommt keinen 422."""
    gesehen = _antwort_ohne_modell(monkeypatch)
    t0 = time.monotonic()
    with client.stream("POST", "/api/council/ask",
                       json={"question": "Radwege " * 25_000}) as r:
        assert r.status_code == 200
        "".join(r.iter_text())
    assert len(gesehen["frage"]) <= 300
    assert time.monotonic() - t0 < 5


def test_bausteine_zaehlen_je_konto_nicht_je_adresse(client, monkeypatch):
    """Zwei Konten hinter derselben Adresse (Mobilfunk-NAT) teilen sich die
    Bremse nicht mehr — und ein Konto kommt über einen Adresswechsel nicht
    an ihr vorbei."""
    monkeypatch.delenv("DISABLE_RATE_LIMIT", raising=False)
    from council import embeddings as emb
    monkeypatch.setattr(emb, "search_wortbeitraege_je_fraktion", lambda *a, **k: [])
    monkeypatch.setattr(emb, "search_wortbeitraege", lambda *a, **k: [])
    for limiter, pfad in ((partei_meinungen_limiter, "/api/council/party-meinungen"),
                          (debatten_limiter, "/api/council/debates")):
        limiter._calls.clear()
        try:
            for _ in range(limiter.max_calls):
                assert client.post(pfad, json={"question": "Stadion?"}).status_code == 200
            assert client.post(pfad, json={"question": "Stadion?"}).status_code == 429
            assert set(limiter._calls) == {f"account:{_konto_id()}"}, limiter._calls.keys()
        finally:
            limiter._calls.clear()
