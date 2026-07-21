#!/usr/bin/env python3
"""„Lotti erklärt's einfach" (RL-904): Kurzfassungen für Beschlusstexte nachziehen.

Holt Beschlüsse ohne ``simple_summary`` (kind='decision', Beschlusstext
≥ 200 Zeichen, neueste zuerst), erzeugt je Beschluss eine 2–3-Satz-Erklärung
per LLM (Thread-Pool) und schreibt sie im Main-Thread zurück (SQLite mag
keine geteilten Verbindungen). Idempotent — ein Re-Run ergänzt nur fehlende.

Usage::

    python scripts/generate_simple_summaries.py               # bis zu 500
    python scripts/generate_simple_summaries.py --limit 20    # smoke test
    python scripts/generate_simple_summaries.py --workers 8 --limit 2000
"""
from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import simple_summary  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"
# Wochen-Budget des Enrich-Laufs: der Bestand (seit 2018) füllt sich über
# mehrere Wochen von neu nach alt auf, statt einen Riesen-Lauf zu riskieren.
DEFAULT_LIMIT = 500


def process(db_path, limit: int | None = DEFAULT_LIMIT, workers: int = 4) -> dict:
    store = CouncilStore(db_path)
    pending = store.decisions_needing_simple_summary(limit=limit)
    print(f"{len(pending)} Beschlüsse ohne Kurzfassung (Limit {limit}).")

    written = failed = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(simple_summary.generate_one, d): d for d in pending}
        for fut in as_completed(futures):
            d = futures[fut]
            text = fut.result()
            if text:
                store.save_simple_summary(d["id"], text)
                written += 1
            else:
                failed += 1
            if (written + failed) % 25 == 0:
                print(f"  {written + failed}/{len(pending)} …", flush=True)

    store.close()
    print(f"Fertig — {written} gespeichert, {failed} ohne Ergebnis.")
    return {"pending": len(pending), "written": written, "failed": failed}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                    help=f"max. Beschlüsse pro Lauf (Default {DEFAULT_LIMIT}; 0 = alle)")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    process(COUNCIL_DB, limit=(args.limit or None), workers=args.workers)


if __name__ == "__main__":
    main()
