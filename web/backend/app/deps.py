"""Request-scoped dependencies: DB stores and the authenticated user."""
from __future__ import annotations

from typing import Iterator

from fastapi import Depends, HTTPException, Request, status

from .clients import client_kind
from .config import get_settings
from .security import decode_access_token

from kern.store import Store
from council.store import CouncilStore
from buergerportal.reports import PrivateReportStore
from buergerportal.store import ProblemStore


def get_store() -> Iterator[Store]:
    settings = get_settings()
    store = Store(settings.ratslotse_db)
    try:
        yield store
    finally:
        store.close()


def get_problem_store() -> Iterator[ProblemStore]:
    """Öffentliche Problemprojektion in der aktuellen Ratslotse-Datenbank."""
    store = ProblemStore(get_settings().ratslotse_db)
    try:
        yield store
    finally:
        store.close()


def get_private_report_store() -> Iterator[PrivateReportStore]:
    """Privates Schreibmodell in der request-spezifischen Datenbankverbindung."""
    store = PrivateReportStore(get_settings().ratslotse_db)
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
    # Aktivität fürs Admin-Dashboard (20a): einmal je Request und Client,
    # tages-throttled über den PK. Best-effort — darf den Request nie brechen.
    store.record_activity(user["id"], "session", client_kind(request))
    return user


def optional_user(request: Request, store: Store = Depends(get_store)) -> dict | None:
    """Der angemeldete Nutzer — oder ``None`` statt 401.

    Für die Seiten, die geteilt werden. Ein weitergereichter Beschluss-Link soll
    sich lesen lassen, ohne dass die Empfängerin erst ein Konto anlegt; wer
    angemeldet ist, bekommt auf derselben Seite trotzdem die persönlichen
    Zusätze (folge ich diesem Vorgang schon?).

    Bewusst dieselbe Schwelle wie ``require_active``: Ein unbestätigtes oder
    gesperrtes Konto gilt hier als *nicht angemeldet* und sieht die öffentliche
    Fassung. Sonst wäre das hier ein stiller Seiteneingang an der Sperre vorbei.
    """
    if not _token_from_request(request):
        return None
    try:
        user = get_current_user(request, store)
    except HTTPException:
        return None
    if user.get("role") != "admin" and user.get("status") != "active":
        return None
    return user


def require_active(user: dict = Depends(get_current_user)) -> dict:
    """Account must be active: email confirmed and not suspended by an admin
    (admins are always active)."""
    if user.get("role") != "admin" and user.get("status") != "active":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Bitte bestätige zuerst deine E-Mail-Adresse."
            if not user.get("email_verified")
            else "Dein Konto ist derzeit deaktiviert.",
        )
    return user


def require_verified_reporter(user: dict = Depends(require_active)) -> dict:
    """Nur aktive, bestätigte Nicht-Admin-Konten dürfen privat melden."""
    if (
        user.get("role") == "admin"
        or user.get("status") != "active"
        or not user.get("email_verified")
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Dieses Konto kann keine privaten Meldungen abgeben.",
        )
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Adminrechte erforderlich.")
    return user
