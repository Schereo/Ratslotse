#!/usr/bin/env python3
"""Sitzungen nachtragen, die der tägliche Kalenderlauf nie gesehen hat.

Der Watcher (``council/watcher.py``) liest den Kalender vom laufenden Monat an
nach vorn und seit 09/2026 drei Monate zurück. Was davor durchgerutscht ist,
sieht er nie wieder. Am 23.09.2026 gegen die Monatsübersichten des
Ratsinformationssystems gemessen: **48 öffentliche Sitzungen seit 2018 fehlten
im Bestand**, mit rund 150 Vorlagen, die wir nicht kannten — darunter der
Betriebsausschuss Abfallwirtschaft vom 13.10.2021 (Wirtschaftsplan AWB und
Gebührenbedarfsberechnung 2022; die Haushaltsseiten schrieben „nicht im
Ratsinformationssystem“), zwei Ratssitzungen und der Finanzausschuss vom
06.05.2026.

``backfill_protocols.py`` half dabei nicht: Er speichert eine Sitzung nur, wenn
er ihr Protokoll lesen kann. Eine Sitzung ohne (lesbares) Protokoll blieb
damit samt Tagesordnung für immer weg — und mit ihr jede Vorlage, die nur dort
auf der Tagesordnung stand.

Dieses Skript speichert **nur die Sitzung mit ihrer Tagesordnung** (kein LLM,
eine Kalenderseite je Monat plus eine Seite je fehlender Sitzung). Den Rest
holen die vorhandenen Läufe von selbst: ``check_protocols`` die Vorlagen und
Anlagen (``missing_vorlage_kvonrs`` liest die Tagesordnungen), ``weekly_enrich``
die Anlagen-Volltexte, ``check_finanzdaten`` die Haushaltsschichten daraus.
Protokolle älter als 90 Tage bleiben Sache von ``backfill_protocols.py``.

    python scripts/nachlauf_sitzungen.py --seit 2018-01        # Einmal-Nachlauf
    python scripts/nachlauf_sitzungen.py --monate 24           # wöchentlich (weekly_enrich)
    python scripts/nachlauf_sitzungen.py --seit 2018-01 --trocken

Idempotent: Bekannte Sitzungen werden nicht noch einmal abgerufen.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council.scraper import CouncilScraper  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"


def monate(seit: str, bis: date) -> list[tuple[int, int]]:
    """Alle (Jahr, Monat) von ``seit`` (JJJJ-MM) bis einschließlich ``bis``."""
    y, m = int(seit[:4]), int(seit[5:7])
    out: list[tuple[int, int]] = []
    while (y, m) <= (bis.year, bis.month):
        out.append((y, m))
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def seit_fuer(monate_zurueck: int, heute: date) -> str:
    """Der Monat, ``monate_zurueck`` Monate vor dem laufenden."""
    y, m = heute.year, heute.month - monate_zurueck
    while m < 1:
        y, m = y - 1, m + 12
    return f"{y:04d}-{m:02d}"


def nachlauf(council_db: Path, seit: str, trocken: bool = False,
             scraper: CouncilScraper | None = None) -> dict:
    scraper = scraper or CouncilScraper(delay=1.0)
    store = CouncilStore(council_db)
    heute = date.today()
    gefunden: list[int] = []
    for y, m in monate(seit, heute):
        try:
            ids = scraper.session_ids_for_month(y, m)
        except Exception as exc:  # noqa: BLE001 — ein Monat stoppt nicht den Lauf
            print(f"  {y}-{m:02d}: Kalender nicht lesbar ({exc})", flush=True)
            continue
        bekannt = store.known_session_ids(ids)
        neu = [k for k in ids if k not in bekannt and k not in gefunden]
        if neu:
            print(f"  {y}-{m:02d}: {len(neu)} fehlende Sitzung(en) {neu}", flush=True)
        gefunden.extend(neu)

    gespeichert = leer = 0
    if not trocken:
        for ksinr in gefunden:
            try:
                session = scraper.fetch_session(ksinr)
            except Exception as exc:  # noqa: BLE001
                print(f"  {ksinr}: nicht abrufbar ({exc})", flush=True)
                continue
            if not session:
                leer += 1
                continue
            store.save_session(session)
            gespeichert += 1
            print(f"  ✓ {session.session_date} {session.committee} "
                  f"({len(session.agenda_items)} TOPs)", flush=True)
    store.close()
    return {"Monate": len(monate(seit, heute)), "Fehlende Sitzungen": len(gefunden),
            "Nachgetragen": gespeichert, "Ohne Tagesordnung": leer}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    gruppe = ap.add_mutually_exclusive_group()
    gruppe.add_argument("--seit", help="erster Monat, JJJJ-MM (Vorgabe: 24 Monate zurück)")
    gruppe.add_argument("--monate", type=int, default=24,
                        help="so viele Monate zurück (Vorgabe 24)")
    ap.add_argument("--trocken", action="store_true", help="nur zählen, nichts speichern")
    args = ap.parse_args()
    seit = args.seit or seit_fuer(args.monate, date.today())
    print(f"Sitzungs-Nachlauf ab {seit}{' (trocken)' if args.trocken else ''}")
    stats = nachlauf(args.db, seit, trocken=args.trocken)
    print(" · ".join(f"{k}: {v}" for k, v in stats.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
