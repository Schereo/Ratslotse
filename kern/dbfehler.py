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


def nur_lesen(pfad) -> sqlite3.Connection:
    """Eine Verbindung zum Lesen — auch neben einer laufenden Anwendung.

    ``file:…?mode=ro`` ist der saubere Weg und scheitert trotzdem regelmäßig:
    Neben einer WAL-Datenbank muss SQLite eine ``-shm`` anlegen, und genau das
    darf es im Nur-Lese-Modus nicht. Die Meldung lautet dann „unable to open
    database file" — sie klingt nach fehlender Datei und ist keine.

    Dann wird normal geöffnet. Das legt die Begleitdateien an, ändert aber
    nichts am Inhalt; die Anwendung tut ohnehin dasselbe. Wer diese Verbindung
    benutzt, liest — Schreiben ist hier nicht verboten, sondern sinnlos.

    ``immutable=1`` wäre der dritte Weg und der falsche: Es verspricht SQLite,
    dass sich die Datei nicht ändert. Bei einer laufenden Anwendung ist das
    schlicht gelogen, und die Antworten dürfen dann alles sein.
    """
    pfad = str(pfad)
    try:
        verbindung = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
        verbindung.execute("SELECT 1 FROM sqlite_master LIMIT 1")
        return verbindung
    except sqlite3.Error:
        return sqlite3.connect(pfad, timeout=5)


def neue_id(cur: sqlite3.Cursor) -> int:
    """Die ID der Zeile, die dieser Cursor gerade eingefügt hat.

    ``cur.lastrowid`` ist als ``int | None`` typisiert, und das zu Recht: Nach
    einem ``SELECT``, nach einem ``executemany`` und nach einem ``INSERT`` in
    eine ``WITHOUT ROWID``-Tabelle steht dort ``None``. Nach einem einzelnen
    ``INSERT`` in eine gewöhnliche Tabelle steht dort immer eine Zahl.

    Im Bestand stand deshalb an einem Dutzend Stellen ``return cur.lastrowid``
    unter der Annotation ``-> int``. Die Annahme stimmt an jeder dieser
    Stellen — sichtbar ist sie an keiner. Dieser Helfer schreibt sie hin und
    prüft sie: Trifft sie einmal nicht zu, gibt es einen Fehler mit Namen
    statt eines ``None``, das als ID weiterwandert und erst drei Tabellen
    später als verwaister Verweis auffällt.
    """
    if cur.lastrowid is None:  # pragma: no cover — siehe Docstring
        raise RuntimeError(
            "INSERT ohne lastrowid — kein einzelnes INSERT in eine rowid-Tabelle?")
    return cur.lastrowid
