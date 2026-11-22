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

Dazu, unabhängig von beiden und zuerst: die **aktuelle Besetzung** von Rat
und Ausschüssen je Fraktion (``council/committee_seats.py``) — die Grundlage des
Mehrheitsrechners in den Werkzeugen. Sie liest das Ratsinfo unter seinem neuen
Host (ratsinfo.oldenburg.de/bi, seit 11/2026) und scheitert für sich: Ein
Fehler dort hält die Stammdaten nicht auf und umgekehrt.

Usage::

    python scripts/backfill_stammdaten.py
    python scripts/backfill_stammdaten.py --skip-memberships   # nur Personenliste
    python scripts/backfill_stammdaten.py --nur-besetzung      # nur Gremienbesetzung (~70 Abrufe)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import committee_seats, stammdaten  # noqa: E402
from council.scraper import CouncilScraper  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"


def besetzung(council_db: Path, delay: float = 1.0) -> int:
    """Die Besetzung aller Gremien neu holen und ersetzen; gibt die Zahl der
    Sitze zurück. Wirft, wenn das Ratsinfo keinen brauchbaren Rat liefert —
    dann bleibt der gespeicherte Stand stehen."""
    print("Gremienbesetzung (ratsinfo.oldenburg.de):", flush=True)
    seats = committee_seats.fetch_all(committee_seats.RisClient(delay=delay))
    store = CouncilStore(council_db)
    try:
        n = store.replace_committee_seats(seats)
    finally:
        store.close()
    gremien = len({s["committee"] for s in seats})
    print(f"  {n} Sitze in {gremien} Gremien gespeichert.", flush=True)
    return n


def process(council_db: Path, delay: float = 0.3, skip_memberships: bool = False) -> dict:
    try:
        sitze = besetzung(council_db)
        sitze_fehler = None
    except Exception as exc:  # noqa: BLE001 — die Stammdaten sollen trotzdem laufen
        sitze, sitze_fehler = 0, repr(exc)
        print(f"  Gremienbesetzung FEHLGESCHLAGEN: {exc!r}", flush=True)

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

    stats = {"personen": len(personen), "mitgliedschaften": memberships, "failed": failed,
             "gremiensitze": sitze, "gremiensitze_fehler": sitze_fehler}
    print(f"\n=== done: {stats['personen']} Personen, "
          f"{stats['mitgliedschaften']} Mitgliedschaften, {stats['failed']} Fehler ===")
    store.close()
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--delay", type=float, default=0.3)
    ap.add_argument("--skip-memberships", action="store_true")
    ap.add_argument("--nur-besetzung", action="store_true",
                    help="nur die aktuelle Besetzung der Gremien holen")
    args = ap.parse_args()
    if args.nur_besetzung:
        return 0 if besetzung(args.db) else 1
    stats = process(args.db, delay=args.delay, skip_memberships=args.skip_memberships)
    # Eine gescheiterte Gremienbesetzung macht den Lauf rot: Sonst rechnete der
    # Mehrheitsrechner wochenlang auf einem alten Stand, ohne dass es jemand merkt.
    if stats["gremiensitze_fehler"]:
        return 1
    return 1 if stats["failed"] and not stats["personen"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
