"""Native-app push device-token registration.

The Capacitor app registers its APNs (iOS) / FCM (Android) device token here after
the user grants notification permission, so the digest cron can reach it. Delivery
itself happens in ``nwz.delivery`` alongside Telegram/email.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status

from nwz.store import Store

from ..deps import get_store, require_active
from ..schemas import PushRegisterRequest, PushUnregisterRequest

router = APIRouter(prefix="/api/push", tags=["push"])


@router.post("/register", status_code=status.HTTP_204_NO_CONTENT)
def register_push(
    body: PushRegisterRequest,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> None:
    """Register (or refresh) the caller's device push token. Idempotent — the app
    re-registers on every launch, which also re-homes a token if the OS rotated it."""
    store.add_push_token(int(user["id"]), body.token, body.platform)


@router.post("/unregister", status_code=status.HTTP_204_NO_CONTENT)
def unregister_push(
    body: PushUnregisterRequest,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> None:
    """Drop the caller's device token (on logout / disabling notifications). Scoped
    to the caller's own tokens so one account can't unregister another's device."""
    owned = {t["token"] for t in store.get_push_tokens_for_owner(int(user["id"]))}
    if body.token in owned:
        store.remove_push_token(body.token)
