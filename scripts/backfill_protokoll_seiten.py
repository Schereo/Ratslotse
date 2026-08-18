#!/usr/bin/env python3
"""Seiten-Offsets für den Protokoll-Bestand nachrüsten (Tims Wunsch 18.08.).

Der gespeicherte ``raw_text`` kennt keine Seitengrenzen (die Seiten wurden
mit ``"\\n"`` verklebt) — für seitengenaue Protokoll-Links braucht es je
Protokoll einen Re-Download: Seiten frisch extrahieren, ``raw_text`` +
``page_offsets`` GEMEINSAM ersetzen (die Offsets gelten nur für exakt diesen
Text), dann die Fundstellen-Seiten der Wortbeiträge auflösen.

Kein LLM, nur Downloads + CPU. Idempotent: erledigte Protokolle (Offsets
vorhanden) werden nicht mehr angefasst; ein Abbruch macht beim nächsten Lauf
genau da weiter. Einmalig über den Bestand::

    python scripts/backfill_protokoll_seiten.py             # alles Fehlende
    python scripts/backfill_protokoll_seiten.py --limit 5   # Stichprobe
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import protocols  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from council.wortbeitraege import seiten_aufloesen  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")

#: Pause zwischen den Downloads — das RIS ist ein Behörden-Server, kein CDN.
PAUSE_S = 0.4


def process(db_path: Path, limit: int | None) -> dict:
    store = CouncilStore(db_path)
    try:
        todo = store.ksinr_mit_beitraegen_ohne_offsets(limit or 0)
        print(f"{len(todo)} Protokoll(e) ohne Seiten-Offsets.", flush=True)
        ok = fehler = seiten = 0
        for i, ksinr in enumerate(todo, 1):
            url = store.protokoll_urls_fuer([ksinr]).get(ksinr)
            if not url:
                fehler += 1
                continue
            try:
                text, n_pages, offsets = protocols.extract_pdf_text(url)
            except Exception as exc:  # noqa: BLE001 — ein totes PDF stoppt nicht den Lauf
                print(f"  ksinr {ksinr}: FEHLER {exc!r}", flush=True)
                fehler += 1
                time.sleep(PAUSE_S)
                continue
            store.replace_protocol_text(ksinr, text, n_pages, offsets)
            n = seiten_aufloesen(store, ksinr)
            seiten += n
            ok += 1
            if i % 25 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)} Protokolle, {seiten} Beiträge mit Seite", flush=True)
            time.sleep(PAUSE_S)
        return {"protokolle": ok, "fehler": fehler, "seiten_gesetzt": seiten}
    finally:
        store.close()


def main() -> dict:
    ap = argparse.ArgumentParser(description="Seiten-Offsets + Fundstellen-Seiten nachrüsten")
    ap.add_argument("--limit", type=int, default=None, help="max. Protokolle in diesem Lauf")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()
    stats = process(Path(args.db), args.limit)
    print(f"Fertig — {stats['protokolle']} Protokolle, {stats['seiten_gesetzt']} Beiträge "
          f"mit Seite, {stats['fehler']} Fehler.", flush=True)
    return stats


if __name__ == "__main__":
    from kern.alerts import run_guarded

    run_guarded("backfill_protokoll_seiten", main)
