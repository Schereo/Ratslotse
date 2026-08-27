#!/usr/bin/env python3
"""Beschlüsse einmalig und danach inkrementell physischen Orten zuordnen.

Der normale Lauf verarbeitet nur neue oder später um Vorlagentext ergänzte Beschlüsse. Ein
Backfill des gesamten Bestands ist damit derselbe Codepfad::

    .venv/bin/python scripts/extract_decision_locations.py --full

Für einen kostenlosen Regex-/Bestands-Smoke-Test ohne LLM::

    .venv/bin/python scripts/extract_decision_locations.py --no-llm --limit 100
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

from council import locations  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"


def process(council_db: Path, *, full: bool = False, limit: int | None = None,
            use_llm: bool = True, batch_size: int = 12) -> dict:
    store = CouncilStore(council_db)
    place_catalog = store.all_places()
    if full:
        store.reset_decision_location_scans()

    saved_links = assigned = scanned = failed_batches = candidates = 0
    batches = store.decision_location_batches(
        batch_size=batch_size, pending_only=not full, limit=limit)
    for batch_number, batch in enumerate(batches, start=1):
        candidates += len(batch)
        for row in batch:
            row["source_hash"] = locations.source_hash(row)
        ids = [row["id"] for row in batch]
        old_places = store.place_observations_for_decisions(ids)
        llm_places: dict[int, list[dict]] = {}
        llm_ok: set[int] = set(ids) if not use_llm else set()
        if use_llm:
            try:
                llm_places, _usage = locations.extract_batch(batch)
                llm_ok = set(llm_places)
            except Exception as exc:  # noqa: BLE001 — sichere Funde speichern, später erneut versuchen
                failed_batches += 1
                print(f"LLM-Batch fehlgeschlagen ({ids[0]}…): {exc!r}", flush=True)

        for row in batch:
            rid = row["id"]
            explicit_title = locations.extract_explicit_locations(
                row.get("title") or "", source="title", catalog_places=place_catalog)
            explicit_decision = locations.extract_explicit_locations(
                row.get("beschluss") or "", source="beschluss", catalog_places=place_catalog)
            merged = locations.merge_candidates(
                explicit_title, explicit_decision, old_places.get(rid, []), llm_places.get(rid, []))
            # Nur ein vollständiger LLM-Lauf (oder bewusst --no-llm) setzt den
            # Hash. Fehlende Ergebnis-IDs werden beim nächsten Lauf erneut versucht.
            done_hash = row["source_hash"] if rid in llm_ok else None
            saved_links += store.save_decision_locations(rid, merged, done_hash)
            assigned += bool(merged)
            scanned += done_hash is not None

        if batch_number % 10 == 0:
            print(
                f"Fortschritt: candidates={candidates}, scanned={scanned}, "
                f"assigned={assigned}, links={saved_links}, failed_batches={failed_batches}",
                flush=True,
            )

    store.close()
    return {
        "candidates": candidates,
        "scanned": scanned,
        "assigned": assigned,
        "links": saved_links,
        "failed_batches": failed_batches,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--full", action="store_true", help="alle Beschlüsse neu zuordnen")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--batch-size", type=int, default=12)
    ap.add_argument("--no-llm", action="store_true", help="nur Regex + alte Ortsentitäten")
    args = ap.parse_args()
    if not args.no_llm and not os.environ.get("OPENROUTER_API_KEY"):
        ap.error("OPENROUTER_API_KEY fehlt; für einen Smoke-Test --no-llm verwenden")
    stats = process(args.db, full=args.full, limit=args.limit,
                    use_llm=not args.no_llm, batch_size=args.batch_size)
    print("Ortszuordnung: " + ", ".join(f"{key}={value}" for key, value in stats.items()))
    return 1 if stats["failed_batches"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
