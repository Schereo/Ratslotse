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
  Dasselbe Dokument trägt zwei weitere Ebenen, jede mit eigener Probe und
  eigenem Schicksal — reißt eine, fehlt sie allein, und der Rest des
  Jahrgangs steht trotzdem: Abschnitt 4.1 die **Finanzrechnung**
  (``council_finanzrechnung``, was tatsächlich geflossen ist,
  ``finanzberichte.finanzprobe``) und Abschnitt 2.1 die **Bilanz**
  (``council_bilanz``, was am Stichtag da ist und wem es zusteht,
  ``bilanz.bilanzprobe``) samt den Erläuterungen des Anhangs dazu
  (``council_bilanz_erlaeuterungen``, Abschnitt 6.2.1–6.2.9). Über
  Dokumentgrenzen hinweg laufen dabei drei Ketten: Kassen- und
  Bilanz-Vorjahreskette und die Kreuzprobe zwischen beiden Tabellen —
  „Liquide Mittel" der Bilanz ist der „Endbestand an Zahlungsmitteln" der
  Finanzrechnung, gelesen von zwei getrennten Parsern.
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
                         "kleiner wird — für den Fall, dass exact das die Absicht ist "
                         "(ein früherer Lauf war zu großzügig). Ein LEERES Ergebnis "
                         "ersetzt trotzdem nichts.")
    args = ap.parse_args()

    store = CouncilStore(Path(args.db))
    p = finanzquellen.Protokoll()
    schuetzen = not args.auch_schrumpfen
    result: dict = {}

    def uebernehmen(name: str, teil: dict) -> None:
        for schluessel, wert in teil.items():
            result[f"{name}_{schluessel}" if schluessel in _EIGEN else schluessel] = wert

    try:
        if args.nur in (None, "jahresabschluss"):
            print("Jahresabschlüsse (Ergebnisrechnung):")
            uebernehmen("jahresabschluss",
                        finanzquellen.lies_jahresabschluesse(store, p, schuetzen=schuetzen))
            print("Schlussberichte des Rechnungsprüfungsamts:")
            uebernehmen("rpa", finanzquellen.lies_schlussbericht_fundstellen(store, p))
            # Aus denselben Dokumenten, aber an eigener Probe: wofür die Stadt
            # geradesteht (Anhang 6.2.10). Steht nach den beiden oben, weil ein
            # gerissener Bürgschafts-Lauf die Ergebnisrechnung nicht aufhalten
            # darf — es sind verschiedene Abschnitte hinter verschiedenen Proben.
            print("Bürgschaftsbestand (Eventualverbindlichkeiten):")
            uebernehmen("buergschaft", finanzquellen.lies_buergschaften(store, p))
            # Und aus demselben Heft, ganz hinten: was aus Investitionen wird
            # (Abschnitt 8.1). Steht NACH der Bilanz, weil seine vierte Probe
            # den Buchwert gegen die Bilanzposition hält — läuft sie vorher,
            # gibt es die Gegenprobe im ersten Lauf einer leeren Datenbank
            # nicht, und der Beleg trüge eine Probe weniger.
            print("Anlagenspiegel (was aus Investitionen wird):")
            uebernehmen("anlagenspiegel", finanzquellen.lies_anlagenspiegel(store, p))
            # Der Rechenschaftsbericht ist ein ANDERES Dokument als der
            # Jahresabschluss, steht aber in derselben Sitzungsvorlage. Sein
            # Leser kommt zuletzt, weil zwei seiner drei Proben gegen die
            # Bilanz rechnen — die muss vorher stehen.
            print("Kennzahlen des Rechenschaftsberichts:")
            uebernehmen("kennzahlen", finanzquellen.lies_kennzahlen(store, p))
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
        result["herkunft_verwaist"] = store.herkunft_aufraeumen()
        result["ohne_herkunft"] = store.herkunft_luecken()
    finally:
        store.close()
    print(f"Fertig: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
