#!/usr/bin/env python3
"""Oldenburger Haushaltspläne einlesen → Haushalts-Tabelle + Quizfragen.

Lädt die **beschlossenen** Haushaltsplan-PDFs (oldenburg.de), parst je Jahr die
„Übersicht Ergebnishaushalt" (Teilhaushalte × Erträge/Aufwendungen/Ergebnis)
und erzeugt daraus **deterministische** Quizfragen mit Diagrammen — kein LLM,
jede Zahl 1:1 aus dem PDF, jede Frage mit PDF-Quelle:

- Basis-Fragen aus dem **neuesten** Jahr (Gesamt, Defizit, Anteil/Donut,
  große Blöcke, Erträge, Ranking-MCs),
- **Trend-Fragen** über alle eingelesenen Jahre (Wachstums-Schätzfrage +
  stärkster Wachstumsbereich, mit Trendlinien-Diagramm).

Default lädt ALLE bekannten Jahre (2020–2026, ohne 2024 — dessen PDF hat eine
defekte Text-Kodierung). Läuft einmal je neuem Haushaltsjahr::

    python scripts/ingest_haushalt.py                 # alle bekannten Jahre
    python scripts/ingest_haushalt.py --year 2026     # nur ein Jahr nachladen
    python scripts/ingest_haushalt.py --pdf datei.pdf --year 2026
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


def _ingest_year(store: CouncilStore, year: int, url: str | None, pdf: str | None) -> bool:
    """Ein Jahr laden + parsen + speichern. False bei Parse-Fehlschlag."""
    if pdf:
        pdf_path = pdf
    else:
        r = requests.get(url, headers=_UA, timeout=120)
        r.raise_for_status()
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.write(r.content)
        tmp.close()
        pdf_path = tmp.name
    rows = haushalt.extract_from_pdf(pdf_path)
    if not rows:
        print(f"  {year}: Übersicht nicht gefunden/validiert — übersprungen.", file=sys.stderr)
        return False
    store.save_haushalt(year, rows, url or f"file:{pdf}")
    summe = next((r for r in rows if r["is_summe"]), {})
    print(f"  {year}: {len(rows)} Zeilen (Aufwendungen {round((summe.get('aufwendungen') or 0) / 1e6)} Mio. €)")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Haushaltspläne einlesen + Quizfragen bauen")
    ap.add_argument("--year", type=int, default=None, help="nur dieses Jahr laden (Default: alle bekannten)")
    ap.add_argument("--url", default=None, help="PDF-URL (mit --year)")
    ap.add_argument("--pdf", default=None, help="lokale PDF-Datei statt Download (mit --year)")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()

    store = CouncilStore(Path(args.db))
    try:
        print("Einlesen:", flush=True)
        if args.year:
            url = args.url or haushalt.HAUSHALT_URLS.get(args.year)
            if not url and not args.pdf:
                print(f"Keine bekannte PDF-URL für {args.year} — bitte --url/--pdf angeben.", file=sys.stderr)
                return 2
            _ingest_year(store, args.year, url, args.pdf)
        else:
            for year, url in sorted(haushalt.HAUSHALT_URLS.items()):
                try:
                    _ingest_year(store, year, url, None)
                except requests.RequestException as exc:
                    print(f"  {year}: Download fehlgeschlagen ({exc}) — übersprungen.", file=sys.stderr)

        # Fragen aus dem DB-Stand bauen: Basis = neuestes Jahr, Trend = alle Jahre.
        years = store.haushalt_years()
        if not years:
            print("Keine Haushaltsdaten in der DB — keine Fragen gebaut.", file=sys.stderr)
            return 1
        newest = years[-1]
        by_year = {y: store.get_haushalt(y) for y in years}
        src = haushalt.HAUSHALT_URLS.get(newest) or (by_year[newest][0].get("source_url") if by_year[newest] else "")
        questions = haushalt.build_questions(by_year[newest], newest, src)
        questions += haushalt.build_trend_questions(by_year, src)
        n_new = store.save_quiz_questions(questions)
        # Bestehende Fragen auffrischen (z. B. Trendlinie um neue Jahre verlängern).
        n_upd = store.refresh_quiz_payloads(questions)
        print(f"Jahre in DB: {years} · {len(questions)} Fragen gebaut, {n_new} neu, {n_upd} aufgefrischt.", flush=True)
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
