#!/usr/bin/env python3
"""Finanz-Datensätze des Open-Data-Portals der Stadt einlesen.

Zwei CSVs von opendata.oldenburg.de (Lizenz dl-de/by-2-0), beide jährlich
fortgeschrieben — Grundlage des Haushalts-Bereichs:

- **Steuereinnahmen seit 1998** (Ist, je Steuerart) → ``council_steuern``.
  Für Steuer-Steckbriefe und Zeitreihen: Grundsteuer A+B, Gewerbesteuer
  (nach Umlage), Einkommensteuer-/Umsatzsteueranteil, Vergnügungssteuer …
- **Steuerkraftmesszahlen + Schlüsselzuweisungen seit 1992** →
  ``council_steuerkraft``. Zeigt die NFAG-Mechanik (mehr eigene Steuerkraft
  → weniger Landeszuweisungen) — Pflichtkontext für jede Hebesatz-Simulation.

Idempotent (INSERT OR REPLACE); einmal jährlich reicht, es gibt keinen Cron::

    python scripts/ingest_finanzen_opendata.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council import haushalt  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")
_UA = {"User-Agent": "Ratslotse/1.0 (ratslotse.de; Haushalts-Bereich)"}


def main() -> int:
    store = CouncilStore(COUNCIL_DB)
    try:
        r = requests.get(haushalt.STEUERN_CSV_URL, headers=_UA, timeout=120)
        r.raise_for_status()
        steuern = haushalt.parse_steuereinnahmen(r.text)
        if not steuern:
            print("Steuereinnahmen-CSV nicht lesbar — nichts gespeichert.", file=sys.stderr)
            return 1
        n = store.save_steuereinnahmen(steuern, haushalt.STEUERN_CSV_URL)
        jahre = sorted({s["jahr"] for s in steuern})
        print(f"Steuereinnahmen: {n} Zeilen ({jahre[0]}–{jahre[-1]}).")

        r = requests.get(haushalt.STEUERKRAFT_CSV_URL, headers=_UA, timeout=120)
        r.raise_for_status()
        kraft = haushalt.parse_steuerkraft(r.text)
        if not kraft:
            print("Steuerkraft-CSV nicht lesbar — nichts gespeichert.", file=sys.stderr)
            return 1
        n = store.save_steuerkraft(kraft, haushalt.STEUERKRAFT_CSV_URL)
        print(f"Steuerkraft/Schlüsselzuweisungen: {n} Jahre "
              f"({kraft[0]['jahr']}–{kraft[-1]['jahr']}).")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
