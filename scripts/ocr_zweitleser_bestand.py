#!/usr/bin/env python3
"""Den OCR-Bestand nachträglich vom Zweitleser prüfen lassen.

Neue Finanz-Scans liest ``backfill_anlagen_ocr.py`` seit 10/2026 mit einem
Zweitleser (``council/ocr.py``, Abschnitt „Zweitleser"). Was vorher gelesen
wurde, hat keinen. Dieses Skript holt das nach — dokumentweise, weil es Geld
kostet (Sonnet 4.6 rund 0,022 $ je Tabellenseite)::

    python scripts/ocr_zweitleser_bestand.py --document-id 193959 --document-id 208461 \\
        --ablage ~/ocr-zweitleser-2026-10-17

Je Seite:

1. Gemini liest die Seite (0,0012 $) — nur um zu wissen, ob sie eine
   vergleichbare Zahlentabelle trägt. Fließtext und Bilanzen mit Aktiva und
   Passiva nebeneinander fallen hier heraus, ohne den teuren Leser.
2. Sonnet liest die Tabellenseiten, und seine Lesung wird gegen den
   GESPEICHERTEN Text gehalten (``ocr.abgleich_gegen_bestand``) — der ist
   es, den die Parser lesen, nicht eine frische Lesung.
3. Das Ergebnis steht in ``council_ocr_checks``; ``check_finanzdaten`` meldet
   strittige Seiten, sobald eine Datenschicht das Dokument liest.

Der Bestandstext wird NICHT verändert. Mit ``--ablage`` liegen alle Lesungen
als Dateien da, damit sich jeder Befund am PDF nachprüfen lässt.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

import io  # noqa: E402

import pypdf  # noqa: E402

from council import ocr  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from scripts.backfill_anlagen_ocr import MAX_SEITEN, _hole  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def pruefe_dokument(daten: bytes, bestand: str, ablage: Path | None, did: int,
                    zweitleser: str = ocr.MODEL_ZWEIT) -> dict:
    """Ein Dokument Seite für Seite gegen seinen gespeicherten Text prüfen."""
    leser = pypdf.PdfReader(io.BytesIO(daten))
    geprueft, strittig, nebeneinander, beispiele = 0, [], 0, {}
    for nr, page in enumerate(leser.pages[:MAX_SEITEN], start=1):
        try:
            bild = ocr.aufrichten(ocr.seite_als_bild(page))
        except ocr.OcrFehler:
            continue
        erst = ocr.lies_seite(bild)
        if ocr.betragszeilen_anzahl(erst) < ocr.ZWEIT_AB_ZEILEN:
            continue
        if ocr.nebeneinander(erst):
            nebeneinander += 1
            continue
        zweit = ocr.lies_seite(bild, model=zweitleser)
        ergebnis = ocr.abgleich_gegen_bestand(zweit, bestand)
        if ergebnis.nicht_vergleichbar:
            nebeneinander += 1
            continue
        geprueft += 1
        if ablage:
            (ablage / f"{did}_{nr:02d}.erst.txt").write_text(erst)
            (ablage / f"{did}_{nr:02d}.zweit.txt").write_text(zweit)
        if ergebnis.strittig:
            strittig.append(nr)
            beispiele[nr] = [[list(k), a, b] for k, a, b in ergebnis.beispiele]
    return {"geprueft": geprueft, "strittig": strittig,
            "nebeneinander": nebeneinander, "beispiele": beispiele}


def main() -> dict:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--document-id", type=int, action="append", required=True)
    ap.add_argument("--ablage", type=Path, help="Lesungen und Befunde hierhin")
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    args = ap.parse_args()
    if args.ablage:
        args.ablage.mkdir(parents=True, exist_ok=True)
    store = CouncilStore(args.db)
    gesamt: dict[int, dict] = {}
    try:
        for did in args.document_id:
            row = store._conn.execute(  # noqa: SLF001
                "SELECT url, raw_text, ocr_model FROM council_attachments "
                "WHERE document_id = ?", (did,)).fetchone()
            if row is None or not row["ocr_model"]:
                print(f"  [{did}] kein OCR-Text im Bestand — übersprungen", flush=True)
                continue
            ergebnis = pruefe_dokument(_hole(row["url"]), row["raw_text"] or "",
                                       args.ablage, did)
            store.save_ocr_check(did, row["ocr_model"], ocr.MODEL_ZWEIT,
                                 ergebnis["geprueft"], ergebnis["strittig"])
            gesamt[did] = ergebnis
            print(f"  [{did}] {ergebnis['geprueft']} Tabellenseiten geprüft, "
                  f"{ergebnis['nebeneinander']} Bilanzen nebeneinander ausgelassen, "
                  f"strittig: {ergebnis['strittig'] or 'keine'}", flush=True)
            for nr, bsp in ergebnis["beispiele"].items():
                print(f"      S. {nr}: {bsp[:2]}", flush=True)
    finally:
        store.close()
    if args.ablage:
        (args.ablage / "befunde.json").write_text(json.dumps(gesamt, ensure_ascii=False, indent=1))
    return {"dokumente": len(gesamt),
            "strittige_seiten": sum(len(e["strittig"]) for e in gesamt.values())}


if __name__ == "__main__":
    print(f"Fertig: {main()}")
