"""Zwei Fehler, die gleich heißen und Verschiedenes bedeuten.

SQLite meldet beides als ``sqlite3.OperationalError``:

* **„no such table"** — die Tabelle gibt es noch nicht. Das ist im Bestand
  dieses Repos der Normalfall: Viele Tabellen entstehen erst beim ersten Lauf
  ihres Ingests, und eine Abfrage darauf soll dann eine leere Liste liefern,
  keinen Fehler. Eine frische Datenbank hat schlicht noch nicht alles.
* **„no such column"** — die Abfrage passt nicht zum Schema. Das ist nie
  normal. Es heißt, dass eine Umbenennung im Code angekommen ist und in
  dieser Abfrage nicht (oder umgekehrt).

Bis 09/2026 stand an 45 Stellen dieselbe Abkürzung::

    except sqlite3.OperationalError:
        return []

Sie verschluckt beide Fälle gleich. Der zweite wird damit unsichtbar: Die
Seite zeigt „keine Daten", der Cron meldet „nichts gefunden", und beides
sieht aus wie ein leerer Bestand. Genau so lag ``hebesatz_probe`` monatelang
still — sie fragte nach einer Spalte, die es seit einer Umbenennung nicht
mehr gab, und meldete deshalb immer den Normalfall.

Der Helfer trennt die beiden::

    except sqlite3.OperationalError as e:
        if not tabelle_fehlt(e):
            raise
        return []

Statisch fängt ``tests/test_sql_spalten.py`` diese Klasse schon vor dem
Merge — aber nur für Abfragen, die als ganzes Literal im Code stehen. Was aus
f-Strings zusammengesetzt wird, sieht er nicht; dort ist dieser Helfer das
Netz.
"""
from __future__ import annotations

import logging
import sqlite3

_LOG = logging.getLogger("kern.dbfehler")


def tabelle_fehlt(fehler: sqlite3.OperationalError) -> bool:
    """``True``, wenn die Tabelle fehlt — der harmlose Fall.

    Für alles andere wird eine Warnung geloggt und ``False`` geliefert: Der
    Aufrufer soll die Ausnahme dann weiterwerfen, statt ein leeres Ergebnis
    vorzutäuschen.
    """
    text = str(fehler).lower()
    if text.startswith("no such table"):
        return True
    _LOG.warning(
        "Abfrage passt nicht zum Schema — das ist kein leerer Bestand, "
        "sondern ein Fehler: %s", fehler)
    return False
