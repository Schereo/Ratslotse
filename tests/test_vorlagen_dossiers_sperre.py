"""Eine gesperrte Datenbank kostet eine Vorlage, nicht den Lauf.

Am 14.11.2026 brach der Wahlprogramm-Bestand auf dev nach 461 von 662 Vorlagen
an ``database is locked`` ab (``scripts/vorlagen_dossiers.py::Sperre``).
"""
from __future__ import annotations

import sqlite3

import pytest

from scripts import vorlagen_dossiers as vd


@pytest.fixture(autouse=True)
def _ohne_warten(monkeypatch):
    pausen: list[float] = []
    monkeypatch.setattr(vd.time, "sleep", pausen.append)
    return pausen


def _gesperrt():
    raise sqlite3.OperationalError("database is locked")


def test_gesperrte_datenbank_ueberspringt_die_vorlage(_ohne_warten):
    sperre = vd.Sperre()
    assert sperre.bauen("26/0001", _gesperrt) is None
    assert sperre.uebersprungen == 1 and _ohne_warten == [vd.SPERRE_PAUSE_SEKUNDEN]
    # Die nächste Vorlage läuft normal — und setzt die Folge zurück.
    assert sperre.bauen("26/0002", lambda: {"payload": {}}) == {"payload": {}}
    assert sperre.in_folge == 0


def test_dauerhafte_sperre_beendet_den_lauf_mit_dem_fehler():
    sperre = vd.Sperre()
    for _ in range(vd.SPERRE_MAX - 1):
        assert sperre.bauen("26/0001", _gesperrt) is None
    with pytest.raises(sqlite3.OperationalError):
        sperre.bauen("26/0001", _gesperrt)


def test_andere_datenbankfehler_bleiben_fehler():
    def kaputt():
        raise sqlite3.OperationalError("no such table: template_terms")
    with pytest.raises(sqlite3.OperationalError):
        vd.Sperre().bauen("26/0001", kaputt)


def test_alle_drei_stufen_bauen_ueber_die_sperre():
    """Wer eine vierte Stufe ergänzt, ruft ``build_for_template`` nicht nackt auf."""
    import inspect
    import re
    quelle = inspect.getsource(vd)
    aufrufe = re.findall(r"^.*\.build_for_template\(.*$", quelle, flags=re.M)
    assert len(aufrufe) == 3
    assert all("sperre.bauen(" in zeile for zeile in aufrufe), aufrufe
