#!/usr/bin/env python3
"""Den Vorbericht des Haushaltsplans einlesen (Anlage 001): der Wortlaut je
Teilhaushalt, zum Ergebnishaushalt und zu den Investitionen.

Parser und Probe: ``council/vorbericht.py``. Der Lauf lädt die PDFs selbst —
die Absätze kommen aus den Textblöcken, die der gespeicherte Textauszug nicht
hergibt. Acht Pläne à 80–100 Seiten, höflich nacheinander.

    python scripts/ingest_vorbericht.py
    python scripts/ingest_vorbericht.py --trocken
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.request
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import finanzquellen, herkunft, vorbericht  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")
#: Das Sammel-PDF „2-5 Vorbericht, Übersichten, …" (280 Seiten) nicht laden.
MAX_SEITEN = 150


def _laden(url: str) -> bytes:
    anfrage = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(anfrage, timeout=120) as antwort:
        return antwort.read()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--trocken", action="store_true", help="nur lesen und prüfen")
    ap.add_argument("--pause", type=float, default=1.5)
    args = ap.parse_args()

    store = CouncilStore(args.db)
    p = finanzquellen.Protokoll()
    rows = [r for r in finanzquellen.QUELLEN["budget_notes"].dokumente(
        store, "document_id, label, url, n_pages") if (r.get("n_pages") or 0) <= MAX_SEITEN]
    print(f"{len(rows)} Anlage(n) als Vorbericht erkannt.", flush=True)
    gelesen: dict[int, int] = {}
    verworfen = 0
    abrufe = 0
    for r in rows:
        jahr_label = next(iter(finanzquellen._einheiten_uebersichten(r)), (None,))[0]  # noqa: SLF001
        if jahr_label in gelesen:
            continue
        if abrufe:
            time.sleep(args.pause)
        abrufe += 1
        try:
            erg = vorbericht.lies(vorbericht.bloecke_aus_pdf(_laden(r["url"])))
        except Exception as exc:  # noqa: BLE001 — ein Dokument stoppt nicht den Lauf
            p.warnen(f"  {r['document_id']}: nicht ladbar ({exc})")
            verworfen += 1
            continue
        jahr = erg.budget_year
        if jahr is None or jahr in gelesen:
            continue
        if not erg.bestanden:
            p.warnen(f"  {r['document_id']} ({jahr}): {'; '.join(erg.hinweise)} — nicht gespeichert")
            verworfen += 1
            continue
        zeichen = sum(len(a.text) for a in erg.abschnitte)
        p.sagen(f"  {jahr}: {len(erg.abschnitte)} Abschnitte, {zeichen:,} Zeichen · Dokument {r['document_id']}")
        gelesen[jahr] = len(erg.abschnitte)
        if args.trocken:
            continue
        store.save_vorbericht(jahr, [asdict(a) for a in erg.abschnitte], herkunft.Herkunft(
            kind="ris", probe=[vorbericht.PROBE_VORBERICHT],
            document_id=r["document_id"], label=r["label"], url=r["url"],
            citation="Vorbericht, Abschnitte 2.4.2 (Teilhaushalte) und 3.2.2 (Investitionen)",
            probe_result=f"{len(erg.im_inhalt)} Abschnitte im Inhaltsverzeichnis, alle im Text",
            as_of=f"Haushaltsplan {jahr}, Anlage 001 — Stand der Einbringung"))
    if not args.trocken:
        store.herkunft_aufraeumen()
    store.close()
    print(f"\n{len(gelesen)} Vorberichte gelesen ({', '.join(map(str, sorted(gelesen)))}), "
          f"{verworfen} verworfen.", flush=True)
    return 1 if verworfen and not gelesen else 0


if __name__ == "__main__":
    raise SystemExit(main())
