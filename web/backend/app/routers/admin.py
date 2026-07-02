"""Admin: edit LLM prompts, manage web users and the Telegram whitelist."""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from council.store import CouncilStore
from nwz import prompts
from nwz.email import send_email
from nwz.store import Store

from ..config import get_settings
from ..deps import get_council_store, get_store, require_admin
from ..schemas import NwzFulltextUpdate, PromptOut, PromptUpdate, RoleUpdate, StatusUpdate, WebUserOut

logger = logging.getLogger("nwz.web.admin")

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _send_activation_email(email: str) -> None:
    """Best-effort: tell a user their account was approved (status pending → active)."""
    settings = get_settings()
    if not settings.resend_api_key or not email:
        return
    login = f"{settings.app_base_url.rstrip('/')}/login"
    body = (
        "<div style='max-width:560px;margin:0 auto;padding:24px 16px;"
        "font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#0f172a'>"
        "<div style='font-size:20px;font-weight:700;color:#2563eb'>Ratslotse</div>"
        "<p style='margin:20px 0 8px'>Gute Nachrichten: Dein Konto wurde freigeschaltet — du kannst dich "
        "jetzt anmelden und loslegen.</p>"
        f"<a href='{login}' style='display:inline-block;background:#2563eb;color:#fff;"
        "text-decoration:none;padding:10px 18px;border-radius:8px;font-size:14px'>Jetzt anmelden &rarr;</a>"
        "<p style='margin-top:20px;color:#94a3b8;font-size:12px'>"
        "Fragen oder Feedback? Antworte einfach auf diese E-Mail.</p></div>"
    )
    text = (
        "Dein Ratslotse-Konto wurde freigeschaltet.\n\n"
        f"Jetzt anmelden: {login}\n\n"
        "Fragen oder Feedback? Antworte einfach auf diese E-Mail.\n"
    )
    try:
        send_email(
            email, "Ratslotse – dein Konto ist freigeschaltet", body, text=text,
            reply_to=settings.feedback_email or settings.web_admin_email or None,
            api_key=settings.resend_api_key, sender=settings.email_from,
        )
    except Exception:  # noqa: BLE001 — approval must not fail on a mail hiccup
        logger.exception("activation email failed for %s", email)


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


@router.get("/llm-usage")
def llm_usage(_admin: dict = Depends(require_admin)) -> dict:
    """Per-feature LLM token usage + estimated cost (from llm_usage in nwz.sqlite)."""
    from nwz import usage
    return usage.summary()


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
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nutzer:in nicht gefunden.")
    if target["id"] == admin["id"] and body.role != "admin":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Du kannst dir nicht selbst die Adminrechte entziehen.")
    store.set_web_user_role(user_id, body.role)
    return WebUserOut(**store.get_web_user_by_id(user_id))


@router.put("/users/{user_id}/status", response_model=WebUserOut)
def set_status(
    user_id: int,
    body: StatusUpdate,
    background: BackgroundTasks,
    admin: dict = Depends(require_admin),
    store: Store = Depends(get_store),
) -> WebUserOut:
    """Approve ('active') or suspend ('pending') a web account. Emails the user on first approval."""
    if body.status not in ("active", "pending"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Status muss 'active' oder 'pending' sein.")
    target = store.get_web_user_by_id(user_id)
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nutzer:in nicht gefunden.")
    if target["id"] == admin["id"] and body.status != "active":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Du kannst dich nicht selbst sperren.")
    store.set_web_user_status(user_id, body.status)
    # Notify the user only on the pending → active transition (not on re-saves/no-ops).
    if body.status == "active" and target.get("status") != "active":
        background.add_task(_send_activation_email, target.get("email", ""))
    return WebUserOut(**store.get_web_user_by_id(user_id))


@router.put("/users/{user_id}/nwz-fulltext", response_model=WebUserOut)
def set_nwz_fulltext(
    user_id: int,
    body: NwzFulltextUpdate,
    _admin: dict = Depends(require_admin),
    store: Store = Depends(get_store),
) -> WebUserOut:
    """Manually allow/revoke full NWZ article text for a specific user."""
    if not store.get_web_user_by_id(user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nutzer:in nicht gefunden.")
    store.set_nwz_fulltext_allowed(user_id, body.allowed)
    return WebUserOut(**store.get_web_user_by_id(user_id))
