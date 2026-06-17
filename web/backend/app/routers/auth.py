"""Registration, login, logout, current user."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from nwz.store import Store

from ..config import get_settings
from ..deps import get_current_user, get_store
from ..ratelimit import login_limiter, register_limiter
from ..schemas import LoginRequest, RegisterRequest, UserOut
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_NAME = "access_token"


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


def _to_out(user: dict) -> UserOut:
    return UserOut(
        id=user["id"],
        email=user["email"],
        role=user["role"],
        status=user.get("status", "active"),
        telegram_chat_id=user.get("telegram_chat_id"),
        linked=bool(user.get("telegram_chat_id")),
        nwz_verified=bool(user.get("nwz_verified_at")),
        nwz_username=user.get("nwz_username"),
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(
    request: Request,
    body: RegisterRequest,
    response: Response,
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
    user_id = store.create_web_user(email, hash_password(body.password), role, user_status)
    created_user = store.get_web_user_by_id(user_id)
    _set_auth_cookie(response, created_user)
    return _to_out(created_user)


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
    return _to_out(user)


@router.post("/logout")
def logout(response: Response) -> dict:
    settings = get_settings()
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, secure=settings.cookie_secure, samesite="lax")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)) -> UserOut:
    return _to_out(user)
