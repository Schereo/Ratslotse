"""Request-scoped dependencies: DB stores and the authenticated user."""
from __future__ import annotations

from typing import Iterator

from fastapi import Depends, HTTPException, Request, status

from .config import get_settings
from .security import decode_access_token

from nwz.store import Store
from council.store import CouncilStore


def get_store() -> Iterator[Store]:
    settings = get_settings()
    store = Store(settings.nwz_db)
    try:
        yield store
    finally:
        store.close()


def get_council_store() -> Iterator[CouncilStore]:
    settings = get_settings()
    store = CouncilStore(settings.council_db)
    try:
        yield store
    finally:
        store.close()


def _token_from_request(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.cookies.get("access_token")


def get_current_user(request: Request, store: Store = Depends(get_store)) -> dict:
    token = _token_from_request(request)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Nicht angemeldet.")
    decoded = decode_access_token(token)
    if not decoded:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sitzung ungültig oder abgelaufen.")
    sub, token_version = decoded
    user = store.get_web_user_by_id(int(sub))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Konto nicht gefunden.")
    if token_version != user.get("token_version", 0):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sitzung wurde beendet. Bitte neu anmelden.")
    return user


def require_active(user: dict = Depends(get_current_user)) -> dict:
    """Account must be approved by an admin (admins are always active)."""
    if user.get("role") != "admin" and user.get("status") != "active":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Dein Konto wartet noch auf Freischaltung.",
        )
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Adminrechte erforderlich.")
    return user
