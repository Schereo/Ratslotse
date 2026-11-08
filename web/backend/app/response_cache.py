"""Prozess-Zwischenspeicher für Antworten, die allein vom Datenbestand abhängen.

Der gewählte Rat, das Personenverzeichnis, die Ortsfilter, die Parteien-
Auswertung, die Themenfelder der Ideen: Jede dieser Antworten ist für jedes
Konto gleich, ändert sich nur, wenn ein Cron etwas einliest — und wurde bis
11/2026 trotzdem bei jeder Anfrage neu gerechnet, weil jede Anfrage einen
frischen Store öffnet. Gemessen am 08.11.2026 (in-process, Median aus 7):
``/topics/suggestions`` 110 ms, ``/cities/ideas/fields`` 103 ms,
``/council/districts`` 97 ms, ``/council/elected`` 70 ms — jeweils die letzte
Anfrage ihrer Seite.

**Der Schlüssel ist der Datenstand, keine Uhr.** ``PRAGMA data_version`` einer
Verbindung zählt hoch, sobald IRGENDEINE andere Verbindung committet hat —
der Cron im eigenen Prozess genauso wie eine schreibende Anfrage hier. Der
Wert ist je Verbindung, also hält dieses Modul je Datenbankdatei EINE
langlebige Wächter-Verbindung, nur lesend geöffnet. Ein Zeitstempel als
Schlüssel taugt nicht: Die ``-wal``-Datei entsteht und verschwindet mit den
Verbindungen je Anfrage, ``stat()`` darauf traf in der Messung nie.

Vier Regeln, auf die es ankommt:

- **Der Wächter hält keinen Lese-Schnappschuss.** Er stellt eine einzige
  Abfrage, holt sie mit ``fetchall`` vollständig ab und öffnet nie eine
  Transaktion. Ein offener Leser blockierte das Einchecken der WAL — sie
  wüchse lautlos (``tests/test_store_orte_wal.py``, zweimal passiert).
- **Die Release-Barriere wirkt** (``kern.maintenance``). Steht die
  Wartungsmarke, schließt der Wächter, und jede Anfrage rechnet ungepuffert
  mit ihrem eigenen Store — der öffnet dann gar nicht erst.
- **Nichts Persönliches.** Hier liegt nur, was für alle Konten gleich ist.
  Rechteprüfungen (``require_budget`` …) bleiben Abhängigkeiten des Endpunkts
  und laufen damit VOR dem Zwischenspeicher. Persönliche Felder (``reported``
  einer Tafel) werden je Anfrage dazugemischt, nie gespeichert.
- **Gespeicherte Objekte werden nie verändert.** Der Bauplan liefert die
  fertige Antwort; wer etwas ergänzen will, baut ein neues dict
  (``{**gespeichert, "feld": …}``), statt das gespeicherte zu beschreiben —
  sonst sähe die nächste Anfrage die Änderung der vorigen.

Eine Nebenwirkung hat der Wächter, und sie ist gemessen: Solange irgendeine
Verbindung offen ist, löscht SQLite die ``-wal``-Datei nicht, wenn der letzte
Schreiber schließt. Sie wächst dadurch nicht — eingecheckt wird weiter, und
kleine Läufe schreiben sie von vorn neu —, bliebe aber in der Größe des
größten Laufs stehen (Probe: 41 MB nach einem großen Schreiblauf, dort auch
nach 50 kleinen). Deshalb tritt der Wächter nach einem Commit zur Seite, wenn
die Datei größer als :data:`WAL_RELEASE_BYTES` ist: Er schließt, und die
nächste Anfrage öffnet ihn neu. Der Zwischenspeicher verliert dabei nichts —
nach einem Commit ist er ohnehin neu zu rechnen.

Ohne Wächter (``:memory:``, fehlende Datei, Barriere, Fehler beim Öffnen)
rechnet :func:`cached` einfach ungepuffert — dasselbe Ergebnis, nur langsam.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from collections import OrderedDict
from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TypeVar, cast

from kern.maintenance import BYPASS_ENV, marker_for_database

T = TypeVar("T")

#: Der Dienst beobachtet zwei Dateien (council, cities). Die Grenze fängt nur
#: einen Fehler ab, der je Anfrage einen neuen Pfad erfände — jeder Wächter
#: hält drei Dateien offen.
MAX_WATCHERS = 4

#: Ab dieser Größe der ``-wal``-Datei schließt der Wächter nach einem Commit,
#: damit SQLite sie beim Schließen der letzten Verbindung wieder löschen kann
#: (s. Modulkopf). Unterhalb bleibt er offen: Eine kleine Datei kostet nichts,
#: und jedes Schließen kostet einen Neubau der gespeicherten Antworten.
WAL_RELEASE_BYTES = 32 * 1024 * 1024


@dataclass
class _Watcher:
    conn: sqlite3.Connection
    #: (st_dev, st_ino) beim Öffnen. Wird die Datei ERSETZT (Wiederherstellung,
    #: ``lokale_daten.py setz``), sähe der Wächter sonst für immer die alte.
    inode: tuple[int, int]
    #: Zählt je Öffnen hoch: ``data_version`` einer neuen Verbindung ist mit
    #: dem der alten nicht vergleichbar.
    generation: int
    lock: threading.Lock = field(default_factory=threading.Lock)
    #: Zuletzt gelesenes ``data_version`` — ein Wechsel heißt „Commit".
    last_version: int | None = None


_lock = threading.Lock()
_watchers: dict[str, _Watcher] = {}
_generation = 0
#: name → OrderedDict(key → (stand, wert)), älteste zuerst.
_entries: dict[str, OrderedDict[Hashable, tuple[tuple, object]]] = {}
_build_locks: dict[tuple[str, Hashable], threading.Lock] = {}


def _close_locked(path: str) -> None:
    """Wächter schließen; ``_lock`` hält der Aufrufer."""
    w = _watchers.pop(path, None)
    if w is not None:
        # Unter dem Schloss des Wächters: Keine andere Anfrage liest gerade.
        with w.lock:
            try:
                w.conn.close()
            except sqlite3.Error:
                pass


#: Datenbankpfad → Pfad der Wartungsmarke, einmal je Datei aufgelöst.
_markers: dict[str, Path | None] = {}


def _barrier_active(path: str) -> bool:
    """Dieselbe Prüfung wie ``kern.maintenance.require_database_available``
    beim Öffnen eines Stores — nur mit dem Pfad der Marke einmal je Datei
    aufgelöst: ``resolve()`` kostete je Aufruf das Zwanzigfache der ganzen
    übrigen Prüfung (gemessen 156 gegen 7 µs)."""
    if path not in _markers:
        _markers[path] = marker_for_database(path)
    marker = _markers[path]
    return marker is not None and marker.exists() and os.environ.get(BYPASS_ENV) != "1"


def _watcher(path: str) -> _Watcher | None:
    """Der Wächter für ``path`` — geöffnet, wenn nötig; ``None``, wenn nicht."""
    global _generation
    try:
        # Steht die Wartungsmarke, bleibt der Wächter zu — und ein schon
        # offener wird geschlossen. Ebenso, wenn die Datei fehlt.
        st = None if _barrier_active(path) else os.stat(path)
    except OSError:
        st = None
    if st is None:
        with _lock:
            _close_locked(path)
        return None
    inode = (st.st_dev, st.st_ino)
    with _lock:
        w = _watchers.get(path)
        if w is not None and w.inode == inode:
            return w
        _close_locked(path)
        while len(_watchers) >= MAX_WATCHERS:
            _close_locked(next(iter(_watchers)))
        try:
            # Nur lesend: Der Wächter legt keine Datei an und schreibt nie.
            conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro",
                                   uri=True, timeout=0.5, check_same_thread=False)
        except sqlite3.Error:
            return None
        _generation += 1
        w = _watchers[path] = _Watcher(conn, inode, _generation)
        return w


def data_state(path: str | os.PathLike | None) -> tuple[int, int] | None:
    """Ein Wert, der sich mit jedem Commit auf ``path`` ändert — oder ``None``.

    ``None`` heißt „nicht beobachtbar" (``:memory:``, keine Datei, Release-
    Barriere, Fehler); :func:`cached` rechnet dann ungepuffert. Kostet eine
    Abfrage und zwei ``stat`` — wenige Mikrosekunden."""
    if path is None or str(path) == ":memory:":
        return None
    key = str(path)
    w = _watcher(key)
    if w is None:
        return None
    try:
        with w.lock:
            # fetchall: Die Anweisung ist danach abgeschlossen, die Verbindung
            # hält keinen Lese-Schnappschuss — sonst blockierte sie das
            # Einchecken der WAL.
            version = int(w.conn.execute("PRAGMA data_version").fetchall()[0][0])
            commit = w.last_version is not None and version != w.last_version
            w.last_version = version
    except sqlite3.Error:
        with _lock:
            if _watchers.get(key) is w:
                _close_locked(key)
        return None
    if commit and _wal_size(key) > WAL_RELEASE_BYTES:
        with _lock:
            if _watchers.get(key) is w:
                _close_locked(key)
        return None
    return (w.generation, version)


def _wal_size(path: str) -> int:
    try:
        return os.stat(f"{path}-wal").st_size
    except OSError:
        return 0


def _lookup(name: str, key: Hashable, stand: tuple) -> tuple[bool, object]:
    """Treffer zum Stand ``stand``? ``_lock`` hält der Aufrufer."""
    bucket = _entries.get(name)
    if bucket is None:
        return False, None
    hit = bucket.get(key)
    if hit is None or hit[0] != stand:
        return False, None
    bucket.move_to_end(key)
    return True, hit[1]


def _path_of(source: object) -> str | None:
    """Die Datei hinter einem Store (``_path`` beim Rats-, ``path`` beim
    Städte-Speicher) oder ein Pfad selbst. ``None`` für einen Test-Ersatz ohne
    Datei — dann wird ungepuffert gerechnet."""
    if isinstance(source, (str, os.PathLike)):
        return os.fspath(source)
    for attr in ("_path", "path"):
        value = getattr(source, attr, None)
        if isinstance(value, (str, os.PathLike)):
            return os.fspath(value)
    return None


def cached(name: str, sources: Sequence[object], build: Callable[[], T], *,
           key: Hashable = None, maxsize: int = 1, per_day: bool = True) -> T:
    """``build()`` einmal je Datenstand der Datenbanken in ``sources``.

    ``sources`` sind die Stores, aus denen ``build`` liest (oder ihre Pfade).
    ``name`` trennt die Endpunkte, ``key`` die Varianten eines Endpunkts (der
    Slug einer Person, die Kennung eines Ortsbereichs); je ``name`` bleiben
    höchstens ``maxsize`` Varianten, die zuletzt benutzten. ``per_day`` nimmt
    das Datum in den Schlüssel: Viele Auswertungen rechnen mit „heute"
    (zwölf Monate zurück, kommende Sitzungen) — ohne das stünde nach
    Mitternacht der Stand von gestern da, bis der nächste Cron schreibt.

    Ein Fehler in ``build`` wird nicht gespeichert, sondern weitergereicht
    (eine 404 bleibt eine 404 und kostet beim nächsten Mal wieder). Je
    Schlüssel rechnet nur eine Anfrage, die gleichzeitigen warten auf sie.

    Der Rückgabewert ist GETEILT — nie verändern (s. Modulkopf)."""
    states = []
    for source in sources:
        path = _path_of(source)
        s = data_state(path)
        if s is None:
            return build()
        states.append((path, s))
    stand = (tuple(states), date.today() if per_day else None)

    with _lock:
        found, value = _lookup(name, key, stand)
        if found:
            return cast(T, value)
        build_lock = _build_locks.setdefault((name, key), threading.Lock())

    with build_lock:
        with _lock:
            found, value = _lookup(name, key, stand)
        if found:
            return cast(T, value)
        # Der Stand wurde VOR dem Rechnen gelesen. Schreibt jemand währenddessen,
        # trägt der Eintrag den alten Stand, und die nächste Anfrage rechnet neu —
        # nie umgekehrt (alter Inhalt unter neuem Stand).
        try:
            value = build()
        except BaseException:
            # Ein Fehler hinterlässt auch kein Schloss. Sonst wüchse
            # `_build_locks` mit jedem Schlüssel, der nur Fehler liefert,
            # unbegrenzt — `/person/{slug}` ist öffentlich, jeder erfundene
            # Slug ist eine 404 und bliebe ein Eintrag bis zum Neustart.
            with _lock:
                if key not in _entries.get(name, {}) and \
                        _build_locks.get((name, key)) is build_lock:
                    del _build_locks[(name, key)]
            raise
        with _lock:
            bucket = _entries.setdefault(name, OrderedDict())
            bucket[key] = (stand, value)
            bucket.move_to_end(key)
            while len(bucket) > maxsize:
                alt, _ = bucket.popitem(last=False)
                _build_locks.pop((name, alt), None)
    return value


def reset() -> None:
    """Alles vergessen und die Wächter schließen — für Tests und Messungen.

    Die Suite ruft das vor und nach jedem Test (``tests/conftest.py``): Jeder
    Test hat seine eigene Datenbank, und ein Wächter je Test hielte sonst
    Hunderte Dateien offen."""
    with _lock:
        _entries.clear()
        _build_locks.clear()
        _markers.clear()
        for path in list(_watchers):
            _close_locked(path)
