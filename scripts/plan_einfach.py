#!/usr/bin/env python3
"""Pläne der Stadt in einfacher Sprache — drei Sätze von Lotti und drei Fragen dazu.

Die Quelle sind NUR die belegten Kernpunkte (``council/plan_key_points/<plan>.json``),
nicht die Dokumente: Was dort nicht steht, kann hier nicht dazukommen. Ohne Modell wird
geprüft, dass keine Zahl auftaucht, die die Kernpunkte nicht nennen; eine zweite Lesung
des Modells streicht die Fassung, wenn ein Satz mehr sagt als die Punkte.

Die Datei (``council/plan_plain/<plan>.json``, eingecheckt) trägt einen Fingerabdruck
der Kernpunkte. Ändert sich ein Kernpunkt, passt die Fassung nicht mehr: Die Seite
zeigt sie dann nicht, und ``--pruefen`` meldet es.

    python scripts/plan_einfach.py --limit 5     # messen, nichts schreiben
    python scripts/plan_einfach.py               # alle, die fehlen oder veraltet sind
    python scripts/plan_einfach.py --nur schulverpflegung
    python scripts/plan_einfach.py --pruefen     # ohne Modell
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from council import plan_judge, plan_state, plans  # noqa: E402


def mode_of(plan: plans.Plan) -> str:
    return plan.adopted.mode if plan.adopted else "draft"


def stale(key: str) -> bool:
    """Fehlt die Fassung, oder gehört sie zu Kernpunkten, die es so nicht mehr gibt?"""
    data, points = plan_state.plain(key), plan_state.key_points(key)
    return bool(points) and (data is None or data["based_on"] != plan_judge.plain_basis(plan_judge.key_point_lines(points)))


def check(key: str) -> list[str]:
    """Ohne Modell: passt die Fassung zu den heutigen Kernpunkten, und nennt sie keine fremde Zahl?"""
    data, points = plan_state.plain(key), plan_state.key_points(key)
    if data is None:
        return []
    if points is None:
        return [f"{key}: einfache Fassung ohne Kernpunkte — Datei löschen"]
    lines = plan_judge.key_point_lines(points)
    problems = [f"{key}: {p}" for p in plan_judge.check_plain(data["plain"], data["questions"], plans.PLANS[key].title, lines)]
    if data["based_on"] != plan_judge.plain_basis(lines):
        problems.append(f"{key}: Kernpunkte haben sich geändert — python scripts/plan_einfach.py --nur {key}")
    return problems


def questions_only(args: argparse.Namespace) -> int:
    """Die drei Fragen je Plan neu schreiben; die einfache Fassung und ihr Fingerabdruck bleiben."""
    wanted = args.nur.split(",") if args.nur else plan_state.plain_keys()
    if args.limit:
        wanted = wanted[:args.limit]

    def run(key: str) -> tuple[str, list[str] | None, list[str], float]:
        data, points = plan_state.plain(key), plan_state.key_points(key)
        if not data or not points:
            return key, None, ["keine einfache Fassung"], 0.0
        try:
            return (key, *plan_judge.plan_questions(plans.PLANS[key].title, data["plain"],
                                                    plan_judge.key_point_lines(points), args.modell))
        except Exception as error:
            return key, None, [f"FEHLER {type(error).__name__}: {error}"], 0.0

    total = 0.0
    with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as pool:
        for key, questions, notes, cost in pool.map(run, wanted):
            total += cost
            if questions is None:
                print(f"  – {key}: {'; '.join(notes)[:200]}", flush=True)
                continue
            print(f"  ✓ {key}: {' | '.join(questions)}", flush=True)
            if not args.limit:
                data = {**(plan_state.plain(key) or {}), "questions": questions, "reviewed": False}
                (plan_state.PLAIN_DIR / f"{key}.json").write_text(
                    json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Modellkosten: {total:.4f} $ für {len(wanted)} Pläne" + (" — Messlauf, nichts geschrieben." if args.limit else ""))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--nur", help="Plan-Schlüssel, kommagetrennt (schreibt auch über vorhandene Dateien)")
    ap.add_argument("--limit", type=int, help="nur so viele Pläne und NICHTS schreiben (Kosten messen)")
    ap.add_argument("--pruefen", action="store_true", help="ohne Modell: Dateien gegen die Kernpunkte halten")
    ap.add_argument("--fragen", action="store_true", help="nur die drei Fragen neu, die einfache Fassung bleibt")
    ap.add_argument("--modell", default=plan_judge.MODEL)
    ap.add_argument("--parallel", type=int, default=4)
    args = ap.parse_args(argv)
    if args.pruefen:
        problems = [p for key in plan_state.plain_keys() for p in check(key)]
        missing = [k for k in plan_state.key_point_keys() if plan_state.plain(k) is None]
        print("\n".join(problems) or f"✓ {len(plan_state.plain_keys())} Dateien passen zu ihren Kernpunkten")
        if missing:
            print(f"Hinweis: ohne einfache Fassung: {', '.join(missing)}")
        return 1 if problems else 0
    if args.fragen:
        return questions_only(args)
    wanted = args.nur.split(",") if args.nur else [k for k in plan_state.key_point_keys() if stale(k)]
    if args.limit:
        wanted = wanted[:args.limit]

    def run(key: str) -> tuple[str, dict | None, list[str], float]:
        points = plan_state.key_points(key)
        if not points:
            return key, None, ["keine Kernpunkte"], 0.0
        lines = plan_judge.key_point_lines(points)
        try:
            result, notes, cost = plan_judge.plain_text(plans.PLANS[key].title, mode_of(plans.PLANS[key]), lines, args.modell)
        except Exception as error:  # ein Plan darf scheitern, ohne die anderen mitzunehmen
            return key, None, [f"FEHLER {type(error).__name__}: {error}"], 0.0
        if result is None:
            return key, None, notes, cost
        return key, {"plan": key, "read_by": "model", "model": args.modell,
                     "generated": dt.date.today().isoformat(),
                     #: Von Hand gegen die Kernpunkte gelesen?
                     "reviewed": False,
                     "based_on": plan_judge.plain_basis(lines), **result}, [], cost

    total = 0.0
    plan_state.PLAIN_DIR.mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as pool:
        for key, data, notes, cost in pool.map(run, wanted):
            total += cost
            if data is None:
                print(f"  – {key}: {'; '.join(notes)[:200]}", flush=True)
                continue
            print(f"  ✓ {key}: {data['plain'][0]}", flush=True)
            if not args.limit:
                (plan_state.PLAIN_DIR / f"{key}.json").write_text(
                    json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Modellkosten: {total:.4f} $ für {len(wanted)} Pläne" + (" — Messlauf, nichts geschrieben." if args.limit else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
