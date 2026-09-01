"""Das Live-Fenster einer Sitzung endet, wenn die nächste beginnt.

An Ratstagen tagen in Oldenburg drei Gremien **nacheinander** im selben Haus:
16:00 Ausschuss für Allgemeine Angelegenheiten, 16:30 Verwaltungsausschuss
(nichtöffentlich, steht nur im Kalender), 18:00 Rat. Es sind weitgehend
dieselben Leute — sie warten aufeinander und tagen nicht parallel (Tims Befund
31.08.2026).

Vorher galt in allen Clients ein pauschales Fenster von vier Stunden ab Start.
Um 18:30 lief damit rechnerisch alles drei gleichzeitig, und die Live-Karte
zeigte die erste davon: den Ausschuss, der seit zwei Stunden vorbei war.

Folgt keine weitere Sitzung, greift ein Deckel ab Beginn: drei Stunden für
Ausschüsse, vier für den Rat (Tims Maß 31.08.2026). Gerechnet wird er im
Server, damit er nicht in drei Clients verschieden altert.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

# Wie in test_backend_api.py: Backend importierbar machen und auf
# Wegwerf-Datenbanken zeigen, BEVOR die App importiert wird.
_BACKEND = Path(__file__).resolve().parents[1] / "web" / "backend"
sys.path.insert(0, str(_BACKEND))
_TMP = tempfile.mkdtemp()
os.environ["NWZ_DB"] = str(Path(_TMP) / "nwz.sqlite")
os.environ["COUNCIL_DB"] = str(Path(_TMP) / "council.sqlite")
os.environ["WEB_JWT_SECRET"] = "test-secret"
os.environ["COOKIE_SECURE"] = "false"
os.environ["DISABLE_RATE_LIMIT"] = "1"

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.deps import get_council_store, require_active  # noqa: E402
from app.routers import council as council_router  # noqa: E402
from council import live as live_mod  # noqa: E402
from council.scraper import AgendaItem, CouncilSession, ScheduledSession  # noqa: E402
from council.store import CouncilStore  # noqa: E402

HEUTE = date.today().isoformat()


def _ratstag_store(pfad: Path) -> CouncilStore:
    """Ein echter Ratstag: Ausschuss 16:00 · Verwaltungsausschuss 16:30 · Rat
    18:00 — die mittlere Sitzung kennt das RIS nur als Kalendertermin."""
    store = CouncilStore(pfad)
    store.save_session(CouncilSession(
        ksinr=1, committee="Ausschuss für Allgemeine Angelegenheiten",
        session_date=HEUTE, session_time="16:00", location="Kulturzentrum PFL",
        agenda_items=[AgendaItem(item_number="Ö 1", title="Bericht der Verwaltung")],
    ))
    store.save_session(CouncilSession(
        ksinr=2, committee="Rat", session_date=HEUTE, session_time="18:00",
        location="Kulturzentrum PFL",
        agenda_items=[
            AgendaItem(item_number="Ö 1", title="Haushaltssatzung 2027"),
            AgendaItem(item_number="Ö 2", title="Neubau der Kita Bloherfelde"),
            AgendaItem(item_number="Ö 3", title="Anträge der Fraktionen"),
        ],
    ))
    store.replace_scheduled_sessions([ScheduledSession(
        committee="Verwaltungsausschuss", session_date=HEUTE,
        session_time="16:30", location="Kulturzentrum PFL",
    )])
    return store


@pytest.fixture
def store(tmp_path):
    s = _ratstag_store(tmp_path / "council.sqlite")
    app.dependency_overrides[get_council_store] = lambda: s
    # Die Sitzungsliste hängt an einem Konto (sie markiert eigene Themen) —
    # hier zählt nur das Live-Fenster, deshalb ein gesetztes Konto von Hand.
    app.dependency_overrides[require_active] = lambda: {"id": 1, "role": "user", "status": "active"}
    council_router._HEUTE_CACHE.update(at=0.0, data=None)
    try:
        yield s
    finally:
        app.dependency_overrides.clear()
        council_router._HEUTE_CACHE.update(at=0.0, data=None)
        s.close()


def test_live_windows_verkettet_den_ratstag(store):
    """Jede Startzeit endet an der nächsten — die letzte bleibt offen."""
    assert store.live_windows(HEUTE) == {"16:00": "16:30", "16:30": "18:00"}
    # Für die letzte Sitzung des Tages steht hier nichts; ihr Ende rechnet
    # `council.live` aus dem Deckel.
    assert "18:00" not in store.live_windows(HEUTE)


def test_deckel_haengt_am_gremium():
    """Ausschüsse drei Stunden, der Rat vier — Tims Maß 31.08.2026."""
    assert live_mod.window_end("Verkehrsausschuss", "17:00") == "20:00"
    assert live_mod.window_end("Verwaltungsausschuss", "16:30") == "19:30"
    assert live_mod.window_end("Rat", "18:00") == "22:00"
    # Der Ortsrat ist kein Rat — sonst führte ein Teilstring-Abgleich in die
    # Irre („Beirat", „Integrationsbeirat" tragen ebenfalls „rat").
    assert live_mod.window_end("Ortsrat Eversten", "17:00") == "20:00"
    # Die Nachfolgerin schlägt den Deckel immer.
    assert live_mod.window_end("Rat", "18:00", "19:00") == "19:00"


def test_deckel_rechnet_nicht_ueber_mitternacht():
    """Ein Ende VOR dem Beginn könnte kein Client einordnen."""
    assert live_mod.window_end("Rat", "22:00") == "23:59"
    assert live_mod.window_end("Verkehrsausschuss", "21:30") == "23:59"
    assert live_mod.window_end("Verkehrsausschuss", "") is None
    assert live_mod.window_end("Verkehrsausschuss", "Uhrzeit folgt") is None


def test_live_windows_haelt_gleichzeitige_sitzungen_zusammen(tmp_path):
    """Zwei Gremien zur selben Zeit dürfen sich nicht gegenseitig beenden."""
    s = CouncilStore(tmp_path / "parallel.sqlite")
    s.replace_scheduled_sessions([
        ScheduledSession(committee="Ortsrat Nord", session_date=HEUTE,
                         session_time="17:00", location="Bürgerhaus"),
        ScheduledSession(committee="Ortsrat Süd", session_date=HEUTE,
                         session_time="17:00", location="Schulaula"),
        ScheduledSession(committee="Rat", session_date=HEUTE,
                         session_time="19:00", location="PFL"),
    ])
    assert s.live_windows(HEUTE) == {"17:00": "19:00"}
    s.close()


def test_live_windows_ohne_uhrzeit(tmp_path):
    """Termine ohne Uhrzeit begrenzen nichts — sie können es gar nicht."""
    s = CouncilStore(tmp_path / "ohne.sqlite")
    s.replace_scheduled_sessions([
        ScheduledSession(committee="Rat", session_date=HEUTE,
                         session_time="18:00", location="PFL"),
        ScheduledSession(committee="Wirtschaftsausschuss", session_date=HEUTE,
                         session_time="", location="VIEROL"),
    ])
    assert s.live_windows(HEUTE) == {}
    s.close()


def test_sessions_endpunkt_liefert_live_until(store):
    """Die Sitzungsliste trägt das Fenster — für heute, und nur für heute."""
    morgen = (date.today() + timedelta(days=1)).isoformat()
    store.replace_scheduled_sessions([
        ScheduledSession(committee="Verwaltungsausschuss", session_date=HEUTE,
                         session_time="16:30", location="PFL"),
        ScheduledSession(committee="Schulausschuss", session_date=morgen,
                         session_time="17:00", location="Alte Fleiwa"),
    ])
    rows = TestClient(app).get("/api/council/sessions?scope=upcoming&limit=10").json()["sessions"]
    fenster = {(r["committee"], r["session_date"]): r.get("live_until") for r in rows}
    assert fenster[("Ausschuss für Allgemeine Angelegenheiten", HEUTE)] == "16:30"
    assert fenster[("Verwaltungsausschuss", HEUTE)] == "18:00"
    # Der Rat ist der letzte des Tages: vier Stunden ab Beginn.
    assert fenster[("Rat", HEUTE)] == "22:00"
    # Morgen kann nichts live sein, dort steht das Feld gar nicht erst.
    assert fenster[("Schulausschuss", morgen)] is None


def test_heute_briefing_kennt_den_ganzen_tag(store):
    """Die Landing-Leiste bekommt alle Sitzungen des Tages samt Fenster —
    sonst könnte sie um 18:30 nicht auf den Rat umschalten."""
    daten = TestClient(app).get("/api/council/heute").json()
    assert daten["state"] == "heute"
    assert [(s["committee"], s["session_time"], s["live_until"]) for s in daten["sessions"]] == [
        ("Ausschuss für Allgemeine Angelegenheiten", "16:00", "16:30"),
        ("Verwaltungsausschuss", "16:30", "18:00"),
        ("Rat", "18:00", "22:00"),
    ]
    # Die TOPs gehören jeweils zur eigenen Sitzung, nicht pauschal zur ersten.
    assert daten["sessions"][2]["tops"] == ["Haushaltssatzung 2027", "Neubau der Kita Bloherfelde"]
    assert daten["sessions"][2]["remaining"] == 1
    assert daten["sessions"][1]["tops"] == []          # nur ein Kalendertermin
    # Die Kopf-Felder bleiben bei der ersten Sitzung — ältere App-Installationen
    # lesen sie unverändert weiter.
    assert daten["committee"] == "Ausschuss für Allgemeine Angelegenheiten"
    assert daten["n_sessions_today"] == 3
