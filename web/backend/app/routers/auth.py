"""Registration, login, logout, current user."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from nwz.store import Store

from ..config import get_settings
from ..deps import get_current_user, get_store
from ..schemas import LoginRequest, RegisterRequest, UserOut
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_NAME = "access_token"


def _set_auth_cookie(response: Response, user_id: int) -> None:
    settings = get_settings()
    token = create_access_token(user_id)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )


def _to_out(user: dict) -> UserOut:
    return UserOut(
        id=user["id"],
        email=user["email"],
        role=user["role"],
        telegram_chat_id=user.get("telegram_chat_id"),
        linked=bool(user.get("telegram_chat_id")),
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, response: Response, store: Store = Depends(get_store)) -> UserOut:
    settings = get_settings()
    email = str(body.email).lower().strip()
    if store.get_web_user_by_email(email):
        raise HTTPException(status.HTTP_409_CONFLICT, "E-Mail ist bereits registriert.")
    # First user, or the configured admin email, becomes admin.
    role = "admin" if (email == settings.web_admin_email.lower() or store.count_web_users() == 0) else "user"
    user_id = store.create_web_user(email, hash_password(body.password), role)
    _set_auth_cookie(response, user_id)
    return _to_out(store.get_web_user_by_id(user_id))


@router.post("/login", response_model=UserOut)
def login(body: LoginRequest, response: Response, store: Store = Depends(get_store)) -> UserOut:
    user = store.get_web_user_by_email(str(body.email))
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-Mail oder Passwort falsch.")
    _set_auth_cookie(response, user["id"])
    return _to_out(user)


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)) -> UserOut:
    return _to_out(user)
