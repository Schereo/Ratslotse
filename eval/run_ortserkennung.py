#!/usr/bin/env python3
"""Ortserkennung der KI-Frage: Wortabgleich allein gegen Wortabgleich plus
Auswahl durch das Analyse-Modell (``qa._ortsblock``).

Anlass: „Was wird gerade beim Oldenburger Hafenbecken gebaut?“ (12.10.2026)
fand keinen Ort, weil „Hafenbecken“ kein Katalogwort ist. Die Fälle in
``cases_ortserkennung.json`` sind Alltagssprache, Teilwörter, Tippfehler —
und Fragen OHNE Ort, die keinen bekommen dürfen.

    .venv/bin/python eval/run_ortserkennung.py            # Katalog aus data/council.sqlite
    .venv/bin/python eval/run_ortserkennung.py --db pfad

Kosten: ein Analyse-Aufruf je Fall (Flash Lite), zusammen unter einem Cent.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from council import qa  # noqa: E402
from council.store import CouncilStore  # noqa: E402


def erkenne(store, frage: str, mit_modell: bool) -> str | None:
    """Dieselbe Reihenfolge wie im Router: Wortlaut zuerst, dann die Wahl."""
    ort = qa.finde_ort(frage, store)
    if mit_modell and qa.braucht_ortsliste(ort):
        analyse = qa.analyse_query(frage, orte=qa.ortsliste(store))
        ort = qa.ort_entscheiden(ort, analyse.get("ort_id"), store)
    return ort["id"] if ort else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/council.sqlite")
    args = ap.parse_args()
    store = CouncilStore(args.db)
    faelle = json.loads((Path(__file__).parent / "cases_ortserkennung.json").read_text())
    ids = {i for i, _ in qa.ortsliste(store)}
    stand = {"vorher": 0, "nachher": 0}
    for f in faelle:
        unbekannt = [e for e in f["expect"] if e and e not in ids]
        if unbekannt:
            print(f"{f['id']}: erwartete id fehlt im Katalog: {unbekannt}")
            return 2
        vorher = erkenne(store, f["question"], mit_modell=False)
        nachher = erkenne(store, f["question"], mit_modell=True)
        ok_v, ok_n = vorher in f["expect"], nachher in f["expect"]
        stand["vorher"] += ok_v
        stand["nachher"] += ok_n
        print(f"{'✓' if ok_v else '✗'} {'✓' if ok_n else '✗'}  {f['id']:<24} vorher={vorher}  nachher={nachher}")
    n = len(faelle)
    print(f"\nRichtig: vorher {stand['vorher']}/{n}, nachher {stand['nachher']}/{n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
