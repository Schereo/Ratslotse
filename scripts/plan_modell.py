#!/usr/bin/env python3
"""Was ein Sprachmodell aus den Texten der Stadt heraussucht (Plan „Pläne der Stadt“).

Schreibt geprüfte Dateien wie ``scripts/plan_status.py`` — nur dass hier ein
Modell die Stellen findet. Es urteilt nicht frei: Jede Angabe trägt ein
wörtliches Zitat, und was sich nicht belegen lässt, fällt weg
(``council/plan_judge.py``). ``--pruefen`` prüft die Dateien später **ohne
Modell** gegen die Vorlagentexte.

Kosten: jeder Lauf nennt, was er gekostet hat. Vor einem ganzen Lauf mit
``--limit`` messen und hochrechnen; ab etwa 1 $ je Lauf erst fragen.

    python scripts/plan_modell.py mobilitaet --limit 1 --golden   # ein Bericht, gegen das Golden-Set
    python scripts/plan_modell.py mobilitaet                      # alle Berichte, Datei schreiben
    python scripts/plan_modell.py mobilitaet --pruefen            # ohne Modell: Zitate gegen den Bestand
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from council import plan_judge, plan_state, plans  # noqa: E402
from council.store import CouncilStore  # noqa: E402

GOLDEN = WURZEL / "eval"

# ── Mobilitätsplan: Stand je Maßnahme aus den Sachstandsberichten ──────────

MOBILITY = "mobilitaetsplan_2030"
#: Die Sachstandsberichte im Verkehrsausschuss, ältester zuerst.
MOBILITY_REPORTS = ("23/0562", "25/0041", "26/0190")


def _report(store: CouncilStore, number: str) -> tuple[str, str]:
    """(Text, Stichtag JJJJ-MM) eines Berichts; der Stichtag ist seine erste Beratung."""
    row = store.get_vorlage_by_nr(number)
    if not row or not row.get("raw_text"):
        raise SystemExit(f"Vorlage {number}: kein Text im Bestand")
    stem = "/".join(number.split("/")[:2])
    dates = [i["date"] for i in store.plan_items(MOBILITY) if (i["template_number"] or "").startswith(stem)]
    if not dates:
        raise SystemExit(f"Vorlage {number}: nicht unter den Tagesordnungspunkten des Plans")
    return row["raw_text"], min(dates)[:7]


def mobility_snapshot(number: str, as_of: str, found: list[dict], total: int) -> dict:
    return {
        "as_of": as_of,
        "source": {"kind": "template", "label": "Sachstandsbericht Mobilitätsplan", "template": number,
                   "url": None, "fetched": None, "read_by": "model"},
        "total": total,
        "complete": False,
        "counts": [],
        "measures": found,
    }


def mobility_check(store: CouncilStore) -> list[str]:
    """Ohne Modell: Steht jedes Zitat der Datei wörtlich in seinem Bericht, jedes Statuswort im Zitat?"""
    data = plan_state.load(MOBILITY)
    codes = {m["code"] for m in (plans.measures(MOBILITY) or {"measures": []})["measures"]}
    problems = []
    for snap in (data or {}).get("snapshots", []):
        text = plan_judge.squash(_report(store, snap["source"]["template"])[0])
        kept = plan_judge.verified([{"code": m["code"], "quote": m["quote"], "status_words": m["status_raw"],
                                     "status": m["status_norm"]} for m in snap["measures"]], text, codes)
        if len(kept) != len(snap["measures"]):
            lost = sorted({m["code"] for m in snap["measures"]} - {k["code"] for k in kept})
            problems.append(f"{snap['source']['template']}: nicht belegt {lost}")
    return problems


def mobility_golden(found: list[dict]) -> dict:
    """Vergleich mit dem von Hand gelesenen Bericht 26/0190: falsche Zuordnungen, Lücken, Stufe."""
    gold = json.loads((GOLDEN / "cases_plan_mobility.json").read_text(encoding="utf-8"))
    got = {m["code"]: m for m in found}
    judged = [c for c in got if c not in gold["optional"]]
    wrong = sorted(c for c in judged if c not in gold["mentioned"])
    missed = sorted(c for c in gold["mentioned"] if c not in got)
    level_off = sorted(c for c in judged if c in gold["mentioned"] and got[c]["status_norm"] not in gold["mentioned"][c])
    return {"zugeordnet": len(judged), "falsch_zugeordnet": wrong, "fehlen": missed, "stufe_abweichend": level_off}


def mobilitaet(args: argparse.Namespace) -> int:
    store = CouncilStore(args.db)
    try:
        if args.pruefen:
            problems = mobility_check(store)
            print("\n".join(problems) or "✓ alle Zitate stehen wörtlich in ihren Berichten")
            return 1 if problems else 0
        measures = (plans.measures(MOBILITY) or {"measures": []})["measures"]
        reports = MOBILITY_REPORTS[::-1][:args.limit] if args.limit else MOBILITY_REPORTS[::-1]
        snapshots, spent = [], 0.0
        for number in reports:
            text, as_of = _report(store, number)
            found, cost = plan_judge.measure_status(measures, text)
            spent += cost
            print(f"{number} ({as_of}): {len(found)} Maßnahmen mit belegtem Stand · {cost:.4f} $")
            if args.golden and number == "26/0190":
                print("   Golden-Set:", json.dumps(mobility_golden(found), ensure_ascii=False))
            snapshots.append(mobility_snapshot(number, as_of, found, len(measures)))
        print(f"Kosten: {spent:.4f} $ für {len(reports)} Aufrufe"
              + (f" — hochgerechnet auf alle {len(MOBILITY_REPORTS)}: {spent / len(reports) * len(MOBILITY_REPORTS):.4f} $"
                 if args.limit else ""))
        if args.limit:
            return 0
        out = {"plan": MOBILITY, "snapshots": sorted(snapshots, key=lambda s: s["as_of"]), "notes": [
            {"text": "Die Stadt zählt den Stand beim Mobilitätsplan nicht aus. Was hier steht, hat ein Sprachmodell aus "
                     "den Sachstandsberichten herausgesucht; jedes Zitat steht wörtlich im Bericht.", "url": None}]}
        path = plan_state.STATUS_DIR / f"{MOBILITY}.json"
        path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"✓ {path.relative_to(WURZEL)}")
        return 0
    finally:
        store.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    sub = ap.add_subparsers(dest="task", required=True)
    for name, run in (("mobilitaet", mobilitaet),):
        p = sub.add_parser(name)
        p.add_argument("--limit", type=int, help="nur so viele Aufrufe, zum Kostenmessen; schreibt nichts")
        p.add_argument("--golden", action="store_true", help="gegen das Golden-Set auswerten")
        p.add_argument("--pruefen", action="store_true", help="ohne Modell: die Datei gegen den Bestand prüfen")
        p.add_argument("--db", type=Path, default=WURZEL / "data" / "council.sqlite")
        p.set_defaults(run=run)
    args = ap.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    raise SystemExit(main())
