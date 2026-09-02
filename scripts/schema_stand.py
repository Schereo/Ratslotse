#!/usr/bin/env python3
"""Schreibt die Form einer SQLite-Datenbank als DDL — ohne eine Datenzeile.

Wozu: ``tests/test_migration_bestand.py`` prüft die Migration gegen einen
**gewachsenen** Bestand statt gegen eine frische Datenbank. Der Bestand liegt
als Schema-Auszug in ``tests/schema_staende/``; dieses Skript erzeugt ihn.

Aufruf::

    python scripts/schema_stand.py data/council.sqlite \\
        > tests/schema_staende/dev-council.sql

Ausgegeben wird nur, was in ``sqlite_master`` steht: Tabellen, Indizes,
Trigger, Views. Werte werden nicht gelesen, die Datenbank nur lesend geöffnet.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("datenbank", type=Path)
    args = p.parse_args()

    if not args.datenbank.exists():
        print(f"Nicht gefunden: {args.datenbank}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(f"file:{args.datenbank}?mode=ro", uri=True)
    try:
        zeilen = conn.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' "
            "ORDER BY CASE type WHEN 'table' THEN 0 WHEN 'index' THEN 1 "
            "ELSE 2 END, name"
        ).fetchall()
    finally:
        conn.close()

    # Schattentabellen der Volltextindizes weglassen. FTS5 legt zu jedem
    # `CREATE VIRTUAL TABLE x USING fts5(…)` selbst `x_config`, `x_data`,
    # `x_docsize`, `x_idx` und ggf. `x_content` an — sie stehen in
    # `sqlite_master`, dürfen aber nicht mitgeschrieben werden: Beim
    # Einspielen legt bereits die virtuelle Tabelle sie an, und die zweite
    # Anweisung stirbt mit „table already exists".
    virtuell = [n for typ, n, sql in zeilen
                if typ == "table" and "VIRTUAL TABLE" in sql.upper()]
    schatten = {f"{v}_{teil}" for v in virtuell
                for teil in ("config", "data", "docsize", "idx", "content")}

    geschrieben = 0
    for _typ, name, sql in zeilen:
        if name in schatten:
            continue
        print(f"{sql.strip()};")
        geschrieben += 1
    print(f"# {geschrieben} Objekte "
          f"({len(zeilen) - geschrieben} FTS-Schattentabellen ausgelassen)",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
