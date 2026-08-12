#!/usr/bin/env python3
"""Täglicher Abgleich der Stadt-Pressemitteilungen (RSS → Details → FTS/Chunks).

Holt den RSS-Feed (60 Einträge), lädt fehlende Detailseiten, schreibt sie in
council_presse (+FTS) und embeddet die neuen Texte direkt (best-effort — ohne
fastembed übernimmt der Wochenlauf embed_decisions.py). Kein LLM.

Crontab (Server): täglich, z. B.  15 5 * * *  … scripts/check_presse.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import presse  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from kern.alerts import run_guarded  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"


def main() -> dict:
    store = CouncilStore(COUNCIL_DB)
    bekannt = store.presse_urls()
    feed = presse.fetch_feed()
    neu = fehlgeschlagen = 0
    for eintrag in feed:
        if eintrag["url"] in bekannt:
            continue
        try:
            detail = presse.fetch_detail(eintrag["url"])
        except Exception:  # noqa: BLE001 — eine kaputte Seite killt nicht den Lauf
            fehlgeschlagen += 1
            continue
        if not detail:
            fehlgeschlagen += 1
            continue
        store.save_presse(
            eintrag["url"], eintrag["news_id"],
            detail["titel"] or eintrag["titel"],
            detail["datum"] or eintrag["datum"], detail["text"])
        neu += 1
    chunks = 0
    if neu:
        try:
            from council import embeddings
            chunks = embeddings.embed_presse_missing(store)
        except Exception:  # noqa: BLE001 — fastembed fehlt → Wochenlauf holt nach
            pass
    # Laufende Bauleitplan-Beteiligungen im selben Tageslauf aktualisieren —
    # eigener try: ein Ausfall des Portals darf den Presse-Teil nicht kosten.
    beteiligungen = -1
    try:
        from council import beteiligung
        beteiligungen = store.save_beteiligungen(beteiligung.fetch_planfaelle())
    except Exception:  # noqa: BLE001
        pass
    store.close()
    return {"feed": len(feed), "neu": neu, "fehlgeschlagen": fehlgeschlagen,
            "chunks": chunks, "beteiligungen": beteiligungen}


if __name__ == "__main__":
    raise SystemExit(run_guarded("check_presse", main))
