"""Admin: edit LLM prompts, manage web users and the Telegram whitelist."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from council.store import CouncilStore
from nwz import prompts
from nwz.store import Store

from ..deps import get_council_store, get_store, require_admin
from ..schemas import PromptOut, PromptUpdate, RoleUpdate, StatusUpdate, WebUserOut

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ---- stats ----
@router.get("/stats")
def stats(
    _admin: dict = Depends(require_admin),
    store: Store = Depends(get_store),
    council: CouncilStore = Depends(get_council_store),
) -> dict:
    data = store.admin_stats()
    data["council"] = council.admin_stats()
    return data


# ---- prompts ----
@router.get("/prompts", response_model=list[PromptOut])
def list_prompts(_admin: dict = Depends(require_admin)) -> list[PromptOut]:
    return [PromptOut(**p) for p in prompts.list_all()]


@router.put("/prompts/{key}", response_model=PromptOut)
def update_prompt(key: str, body: PromptUpdate, _admin: dict = Depends(require_admin)) -> PromptOut:
    if key not in prompts.DEFAULTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unbekannter Prompt.")
    error = prompts.validate_template(key, body.content)
    if error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Ungültiges Template: {error}")
    prompts.set_content(key, body.content)
    return PromptOut(**next(p for p in prompts.list_all() if p["key"] == key))


@router.post("/prompts/{key}/reset", response_model=PromptOut)
def reset_prompt(key: str, _admin: dict = Depends(require_admin)) -> PromptOut:
    if key not in prompts.DEFAULTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unbekannter Prompt.")
    prompts.reset(key)
    return PromptOut(**next(p for p in prompts.list_all() if p["key"] == key))


# ---- web users ----
@router.get("/users", response_model=list[WebUserOut])
def list_users(_admin: dict = Depends(require_admin), store: Store = Depends(get_store)) -> list[WebUserOut]:
    return [WebUserOut(**u) for u in store.list_web_users()]


@router.put("/users/{user_id}/role", response_model=WebUserOut)
def set_role(
    user_id: int,
    body: RoleUpdate,
    admin: dict = Depends(require_admin),
    store: Store = Depends(get_store),
) -> WebUserOut:
    if body.role not in ("user", "admin"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Rolle muss 'user' oder 'admin' sein.")
    target = store.get_web_user_by_id(user_id)
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nutzer nicht gefunden.")
    if target["id"] == admin["id"] and body.role != "admin":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Du kannst dir nicht selbst die Adminrechte entziehen.")
    store.set_web_user_role(user_id, body.role)
    return WebUserOut(**store.get_web_user_by_id(user_id))


@router.put("/users/{user_id}/status", response_model=WebUserOut)
def set_status(
    user_id: int,
    body: StatusUpdate,
    admin: dict = Depends(require_admin),
    store: Store = Depends(get_store),
) -> WebUserOut:
    """Approve ('active') or suspend ('pending') a web account."""
    if body.status not in ("active", "pending"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Status muss 'active' oder 'pending' sein.")
    target = store.get_web_user_by_id(user_id)
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nutzer nicht gefunden.")
    if target["id"] == admin["id"] and body.status != "active":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Du kannst dich nicht selbst sperren.")
    store.set_web_user_status(user_id, body.status)
    return WebUserOut(**store.get_web_user_by_id(user_id))


# ---- telegram whitelist ----
@router.get("/telegram-users")
def telegram_users(_admin: dict = Depends(require_admin), store: Store = Depends(get_store)) -> dict:
    return {"users": store.get_users_with_topic_count()}


@router.delete("/telegram-users/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_telegram_user(
    chat_id: int,
    _admin: dict = Depends(require_admin),
    store: Store = Depends(get_store),
) -> None:
    store.remove_user(chat_id)
