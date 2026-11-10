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
    python scripts/plan_modell.py nennungen --golden              # Phase 4 Teil 2 gegen das Golden-Set (40 Paare)
    python scripts/plan_modell.py nennungen                       # alle Paare, Dateien schreiben
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from council import open_mandates, plan_judge, plan_state, plans  # noqa: E402
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


# ── Phase 4, Teil 2: Vorlagen, die einen Plan beim Namen nennen ────────────

#: Antrag oder Anfrage aus dem Rat: „(Fraktion … vom 05.03.2025)“, „(beratendes Mitglied …)“.
MOTION_TITLE = re.compile(r"\((?:[^)]*\b(?:Fraktion|Fraktionen|Gruppe|Ratsfrau|Ratsherr)\b|beratendes Mitglied|Antrag der)[^)]*\)?", re.I)


def link_candidates(store: CouncilStore) -> dict[str, list[dict]]:
    """Je Plan die Vorlagen mit Beschluss, die ihn beim Namen nennen — ohne die Vorlagen des Plans
    selbst und ohne das, was schon als Bericht oder Beschluss zum Plan gehört. Je Vorlagenstamm die
    jüngste Fassung.

    Zwei Arten von Vorlagen können einen Plan nicht umsetzen und werden gar nicht erst gefragt
    (beide fielen bei der Durchsicht aller Treffer von Hand als die einzigen Fehler auf): der
    Sachstandsbericht IRGENDEINES Plans — er beschreibt Umsetzung, ist aber keine — und Anträge
    oder Anfragen aus dem Rat."""
    by_stem = store.plan_decisions_by_stem()
    items = store.plan_items()
    known = {(i["plan_key"], plans.template_stem(i["template_number"])) for i in items if i["template_number"]}
    reports = {plans.template_stem(i["template_number"]) for i in items
               if i["template_number"] and i["role"] in plan_state.REPORT_ROLES}
    own = {key: {plans.template_stem(n) for n in plans.all_templates(plans.PLANS[key])} for key in plan_judge.NAME_PATTERNS}
    found: dict[str, dict[str, dict]] = {key: {} for key in plan_judge.NAME_PATTERNS}
    for number, title, text in sorted(store.plan_templates_with_text()):
        stem = plans.template_stem(number)
        if stem not in by_stem or stem in reports or MOTION_TITLE.search(title):
            continue
        for key, pattern in plan_judge.NAME_PATTERNS.items():
            if stem in own[key] or (key, stem) in known:
                continue
            hits = plan_judge.passages(text, pattern)
            if hits:
                found[key][stem] = {"template": number, "title": plan_judge.squash(title), "passages": hits}
    return {key: list(by.values()) for key, by in found.items()}


def links_check(store: CouncilStore) -> list[str]:
    """Ohne Modell: Steht jedes Zitat der Dateien wörtlich in seiner Vorlage?"""
    problems = []
    for key in plan_state.judged_keys():
        for link in plan_state.judged_links(key):
            row = store.get_vorlage_by_nr(link["template"])
            if not row or link["quote"] not in plan_judge.squash(row.get("raw_text") or ""):
                problems.append(f"{key}: Zitat nicht in {link['template']}")
    return problems


def nennungen(args: argparse.Namespace) -> int:
    store = CouncilStore(args.db)
    try:
        if args.pruefen:
            problems = links_check(store)
            print("\n".join(problems) or "✓ alle Zitate stehen wörtlich in ihren Vorlagen")
            return 1 if problems else 0
        candidates = link_candidates(store)
        total = sum(len(v) for v in candidates.values())
        gold = {}
        if args.golden:
            cases = json.loads((GOLDEN / "cases_plan_links.json").read_text(encoding="utf-8"))["cases"]
            gold = {(c["plan"], plans.template_stem(c["template"])): c["accept"] for c in cases}
            candidates = {key: [c for c in items if (key, plans.template_stem(c["template"])) in gold]
                          for key, items in candidates.items()}
        elif args.limit:
            rest = args.limit
            for key in candidates:
                candidates[key], rest = candidates[key][:rest], max(0, rest - len(candidates[key]))
        judged, spent, tally = {}, 0.0, {}
        for key, items in candidates.items():
            if not items:
                continue
            results, cost = plan_judge.judge_links(key, items)
            spent += cost
            judged[key] = results
            for r in results:
                tally[r["relation"]] = tally.get(r["relation"], 0) + 1
        n = sum(len(v) for v in judged.values())
        print(f"{n} von {total} Paaren beurteilt: {tally} · {spent:.4f} $"
              + (f" — hochgerechnet auf alle: {spent / n * total:.4f} $" if n and n < total else ""))
        if args.golden:
            wrong, said, said_ok = [], 0, 0
            for key, results in judged.items():
                for r in results:
                    accept = gold[(key, plans.template_stem(r["template"]))]
                    if r["relation"] == "implements":
                        said += 1
                        said_ok += "implements" in accept
                    if r["relation"] not in accept:
                        wrong.append(f"{key} {r['template']}: {r['relation']} statt {accept}")
            print(f"Golden-Set: {n - len(wrong)} von {n} vertretbar · „dient der Umsetzung“: {said_ok} von {said} richtig")
            print("\n".join("   " + w for w in wrong))
            return 0
        if args.limit:
            return 0
        plan_state.LINKS_DIR.mkdir(exist_ok=True)
        for key, results in judged.items():
            links = [{"template": r["template"], "relation": "implements", "quote": r["quote"]}
                     for r in results if r["relation"] == "implements"]
            path = plan_state.LINKS_DIR / f"{key}.json"
            if links:
                path.write_text(json.dumps({"plan": key, "judged": len(results), "links": links},
                                           ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
                print(f"✓ {key}: {len(links)} von {len(results)} → {path.relative_to(WURZEL)}")
            elif path.exists():
                path.unlink()
        return 0
    finally:
        store.close()


# ── § 3.5, Art 2: Ratsaufträge ohne gefundene Folge ────────────────────────


def auftraege(args: argparse.Namespace) -> int:
    """Zwei Modellschritte: Art des Auftrags (soll dem Rat etwas vorgelegt werden?), dann je
    Berichtsauftrag die Frage, ob ein späterer Tagesordnungspunkt die Folge ist."""
    store = CouncilStore(args.db)
    try:
        found = open_mandates.mandates(store.mandate_decisions())
        agenda = store.agenda_titles()
        today = max(a["date"] for a in agenda)
        gold = json.loads((GOLDEN / "cases_plan_mandates.json").read_text(encoding="utf-8"))
        if args.golden:
            found = [m for m in found if m["stem"] in gold["types"] or m["stem"] in gold["followed"]]
        elif args.limit:
            found = found[:args.limit]
        kinds, spent = plan_judge.classify_mandates(found)
        kind_of = {k["stem"]: k for k in kinds}
        wrong_type = sorted(s for s, accept in gold["types"].items() if s in kind_of and kind_of[s]["type"] not in accept)
        typed = sum(1 for s in gold["types"] if s in kind_of)
        report = [m for m in found if kind_of[m["stem"]]["type"] == "report_back"]
        due = [m for m in report if open_mandates.old_enough(m, today)]
        still_open = []
        for m in due:
            candidates = open_mandates.follow_up_candidates(m, kind_of[m["stem"]]["subject"], agenda)
            index, cost = plan_judge.find_follow_up(m, candidates)
            spent += cost
            if index is None:
                still_open.append({**m, "subject": kind_of[m["stem"]]["subject"], "candidates": len(candidates)})
        print(f"{len(found)} Aufträge · {len(report)} Berichtsaufträge · {len(due)} älter als sechs Monate · "
              f"{len(still_open)} ohne gefundene Folge · {spent:.4f} $")
        print(f"Golden-Set: Art des Auftrags {typed - len(wrong_type)} von {typed} vertretbar {wrong_type or ''}")
        false_open = sorted(m["stem"] for m in still_open if m["stem"] in gold["followed"])
        print(f"Golden-Set: nachweislich fortgeführte Aufträge unter „ohne Folge“: {false_open or 'keine'}")
        if args.out:
            Path(args.out).write_text(json.dumps(still_open, ensure_ascii=False, indent=1), encoding="utf-8")
        return 0
    finally:
        store.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    sub = ap.add_subparsers(dest="task", required=True)
    for name, run in (("mobilitaet", mobilitaet), ("nennungen", nennungen), ("auftraege", auftraege)):
        p = sub.add_parser(name)
        p.add_argument("--limit", type=int, help="nur so viele Aufrufe, zum Kostenmessen; schreibt nichts")
        p.add_argument("--golden", action="store_true", help="gegen das Golden-Set auswerten")
        p.add_argument("--pruefen", action="store_true", help="ohne Modell: die Datei gegen den Bestand prüfen")
        p.add_argument("--db", type=Path, default=WURZEL / "data" / "council.sqlite")
        p.add_argument("--out", help="Ergebnis zusätzlich als JSON hierhin (zum Durchsehen von Hand)")
        p.set_defaults(run=run)
    args = ap.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    raise SystemExit(main())
