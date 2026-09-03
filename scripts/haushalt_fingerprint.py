#!/usr/bin/env python3
"""Fingerabdruck der Finanzdaten — damit sich zwei Umgebungen vergleichen lassen.

**Warum es das braucht.** Der Ops-Lauf `ops-finanzdaten-ingest.yml` liest die
Haushaltszahlen auf einer VM ein. Ob er das RICHTIG getan hat, sagt seine
Zeilenzahl nur halb: Zwei Umgebungen können dieselbe Anzahl Zeilen tragen und
in jeder einzelnen Zahl auseinanderliegen. Umgekehrt ist ein bloßer
`sqlite3 .dump`-Vergleich unbrauchbar — er meldet Unterschiede, die keine sind.

**Das ist der eigentliche Punkt dieser Datei.** Drei Spaltenarten sind je VM
verschieden, ohne dass inhaltlich etwas abweicht:

* ``id`` — `INTEGER PRIMARY KEY AUTOINCREMENT`, je Maschine eigen. Auf der
  Dev-Kopie hat `council_provenance` 1.428 Zeilen bei einer höchsten id von
  1.962; die Lücken entstehen bei jedem ROLLBACK neu und sind reine Historie.
* ``herkunft_id`` — zeigt in genau diese Tabelle. 17.814 Zeilen über 56
  Tabellen tragen so einen Verweis. Verglichen wird deshalb **nicht die
  Nummer, sondern das Papier dahinter**: `council_provenance.key` ist ein
  sha256 über die Quelle und damit über alle VMs derselbe. Genau das ist die
  Frage, die zählt — führt dieselbe Zahl hier und dort zu demselben PDF?
* ``decision_id`` — ebenfalls VM-eigen. Aufgelöst auf den dreistufigen
  Beschluss-Schlüssel (`ksinr` / `position` / `item_number`), der aus dem
  Ratsinformationssystem stammt und deshalb überall gleich ist.

Zeitstempel des Laufs (``fetched_at`` und Verwandte) fallen heraus: Sie sagen,
WANN gelesen wurde, nicht WAS.

**Welche Tabellen.** Nicht die von Hand gepflegte Liste in
`council/herkunft.py`, sondern die aus dem **Schema** — jede Tabelle mit einer
`herkunft_id`. Dieselbe Begründung wie bei
`CouncilStore._herkunft_verweistabellen()`: Eine vergessene Liste macht den
Vergleich blind, ohne dass es auffällt.

Aufruf (auf der VM, dort liegt die Datenbank)::

    .venv/bin/python scripts/haushalt_fingerprint.py

Die Ausgabe ist zeilenweise `tabelle  zeilen  hash` und dafür gemacht, mit
`diff` gegen dieselbe Ausgabe der anderen VM zu laufen. Eine abweichende Zeile
nennt die Tabelle; wer dann wissen will, WELCHE Zahl abweicht, ruft mit
``--tabelle <name> --zeilen`` die Einzelhashes ab.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]

#: Spalten, die je Umgebung verschieden sind, ohne inhaltlich abzuweichen.
#: `id` und `herkunft_id` sind Autoincrement-Nummern, der Rest sind
#: Lauf-Zeitstempel. `document_id` steht bewusst NICHT hier: Das ist die
#: getfile-Nummer des Ratsinformationssystems und über alle VMs dieselbe — sie
#: soll verglichen werden.
ORTSGEBUNDEN = {"id", "herkunft_id", "decision_id",
                "fetched_at", "created_at", "updated_at", "ingested_at"}


def _db_pfad(angabe: str | None) -> Path:
    if angabe:
        return Path(angabe)
    return Path(os.environ.get("COUNCIL_DB") or WURZEL / "data" / "council.sqlite")


def _tabellen(conn: sqlite3.Connection) -> list[str]:
    """Jede Tabelle mit `herkunft_id` — aus dem Schema, nicht aus einer Liste."""
    aus = []
    for (name,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        cols = {r[1] for r in conn.execute(f'PRAGMA table_info("{name}")')}
        if "herkunft_id" in cols:
            aus.append(name)
    return aus


def _ausdruck(conn: sqlite3.Connection, tabelle: str) -> tuple[str, str]:
    """``(SELECT-Liste, FROM/JOIN-Teil)`` für eine Tabelle.

    Die Verweise werden im SQL aufgelöst statt in Python: Bei 17.814 Zeilen
    wären das sonst zwei Abfragen je Zeile.
    """
    cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{tabelle}")')]
    teile = [f't."{c}"' for c in cols if c not in ORTSGEBUNDEN]
    frm = f'"{tabelle}" t'
    if "herkunft_id" in cols:
        # Der sha256 der Quelle statt ihrer Nummer. LEFT JOIN, weil eine
        # fehlende Herkunft ein Befund ist und kein Grund, die Zeile zu
        # verschweigen — sie fällt dann als NULL auf.
        teile.append("p.key")
        frm += ' LEFT JOIN council_provenance p ON p.id = t.herkunft_id'
    if "decision_id" in cols:
        # Der dreistufige Beschluss-Schlüssel aus dem Ratsinformationssystem.
        teile.append("d.ksinr || '/' || COALESCE(d.position, '') "
                     "|| '/' || COALESCE(d.item_number, '')")
        frm += ' LEFT JOIN council_decisions d ON d.id = t.decision_id'
    return ", ".join(teile), frm


def fingerabdruck(conn: sqlite3.Connection, tabelle: str) -> tuple[int, str, list[str]]:
    """``(Zeilen, Hash, Zeilenhashes)`` einer Tabelle.

    Sortiert wird über den fertigen Zeilentext und nicht über Spalten: Welche
    Spalten eine Tabelle sortierbar machen, ist von Tabelle zu Tabelle
    verschieden, und eine falsche Reihenfolge würde einen Unterschied
    behaupten, den es nicht gibt.
    """
    auswahl, frm = _ausdruck(conn, tabelle)
    zeilen = []
    for r in conn.execute(f"SELECT {auswahl} FROM {frm}"):
        text = "\x1f".join("\x00" if v is None else str(v) for v in r)
        zeilen.append(hashlib.sha256(text.encode()).hexdigest())
    zeilen.sort()
    gesamt = hashlib.sha256("".join(zeilen).encode()).hexdigest()
    return len(zeilen), gesamt, zeilen


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--db", help="Pfad zur council.sqlite (Vorgabe: COUNCIL_DB bzw. data/)")
    p.add_argument("--tabelle", help="nur diese eine Tabelle")
    p.add_argument("--zeilen", action="store_true",
                   help="die Einzelhashes ausgeben — für den Vergleich INNERHALB "
                        "einer Tabelle, wenn ihr Gesamthash abweicht")
    args = p.parse_args(argv)

    pfad = _db_pfad(args.db)
    if not pfad.exists():
        print(f"✗ keine Datenbank unter {pfad}", file=sys.stderr)
        return 2
    # Nur lesend: Das Skript läuft neben einem laufenden Dienst.
    conn = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
    try:
        namen = [args.tabelle] if args.tabelle else _tabellen(conn)
        if not namen:
            print("✗ keine Tabelle mit herkunft_id gefunden — Schema geprüft?", file=sys.stderr)
            return 2
        ohne_herkunft = 0
        for name in namen:
            try:
                n, h, einzeln = fingerabdruck(conn, name)
            except sqlite3.OperationalError as exc:
                print(f"{name:42} FEHLER  {exc}")
                continue
            print(f"{name:42} {n:>6}  {h}")
            if args.zeilen:
                for z in einzeln:
                    print(f"    {z}")
        # Dieselbe Zahl, die der Ops-Lauf meldet — hier noch einmal, damit ein
        # Vergleich der beiden Ausgaben sie mitprüft.
        for name in namen:
            cols = {r[1] for r in conn.execute(f'PRAGMA table_info("{name}")')}
            if "herkunft_id" not in cols:
                continue
            try:
                ohne_herkunft += conn.execute(
                    f'SELECT COUNT(*) FROM "{name}" WHERE herkunft_id IS NULL').fetchone()[0]
            except sqlite3.OperationalError:
                pass
        print(f"\n{len(namen)} Tabellen, {ohne_herkunft} Zeilen ohne Herkunft")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
