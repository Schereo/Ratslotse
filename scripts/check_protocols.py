#!/usr/bin/env python3
"""Pick up newly published council protocols.

Protocols appear days–weeks after a session. This re-scans the last ~90 days and
parses any session whose public protocol is now available but not yet stored.
Idempotent — already-parsed sessions are skipped.

Run daily via cron, e.g. ``0 9 * * *``.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from scripts.backfill_protocols import process_range  # noqa: E402
from scripts.backfill_anlagen import process_missing as fetch_anlagen_missing  # noqa: E402
from scripts.backfill_anlagen import rescan_recent as rescan_recent_anlagen  # noqa: E402
from scripts.backfill_beratungen import process_missing as fetch_beratungen_missing  # noqa: E402
from scripts.backfill_beratungen import rescan_recent as rescan_beratungen  # noqa: E402
from scripts.backfill_vorlagen import process_missing as fetch_vorlagen  # noqa: E402
from scripts.classify_decisions import process as classify_decisions  # noqa: E402
from scripts.extract_amounts import process as extract_amounts  # noqa: E402
from scripts.track_goals import process as track_goals  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"
LOOKBACK_DAYS = 90


def main() -> None:
    since = (date.today() - timedelta(days=LOOKBACK_DAYS)).isoformat()
    print(f"Checking for new protocols since {since}…")
    stats = process_range(COUNCIL_DB, since=since)
    print(f"Done — {stats['parsed']} newly parsed, {stats['no_protocol']} still without "
          f"protocol, {stats['failed']} failed.")
    # Classify any decisions still without a policy field — including the ones just
    # parsed above. Idempotent, so it doubles as the daily classification catch-up.
    cstats = classify_decisions(COUNCIL_DB)
    print(f"Classified {cstats['classified']} decision(s), {cstats['failed']} failed "
          f"→ ${cstats['cost']:.4f}.")
    # Assess newly classified decisions against the city goals (incremental — only
    # decisions not yet linked to each goal, so this is cheap to run daily).
    gstats = track_goals(COUNCIL_DB, incremental=True)
    print(f"Goal links added: {gstats['links']} → ${gstats['cost']:.4f}.")
    # Extract € amounts from any decisions still missing one (regex, no cost).
    astats = extract_amounts(COUNCIL_DB, only_missing=True)
    print(f"€ amounts: {astats['with_amount']}/{astats['decisions']} newly scanned.")
    # Ingest Vorlagen texts for new agenda items (network + pypdf only, no LLM).
    # Newest first + capped, so a normal day fetches a handful; the historic bulk
    # is scripts/backfill_vorlagen.py without limit. Runs before the FTS rebuild
    # so fresh Sachverhalt wording is searchable the same day.
    vstats = fetch_vorlagen(COUNCIL_DB, limit=300)
    print(f"Vorlagen: {vstats['fetched']} ingested, {vstats['no_pdf']} without PDF/text, "
          f"{vstats['failed']} failed.")
    # Anlagen: catch-up for never-scanned Vorlagen + re-scan of recent agendas —
    # Änderungsanträge landen oft erst Tage nach der Vorlage auf der Seite.
    astats2 = fetch_anlagen_missing(COUNCIL_DB, limit=300)
    rstats = rescan_recent_anlagen(COUNCIL_DB)
    print(f"Anlagen: {astats2['anlagen'] + rstats['anlagen']} neu "
          f"({astats2['antraege'] + rstats['antraege']} Anträge), "
          f"{astats2['failed'] + rstats['failed']} Fehler.")
    # Beratungsfolge: neue Vorlagen nachziehen + bewegliche aktualisieren
    # (nachgetragene Ergebnisse, neu angesetzte künftige Stationen).
    bstats = fetch_beratungen_missing(COUNCIL_DB, limit=300)
    b2stats = rescan_beratungen(COUNCIL_DB)
    print(f"Beratungsfolge: {bstats['stationen'] + b2stats['stationen']} Stationen "
          f"({bstats['geplant'] + b2stats['geplant']} geplant), "
          f"{bstats['failed'] + b2stats['failed']} Fehler.")
    # Keep the full-text index in sync for hybrid retrieval (pure SQLite, instant).
    from council.store import CouncilStore
    _store = CouncilStore(COUNCIL_DB)
    print(f"FTS rebuilt: {_store.rebuild_fts()} decisions indexed.")
    _store.close()


if __name__ == "__main__":
    from nwz.alerts import run_guarded

    run_guarded("check_protocols", main)
