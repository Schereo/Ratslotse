#!/usr/bin/env python3
"""Sucht gespeicherte Werte, die im Code nicht mehr vorkommen.

**Das Problem.** Beim Umbau auf englische Bezeichner benennt ein Schnitt
Spalten um und trägt dafür ein Migrationspaar ein. Manche dieser Begriffe
stehen aber zusätzlich als **Wert** in einer Zeile:
``council_finanzrechnung.role`` führt ``'saldo_verwaltung'``,
``council_konzern_posten.role`` führt ``'ao_ertraege'``,
``council_herkunft.probe`` führt ``'anlagen_buchwert'``. Wird nur die Spalte
migriert, schreibt der Code danach ``'balance_operating'``, in der Datenbank
steht weiter der deutsche Wert — und **jede Abfrage danach findet nichts**.

Kein Test schlägt an: Frische Datenbanken sind leer, und die Testfixtures
schreiben ohnehin schon die neuen Werte. Genau so sind am 31.08.2026 drei
Stellen mit 90 Zeilen auf dev unbemerkt tot gegangen.

**Der Ansatz.** Nicht nach alten Namen suchen (die müsste jemand pflegen),
sondern umgekehrt: Jeder gespeicherte Wert einer *schlüsselartigen* Spalte
sollte im Quelltext als Zeichenkette vorkommen — der Code fragt ihn ja ab.
Ein Wert, den niemand mehr nennt, ist entweder tot oder ein Umbenennungs-Opfer.

Schlüsselartig heißt: höchstens :data:`MAX_WERTE` verschiedene Werte, und alle
sehen aus wie Bezeichner (``^[a-z][a-z0-9_]*$``). Das hält Freitext draußen —
Steuerarten („Grundsteuer A"), Rollen aus dem Ratsinformationssystem
(„Ratsmitglied") und Gebühreneinheiten („Mg") sind Text aus Dokumenten, kein
Schlüsselwort des Codes.

Aufruf::

    python scripts/pruefe_wertreste.py data/council.sqlite

Exit 1, sobald ein Fund vorliegt — so lässt es sich hinter einen
Migrationslauf hängen.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]

#: Mehr verschiedene Werte als das: keine Schlüsselspalte, sondern Freitext.
MAX_WERTE = 25

#: Wo der Code nach den Werten durchsucht wird.
QUELLEN = ("council", "kern", "scripts", "web/backend", "web/frontend/app",
           "web/frontend/components", "web/frontend/lib", "ios/Packages", "tests")
ENDUNGEN = {".py", ".ts", ".tsx", ".swift"}

_BEZEICHNER = re.compile(r"^[a-z][a-z0-9_]*$")


#: Migrations- und Alias-Paare: ``("alt", "neu")``. Sie werden aus dem
#: Quelltext GESCHNITTEN, bevor gesucht wird — sonst gilt jeder alte Name als
#: „kommt im Code vor", nur weil seine eigene Migration ihn nennt. Genau daran
#: wäre diese Prüfung sonst blind für das, wofür es sie gibt.
_PAAR = re.compile(r"""\(\s*["'][a-z][a-z0-9_]*["']\s*,\s*["'][a-z][a-z0-9_]*["']\s*\)""")


def quelltext() -> str:
    teile = []
    for ordner in QUELLEN:
        wurzel = WURZEL / ordner
        if not wurzel.exists():
            continue
        for p in wurzel.rglob("*"):
            if p.suffix in ENDUNGEN and p.is_file() and "node_modules" not in str(p):
                teile.append(p.read_text(errors="ignore"))
    return _PAAR.sub(" ", "\n".join(teile))


def funde(db: Path, code: str) -> list[tuple[str, str, list[tuple[str, int]]]]:
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    aus = []
    tabellen = [t for (t,) in c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%_fts_%'")]
    for tabelle in tabellen:
        for zeile in c.execute(f"PRAGMA table_info({tabelle})"):
            spalte, typ = zeile[1], (zeile[2] or "").upper()
            if "TEXT" not in typ and "CHAR" not in typ:
                continue
            try:
                werte = [w for (w,) in c.execute(
                    f"SELECT DISTINCT {spalte} FROM {tabelle} "
                    f"WHERE {spalte} IS NOT NULL LIMIT {MAX_WERTE + 1}")]
            except sqlite3.OperationalError:
                continue
            if not werte or len(werte) > MAX_WERTE:
                continue
            if not all(isinstance(w, str) and _BEZEICHNER.match(w) for w in werte):
                continue
            stumm = []
            for w in sorted(werte):
                if f'"{w}"' in code or f"'{w}'" in code:
                    continue
                n = c.execute(f"SELECT count(*) FROM {tabelle} WHERE {spalte} = ?",
                              (w,)).fetchone()[0]
                stumm.append((w, n))
            if stumm:
                aus.append((tabelle, spalte, stumm))
    c.close()
    return aus


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("db", type=Path, help="Pfad zur SQLite-Datei")
    args = p.parse_args()
    if not args.db.exists():
        print(f"FEHLT: {args.db}")
        return 2

    gefunden = funde(args.db, quelltext())
    print(f"{args.db.name}: Schlüsselspalten gegen den Quelltext geprüft.")
    if not gefunden:
        print("Jeder gespeicherte Schlüssel kommt im Code vor.")
        return 0
    for tabelle, spalte, stumm in gefunden:
        liste = ", ".join(f"{w} ({n} Zeilen)" for w, n in stumm)
        print(f"  {tabelle}.{spalte}: {liste}")
    print("\nDiese Werte nennt der Code nirgends mehr. Entweder fehlt ein\n"
          "`_werte_umschreiben` in `_migrate` — oder der Wert ist tot und die\n"
          "Zeilen gehören aufgeräumt. Beides ist eine Entscheidung, kein Zufall.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
