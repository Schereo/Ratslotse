"""Topic management and committee subscriptions for the linked Telegram account."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from nwz.store import Store

from ..deps import get_store, require_linked
from ..schemas import SubscriptionIn, TopicIn, TopicOut

router = APIRouter(prefix="/api/topics", tags=["topics"])


def _own_topic(store: Store, chat_id: int, topic_id: int):
    topic = next((t for t in store.get_topics(chat_id) if t.id == topic_id), None)
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thema nicht gefunden.")
    return topic


@router.get("", response_model=list[TopicOut])
def list_topics(user: dict = Depends(require_linked), store: Store = Depends(get_store)) -> list[TopicOut]:
    chat_id = user["telegram_chat_id"]
    out = []
    for t in store.get_topics(chat_id):
        out.append(
            TopicOut(
                id=t.id,
                name=t.name,
                description=t.description,
                created_at=t.created_at,
                match_count=store.count_article_matches(chat_id, t.id),
            )
        )
    return out


@router.post("", response_model=TopicOut, status_code=status.HTTP_201_CREATED)
def add_topic(body: TopicIn, user: dict = Depends(require_linked), store: Store = Depends(get_store)) -> TopicOut:
    chat_id = user["telegram_chat_id"]
    t = store.add_topic(chat_id, body.name, body.description)
    return TopicOut(id=t.id, name=t.name, description=t.description, created_at=t.created_at, match_count=0)


@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_topic(topic_id: int, user: dict = Depends(require_linked), store: Store = Depends(get_store)) -> None:
    _own_topic(store, user["telegram_chat_id"], topic_id)
    store.delete_topic(topic_id)


@router.get("/{topic_id}/matches")
def topic_matches(
    topic_id: int,
    limit: int = 50,
    user: dict = Depends(require_linked),
    store: Store = Depends(get_store),
) -> dict:
    chat_id = user["telegram_chat_id"]
    _own_topic(store, chat_id, topic_id)
    return {"matches": store.get_article_matches(chat_id, topic_id, limit=limit)}


# ---- committee subscriptions ----
sub_router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


@sub_router.get("")
def list_subscriptions(user: dict = Depends(require_linked), store: Store = Depends(get_store)) -> dict:
    return {"subscriptions": store.get_subscriptions(user["telegram_chat_id"])}


@sub_router.post("", status_code=status.HTTP_201_CREATED)
def subscribe(body: SubscriptionIn, user: dict = Depends(require_linked), store: Store = Depends(get_store)) -> dict:
    ok = store.subscribe(user["telegram_chat_id"], body.committee_name)
    return {"subscribed": ok, "committee_name": body.committee_name}


@sub_router.delete("")
def unsubscribe(body: SubscriptionIn, user: dict = Depends(require_linked), store: Store = Depends(get_store)) -> dict:
    ok = store.unsubscribe(user["telegram_chat_id"], body.committee_name)
    return {"unsubscribed": ok, "committee_name": body.committee_name}
