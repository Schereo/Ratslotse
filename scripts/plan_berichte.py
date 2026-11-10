#!/usr/bin/env python3
"""Berichte zu den Plänen der Stadt: je Bericht ein Satz mit Zitat — und was im jüngsten neu ist.

Die Titel im Ratsinformationssystem sagen nichts („Klimaschutz-Aktivitäten 3/2026 - Bericht“).
Ein Sprachmodell liest je Bericht die Vorlage der Verwaltung und schlägt EINEN Satz vor, was
sie darin meldet. In die Datei (``council/plan_reports/<plan>.json``, eingecheckt) kommt nur,
was ``council/plan_judge.py`` ohne Modell belegen kann: Das Zitat steht wörtlich in der
Vorlage, jede Zahl des Satzes steht im Zitat. Eine zweite Lesung des Modells kann nur
streichen.

Wo die zwei jüngsten Berichte zur selben Reihe gehören (gleicher Titel bis auf Nummer und
Jahr), kommt dazu, was im jüngsten NEU ist: bis zu drei Sätze, deren Zitat im neuen Bericht
steht und im vorigen nicht.

Berichte ohne Vorlagentext (mündlich, nur als Anlage) bekommen keinen Satz — und die Seite
keinen Platzhalter.

    python scripts/plan_berichte.py --limit 20     # messen: 20 Berichte, nichts schreiben
    python scripts/plan_berichte.py                # alle, die noch keinen Satz haben
    python scripts/plan_berichte.py --nur klimaschutzplan_2035 --neu
    python scripts/plan_berichte.py --pruefen      # ohne Modell: Dateien gegen den Bestand

Kosten (gemessen, s. docs/plan-ziele-plaene.md): rund 0,0005 $ je Bericht.
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

from council import plan_judge, plan_pages, plan_state, plans  # noqa: E402
from council.store import CouncilStore  # noqa: E402

#: Darunter ist eine Vorlage ein Deckblatt („siehe Anlage“) und kein Bericht.
MIN_CHARS = 300


def _date(iso: str) -> str:
    return ".".join(reversed(iso.split("-")))


def report_sources(store: CouncilStore, plan: plans.Plan) -> list[dict]:
    """Die Berichte eines Plans mit Vorlagentext, ältester zuerst: ``{template, date, title, text}``."""
    out = []
    for station in plan_pages.timeline(store.plan_items(plan.key), plan)["stations"]:
        number = station["template_number"]
        if station["kind"] not in plan_pages.REPORT_ROLES or not number:
            continue
        row = store.get_vorlage_by_nr(number)
        text = (row or {}).get("raw_text") or ""
        if row and row.get("template_number") == number and len(text.strip()) >= MIN_CHARS:
            out.append({"template": number, "date": station["date_end"] or station["date"],
                        "title": station["title"], "text": text})
    return sorted(out, key=lambda r: (r["date"], r["template"]))


def series_pair(reports: list[dict]) -> tuple[dict, dict] | None:
    """Die zwei jüngsten Berichte, wenn sie zur selben Reihe gehören — sonst ``None``."""
    if len(reports) < 2 or not plan_judge.same_series(reports[-2]["title"], reports[-1]["title"]):
        return None
    return reports[-2], reports[-1]


def sentence(plan: plans.Plan, report: dict, model: str) -> tuple[dict | None, float, list[str]]:
    """Ein Bericht, zwei Modellaufrufe (vorschlagen, gegenlesen). Fasst weder Datenbank noch Netz an."""
    kept, notes, cost = plan_judge.report_sentence(plan.title, report["title"], _date(report["date"]),
                                                   report["text"], model)
    if kept:
        weak, second = plan_judge.unsupported(kept, model, feature="plan_reports")
        cost += second
        notes += [f"{kept[i]['text'][:70]} — Zitat trägt den Satz nicht ({why})" for i, why in sorted(weak.items())
                  if i < len(kept)]
        kept = [st for i, st in enumerate(kept) if i not in weak]
    if not kept:
        return None, cost, notes or ["kein Vorschlag"]
    # Der zweite Vorschlag bleibt in Reserve: Er kommt zum Zug, wenn ein früherer Bericht des Plans
    # schon dieselbe Stelle zitiert (``distinct``).
    return {"template": report["template"], "date": report["date"], **kept[0], "alternatives": kept[1:]}, cost, notes


def overlaps(quote: str, others: list[str]) -> bool:
    """Zitiert ``quote`` eine Stelle, die schon ein anderes Zitat trägt — gleich, oder eines im anderen?"""
    q = plan_judge.tight(quote)
    return any(q in o or o in q for o in (plan_judge.tight(x) for x in others))


def distinct(reports: list[dict]) -> list[dict]:
    """Je Plan zitiert jede Stelle nur EIN Bericht — der früheste. Wiederholt ein späterer Bericht einen
    Satz aus dem vorigen wörtlich, ist das dort keine Auskunft mehr: Dann zählt sein zweiter Vorschlag,
    und gibt es keinen, bleibt der Bericht ohne Satz."""
    seen: list[str] = []
    out = []
    for report in sorted(reports, key=lambda r: (r["date"], r["template"])):
        options = [{"text": report["text"], "quote": report["quote"]}, *report.get("alternatives", [])]
        chosen = next((o for o in options if not overlaps(o["quote"], seen)), None)
        if chosen is None:
            continue
        seen.append(chosen["quote"])
        out.append({"template": report["template"], "date": report["date"], **chosen})
    return out


def fresh_only(news_block: dict | None, reports: list[dict]) -> dict | None:
    """Was unter „Neu“ steht, wiederholt nicht den Satz, der schon am jüngsten Bericht steht."""
    if not news_block:
        return None
    taken = [r["quote"] for r in reports if r["template"] == news_block["to"]]
    items = [i for i in news_block["items"] if not overlaps(i["quote"], taken)]
    return {**news_block, "items": items} if items else None


def news(plan: plans.Plan, old: dict, new: dict, model: str) -> tuple[dict | None, float, list[str]]:
    kept, notes, cost = plan_judge.report_news(plan.title, {"date": _date(old["date"]), "text": old["text"]},
                                               {"date": _date(new["date"]), "text": new["text"]}, model)
    if kept:
        weak, second = plan_judge.unsupported(kept, model, feature="plan_reports")
        cost += second
        notes += [f"{kept[i]['text'][:70]} — Zitat trägt den Satz nicht ({why})" for i, why in sorted(weak.items())
                  if i < len(kept)]
        kept = [st for i, st in enumerate(kept) if i not in weak][:plan_judge.NEWS_MAX]
    if not kept:
        return None, cost, notes or ["nichts Neues belegt"]
    return {"from": old["template"], "from_date": old["date"], "to": new["template"], "to_date": new["date"],
            "items": kept}, cost, notes


def check(store: CouncilStore, key: str) -> list[str]:
    """Ohne Modell: Steht jedes Zitat wörtlich in seiner Vorlage, jede Zahl im Zitat — und das Neue
    im jüngsten Bericht, nicht im vorigen?"""
    data = plan_state.reports(key)
    if data is None:
        return []
    texts = {r["template"]: r["text"] for r in report_sources(store, plans.PLANS[key])}
    problems = []

    def held(entry: dict, template: str, what: str, absent: str | None = None) -> None:
        text = texts.get(template)
        if text is None:
            problems.append(f"{key}: {what} {template} — Bericht nicht mehr im Bestand")
            return
        kept, dropped = plan_judge.checked_statements([entry], text, plan_judge.REPORT_TEXT_MAX, absent_from=absent)
        problems.extend(f"{key}: {what} {template} — {why}" for why in dropped)

    for report in data["reports"]:
        held(report, report["template"], "Bericht")
    for n, report in enumerate(data["reports"]):
        if overlaps(report["quote"], [r["quote"] for r in data["reports"][:n]]):
            problems.append(f"{key}: Bericht {report['template']} zitiert eine Stelle, die schon ein früherer trägt")
    if fresh := data.get("news"):
        if fresh["from"] not in texts:
            problems.append(f"{key}: Neues — voriger Bericht {fresh['from']} nicht mehr im Bestand")
        for item in fresh["items"]:
            held(item, fresh["to"], "Neues in", absent=texts.get(fresh["from"]))
        if fresh_only(fresh, data["reports"]) != fresh:
            problems.append(f"{key}: „Neu“ wiederholt den Satz des jüngsten Berichts {fresh['to']}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--db", default=str(WURZEL / "data" / "council.sqlite"))
    ap.add_argument("--nur", help="Plan-Schlüssel, kommagetrennt")
    ap.add_argument("--neu", action="store_true", help="auch Berichte, die schon einen Satz haben")
    ap.add_argument("--limit", type=int, help="nur so viele Berichte lesen und NICHTS schreiben (Kosten messen)")
    ap.add_argument("--pruefen", action="store_true", help="ohne Modell: Dateien gegen den Bestand halten")
    ap.add_argument("--modell", default=plan_judge.MODEL)
    ap.add_argument("--parallel", type=int, default=4, help="Modellaufrufe nebeneinander (Vorgabe 4)")
    args = ap.parse_args(argv)
    store = CouncilStore(args.db)
    try:
        if args.pruefen:
            problems = [p for key in plan_state.report_keys() for p in check(store, key)]
            print("\n".join(problems) or f"✓ {len(plan_state.report_keys())} Dateien: jedes Zitat steht wörtlich in seiner Vorlage")
            return 1 if problems else 0
        wanted = args.nur.split(",") if args.nur else [k for k, p in plans.PLANS.items() if p.kind != "reference"]
        # Erst die Quellen aus der Datenbank, dann die Modellaufrufe nebeneinander.
        jobs: list[tuple[str, str, tuple]] = []
        before: dict[str, dict] = {}
        available: dict[str, list[dict]] = {}
        for key in wanted:
            plan = plans.PLANS[key]
            reports = report_sources(store, plan)
            if not reports:
                continue
            available[key] = reports
            old = plan_state.reports(key) or {}
            before[key] = old
            have = set() if args.neu else {r["template"] for r in old.get("reports", [])}
            jobs += [(key, "report", (plan, r)) for r in reports if r["template"] not in have]
            pair = series_pair(reports)
            stale = not old.get("news") or old["news"]["to"] != pair[1]["template"] if pair else False
            if pair and (args.neu or stale):
                jobs.append((key, "news", (plan, *pair)))
        if args.limit:
            jobs = [j for j in jobs if j[1] == "report"][:args.limit] + [j for j in jobs if j[1] == "news"][:2]
        print(f"{len(jobs)} Modellaufträge ({sum(1 for j in jobs if j[1] == 'report')} Berichte, "
              f"{sum(1 for j in jobs if j[1] == 'news')} Vergleiche)", flush=True)

        def run(job: tuple[str, str, tuple]) -> tuple[str, str, dict | None, float, list[str], str]:
            key, kind, payload = job
            label = payload[1]["template"] if kind == "report" else f"{payload[1]['template']}→{payload[2]['template']}"
            try:
                result, cost, notes = (sentence(payload[0], payload[1], args.modell) if kind == "report"
                                       else news(payload[0], payload[1], payload[2], args.modell))
                return key, kind, result, cost, notes, label
            except Exception as error:  # ein Bericht darf scheitern, ohne die anderen mitzunehmen
                return key, kind, None, 0.0, [f"FEHLER {type(error).__name__}: {error}"], label

        total = 0.0
        found: dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as pool:
            for key, kind, result, cost, notes, label in pool.map(run, jobs):
                total += cost
                mark = "✓" if result else "–"
                shown = (result["text"] if kind == "report" else f"{len(result['items'])} neu") if result else "; ".join(notes)[:150]
                print(f"  {mark} {key} {label}: {shown}", flush=True)
                if result:
                    slot = found.setdefault(key, {"reports": [], "news": None})
                    if kind == "report":
                        slot["reports"].append(result)
                    else:
                        slot["news"] = result
        print(f"Modellkosten: {total:.4f} $ für {len(jobs)} Aufträge"
              + (f" — je Auftrag {total / len(jobs):.5f} $" if jobs else ""))
        if args.limit:
            print("Messlauf: nichts geschrieben.")
            return 0
        plan_state.REPORTS_DIR.mkdir(exist_ok=True)
        for key, slot in sorted(found.items()):
            old = before.get(key) or {}
            current = {r["template"] for r in available[key]}
            merged = {r["template"]: r for r in old.get("reports", []) if r["template"] in current}
            merged.update({r["template"]: r for r in slot["reports"]})
            fresh = slot["news"] or old.get("news")
            pair = series_pair(available[key])
            if fresh and (not pair or fresh["to"] != pair[1]["template"]):
                fresh = None  # der Vergleich gehört zu einem Bericht, der nicht mehr der jüngste ist
            data = {"plan": key, "read_by": "model", "model": args.modell,
                    "generated": dt.date.today().isoformat(),
                    #: Von Hand gegen die Vorlage gelesen?
                    "reviewed": False,
                    "reports": distinct(list(merged.values()))}
            fresh = fresh_only(fresh, data["reports"])
            if fresh:
                data["news"] = fresh
            path = plan_state.REPORTS_DIR / f"{key}.json"
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            print(f"geschrieben: {path.relative_to(WURZEL)} ({len(data['reports'])} Berichte"
                  + (f", {len(fresh['items'])} neu" if fresh else "") + ")")
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    sys.exit(main())
