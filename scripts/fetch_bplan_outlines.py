#!/usr/bin/env python3
"""Bebauungsplan-Umringe der Stadt Oldenburg spiegeln (openGEOdata → council_bplan_outlines).

Ein Aufruf, ~3 MB, kein LLM. Wöchentlich als Schritt in ``weekly_enrich.py``
(vor „Mein Viertel — Vorhaben", weil die Tafel die Flächen beim Lesen an die
Vorhaben hängt); von Hand::

    python scripts/fetch_bplan_outlines.py

Der Bestand wird nur ersetzt, wenn der Dienst einen Vollabzug liefert
(``council/bplan.py::fetch_outlines`` wirft sonst) — ein Netzfehler lässt die
alten Flächen stehen.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import bplan  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def main() -> dict:
    zeilen = bplan.fetch_outlines()
    store = CouncilStore(COUNCIL_DB)
    try:
        n = store.replace_bplan_outlines(zeilen)
        stand = store.bplan_outline_stats()
    finally:
        store.close()
    return {"Bebauungspläne": n, "mit Fläche": stand["mit_flaeche"],
            "rechtskräftig ab 2020": sum(1 for z in zeilen if (z["effective_date"] or "") >= "2020")}


if __name__ == "__main__":
    print(main())
