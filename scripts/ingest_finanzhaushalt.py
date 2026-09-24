#!/usr/bin/env python3
"""Gesamtfinanzhaushalt (Anlage 006 der Haushaltspläne) einlesen.

Die Zahlungen eines Planjahres — laufend, Investitionen, Finanzierung — samt
Finanzplanung für die drei folgenden Jahre. Parser und Probe:
``council/finance_budget.py``.

Anders als die meisten Haushalts-Schichten lädt dieser Lauf die PDFs selbst:
Die Spalten brauchen Wortkoordinaten, die der gespeicherte Textauszug nicht
hergibt (leere Zellen fehlen dort, und die Planjahr-Spalte wandert ans
Zeilenende). Vier Seiten je Plan, acht Pläne — höflich nacheinander.

    python scripts/ingest_finanzhaushalt.py
    python scripts/ingest_finanzhaushalt.py --trocken
    python scripts/ingest_finanzhaushalt.py --auch-schrumpfen
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import finance_budget, finanzquellen, herkunft  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def _laden(url: str) -> bytes:
    anfrage = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(anfrage, timeout=90) as antwort:
        return antwort.read()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--trocken", action="store_true", help="nur lesen und prüfen")
    ap.add_argument("--auch-schrumpfen", action="store_true",
                    help="einen Plan auch ersetzen, wenn er dabei weniger Zeilen hat")
    ap.add_argument("--pause", type=float, default=1.5,
                    help="Sekunden zwischen zwei Abrufen (Vorgabe 1,5)")
    args = ap.parse_args()

    store = CouncilStore(args.db)
    p = finanzquellen.Protokoll()
    quelle = finanzquellen.QUELLEN["finance_budget"]
    rows = quelle.dokumente(store, "document_id, label, url")
    print(f"{len(rows)} Anlage(n) als Gesamtfinanzhaushalt erkannt.", flush=True)

    gelesen_je_jahr: dict[int, int] = {}
    verworfen = 0
    for i, r in enumerate(rows):
        if i:
            time.sleep(args.pause)
        try:
            seiten = finance_budget.woerter_aus_pdf(_laden(r["url"]))
        except Exception as exc:  # noqa: BLE001 — ein Dokument stoppt nicht den Lauf
            p.warnen(f"  {r['document_id']}: nicht ladbar ({exc})")
            verworfen += 1
            continue
        erg = finance_budget.lies(seiten)
        jahr = erg["budget_year"]
        if not erg["bestanden"]:
            p.warnen(f"  {r['document_id']} ({r['label']!r}): {erg['nachweis']} — nicht gespeichert")
            verworfen += 1
            continue
        if jahr in gelesen_je_jahr:
            p.sagen(f"  {jahr}: zweites Dokument ({r['document_id']}) — übersprungen")
            continue
        ansatz = {z["role"]: z["amount"] for z in erg["zeilen"]
                  if z["kind"] == "budget" and z["role"]}
        p.sagen(f"  {jahr}: Investitionen {ansatz['total_out_capital'] / 1e6:.1f} Mio. € "
                f"Auszahlungen, {ansatz['total_in_capital'] / 1e6:.1f} Mio. € Einzahlungen · "
                f"Finanzmittelveränderung {ansatz['cash_change'] / 1e6:+.1f} Mio. € · "
                f"{erg['nachweis']} · Dokument {r['document_id']}")
        gelesen_je_jahr[jahr] = len(erg["zeilen"])
        if args.trocken:
            continue
        alt = len([1 for z in store.get_finanzhaushalt_investitionen()
                   if z["plan_budget_year"] == jahr])
        neu = len([1 for z in erg["zeilen"] if z["role"] in (
            "total_in_capital", "total_out_capital", "balance_capital")])
        if alt and not finanzquellen.bestandsschutz(
                p, f"{jahr} Finanzhaushalt", alt, neu, not args.auch_schrumpfen):
            continue
        store.save_finanzhaushalt(jahr, erg["zeilen"], herkunft.Herkunft(
            kind="ris", probe=[finance_budget.PROBE],
            document_id=r["document_id"], label=r["label"], url=r["url"],
            citation=f"Gesamtfinanzhaushalt — Spalte „Ansatz {jahr}“ und die drei "
                     f"Finanzplanungsjahre",
            probe_result=erg["nachweis"],
            # Wie Anlage 005: Die Anlage hängt an der Einbringungs-Vorlage.
            as_of=f"Haushaltsplan {jahr}, Anlage 006 — Stand der Einbringung"))

    if not args.trocken:
        store.herkunft_aufraeumen()
    store.close()
    print(f"\n{len(gelesen_je_jahr)} Plan-Jahrgänge gelesen "
          f"({', '.join(map(str, sorted(gelesen_je_jahr)))}), {verworfen} verworfen"
          f"{' — Trockenlauf, nichts gespeichert' if args.trocken else ''}.", flush=True)
    return 1 if verworfen and not gelesen_je_jahr else 0


if __name__ == "__main__":
    raise SystemExit(main())
