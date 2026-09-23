#!/usr/bin/env python3
"""Quizfragen aus den eigenen Daten bauen — ohne Modell, ohne Kosten.

„Angenommen oder abgelehnt?“ aus den Anträgen mit klarem Ausgang und „Wofür
gibt Oldenburg mehr aus?“ aus den Haushaltsprodukten (``council.quiz_formats``).
Idempotent: Neue Fragen werden angelegt, vorhandene über ihren stabilen
Schlüssel aufgefrischt — ein neues Haushaltsjahr ändert also Zahlen und
Lösung derselben Frage, statt eine zweite daneben zu legen.

Läuft als Schritt von ``weekly_enrich.py``; von Hand::

    python scripts/build_quiz_formats.py            # bauen und speichern
    python scripts/build_quiz_formats.py --trocken  # nur zeigen
"""
from __future__ import annotations

import argparse
import collections
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import quiz_formats  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--trocken", action="store_true", help="nur zeigen, nichts speichern")
    args = ap.parse_args()

    store = CouncilStore(args.db)
    try:
        questions = quiz_formats.build_all(store)
        by = collections.Counter(q["format"] for q in questions)
        print(f"{len(questions)} Fragen gebaut: {dict(by)}")
        if args.trocken:
            for q in questions[:8]:
                print(f"  [{q['format']}] {q['question']} → {q['options'][q['correct_index']]}")
            return 0
        n_new = store.save_quiz_questions(questions)
        n_upd = store.refresh_quiz_payloads(questions)
        print(f"{n_new} neu, {n_upd} aufgefrischt.")
        # Kein einziger Baustein heißt: Tabelle leer oder Filter zu streng —
        # beides soll im Wochenlauf auffallen statt still nichts zu tun.
        return 0 if questions else 1
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
