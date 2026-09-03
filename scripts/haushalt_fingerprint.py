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


def _ausdruck(conn: sqlite3.Connection, tabelle: str,
              mit_herkunft: bool = True) -> tuple[str, str, list[str]]:
    """``(SELECT-Liste, FROM/JOIN-Teil, Feldnamen)`` für eine Tabelle.

    Die Verweise werden im SQL aufgelöst statt in Python: Bei 17.814 Zeilen
    wären das sonst zwei Abfragen je Zeile.

    Die Spalten gehen NACH NAMEN sortiert hinein, nicht in der Reihenfolge des
    Schemas. Das ist keine Kosmetik, sondern der Grund, warum dieser Vergleich
    überhaupt funktioniert: ``PRAGMA table_info`` liefert die PHYSISCHE
    Reihenfolge, und die hängt an der Migrationsgeschichte. Auf dev sind
    Spalten einzeln per ALTER TABLE gewachsen, auf Prod am Stück aus dem
    ``SCHEMA`` entstanden — ``council_products`` trägt dieselben 19 Spalten in
    verschiedener Folge, ``council_budget_amendments`` und
    ``council_business_plans`` ebenso.

    Die erste Fassung verkettete positionsweise und meldete daraufhin alle 623
    Zeilen als abweichend, obwohl jede Zahl übereinstimmte. Ein
    Vergleichswerkzeug, das denselben Bestand für verschieden erklärt, ist
    schlimmer als keines: Es schickt jemanden auf die Suche nach einem Fehler,
    den es nicht gibt.
    """
    cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{tabelle}")')]
    genutzt = sorted(c for c in cols if c not in ORTSGEBUNDEN)
    teile = [f't."{c}"' for c in genutzt]
    namen = list(genutzt)
    frm = f'"{tabelle}" t'
    if "herkunft_id" in cols and mit_herkunft:
        # Der sha256 der Quelle statt ihrer Nummer. LEFT JOIN, weil eine
        # fehlende Herkunft ein Befund ist und kein Grund, die Zeile zu
        # verschweigen — sie fällt dann als NULL auf.
        teile.append("p.key")
        namen.append("herkunft")
        frm += ' LEFT JOIN council_provenance p ON p.id = t.herkunft_id'
    if "decision_id" in cols:
        # Der dreistufige Beschluss-Schlüssel aus dem Ratsinformationssystem.
        teile.append("d.ksinr || '/' || COALESCE(d.position, '') "
                     "|| '/' || COALESCE(d.item_number, '')")
        namen.append("beschluss")
        frm += ' LEFT JOIN council_decisions d ON d.id = t.decision_id'
    return ", ".join(teile), frm, namen


def fingerabdruck(conn: sqlite3.Connection, tabelle: str,
                  mit_herkunft: bool = True) -> tuple[int, str, list[str]]:
    """``(Zeilen, Hash, Zeilenhashes)`` einer Tabelle.

    Sortiert wird über den fertigen Zeilentext und nicht über Spalten: Welche
    Spalten eine Tabelle sortierbar machen, ist von Tabelle zu Tabelle
    verschieden, und eine falsche Reihenfolge würde einen Unterschied
    behaupten, den es nicht gibt.

    Die Spalten selbst gehen NAMENSSORTIERT und mit ihrem Namen in den Hash
    (siehe `_ausdruck`) — sonst hinge das Ergebnis an der Migrationsgeschichte
    der jeweiligen Umgebung.
    """
    auswahl, frm, namen = _ausdruck(conn, tabelle, mit_herkunft)
    zeilen = []
    for r in conn.execute(f"SELECT {auswahl} FROM {frm}"):
        # Jeder Wert trägt seinen Spaltennamen. Damit ist der Abdruck
        # unabhängig von der Spaltenreihenfolge UND merkt eine Umbenennung,
        # statt sie stillschweigend wegzusortieren. Die Benennung passiert
        # hier und nicht im SQL: Der Platzhalter für NULL ist ein Nullbyte, und
        # das lässt SQLite in einer Abfrage nicht durch.
        # `\x00` als Platzhalter für NULL, nicht der Leerstring: „nie gefüllt"
        # und „leer gelesen" sind zwei verschiedene Befunde, und ein Werkzeug,
        # das sie verwischt, verschweigt genau die Sorte Lücke, die es finden
        # soll. Genau diese Verwechslung ist beim Umbau hier passiert und von
        # `tests/test_haushalt_fingerprint.py` gefangen worden. Das Nullbyte
        # steht deshalb in Python und nicht im SQL — dort lässt SQLite es nicht
        # durch ("the query contains a null character").
        text = "\x1f".join(f"{n}={chr(0) if v is None else v}"
                           for n, v in zip(namen, r))
        zeilen.append(hashlib.sha256(text.encode()).hexdigest())
    zeilen.sort()
    gesamt = hashlib.sha256("".join(zeilen).encode()).hexdigest()
    return len(zeilen), gesamt, zeilen


def spaltenabdruck(conn: sqlite3.Connection, tabelle: str) -> list[tuple[str, str]]:
    """``[(spalte, hash)]`` — je Spalte ein Abdruck über ihre sortierten Werte.

    Der Schritt NACH einem Befund, und der wichtigste: Weicht eine Tabelle in
    JEDER Zeile ab, ist das fast nie ein Datenproblem, sondern eine einzelne
    Spalte, die überall anders aussieht — eine VM-eigene Nummer, ein Pfad, ein
    Zeitstempel unter unerwartetem Namen. Zeilenweise sieht man das nicht: Dort
    weichen einfach alle 623 ab.

    Sortiert wird JE SPALTE für sich. Die Zeilenzuordnung geht dabei verloren,
    und das ist Absicht: Gefragt ist „steht in dieser Spalte dieselbe Menge an
    Werten?", nicht „in derselben Reihenfolge". Eine Spalte, die hier
    übereinstimmt, kann als Ursache ausgeschlossen werden.
    """
    cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{tabelle}")')]
    aus = []
    for c in cols:
        werte = sorted(
            "\x00" if v[0] is None else str(v[0])
            for v in conn.execute(f'SELECT "{c}" FROM "{tabelle}"'))
        aus.append((c, hashlib.sha256("\x1f".join(werte).encode()).hexdigest()))
    return aus


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--db", help="Pfad zur council.sqlite (Vorgabe: COUNCIL_DB bzw. data/)")
    p.add_argument("--tabelle", help="nur diese eine Tabelle")
    p.add_argument("--zeilen", action="store_true",
                   help="die Einzelhashes ausgeben — für den Vergleich INNERHALB "
                        "einer Tabelle, wenn ihr Gesamthash abweicht")
    p.add_argument("--spalten", action="store_true",
                   help="je Spalte einen Abdruck ausgeben statt je Zeile. Der "
                        "Schritt nach einem Befund: Weicht eine Tabelle in JEDER "
                        "Zeile ab, nennt das hier die Spalte, die daran schuld "
                        "ist. Auch das nur als Hash, nie als Inhalt.")
    p.add_argument("--ohne-herkunft", action="store_true",
                   help="den Beleg NICHT mitzählen, nur die Zahlen. Trennt die "
                        "beiden Diagnosen: Weichen zwei Umgebungen auch ohne "
                        "Herkunft ab, stehen dort andere ZAHLEN; weichen sie nur "
                        "MIT ab, sind die Zahlen gleich und stammen aus einem "
                        "anders belegten Dokument. Das ist ein sehr großer "
                        "Unterschied und die erste Frage bei jedem Befund.")
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
                n, h, einzeln = fingerabdruck(conn, name, not args.ohne_herkunft)
            except sqlite3.OperationalError as exc:
                print(f"{name:42} FEHLER  {exc}")
                continue
            print(f"{name:42} {n:>6}  {h}")
            if args.spalten:
                for spalte, sh in spaltenabdruck(conn, name):
                    print(f"    {name}\t{spalte}\t{sh}")
            if args.zeilen:
                # MIT Tabellenname, damit sich die Ausgabe je Tabelle
                # auseinandernehmen lässt. Und bewusst nur Hashes: Diese Zeilen
                # landen in Action-Protokollen, und die sind bei einem
                # öffentlichen Repo öffentlich. `council_donations` trägt
                # Spendernamen — ein Inhalts-Dump wäre hier ein Datenleck und
                # kein Diagnosewerkzeug.
                for z in einzeln:
                    print(f"    {name}\t{z}")
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
