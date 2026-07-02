#!/usr/bin/env python3
"""Purge scraped NWZ article data from the databases.

Run this ON THE SERVER **after** the NWZ-removal deploy is live, so the app no
longer reads these tables while they empty. It removes the actual scraped
content (the legal liability) but keeps the (now-empty) table shells and the
web-account/council data intact — no schema migration, no downtime.

What it does NOT touch: web_users, topics, committee_subscriptions, push_tokens,
council.* — all of that stays.

Usage:
    # ALWAYS back up first (the daily backup script does this too):
    .venv/bin/python scripts/backup_db.py
    # Dry run (default) — shows row counts, changes nothing:
    .venv/bin/python scripts/purge_nwz_data.py
    # Actually delete:
    .venv/bin/python scripts/purge_nwz_data.py --yes
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# Tables emptied in nwz.sqlite — scraped articles, editions, the FTS index and
# the NWZ article↔topic matches / classification bookkeeping.
NWZ_TABLES = [
    "articles",
    "articles_fts",
    "editions",
    "article_topic_matches",
    "topic_classified_editions",
]
# In council.sqlite: the pre-matched decision↔article press links carry scraped
# article titles, so empty them too. The "In der Presse" UI now uses a plain
# NWZonline search link instead.
COUNCIL_TABLES = ["council_news_links"]


def _count(con: sqlite3.Connection, table: str) -> int | None:
    try:
        return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except sqlite3.OperationalError:
        return None  # table doesn't exist (fine — nothing to purge)


def _purge_db(path: Path, tables: list[str], do_it: bool) -> None:
    if not path.exists():
        print(f"  {path.name}: nicht gefunden — übersprungen")
        return
    con = sqlite3.connect(path)
    try:
        for t in tables:
            n = _count(con, t)
            if n is None:
                print(f"  {path.name}.{t}: existiert nicht")
                continue
            if do_it:
                con.execute(f"DELETE FROM {t}")
                print(f"  {path.name}.{t}: {n} Zeilen gelöscht")
            else:
                print(f"  {path.name}.{t}: {n} Zeilen (würde gelöscht)")
        # Prompt-Overrides für entfernte NWZ-Prompts mitnehmen (falls vorhanden).
        try:
            like = con.execute(
                "SELECT COUNT(*) FROM prompts WHERE key LIKE 'nwz\\_%' ESCAPE '\\' "
                "OR key LIKE 'weekly_highlights%'"
            ).fetchone()[0]
            if do_it and like:
                con.execute(
                    "DELETE FROM prompts WHERE key LIKE 'nwz\\_%' ESCAPE '\\' "
                    "OR key LIKE 'weekly_highlights%'"
                )
            print(f"  {path.name}.prompts: {like} NWZ-Overrides "
                  f"{'gelöscht' if do_it else 'würden gelöscht'}")
        except sqlite3.OperationalError:
            pass
        if do_it:
            con.commit()
            con.execute("VACUUM")
            print(f"  {path.name}: committed + VACUUM")
    finally:
        con.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Purge scraped NWZ data")
    ap.add_argument("--yes", action="store_true", help="tatsächlich löschen (sonst Dry-Run)")
    args = ap.parse_args()

    nwz_db = Path(os.environ.get("NWZ_DB", DATA / "nwz.sqlite"))
    council_db = Path(os.environ.get("COUNCIL_DB", DATA / "council.sqlite"))

    mode = "LÖSCHEN" if args.yes else "DRY-RUN (nichts wird verändert)"
    print(f"NWZ-Datenpurge — {mode}\n")
    if args.yes:
        print("⚠ Stelle sicher, dass vorher ein Backup lief (scripts/backup_db.py)\n")
    _purge_db(nwz_db, NWZ_TABLES, args.yes)
    _purge_db(council_db, COUNCIL_TABLES, args.yes)
    if not args.yes:
        print("\nZum Ausführen erneut mit --yes starten.")


if __name__ == "__main__":
    sys.exit(main())
