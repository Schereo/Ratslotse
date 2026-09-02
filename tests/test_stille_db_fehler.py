"""Ein verschluckter Datenbankfehler darf nicht wie ein leerer Bestand aussehen.

SQLite meldet zwei sehr verschiedene Dinge als ``sqlite3.OperationalError``:
„no such table" heißt „dieses Feature hat noch nie gelaufen" und ist im
Bestand dieses Repos der Normalfall. „no such column" heißt „diese Abfrage
passt nicht zum Schema" und ist immer ein Fehler.

Bis 09/2026 stand an 44 Stellen dieselbe Abkürzung, die beides gleich
behandelte::

    except sqlite3.OperationalError:
        return []

Damit wird der zweite Fall unsichtbar: Die Seite zeigt „keine Daten", der
Cron meldet „nichts gefunden", und beides sieht aus wie ein leerer Bestand.
Genau so lag ``hebesatz_probe`` monatelang still.

Dieser Wächter hält fest, dass jeder solche Handler den Helfer benutzt.
``tests/test_sql_spalten.py`` fängt dieselbe Klasse statisch, aber nur für
Abfragen, die als ganzes Literal im Code stehen — was aus f-Strings
zusammengesetzt wird, sieht er nicht.
"""
from __future__ import annotations

import ast
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
BEREICHE = ("council", "kern")


def _stiller_koerper(koerper: list[ast.stmt]) -> bool:
    """Kehrt der Handler nur zurück — ohne zu werfen, zu loggen, zu melden?"""
    text = ast.dump(ast.Module(body=koerper, type_ignores=[]))
    if "Raise" in text or "log" in text.lower() or "print" in text.lower():
        return False
    return all(isinstance(k, (ast.Return, ast.Pass, ast.Continue)) for k in koerper)


def _liest_die_datenbank(koerper: list[ast.stmt]) -> bool:
    text = ast.dump(ast.Module(body=koerper, type_ignores=[]))
    return any(x in text for x in (".execute", "fetchall", "fetchone"))


def test_kein_handler_verschluckt_ein_falsches_schema():
    treffer: list[str] = []
    geprueft = 0
    for bereich in BEREICHE:
        for pfad in sorted((WURZEL / bereich).rglob("*.py")):
            try:
                baum = ast.parse(pfad.read_text())
            except SyntaxError:
                continue
            for knoten in ast.walk(baum):
                if not isinstance(knoten, ast.Try):
                    continue
                if not _liest_die_datenbank(knoten.body):
                    continue
                for h in knoten.handlers:
                    if h.type is None:
                        continue
                    if ast.unparse(h.type) != "sqlite3.OperationalError":
                        continue
                    geprueft += 1
                    if _stiller_koerper(h.body):
                        treffer.append(
                            f"{pfad.relative_to(WURZEL).as_posix()}:{h.lineno}")

    assert geprueft > 30, (
        f"Nur {geprueft} Handler gefunden — der Leser in dieser Datei greift "
        f"nicht mehr, der Test wacht also über nichts."
    )
    assert not treffer, (
        "Diese Handler verschlucken jeden OperationalError, auch ein falsches "
        "Schema:\n  " + "\n  ".join(treffer)
        + "\n\nSo lässt sich „die Tabelle gibt es noch nicht“ nicht mehr von "
          "„diese Abfrage passt nicht zum Schema“ unterscheiden, und der "
          "zweite Fall sieht aus wie ein leerer Bestand. Muster:\n\n"
          "    except sqlite3.OperationalError as fehler:\n"
          "        if not tabelle_fehlt(fehler):\n"
          "            raise\n"
          "        return []\n"
    )


def test_der_helfer_trennt_die_beiden_faelle():
    import sqlite3
    import sys

    sys.path.insert(0, str(WURZEL))
    from kern.dbfehler import tabelle_fehlt

    assert tabelle_fehlt(sqlite3.OperationalError("no such table: council_x"))
    assert not tabelle_fehlt(sqlite3.OperationalError("no such column: art"))
    # Alles Unbekannte gilt als Fehler, nicht als leerer Bestand.
    assert not tabelle_fehlt(sqlite3.OperationalError("database is locked"))
