#!/usr/bin/env python3
"""Daily SQLite backup — keeps the last 7 copies of each database.

Cron (as user tim on app-server):
  0 3 * * * /home/<user>/app/.venv/bin/python /home/<user>/app/scripts/backup_db.py
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BACKUP_DIR = DATA / "backups"
KEEP = 7


def backup_db(src: Path) -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    dst = BACKUP_DIR / f"{src.stem}_{date_str}.sqlite"

    src_conn = sqlite3.connect(src)
    dst_conn = sqlite3.connect(dst)
    with dst_conn:
        src_conn.backup(dst_conn)
    src_conn.close()
    dst_conn.close()

    # Prune old backups
    backups = sorted(BACKUP_DIR.glob(f"{src.stem}_*.sqlite"))
    for old in backups[:-KEEP]:
        old.unlink()

    print(f"✓  {src.name} → {dst.name}")


if __name__ == "__main__":
    for db_name in ["nwz.sqlite", "council.sqlite"]:
        db_path = DATA / db_name
        if db_path.exists():
            backup_db(db_path)
        else:
            print(f"Skipping {db_name} (not found)", file=sys.stderr)
