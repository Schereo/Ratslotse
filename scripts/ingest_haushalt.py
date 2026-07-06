#!/usr/bin/env python3
"""Oldenburger Haushaltsplan einlesen → Haushalts-Tabelle + Quizfragen.

Lädt die „Übersichten" des **beschlossenen** Haushaltsplans (oldenburg.de),
parst die Seite „Übersicht Ergebnishaushalt" (Teilhaushalte × Erträge/
Aufwendungen/Ergebnis) und erzeugt daraus **deterministische** Quizfragen mit
Diagramm — kein LLM, jede Zahl 1:1 aus dem PDF, jede Frage mit PDF-Quelle.

Läuft einmalig je Haushaltsjahr (der Plan ändert sich nicht unterjährig)::

    python scripts/ingest_haushalt.py                # Haushalt 2026 (Default)
    python scripts/ingest_haushalt.py --year 2026 --url https://…/UEbersichten.pdf
    python scripts/ingest_haushalt.py --pdf lokal.pdf --year 2026
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import haushalt  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")
_UA = {"User-Agent": "Ratslotse/1.0 (ratslotse.de; Haushalts-Quiz)"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Haushaltsplan einlesen + Quizfragen bauen")
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--url", default=None, help="PDF-URL (Default: bekannter Plan des Jahres)")
    ap.add_argument("--pdf", default=None, help="lokale PDF-Datei statt Download")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()

    url = args.url or haushalt.HAUSHALT_URLS.get(args.year)
    if not url and not args.pdf:
        print(f"Keine bekannte PDF-URL für {args.year} — bitte --url angeben.", file=sys.stderr)
        return 2

    if args.pdf:
        pdf_path = args.pdf
    else:
        r = requests.get(url, headers=_UA, timeout=60)
        r.raise_for_status()
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.write(r.content)
        tmp.close()
        pdf_path = tmp.name

    rows = haushalt.extract_from_pdf(pdf_path)
    if not rows:
        print("Übersicht Ergebnishaushalt nicht gefunden/validiert — Layout geändert?", file=sys.stderr)
        return 1

    store = CouncilStore(Path(args.db))
    try:
        n_rows = store.save_haushalt(args.year, rows, url or f"file:{args.pdf}")
        questions = haushalt.build_questions(rows, args.year, url or f"file:{args.pdf}")
        n_new = store.save_quiz_questions(questions)
    finally:
        store.close()

    summe = next((r for r in rows if r["is_summe"]), {})
    print(f"Haushalt {args.year}: {n_rows} Zeilen gespeichert "
          f"(Aufwendungen gesamt {round((summe.get('aufwendungen') or 0) / 1e6)} Mio. €) · "
          f"{len(questions)} Fragen gebaut, {n_new} neu.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
