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
- **Gesamtergebnishaushalt** (Anlage 005 des Haushaltsplans) →
  ``council_ergebnishaushalt``: dieselben Einnahme- und Ausgabearten, aber für
  Jahre, die noch **keinen** Jahresabschluss haben. Ansatz und mittelfristige
  Finanzplanung stehen dabei getrennt in der Tabelle — das Dokument nennt
  beides „Ansatz", beschlossen ist aber nur ein Jahr.
- **Stellenplan** (Anlage 21/22 desselben Plans) → ``council_stellenplan``:
  die einzige Schicht, die nicht in Euro rechnet. Wie viele Stellen die Stadt
  vorhält, getrennt nach Beamt*innen (Teil A) und Tarifbeschäftigten
  (Teil B) — und wie viele davon am Stichtag **nicht besetzt** waren.

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
    python scripts/ingest_finanzberichte.py --nur ergebnishaushalt
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
    ap.add_argument("--nur", choices=["jahresabschluss", "teilhaushalte",
                                      "ergebnishaushalt", "stellenplan",
                                      "investitionsprogramm"],
                    default=None)
    ap.add_argument("--db", default=str(COUNCIL_DB))
    ap.add_argument("--auch-schrumpfen", action="store_true",
                    help="einen Jahrgang auch dann ersetzen, wenn er dabei deutlich "
                         "kleiner wird — für den Fall, dass genau das die Absicht ist "
                         "(ein früherer Lauf war zu großzügig). Ein LEERES Ergebnis "
                         "ersetzt trotzdem nichts.")
    args = ap.parse_args()

    store = CouncilStore(Path(args.db))
    p = finanzquellen.Protokoll()
    schuetzen = not args.auch_schrumpfen
    ergebnis: dict = {}

    def uebernehmen(name: str, teil: dict) -> None:
        for schluessel, wert in teil.items():
            ergebnis[f"{name}_{schluessel}" if schluessel in _EIGEN else schluessel] = wert

    try:
        if args.nur in (None, "jahresabschluss"):
            print("Jahresabschlüsse (Ergebnisrechnung):")
            uebernehmen("jahresabschluss",
                        finanzquellen.lies_jahresabschluesse(store, p, schuetzen=schuetzen))
            print("Schlussberichte des Rechnungsprüfungsamts:")
            uebernehmen("rpa", finanzquellen.lies_schlussbericht_fundstellen(store, p))
        if args.nur in (None, "teilhaushalte"):
            print("Teilhaushalte (Produktebene):")
            uebernehmen("teilhaushalt",
                        finanzquellen.lies_teilhaushalte(store, p, schuetzen=schuetzen))
        if args.nur in (None, "ergebnishaushalt"):
            print("Gesamtergebnishaushalt (Planjahre):")
            uebernehmen("ergebnishaushalt",
                        finanzquellen.lies_ergebnishaushalte(store, p, schuetzen=schuetzen))
        if args.nur in (None, "stellenplan"):
            print("Stellenplan (Stellen und Besetzung):")
            uebernehmen("stellenplan",
                        finanzquellen.lies_stellenplaene(store, p, schuetzen=schuetzen))
        if args.nur in (None, "investitionsprogramm"):
            print("Investitionsprogramm (einzelne Vorhaben):")
            uebernehmen("investitionsprogramm",
                        finanzquellen.lies_investitionsprogramme(
                            store, p, schuetzen=schuetzen))
        # Zeilen, die nicht sagen, woher sie kommen. Leer ist der Sollzustand;
        # steht hier etwas, hat eine Zieltabelle ihre `herkunft_id` nicht
        # gefüllt (siehe council/herkunft.py).
        ergebnis["herkunft_verwaist"] = store.herkunft_aufraeumen()
        ergebnis["ohne_herkunft"] = store.herkunft_luecken()
    finally:
        store.close()
    print(f"Fertig: {ergebnis}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
