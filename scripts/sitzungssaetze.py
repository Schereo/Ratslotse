"""Lottis Satz zur Sitzung für den Bestand nachziehen (``council/session_summary.py``).

Im Alltag entsteht er in ``check_committees`` (Tagesordnung) und
``check_protocols`` (Protokoll). Dieses Skript holt die Sitzungen nach, die
es davor schon gab — ohne ``--schreiben`` nur ein Bericht, wie viele offen
sind. Ein Satz kostet rund 0,0004 $ (gemessen 11.11.2026 an zwölf Sitzungen).

    python scripts/sitzungssaetze.py                       # Bericht
    python scripts/sitzungssaetze.py --schreiben --limit 20
    python scripts/sitzungssaetze.py --schreiben           # ein Jahr, Kostengrenze 1 $
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import session_summary  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def main() -> int:
    ap = argparse.ArgumentParser(description="Lottis Satz zur Sitzung nachziehen")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    ap.add_argument("--seit", default=(date.today() - timedelta(days=365)).isoformat(),
                    help="Sitzungen ab diesem Datum (Vorgabe: ein Jahr zurück)")
    ap.add_argument("--limit", type=int, default=0, help="höchstens so viele Sitzungen")
    ap.add_argument("--max-usd", type=float, default=1.0, help="Kostengrenze für den Lauf (Vorgabe 1 $)")
    ap.add_argument("--schreiben", action="store_true", help="wirklich schreiben (sonst Bericht)")
    a = ap.parse_args()

    store = CouncilStore(a.db)
    ksinrs = store.sessions_for_sentences(a.seit)
    if a.limit:
        ksinrs = ksinrs[:a.limit]
    zahl = session_summary.nachziehen(store, ksinrs, schreiben=a.schreiben, max_usd=a.max_usd)
    print(f"{len(ksinrs)} Sitzungen seit {a.seit}: {zahl}")
    if not a.schreiben:
        print("Bericht — mit --schreiben erzeugen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
