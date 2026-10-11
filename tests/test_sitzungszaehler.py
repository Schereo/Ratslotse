"""Der Sitzungs-Zähler darf keine Anfrage aufhalten (BL-02, 09.10.2026).

Bis dahin schrieb jede angemeldete Anfrage mit Commit in ratslotse.sqlite.
Hielt jemand die Schreibsperre, wartete jede den vollen busy_timeout von 5 s
ab — gemessen: angemeldete Beschluss-Seite 5,4 s, und weil der Threadpool
volllief, eine ANONYME daneben 6,0 s.
"""
from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))

from app import deps  # noqa: E402
from kern.store import Store  # noqa: E402


class _Aufzeichner:
    def __init__(self, gelingt: bool = True):
        self.rufe: list[tuple[int, str, int, bool]] = []
        self.gelingt = gelingt

    def record_activity(self, owner_id, feature, client, *, anzahl=1, warten=True):
        self.rufe.append((owner_id, client, anzahl, warten))
        return self.gelingt


@pytest.fixture
def gedrosselt(monkeypatch):
    monkeypatch.setattr(deps, "_SITZUNG_TAKT_S", 60.0)
    deps.sitzungen_vergessen()
    yield
    deps.sitzungen_vergessen()


def test_erste_anfrage_schreibt_sofort_und_ohne_warten(gedrosselt):
    s = _Aufzeichner()
    deps._sitzung_zaehlen(s, 7, "web")
    assert s.rufe == [(7, "web", 1, False)]


def test_weitere_anfragen_sammeln_sich_und_kommen_gebuendelt(gedrosselt, monkeypatch):
    s = _Aufzeichner()
    uhr = [1000.0]
    monkeypatch.setattr(deps.time, "monotonic", lambda: uhr[0])
    deps._sitzung_zaehlen(s, 7, "web")
    for _ in range(14):                      # eine Seite: 14 weitere Anfragen
        deps._sitzung_zaehlen(s, 7, "web")
    assert len(s.rufe) == 1                  # nichts geschrieben
    uhr[0] += 61
    deps._sitzung_zaehlen(s, 7, "web")
    assert s.rufe[-1] == (7, "web", 15, False)   # 14 gesammelte + diese


def test_clients_und_konten_zaehlen_getrennt(gedrosselt):
    s = _Aufzeichner()
    deps._sitzung_zaehlen(s, 7, "web")
    deps._sitzung_zaehlen(s, 7, "ios")
    deps._sitzung_zaehlen(s, 8, "web")
    assert [(o, c) for o, c, _, _ in s.rufe] == [(7, "web"), (7, "ios"), (8, "web")]


def test_gesperrte_datei_verliert_nichts(gedrosselt, monkeypatch):
    uhr = [1000.0]
    monkeypatch.setattr(deps.time, "monotonic", lambda: uhr[0])
    deps._sitzung_zaehlen(_Aufzeichner(gelingt=False), 7, "web")
    uhr[0] += 61
    s = _Aufzeichner()
    deps._sitzung_zaehlen(s, 7, "web")
    assert s.rufe == [(7, "web", 2, False)]


def test_record_activity_wartet_nicht_auf_eine_sperre(tmp_path):
    """Der eigentliche Punkt: Hält ein anderer die Schreibsperre, gibt der
    Zähler sofort auf — statt 5 s busy_timeout."""
    pfad = tmp_path / "ratslotse.sqlite"
    store = Store(pfad)
    fremd = sqlite3.connect(pfad, isolation_level=None)
    fremd.execute("BEGIN IMMEDIATE")          # Schreibsperre halten
    try:
        t = time.perf_counter()
        assert store.record_activity(1, "session", "web", warten=False) is False
        assert time.perf_counter() - t < 0.5
    finally:
        fremd.execute("ROLLBACK")
        fremd.close()
    # Danach wieder normal — und mit dem alten busy_timeout.
    assert store.record_activity(1, "session", "web", anzahl=3, warten=False) is True
    assert store._conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    n = store._conn.execute("SELECT count FROM user_activity WHERE owner_id = 1").fetchone()[0]
    assert n == 3
    store.close()
