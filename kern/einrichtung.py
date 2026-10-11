"""Schema einrichten — einmal je Prozess und Datei, nicht je Anfrage.

Beide Stores richten beim Öffnen ihr Schema ein: Tabellen umbenennen,
``CREATE TABLE IF NOT EXISTS``, dann die Migrationen samt Wert-Proben. Das ist
idempotent und soll so bleiben — ein Cron, ein Skript, ein Test öffnen die
Datei und bekommen garantiert den Stand des Codes.

Der Web-Dienst öffnet aber je ANFRAGE einen Store. Gemessen am 09.10.2026
kostete das 22–25 ms und 736 SQL-Anweisungen je Rats-Anfrage, darunter 67
Wert-Proben mit vollen Tabellenscans — praktisch der ganze Median aller
Routen. Unter Last schlimmer: 20 gleichzeitige Anfragen brauchten 3 s statt
0,55 s, weil 20 Threads dieselbe Migration gleichzeitig prüften.

Deshalb merkt sich der Web-Dienst (und NUR er: ``einmal=True`` in
``app.deps``), welche Datei er schon eingerichtet hat, und
zwar zusammen mit ``PRAGMA schema_version``. Ändert jemand das Schema von
außen (ein anderer Prozess mit neuerem Code, ein Test, der eine Spalte
entfernt), ändert sich die Zahl, und es wird wieder eingerichtet. Eine neu
angelegte Datei hat ein anderes Inode. Ein neuer Code-Stand heißt ein neuer
Prozess — der Deploy startet die Dienste neu.

Crons, Skripte und Tests richten weiter bei jedem Öffnen ein. Dort kostet es
nichts Spürbares, und ein Test, der eine Zeile auf einen alten Wert setzt und
neu öffnet, verlässt sich darauf, dass die Wert-Migration dann wieder läuft —
das ändert ``schema_version`` nicht und wäre sonst unsichtbar.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from collections.abc import Callable
from pathlib import Path

_sperre = threading.Lock()
_stand: dict[tuple[str, int, int], int] = {}


def _schluessel(path: str | Path) -> tuple[str, int, int] | None:
    if str(path) == ":memory:":
        return None
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (os.path.realpath(path), st.st_dev, st.st_ino)


def _version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA schema_version").fetchone()[0])


def einmal_einrichten(conn: sqlite3.Connection, path: str | Path,
                      einrichten: Callable[[], None], *, einmal: bool = True) -> bool:
    """Führt ``einrichten`` aus, wenn dieser Prozess die Datei in ihrem
    jetzigen Schema-Stand noch nicht eingerichtet hat. Gibt zurück, ob es lief.

    Die Sperre hält gleichzeitige Erst-Einrichtungen auseinander: Nach einem
    Neustart kommen die ersten Anfragen gebündelt, und nur eine soll prüfen."""
    if not einmal:
        einrichten()
        return True
    key = _schluessel(path)
    if key is not None and _stand.get(key) == _version(conn):
        return False
    with _sperre:
        if key is not None and _stand.get(key) == _version(conn):
            return False
        einrichten()
        if key is not None:
            _stand[key] = _version(conn)
    return True


def vergessen() -> None:
    """Für Tests: alles wieder neu einrichten lassen."""
    _stand.clear()
