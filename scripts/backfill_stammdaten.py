#!/usr/bin/env python3
"""Backfill/refresh der Personen-Stammdaten aus dem Ratsinformationssystem.

Zwei Schritte, zusammen ein paar hundert Requests (Minuten, kein LLM):

1. **Mandatsträger** über alle Wahlperioden (zurück bis 2001) einsammeln —
   Personen-Nummer (kpenr), Name und die aktuelle Fraktion laut Ratsinfo.
2. Je Person die **Mitarbeit** über alle Wahlperioden: Gremium, Art der
   Mitarbeit (Rolle), von/bis. Je Person komplett ersetzt → idempotent.

Die Fraktions-HISTORIE kommt bewusst nicht von hier: SessionNet überschreibt
Fraktionen rückwirkend mit dem aktuellen Stand (an einem Fraktionswechsler
verifiziert) — der Verlauf wird aus unseren Anwesenheitsdaten abgeleitet.
Kontaktdaten der Personenseiten (Adresse, Telefon, Beruf) werden nicht geladen.

Usage::

    python scripts/backfill_stammdaten.py
    python scripts/backfill_stammdaten.py --skip-memberships   # nur Personenliste
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import stammdaten  # noqa: E402
from council.scraper import CouncilScraper  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"


def process(council_db: Path, delay: float = 0.3, skip_memberships: bool = False) -> dict:
    store = CouncilStore(council_db)
    scraper = CouncilScraper(delay=delay)

    # 1. Personen über alle Wahlperioden (älteste zuerst — die letzte Schreibung
    #    einer Person gewinnt, also trägt sie am Ende den neuesten Namen/Stand).
    wps = stammdaten.fetch_wahlperioden(scraper)
    print(f"{len(wps)} Wahlperioden: "
          + ", ".join(w["label"] for w in wps), flush=True)
    personen: dict[int, dict] = {}
    for wp in wps:
        rows = stammdaten.fetch_mandatstraeger(scraper, wp["wpnr"])
        for r in rows:
            personen[r["kpenr"]] = r
        print(f"  WP {wp['label']}: {len(rows)} Mandatsträger", flush=True)
    # Aktuelle Ansicht zuletzt — hält Namen + Fraktion auf dem neuesten Stand.
    for r in stammdaten.fetch_mandatstraeger(scraper):
        personen[r["kpenr"]] = r

    for p in personen.values():
        store.save_person(p["kpenr"], p["name"], p.get("fraktion"))
    print(f"{len(personen)} Personen gespeichert.", flush=True)

    # 2. Mitgliedschaften je Person (alle Wahlperioden in einem Abruf).
    memberships = failed = 0
    if not skip_memberships:
        kpenrs = sorted(personen)
        for i, kpenr in enumerate(kpenrs, 1):
            try:
                rows = stammdaten.fetch_person_mitarbeit(scraper, kpenr)
                memberships += store.save_memberships(kpenr, rows)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"  kpenr={kpenr} FAILED: {exc!r}", flush=True)
            if i % 50 == 0 or i == len(kpenrs):
                print(f"  [{i}/{len(kpenrs)}] … {memberships} Mitgliedschaften", flush=True)

    stats = {"personen": len(personen), "mitgliedschaften": memberships, "failed": failed}
    print(f"\n=== done: {stats['personen']} Personen, "
          f"{stats['mitgliedschaften']} Mitgliedschaften, {stats['failed']} Fehler ===")
    store.close()
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--delay", type=float, default=0.3)
    ap.add_argument("--skip-memberships", action="store_true")
    args = ap.parse_args()
    stats = process(args.db, delay=args.delay, skip_memberships=args.skip_memberships)
    return 1 if stats["failed"] and not stats["personen"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
