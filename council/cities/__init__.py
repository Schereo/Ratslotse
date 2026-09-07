"""Der Städte-Speicher: Ratsdokumente vieler Kommunen, Oldenburg eingeschlossen.

Fünf Schichten, streng getrennt (``schema.py``): roh, normalisiert, Text,
Annotationen, Indizes. Jede ist aus der darunter neu berechenbar — das ist
die Eigenschaft, die spätere Auswertungen von heutigen Entscheidungen
unabhängig macht.

Einstieg: ``docs/vorschlag-staedte-speicher.md`` (warum so) und
``docs/plan-cities-umsetzung.md`` (was in welcher Reihenfolge).
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def default_paths() -> tuple[Path, Path, Path]:
    """``(datenbank, dateiablage, rohernte)`` — aus der Umgebung, mit Vorgaben.

    Skripte importieren nicht aus ``web/`` (das wäre ein Ring über die
    Schichten); die Backend-Konfiguration liest dieselben Variablen mit
    denselben Vorgaben.
    """
    db = Path(os.environ.get("CITIES_DB", ROOT / "data" / "cities.sqlite"))
    files = Path(os.environ.get("CITIES_FILES_DIR", ROOT / "data" / "cities-files"))
    raw = Path(os.environ.get("CITIES_RAW_DIR", ROOT / "data" / "cities-raw"))
    return db, files, raw
