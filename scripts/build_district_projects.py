#!/usr/bin/env python3
"""„Mein Viertel": das Vorhaben-Register je Ortsbereich neu rechnen.

Zwei LLM-Stufen hinter der Orts-Pipeline (``council/viertel.py``): Richter je
Beschluss (gecacht, nur Neues geht ans Modell) und Bündelung zu Vorhaben (ein
Aufruf je Ortsbereich). Wöchentlich in ``scripts/weekly_enrich.py``; von Hand::

    python scripts/build_district_projects.py                  # alle 31
    python scripts/build_district_projects.py kreyenbrueck osternburg
    python scripts/build_district_projects.py --trocken        # rechnen, nichts schreiben

Erstlauf über die ganze Stadt: rund 700 Beschlüsse in 24 Monaten, also etwa
150 Richter-Aufrufe plus 31 Bündelungen. Danach nur der Zuwachs.
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

from council.store import CouncilStore  # noqa: E402
from council.viertel import build_all  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def main(place_ids: list[str] | None = None, *, trocken: bool = False) -> dict:
    store = CouncilStore(COUNCIL_DB)
    try:
        stats = build_all(store, place_ids or None, dry_run=trocken)
    finally:
        store.close()
    return {
        "Ortsbereiche": len(stats),
        "Kandidaten": sum(s["candidates"] for s in stats),
        "im Viertel": sum(s["hits"] for s in stats),
        "Vorhaben": sum(s["projects"] for s in stats),
        "auf der Tafel": sum(s["visible"] for s in stats),
        "übersprungen": sum(1 for s in stats if s.get("failed")),
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("place_ids", nargs="*", help="Ortsbereich-IDs (Vorgabe: alle)")
    p.add_argument("--trocken", action="store_true", help="rechnen, aber nichts schreiben")
    a = p.parse_args()
    print(main(a.place_ids, trocken=a.trocken))
