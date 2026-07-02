"""Account self-service: delivery channel, password, account deletion."""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status

from nwz.email import send_email
from nwz.store import Store

from ..config import get_settings
from ..deps import get_store, require_active
from ..schemas import ChangePasswordRequest, DeleteAccountRequest, DeliveryUpdate, UserOut
from ..security import hash_password, verify_password
from .auth import _set_auth_cookie, _to_out

logger = logging.getLogger("nwz.web.account")

router = APIRouter(prefix="/api/account", tags=["account"])


def _send_goodbye_email(email: str) -> None:
    """Best-effort: schriftliche Bestätigung der Löschung (Nachweis für die
    Person, Warnung bei Fremdauslösung). Läuft nach der Löschung — ein
    Mail-Fehler ändert nichts mehr."""
    settings = get_settings()
    if not settings.resend_api_key or not email or email.endswith("@local"):
        return
    body = (
        "<div style='max-width:560px;margin:0 auto;padding:24px 16px;"
        "font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#0f172a'>"
        "<div style='font-size:20px;font-weight:700;color:#2563eb'>Ratslotse</div>"
        "<p style='margin:20px 0 8px'>Dein Ratslotse-Konto und alle zugehörigen Daten "
        "(Themen, Treffer, Abos, Geräte) wurden endgültig gelöscht.</p>"
        "<p style='margin:0 0 8px'>Danke, dass du dabei warst — du bist jederzeit wieder willkommen.</p>"
        "<p style='margin-top:20px;color:#94a3b8;font-size:12px'>"
        "Falls du diese Löschung nicht selbst ausgelöst hast, antworte bitte umgehend auf diese E-Mail.</p>"
        "</div>"
    )
    text = (
        "Dein Ratslotse-Konto und alle zugehörigen Daten wurden endgültig gelöscht.\n\n"
        "Falls du diese Löschung nicht selbst ausgelöst hast, antworte bitte umgehend auf diese E-Mail.\n"
    )
    try:
        send_email(
            email, "Ratslotse – dein Konto wurde gelöscht", body, text=text,
            reply_to=settings.feedback_email or settings.web_admin_email or None,
            api_key=settings.resend_api_key, sender=settings.email_from,
        )
    except Exception:  # noqa: BLE001 — die Löschung ist durch, die Mail ist Kür
        logger.exception("goodbye email failed for %s", email)


@router.put("/delivery", response_model=UserOut)
def set_delivery(
    body: DeliveryUpdate,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> UserOut:
    """Choose where notifications are delivered: email, push, or both."""
    channel = body.delivery_channel
    if channel in ("email", "both"):
        email = str(user.get("email", ""))
        if email.startswith("tg-") and email.endswith("@local"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Keine E-Mail-Adresse hinterlegt.")
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
    body: DeleteAccountRequest,
    response: Response,
    background: BackgroundTasks,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> None:
    """Permanently delete the account and all data keyed to it (DSGVO right to
    erasure). Verlangt das aktuelle Passwort — eine Session allein (offener
    Laptop, gestohlenes Cookie) darf das Konto nicht zerstören können."""
    if not verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Aktuelles Passwort ist falsch.")
    email = str(user.get("email", ""))
    store.delete_web_user(user["id"])
    background.add_task(_send_goodbye_email, email)
    settings = get_settings()
    response.delete_cookie("access_token", path="/", httponly=True,
                           secure=settings.cookie_secure, samesite="lax")
