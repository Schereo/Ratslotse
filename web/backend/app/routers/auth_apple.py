"""Sign in with Apple (RL-1002): Identity-Token verifizieren, Konto verknüpfen.

Die native App holt über das Apple-SDK ein RS256-signiertes Identity-Token und
schickt es hierher. Verifiziert wird gegen Apples JWKS (Signatur, iss, aud,
exp); danach gilt:

- ``apple_sub`` bekannt → Anmeldung in dieses Konto.
- sonst: gleiche (von Apple bestätigte) E-Mail vorhanden → Konto verknüpfen —
  auch Private-Relay-Adressen sind normale Mailadressen.
- sonst: neues Konto, sofort aktiv (Apple bestätigt die Adresse), ohne eigenes
  Passwort (``password_set = 0``; über „Passwort vergessen" nachrüstbar).
"""
from __future__ import annotations

import json
import logging
import secrets
import time
import urllib.request

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from nwz.store import Store

from ..config import get_settings
from ..deps import get_store
from ..ratelimit import login_limiter
from ..schemas import UserOut
from ..security import decode_rs256_token, hash_password
from .auth import _app_access_token, _set_auth_cookie, _to_out

logger = logging.getLogger("nwz.web.auth_apple")

router = APIRouter(prefix="/api/auth", tags=["auth"])

APPLE_ISSUER = "https://appleid.apple.com"
APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"

# Apples Schlüssel rotieren selten — 24 h Cache erspart jedem Login den
# JWKS-Roundtrip; bei unbekannter kid wird einmal zwangs-erneuert.
_JWKS_CACHE: dict = {"at": 0.0, "keys": []}
_JWKS_TTL = 24 * 3600


class AppleLoginRequest(BaseModel):
    identity_token: str = Field(min_length=20)
    # Apple übermittelt den Namen NUR bei der ersten Autorisierung und NICHT im
    # signierten Token — er kommt daher ungeprüft vom Client. Das ist vertretbar,
    # weil ein Anzeigename keine Berechtigung trägt; er wird ausschließlich für
    # ein frisch angelegtes bzw. noch namenloses Konto übernommen (siehe unten).
    given_name: str = Field(default="", max_length=60)
    family_name: str = Field(default="", max_length=60)


def _fetch_jwks() -> list[dict]:
    req = urllib.request.Request(APPLE_JWKS_URL, headers={"User-Agent": "ratslotse-backend"})
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 — feste https-URL
        return json.loads(resp.read()).get("keys", [])


def _apple_keys(force: bool = False) -> list[dict]:
    now = time.time()
    if force or not _JWKS_CACHE["keys"] or now - _JWKS_CACHE["at"] > _JWKS_TTL:
        try:
            _JWKS_CACHE.update(at=now, keys=_fetch_jwks())
        except Exception as exc:  # noqa: BLE001
            logger.warning("Apple-JWKS nicht erreichbar: %r", exc)
            if not _JWKS_CACHE["keys"]:
                raise HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "Apple-Anmeldung derzeit nicht verfügbar — bitte später erneut versuchen.",
                ) from exc
    return _JWKS_CACHE["keys"]


def verify_apple_identity_token(identity_token: str) -> dict:
    """Signatur + iss/aud/exp prüfen; gibt die Token-Claims zurück (401 sonst)."""
    settings = get_settings()
    payload = decode_rs256_token(identity_token, _apple_keys())
    if payload is None:
        # kid evtl. frisch rotiert → einmal mit erzwungenem JWKS-Refresh.
        payload = decode_rs256_token(identity_token, _apple_keys(force=True))
    if payload is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Apple-Anmeldung ungültig oder abgelaufen.")

    audiences = {settings.apple_bundle_id}
    if settings.apple_service_id:
        audiences.add(settings.apple_service_id)
    aud = payload.get("aud")
    aud_ok = aud in audiences or (isinstance(aud, list) and any(a in audiences for a in aud))
    if payload.get("iss") != APPLE_ISSUER or not aud_ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Apple-Anmeldung ungültig oder abgelaufen.")
    if not payload.get("sub"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Apple-Anmeldung ungültig oder abgelaufen.")
    return payload


@router.post("/apple", response_model=UserOut)
def apple_login(
    request: Request,
    body: AppleLoginRequest,
    response: Response,
    store: Store = Depends(get_store),
) -> UserOut:
    login_limiter.check(request)
    settings = get_settings()
    claims = verify_apple_identity_token(body.identity_token)
    sub = str(claims["sub"])
    # Nur die E-Mail aus dem signierten Token zählt — eine Client-Angabe wäre
    # fälschbar und würde fremde Konten verknüpfbar machen.
    email = str(claims.get("email") or "").lower().strip()
    apple_name = " ".join(p for p in (body.given_name.strip(), body.family_name.strip()) if p)[:60]

    user = store.get_web_user_by_apple_sub(sub)
    if user is None and email:
        existing = store.get_web_user_by_email(email)
        if existing:
            # Verknüpfen: gleiche, von Apple bestätigte Adresse. Apple bestätigt
            # damit auch die Mailbox — ein evtl. offener Verifizierungs-Schwebezustand
            # ist erledigt.
            store.link_apple_sub(existing["id"], sub)
            if not existing.get("email_verified"):
                store.set_email_verified(existing["id"])
            if existing.get("status") == "pending":
                store.set_web_user_status(existing["id"], "active")
            user = store.get_web_user_by_id(existing["id"])
            logger.info("Apple-Konto mit bestehendem Konto %s verknüpft", existing["id"])
    if user is None:
        if not email:
            # Ohne sub-Treffer UND ohne E-Mail-Claim können wir kein Konto
            # zuordnen. Passiert praktisch nur, wenn die App-Berechtigung auf
            # Apple-Seite verwaist ist — dort lösen und neu autorisieren.
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Apple hat keine E-Mail-Adresse übermittelt. Bitte entferne Ratslotse in den "
                "Apple-ID-Einstellungen unter „Mit Apple anmelden“ und versuche es erneut.",
            )
        # Neues Konto: Apple bestätigt die Adresse → sofort aktiv; Platzhalter-
        # Passwort (nicht anmeldbar), bis über den Reset-Weg eines gesetzt wird.
        is_admin = email == settings.web_admin_email.lower() or store.count_web_users() == 0
        user_id = store.create_web_user(
            email, hash_password(secrets.token_urlsafe(32)),
            "admin" if is_admin else "user", "active", email_verified=True,
        )
        store.set_delivery_channel(user_id, "email")
        store.link_apple_sub(user_id, sub, password_set=False)
        if apple_name:
            store.set_display_name(user_id, apple_name)
        user = store.get_web_user_by_id(user_id)
        logger.info("Neues Konto %s über Apple erstellt", user_id)

    # Nachtrag für Konten, die vor „name" im Scope entstanden sind: Wer sich
    # bei Apple neu autorisiert, liefert den Namen noch einmal — aber nur füllen,
    # nie überschreiben, sonst ersetzte der Apple-Name einen selbst gewählten.
    if apple_name and not (user.get("display_name") or "").strip():
        store.set_display_name(user["id"], apple_name)
        user = store.get_web_user_by_id(user["id"])

    _set_auth_cookie(response, user)
    return _to_out(user, _app_access_token(request, user))
