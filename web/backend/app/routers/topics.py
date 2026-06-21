"""Topic management and committee subscriptions for the linked Telegram account."""
from __future__ import annotations

import logging
from datetime import date, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from nwz.classify import build_digest
from nwz.store import Store

from ..config import get_settings
from ..deps import get_store, require_linked
from ..schemas import SubscriptionIn, TopicIn, TopicOut

logger = logging.getLogger("nwz.web.topics")

router = APIRouter(prefix="/api/topics", tags=["topics"])


def _reclassify_topic(chat_id: int, topic_id: int, name: str, description: str) -> None:
    """Background job: re-classify the last 30 days of editions for one topic from scratch."""
    settings = get_settings()
    store = Store(settings.nwz_db)
    try:
        cutoff = (date.today() - timedelta(days=30)).isoformat()
        topic_dict = [{"id": topic_id, "name": name, "description": description}]
        for pub_date in [d for d in store.edition_dates() if d >= cutoff]:
            articles = store.articles_for_date(pub_date)
            store.mark_edition_classified(chat_id, topic_id, pub_date)
            if not articles:
                continue
            try:
                _, matches = build_digest(articles, topic_dict, pub_date)
                store.save_article_matches(chat_id, matches)
            except Exception:
                logger.exception("reclassify failed: topic %s, %s", topic_id, pub_date)
    finally:
        store.close()


def _own_topic(store: Store, chat_id: int, topic_id: int):
    topic = store.get_topic_for_user(chat_id, topic_id)
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


@router.put("/{topic_id}", response_model=TopicOut)
def update_topic(
    topic_id: int,
    body: TopicIn,
    user: dict = Depends(require_linked),
    store: Store = Depends(get_store),
) -> TopicOut:
    chat_id = user["telegram_chat_id"]
    _own_topic(store, chat_id, topic_id)
    store.update_topic(topic_id, body.name, body.description)
    t = store.get_topic_for_user(chat_id, topic_id)
    return TopicOut(
        id=t.id,
        name=t.name,
        description=t.description,
        created_at=t.created_at,
        match_count=store.count_article_matches(chat_id, topic_id),
    )


@router.post("/{topic_id}/reclassify", status_code=status.HTTP_202_ACCEPTED)
def reclassify_topic(
    topic_id: int,
    background: BackgroundTasks,
    user: dict = Depends(require_linked),
    store: Store = Depends(get_store),
) -> dict:
    """Drop the topic's matches and re-classify the last 30 days in the background."""
    chat_id = user["telegram_chat_id"]
    topic = _own_topic(store, chat_id, topic_id)
    store.reset_topic_for_reclassify(chat_id, topic_id)
    background.add_task(_reclassify_topic, chat_id, topic_id, topic.name, topic.description)
    return {"started": True}


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
