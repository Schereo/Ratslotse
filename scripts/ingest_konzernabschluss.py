#!/usr/bin/env python3
"""Den Konzern Stadt Oldenburg aus den konsolidierten Gesamtabschlüssen einlesen.

Einmal im Jahr rechnet die Stadt Kernverwaltung, Eigenbetriebe und
Beteiligungen zu **einer** Rechnung zusammen (§ 128 NKomVG). Das
Rechnungsprüfungsamt prüft das Ergebnis und legt seinen Bericht dem Rat als
Anlage vor — mit Volltext, den der Protokoll-Scraper ohnehin zieht. Dieses
Skript liest ihn aus, ohne etwas herunterzuladen:

- ``council_konzern_posten``   — die Gesamtergebnisrechnung des Konzerns
- ``council_konzern_traeger``  — dieselben Summen, aufgeteilt auf die acht
  einbezogenen Aufgabenträger plus die Zeile „Konsolidierung"

Vier Proben entscheiden, was gespeichert wird; sie stehen in
``council/finanzquellen.lies_konzernabschluesse`` beschrieben und gelten hier
wie im Cron ``scripts/check_finanzdaten.py``, der neue Jahrgänge von allein
nachzieht. **Woran ein Dokument erkannt wird, steht nicht hier**, sondern in
``council/finanzquellen.py`` — die Labels dieser Reihe sind wertlos (der
Jahrgang 2016 heißt schlicht „Anlage"), erkannt wird am Textkopf.

Dieses Skript bleibt der Weg von Hand: Es liest **alle** Jahrgänge neu ein,
auch die schon gespeicherten, und ist damit das Mittel, einen verbesserten
Parser über den Bestand zu ziehen (was der Cron bewusst nicht tut)::

    python scripts/ingest_konzernabschluss.py
    python scripts/ingest_konzernabschluss.py --nur-fehlende
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council import finanzquellen  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Konsolidierte Gesamtabschlüsse einlesen (Konzern Stadt)")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    ap.add_argument("--nur-fehlende", action="store_true",
                    help="nur Jahrgänge lesen, die noch nicht im Bestand stehen "
                         "— so arbeitet auch der Cron")
    ap.add_argument("--auch-schrumpfen", action="store_true",
                    help="einen Jahrgang auch dann ersetzen, wenn er dabei deutlich "
                         "kleiner wird. Ein LEERES Ergebnis ersetzt trotzdem nichts.")
    args = ap.parse_args()

    store = CouncilStore(Path(args.db))
    p = finanzquellen.Protokoll()
    try:
        print("Konsolidierte Gesamtabschlüsse (Konzern Stadt Oldenburg):")
        ergebnis = finanzquellen.lies_konzernabschluesse(
            store, p, nur_fehlende=args.nur_fehlende,
            schuetzen=not args.auch_schrumpfen)
    finally:
        store.close()
    print(f"Fertig: {ergebnis}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
