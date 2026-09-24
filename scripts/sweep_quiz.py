#!/usr/bin/env python3
"""Den Quiz-Bestand aufräumen: Dubletten und langweilige Fragen ausmustern.

Zwei Durchgänge über die aktiven Fragen:

1. **Dubletten** (ohne Modell): gleicher Fragetext im selben Gebiet — so
   lagen alle 17 Haushaltsfragen doppelt da, weil der Umbau ``thema`` →
   ``topic`` den content_hash der alten Zeilen nicht mitnahm und der nächste
   Ingest sie neu anlegte. Dazu Umformulierungen derselben Frage
   (:func:`council.quiz.is_near_duplicate`), bei den KI-Fragen.
   Behalten wird jeweils die jüngste Zeile.
2. **Reiz** (ein kleines Modell je Frage): :func:`council.quiz.rate_appeal`
   benotet 1–5, die Note landet in ``appeal``. Unter
   :data:`council.store_quiz.MIN_APPEAL` kommt eine Frage in der Runde erst
   nach den reizvollen dran und nie in die Tages-Challenge; unter
   ``--retire-below`` (Vorgabe 2, also nur Note 1) wird sie ausgemustert.
   Die deterministischen Haushaltsfragen sind davon ausgenommen.

Warum nicht alles unter 3 ausmustern? Gemessen am Abzug vom 23.09.2026
wären das 539 von 777 Fragen gewesen, und unter den Zweien stehen neben
Straßenbreiten auch brauchbare („Aus welchem Jahr stammt die ursprüngliche
Weser-Ems-Halle?"). Nachrangig spielen kostet nichts, leer spielen schon.

Ohne ``--retire`` wird nur gezählt und gezeigt (und nichts gespeichert).
Ausgemusterte Fragen füllt der nächste ``generate_quiz.py``-Lauf
(wöchentlich) wieder auf — dann schon mit Richter.

Kosten, gemessen: 688 Fragen in 117 s für $0,034.

Usage::

    python scripts/sweep_quiz.py --limit 20          # Probe: Noten + Kosten
    python scripts/sweep_quiz.py                     # alles benoten, nichts ändern
    python scripts/sweep_quiz.py --retire            # ausmustern
    python scripts/sweep_quiz.py --no-appeal --retire  # nur Dubletten
"""
from __future__ import annotations

import argparse
import collections
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import quiz  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from council.store_quiz import MIN_APPEAL  # noqa: E402
from kern import llm  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")

#: Gebiete, deren Fragen aus Zahlen gebaut werden statt vom Modell — die
#: benotet der Richter nicht, und „fast gleich" heißt dort nichts (die
#: Bereichsfragen unterscheiden sich nur im Bereichsnamen).
DETERMINISTIC = {("topic", "haushalt")}


def find_duplicates(questions: list[dict]) -> list[tuple[dict, dict]]:
    """(auszumustern, behalten)-Paare. Die jüngere Zeile (höhere id) bleibt."""
    by_area: dict[tuple, list[dict]] = collections.defaultdict(list)
    for q in questions:
        by_area[(q["area_type"], q["area_key"])].append(q)
    out = []
    for area, qs in by_area.items():
        kept: list[dict] = []
        for q in sorted(qs, key=lambda x: -x["id"]):
            exact = next((k for k in kept if quiz._norm(k["question"]) == quiz._norm(q["question"])), None)
            near = None
            if exact is None and area not in DETERMINISTIC:
                near = next((k for k in kept
                             if quiz.is_near_duplicate(q["question"], [k["question"]])), None)
            if exact or near:
                out.append((q, exact or near))
            else:
                kept.append(q)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--limit", type=int, default=None, help="nur so viele Fragen benoten (Probe)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--no-appeal", action="store_true", help="nur Dubletten, kein Modell")
    ap.add_argument("--retire", action="store_true", help="Noten speichern und ausmustern")
    ap.add_argument("--retire-below", type=int, default=2,
                    help="Note, unter der ausgemustert wird (Vorgabe 2 = nur Note 1)")
    ap.add_argument("--show", type=int, default=15, help="so viele Beispiele je Note zeigen")
    args = ap.parse_args()

    store = CouncilStore(args.db)
    questions = store.quiz_active_rows()
    print(f"{len(questions)} aktive Fragen.")

    dups = find_duplicates(questions)
    print(f"\n== Dubletten: {len(dups)} ==")
    for drop, keep in dups[:args.show]:
        print(f"  #{drop['id']} → bleibt #{keep['id']}: {drop['question'][:90]}")
    dup_ids = {d["id"] for d, _ in dups}

    low: list[tuple[dict, int]] = []
    if not args.no_appeal:
        pool = [q for q in questions if q["id"] not in dup_ids
                and (q["area_type"], q["area_key"]) not in DETERMINISTIC]
        if args.limit:
            import random
            pool = random.Random(0).sample(pool, min(args.limit, len(pool)))
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            notes = list(ex.map(quiz.rate_appeal, pool))
        cost = llm.session_cost()
        dauer = time.time() - t0
        hist = collections.Counter(notes)
        print(f"\n== Reiz: {len(pool)} benotet in {dauer:.0f} s, "
              f"${cost['usd']:.4f} ({cost['calls_ohne']} ohne Kostenangabe) ==")
        if pool:
            je = cost["usd"] / len(pool)
            print(f"   je Frage ${je:.5f} → hochgerechnet auf alle KI-Fragen: "
                  f"${je * sum(1 for q in questions if (q['area_type'], q['area_key']) not in DETERMINISTIC):.2f}")
        for note in (1, 2, 3, 4, 5, None):
            print(f"   Note {note}: {hist.get(note, 0)}")
        by_note = collections.defaultdict(list)
        for q, n in zip(pool, notes):
            by_note[n].append(q)
        for note in (1, 2, 3, 4, 5):
            for q in by_note[note][:args.show]:
                print(f"   [{note}] #{q['id']} {q['category']}: {q['question'][:110]}")
        rated = {q["id"]: n for q, n in zip(pool, notes) if n is not None}
        low = [(q, n) for q, n in zip(pool, notes) if n is not None and n < args.retire_below]
        weak = sum(1 for n in rated.values() if n < MIN_APPEAL)
        by_cat = collections.Counter(q["category"] for q, _ in low)
        print(f"\n   nachrangig (unter {MIN_APPEAL}): {weak}")
        print(f"   auszumustern (unter {args.retire_below}): {len(low)} — je Kategorie {dict(by_cat)}")
        if args.retire:
            store.set_quiz_appeal(rated)

    retire = sorted(dup_ids | {q["id"] for q, _ in low})
    if args.retire:
        for qid in retire:
            store.retire_quiz_question(qid)
        print(f"\n{len(retire)} Fragen ausgemustert.")
    else:
        print(f"\nTrockenlauf: {len(retire)} Fragen würden ausgemustert (--retire).")
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
