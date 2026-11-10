#!/usr/bin/env python3
"""Haushalt zum Plan — nur Posten, deren eigener Text den Plan beim Namen nennt.

Ein Plan hat im Haushalt keine eigene Zeile. Was sich belegen lässt, ist enger: ein Produkt,
das den Plan als Rechtsgrundlage nennt; eine Investition, deren Bezeichnung ihn nennt; eine
Änderung, deren Begründung sich auf ihn beruft. Dieses Skript sucht solche Zeilen über ein
Muster je Plan (``PATTERNS``) in vier Haushaltstabellen; was trifft, aber nicht trägt, steht in
``REJECTED`` (mit Grund). Das Ergebnis — Verweise auf Zeilen, keine Beträge — steht in
``council/plan_budget.json``; die Beträge liest die Seite zur Laufzeit aus dem Bestand.

Geraten wird nichts: Kein Produkt kommt dazu, weil sein Name zum Plan „passt“.

    python scripts/plan_haushalt.py --zeigen    # Treffer mit Fundstelle, nichts schreiben
    python scripts/plan_haushalt.py             # council/plan_budget.json schreiben
    python scripts/plan_haushalt.py --pruefen   # nennt jede verwiesene Zeile den Plan noch?
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from council import plan_state, plans  # noqa: E402
from council.store import CouncilStore  # noqa: E402

#: So heißt ein Plan in den Haushaltstexten — nur Formen, die keinen anderen Plan meinen können.
PATTERNS: dict[str, str] = {
    "klimaschutzplan_2035": r"Klimaschutzplan",
    "mobilitaetsplan_2030": r"Mobilitätsplan|RMV 2030",
    "laermaktionsplan": r"Lärmaktionsplan",
    "ernaehrungsstrategie": r"Ernährungsstrategie",
    "kita_ausbau": r"Kita-Ausbau, \d\. Fortschreibung",
    "orte_fuer_alle": r"Orte für Alle",
    "aktionsplan_gewalt_2020": r"Aktionsplan gegen Gewalt an Frauen",
    "kai_2015": r"Kommunaler Aktionsplan Inklusion",
}
#: Das Suchwort für die Datenbank (grob); das Muster oben entscheidet.
TERMS: dict[str, str] = {
    "klimaschutzplan_2035": "klimaschutzplan", "mobilitaetsplan_2030": "mobilitätsplan",
    "laermaktionsplan": "lärmaktionsplan", "ernaehrungsstrategie": "ernährungsstrategie",
    "kita_ausbau": "kita-ausbau", "orte_fuer_alle": "orte für alle",
    "aktionsplan_gewalt_2020": "aktionsplan gegen gewalt", "kai_2015": "aktionsplan inklusion",
}
#: Ein zweites Suchwort, wo der Plan zwei Namen hat.
EXTRA_TERMS: dict[str, str] = {"mobilitaetsplan_2030": "rmv 2030"}

#: Was das Muster findet, aber nicht zum Plan gehört — (Plan, Tabelle, Nummer): Grund.
REJECTED: dict[tuple[str, str, str], str] = {
    ("laermaktionsplan", "investments", "I10.210819"): "Geräte für den Lärmaktionsplan von 2019 — der Vorgänger, nicht dieser Plan",
    ("laermaktionsplan", "investments", "I10.210820"): "Geräte für den Lärmaktionsplan von 2019 — der Vorgänger, nicht dieser Plan",
}

TEXT_FIELDS = ("legal_basis", "short_description", "product_name", "label", "details", "explanation")


def _number(table: str, row: dict) -> str:
    if table == "products":
        return row["product_no"]
    if table == "investments":
        return row["code"]
    return f"{row['budget_year']}/{row['list_key']}/{row['year']}/{row['seq']}"


def _field(row: dict, pattern: str) -> str | None:
    """Das erste Textfeld, in dem das Muster steht (Groß- und Kleinschreibung egal: „Orte für alle“)."""
    return next((f for f in TEXT_FIELDS if row.get(f) and re.search(pattern, str(row[f]), re.I)), None)


def propose(store: CouncilStore, key: str) -> list[dict]:
    """Verweise für einen Plan: Produkte und Investitionen je Nummer (alle Jahre), Änderungen je Zeile."""
    pattern = PATTERNS[key]
    out: dict[tuple, dict] = {}
    for table in ("products", "investments", "amendments", "amendments_cash"):
        rows = store.plan_budget_matches(table, TERMS[key])
        if key in EXTRA_TERMS:
            rows += store.plan_budget_matches(table, EXTRA_TERMS[key])
        for row in rows:
            field = _field(row, pattern)
            number = _number(table, row)
            if field is None or (key, table, number) in REJECTED:
                continue
            if table == "products":
                ref = {"table": table, "product_no": row["product_no"]}
            elif table == "investments":
                ref = {"table": table, "code": row["code"]}
            else:
                ref = {"table": table, "budget_year": row["budget_year"], "list_key": row["list_key"],
                       "year": row["year"], "seq": row["seq"]}
            entry = out.setdefault(tuple(sorted(ref.items())), {**ref, "field": field})
            # Produkte und Investitionen stehen in mehreren Jahrgängen — gezählt werden nur die, deren Text
            # den Plan nennt (ein Produkt kann ihn 2019 nennen und 2024 nicht mehr).
            if table in ("products", "investments"):
                entry.setdefault("years", [])
                if row["year"] not in entry["years"]:
                    entry["years"] = sorted([*entry["years"], row["year"]])
    return sorted(out.values(), key=lambda r: (r["table"], str(r.get("product_no") or r.get("code") or ""),
                                              r.get("budget_year") or 0, r.get("list_key") or "", r.get("year") or 0,
                                              r.get("seq") or 0))


def check(store: CouncilStore) -> list[str]:
    """Gibt es jede verwiesene Zeile noch, und nennt ihr Feld den Plan noch?"""
    problems = []
    for key, refs in plan_state.budget_refs().items():
        if key not in plans.PLANS or key not in PATTERNS:
            problems.append(f"{key}: unbekannter Plan oder kein Muster")
            continue
        if plan_state.budget_patterns().get(key) != PATTERNS[key]:
            problems.append(f"{key}: Muster in der Datei passt nicht zu PATTERNS — python scripts/plan_haushalt.py")
        for ref in refs:
            rows = store.plan_budget_rows(ref["table"], ref)
            if "years" in ref:
                rows = [r for r in rows if r["year"] in ref["years"]]
            if not rows:
                problems.append(f"{key}: Zeile fehlt im Bestand — {ref}")
            elif not all(re.search(PATTERNS[key], str(r.get(ref["field"]) or ""), re.I) for r in rows):
                problems.append(f"{key}: {ref} nennt den Plan nicht (mehr) in „{ref['field']}“")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--db", default=str(WURZEL / "data" / "council.sqlite"))
    ap.add_argument("--zeigen", action="store_true")
    ap.add_argument("--pruefen", action="store_true")
    args = ap.parse_args(argv)
    store = CouncilStore(args.db)
    try:
        if args.pruefen:
            problems = check(store)
            print("\n".join(problems) or f"✓ {sum(len(v) for v in plan_state.budget_refs().values())} Verweise nennen ihren Plan")
            return 1 if problems else 0
        found = {key: refs for key in PATTERNS if (refs := propose(store, key))}
        if args.zeigen:
            for key, refs in found.items():
                print(f"## {key}")
                for ref in refs:
                    rows = store.plan_budget_rows(ref["table"], ref)
                    row = [r for r in rows if r.get("year") in ref.get("years", [r.get("year")])][-1]
                    text = str(row.get(ref["field"]) or "")
                    m = re.search(r"[^.]{0,70}(?:" + PATTERNS[key] + r")[^.]{0,70}", text)
                    print(f"   {ref['table']:15s} {_number(ref['table'], row):28s} {str(row.get('product_name') or row.get('label'))[:40]:40s} …{(m.group(0) if m else text[:100]).strip()}…")
            return 0
        data = {"method": "Haushaltszeilen, deren eigener Text den Plan beim Namen nennt (Muster je Plan in "
                          "scripts/plan_haushalt.py), von Hand durchgesehen",
                "generated": dt.date.today().isoformat(),
                "patterns": {key: PATTERNS[key] for key in found}, "plans": found}
        plan_state.BUDGET_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"geschrieben: {plan_state.BUDGET_FILE.relative_to(WURZEL)} "
              f"({sum(len(v) for v in found.values())} Verweise für {len(found)} Pläne)")
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    sys.exit(main())
