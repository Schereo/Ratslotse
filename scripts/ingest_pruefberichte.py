#!/usr/bin/env python3
"""Prüfungsfeststellungen aus den Schlussberichten des Rechnungsprüfungsamts.

Bewusst getrennt von ``ingest_finanzberichte.py``: Dort geht es um Zahlen aus
dem Jahresabschluss, hier um Prosa aus einem anderen Dokument einer anderen
Stelle. Beide lesen nur ``council_anlagen``, laden nichts nach und laufen
einmal je neuem Jahrgang — es gibt keinen Cron::

    python scripts/ingest_pruefberichte.py
    python scripts/ingest_pruefberichte.py --trocken    # nur zählen

Die Auswahl der Dokumente ist der heikle Teil und läuft deshalb **nicht über
das Label**. „Schlussbericht JA 2017" (``document_id`` 192039) ist der Bericht
zum Eigenbetrieb Gebäudewirtschaft; dazu kommen jedes Jahr die formgleichen
Berichte zur Klävemann-Stiftung, zur Vereinten Oldenburger Sozialstiftung, zu
AWB und EGH. Sie alle heißen ähnlich und tragen dieselbe Jahreszahl. Getrennt
wird über den Textanfang (``pruefberichte.erkenne_jahrgang``), der zugleich
sagt, zu welchem Jahresabschluss der Bericht gehört.

Am Ende steht je Jahrgang, wie viele Feststellungen gefunden und wie viele
verworfen wurden. Die Zahl der Verworfenen ist die eigentliche Kennzahl: Sie
bleibt bei 0, solange das Dokumentformat hält. Steigt sie, hat sich etwas
geändert und es ist Zeit für einen Blick in den Bericht — nicht für eine
gelockerte Regel.
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council import pruefberichte  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def _kandidaten(store: CouncilStore) -> list[dict]:
    """Anlagen, die ein Schlussbericht des RPA über die **Kernverwaltung**
    sein könnten — vorgefiltert in SQL, entschieden am Textanfang.

    Der SQL-Filter ist absichtlich grob: Im Extrakt steht der Titel über vier
    Zeilen verteilt, ein ``LIKE 'Schlussbericht des Rechnungsprüfungsamtes%'``
    fände deshalb keinen einzigen Bericht. Gefiltert wird nur, um nicht alle
    Anlagen des Bestands durch den Parser zu schicken."""
    rows = store._conn.execute(
        "SELECT document_id, label, url, raw_text FROM council_anlagen "
        "WHERE raw_text LIKE '%Rechnungsprüfungsamtes%' AND n_pages > 30 "
        "ORDER BY document_id").fetchall()
    return [dict(r) for r in rows]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Prüfungsfeststellungen aus den RPA-Schlussberichten einlesen")
    ap.add_argument("--trocken", action="store_true",
                    help="nur zählen, nichts schreiben")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()

    store = CouncilStore(Path(args.db))
    je_jahr: dict[int, dict] = {}
    try:
        kandidaten = _kandidaten(store)
        for r in kandidaten:
            ergebnis = pruefberichte.parse_feststellungen(r["raw_text"] or "")
            jahr = ergebnis["jahr"]
            if jahr is None:
                continue  # Stiftung, Eigenbetrieb oder kaputter Textextrakt
            gefunden = ergebnis["feststellungen"]
            if not gefunden:
                print(f"  {jahr}: keine Feststellung lesbar "
                      f"(Legende {sorted(ergebnis['legende']) or '—'}) — übersprungen",
                      file=sys.stderr)
                continue
            if jahr in je_jahr:
                print(f"  {jahr}: zweites Dokument ({r['document_id']}) — übersprungen",
                      file=sys.stderr)
                continue
            marken = Counter(f["marke"] for f in gefunden)
            if not args.trocken:
                store.save_pruefbericht(jahr, gefunden, r["label"], r["url"])
            je_jahr[jahr] = {"feststellungen": len(gefunden),
                             "verworfen": len(ergebnis["verworfen"]),
                             "marken": dict(marken)}
            marken_text = " · ".join(
                f"{m} {marken[m]}" for m in pruefberichte.MARKEN if marken.get(m))
            print(f"  {jahr}: {len(gefunden)} Feststellungen ({marken_text})"
                  f" · verworfen {len(ergebnis['verworfen'])}"
                  f" · Dokument {r['document_id']}")
            for v in ergebnis["verworfen"]:
                print(f"      verworfen: {v}", file=sys.stderr)
    finally:
        store.close()

    gesamt = Counter()
    for d in je_jahr.values():
        gesamt.update(d["marken"])
    print(f"Fertig: {len(je_jahr)} Jahrgänge · "
          f"{sum(d['feststellungen'] for d in je_jahr.values())} Feststellungen "
          f"({dict(gesamt)}) · "
          f"{sum(d['verworfen'] for d in je_jahr.values())} verworfen"
          + (" · TROCKENLAUF, nichts geschrieben" if args.trocken else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
