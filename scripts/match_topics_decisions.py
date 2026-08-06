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
import html
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import embeddings  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from nwz.store import Store  # noqa: E402
from nwz import digest_email  # noqa: E402
from council.ergebnisse import decision_href  # noqa: E402

NWZ_DB = ROOT / "data" / "nwz.sqlite"
COUNCIL_DB = ROOT / "data" / "council.sqlite"


def _notify_new_matches(nwz, council, owner_id: int, topic_name: str, new_ids: list[int]) -> int:
    """13a-D: EIN Push/Mail je Thema — der Titel mit der größten Tragweite
    führt (COALESCE impact, importance — nicht der erste oder kurioseste),
    Rest als „— und n weitere". Tap öffnet die Themen-Trefferliste.

    Geht über die Warteschlange (``notify.einreihen``), nicht direkt über
    ``deliver_message``. Vorher tat es das — und stand damit als einziger Anlass
    außerhalb aller Grenzen aus Design 30a: Es kam auch dann an, wenn jemand
    „Ergebnisse zu meinen Themen" abgeschaltet oder Benachrichtigungen ganz
    ausgestellt hatte, es zählte nicht gegen die zwei am Tag, und es hätte
    mitten in der Nachtruhe klingeln können.

    Der Anlass ist **N3**: „Der Rat hat zu deinem Thema entschieden." Dass der
    Treffer hier aus dem Ähnlichkeitsabgleich stammt statt aus dem Protokoll
    einer abonnierten Sitzung, ist eine Frage der Herkunft, nicht der Bedeutung
    — für die Person ist es dieselbe Nachricht und gehört unter denselben
    Schalter.
    """
    from nwz import notify

    if not nwz.get_web_user_by_id(owner_id):
        return 0                      # Konto zwischenzeitlich gelöscht
    # get_decision liefert d.* (impact/importance/amount_eur) — die schlanke
    # Batch-Query der QA-Zitate kennt diese Spalten nicht.
    decisions = [d for d in (council.get_decision(i) for i in new_ids) if d]
    if not decisions:
        return 0
    decisions.sort(key=lambda d: (d.get("impact") if d.get("impact") is not None
                                  else (d.get("importance") or 0)), reverse=True)
    lead = decisions[0]
    n = len(decisions)
    kurz = " ".join(str(topic_name or "").split())[:80]
    subject = f"Neu zu \u201e{kurz}\u201c" + (f" \u2014 {n} Beschl\u00fcsse" if n > 1 else "")
    lead_line = html.escape((lead.get("title") or "").strip())
    if lead.get("amount_eur"):
        lead_line += f" ({int(lead['amount_eur']):,} \u20ac)".replace(",", ".")
    # Der Text nannte „Meine Themen“ nur — jetzt führt ein Knopf auch dorthin,
    # und der führende Beschluss ist direkt anklickbar.
    msg = (
        f"<p style='margin:0'>Neu zu deinem Thema <b>{html.escape(kurz)}</b>:</p>"
        + digest_email.liste(
            [f"<a href=\"{digest_email.absolut(decision_href(lead["id"]))}\">{lead_line}</a>"]
            + ([f"und {n - 1} weitere"] if n > 1 else [])
        )
        + digest_email.knopf("/topics", "Alle Treffer ansehen" if n > 1 else "Beschluss ansehen")
    )
    return 1 if notify.einreihen(nwz, owner_id, notify.N3_ERGEBNIS, subject, msg, "/topics") else 0


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
        # Eingereiht ist nicht zugestellt: Ohne diesen Aufruf läge alles bis zum
        # nächsten Cron-Job (7 Uhr) still. Die Nachtruhe verschiebt ohnehin, was
        # jetzt nicht raus darf — dieser Lauf startet sonntags um 3 Uhr.
        from nwz import notify

        zugestellt = notify.zustellen(nwz)
        return {"topics": n_topics, "matches": total, "notified": notified,
                "zugestellt": zugestellt}
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
