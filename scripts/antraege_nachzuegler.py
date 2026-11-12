#!/usr/bin/env python3
"""Nachzügler-Lauf für Änderungsanträge (docs/plan-vorlagen-aufbereiten.md, § 4.3).

Anträge kommen am Vortag oder am Sitzungstag (Volt am 01.11., die CDU am
02.11. zur Ratssitzung am 02.11.2026). Der Morgenlauf von ``check_committees``
sieht sie dann nicht mehr. Dieser Lauf liest an Sitzungstagen und am Tag davor
die Tagesordnung der betroffenen Sitzungen neu (ein Abruf je Sitzung), lädt
neue Punkt-Anlagen und liest neue Anträge. Sonst Leerlauf.

crontab: ``0 11,13,16,18 * * *``
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from council import motions, punkt_texte  # noqa: E402
from council.scraper import CouncilScraper  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from kern.alerts import run_guarded  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"


def main() -> dict:
    store = CouncilStore(COUNCIL_DB)
    heute = date.today()
    sitzungen = [r["ksinr"] for r in store._conn.execute(  # noqa: SLF001 — eine Abfrage, kein Store-Zweck
        "SELECT ksinr FROM council_sessions WHERE session_date IN (?, ?)",
        (heute.isoformat(), (heute + timedelta(days=1)).isoformat()))]
    if not sitzungen:
        return {"sitzungen": 0, "anlagen": 0, "antraege": 0}
    scraper = CouncilScraper()
    for ksinr in sitzungen:
        session = scraper.fetch_session(ksinr)
        if session:
            store.save_session(session)
    texte = punkt_texte.nachladen(store, tage_zurueck=0, limit=40)
    gelesen = motions.nachziehen(store, tage_zurueck=0, tage_voraus=1, limit=20)
    return {"sitzungen": len(sitzungen), "anlagen": texte["geladen"], "antraege": gelesen["gelesen"]}


if __name__ == "__main__":
    raise SystemExit(run_guarded("antraege_nachzuegler", main))
