#!/usr/bin/env python3
"""Backfill parsed council protocols (decisions + attendance) over a date range.

Walks the council calendar, and for every past session that has a public protocol
not yet parsed, downloads the PDF, extracts structured data via the LLM and stores
it. Idempotent (skips already-parsed sessions) and tolerant of a single bad
protocol.

The slow part is the per-protocol PDF download + LLM call, so those run in a
thread pool (``--workers``); all DB writes happen on the main thread (SQLite is
not shared across threads).

Usage::

    python scripts/backfill_protocols.py                       # 2023-01 → today
    python scripts/backfill_protocols.py --since 2018-01-01 --workers 12
    python scripts/backfill_protocols.py --force               # re-parse everything
"""
from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import protocols  # noqa: E402
from council.scraper import CouncilScraper  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"
DEFAULT_SINCE = "2023-01-01"
PRICE_IN, PRICE_OUT = 0.435, 0.87  # deepseek-v4-pro $/1M, for the printout


def _months(since: str, until: str):
    y, m = int(since[:4]), int(since[5:7])
    ey, em = int(until[:4]), int(until[5:7])
    while (y, m) <= (ey, em):
        yield y, m
        m += 1
        if m > 12:
            y, m = y + 1, 1


def _process_one(scraper: CouncilScraper, ksinr: int, since: str, until: str, today: str) -> dict:
    """Network + LLM work for one session — runs in a worker thread, no DB access."""
    try:
        doc = protocols.find_protocol(ksinr)
        if not doc:
            return {"status": "no_protocol", "ksinr": ksinr}
        session = scraper.fetch_session(ksinr)
        if not session or session.session_date < since or session.session_date > until \
                or session.session_date > today:
            return {"status": "skip", "ksinr": ksinr}
        text, n_pages = protocols.extract_pdf_text(doc["url"])
        data, usage = protocols.extract_protocol(text)
        return {"status": "ok", "ksinr": ksinr, "session": session, "doc": doc,
                "text": text, "n_pages": n_pages, "data": data, "usage": usage}
    except Exception as exc:  # noqa: BLE001 — surface per-protocol failures, keep going
        return {"status": "failed", "ksinr": ksinr, "doc": locals().get("doc"), "error": repr(exc)}


def process_range(
    council_db: Path,
    since: str,
    until: str | None = None,
    force: bool = False,
    workers: int = 8,
) -> dict:
    until = until or date.today().isoformat()
    today = date.today().isoformat()
    scraper = CouncilScraper(delay=0.0)
    store = CouncilStore(council_db)

    print("Enumerating sessions…", flush=True)
    candidates: list[int] = []
    seen: set[int] = set()
    for y, m in _months(since, until):
        for ksinr in scraper.session_ids_for_month(y, m):
            if ksinr in seen:
                continue
            seen.add(ksinr)
            if not force and store.has_protocol(ksinr):
                continue
            candidates.append(ksinr)
    print(f"{len(candidates)} session(s) to check with up to {workers} workers.", flush=True)

    parsed = no_protocol = failed = 0
    tok_in = tok_out = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_process_one, scraper, k, since, until, today): k for k in candidates}
        for i, fut in enumerate(as_completed(futures), 1):
            r = fut.result()
            st = r["status"]
            if st == "no_protocol" or st == "skip":
                no_protocol += 1
                continue
            if st == "failed":
                if r.get("doc"):
                    store.mark_protocol_failed(r["ksinr"], r["doc"])
                failed += 1
                print(f"  [{i}/{len(candidates)}] {r['ksinr']} FAILED: {r['error']}", flush=True)
                continue
            store.save_session(r["session"])
            data = r["data"]
            store.save_protocol(
                r["ksinr"], r["doc"],
                {"protocol_nr": data.get("protocol_nr"),
                 "session_start": data.get("session_start"),
                 "session_end": data.get("session_end")},
                r["text"], r["n_pages"], protocols.MODEL,
                data.get("decisions", []), data.get("attendance", []),
            )
            tok_in += r["usage"].prompt_tokens
            tok_out += r["usage"].completion_tokens
            parsed += 1
            n_sub = sum(len(d.get("sub_votes") or []) for d in data.get("decisions", []))
            print(f"  [{i}/{len(candidates)}] {r['session'].session_date} "
                  f"{r['session'].committee[:36]} → {len(data.get('decisions', []))} Beschl. "
                  f"(+{n_sub} Teilabst.)", flush=True)

    store.close()
    cost = tok_in / 1e6 * PRICE_IN + tok_out / 1e6 * PRICE_OUT
    return {"parsed": parsed, "no_protocol": no_protocol, "failed": failed,
            "tokens_in": tok_in, "tokens_out": tok_out, "cost": cost}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--since", default=DEFAULT_SINCE)
    ap.add_argument("--until", default=date.today().isoformat())
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    print(f"Backfilling protocols {args.since} … {args.until}")
    stats = process_range(args.db, args.since, args.until, args.force, args.workers)
    print(f"\n=== done: {stats['parsed']} parsed, {stats['no_protocol']} without protocol, "
          f"{stats['failed']} failed ===")
    print(f"Tokens: {stats['tokens_in']:,} in + {stats['tokens_out']:,} out → ${stats['cost']:.4f}")
    return 1 if stats["failed"] and not stats["parsed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
