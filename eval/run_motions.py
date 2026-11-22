#!/usr/bin/env python3
"""Messlauf: Änderungsanträge lesen gegen eval/motions_gold.json (Plan Vorlagen § 7.3).

Automatisch geprüft: Antragsteller, Ziel, Muster, alt/neu vorhanden oder
nicht, Fassungsbezug, „Altfassung nicht beigefügt", Wortdiff. Treue des
Bedeutungssatzes und richtige alt/neu-Paare prüft die Hand anhand der Ausgabe.
Kleiner Lauf über den lokalen Key (12 Aufrufe, ≈ 0,01 $).

    PYTHONPATH=. .venv/bin/python eval/run_motions.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council import motions  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from kern import usage  # noqa: E402


def main() -> int:
    gold = json.loads((ROOT / "eval" / "motions_gold.json").read_text())["faelle"]
    store = CouncilStore(str(ROOT / "data" / "council.sqlite"))
    marke = usage.jetzt_utc()
    punkte = {"applicants": 0, "target": 0, "pattern": 0, "before_after": 0, "base": 0}
    for g in gold:
        p = motions.extract_one(store, g["document_id"], g["ksinr"], g["item"], batch=False, force=True) or {}
        fehler = []
        if not set(g["applicants"]) <= set(p.get("applicants") or []):
            fehler.append(f"Antragsteller {p.get('applicants')} statt {g['applicants']}")
        else:
            punkte["applicants"] += 1
        if g["target"] and g["target"].lower() not in (p.get("target") or "").lower():
            fehler.append(f"Ziel {p.get('target')!r} ohne {g['target']!r}")
        else:
            punkte["target"] += 1
        if p.get("pattern") not in g["pattern"]:
            fehler.append(f"Muster {p.get('pattern')} statt {g['pattern']}")
        else:
            punkte["pattern"] += 1
        ba_ok = True
        for feld in ("before", "after"):
            soll = g[feld]
            if (soll == "ja" and not p.get(feld)) or (soll == "nein" and p.get(feld)):
                fehler.append(f"{feld} {'fehlt' if soll == 'ja' else 'ist da'}")
                ba_ok = False
        if g.get("diff_enthaelt"):
            text = " ".join(t for op, t in (p.get("diff") or []) if op != "=")
            if not all(w in text for w in g["diff_enthaelt"]):
                fehler.append(f"Wortdiff ohne {g['diff_enthaelt']}")
                ba_ok = False
        punkte["before_after"] += ba_ok
        base_ok = (g.get("base_template") == p.get("base_template")) and (bool(g.get("base_missing")) == bool(p.get("base_missing")))
        if not base_ok:
            fehler.append(f"Basis {p.get('base_template')}/{p.get('base_missing')} statt {g.get('base_template')}/{g.get('base_missing', False)}")
        punkte["base"] += base_ok
        print(f"\n=== {g['document_id']} {g['item']} — {g['notiz']}")
        print(f"  {p.get('applicants')} · {p.get('target')} · {p.get('pattern')} · Basis {p.get('base_template')} · fehlt {p.get('base_missing')}")
        for feld in ("before", "after", "meaning", "reason"):
            v = p.get(feld)
            print(f"  {feld}: {v['text'][:180] if v else '—'}")
        if p.get("diff"):
            print("  diff:", [d for d in p["diff"] if d[0] != "="][:4])
        print("  ✓" if not fehler else "  ✗ " + "; ".join(fehler))
    n = len(gold)
    print("\n" + " · ".join(f"{k} {v}/{n}" for k, v in punkte.items()))
    print("Kosten:", usage.seit(motions.FEATURE, marke))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
