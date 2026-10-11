"""Schema einmal je Prozess einrichten — nur im Web-Dienst (BL-01, 09.10.2026).

Gemessen: CouncilStore() kostete je Anfrage 22–25 ms und 736 SQL-Anweisungen;
20 gleichzeitige Anfragen brauchten 3 s statt 0,55 s.
"""
from __future__ import annotations

import sqlite3

from council.store import CouncilStore
from kern import einrichtung
from kern.store import Store


def _zaehler(pfad, monkeypatch, klasse):
    laeufe = []
    alt = klasse._migrate
    monkeypatch.setattr(klasse, "_migrate", lambda self: (laeufe.append(1), alt(self))[1])
    return laeufe


def test_web_dienst_richtet_einmal_ein(tmp_path, monkeypatch):
    pfad = tmp_path / "council.sqlite"
    laeufe = _zaehler(pfad, monkeypatch, CouncilStore)
    for _ in range(5):
        CouncilStore(pfad, einmal=True).close()
    assert len(laeufe) == 1


def test_alle_anderen_richten_jedes_mal_ein(tmp_path, monkeypatch):
    """Crons, Skripte, Tests: unverändert — dort verlässt man sich darauf."""
    pfad = tmp_path / "council.sqlite"
    laeufe = _zaehler(pfad, monkeypatch, CouncilStore)
    for _ in range(3):
        CouncilStore(pfad).close()
    assert len(laeufe) == 3


def test_schemaaenderung_von_aussen_richtet_neu_ein(tmp_path, monkeypatch):
    pfad = tmp_path / "ratslotse.sqlite"
    laeufe = _zaehler(pfad, monkeypatch, Store)
    Store(pfad, einmal=True).close()
    Store(pfad, einmal=True).close()
    assert len(laeufe) == 1
    # Ein anderer Prozess (neuerer Code, ein Werkzeug) ändert das Schema.
    with sqlite3.connect(pfad) as c:
        c.execute("CREATE TABLE fremd (x INTEGER)")
    Store(pfad, einmal=True).close()
    assert len(laeufe) == 2


def test_neue_datei_unter_altem_namen_wird_eingerichtet(tmp_path):
    pfad = tmp_path / "council.sqlite"
    CouncilStore(pfad, einmal=True).close()
    for f in tmp_path.iterdir():
        f.unlink()
    s = CouncilStore(pfad, einmal=True)   # leere Datei: muss die Tabellen bekommen
    assert s._conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name = 'council_decisions'").fetchone()
    s.close()


def test_vergessen_setzt_zurueck(tmp_path, monkeypatch):
    pfad = tmp_path / "council.sqlite"
    laeufe = _zaehler(pfad, monkeypatch, CouncilStore)
    CouncilStore(pfad, einmal=True).close()
    einrichtung.vergessen()
    CouncilStore(pfad, einmal=True).close()
    assert len(laeufe) == 2
