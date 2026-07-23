#!/usr/bin/env python3
"""Daily SQLite backup — keeps the last 7 copies of each database, optionally
mirrored off-site per rsync.

Cron (as user tim on app-server):
  0 3 * * * /home/<user>/app/.venv/bin/python /home/<user>/app/scripts/backup_db.py

Off-Site-Mirror (optional, .env):
  BACKUP_RSYNC_TARGET=user@host:pfad/   # z. B. die Edge-VM — bei Serververlust
  BACKUP_RSYNC_SSH_PORT=22              # bleiben die letzten 7 Kopien erhalten
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")  # BACKUP_RSYNC_*, RESEND_API_KEY/ALERT_EMAIL (Alerts)

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


def offsite_sync() -> None:
    """Mirror the backup directory to BACKUP_RSYNC_TARGET (if configured).

    `--delete` hält das Ziel als exakten Spiegel der lokalen 7-Tage-Rotation.
    BatchMode verhindert Passwort-Prompts im Cron; ein Fehler wirft und landet
    damit im run_guarded-Alert."""
    target = os.environ.get("BACKUP_RSYNC_TARGET")
    if not target:
        return
    port = os.environ.get("BACKUP_RSYNC_SSH_PORT", "22")
    subprocess.run(
        [
            "rsync", "-az", "--delete",
            "-e", f"ssh -p {port} -o BatchMode=yes -o ConnectTimeout=15",
            f"{BACKUP_DIR}/", target,
        ],
        check=True,
        timeout=30 * 60,
    )
    print(f"✓  Off-Site-Mirror → {target}")


def main() -> dict:
    """Gibt die Kennzahlen des Laufs für die Cron-Übersicht zurück."""
    gesichert, bytes_total = 0, 0
    for db_name in ["nwz.sqlite", "council.sqlite"]:
        db_path = DATA / db_name
        if db_path.exists():
            backup_db(db_path)
            gesichert += 1
            bytes_total += db_path.stat().st_size
        else:
            print(f"Skipping {db_name} (not found)", file=sys.stderr)
    if not gesichert:
        raise RuntimeError("keine Datenbank gefunden — es wurde nichts gesichert")
    offsite_sync()
    return {
        "Datenbanken gesichert": gesichert,
        "Größe (MB)": round(bytes_total / 1_000_000, 1),
        "Off-Site-Mirror": "ja" if os.environ.get("BACKUP_RSYNC_TARGET") else "nein",
    }


if __name__ == "__main__":
    from nwz.alerts import run_guarded

    run_guarded("backup_db", main)
