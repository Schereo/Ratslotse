#!/usr/bin/env python3
"""Messlauf: Dossier je Vorlage gegen eval/dossier_gold.json (Plan Vorlagen § 7.2).

Automatisch: Pflichtfakten im richtigen Abschnitt, Status leerer Felder,
Wegfallquote je Form, verbotene Inhalte (die Belegprüfung verwirft sie schon —
hier wird gezählt, dass keiner durchkam). Von Hand anhand der Ausgabe:
gestützt, treu, Leitfragen ohne PDF beantwortbar. Kleiner Lauf über den
lokalen Key (12 Aufrufe).

    PYTHONPATH=. .venv/bin/python eval/run_dossier.py [--modell openai/gpt-5.6-luna] [--nur 26/0796]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council.store import CouncilStore  # noqa: E402
from kern import usage  # noqa: E402

ABSCHNITTE = ("proposal", "costs", "changes", "affected", "places", "figures", "administration", "next")


def _aussagen(payload: dict, abschnitt: str) -> list[dict]:
    feld = payload.get(abschnitt) or {}
    out = []
    for v in feld.values() if isinstance(feld, dict) else []:
        for x in v if isinstance(v, list) else [v]:
            if isinstance(x, dict) and x.get("text"):
                out.append(x)
            if isinstance(x, dict):
                for y in x.values():
                    if isinstance(y, dict) and y.get("text"):
                        out.append(y)
    return out


def main() -> int:
    try:
        from council import template_dossier
    except ImportError:
        print("council/template_dossier.py fehlt noch — das Gold steht vor dem Prompt (Plan PR 11/12).")
        return 1
    ap = argparse.ArgumentParser()
    ap.add_argument("--modell")
    ap.add_argument("--nur")
    a = ap.parse_args()
    gold = json.loads((ROOT / "eval" / "dossier_gold.json").read_text())["faelle"]
    store = CouncilStore(str(ROOT / "data" / "council.sqlite"))
    marke = usage.jetzt_utc()
    fakten_ok = fakten_n = status_ok = status_n = 0
    wegfall: dict[str, list[int]] = {}
    for g in gold:
        if a.nur and g["template"] != a.nur:
            continue
        d = template_dossier.build_for_template(store, g["template"], batch=False, force=True, model=a.modell) or {}
        p = d.get("payload") or {}
        print(f"\n=== {g['template']} (Form {p.get('form')}, Gold {g['form']})")
        for s in ABSCHNITTE:
            for x in _aussagen(p, s):
                print(f"  [{s}] {x['text'][:170]}  ({x.get('source')} S.{x.get('page')})")
        for f in g["fakten"]:
            fakten_n += 1
            texte = " ".join(x["text"] for x in _aussagen(p, f["section"]))
            hit = any(w in texte for w in f["any"])
            fakten_ok += hit
            print(f"  {'✓' if hit else '✗'} {f['section']}: {f['notiz']}")
        for feld, erlaubt in (g.get("status") or {}).items():
            status_n += 1
            ist = (p.get(feld) or {}).get("status")
            status_ok += ist in erlaubt
            print(f"  {'✓' if ist in erlaubt else '✗'} Status {feld}: {ist} (erlaubt {erlaubt})")
        kept = sum(len(_aussagen(p, s)) for s in ABSCHNITTE)
        dropped = len(p.get("dropped") or [])
        wegfall.setdefault(p.get("form") or "?", []).extend([kept, dropped])
        print(f"  Aussagen {kept}, verworfen {dropped}")
    print(f"\nPflichtfakten {fakten_ok}/{fakten_n} ({fakten_ok / max(1, fakten_n):.0%}) · Status {status_ok}/{status_n}")
    for form, werte in sorted(wegfall.items()):
        k, dr = sum(werte[0::2]), sum(werte[1::2])
        print(f"  Wegfall {form}: {dr}/{k + dr} ({dr / max(1, k + dr):.0%})")
    print("Kosten:", usage.seit("template_dossier", marke))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
