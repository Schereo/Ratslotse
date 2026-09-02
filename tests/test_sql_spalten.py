"""Jede SQL-Anweisung im Code nennt nur Tabellen und Spalten, die es gibt.

**Die Lücke.** SQL ist für Python eine Zeichenkette. Ob ``SELECT art, rate
FROM council_tax_rates`` zum Schema passt, merkt niemand beim Übersetzen,
beim Linten oder im Review — sondern erst, wenn die Zeile läuft. Und sie
läuft oft nur nachts im Cron, manchmal in einem ``try/except``, das den
Fehler schluckt.

Genau so lag ``scripts/ingest_haushaltssatzung.py`` still: Die Spalte hieß
nach dem Umbau ``kind``, die Abfrage fragte weiter nach ``art``, und weil sie
in einem ``except Exception: return None`` steckte, meldete die Plausibilitäts-
probe seither für jeden Jahrgang „nichts gefunden" statt zu prüfen.

**Wie geprüft wird.** Alle SQL-Literale werden per AST eingesammelt und gegen
eine frisch angelegte Datenbank *vorbereitet* (``EXPLAIN``) — vorbereitet,
nicht ausgeführt: SQLite löst dabei Tabellen- und Spaltennamen auf, rührt
aber keine Zeile an.

**Drei Dinge werden bewusst übersprungen**, und zwar mit Regel statt mit
Namensliste, damit die Ausnahme nicht mitwächst:

1. **f-Strings und zusammengesetzte Abfragen.** Ein Literal mit ``{`` ist nur
   ein Bruchstück; sein Rest steht woanders.
2. **Alles innerhalb der Migrationen.** Eine Migration spricht notwendig die
   ALTE Form: Sie liest die alte Spalte, um sie in die neue zu schreiben.
   Dass sie das darf, ist ihr ganzer Zweck.
3. **Tabellen und Spalten, die der Code selbst nachlegt.** Vor der Prüfung
   werden alle ``CREATE TABLE IF NOT EXISTS``- und ``ALTER TABLE … ADD
   COLUMN``-Literale ausgeführt — so gelten auch Tabellen, die erst beim
   ersten Schreiben entstehen.
"""
from __future__ import annotations

import ast
import sqlite3
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

BEREICHE = ("council", "kern", "scripts", "web/backend")
ANFANG = ("SELECT", "INSERT", "UPDATE", "DELETE", "REPLACE")

#: Stellen, die eine nicht vorhandene Form nennen dürfen — mit Grund.
#: Jede Zeile ist eine Entscheidung, keine Sammelstelle.
AUSNAHMEN = {
    # `prompts` legt seine Tabelle in kern/prompts.py an, nicht im Store.
    ("kern/store.py", "prompts"),
    # Datiertes Einmal-Werkzeug vom 08/2026: Es arbeitete auf der Form von
    # damals und wird nicht mehr ausgeführt. Der Dateiname sagt es.
    ("scripts/review_location_candidates_2026_08.py", "stadtteil"),
    # `_doppelte_bildspalte_aufloesen` räumt eine doppelt angelegte Spalte auf
    # und muss dafür die alte lesen. Es ist eine Migration, nur heißt sie
    # nicht so — deshalb greift die Regel oben hier nicht.
    ("council/store.py", "bild"),
}


def _ist_migration(name: str) -> bool:
    n = name.lower()
    return (n.startswith("_migrate") or "migrat" in n
            or "umbenenn" in n or "umschreib" in n or "umzieh" in n)


def _literale(baum: ast.AST):
    """``(zeile, sql, in_migration)`` für jedes eigenständige String-Literal.

    Teile eines f-Strings werden übersprungen: Sie sehen aus wie eine ganze
    Abfrage, sind aber nur das Stück vor dem nächsten eingesetzten Ausdruck.
    """
    in_fstring: set[int] = set()
    for k in ast.walk(baum):
        if isinstance(k, ast.JoinedStr):
            for kind in ast.walk(k):
                if isinstance(kind, ast.Constant):
                    in_fstring.add(id(kind))

    def laufen(knoten, migration: bool):
        for kind in ast.iter_child_nodes(knoten):
            hier = migration
            if isinstance(kind, (ast.FunctionDef, ast.AsyncFunctionDef)):
                hier = migration or _ist_migration(kind.name)
            if (isinstance(kind, ast.Constant) and isinstance(kind.value, str)
                    and id(kind) not in in_fstring):
                yield kind.lineno, kind.value.strip(), hier
            yield from laufen(kind, hier)

    yield from laufen(baum, False)


def _dateien():
    for bereich in BEREICHE:
        for pfad in sorted((WURZEL / bereich).rglob("*.py")):
            yield pfad.relative_to(WURZEL).as_posix(), pfad


@pytest.fixture(scope="module")
def datenbanken(tmp_path_factory):
    """Zwei frische Datenbanken plus alles, was der Code selbst nachlegt."""
    from council.store import CouncilStore
    from kern.store import Store

    ordner = tmp_path_factory.mktemp("sql")
    CouncilStore(ordner / "council.sqlite")
    Store(ordner / "ratslotse.sqlite")
    conns = [sqlite3.connect(ordner / "council.sqlite"),
             sqlite3.connect(ordner / "ratslotse.sqlite")]

    for _rel, pfad in _dateien():
        try:
            baum = ast.parse(pfad.read_text())
        except SyntaxError:
            continue
        for _zeile, sql, _mig in _literale(baum):
            oben = sql.upper()
            if "{" in sql:
                continue
            if oben.startswith("CREATE TABLE IF NOT EXISTS") or (
                    oben.startswith("ALTER TABLE") and "ADD COLUMN" in oben):
                for c in conns:
                    try:
                        c.execute(sql)
                        break
                    except sqlite3.Error:
                        pass
    return conns


def _vorbereitbar(conns, sql: str) -> str | None:
    """``None``, wenn die Anweisung auf einer der beiden Datenbanken aufgeht."""
    platzhalter = [None] * sql.count("?")
    fehler = []
    for c in conns:
        try:
            c.execute("EXPLAIN " + sql, platzhalter)
            return None
        except sqlite3.Error as e:
            fehler.append(str(e))
    if any("incomplete input" in f for f in fehler):
        return None                       # Bruchstück, kein vollständiger Satz
    if all("no such table" in f or "no such column" in f for f in fehler):
        return fehler[0]
    return None                           # anderer Grund — nicht unsere Sache


def test_kein_sql_nennt_eine_form_die_es_nicht_gibt(datenbanken):
    treffer = []
    geprueft = 0
    for rel, pfad in _dateien():
        try:
            baum = ast.parse(pfad.read_text())
        except SyntaxError:
            continue
        for zeile, sql, in_migration in _literale(baum):
            if in_migration or "{" in sql or "%s" in sql:
                continue
            if not sql.upper().startswith(ANFANG):
                continue
            geprueft += 1
            grund = _vorbereitbar(datenbanken, sql)
            if grund is None:
                continue
            fehlt = grund.rsplit(":", 1)[-1].strip()
            if (rel, fehlt) in AUSNAHMEN:
                continue
            treffer.append(f"{rel}:{zeile}  {grund}\n      {sql[:80].splitlines()[0]}")

    assert geprueft > 400, (
        f"Nur {geprueft} Anweisungen geprüft — der Sammler in dieser Datei "
        f"greift nicht mehr, der Test wacht also über nichts."
    )
    assert not treffer, (
        "Diese SQL-Anweisungen nennen eine Tabelle oder Spalte, die das "
        "Schema nicht hat:\n  " + "\n  ".join(treffer)
        + "\n\nMeist ist eine Umbenennung nur im Schema angekommen und hier "
          "nicht. Wenn die Stelle wirklich richtig ist (etwa weil eine andere "
          "Datenbank gemeint ist), gehört sie mit Grund in AUSNAHMEN."
    )
