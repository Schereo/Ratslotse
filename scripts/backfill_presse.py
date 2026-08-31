#!/usr/bin/env python3
"""Backfill der Stadt-Pressemitteilungen über das paginierte Archiv.

Crawlt die Listen-Kette (TYPO3-Pagination, ~20 Einträge/Seite, cHash-Links
werden verfolgt statt konstruiert) und lädt fehlende Detailseiten, bis das
PM-Datum vor --since liegt. Idempotent; ein zweiter Lauf holt nur Fehlendes.
Kein LLM — nur HTTP + Parsing. Danach einmal embed_decisions.py laufen lassen
(oder check_presse.py, das embeddet direkt)::

    python scripts/backfill_presse.py --since 2018-01-01
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import presse  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--since", default="2018-01-01",
                    help="ältestes mitzunehmendes PM-Datum (Deckung mit den Ratsdaten)")
    ap.add_argument("--max-seiten", type=int, default=600)
    args = ap.parse_args()

    store = CouncilStore(args.db)
    bekannt = store.presse_urls()
    url: str | None = None
    neu = alt_erreicht = fehlgeschlagen = seiten = 0
    while seiten < args.max_seiten:
        eintraege, url = presse.fetch_liste(url)
        seiten += 1
        if not eintraege:
            break
        for e in eintraege:
            if e["url"] in bekannt:
                continue
            try:
                detail = presse.fetch_detail(e["url"])
            except Exception as exc:  # noqa: BLE001
                fehlgeschlagen += 1
                print(f"  FEHLER {e['url']}: {exc!r}", flush=True)
                continue
            if not detail:
                fehlgeschlagen += 1
                continue
            date = detail["date"] or ""
            if date and date < args.since:
                alt_erreicht += 1
                continue
            store.save_presse(e["url"], None, detail["title"] or e["title"], detail["date"], detail["text"])
            bekannt.add(e["url"])
            neu += 1
        print(f"  Seite {seiten}: {neu} neu gesamt", flush=True)
        # Sobald eine ganze Seite nur noch Zu-Altes lieferte, ist Schluss.
        if alt_erreicht >= len(eintraege):
            break
        alt_erreicht = 0
        if url is None:
            break
    store.close()
    print(f"=== done: {neu} Pressemitteilungen neu, {fehlgeschlagen} fehlgeschlagen, {seiten} Seiten ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
