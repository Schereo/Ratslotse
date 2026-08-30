#!/usr/bin/env python3
"""Kurzfassungen je Tagesordnungspunkt nachgenerieren (Tims Wunsch 12.08.).

Die Sätze entstehen sonst nur im täglichen `check_committees`-Lauf und auch
nur für Sitzungen, zu denen jemand benachrichtigt wird. Dieses Skript füllt
den Bestand: alle KOMMENDEN Sitzungen mit Tagesordnung und die letzten N
vergangenen.

    .venv/bin/python scripts/backfill_top_summaries.py                  # Vorschau
    .venv/bin/python scripts/backfill_top_summaries.py --schreiben
    .venv/bin/python scripts/backfill_top_summaries.py --schreiben --vergangene 10

Ohne `--schreiben` wird nichts gespeichert (nur gezählt und angezeigt).
Sitzungen, die schon Kurzfassungen haben, werden übersprungen — mit
`--neu` auch die.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from council.committee_summary import summarize_agenda_items
from council.scraper import AgendaItem
from council.store import CouncilStore

COUNCIL_DB = ROOT / "data" / "council.sqlite"


def main() -> dict:
    p = argparse.ArgumentParser(description="TOP-Kurzfassungen nachgenerieren")
    p.add_argument("--schreiben", action="store_true", help="Ergebnisse wirklich speichern")
    p.add_argument("--vergangene", type=int, default=10, help="wie viele vergangene Sitzungen (0 = keine)")
    p.add_argument("--neu", action="store_true", help="auch Sitzungen mit vorhandenen Kurzfassungen")
    args = p.parse_args()

    store = CouncilStore(COUNCIL_DB)
    heute = date.today().isoformat()
    try:
        kommend = [dict(r) for r in store._conn.execute(
            "SELECT ksinr, committee, session_date FROM council_sessions "
            "WHERE session_date >= ? ORDER BY session_date", (heute,))]
        vergangen = [dict(r) for r in store._conn.execute(
            "SELECT ksinr, committee, session_date FROM council_sessions "
            "WHERE session_date < ? ORDER BY session_date DESC LIMIT ?",
            (heute, max(0, args.vergangene)))] if args.vergangene > 0 else []
        sitzungen = kommend + vergangen
        print(f"{len(kommend)} kommende + {len(vergangen)} vergangene Sitzungen"
              f"{'' if args.schreiben else ' (Vorschau — nichts wird gespeichert)'}")

        erledigt = fehlend = uebersprungen = 0
        for s in sitzungen:
            ksinr = s["ksinr"]
            items = store.agenda_items(ksinr)
            if not items:
                continue
            if not args.neu and any(i.get("summary") for i in items):
                uebersprungen += 1
                continue
            agenda = [AgendaItem(item_number=i["item_number"], title=i["title"],
                                 template_number=i.get("template_number") or "",
                                 is_public=bool(i.get("is_public", 1)))
                      for i in items]
            try:
                punkte = summarize_agenda_items(committee=s["committee"],
                                                session_date=s["session_date"],
                                                agenda_items=agenda)
            except Exception as exc:  # noqa: BLE001 — eine Sitzung darf den Lauf nicht kippen
                print(f"  ⚠️ {s['session_date']} {s['committee']}: {exc!r}")
                fehlend += 1
                continue
            if punkte is None:
                print(f"  ⚠️ {s['session_date']} {s['committee']}: unbrauchbare Antwort")
                fehlend += 1
                continue
            print(f"  {s['session_date']} {s['committee']}: {len(punkte)} von {len(items)} TOPs")
            if args.schreiben and punkte:
                store.save_item_summaries(ksinr, "backfill", punkte)
            erledigt += 1

        print(f"Fertig: {erledigt} Sitzungen bearbeitet, {uebersprungen} hatten schon "
              f"Kurzfassungen, {fehlend} fehlgeschlagen"
              f"{'' if args.schreiben else ' (Vorschau)'}")
        return {"bearbeitet": erledigt, "uebersprungen": uebersprungen, "fehler": fehlend}
    finally:
        store.close()


if __name__ == "__main__":
    main()
