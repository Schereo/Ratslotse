#!/usr/bin/env python3
"""Scan upcoming Oldenburg council sessions, classify agendas, send per-user alerts (email/push).
Run periodically via cron: 0 8,14 * * * /path/to/.venv/bin/python /path/to/scripts/check_council.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from nwz.store import Store
from council.watcher import run_watcher

DB = ROOT / "data" / "nwz.sqlite"
COUNCIL_DB = ROOT / "data" / "council.sqlite"


def main() -> None:
    store = Store(DB)
    owner_digests = store.get_all_owner_digests()

    if not owner_digests:
        print("No topics saved for any owner — nothing to do.")
        return

    total_alerts = 0
    for owner in owner_digests:
        topic_dicts = [
            {"id": t.id, "name": t.name, "description": t.description}
            for t in owner["topics"]
        ]
        print(f"Owner {owner['owner_id']} ({owner['delivery_channel']}): checking {len(topic_dicts)} topic(s): "
              f"{[t['name'] for t in topic_dicts]}")
        alerts = run_watcher(COUNCIL_DB, topic_dicts, months_ahead=3, owner=owner)
        total_alerts += len(alerts)

    print(f"Done — {total_alerts} alert(s) sent across all owners.")


if __name__ == "__main__":
    from nwz.alerts import run_guarded
    run_guarded("check_council", main)
