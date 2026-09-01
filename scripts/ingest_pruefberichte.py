#!/usr/bin/env python3
"""Prüfungsfeststellungen aus den Schlussberichten des Rechnungsprüfungsamts.

Bewusst getrennt von ``ingest_finanzberichte.py``: Dort geht es um Zahlen aus
dem Jahresabschluss, hier um Prosa aus einem anderen Dokument einer anderen
Stelle. Beide lesen nur ``council_attachments`` und laden nichts nach::

    python scripts/ingest_pruefberichte.py
    python scripts/ingest_pruefberichte.py --trocken    # nur zählen

Die Auswahl der Dokumente ist der heikle Teil und läuft deshalb **nicht über
das Label**; wie sie stattdessen läuft, steht mit allen anderen
Quellendefinitionen in ``council/finanzquellen.py``. Von dort holt sich auch
der Cron ``scripts/check_finanzdaten.py`` seine Erkennung — dieses Skript
bleibt der Weg von Hand, der **alle** Jahrgänge neu einliest.

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

from council import finanzquellen  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Prüfungsfeststellungen aus den RPA-Schlussberichten einlesen")
    ap.add_argument("--trocken", action="store_true",
                    help="nur zählen, nichts schreiben")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    ap.add_argument("--auch-schrumpfen", action="store_true",
                    help="einen Jahrgang auch dann ersetzen, wenn er dabei deutlich "
                         "kleiner wird — für den Fall, dass genau das die Absicht ist. "
                         "Ein LEERES Ergebnis ersetzt trotzdem nichts.")
    args = ap.parse_args()

    store = CouncilStore(Path(args.db))
    p = finanzquellen.Protokoll()
    try:
        bericht = finanzquellen.lies_pruefungsfeststellungen(
            store, p, schuetzen=not args.auch_schrumpfen, trocken=args.trocken)
        if not args.trocken:
            store.herkunft_aufraeumen()
        luecken = store.herkunft_luecken()
    finally:
        store.close()

    if luecken:
        # Sollzustand ist leer: Jede Zeile weiß, woher sie kommt.
        print(f"Ohne Herkunft: {luecken}", file=sys.stderr)
    je_jahr = bericht["je_jahr"]
    gesamt: Counter = Counter()
    for d in je_jahr.values():
        gesamt.update(d["marken"])
    print(f"Fertig: {len(je_jahr)} Jahrgänge · "
          f"{bericht['feststellungen']} Feststellungen ({dict(gesamt)}) · "
          f"{bericht['verworfen']} verworfen"
          + (" · TROCKENLAUF, nichts geschrieben" if args.trocken else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
