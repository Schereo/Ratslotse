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


def _notify_new_matches(nwz, council, owner_id: int, topic_name: str, new_ids: list[int]) -> int:
    """13a-D: EIN Push/Mail je Thema — der Titel mit der größten Tragweite
    führt (COALESCE impact, importance — nicht der erste oder kurioseste),
    Rest als „— und n weitere". Tap öffnet die Themen-Trefferliste."""
    from nwz.delivery import deliver_message

    owner = nwz.get_web_user_by_id(owner_id)
    if not owner:
        return 0
    owner = dict(owner)
    owner["push_tokens"] = nwz.get_push_tokens_for_owner(owner_id)
    # get_decision liefert d.* (impact/importance/amount_eur) — die schlanke
    # Batch-Query der QA-Zitate kennt diese Spalten nicht.
    decisions = [d for d in (council.get_decision(i) for i in new_ids) if d]
    if not decisions:
        return 0
    decisions.sort(key=lambda d: (d.get("impact") if d.get("impact") is not None
                                  else (d.get("importance") or 0)), reverse=True)
    lead = decisions[0]
    n = len(decisions)
    subject = f"Neu zu \u201e{topic_name}\u201c" + (f" \u2014 {n} Beschl\u00fcsse" if n > 1 else "")
    lead_line = (lead.get("title") or "").strip()
    if lead.get("amount_eur"):
        lead_line += f" ({int(lead['amount_eur']):,} \u20ac)".replace(",", ".")
    if n > 1:
        lead_line += f" \u2014 und {n - 1} weitere"
    msg = f"{lead_line}\n\nAlle Treffer findest du unter \u201eMeine Themen\u201c."
    sent = deliver_message(owner, msg, email_subject=subject, push_url="/topics")
    return 1 if sent else 0


def process(top_k: int = 8, threshold: float = 0.45) -> dict:
    nwz = Store(NWZ_DB)
    council = CouncilStore(COUNCIL_DB)
    try:
        by_owner = nwz.get_all_owner_topics()  # {owner_id: [TopicRow]}
        n_topics = sum(len(v) for v in by_owner.values())
        total = 0
        notified = 0
        for owner_id, topics in by_owner.items():
            for t in topics:
                # RL-U15 (13a-D): „neu" = Diff gegen den letzten Lauf. Beim
                # allerersten Matching eines Themas wird nicht gepusht (der
                # „Neu"-Zähler in der App zeigt die Erst-Treffer ohnehin).
                old_ids = {m["decision_id"] for m in nwz.get_topic_decision_matches(t.id)}
                text = f"{t.name}. {t.description}".strip()
                hits = embeddings.search(council, text, top_k=top_k, min_score=threshold)
                nwz.save_topic_decision_matches(t.id, owner_id, hits)
                total += len(hits)
                new_ids = [int(did) for did, _ in hits if int(did) not in old_ids]
                if new_ids and old_ids:
                    notified += _notify_new_matches(nwz, council, owner_id, t.name, new_ids)
        return {"topics": n_topics, "matches": total, "notified": notified}
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
