#!/usr/bin/env python3
"""Pressemitteilungen der Stadt nachträglich verorten (council/presse_orte.py).

Der Tageslauf (``check_presse.py``) verortet, was neu kommt, und holt je Nacht
bis zu 300 noch nie geprüfte nach. Für den Bestand seit 2024 (rund 3.200
Mitteilungen) ist das ein Einmal-Lauf von wenigen Sekunden — regelbasiert,
kein Modell, kein Netz::

    python scripts/backfill_press_places.py
    python scripts/backfill_press_places.py --neu     # alle noch einmal, z. B. nach neuen Straßen
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

from council import presse_orte  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def main(*, neu: bool = False) -> dict:
    store = CouncilStore(COUNCIL_DB)
    try:
        if neu:
            with store._conn:
                store._conn.execute("DELETE FROM council_press_places")
        gesamt = {"verortet": 0, "ohne Ort": 0}
        while True:
            batch = store.press_without_places(limit=500)
            if not batch:
                break
            stats = presse_orte.verorte(store, batch)
            for k in gesamt:
                gesamt[k] += stats[k]
    finally:
        store.close()
    return gesamt


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--neu", action="store_true", help="alle Mitteilungen noch einmal verorten")
    print(main(neu=p.parse_args().neu))
