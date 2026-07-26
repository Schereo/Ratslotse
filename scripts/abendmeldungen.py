#!/usr/bin/env python3
"""Abend-Anlässe aus Design 30a — täglich 18 Uhr.

Ein Skript für beide, weil beide zur selben Zeit laufen und beide standardmäßig
aus sind: eine crontab-Zeile statt zwei.

    0 18 * * * /pfad/.venv/bin/python /pfad/scripts/abendmeldungen.py

* **N5 · Vorabend** — täglich: Was morgen ansteht, für alle mit Themen-Treffer
  oder Gremien-Abo auf die Sitzung.
* **N6 · Wochenüberblick** — nur sonntags: die Beschlüsse der Woche zu den
  eigenen Themen, eine Nachricht für alles.

Beides wird nur **eingereiht**; zugestellt wird am Ende desselben Laufs unter
den Grenzen aus ``nwz/notify.py`` (höchstens zwei am Tag, Nachtruhe ab 21 Uhr).
Um 18 Uhr ist die Nachtruhe noch nicht angebrochen, die Zustellung geht also
direkt raus.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from council.abendmeldungen import vorabend, wochenueberblick  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from nwz import notify  # noqa: E402
from nwz.store import Store  # noqa: E402

import os  # noqa: E402

NWZ_DB = os.environ.get("NWZ_DB") or str(ROOT / "data" / "nwz.sqlite")
COUNCIL_DB = os.environ.get("COUNCIL_DB") or str(ROOT / "data" / "council.sqlite")


def main() -> dict:
    heute = date.today()
    nwz = Store(NWZ_DB)
    council = CouncilStore(COUNCIL_DB)

    n5 = vorabend(council, nwz, heute)
    print(f"N5 Vorabend: {n5} Erinnerung(en) eingereiht.")

    # weekday(): Montag=0 … Sonntag=6
    n6 = 0
    if heute.weekday() == 6:
        n6 = wochenueberblick(council, nwz, heute)
        print(f"N6 Wochenüberblick: {n6} Meldung(en) eingereiht.")
    else:
        print("N6 Wochenüberblick: heute nicht (nur sonntags).")

    council.close()
    zugestellt = notify.zustellen(nwz)
    nwz.close()
    print(f"Zugestellt: {zugestellt}.")
    return {"Vorabend-Erinnerungen": n5, "Wochenüberblicke": n6,
            "Zugestellt": zugestellt}


if __name__ == "__main__":
    from nwz.alerts import run_guarded

    run_guarded("abendmeldungen", main)
