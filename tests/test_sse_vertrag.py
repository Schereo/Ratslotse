"""Sperrklinke für den Ereignis-Strom: Kein Client liest ins Leere.

Die Messung steht in ``scripts/sse_vertrag.py`` — dort steht auch, warum es
sie gibt. Hier steht nur, was offen bleiben darf: heute nichts.
"""
from __future__ import annotations

import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from scripts.sse_vertrag import (app_gelesen, befunde,  # noqa: E402
                                 gesendet, gespeicherter_blob, web_gelesen)


def test_kein_client_liest_ein_feld_das_niemand_sendet():
    gefunden = befunde()
    assert not gefunden, (
        "Diese Felder werden gelesen, aber von niemandem geschrieben:\n  "
        + "\n  ".join(f"{c} ({q}): {f}" for c, q, f in gefunden)
        + "\n\nFast immer eine Umbenennung ohne Nachzug — der Client bekommt "
          "dann nichts und setzt seine Vorgabe ein, ohne Fehler.\n"
          "Einzelheiten: python scripts/sse_vertrag.py"
    )


def test_die_messung_findet_ueberhaupt_etwas():
    """Ein leerer Vergleich meldet ebenfalls null Befunde.

    Beim Bauen zweimal passiert: Der Recherche-Leser griff ins Leere (der
    Rahmen ist dort das ZWEITE Argument), und der Blob-Leser fand das
    Wörterbuch nicht, weil es in einer Variablen steht. Beide Male sah das
    Ergebnis nach „alles in Ordnung" aus.
    """
    rahmen, felder = gesendet()
    assert len(rahmen) >= 12, sorted(rahmen)
    assert len(felder) >= 30, sorted(felder)
    assert len(gespeicherter_blob()) >= 10
    assert len(web_gelesen()) >= 15
    assert len(app_gelesen()) >= 5


def test_beide_stroeme_sind_vertreten():
    """Frage UND Recherche — sonst prüft die Sperrklinke nur den halben Strom."""
    rahmen, _ = gesendet()
    assert {"step", "sources", "token", "done"} <= set(rahmen), sorted(rahmen)
    assert {"phase", "facets", "facette", "gestoppt", "fehler"} <= set(rahmen), sorted(rahmen)
