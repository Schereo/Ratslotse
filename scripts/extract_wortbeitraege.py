#!/usr/bin/env python3
"""Wortbeiträge aus gespeicherten Sitzungsprotokollen extrahieren (Task 16).

Ein LLM-Pass je Protokoll über den vorhandenen ``raw_text`` (kein Re-Download):
Redebeiträge, „Anfragen und Anregungen" samt Verwaltungsantwort, Einwohner-
fragen und Zusagen landen in ``council_wortbeitraege`` (+ FTS + Embeddings)
und speisen den „Aus den Ratsdebatten"-Block der KI-Frage.

Idempotent: Nur Protokolle ohne vorhandene Beiträge werden angefasst; ein
Wiederholungslauf nach Abbruch macht genau da weiter. Erstlauf über den
Bestand (~800 Protokolle, grob $6–8)::

    python scripts/extract_wortbeitraege.py            # alles Fehlende
    python scripts/extract_wortbeitraege.py --limit 5  # Stichprobe
"""
from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council.store import CouncilStore  # noqa: E402
from council.wortbeitraege import extract_wortbeitraege  # noqa: E402
from nwz import llm  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def process(db_path: Path, limit: int | None, workers: int) -> dict:
    store = CouncilStore(db_path)
    try:
        todo = store.ksinr_ohne_wortbeitraege(limit or 0)
        ok = fehler = beitraege = 0

        def extrahieren(ksinr: int):
            text = store.protocol_raw_text(ksinr)  # nur Lesen, threadsicher genug
            if not text:
                return ksinr, None
            try:
                return ksinr, extract_wortbeitraege(text)
            except Exception as exc:  # noqa: BLE001 — ein kaputtes Protokoll stoppt nicht den Lauf
                print(f"  ksinr {ksinr}: FEHLER {exc}", flush=True)
                return ksinr, None

        # LLM-Calls in Workern, DB-Schreiben im Main-Thread (SQLite-Konvention).
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for ksinr, rows in pool.map(extrahieren, todo):
                if rows is None:
                    fehler += 1
                    continue
                n = store.save_wortbeitraege(ksinr, rows)
                ok += 1
                beitraege += n
                if ok % 25 == 0:
                    print(f"  {ok}/{len(todo)} Protokolle, {beitraege} Beiträge, "
                          f"~${llm.session_cost()['usd']:.2f}", flush=True)

        try:  # Embeddings direkt mitschreiben (fastembed nötig — best-effort)
            from council import embeddings as emb
            n_vec = emb.embed_wortbeitraege_missing(store)
        except Exception as exc:  # noqa: BLE001
            print(f"  Embeddings übersprungen: {exc}", flush=True)
            n_vec = 0
        return {"protokolle": ok, "fehler": fehler, "beitraege": beitraege,
                "embeddings": n_vec, "kosten_usd": round(llm.session_cost()["usd"], 2)}
    finally:
        store.close()


def main() -> dict:
    ap = argparse.ArgumentParser(description="Wortbeiträge aus Protokollen extrahieren (LLM)")
    ap.add_argument("--limit", type=int, default=None, help="max. Protokolle in diesem Lauf")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()

    stats = process(Path(args.db), args.limit, args.workers)
    print(f"Wortbeiträge: {stats['beitraege']} aus {stats['protokolle']} Protokollen "
          f"({stats['fehler']} Fehler, {stats['embeddings']} Vektoren, "
          f"~${stats['kosten_usd']})", flush=True)
    return stats


if __name__ == "__main__":
    from nwz.alerts import run_guarded

    run_guarded("extract_wortbeitraege", main)
