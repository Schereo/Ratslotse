#!/usr/bin/env python3
"""Zusammenfassungen abgelehnter/vertagter Punkte neu schreiben — nur die betroffenen.

Bis 09/2026 bekamen ``summary`` (Themen-Klassifikation) und
``simple_summary`` („Lotti erklärt's einfach") nur ``official_text`` — bei
einem abgelehnten oder vertagten Punkt ist das der VORSCHLAG. Gemessen am
23.09.2026: 5988 („einstimmig abgelehnt") hieß „Der Satz für die Grundsteuer B
steigt von 445 auf 490 Prozent". Die Erzeugung kennt das Ergebnis inzwischen
(``council/outcome_note.py``); dieses Skript zieht den Bestand nach.

Betroffen ist eine Zeile, deren Ergebnis ``rejected``/``postponed``/
``no_decision`` ist und deren Text das Ergebnis NICHT nennt
(``outcome_note.states_outcome``). Alles andere bleibt unberührt — ein zweiter
Lauf findet also nur noch, was beim ersten nicht gelang.

Dazu ein Schritt ohne Modell: ``vote`` nach ``votes.normalize_vote`` („einstimmig
bei neun Enthaltungen" war ``majority``, 8426).

Was nicht gelingt, wird GELEERT statt stehen gelassen: Eine fehlende
Kurzfassung erzeugt der Wochenlauf neu, eine falsche bliebe für immer.
Beim Themen-Satz bleiben Themenfeld und Schlagworte, wie sie sind.

Usage::

    python scripts/fix_outcome_summaries.py                        # Bericht, nichts ändert sich
    python scripts/fix_outcome_summaries.py --probe --limit 20     # Modell rufen, alt/neu zeigen, Kosten messen
    python scripts/fix_outcome_summaries.py --schreiben            # alles Betroffene neu schreiben
    python scripts/fix_outcome_summaries.py --schreiben --nur simple --limit 50
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import outcome_note, simple_summary, topics  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from council.votes import normalize_vote  # noqa: E402
from kern import llm  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"
BATCH_SIZE = 15  # wie scripts/classify_decisions.py
_OUTCOMES = ", ".join(f"'{o}'" for o in outcome_note.NOT_ADOPTED)


def _affected(store: CouncilStore, column: str) -> list[dict]:
    rows = store._conn.execute(
        f"""SELECT d.id, d.kind, d.title, d.official_text, d.outcome, d.raw_result,
                   d.policy_field, d.policy_tags, d.{column} AS text,
                   cs.committee, cs.session_date
            FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr
            WHERE d.outcome IN ({_OUTCOMES}) AND d.{column} IS NOT NULL
            ORDER BY cs.session_date DESC, d.id"""
    ).fetchall()
    return [dict(r) for r in rows if not outcome_note.states_outcome(r["outcome"], r["text"])]


def _vote_fixes(store: CouncilStore) -> list[tuple[int, str | None, str | None]]:
    rows = store._conn.execute("SELECT id, vote, raw_result FROM council_decisions").fetchall()
    return [(r["id"], r["vote"], normalize_vote(r["vote"], r["raw_result"]))
            for r in rows if normalize_vote(r["vote"], r["raw_result"]) != r["vote"]]


def _new_simple(rows: list[dict], workers: int) -> dict[int, str | None]:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return dict(zip((r["id"] for r in rows), pool.map(simple_summary.generate_one, rows)))


def _new_summary(rows: list[dict], workers: int) -> dict[int, str | None]:
    batches = [rows[i:i + BATCH_SIZE] for i in range(0, len(rows), BATCH_SIZE)]
    out: dict[int, str | None] = {r["id"]: None for r in rows}

    def run(batch: list[dict]) -> dict:
        try:
            return topics.classify_batch(batch)[0]
        except Exception as exc:  # noqa: BLE001 — ein Stapel darf scheitern, die Zeilen bleiben
            print(f"  Stapel gescheitert: {exc!r}", flush=True)
            return {}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for res in pool.map(run, batches):
            for rid, r in res.items():
                out[rid] = r.get("summary")
    return out


def _show(label: str, rows: list[dict], new: dict[int, str | None]) -> None:
    for r in rows:
        print(f"\n[{label}] {r['id']} · {r['outcome']} · {(r['raw_result'] or '')[:80]}")
        print(f"  alt: {r['text']}")
        print(f"  neu: {new.get(r['id']) or '— (wird geleert)'}")


def process(db: Path, write: bool = False, probe: bool = False, only: str = "alle",
            limit: int | None = None, workers: int = 4) -> dict:
    store = CouncilStore(db)
    stats: dict = {}
    try:
        if only in ("alle", "vote"):
            fixes = _vote_fixes(store)
            stats["vote"] = len(fixes)
            print(f"vote: {len(fixes)} Zeile(n) — " + ", ".join(f"{i}: {a}→{b}" for i, a, b in fixes[:20]))
            if write and fixes:
                with store._conn:
                    store._conn.executemany("UPDATE council_decisions SET vote = ? WHERE id = ?",
                                            [(b, i) for i, _a, b in fixes])

        for column, label in (("simple_summary", "simple"), ("summary", "summary")):
            if only not in ("alle", label):
                continue
            rows = _affected(store, column)
            by_outcome: dict[str, int] = {}
            for r in rows:
                by_outcome[r["outcome"]] = by_outcome.get(r["outcome"], 0) + 1
            print(f"{column}: {len(rows)} betroffen {by_outcome}")
            stats[f"{label}_betroffen"] = len(rows)
            rows = rows[:limit] if limit else rows
            if not (write or probe) or not rows:
                continue

            new = (_new_simple(rows, workers) if column == "simple_summary"
                   else _new_summary(rows, workers))
            if probe:
                _show(label, rows, new)
            ok = sum(1 for v in new.values() if v)
            stats[f"{label}_neu"] = ok
            stats[f"{label}_geleert"] = len(new) - ok
            if not write:
                continue
            if column == "simple_summary":
                store._conn.executemany(
                    "UPDATE council_decisions SET simple_summary = ? WHERE id = ?",
                    [(v or None, rid) for rid, v in new.items()])
                store._conn.commit()
            else:
                # Nur der Satz — Feld und Schlagworte bleiben, wie sie sind.
                store.set_classifications({
                    r["id"]: {"field": r["policy_field"],
                              "tags": json.loads(r["policy_tags"] or "[]"),
                              "summary": new.get(r["id"])}
                    for r in rows})
    finally:
        store.close()

    cost = llm.session_cost()
    stats["kosten_usd"] = round(cost["usd"], 4)
    print(f"\nKosten: ${cost['usd']:.4f} ({cost['calls_mit']} Aufrufe mit Preis, "
          f"{cost['calls_ohne']} ohne)")
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--schreiben", action="store_true", help="wirklich schreiben (sonst nur Bericht)")
    ap.add_argument("--probe", action="store_true", help="Modell rufen und alt/neu zeigen, nichts schreiben")
    ap.add_argument("--nur", choices=("alle", "simple", "summary", "vote"), default="alle")
    ap.add_argument("--limit", type=int, default=None, help="höchstens so viele Zeilen je Spalte")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    stats = process(args.db, write=args.schreiben, probe=args.probe, only=args.nur,
                    limit=args.limit, workers=args.workers)
    print(json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
