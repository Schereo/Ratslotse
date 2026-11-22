"""Gibt eine Stadt ihre Daten noch heraus? ``pipeline.access_status``.

Gemessen am Lauf vom 09.11.2026: Wolfsburg lieferte gar nichts (403
„administrative rules"), Braunschweig stellte die Dokumente hinter eine
ALTCHA-Prüfung, Osnabrück wies jeden Dokumentabruf mit 403 ab, Potsdam nahm
nach drei Versuchen keine Verbindung mehr an. Was davon die Ideen-Seite sagt,
hängt an dieser einen Funktion.
"""
from __future__ import annotations

import pytest

from council.cities import pipeline

ERNTE = {"organizations": 198, "meetings": 143, "papers": 168,
         "files_fetched": 0, "files_failed": 0}


@pytest.mark.parametrize("ernte, erwartet", [
    # Gesund: Dokumente kommen, auch wenn einzelne fehlschlagen.
    ({**ERNTE, "files_fetched": 40, "files_failed": 12}, "ok"),
    # Gesund und ruhig: nichts Neues zu holen.
    (ERNTE, "ok"),
    # Wolfsburg: nichts geerntet.
    ({**ERNTE, "organizations": 0, "meetings": 0, "papers": 0}, "blocked"),
    # Braunschweig: ALTCHA vor den Dokumenten.
    ({**ERNTE, "files_gated": 1}, "documents_blocked"),
    # Potsdam: der Server nimmt keine Verbindung mehr an.
    ({**ERNTE, "host_unreachable": 1}, "documents_blocked"),
    # Osnabrück: 403 auf jede Dokument-Adresse.
    ({**ERNTE, "files_failed": 86}, "documents_blocked"),
])
def test_der_zugangsstand_folgt_der_ernte(ernte, erwartet):
    status, _grund = pipeline.access_status(ernte)
    assert status == erwartet


@pytest.mark.parametrize("ernte", [
    # Unterbrochen (Deploy wartet): Der Zugang hat sich gar nicht gezeigt —
    # auch nicht, wenn bis dahin nichts geerntet war.
    {**ERNTE, "organizations": 0, "meetings": 0, "papers": 0,
     "abgebrochen": "Ein Deploy wartet"},
    # Drei Nieten ohne Treffer können drei nichtöffentliche Anlagen sein.
    {**ERNTE, "files_failed": 3},
])
def test_was_sich_nicht_sagen_laesst_laesst_den_stand_stehen(ernte):
    assert pipeline.access_status(ernte) is None


def test_der_wochenlauf_schreibt_den_zugangsstand():
    """Der Aufruf steht im Sonntagslauf, nicht nur in der Funktion — sonst
    bliebe die Tabelle leer und die Seite schwiege."""
    from pathlib import Path

    quelle = (Path(__file__).resolve().parents[1] / "scripts" / "check_cities.py").read_text()
    assert "pipeline.access_status(ernte)" in quelle
    assert "main_store.set_access(" in quelle
