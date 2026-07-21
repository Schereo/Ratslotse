"""Topic management and committee subscriptions for the web account.

Ownership is keyed on the web account (owner_id = web_users.id); a linked
Telegram chat is only a delivery target, so these endpoints work for web-only
users too. Topics match against council decisions (semantic); the former NWZ
article matching was removed with the NWZ scraper.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from nwz.store import Store
from council.store import CouncilStore

from ..deps import get_council_store, get_store, require_active
from ..schemas import SubscriptionIn, TopicIn, TopicOut

logger = logging.getLogger("nwz.web.topics")

router = APIRouter(prefix="/api/topics", tags=["topics"])


def _own_topic(store: Store, owner_id: int, topic_id: int):
    topic = store.get_topic_for_owner(owner_id, topic_id)
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thema nicht gefunden.")
    return topic


@router.get("", response_model=list[TopicOut])
def list_topics(
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
    council: CouncilStore = Depends(get_council_store),
) -> list[TopicOut]:
    owner_id = user["id"]
    dec_counts = store.topic_decision_counts(owner_id)
    topics = store.get_topics(owner_id)
    # Jüngster Treffer je Thema (RL-701): Kandidaten je Thema sammeln, Beschlüsse
    # in EINEM Batch nachschlagen, dann pro Thema das neueste Sitzungsdatum wählen.
    cand: dict[int, list[int]] = {t.id: [m["decision_id"] for m in store.get_topic_decision_matches(t.id)[:10]]
                                  for t in topics}
    all_ids = [d for ids in cand.values() for d in ids]
    by_id = {d["id"]: d for d in council.get_decisions_by_ids(all_ids)} if all_ids else {}
    out = []
    for t in topics:
        hits = sorted((by_id[d] for d in cand.get(t.id, []) if d in by_id),
                      key=lambda d: d.get("session_date") or "", reverse=True)
        last = hits[0] if hits else None
        out.append(
            TopicOut(
                id=t.id,
                name=t.name,
                description=t.description,
                created_at=t.created_at,
                decision_count=dec_counts.get(t.id, 0),
                last_hit_id=last["id"] if last else None,
                last_hit_title=last["title"] if last else None,
                last_hit_date=last.get("session_date") if last else None,
            )
        )
    return out


@router.get("/suggestions")
def topic_suggestions(
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
    council: CouncilStore = Depends(get_council_store),
) -> dict:
    """Anklickbare Themen-Vorschläge aus den echten Daten: die häufigsten
    Beschluss-Schlagworte der letzten sechs Monate — ohne Themen, die der
    Account schon angelegt hat. Ein Klick im Frontend legt den Vorschlag
    direkt als eigenes Thema an."""
    existing = {t.name.strip().lower() for t in store.get_topics(user["id"])}
    out = []
    for t in council.trending_tags(days_back=180, limit=16):
        name = t["tag"].strip()
        if not name or name.lower() in existing:
            continue
        out.append({
            "name": name[:1].upper() + name[1:],
            "description": (
                f"Neue Beschlüsse, Planungen und Maßnahmen des Oldenburger "
                f"Stadtrats rund um das Thema {name}."
            ),
            "n": t["n"],
        })
        if len(out) >= 6:
            break
    return {"suggestions": out}


@router.post("", response_model=TopicOut, status_code=status.HTTP_201_CREATED)
def add_topic(body: TopicIn, user: dict = Depends(require_active), store: Store = Depends(get_store)) -> TopicOut:
    t = store.add_topic(user["id"], body.name, body.description)
    return TopicOut(id=t.id, name=t.name, description=t.description, created_at=t.created_at, decision_count=0)


@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_topic(topic_id: int, user: dict = Depends(require_active), store: Store = Depends(get_store)) -> None:
    _own_topic(store, user["id"], topic_id)
    store.delete_topic(topic_id)


@router.put("/{topic_id}", response_model=TopicOut)
def update_topic(
    topic_id: int,
    body: TopicIn,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> TopicOut:
    owner_id = user["id"]
    _own_topic(store, owner_id, topic_id)
    store.update_topic(topic_id, body.name, body.description)
    t = store.get_topic_for_owner(owner_id, topic_id)
    return TopicOut(
        id=t.id,
        name=t.name,
        description=t.description,
        created_at=t.created_at,
        decision_count=len(store.get_topic_decision_matches(topic_id)),
    )


@router.get("/latest-hits")
def latest_hits(
    limit: int = Query(2, ge=1, le=10),
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
    council: CouncilStore = Depends(get_council_store),
) -> dict:
    """Die jüngsten Beschluss-Treffer über ALLE Themen des Kontos — für die
    „Neu zu deinen Themen"-Karte im Heute-Briefing (RL-401). Vor der
    {topic_id}-Route registriert, damit „latest-hits" nicht als ID parst."""
    pairs: list[tuple[str, int]] = []
    for t in store.get_topics(user["id"]):
        pairs += [(t.name, m["decision_id"]) for m in store.get_topic_decision_matches(t.id)[:10]]
    by_id = {d["id"]: d for d in council.get_decisions_by_ids([d_id for _, d_id in pairs])}
    rows = [
        {"topic_name": name, "id": d["id"], "title": d["title"],
         "committee": d["committee"], "session_date": d["session_date"]}
        for name, d_id in pairs if (d := by_id.get(d_id))
    ]
    rows.sort(key=lambda r: r["session_date"] or "", reverse=True)
    seen: set[int] = set()
    out = [r for r in rows if not (r["id"] in seen or seen.add(r["id"]))]
    return {"hits": out[:limit]}


@router.get("/{topic_id}/decisions")
def topic_decisions(
    topic_id: int,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
    council: CouncilStore = Depends(get_council_store),
) -> dict:
    """Council decisions matched to this topic (semantic), best first."""
    owner_id = user["id"]
    _own_topic(store, owner_id, topic_id)
    matches = store.get_topic_decision_matches(topic_id)
    score_by = {m["decision_id"]: m["score"] for m in matches}
    decisions = council.get_decisions_by_ids([m["decision_id"] for m in matches])
    return {
        "decisions": [
            {
                "id": d["id"],
                "title": d["title"],
                "committee": d["committee"],
                "session_date": d["session_date"],
                "policy_field": d["policy_field"],
                "outcome": d["outcome"],
                "score": score_by.get(d["id"], 0.0),
            }
            for d in decisions
        ]
    }


# ---- committee subscriptions ----
sub_router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


@sub_router.get("")
def list_subscriptions(user: dict = Depends(require_active), store: Store = Depends(get_store)) -> dict:
    return {"subscriptions": store.get_subscriptions(user["id"])}


@sub_router.post("", status_code=status.HTTP_201_CREATED)
def subscribe(body: SubscriptionIn, user: dict = Depends(require_active), store: Store = Depends(get_store)) -> dict:
    ok = store.subscribe(user["id"], body.committee_name)
    return {"subscribed": ok, "committee_name": body.committee_name}


@sub_router.delete("")
def unsubscribe(body: SubscriptionIn, user: dict = Depends(require_active), store: Store = Depends(get_store)) -> dict:
    ok = store.unsubscribe(user["id"], body.committee_name)
    return {"unsubscribed": ok, "committee_name": body.committee_name}
