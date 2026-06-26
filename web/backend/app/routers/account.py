"""Account self-service: NWZ credentials and password management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from nwz.store import Store

from ..config import get_settings
from ..deps import get_store, require_active
from ..schemas import ChangePasswordRequest, DeliveryUpdate, UserOut
from ..security import hash_password, verify_password
from .auth import _set_auth_cookie, _to_out

router = APIRouter(prefix="/api/account", tags=["account"])


@router.put("/delivery", response_model=UserOut)
def set_delivery(
    body: DeliveryUpdate,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> UserOut:
    """Choose where the digest is delivered: telegram, email, or both."""
    channel = body.delivery_channel
    if channel in ("email", "both"):
        email = str(user.get("email", ""))
        if email.startswith("tg-") and email.endswith("@local"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Keine E-Mail-Adresse hinterlegt.")
    if channel in ("telegram", "both") and not user.get("telegram_chat_id"):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Für Telegram-Zustellung musst du zuerst dein Konto mit Telegram verbinden.",
        )
    store.set_delivery_channel(user["id"], channel)
    return _to_out(store.get_web_user_by_id(user["id"]))


@router.post("/change-password", response_model=UserOut)
def change_password(
    body: ChangePasswordRequest,
    response: Response,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> UserOut:
    if not verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Aktuelles Passwort ist falsch.")
    store.update_password_hash(user["id"], hash_password(body.new_password))
    store.increment_token_version(user["id"])
    updated = store.get_web_user_by_id(user["id"])
    _set_auth_cookie(response, updated)
    return _to_out(updated)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    response: Response,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> None:
    """Permanently delete the account and all data keyed to it (DSGVO right to erasure)."""
    store.delete_web_user(user["id"])
    settings = get_settings()
    response.delete_cookie("access_token", path="/", httponly=True,
                           secure=settings.cookie_secure, samesite="lax")
