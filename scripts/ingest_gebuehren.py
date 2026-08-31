#!/usr/bin/env python3
"""Die Gebührenbedarfsberechnungen einlesen — Abfall und Straßenreinigung.

Liest die Anlagen, deren Label „Gebührenbedarf" enthält
(`council/gebuehren.py`), und speichert je Bereich und Jahrgang eine Zeile.
Jeder Block prüft sich zweimal selbst: die Kaskade (Kalkulation minus alle
Abzüge = zu deckende Kosten) und die Division (Kosten ÷ Bezugsmenge =
gedruckte Gebühr). Was nicht aufgeht, wird nicht gespeichert.

    python scripts/ingest_gebuehren.py --trockenlauf
    python scripts/ingest_gebuehren.py

Der Jahrgang 2020 liegt nur als Scan vor; ihn macht
`scripts/backfill_anlagen_ocr.py` lesbar, dieser Lauf findet ihn danach von
allein.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council.gebuehren import (  # noqa: E402
    GebuehrenFehler,
    herkunft_fuer,
    herkunft_fuer_satz,
    lies,
    lies_gebuehrensaetze,
)
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def main() -> dict:
    ap = argparse.ArgumentParser(description="Gebührenbedarfsberechnungen einlesen")
    ap.add_argument("--trockenlauf", action="store_true")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()

    store = CouncilStore(Path(args.db))
    try:
        rows = [dict(r) for r in store._conn.execute(  # noqa: SLF001
            "SELECT a.document_id, a.label, a.url, a.raw_text, a.status, "
            "       v.template_number "
            "FROM council_anlagen a LEFT JOIN council_vorlagen v ON v.kvonr = a.kvonr "
            "WHERE a.label LIKE '%Gebührenbedarf%' ORDER BY a.document_id")]
        print(f"{len(rows)} Anlage(n) mit „Gebührenbedarf“ im Label.", flush=True)

        gelesen, saetze_gelesen, risse, ohne_text = [], [], [], []
        for r in rows:
            if not (r["raw_text"] or "").strip():
                ohne_text.append((r["document_id"], r["label"], r["status"]))
                continue
            bereiche, fehler = lies(r["raw_text"], r["template_number"])
            gelesen.extend((b, r) for b in bereiche)
            risse.extend(f"{r['document_id']}: {f}" for f in fehler)
            try:
                saetze = lies_gebuehrensaetze(r["raw_text"], r["template_number"])
            except GebuehrenFehler as fehler:
                risse.append(f"{r['document_id']}, Anlage 4: {fehler}")
            else:
                if saetze:
                    saetze_gelesen.append((saetze, r))

        if gelesen:
            print("\nGelesen:", flush=True)
            for b, _ in sorted(gelesen, key=lambda x: (x[0].year, x[0].area)):
                division = (f"÷ {b.reference_quantity:>9,.0f} {b.reference_unit:18} "
                            f"= {b.gebuehr:>8.3f} €"
                            if b.gebuehr is not None
                            else "(Grundgebühr und Gebühr je Liter, keine Division)")
                print(f"  {b.year}  {b.area_name[:24]:26} "
                      f"{b.costs_to_cover:>12,.0f} €  {division}", flush=True)

        if ohne_text:
            print("\nOhne Volltext — nichts zu lesen:", flush=True)
            for did, label, status in ohne_text:
                note = (" (Scan — backfill_anlagen_ocr.py macht ihn readable)"
                           if status == "empty" else "")
                print(f"  {did}  {label[:50]:52} {status}{note}", flush=True)

        if saetze_gelesen:
            print("\nKonkrete Tarife aus Anlage 4:", flush=True)
            for saetze, _ in sorted(saetze_gelesen, key=lambda x: x[0][0].year):
                beispiele = ", ".join(
                    f"{s.label}: {s.amount:.2f} €"
                    for s in saetze if s.schluessel in
                    ("grundgebuehr", "litergebuehr", "strassenreinigung_qw"))
                print(f"  {saetze[0].year}: {len(saetze)} Tarife — {beispiele}",
                      flush=True)

        if risse:
            print("\nProbe gerissen — NICHT gespeichert:", flush=True)
            for satz in risse:
                print(f"  {satz}", flush=True)

        if args.trockenlauf:
            print("\n— Trockenlauf, nichts gespeichert.", flush=True)
            return {"gelesen": len(gelesen),
                    "gebuehrensaetze": sum(len(s) for s, _ in saetze_gelesen),
                    "risse": len(risse),
                    "ohne_text": len(ohne_text), "trocken": 1}

        for b, r in gelesen:
            store.save_gebuehrenbedarf(b, herkunft_fuer(
                b, url=r["url"], document_id=r["document_id"], label=r["label"]))
        for saetze, r in saetze_gelesen:
            store.save_gebuehrensaetze(saetze, [herkunft_fuer_satz(
                s, url=r["url"], document_id=r["document_id"], label=r["label"])
                for s in saetze])
        print(f"\n{len(gelesen)} Gebührenbereich(e) gespeichert über "
              f"{len({b.year for b, _ in gelesen})} Jahrgänge; "
              f"{sum(len(s) for s, _ in saetze_gelesen)} konkrete Tarife.", flush=True)
        return {"gelesen": len(gelesen), "risse": len(risse),
                "gebuehrensaetze": sum(len(s) for s, _ in saetze_gelesen),
                "ohne_text": len(ohne_text), "befund": risse}
    finally:
        store.close()


if __name__ == "__main__":
    from kern.alerts import run_guarded

    run_guarded("ingest_gebuehren", main)
