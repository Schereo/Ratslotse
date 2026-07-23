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


def main() -> dict:
    """Gibt die Kennzahlen des Laufs zurück — run_guarded legt sie für die
    Cron-Übersicht im Admin-Panel ab."""
    store = Store(DB)
    owner_digests = store.get_all_owner_digests()

    if not owner_digests:
        print("No topics saved for any owner — nothing to do.")
        store.close()
        return {"Konten mit Themen": 0}

    for owner in owner_digests:
        print(f"Owner {owner['owner_id']} ({owner['delivery_channel']}): "
              f"{[t.name for t in owner['topics']]}")

    # Ein Kalender-Durchlauf für alle Nutzer:innen; Klassifikation läuft je
    # Nutzer:in nur bei geänderter Tagesordnung (council_agenda_classified).
    stats: dict = {"Konten mit Themen": len(owner_digests)}
    alerts = run_watcher(COUNCIL_DB, owner_digests, months_ahead=3, nwz_store=store, stats=stats)
    store.close()

    print(f"Done — {len(alerts)} alert(s) sent across all owners.")
    return {**stats, "Benachrichtigungen": len(alerts)}


if __name__ == "__main__":
    from nwz.alerts import run_guarded
    run_guarded("check_council", main)
