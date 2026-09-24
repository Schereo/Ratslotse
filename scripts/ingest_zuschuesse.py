#!/usr/bin/env python3
"""Die Zuschüsse an Dritte einlesen (Übersichten, Anlage 003 des Haushaltsplans).

Parser und Probe: ``council/uebersichten.py``. Der Lauf lädt die PDFs selbst —
die Tabelle steht quer und braucht Wortkoordinaten, die der gespeicherte
Textauszug nicht hergibt. Acht Pläne à gut 40 Seiten, höflich nacheinander.

    python scripts/ingest_zuschuesse.py
    python scripts/ingest_zuschuesse.py --trocken
    python scripts/ingest_zuschuesse.py --auch-schrumpfen
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

from council import finanzquellen, herkunft, uebersichten  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")

#: Das Sammel-PDF „2-5 Vorbericht, Übersichten, …" hat 280 Seiten und trägt
#: dieselbe Tabelle wie die eigene Anlage desselben Jahres — nicht laden.
MAX_SEITEN = 80


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
    quelle = finanzquellen.QUELLEN["grants"]
    rows = [r for r in quelle.dokumente(store, "document_id, label, url, n_pages")
            if (r.get("n_pages") or 0) <= MAX_SEITEN]
    print(f"{len(rows)} Anlage(n) als Übersichten erkannt.", flush=True)

    gelesen: dict[int, int] = {}
    verworfen = 0
    for i, r in enumerate(rows):
        # Ein Jahrgang, den schon ein früheres Dokument geliefert hat, braucht
        # seine Dubletten nicht — nur wenn das Label das Jahr verrät, lässt
        # sich der Abruf sparen.
        jahr_label = next(iter(finanzquellen._einheiten_uebersichten(r)), (None,))[0]  # noqa: SLF001
        if jahr_label in gelesen:
            continue
        if i:
            time.sleep(args.pause)
        try:
            erg = uebersichten.lies(uebersichten.woerter_aus_pdf(_laden(r["url"])))
        except Exception as exc:  # noqa: BLE001 — ein Dokument stoppt nicht den Lauf
            p.warnen(f"  {r['document_id']}: nicht ladbar ({exc})")
            verworfen += 1
            continue
        jahr = erg.budget_year
        if jahr is None or not erg.zeilen:
            p.sagen(f"  {r['document_id']} ({r['label']!r}): keine Zuschuss-Übersicht")
            continue
        if jahr in gelesen:
            p.sagen(f"  {jahr}: zweites Dokument ({r['document_id']}) — übersprungen")
            continue
        if not erg.bestanden:
            p.warnen(f"  {r['document_id']} ({jahr}): {'; '.join(erg.hinweise)} — nicht gespeichert")
            verworfen += 1
            continue
        summe = sum(z.amount or 0 for z in erg.zeilen)
        p.sagen(f"  {jahr}: {len(erg.zeilen)} Zuschüsse, {summe / 1e6:.1f} Mio. € · "
                f"{len(erg.summen)} Teilhaushalts-Summen aufgegangen · Dokument {r['document_id']}"
                + (f" · auffällig: {'; '.join(erg.auffaellig)}" if erg.auffaellig else ""))
        gelesen[jahr] = len(erg.zeilen)
        if args.trocken:
            continue
        alt = len(store.get_zuschuesse(jahr))
        if alt and not finanzquellen.bestandsschutz(
                p, f"{jahr} Zuschüsse", alt, len(erg.zeilen), not args.auch_schrumpfen):
            continue
        nachweis = (f"{len(erg.summen)} von {len(erg.summen)} Teilhaushalts-Summen aufgegangen"
                    + (f"; an der Vorlage auffällig: {'; '.join(erg.auffaellig)}"
                       if erg.auffaellig else ""))
        store.save_zuschuesse(jahr, [asdict(z) for z in erg.zeilen], herkunft.Herkunft(
            kind="ris", probe=[uebersichten.PROBE_ZUSCHUESSE],
            document_id=r["document_id"], label=r["label"], url=r["url"],
            citation="Übersicht über die Zuweisungen und Zuschüsse an Dritte",
            probe_result=nachweis,
            as_of=f"Haushaltsplan {jahr}, Anlage 003 — Stand der Einbringung"))

    if not args.trocken:
        store.herkunft_aufraeumen()
    store.close()
    print(f"\n{len(gelesen)} Plan-Jahrgänge gelesen ({', '.join(map(str, sorted(gelesen)))}), "
          f"{verworfen} verworfen{' — Trockenlauf, nichts gespeichert' if args.trocken else ''}.",
          flush=True)
    return 1 if verworfen and not gelesen else 0


if __name__ == "__main__":
    raise SystemExit(main())
