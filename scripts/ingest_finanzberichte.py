#!/usr/bin/env python3
"""Jahresabschlüsse und Teilhaushalts-Pläne aus dem eigenen Bestand einlesen.

Beide Dokumenttypen hängen als Anlagen an Ratsvorlagen und liegen mit
Volltext in ``council_anlagen`` — der Protokoll-Scraper zieht sie ohnehin.
Dieses Skript liest sie aus, ohne etwas herunterzuladen:

- **Jahresabschluss** → ``council_ergebnisrechnung``: Ansatz und Ergebnis je
  Posten, also „geplant gegen tatsächlich", plus die Erträge nach Arten —
  zweimal: für die Kernverwaltung gesamt und je Teilhaushalt. Die
  Teilhaushalts-Ebene wird nur gespeichert, wenn ihre Summe zur
  Gesamtrechnung passt (``finanzberichte.summenprobe``).
- **Teilhaushalts-Pläne (THH)** → ``council_produkte``: was einzelne Aufgaben
  kosten, mit Produktnummer und Amt — dazu der Steckbrief je Produkt
  (Kurzbeschreibung, Auftragsgrundlage, Grad der Beeinflussbarkeit,
  Wirkungskreis, Zielgruppe). Wie viele Produkte welches Feld tragen, weist
  der Lauf am Ende aus; die Zahl steht später so auf der Produktseite.

Beide Parser verlangen eine im Dokument selbst dokumentierte Rechenprobe
(siehe ``council/finanzberichte.py``); was sie nicht besteht, wird
übersprungen und am Ende als übersprungen ausgewiesen.

**Woran ein Dokument erkannt wird, steht nicht mehr hier**, sondern in
``council/finanzquellen.py`` — dieselbe Definition benutzt der Cron
``scripts/check_finanzdaten.py``, der neue Jahrgänge von allein nachzieht.
Dieses Skript bleibt der Weg von Hand: Es liest **alle** Jahrgänge neu ein,
auch die schon gespeicherten, und ist damit das Mittel, einen verbesserten
Parser über den Bestand zu ziehen (was der Cron bewusst nicht tut)::

    python scripts/ingest_finanzberichte.py
    python scripts/ingest_finanzberichte.py --nur jahresabschluss
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

#: Kennzahlen, die jede Schicht führt — sie brauchen im gemeinsamen Bericht
#: einen Präfix, sonst überschriebe die letzte Schicht die vorherigen.
_EIGEN = ("neue_jahrgaenge", "bestand_geschuetzt")


def main() -> int:
    ap = argparse.ArgumentParser(description="Jahresabschlüsse und Teilhaushalte einlesen")
    ap.add_argument("--nur", choices=["jahresabschluss", "teilhaushalte"], default=None)
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()

    store = CouncilStore(Path(args.db))
    p = finanzquellen.Protokoll()
    ergebnis: dict = {}

    def uebernehmen(name: str, teil: dict) -> None:
        for schluessel, wert in teil.items():
            ergebnis[f"{name}_{schluessel}" if schluessel in _EIGEN else schluessel] = wert

    try:
        if args.nur != "teilhaushalte":
            print("Jahresabschlüsse (Ergebnisrechnung):")
            uebernehmen("jahresabschluss", finanzquellen.lies_jahresabschluesse(store, p))
            print("Schlussberichte des Rechnungsprüfungsamts:")
            uebernehmen("rpa", finanzquellen.lies_schlussbericht_fundstellen(store, p))
        if args.nur != "jahresabschluss":
            print("Teilhaushalte (Produktebene):")
            uebernehmen("teilhaushalt", finanzquellen.lies_teilhaushalte(store, p))
    finally:
        store.close()
    print(f"Fertig: {ergebnis}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
