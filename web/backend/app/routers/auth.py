"""Registration, login, logout, current user."""
from __future__ import annotations

import hashlib
import html as _html
import logging
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status

from nwz.store import Store
from nwz.email import send_email

from ..config import get_settings
from ..deps import get_current_user, get_store
from ..ratelimit import forgot_password_limiter, login_limiter, register_limiter, verify_email_limiter
from ..schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UserOut,
    VerifyEmailRequest,
)
from ..security import create_access_token, hash_password, verify_password

# Email-verification links stay valid for 24h (more forgiving than the 1h reset link).
_VERIFY_TTL_HOURS = 24

logger = logging.getLogger("nwz.web.auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_NAME = "access_token"


def _notify_admins_pending(new_email: str) -> None:
    """Background task: email every admin that a new account awaits approval."""
    settings = get_settings()
    if not settings.resend_api_key:
        return
    store = Store(settings.nwz_db)
    try:
        admins = [
            u["email"] for u in store.list_web_users()
            if u.get("role") == "admin" and not str(u.get("email", "")).endswith("@local")
        ]
    finally:
        store.close()
    if not admins:
        return

    admin_url = f"{settings.app_base_url.rstrip('/')}/admin"
    safe_email = _html.escape(new_email)
    subject = "Ratslotse – neue Registrierung wartet auf Freischaltung"
    body = (
        "<div style='max-width:560px;margin:0 auto;padding:24px 16px;"
        "font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#0f172a'>"
        "<div style='font-size:20px;font-weight:700;color:#2563eb'>Ratslotse</div>"
        "<p style='margin:20px 0 8px'>Eine neue Person hat sich registriert und wartet auf Freischaltung:</p>"
        f"<p style='margin:0 0 20px;font-weight:600'>{safe_email}</p>"
        f"<a href='{admin_url}' style='display:inline-block;background:#2563eb;color:#fff;"
        "text-decoration:none;padding:10px 18px;border-radius:8px;font-size:14px'>"
        "Im Admin-Bereich freischalten →</a>"
        "<p style='margin-top:20px;color:#94a3b8;font-size:12px'>"
        "Du bekommst diese E-Mail, weil du ein Ratslotse-Administrator bist.</p>"
        "</div>"
    )
    text = (
        f"Neue Registrierung wartet auf Freischaltung: {new_email}\n\n"
        f"Im Admin-Bereich freischalten: {admin_url}\n"
    )
    for addr in admins:
        try:
            send_email(addr, subject, body, text=text,
                       api_key=settings.resend_api_key, sender=settings.email_from)
        except Exception:
            logger.exception("admin pending-registration notice failed for %s", addr)


def _set_auth_cookie(response: Response, user: dict) -> None:
    settings = get_settings()
    token = create_access_token(user["id"], user.get("token_version", 0))
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )


def _is_app_client(request: Request) -> bool:
    """The native (Capacitor) app sends `X-Client: app`; browsers don't."""
    return request.headers.get("X-Client", "").lower() == "app"


def _app_access_token(request: Request, user: dict) -> str | None:
    """Mint a long-lived bearer token for native-app clients to store on-device.

    Browsers rely on the httpOnly cookie set by ``_set_auth_cookie`` and get
    ``None`` here (the token is never exposed to page JS). The app can't persist
    cross-site cookies reliably, so it carries the token in the Authorization
    header instead — which ``deps.get_current_user`` already accepts.
    """
    if not _is_app_client(request):
        return None
    settings = get_settings()
    return create_access_token(
        user["id"], user.get("token_version", 0), settings.app_access_token_expire_minutes
    )


def _to_out(user: dict, access_token: str | None = None) -> UserOut:
    return UserOut(
        id=user["id"],
        email=user["email"],
        role=user["role"],
        status=user.get("status", "active"),
        telegram_chat_id=user.get("telegram_chat_id"),
        linked=bool(user.get("telegram_chat_id")),
        delivery_channel=user.get("delivery_channel", "telegram"),
        nwz_fulltext_allowed=bool(user.get("nwz_fulltext_allowed")),
        email_verified=bool(user.get("email_verified")),
        access_token=access_token,
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(
    request: Request,
    body: RegisterRequest,
    response: Response,
    background: BackgroundTasks,
    store: Store = Depends(get_store),
) -> UserOut:
    register_limiter.check(request)
    settings = get_settings()
    email = str(body.email).lower().strip()
    if store.get_web_user_by_email(email):
        raise HTTPException(status.HTTP_409_CONFLICT, "E-Mail ist bereits registriert.")
    # First user, or the configured admin email, becomes an active admin.
    # Everyone else starts 'pending' and must be approved by an admin.
    is_admin = email == settings.web_admin_email.lower() or store.count_web_users() == 0
    role = "admin" if is_admin else "user"
    user_status = "active" if is_admin else "pending"
    # Admins (deployment owner) skip verification; so does the no-email case, since
    # we can't send a link then — otherwise the account could never be confirmed.
    can_send_email = bool(settings.resend_api_key)
    verified = is_admin or not can_send_email
    user_id = store.create_web_user(
        email, hash_password(body.password), role, user_status, email_verified=verified
    )
    # New web accounts have no Telegram yet — default to email delivery so they
    # actually receive their digest. They can switch channels later in /account.
    store.set_delivery_channel(user_id, "email")
    created_user = store.get_web_user_by_id(user_id)
    _set_auth_cookie(response, created_user)
    if user_status == "pending":
        if verified:
            # Can't verify the address (email not configured) — ping admins now.
            background.add_task(_notify_admins_pending, email)
        else:
            # Send a verification link; admins are pinged once it's confirmed real.
            raw = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(raw.encode()).hexdigest()
            expires = (datetime.utcnow() + timedelta(hours=_VERIFY_TTL_HOURS)).isoformat(timespec="seconds")
            store.create_email_verification(user_id, token_hash, expires)
            background.add_task(_send_verification_email, email, raw)
    return _to_out(created_user, _app_access_token(request, created_user))


@router.post("/login", response_model=UserOut)
def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    store: Store = Depends(get_store),
) -> UserOut:
    login_limiter.check(request)
    user = store.get_web_user_by_email(str(body.email))
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-Mail oder Passwort falsch.")
    _set_auth_cookie(response, user)
    return _to_out(user, _app_access_token(request, user))


@router.post("/logout")
def logout(response: Response) -> dict:
    settings = get_settings()
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, secure=settings.cookie_secure, samesite="lax")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)) -> UserOut:
    return _to_out(user)


def _send_reset_email(email: str, raw_token: str) -> None:
    """Background task: email a one-hour password-reset link (best-effort)."""
    settings = get_settings()
    if not settings.resend_api_key:
        return
    link = f"{settings.app_base_url.rstrip('/')}/reset-password?token={raw_token}"
    subject = "Ratslotse – Passwort zurücksetzen"
    body = (
        "<div style='max-width:560px;margin:0 auto;padding:24px 16px;"
        "font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#0f172a'>"
        "<div style='font-size:20px;font-weight:700;color:#2563eb'>Ratslotse</div>"
        "<p style='margin:20px 0 8px'>Du hast angefordert, dein Passwort zurückzusetzen. Über den "
        "folgenden Link kannst du ein neues Passwort vergeben — er ist <b>1 Stunde</b> gültig:</p>"
        f"<a href='{link}' style='display:inline-block;background:#2563eb;color:#fff;"
        "text-decoration:none;padding:10px 18px;border-radius:8px;font-size:14px'>Neues Passwort setzen →</a>"
        "<p style='margin-top:20px;color:#94a3b8;font-size:12px'>"
        "Wenn du das nicht warst, ignoriere diese E-Mail — dein Passwort bleibt unverändert.</p>"
        "</div>"
    )
    text = (
        "Passwort zurücksetzen bei Ratslotse.\n\n"
        f"Neues Passwort setzen (1 Stunde gültig): {link}\n\n"
        "Wenn du das nicht warst, ignoriere diese E-Mail.\n"
    )
    try:
        send_email(email, subject, body, text=text, api_key=settings.resend_api_key, sender=settings.email_from)
    except Exception:
        logger.exception("password-reset email failed for %s", email)


@router.post("/forgot-password")
def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    background: BackgroundTasks,
    store: Store = Depends(get_store),
) -> dict:
    """Start a password reset. Always returns 200 — never reveals whether an account
    exists (no enumeration). A one-hour, single-use token is emailed if it does."""
    forgot_password_limiter.check(request)
    email = str(body.email).lower().strip()
    user = store.get_web_user_by_email(email)
    # Skip synthetic Telegram-only accounts (tg-…@local have no real inbox).
    if user and not email.endswith("@local"):
        raw = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        expires = (datetime.utcnow() + timedelta(hours=1)).isoformat(timespec="seconds")
        store.create_password_reset(int(user["id"]), token_hash, expires)
        background.add_task(_send_reset_email, email, raw)
    return {"ok": True}


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest, store: Store = Depends(get_store)) -> dict:
    """Set a new password from a valid reset token, then invalidate all sessions."""
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    now = datetime.utcnow().isoformat(timespec="seconds")
    user_id = store.consume_password_reset(token_hash, now)
    if user_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Der Link ist ungültig oder abgelaufen. Bitte fordere einen neuen an.")
    store.update_password_hash(user_id, hash_password(body.new_password))
    store.increment_token_version(user_id)
    return {"ok": True}


def _send_verification_email(email: str, raw_token: str) -> None:
    """Background task: email a verification link (valid 24h, best-effort)."""
    settings = get_settings()
    if not settings.resend_api_key:
        return
    link = f"{settings.app_base_url.rstrip('/')}/verify-email?token={raw_token}"
    subject = "Ratslotse – E-Mail bestätigen"
    body = (
        "<div style='max-width:560px;margin:0 auto;padding:24px 16px;"
        "font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#0f172a'>"
        "<div style='font-size:20px;font-weight:700;color:#2563eb'>Ratslotse</div>"
        "<p style='margin:20px 0 8px'>Willkommen! Bitte bestätige deine E-Mail-Adresse über den "
        "folgenden Link — er ist <b>24 Stunden</b> gültig:</p>"
        f"<a href='{link}' style='display:inline-block;background:#2563eb;color:#fff;"
        "text-decoration:none;padding:10px 18px;border-radius:8px;font-size:14px'>E-Mail bestätigen →</a>"
        "<p style='margin-top:20px;color:#94a3b8;font-size:12px'>"
        "Wenn du dich nicht registriert hast, ignoriere diese E-Mail.</p>"
        "</div>"
    )
    text = (
        "Willkommen bei Ratslotse.\n\n"
        f"Bitte bestätige deine E-Mail (24 Stunden gültig): {link}\n\n"
        "Wenn du dich nicht registriert hast, ignoriere diese E-Mail.\n"
    )
    try:
        send_email(email, subject, body, text=text, api_key=settings.resend_api_key, sender=settings.email_from)
    except Exception:
        logger.exception("verification email failed for %s", email)


@router.post("/verify-email", response_model=UserOut)
def verify_email(
    request: Request,
    body: VerifyEmailRequest,
    background: BackgroundTasks,
    store: Store = Depends(get_store),
) -> UserOut:
    """Confirm an email address from a valid verification token."""
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    now = datetime.utcnow().isoformat(timespec="seconds")
    user_id = store.consume_email_verification(token_hash, now)
    if user_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Der Bestätigungslink ist ungültig oder abgelaufen. "
                            "Bitte fordere einen neuen an.")
    store.set_email_verified(user_id, True)
    user = store.get_web_user_by_id(user_id)
    # Now that the address is confirmed, ping admins to approve (if still pending).
    if user and user.get("status") == "pending":
        background.add_task(_notify_admins_pending, user["email"])
    # If the app opened this via a deep link (verification tapped on-device),
    # hand back a bearer token so it lands logged-in.
    return _to_out(user, _app_access_token(request, user))


@router.post("/resend-verification")
def resend_verification(
    request: Request,
    background: BackgroundTasks,
    user: dict = Depends(get_current_user),
    store: Store = Depends(get_store),
) -> dict:
    """Re-send the verification link to the logged-in user's address."""
    verify_email_limiter.check(request)
    settings = get_settings()
    if user.get("email_verified"):
        return {"ok": True}  # already verified — no-op
    email = str(user["email"])
    if not settings.resend_api_key or email.endswith("@local"):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "E-Mail-Versand ist nicht konfiguriert.")
    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    expires = (datetime.utcnow() + timedelta(hours=_VERIFY_TTL_HOURS)).isoformat(timespec="seconds")
    store.create_email_verification(int(user["id"]), token_hash, expires)
    background.add_task(_send_verification_email, email, raw)
    return {"ok": True}
