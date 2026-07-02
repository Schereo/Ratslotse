#!/usr/bin/env python3
"""Generate a plain-language recap per policy field ("Was bewegte den Rat im Bereich X?").

For each policy field, takes its most recent decisions and asks the LLM for a compact
3–5 sentence prose recap, stored in ``council_field_recaps``. The web Trends page shows
them. Skips fields with too few decisions, and fields whose recap is still fresh — so the
weekly enrich cron effectively regenerates each field roughly monthly. ``--force`` ignores
freshness and regenerates everything.

    python scripts/generate_field_recaps.py            # only stale/missing fields
    python scripts/generate_field_recaps.py --force    # regenerate all
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import recaps  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from council.topics import POLICY_FIELDS  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"


def _is_fresh(generated_at: str, max_age_days: int) -> bool:
    try:
        ts = datetime.fromisoformat(generated_at)
    except (ValueError, TypeError):
        return False
    return datetime.utcnow() - ts < timedelta(days=max_age_days)


def process(min_decisions: int = 3, per_field: int = 20, max_age_days: int = 25,
            force: bool = False) -> dict:
    store = CouncilStore(COUNCIL_DB)
    try:
        existing = store.field_recaps_by_key()
        now = datetime.utcnow().isoformat(timespec="seconds")
        generated, skipped = 0, 0
        for key, (label, _desc) in POLICY_FIELDS.items():
            if not force and key in existing and _is_fresh(existing[key]["generated_at"], max_age_days):
                skipped += 1
                continue
            decisions = store.search_decisions(field=key, sort="date_desc", limit=per_field)
            if len(decisions) < min_decisions:
                skipped += 1
                continue
            try:
                summary = recaps.generate_recap(label, decisions)
            except Exception as exc:  # noqa: BLE001 — one field failing must not abort the rest
                print(f"!! {key}: {exc!r}", flush=True)
                skipped += 1
                continue
            dates = sorted(d.get("session_date") or "" for d in decisions if d.get("session_date"))
            store.save_field_recap(key, summary, len(decisions),
                                   dates[0] if dates else "", dates[-1] if dates else "", now)
            generated += 1
            print(f"  ✓ {key} ({len(decisions)} Beschlüsse)", flush=True)
        return {"generated": generated, "skipped": skipped}
    finally:
        store.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-decisions", type=int, default=3)
    ap.add_argument("--per-field", type=int, default=20)
    ap.add_argument("--max-age-days", type=int, default=25)
    ap.add_argument("--force", action="store_true", help="regenerate all fields, ignore freshness")
    args = ap.parse_args()
    st = process(args.min_decisions, args.per_field, args.max_age_days, args.force)
    print(f"=== done: {st['generated']} recaps generated, {st['skipped']} skipped ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
