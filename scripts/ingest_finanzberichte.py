#!/usr/bin/env python3
"""Jahresabschlüsse und Teilhaushalts-Pläne aus dem eigenen Bestand einlesen.

Beide Dokumenttypen hängen als Anlagen an Ratsvorlagen und liegen mit
Volltext in ``council_anlagen`` — der Protokoll-Scraper zieht sie ohnehin.
Dieses Skript liest sie aus, ohne etwas herunterzuladen:

- **Jahresabschluss** → ``council_ergebnisrechnung``: Ansatz und Ergebnis je
  Posten, also „geplant gegen tatsächlich", plus die Erträge nach Arten.
- **Teilhaushalts-Pläne (THH)** → ``council_produkte``: was einzelne Aufgaben
  kosten, mit Produktnummer und Amt.

Beide Parser verlangen eine im Dokument selbst dokumentierte Rechenprobe
(siehe ``council/finanzberichte.py``); was sie nicht besteht, wird
übersprungen und am Ende als übersprungen ausgewiesen. Läuft einmal je neuem
Jahrgang, es gibt keinen Cron::

    python scripts/ingest_finanzberichte.py
    python scripts/ingest_finanzberichte.py --nur jahresabschluss
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council import finanzberichte  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def _jahresabschluesse(store: CouncilStore) -> dict:
    """Gesamtdokumente der Jahresabschlüsse — nicht die Rechenschaftsberichte
    und nicht die Prüfberichte, die dieselbe Jahreszahl im Titel tragen."""
    rows = store._conn.execute(
        "SELECT label, url, raw_text FROM council_anlagen "
        "WHERE label LIKE '%Jahresabschluss%' AND n_pages > 100 "
        "  AND label NOT LIKE '%Rechenschaft%' AND label NOT LIKE '%Schlussbericht%' "
        "ORDER BY label").fetchall()
    gelesen = uebersprungen = 0
    for r in rows:
        m = re.search(r"(20\d\d)", r["label"] or "")
        if not m:
            continue
        jahr = int(m.group(1))
        posten = finanzberichte.parse_ergebnisrechnung(r["raw_text"] or "", jahr)
        # Ohne beide Summenzeilen ist der Jahrgang für „Plan gegen Ist" wertlos.
        hat_summen = {p["nr"] for p in posten} >= {12, 20}
        if not hat_summen:
            print(f"  {jahr}: nur {len(posten)} Posten, keine Summenzeilen — übersprungen",
                  file=sys.stderr)
            uebersprungen += 1
            continue
        store.save_ergebnisrechnung(jahr, posten, r["label"], r["url"])
        e = next(p for p in posten if p["nr"] == 12)
        a = next(p for p in posten if p["nr"] == 20)
        print(f"  {jahr}: {len(posten)} Posten · Erträge {e['ansatz']/1e6:.1f} → "
              f"{e['ergebnis']/1e6:.1f} · Aufwendungen {a['ansatz']/1e6:.1f} → {a['ergebnis']/1e6:.1f}")
        gelesen += 1
    return {"jahre": gelesen, "uebersprungen": uebersprungen}


def _teilhaushalte(store: CouncilStore) -> dict:
    rows = store._conn.execute(
        "SELECT label, url, raw_text FROM council_anlagen "
        "WHERE label LIKE '%THH%' AND n_pages > 40 ORDER BY label").fetchall()
    je_jahr: dict[int, int] = {}
    ohne = 0
    for r in rows:
        produkte = finanzberichte.parse_teilergebnishaushalt(r["raw_text"] or "")
        if not produkte:
            ohne += 1
            continue
        for jahr in {p["jahr"] for p in produkte}:
            teil = [p for p in produkte if p["jahr"] == jahr]
            store.save_produkte(jahr, teil, r["label"], r["url"])
            je_jahr[jahr] = je_jahr.get(jahr, 0) + len(teil)
    for jahr in sorted(je_jahr):
        print(f"  {jahr}: {je_jahr[jahr]} Produkt-Zeilen")
    return {"dokumente": len(rows), "ohne_treffer": ohne,
            "produkte": sum(je_jahr.values())}


def main() -> int:
    ap = argparse.ArgumentParser(description="Jahresabschlüsse und Teilhaushalte einlesen")
    ap.add_argument("--nur", choices=["jahresabschluss", "teilhaushalte"], default=None)
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()

    store = CouncilStore(Path(args.db))
    ergebnis: dict = {}
    try:
        if args.nur != "teilhaushalte":
            print("Jahresabschlüsse (Ergebnisrechnung):")
            ergebnis |= _jahresabschluesse(store)
        if args.nur != "jahresabschluss":
            print("Teilhaushalte (Produktebene):")
            ergebnis |= _teilhaushalte(store)
    finally:
        store.close()
    print(f"Fertig: {ergebnis}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
