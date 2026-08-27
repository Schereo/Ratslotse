#!/usr/bin/env python3
"""Chunk-Vektoren für Anlagen-Volltexte (Task 33) — Dokumentenkanal der
schnellen und gründlichen Recherche. Die Texte lädt scripts/backfill_anlagen_texte.py.

Wie embed_decisions ist fastembed bewusst NICHT in requirements — für den Lauf
installieren, Deploy + Web-Service bleiben unberührt::

    pip install fastembed
    python scripts/embed_anlagen.py            # alles Fehlende (hash-idempotent)
    python scripts/embed_anlagen.py --limit 50 # Stichprobe

Läuft auch als Wochen-Backstop in weekly_enrich (neue Anlagen der Woche).
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

from council import embeddings  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def main() -> dict:
    ap = argparse.ArgumentParser(description="Anlagen-Chunk-Vektoren schreiben (fastembed)")
    ap.add_argument("--limit", type=int, default=None,
                    help="höchstens so viele Anlagen embedden (Standard: alle fehlenden)")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()
    store = CouncilStore(Path(args.db))
    try:
        offen = len(store.anlagen_missing_embeddings(limit=args.limit))
        print(f"{offen} Anlagen ohne (aktuelle) Vektoren …", flush=True)
        chunks = embeddings.embed_anlagen_missing(store, limit=args.limit)
        print(f"fertig: {chunks} Chunks geschrieben", flush=True)
        return {"anlagen_offen": offen, "chunks_geschrieben": chunks}
    finally:
        store.close()


if __name__ == "__main__":
    from kern.alerts import run_guarded

    run_guarded("embed_anlagen", main)
