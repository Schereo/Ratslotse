#!/usr/bin/env python3
"""Verwandte Pläne — ohne Sprachmodell vorgeschlagen, von Hand durchgesehen.

Gemeinsame Beschlüsse taugen als Grundlage nicht: Gemessen am 10.11.2026 teilen nur sieben
Paare überhaupt einen Beschluss, fast alle Vorgänger und Nachfolger. Vorgeschlagen wird
deshalb über die Nähe der Kernpunkte (dasselbe Einbettungsmodell wie „Ähnliche Beschlüsse“,
``council/embeddings.py``; fastembed, bewusst nicht in requirements.txt — das Skript läuft
offline, das Ergebnis ist eine Datei):

- gleiches Themenfeld und Nähe ab ``SAME_FIELD_MIN``, oder
- über Themenfelder hinweg nur bei hoher Nähe (``CROSS_FIELD_MIN``) und wenn beide einander
  unter ihren vier nächsten haben.

Vorgänger und Nachfolger fallen heraus — die stehen schon im Kopf der Planseite. Das Modell
ordnet lange Texte grob; **jeder Vorschlag ist deshalb von Hand angenommen oder verworfen**
(``REJECTED``, mit Grund). Dazu kommen Paare, die das Register selbst nennt (``NAMED``).
Die Seite sagt „verwandt“, nicht „gehört zusammen“ — und nennt keinen Grad.

    python scripts/plan_verwandt.py            # council/plan_related.json neu schreiben
    python scripts/plan_verwandt.py --zeigen   # Vorschläge mit Nähe, ohne zu schreiben
    python scripts/plan_verwandt.py --pruefen  # ohne Einbettung: Datei gegen das Register
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from council import plan_state, plans  # noqa: E402

SAME_FIELD_MIN = 0.55
CROSS_FIELD_MIN = 0.75
PER_PLAN = 3

#: Paare, die das Register selbst nennt — mit der Stelle.
NAMED: dict[tuple[str, str], str] = {
    ("ernaehrungsstrategie", "schulverpflegung"): "Register: Das Rahmenkonzept ist Handlungsansatz A1 der Ernährungsstrategie.",
}

#: Vorschläge, die nach der Regel passen, aber inhaltlich nicht tragen — von Hand verworfen.
REJECTED: dict[tuple[str, str], str] = {
    ("agenda_2025_alter", "aktionsplan_gewalt_2026"): "nur das Themenfeld Soziales gemeinsam",
    ("agenda_2025_alter", "wohnungslosen_suchthilfe"): "nur das Themenfeld Soziales gemeinsam",
    ("aktionsplan_energie", "ernaehrungsstrategie"): "nur das Themenfeld gemeinsam",
    ("aktionsplan_energie", "nachhaltigkeitsleitbild"): "abgelaufener Jahresplan gegen ein Leitbild",
    ("aktionsplan_energie", "thg_neutrale_verwaltung"): "abgelaufener Jahresplan; der Bezug läuft über den Klimaschutzplan",
    ("aktionsplan_gewalt_2026", "inklusion_stadt_fuer_alle"): "nur das Themenfeld Soziales gemeinsam",
    ("aktionsplan_gewalt_2026", "orte_fuer_alle"): "nur das Themenfeld Soziales gemeinsam",
    ("baumstrategie", "thg_neutrale_verwaltung"): "Bäume gegen Verwaltungsemissionen: kein inhaltlicher Bezug",
    ("demografiestrategie", "wohnungslosen_suchthilfe"): "nur das Themenfeld Soziales gemeinsam",
    ("digitalisierungsstrategie", "gleichstellungsplan_2024"): "beides Verwaltung, sonst nichts",
    ("ernaehrungsstrategie", "thg_neutrale_verwaltung"): "der Bezug läuft über den Klimaschutzplan",
    ("gleichstellungsplan_2018", "gleichstellungsplan_2024"): "dieselbe Kette (2018 → 2021 → 2024), steht im Kopf",
    ("inklusion_stadt_fuer_alle", "wohnungslosen_suchthilfe"): "nur das Themenfeld Soziales gemeinsam",
    ("integrationskonzept_2020", "orte_fuer_alle"): "ähnliche Wörter (Teilhabe, Stadtteil), anderes Thema",
    ("isek_2035", "thg_neutrale_verwaltung"): "ähnliche Wörter (2035, Ziele), anderes Thema",
    ("laermaktionsplan", "thg_neutrale_verwaltung"): "nur das Themenfeld gemeinsam",
    ("masterplan_stadtgruen", "thg_neutrale_verwaltung"): "nur das Themenfeld gemeinsam",
}


def pair(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def chained(a: str, b: str) -> bool:
    """Vorgänger oder Nachfolger voneinander? Die stehen schon im Kopf der Planseite."""
    pa, pb = plans.PLANS[a], plans.PLANS[b]
    return b in (pa.predecessor, pa.successor) or a in (pb.predecessor, pb.successor)


def suggestions() -> dict[tuple[str, str], float]:
    """Paare nach der Regel oben, mit ihrer Nähe. Braucht fastembed (nur hier, offline)."""
    import numpy as np

    from council import embeddings

    keys = plan_state.key_point_keys()
    texts = []
    for key in keys:
        data = plan_state.key_points(key) or {}
        texts.append(f"{plans.PLANS[key].title}. {data['purpose']['text']} " + " ".join(p["text"] for p in data["points"]))
    vectors = np.asarray(embeddings.embed(texts), dtype=float)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    sim = vectors @ vectors.T
    nearest = {k: {keys[j] for j in np.argsort(-sim[i]) if j != i and not chained(k, keys[j])}
               for i, k in enumerate(keys)}
    top4 = {k: [keys[j] for j in np.argsort(-sim[i]) if j != i][:4] for i, k in enumerate(keys)}
    out: dict[tuple[str, str], float] = {}
    for i, a in enumerate(keys):
        taken = 0
        for j in np.argsort(-sim[i]):
            b = keys[j]
            if b == a or b not in nearest[a] or taken >= PER_PLAN:
                continue
            score = float(sim[i, j])
            same = plans.PLANS[a].policy_field == plans.PLANS[b].policy_field
            if (same and score >= SAME_FIELD_MIN) or (score >= CROSS_FIELD_MIN and a in top4[b] and b in top4[a]):
                out[pair(a, b)] = round(score, 2)
                taken += 1
    return out


def check() -> list[str]:
    """Ohne Einbettung: Kennt das Register jeden Plan der Datei, und steht kein Paar doppelt oder
    zugleich unter den verworfenen?"""
    if not plan_state.RELATED_FILE.exists():
        return ["council/plan_related.json fehlt — python scripts/plan_verwandt.py"]
    data = json.loads(plan_state.RELATED_FILE.read_text(encoding="utf-8"))
    problems = []
    seen: set[tuple[str, str]] = set()
    for entry in data["pairs"]:
        a, b = entry["a"], entry["b"]
        if a not in plans.PLANS or b not in plans.PLANS:
            problems.append(f"unbekannter Plan: {a} / {b}")
            continue
        if a >= b or (a, b) in seen:
            problems.append(f"Paar doppelt oder nicht sortiert: {a} / {b}")
        if chained(a, b):
            problems.append(f"Vorgänger und Nachfolger stehen schon im Kopf: {a} / {b}")
        if (a, b) in REJECTED:
            problems.append(f"Paar ist verworfen UND in der Datei: {a} / {b}")
        seen.add((a, b))
    for a, b in list(REJECTED) + list(NAMED):
        if a not in plans.PLANS or b not in plans.PLANS or a >= b:
            problems.append(f"REJECTED/NAMED: unbekannt oder nicht sortiert: {a} / {b}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--zeigen", action="store_true", help="Vorschläge mit Nähe zeigen, nichts schreiben")
    ap.add_argument("--pruefen", action="store_true", help="ohne Einbettung: Datei gegen das Register halten")
    args = ap.parse_args(argv)
    if args.pruefen:
        problems = check()
        print("\n".join(problems) or "✓ council/plan_related.json passt zum Register")
        return 1 if problems else 0
    found = suggestions()
    open_pairs = {p: s for p, s in found.items() if p not in REJECTED}
    if args.zeigen:
        for (a, b), score in sorted(found.items(), key=lambda kv: -kv[1]):
            print(f"  {'✗' if (a, b) in REJECTED else '✓'} {score:.2f} {a} — {b}")
        return 0
    pairs = [{"a": a, "b": b, "score": score, "basis": "content"} for (a, b), score in open_pairs.items()]
    pairs += [{"a": a, "b": b, "score": None, "basis": "register"} for (a, b) in NAMED if (a, b) not in open_pairs]
    pairs.sort(key=lambda e: (e["a"], e["b"]))
    data = {"method": "Nähe der Kernpunkte (Einbettung, ohne Sprachmodell) im selben Themenfeld, von Hand "
                      "durchgesehen; dazu Paare, die das Register nennt",
            "generated": dt.date.today().isoformat(), "pairs": pairs}
    plan_state.RELATED_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"geschrieben: {plan_state.RELATED_FILE.relative_to(WURZEL)} ({len(pairs)} Paare, "
          f"{len(found) - len(open_pairs)} verworfen)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
