#!/usr/bin/env python3
"""Was im Plan steht: Zweck und Kernpunkte je Plan (``council/plan_key_points/<plan>.json``).

Die Planseite zeigte bis 11/2026 Laufzeit, Berichte und Beschlüsse — aber nicht,
was der Plan festlegt. Hier entsteht dafür je Plan ein Satz zum Zweck und drei
bis sechs Kernpunkte, jeder mit Beleg.

**Das Modell sucht und entwirft, es entscheidet nicht.** Ausgeliefert wird nur,
was ``council/plan_judge.py`` ohne Modell belegen kann: Das Zitat steht wörtlich
in der genannten Quelle (bei Anlagen: auf der genannten Seite), und jede Zahl
des Satzes steht im Zitat. Die Dateien sind eingecheckt und im Pull Request
lesbar; ``--pruefen`` hält sie später ohne Modell gegen die Quellen.

Quellen je Plan, älteste zuerst: die Beschlüsse aus dem Register
(``council/plans.py``) mit ihrem Beschlusstext und dem Text der Vorlage, dazu
das Plandokument selbst (``DOCUMENTS``, von Hand ausgewählt — die Anlagen einer
Vorlage sind auch Stellungnahmen, Karten und Anträge). Spätere Beschlüsse gehen
vor: Wo einer einen Punkt geändert hat, steht der heute geltende Stand mit
diesem Beschluss als Beleg.

Kosten: jeder Lauf nennt, was er gekostet hat. Erst mit ``--nur`` an fünf Plänen
messen und hochrechnen; ab etwa 1 $ je Lauf erst fragen.

    python scripts/plan_kernpunkte.py --nur schulverpflegung,eek     # diese Pläne (neu) schreiben
    python scripts/plan_kernpunkte.py                                # alle, die noch keine Datei haben
    python scripts/plan_kernpunkte.py --pruefen                      # ohne Modell: Dateien gegen die Quellen
    python scripts/plan_kernpunkte.py --quellen schulverpflegung     # zeigen, was das Modell zu lesen bekäme
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from council import plan_judge, plan_state, plans  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from scripts.plan_massnahmen import _seiten  # noqa: E402

#: Das Plandokument je Plan: (Dokument-Id im Ratsinformationssystem, Vorlage, Name für Menschen).
#: Von Hand ausgewählt am 10.11.2026 aus den Anlagen der Register-Vorlagen. Wo zwei stehen, ist das
#: zweite eine Ergänzung, die der Rat mitbeschlossen hat (Umsetzungsplan, Kurzfassung).
DOCUMENTS: dict[str, tuple[tuple[int, str, str], ...]] = {
    "klimaschutzplan_2035": ((255734, "22/0910", "Klimaschutzplan Oldenburg 2035, Erläuterungen zur Machbarkeit"),),
    "waermeplan": ((306748, "26/0236", "Abschlussbericht Kommunale Wärmeplanung"),),
    "mobilitaetsplan_2030": ((263729, "23/0211/2", "Mobilitätsplan Oldenburg 2030"),
                             (275932, "24/0216", "Ergebnis der Maßnahmenpriorisierung")),
    "aktionsplan_gewalt_2020": ((223427, "20/0564", "Kommunaler Aktionsplan gegen Gewalt an Frauen und Häusliche Gewalt"),),
    "aktionsplan_gewalt_2026": ((314635, "26/0681/1", "Evaluation und Fortschreibung des Aktionsplans"),),
    "ernaehrungsstrategie": ((286179, "24/0810", "Ernährungsstrategie (Entwurf)"),),
    "laermaktionsplan": ((280381, "24/0293/1", "Fortschreibung des Lärmaktionsplans (2. Entwurf, Mai 2024)"),),
    "digitalisierungsstrategie": ((270752, "23/0708", "Digitalisierungsstrategie"),
                                  (284226, "24/0574", "Umsetzungsplan Digitalisierung 2024")),
    "kita_ausbau": ((251642, "22/0620", "Konzept zum Ausbau der Kindertagesbetreuung, 5. Fortschreibung"),),
    "agenda_2025_alter": ((293527, "25/0403", "Agenda 2025 „Selbstbestimmt und mittendrin!“"),),
    "kinder_jugendbeteiligung": ((314712, "26/0710/1", "Handlungskonzept Kinder- und Jugendbeteiligung, Anlagen"),),
    "thg_neutrale_verwaltung": ((301128, "25/0896", "Konzept für eine treibhausgasneutrale Verwaltung"),),
    "isek_2035": ((279907, "24/0425", "Zukunft 2050 (Entwurf)"),),
    "masterplan_stadtgruen": ((251236, "22/0642", "Masterplan Stadtgrün, Textteil"),),
    "baumstrategie": ((293180, "25/0388", "Baumerhalt- und Entwicklungsstrategie"),
                      (293203, "25/0388", "Instrumente der Strategie, Zusammenfassung")),
    "spielleitplanung": ((306888, "26/0255", "Spielleitplanung, Gesamttext (Entwurf)"),),
    "eek": ((285989, "24/0717/1", "Einzelhandelsentwicklungskonzept, Endbericht"),),
    "nachhaltigkeitsleitbild": ((248420, "22/0240/1", "Nachhaltigkeitsleitbild, Vorschlag der Verwaltung"),
                                (248419, "22/0240/1", "Umsetzungsplanung zum Nachhaltigkeitsleitbild")),
    "integrationskonzept_2020": ((213530, "19/0697/2", "Integrationskonzept, Fassung für den Ausschuss"),),
    "integrationskonzept_2026": ((304665, "26/0191", "Integrationskonzept 2026"),),
    "wohnungslosen_suchthilfe": ((200992, "19/0239", "Gesamtkonzept niedrigschwellige Wohnungslosen- und Suchthilfe"),),
    "orte_fuer_alle": ((236979, "21/0478/1", "Gesamtkonzept „Orte für Alle“"),),
    "inklusion_stadt_fuer_alle": ((259558, "23/0189", "Wertorientierte Zielsetzungen des Aktionsplans Inklusion"),),
    "demografiestrategie": ((218513, "20/0371/1", "Demografiestrategie"),),
    "gleichstellungsplan_2024": ((278615, "24/0362", "Gleichstellungsplan 2024–2026"),),
    "gleichstellungsplan_2021": ((236435, "21/0399", "Gleichstellungsplan 2021–2023"),),
    "gleichstellungsplan_2018": ((189127, "18/0406", "Gleichstellungsplan 2018–2020"),),
    "abfallwirtschaftskonzept": ((239675, "21/0668", "Abfallwirtschaftskonzept, Teil 1"),
                                 (239676, "21/0668", "Abfallwirtschaftskonzept, Teil 2"),
                                 (239677, "21/0668", "Abfallwirtschaftskonzept, Teil 3")),
    "brandschutzbedarfsplan": ((300074, "25/0833", "Brandschutzbedarfsplan, Managementfassung"),),
    "schulverpflegung": ((210853, "19/0943", "Rahmenkonzept „Schulverpflegung in Oldenburg“"),),
    "luftreinhalteplan": ((187676, "18/0264", "Luftreinhalteplan, Entwurf der Fortschreibung (04/2018)"),),
    "wohnraumversorgungskonzept": ((254112, "22/0755", "Wohnraumversorgungskonzept"),),
    "schulentwicklungsplan_2018": ((190469, "18/0420/1", "Schulentwicklungsplan, Kurzfassung"),),
    "rad_fussverkehrsprogramm": ((184457, "18/0056", "Rad- und Fußverkehrsprogramm 2018, Maßnahmenliste"),),
    "aktionsplan_energie": ((191988, "18/0516", "Aktionsplan Energie 2019"),
                            (209182, "19/0836", "Aktionsplan Energie 2020")),
    "baederstrategie": ((210876, "19/0832/1", "Sport- und Gesundheitsbad am Flötenteich, Präsentation"),),
}

#: Pläne ohne Block — kein Platzhalter auf der Seite. Der Grund steht hier, damit niemand sie für
#: vergessen hält; ``tests/test_plaene_kernpunkte.py`` verlangt für jeden Plan Datei ODER Grund.
WITHOUT_BLOCK: dict[str, str] = {
    "kai_2015": "2015 beschlossen, vor dem Bestand des Ratsinformationssystems; keine Vorlage",
    "sportentwicklungsplan_2009": "2009 beschlossen, vor dem Bestand; keine Vorlage",
    "step2025": "2014 beschlossen, vor dem Bestand; im Bestand liegt nur die Evaluation (21/0217)",
    "klimaanpassungskonzept": "in Arbeit; es gibt den Auftrag (24/0830), aber noch keinen Plantext",
    # Zu dünn belegt: Der Lauf vom 10.11.2026 fand weniger als drei Kernpunkte, die sich wörtlich belegen lassen.
    "abfallwirtschaftskonzept": "die drei Teile des Konzepts sind Scans ohne Text; die Vorlage (21/0668) allein trägt "
                                "keine drei belegten Kernpunkte",
    "nahverkehrsplan": "Plan des Zweckverbands; im Bestand nur die Vorlage zur Teilfortschreibung (26/0223), ohne Plantext",
    "kitaverpflegung": "das Rahmenkonzept selbst hängt der Vorlage (21/0459) nicht an; die Vorlage allein ist zu knapp",
    "innenstadtstrategie": "im Bestand nur die Kenntnisnahme der Grundsatzvereinbarung (20/0820), nicht die Strategie selbst",
    # Bewusst ohne Block: Die Sätze wären belegt, aber sie täuschten einen geltenden Plan vor.
    "luftreinhalteplan": "beschlossen wurden 2018 Maßnahmen für einen Entwurf (Umweltzone, Busse); ob die Fortschreibung "
                         "je in Kraft trat, ist im Bestand nicht festzustellen",
}

#: Längere Anlagen liest das Modell nur bis hierhin (Seiten). Ziele und Leitlinien stehen vorn.
MAX_PAGES = 260


def _date(iso: str) -> str:
    parts = iso.split("-")
    return ".".join(reversed(parts)) if len(parts) == 3 else iso


def mode_of(plan: plans.Plan) -> str:
    return plan.adopted.mode if plan.adopted else "draft"


def _documents(plan: plans.Plan, template: str | None, used: set[int], pdf: bool) -> list[dict]:
    out = []
    for document_id, number, label in DOCUMENTS.get(plan.key, ()):
        if document_id in used or (template is not None and number != template):
            continue
        used.add(document_id)
        entry = {"kind": "attachment", "template": number, "document_id": document_id, "label": label,
                 "heading": f"Anlage zu Vorlage {number}: {label}"}
        if pdf:
            pages = _seiten(document_id)[:MAX_PAGES]
            if not any(p.strip() for p in pages):  # Scan ohne Textebene
                continue
            entry["pages"] = pages
        out.append(entry)
    return out


def sources(store: CouncilStore, plan: plans.Plan, pdf: bool = True) -> list[dict]:
    """Was das Modell zu lesen bekommt und wogegen später geprüft wird — älteste Quelle zuerst.

    ``pdf=False`` lässt die Anlagen ohne Text (für eine Prüfung, die nur Vorlagen und Beschlüsse hält)."""
    out: list[dict] = []
    used: set[int] = set()
    decisions = sorted([d for d in ((plan.adopted,) if plan.adopted else ()) + plan.decisions if d.template],
                       key=lambda d: d.date)
    for d in decisions:
        assert d.template
        word = "zur Kenntnis genommen" if d.mode == "noted" else "beschlossen"
        ref = store.plan_decision_at(d.template, d.date, d.committee)
        decision = store.get_decision(ref["id"]) if ref else None
        if decision and (decision.get("official_text") or "").strip():
            out.append({"kind": "decision", "template": d.template, "date": d.date, "committee": d.committee,
                        "heading": f"Beschlusstext · {d.committee}, {_date(d.date)} · Vorlage {d.template}"
                                   f"{' · ' + d.label if d.label else ''} · Ergebnis: {word}",
                        "text": decision["official_text"]})
        row = store.get_vorlage_by_nr(d.template)
        if row and (row.get("raw_text") or "").strip() and row.get("template_number") == d.template:
            out.append({"kind": "template", "template": d.template,
                        "heading": f"Vorlage {d.template} der Verwaltung zum Beschluss vom {_date(d.date)} "
                                   f"({word}): {row.get('title') or ''}",
                        "text": row["raw_text"]})
        out.extend(_documents(plan, d.template, used, pdf))
    if plan.adopted is None and plan.commissioned:
        row = store.get_vorlage_by_nr(plan.commissioned)
        if row and (row.get("raw_text") or "").strip():
            out.append({"kind": "template", "template": plan.commissioned,
                        "heading": f"Vorlage {plan.commissioned} der Verwaltung (Entwurf, nicht beschlossen): "
                                   f"{row.get('title') or ''}",
                        "text": row["raw_text"]})
    out.extend(_documents(plan, None, used, pdf))
    counters: dict[str, int] = {}
    for s in out:
        letter = {"decision": "B", "template": "V", "attachment": "A"}[s["kind"]]
        counters[letter] = counters.get(letter, 0) + 1
        s["id"] = f"{letter}{counters[letter]}"
    return out


def _ref(source: dict, page: int | None) -> dict:
    """Der Verweis, wie er in der Datei steht — ohne Datenbank-Ids, die je Umgebung andere sind."""
    if source["kind"] == "decision":
        return {"kind": "decision", "template": source["template"], "date": source["date"],
                "committee": source["committee"]}
    if source["kind"] == "template":
        return {"kind": "template", "template": source["template"]}
    return {"kind": "attachment", "template": source["template"], "document_id": source["document_id"],
            "label": source["label"], "page": page}


def _same(ref: dict, source: dict) -> bool:
    return (ref["kind"] == source["kind"] and ref["template"] == source["template"]
            and ref.get("document_id") == source.get("document_id")
            and ref.get("date") == source.get("date") and ref.get("committee") == source.get("committee"))


def build(key: str, given: list[dict], model: str) -> tuple[dict | None, float, list[str]]:
    """Zwei Modellaufrufe für einen Plan (entwerfen, gegenlesen) auf den Quellen aus :func:`sources`.
    Zurück: die Datei (oder ``None``), die Kosten, was fiel. Fasst weder Datenbank noch Netz der
    Stadt an — darf deshalb neben anderen laufen."""
    plan = plans.PLANS[key]
    if not given:
        return None, 0.0, ["keine Quelle mit Text"]
    found, cost = plan_judge.key_points(plan.title, mode_of(plan), given, model)
    by_id = {s["id"]: s for s in given}
    notes = list(found["dropped"])
    # Zweite Lesung: Sie kann nur streichen. Es bleiben der erste Zweck-Satz und die ersten Punkte, die sie trägt.
    statements = found["purposes"] + found["points"]
    weak: dict[int, str] = {}
    if statements:
        weak, second = plan_judge.unsupported(statements, model)
        cost += second
        for i, why in sorted(weak.items()):
            if 0 <= i < len(statements):
                notes.append(f"{statements[i]['text'][:70]} — Zitat trägt den Satz nicht ({why}) · "
                             f"„{statements[i]['quote'][:90]}“")
    strong = [st for i, st in enumerate(statements) if i not in weak]
    purpose = next((st for st in strong if "kind" not in st), None)
    points = [st for st in strong if "kind" in st][:plan_judge.POINTS_MAX]
    if purpose is None or len(points) < plan_judge.POINTS_MIN:
        notes.append("Zweck nicht belegt" if purpose is None else f"nur {len(points)} belegte Kernpunkte")
        return None, cost, notes
    later = {d.template for d in plan.decisions if d.template and plan.adopted and d.date > plan.adopted.date}
    if later and not any(by_id[p["source"]]["template"] in later for p in points):
        notes.append(f"ACHTUNG: kein Kernpunkt nennt einen späteren Beschluss ({', '.join(sorted(later))}) — von Hand prüfen")
    data = {
        "plan": key,
        "read_by": "model",
        "model": model,
        "generated": dt.date.today().isoformat(),
        #: Von Hand gegen die Quelle gelesen (Stichprobe im Pull Request)?
        "reviewed": False,
        "purpose": {"text": purpose["text"], "quote": purpose["quote"],
                    "source": _ref(by_id[purpose["source"]], purpose["page"])},
        "points": [{"text": p["text"], "kind": p["kind"], "quote": p["quote"],
                    "source": _ref(by_id[p["source"]], p["page"])} for p in points],
    }
    carry_extras(data, plan_state.key_points(key))
    return data, cost, notes


def carry_extras(data: dict, previous: dict | None) -> None:
    """Was von Hand an einem Kernpunkt hängt (``figure``: die Zahl als Kachel, ``due``: der Termin fürs
    Zeitband), überlebt einen neuen Lauf — aber nur an einem Punkt mit DEMSELBEN Zitat. Ändert das Modell
    die Stelle, ist die Zahl nicht mehr gegen sie geprüft und fällt weg."""
    kept = {plan_judge.tight(p["quote"]): p for p in (previous or {}).get("points", [])}
    for point in data["points"]:
        old = kept.get(plan_judge.tight(point["quote"]))
        for extra in ("figure", "due"):
            if old and extra in old:
                point[extra] = old[extra]


def check(store: CouncilStore, key: str) -> list[str]:
    """Ohne Modell: Steht jedes Zitat der Datei wörtlich in seiner Quelle, jede Zahl im Zitat?"""
    data = plan_state.key_points(key)
    if data is None:
        return []
    given = sources(store, plans.PLANS[key])
    problems = []
    for entry in [data["purpose"], *data["points"]]:
        source = next((s for s in given if _same(entry["source"], s)), None)
        if source is None:
            problems.append(f"{key}: Quelle nicht mehr im Bestand — {entry['source']}")
            continue
        found, page = plan_judge.locate(entry["quote"], source, entry["source"].get("page"))
        if not found:
            problems.append(f"{key}: Zitat steht nicht in {entry['source']['template']}: {entry['quote'][:60]}…")
        elif page != entry["source"].get("page"):
            problems.append(f"{key}: Zitat steht auf Seite {page}, nicht {entry['source'].get('page')}: {entry['quote'][:50]}…")
        missing = sorted(plan_judge.numbers(entry["text"]) - plan_judge.numbers(entry["quote"]))
        if missing:
            problems.append(f"{key}: Zahl ohne Beleg ({', '.join(missing)}): {entry['text'][:60]}…")
        problems += [f"{key}: {problem}: {entry['text'][:60]}…" for problem in plan_judge.check_extras(entry)]
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--db", default=str(WURZEL / "data" / "council.sqlite"))
    ap.add_argument("--nur", help="Plan-Schlüssel, kommagetrennt (schreibt auch über vorhandene Dateien)")
    ap.add_argument("--pruefen", action="store_true", help="ohne Modell: Dateien gegen die Quellen halten")
    ap.add_argument("--quellen", help="die Quellen eines Plans zeigen (Kennung, Art, Umfang)")
    ap.add_argument("--modell", default=plan_judge.MODEL)
    ap.add_argument("--parallel", type=int, default=4, help="Modellaufrufe nebeneinander (Vorgabe 4)")
    args = ap.parse_args(argv)
    store = CouncilStore(args.db)
    try:
        if args.quellen:
            for s in sources(store, plans.PLANS[args.quellen]):
                size = sum(len(p) for p in s["pages"]) if "pages" in s else len(s["text"])
                print(f"[{s['id']}] {s['heading'][:110]} · {size} Zeichen"
                      + (f" · {len(s['pages'])} Seiten" if "pages" in s else ""))
            return 0
        if args.pruefen:
            problems = [p for key in plan_state.key_point_keys() for p in check(store, key)]
            print("\n".join(problems) or f"✓ {len(plan_state.key_point_keys())} Dateien: jedes Zitat steht wörtlich in seiner Quelle")
            return 1 if problems else 0
        wanted = args.nur.split(",") if args.nur else [
            k for k in plans.PLANS if k not in WITHOUT_BLOCK and plan_state.key_points(k) is None]
        # Erst die Quellen, eine nach der anderen (Datenbank; PDF-Dateien höflich mit Abstand) —
        # dann die Modellaufrufe nebeneinander: Sie sind das Langsame, und sie treffen die Stadt nicht.
        prepared = [(key, sources(store, plans.PLANS[key])) for key in wanted]
        print(f"{len(prepared)} Pläne, Quellen gelesen", flush=True)

        def run(item: tuple[str, list[dict]]) -> tuple[str, dict | None, float, list[str]]:
            try:
                return (item[0], *build(item[0], item[1], args.modell))
            except Exception as error:  # ein Plan darf scheitern, ohne die anderen mitzunehmen
                return item[0], None, 0.0, [f"FEHLER {type(error).__name__}: {error}"]

        spent = 0.0
        with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as pool:
            results = list(pool.map(run, prepared))
        for key, data, cost, notes in results:
            spent += cost
            path = plan_state.KEY_POINTS_DIR / f"{key}.json"
            if data is None:
                path.unlink(missing_ok=True)  # eine Datei aus einem früheren Lauf wäre jetzt unbelegt
                print(f"✗ {key}: keine Datei · {cost:.4f} $")
            else:
                path.parent.mkdir(exist_ok=True)
                path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
                print(f"✓ {key}: Zweck und {len(data['points'])} Kernpunkte · {cost:.4f} $")
            for note in notes:
                print(f"    gefallen — {note}")
        print(f"Kosten: {spent:.4f} $ für {len(wanted)} Aufrufe")
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
