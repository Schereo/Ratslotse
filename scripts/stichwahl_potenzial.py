#!/usr/bin/env python3
"""Stadtweite Stichwahlanalyse aus eingefrorenen Ergebnissen.

Der bestehende Skriptname bleibt als Einstieg erhalten. Ohne Argumente ein
neutraler Bericht, mit --json PFAD ein Export derselben Daten wie die Seite.
Keine Regler, Gebietsrangfolgen oder Schätzungen von Stimmenwanderungen.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.election import runoff_analysis  # noqa: E402


def zahl(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="Stadtanalyse als JSON schreiben")
    args = parser.parse_args()
    p = runoff_analysis.compute()
    print(f"OB-Wahl {p['election_date']} — {p['data_status']}")
    for candidate in p["candidates"]:
        print(f"{candidate['name']}: {zahl(candidate['votes'])} Stimmen")
    t = p["totals"]
    print(f"Wahlberechtigte: {zahl(t['eligible'])}; Wählende: {zahl(t['voters'])}; nicht teilgenommen: {zahl(t['non_voters'])}")
    print(f"Ratswahl {p['council']['year']}: {zahl(p['council']['cdu_votes'])} CDU-Stimmen (keine Personenzahl)")
    for h in p["history"]:
        print(f"{h['year']}: {zahl(h['first']['voters'])} → {zahl(h['runoff']['voters'])} Wählende. {h['context']}")
    if args.json:
        args.json.write_text(json.dumps(p, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
