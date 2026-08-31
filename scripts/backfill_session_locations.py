#!/usr/bin/env python3
"""Sitzungsorte für Bestandssitzungen nachtragen.

Bis August 2026 riet der Scraper den Ort aus der Überschrift der Sitzungsseite
— die ihn gar nicht nennt. Ergebnis: In `council_sessions` stand für JEDE
Sitzung ein leerer Ort, und die Tagesordnungs-Mail zeigte eine Ortsmarke ohne
Ort. Der Scraper liest ihn jetzt aus dem Feld „Raum"; dieses Skript holt ihn
für die schon gespeicherten Sitzungen nach.

    .venv/bin/python scripts/backfill_session_locations.py            # Vorschau
    .venv/bin/python scripts/backfill_session_locations.py --schreiben
    .venv/bin/python scripts/backfill_session_locations.py --schreiben --ab 2026-01-01

Ohne `--schreiben` wird nichts geändert (nur berichtet). Nur Sitzungen ohne
Ort werden angefasst; die Tagesordnung bleibt unberührt, es wird ausschließlich
die Ortsspalte gesetzt.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council.scraper import CouncilScraper
from council.store import CouncilStore

COUNCIL_DB = ROOT / "data" / "council.sqlite"


def main() -> dict:
    p = argparse.ArgumentParser(description="Fehlende Sitzungsorte nachtragen")
    p.add_argument("--schreiben", action="store_true", help="Änderungen wirklich speichern")
    p.add_argument("--ab", default="", help="nur Sitzungen ab diesem Datum (JJJJ-MM-TT)")
    p.add_argument("--limit", type=int, default=0, help="höchstens so viele Sitzungen")
    args = p.parse_args()

    store = CouncilStore(COUNCIL_DB)
    scraper = CouncilScraper()
    try:
        sql = ("SELECT ksinr, committee, session_date FROM council_sessions "
               "WHERE COALESCE(location,'') = ''")
        params: list = []
        if args.ab:
            sql += " AND session_date >= ?"
            params.append(args.ab)
        sql += " ORDER BY session_date DESC"
        if args.limit:
            sql += f" LIMIT {int(args.limit)}"
        offen = store._conn.execute(sql, params).fetchall()
        print(f"{len(offen)} Sitzungen ohne Ort"
              f"{'' if args.schreiben else ' (Vorschau — nichts wird geschrieben)'}")

        gefunden = 0
        for ksinr, committee, date in offen:
            sitzung = scraper.fetch_session(ksinr)
            ort = (sitzung.location if sitzung else "").strip()
            if not ort:
                print(f"  {date} {committee}: kein Ort auf der Seite")
                continue
            gefunden += 1
            print(f"  {date} {committee}: {ort}")
            if args.schreiben:
                with store._conn:
                    store._conn.execute(
                        "UPDATE council_sessions SET location = ? WHERE ksinr = ?",
                        (ort, ksinr))
        print(f"Fertig: {gefunden} von {len(offen)} Sitzungen haben jetzt einen Ort"
              f"{'' if args.schreiben else ' (Vorschau)'}")
        return {"geprueft": len(offen), "gefunden": gefunden, "geschrieben": bool(args.schreiben)}
    finally:
        store.close()


if __name__ == "__main__":
    main()
