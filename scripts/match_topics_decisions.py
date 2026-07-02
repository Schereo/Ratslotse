#!/usr/bin/env python3
"""Match each user topic to the most similar council decisions (semantic).

For every topic, embeds its name + description with the same model as the decisions
and finds the closest decisions via the precomputed decision vectors, storing the top
matches in ``council_topic_matches``. So a topic like "Radwege" surfaces the relevant
*Ratsbeschlüsse*, not just NWZ articles. Re-run after embed_decisions.py (the weekly
enrich cron does both). fastembed is needed (not a web dependency)::

    pip install fastembed
    python scripts/match_topics_decisions.py --threshold 0.45 --top-k 8
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import embeddings  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from nwz.store import Store  # noqa: E402

NWZ_DB = ROOT / "data" / "nwz.sqlite"
COUNCIL_DB = ROOT / "data" / "council.sqlite"


def process(top_k: int = 8, threshold: float = 0.45) -> dict:
    nwz = Store(NWZ_DB)
    council = CouncilStore(COUNCIL_DB)
    try:
        by_owner = nwz.get_all_owner_topics()  # {owner_id: [TopicRow]}
        n_topics = sum(len(v) for v in by_owner.values())
        total = 0
        for owner_id, topics in by_owner.items():
            for t in topics:
                text = f"{t.name}. {t.description}".strip()
                hits = embeddings.search(council, text, top_k=top_k, min_score=threshold)
                nwz.save_topic_decision_matches(t.id, owner_id, hits)
                total += len(hits)
        return {"topics": n_topics, "matches": total}
    finally:
        nwz.close()
        council.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--top-k", type=int, default=8)
    ap.add_argument("--threshold", type=float, default=0.45)
    args = ap.parse_args()
    st = process(args.top_k, args.threshold)
    print(f"=== done: {st['matches']} decision matches across {st['topics']} topic(s) ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
