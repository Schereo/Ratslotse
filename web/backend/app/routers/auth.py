"""Registration, login, logout, current user."""
from __future__ import annotations

import hashlib
import html as _html
import logging
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status

from kern.store import Store
from kern.digest_email import knopf, render_html_email
from kern.email import send_email

from ..config import get_settings
from ..antworten import Ok
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
from ..security import DUMMY_PASSWORD_HASH, create_access_token, hash_password, verify_password
from ..session import clear_session_cookie, set_session_cookie

# Email-verification links stay valid for 24h (more forgiving than the 1h reset link).
_VERIFY_TTL_HOURS = 24

logger = logging.getLogger("ratslotse.web.auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Ops-Hinweis für Deployments ohne E-Mail-Versand (dort gibt es keinen
# Bestätigungslink, über den sich der erste Admin selbst freischalten könnte).
_GRANT_ADMIN_CMD = ".venv/bin/python scripts/grant_admin.py %s"


def _configured_admin_email(settings) -> str:  # noqa: ANN001 — Settings ODER Test-Fake
    """``WEB_ADMIN_EMAIL`` so normalisiert, wie Adressen gespeichert werden."""
    return str(getattr(settings, "web_admin_email", "") or "").strip().lower()


def _has_admin(store: Store) -> bool:
    """Gibt es in diesem Deployment überhaupt (noch) eine Adminrolle?"""
    return any(u.get("role") == "admin" for u in store.list_web_users())


def _promote_configured_admin(store: Store, user: dict) -> dict:
    """Ersten Admin einrichten — aber erst gegen eine *nachgewiesene* Adresse.

    Wird von ``verify_email`` aufgerufen, nachdem der einmalige Token verbraucht
    und die Adresse als bestätigt markiert wurde. Die Registrierung selbst vergibt
    keine Rolle mehr: sonst würde, wer ``WEB_ADMIN_EMAIL`` als Erstes ins
    Registrierungsformular tippt, das Deployment übernehmen, ohne je bewiesen zu
    haben, dass ihm dieses Postfach gehört.

    Befördert nur, wenn alles davon gilt:
      * ``WEB_ADMIN_EMAIL`` ist gesetzt und ist genau die Adresse dieses Kontos,
      * das Konto ist noch exakt das, was Registrierung + Bestätigung hinterlassen
        (Rolle ``user``, Status ``active``),
      * im Deployment existiert überhaupt keine Adminrolle.

    Die letzte Bedingung ist Absicht: sie verhindert, dass ein Konto, dem ein Admin
    die Rechte bewusst entzogen (oder das er gesperrt) hat, sie sich über einen
    weiteren Bestätigungslink still zurückholt.
    """
    configured = _configured_admin_email(get_settings())
    if not configured or str(user.get("email") or "").strip().lower() != configured:
        return user
    if user.get("role") != "user" or user.get("status") != "active":
        return user
    if _has_admin(store):
        return user
    store.set_web_user_role(int(user["id"]), "admin")
    logger.info("WEB_ADMIN_EMAIL %s bestätigt — Konto %s ist jetzt Admin (Erst-Einrichtung).",
                configured, user["id"])
    return store.get_web_user_by_id(int(user["id"])) or user


def _notify_admins_registration(new_email: str) -> None:
    """Background task: FYI-email to every admin that a new (verified) account
    just activated itself — accounts no longer need manual approval."""
    settings = get_settings()
    if not settings.resend_api_key:
        return
    store = Store(settings.ratslotse_db)
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
    subject = "Ratslotse – neue Registrierung"
    body = render_html_email(
        subject,
        "<p style='margin:0'>Eine neue Person hat sich registriert, die E-Mail-Adresse "
        "bestätigt und ist jetzt aktiv:</p>"
        f"<p style='margin:10px 0 0;font-weight:600'>{safe_email}</p>"
        + knopf(admin_url, "Im Admin-Bereich ansehen"),
        held=None,
        kicker="Für dich als Admin",
        title="Neue Registrierung",
        fusszeile="Nur zur Info — es ist nichts zu tun. Du bekommst diese E-Mail, "
                  "weil dein Ratslotse-Konto Admin-Rechte hat.",
    )
    text = (
        f"Neue Registrierung (bestätigt & aktiv): {new_email}\n\n"
        f"Im Admin-Bereich ansehen: {admin_url}\n"
    )
    for addr in admins:
        try:
            send_email(addr, subject, body, text=text,
                       api_key=settings.resend_api_key, sender=settings.email_from)
        except Exception:
            logger.exception("admin pending-registration notice failed for %s", addr)


def _set_auth_cookie(response: Response, user: dict) -> None:
    set_session_cookie(response, create_access_token(user["id"], user.get("token_version", 0)))


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
        delivery_channel=user.get("delivery_channel", "email"),
        email_verified=bool(user.get("email_verified")),
        apple_linked=bool(user.get("apple_sub")),
        has_password=bool(user.get("password_set", 1)),
        display_name=user.get("display_name"),
        saves_conversations=user.get("saves_conversations"),
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
    # Registration hands out no role at all: everything it could decide on comes
    # from this unauthenticated request body. Even the configured WEB_ADMIN_EMAIL
    # starts as a plain user and is only promoted once it has proven control of
    # the mailbox (_promote_configured_admin, called from verify_email).
    role = "user"
    # Confirming the email address activates the account — no manual admin
    # approval anymore. Only the no-email case skips verification, since we
    # can't send a link then (the account could never be confirmed).
    can_send_email = bool(settings.resend_api_key)
    verified = not can_send_email
    user_status = "active" if verified else "pending"
    user_id = store.create_web_user(
        email, hash_password(body.password), role, user_status, email_verified=verified,
        display_name=body.display_name,
    )
    # Default to email delivery so new accounts actually receive notifications.
    # They can switch channels later in /account.
    store.set_delivery_channel(user_id, "email")
    created_user = store.get_web_user_by_id(user_id)
    _set_auth_cookie(response, created_user)
    if user_status == "pending":
        # Send a verification link; confirming it activates the account and
        # pings the admins (FYI) once the address is confirmed real.
        raw = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        expires = (datetime.utcnow() + timedelta(hours=_VERIFY_TTL_HOURS)).isoformat(timespec="seconds")
        store.create_email_verification(user_id, token_hash, expires)
        background.add_task(_send_verification_email, email, raw, body.display_name)
    elif email == _configured_admin_email(settings) and not _has_admin(store):
        # Ohne E-Mail-Versand gibt es keinen Link zum Bestätigen — der Weg über
        # verify_email() kann dieses Konto also nicht zum Admin machen. Laut sagen,
        # statt das Deployment stillschweigend ohne Admin zu lassen.
        logger.warning(
            "WEB_ADMIN_EMAIL %s hat sich registriert, aber ohne RESEND_API_KEY gibt es "
            "keinen Bestätigungslink — das Konto bleibt ein normales Nutzerkonto. "
            "Adminrechte von Hand vergeben: " + _GRANT_ADMIN_CMD,
            email, email,
        )
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
    # Verify unconditionally — against a dummy hash when the email has no account.
    # Short-circuiting here would skip scrypt for unknown emails and turn the
    # response time into an account-existence oracle (CWE-208).
    stored = user["password_hash"] if user else DUMMY_PASSWORD_HASH
    password_ok = verify_password(body.password, stored)
    if not user or not password_ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-Mail oder Passwort falsch.")
    _set_auth_cookie(response, user)
    return _to_out(user, _app_access_token(request, user))


@router.post("/logout")
def logout(response: Response) -> Ok:
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(request: Request, user: dict = Depends(get_current_user)) -> UserOut:
    """Das aktuelle Konto — und für die App gleich ein frisches Token.

    Die App fragt diesen Endpunkt bei jedem Start. Das Token, das sie dabei
    zurückbekommt, läuft wieder die volle Laufzeit — wer die App benutzt,
    bleibt also angemeldet. Das Gegenstück zur stillen Cookie-Verlängerung im
    Browser (``app/session.py``), die für Bearer-Clients nicht funktioniert.
    """
    return _to_out(user, _app_access_token(request, user))


def _send_reset_email(email: str, raw_token: str, display_name: str | None = None) -> None:
    """Background task: email a one-hour password-reset link (best-effort)."""
    settings = get_settings()
    if not settings.resend_api_key:
        return
    link = f"{settings.app_base_url.rstrip('/')}/reset-password?token={raw_token}"
    subject = "Ratslotse – Passwort zurücksetzen"
    body = render_html_email(
        subject,
        "<p style='margin:0'>Du hast angefordert, dein Passwort zurückzusetzen. "
        "Über den Knopf vergibst du ein neues — der Link ist <b>1 Stunde</b> gültig:</p>"
        + knopf(link, "Neues Passwort setzen"),
        greeting_name=display_name,
        held="passwort",
        kicker="Dein Konto",
        title="Passwort zurücksetzen",
        fusszeile="Wenn du das nicht warst, ignoriere diese E-Mail — "
                  "dein Passwort bleibt unverändert.",
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
) -> Ok:
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
        background.add_task(_send_reset_email, email, raw, user.get("display_name"))
    return {"ok": True}


@router.post("/reset-password", response_model=UserOut)
def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    response: Response,
    store: Store = Depends(get_store),
) -> UserOut:
    """Set a new password from a valid reset token, then invalidate all sessions."""
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    now = datetime.utcnow().isoformat(timespec="seconds")
    user_id = store.consume_password_reset(token_hash, now)
    if user_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Der Link ist ungültig oder abgelaufen. Bitte fordere einen neuen an.")
    store.update_password_hash(user_id, hash_password(body.new_password))
    store.increment_token_version(user_id)
    user = store.get_web_user_by_id(user_id)
    _set_auth_cookie(response, user)
    # Reset links can open directly in the native app. Returning the refreshed
    # account and its app token avoids an unnecessary login immediately after
    # invalidating every previous token.
    return _to_out(user, _app_access_token(request, user))


def _send_verification_email(email: str, raw_token: str, display_name: str | None = None) -> None:
    """Background task: email a verification link (valid 24h, best-effort)."""
    settings = get_settings()
    if not settings.resend_api_key:
        return
    link = f"{settings.app_base_url.rstrip('/')}/verify-email?token={raw_token}"
    subject = "Ratslotse – E-Mail bestätigen"
    body = render_html_email(
        subject,
        "<p style='margin:0'>Ein Klick noch, dann ist dein Konto startklar: "
        "Bestätige bitte deine E-Mail-Adresse — der Link ist <b>24 Stunden</b> gültig.</p>"
        + knopf(link, "E-Mail bestätigen"),
        greeting_name=display_name,
        held="willkommen",
        kicker="Willkommen an Bord",
        title="Schön, dass du da bist!",
        fusszeile="Wenn du dich nicht registriert hast, ignoriere diese E-Mail — "
                  "dann passiert nichts.",
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
    # A confirmed address activates the account — no manual admin approval.
    # (Suspended accounts can't reach this: their tokens are already consumed
    # and resend-verification no-ops for verified addresses.)
    if user and user.get("status") == "pending":
        store.set_web_user_status(user_id, "active")
        user = store.get_web_user_by_id(user_id)
        background.add_task(_notify_admins_registration, user["email"])
    if user:
        # Erst hier — nach verbranntem Token und bestätigter Adresse — kann das
        # konfigurierte Admin-Konto seine Rolle bekommen (Erst-Einrichtung).
        user = _promote_configured_admin(store, user)
    # If the app opened this via a deep link (verification tapped on-device),
    # hand back a bearer token so it lands logged-in.
    return _to_out(user, _app_access_token(request, user))


@router.post("/resend-verification")
def resend_verification(
    request: Request,
    background: BackgroundTasks,
    user: dict = Depends(get_current_user),
    store: Store = Depends(get_store),
) -> Ok:
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
    background.add_task(_send_verification_email, email, raw, user.get("display_name"))
    return {"ok": True}
