"""Telegram account linking via one-time code."""
from __future__ import annotations

import secrets
import string

from fastapi import APIRouter, Depends

from nwz.store import Store

from ..config import get_settings
from ..deps import get_current_user, get_store
from ..schemas import LinkCodeOut, LinkStatusOut

router = APIRouter(prefix="/api/link", tags=["link"])

_TTL_MINUTES = 15
_ALPHABET = string.ascii_uppercase + string.digits


def _generate_code(length: int = 6) -> str:
    # Avoid easily-confused characters.
    alphabet = _ALPHABET.translate(str.maketrans("", "", "O0I1"))
    return "".join(secrets.choice(alphabet) for _ in range(length))


@router.post("/request", response_model=LinkCodeOut)
def request_code(user: dict = Depends(get_current_user), store: Store = Depends(get_store)) -> LinkCodeOut:
    settings = get_settings()
    code = _generate_code()
    store.create_link_code(user["id"], code, ttl_minutes=_TTL_MINUTES)
    return LinkCodeOut(
        code=code,
        bot_username=settings.telegram_bot_username,
        expires_in_minutes=_TTL_MINUTES,
    )


@router.get("/status", response_model=LinkStatusOut)
def status(user: dict = Depends(get_current_user), store: Store = Depends(get_store)) -> LinkStatusOut:
    # Re-read in case the bot linked since login.
    fresh = store.get_web_user_by_id(user["id"])
    chat_id = fresh.get("telegram_chat_id") if fresh else None
    return LinkStatusOut(linked=bool(chat_id), telegram_chat_id=chat_id)
