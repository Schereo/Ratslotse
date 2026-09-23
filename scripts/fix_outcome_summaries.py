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

Danach die Beschreibungen der Themen-Seiten (``council_entity_meta``): Sie
entstehen aus den Einzeilern und kannten das Ergebnis bis 23.09.2026 ebenso
wenig. Bei den 20 Themen des dev-Abzugs, deren Beschlüsse alle scheiterten,
bestanden 8–9 die Eval (``eval/run_ergebnis_texte.py --textart themen``),
etwa „TSH Konzept Berlin": „… der Bau neuer Dreifeldsporthallen … beschlossen"
— beide Beschlüsse abgelehnt. Mit dem Ergebnis im Prompt 20/20.

Usage::

    python scripts/fix_outcome_summaries.py                        # Bericht, nichts ändert sich
    python scripts/fix_outcome_summaries.py --probe --limit 20     # Modell rufen, alt/neu zeigen, Kosten messen
    python scripts/fix_outcome_summaries.py --schreiben            # alles Betroffene neu schreiben
    python scripts/fix_outcome_summaries.py --schreiben --nur simple --limit 50
    python scripts/fix_outcome_summaries.py --schreiben --nur themen
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

from council import entities, outcome_note, simple_summary, topics  # noqa: E402
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


def _affected_entities(store: CouncilStore) -> list[dict]:
    """Themen mit Beschreibung und mindestens einem nicht gefassten Beschluss.

    Anders als beim Einzeiler gibt es hier keine Probe je Zeile: Eine
    Beschreibung erzählt von vielen Beschlüssen, und die falschen nannten die
    Ablehnung oft sogar („lehnte im September ab … beschloss im November ein
    Abstellverbot" — beide abgelehnt). Deshalb alle; ein zweiter Lauf schreibt
    sie noch einmal (251 Themen im dev-Abzug, $0,45 am 23.09.2026).
    """
    rows = store._conn.execute(
        f"""SELECT e.slug, e.name, e.kind, m.description
            FROM council_entities e JOIN council_entity_meta m ON m.slug = e.slug
            WHERE m.description IS NOT NULL AND m.description != ''
              AND EXISTS (SELECT 1 FROM council_entity_links el
                          JOIN council_decisions d ON d.id = el.decision_id
                          WHERE el.entity_id = e.id AND d.outcome IN ({_OUTCOMES}))
            ORDER BY e.n DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


def _new_descriptions(store: CouncilStore, ents: list[dict], workers: int) -> dict[str, str | None]:
    # Die Beschlüsse im Hauptfaden lesen — die Verbindung gehört ihm.
    work = [(e, store.entity_decisions_brief(e["slug"])) for e in ents]

    def run(item: tuple) -> str | None:
        e, decs = item
        return entities.describe(e["name"], e["kind"], decs)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return dict(zip((e["slug"] for e in ents), pool.map(run, work)))


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

        # Themen-Beschreibungen NACH den Einzeilern: Sie werden aus ihnen gebaut.
        if only in ("alle", "themen"):
            ents = _affected_entities(store)
            print(f"themen: {len(ents)} betroffen")
            stats["themen_betroffen"] = len(ents)
            ents = ents[:limit] if limit else ents
            if (write or probe) and ents:
                new_desc = _new_descriptions(store, ents, workers)
                if probe:
                    for e in ents:
                        print(f"\n[themen] {e['slug']}\n  alt: {e['description']}\n"
                              f"  neu: {new_desc.get(e['slug']) or '— (wird geleert)'}")
                ok = sum(1 for v in new_desc.values() if v)
                stats["themen_neu"] = ok
                stats["themen_geleert"] = len(new_desc) - ok
                if write:
                    store.set_entity_descriptions([(s, v) for s, v in new_desc.items() if v])
                    # Geleert statt stehen gelassen: describe_entities.py (Wochenlauf)
                    # füllt eine leere Beschreibung neu, eine falsche nie.
                    with store._conn:
                        store._conn.executemany(
                            "UPDATE council_entity_meta SET description = NULL WHERE slug = ?",
                            [(s,) for s, v in new_desc.items() if not v])
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
    ap.add_argument("--nur", choices=("alle", "simple", "summary", "themen", "vote"), default="alle")
    ap.add_argument("--limit", type=int, default=None, help="höchstens so viele Zeilen je Spalte")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    stats = process(args.db, write=args.schreiben, probe=args.probe, only=args.nur,
                    limit=args.limit, workers=args.workers)
    print(json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
