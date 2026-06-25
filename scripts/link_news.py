#!/usr/bin/env python3
"""Link council decisions to NWZ press articles (semantic + temporal).

Embeds every NWZ article (fastembed, same model as the decisions) and, for each
decision, finds the most similar articles published around the session date — i.e.
articles that actually report on that decision. Stores the matches in
council_news_links for the "In der Presse" section on the detail page.

fastembed is intentionally NOT in requirements — install it for this run:
    pip install fastembed
    python scripts/link_news.py
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import embeddings  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"
NWZ_DB = ROOT / "data" / "nwz.sqlite"


def _ordinal(d) -> int:
    try:
        return date.fromisoformat(str(d)[:10]).toordinal()
    except (ValueError, TypeError):
        return 0


def process(council_db: Path, nwz_db: Path, top_k: int = 3,
            threshold: float = 0.58, window_days: int = 120) -> dict:
    import numpy as np

    store = CouncilStore(council_db)
    drows = store.get_embeddings()
    if not drows:
        store.close()
        return {"articles": 0, "links": 0}
    dids = [r["decision_id"] for r in drows]
    dvecs = np.frombuffer(b"".join(bytes(r["vector"]) for r in drows), dtype="float32").reshape(len(dids), -1)
    ddates = store.decision_dates()
    dord = np.array([_ordinal(ddates.get(i)) for i in dids])

    nwz = sqlite3.connect(nwz_db)
    nwz.row_factory = sqlite3.Row
    arts = nwz.execute(
        "SELECT a.catalog, a.refid, a.title, a.subtitle, f.pub_date "
        "FROM articles a JOIN articles_fts f ON f.catalog = a.catalog AND f.refid = a.refid"
    ).fetchall()
    nwz.close()

    print(f"Embedding {len(arts)} articles…", flush=True)
    atexts = [f"{a['title'] or ''}. {a['subtitle'] or ''}".strip() for a in arts]
    avecs = embeddings.embed(atexts)
    aord = np.array([_ordinal(a["pub_date"]) for a in arts])

    out: list[tuple] = []
    block = 400
    for start in range(0, len(dids), block):
        sims = dvecs[start:start + block] @ avecs.T  # (b, n_articles), both normalised
        for bi, row in enumerate(sims):
            i = start + bi
            if not dord[i]:
                continue
            row = np.where(np.abs(aord - dord[i]) <= window_days, row, -1.0)
            idx = np.argpartition(-row, top_k)[:top_k]
            for j in idx[np.argsort(-row[idx])]:
                s = float(row[j])
                if s < threshold:
                    break
                a = arts[j]
                out.append((dids[i], a["catalog"], a["refid"], a["title"], a["pub_date"], s))
        print(f"  {min(start + block, len(dids))}/{len(dids)}", flush=True)

    store.set_news_links(out)
    store.close()
    return {"articles": len(arts), "links": len(out)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--nwz-db", type=Path, default=NWZ_DB)
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--threshold", type=float, default=0.58)
    ap.add_argument("--window-days", type=int, default=120)
    args = ap.parse_args()

    stats = process(args.db, args.nwz_db, args.top_k, args.threshold, args.window_days)
    print(f"\n=== done: {stats['links']} press links over {stats['articles']} articles ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
