#!/usr/bin/env python3
"""Kuratierte Such-Aliasse säen (Akkuratheits-Paket, 10.08.26).

Umgangssprache und Kurzformen („Cäci", „WEH", „Uni") landen als Zeilen in
``council_entity_aliases`` mit ``source='glossar'`` — DERSELBEN Tabelle wie
die Themen-Dubletten des Admin-Panels. Der Themen-Rebuild ignoriert sie
(kein passendes obs-Slug), der Entitäts-Anker der Suche liest sie mit; die
Pflege kann damit später denselben Admin-Weg gehen wie die Dubletten.

Idempotent (INSERT OR IGNORE); Einträge, deren Ziel-Entität es (noch) nicht
gibt, werden übersprungen und genannt.

    python scripts/seed_glossar.py [--db data/council.sqlite]
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

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")

# alias → kanonischer Entitäts-Slug. Bewusst klein und sicher kuratiert —
# der Anker matcht ganze Wörter, kurze Mehrdeutigkeiten haben hier nichts
# verloren. Erweiterungen später über das Admin-Panel (Dubletten-Muster).
GLOSSAR: dict[str, str] = {
    "caeci": "caecilienbruecke",
    "caecibruecke": "caecilienbruecke",
    "weh": "weser-ems-hallen",
    "weser-ems-halle": "weser-ems-hallen",
    "uni": "universitaet",
    "uni-oldenburg": "universitaet",
    "hbf": "hauptbahnhof",
    "fliegerhorstgelaende": "fliegerhorst",
    # „Stadionneubau" allein ist keine Entität — die heißt „Stadionneubau
    # Maastrichter Straße"; der Alias lässt die Kurzform ankern.
    "stadionneubau": "stadionneubau-maastrichter-strasse",
    # BEWUSST NICHT: „marschwegstadion" → stadion — das Marschwegstadion ist
    # das ALTE Stadion und eine eigene Entität; ein Alias wäre sachlich falsch.
}


def main() -> dict:
    ap = argparse.ArgumentParser(description="Such-Glossar in council_entity_aliases säen")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()
    store = CouncilStore(Path(args.db))
    try:
        vorhandene = {r["slug"] for r in store._conn.execute(
            "SELECT slug FROM council_entities")}
        gesetzt, uebersprungen = 0, []
        with store._conn:
            for alias, ziel in GLOSSAR.items():
                if ziel not in vorhandene:
                    uebersprungen.append(f"{alias}→{ziel}")
                    continue
                cur = store._conn.execute(
                    "INSERT OR IGNORE INTO council_entity_aliases "
                    "(slug, canonical_slug, source, reason, created_at) "
                    "VALUES (?, ?, 'glossar', 'kuratierter Such-Alias', datetime('now'))",
                    (alias, ziel))
                gesetzt += cur.rowcount
        print(f"{gesetzt} Aliasse gesetzt"
              + (f", übersprungen (Ziel fehlt): {', '.join(uebersprungen)}" if uebersprungen else ""))
        return {"gesetzt": gesetzt, "uebersprungen": len(uebersprungen)}
    finally:
        store.close()


if __name__ == "__main__":
    main()
