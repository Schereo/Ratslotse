#!/usr/bin/env python3
"""Themen-Sätze (`summary`) langer Beschlüsse neu schreiben.

Bis 11/2026 sah die Klassifikation (``council/topics.py``) nur die ersten 400
Zeichen von ``official_text``. Was dahinter stand, kam im Satz nicht vor —
meist ein Auftrag, den ein Änderungsantrag angefügt hat. 19134 (Rat,
15.04.2024) beauftragt eine Wirtschaftlichkeitsanalyse und danach die
Erweiterung des EGH um eine Wohnungsgesellschaft; der Satz lautete nur
„Beauftragung einer Wirtschaftlichkeitsanalyse …", und Frag den Rat schloss
daraus, die Gesellschaft sei nie beschlossen worden.

Betroffen ist jede Zeile mit Satz und einem Beschlusstext über der alten
Grenze. Feld und Schlagworte bleiben, wie sie sind; nur der Satz wird neu
geschrieben. Was nicht gelingt, bleibt stehen — der alte Satz ist unvollständig,
aber nicht falsch, und anders als ein geleerter füllt ihn kein Lauf wieder auf.
Ein zweiter Lauf schreibt alles noch einmal (idempotent im Ergebnis, kostet
erneut).

Usage::

    python scripts/fix_long_summaries.py                       # Bericht, nichts ändert sich
    python scripts/fix_long_summaries.py --probe --limit 20    # Modell rufen, alt/neu zeigen, Kosten messen
    python scripts/fix_long_summaries.py --probe --id 19134
    python scripts/fix_long_summaries.py --schreiben           # alles Betroffene neu schreiben
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

from council import topics  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from kern import llm  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"
BATCH_SIZE = 15  # wie scripts/classify_decisions.py
ALTE_GRENZE = 400  # so viel Beschlusstext sah die Klassifikation bis 11/2026


def affected(store: CouncilStore, ids: list[int] | None = None) -> list[dict]:
    where = "d.summary IS NOT NULL AND d.policy_field IS NOT NULL AND length(d.official_text) > ?"
    params: list = [ALTE_GRENZE]
    if ids:
        where = f"d.id IN ({','.join('?' * len(ids))})"
        params = list(ids)
    rows = store._conn.execute(
        f"""SELECT d.id, d.kind, d.title, d.official_text, d.outcome, d.raw_result,
                   d.policy_field, d.policy_tags, d.summary AS text,
                   cs.committee, cs.session_date
            FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr
            WHERE {where}
            ORDER BY cs.session_date DESC, d.id""", params).fetchall()
    return [dict(r) for r in rows]


def new_summaries(rows: list[dict], workers: int) -> dict[int, str | None]:
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


def process(db: Path, write: bool = False, probe: bool = False, limit: int | None = None,
            ids: list[int] | None = None, workers: int = 4) -> dict:
    store = CouncilStore(db)
    stats: dict = {}
    try:
        rows = affected(store, ids)
        stats["betroffen"] = len(rows)
        print(f"summary: {len(rows)} betroffen (Beschlusstext > {ALTE_GRENZE} Zeichen)")
        rows = rows[:limit] if limit else rows
        if (write or probe) and rows:
            new = new_summaries(rows, workers)
            if probe:
                for r in rows:
                    print(f"\n{r['id']} · {r['session_date']} · {r['committee']} · {r['title'][:90]}")
                    print(f"  alt: {r['text']}")
                    print(f"  neu: {new.get(r['id']) or '— (bleibt alt)'}")
            gut = {rid: v for rid, v in new.items() if v}
            stats["neu"] = len(gut)
            stats["unveraendert"] = len(new) - len(gut)
            if write and gut:
                store.set_classifications({
                    r["id"]: {"field": r["policy_field"],
                              "tags": json.loads(r["policy_tags"] or "[]"),
                              "summary": gut[r["id"]]}
                    for r in rows if r["id"] in gut})
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
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--id", type=int, action="append", dest="ids", help="nur diese Beschlüsse (mehrfach)")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    stats = process(args.db, write=args.schreiben, probe=args.probe, limit=args.limit,
                    ids=args.ids, workers=args.workers)
    print(json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
