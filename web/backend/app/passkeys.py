"""Passkeys zum Anmelden (WebAuthn) — die Prüfung, ohne Router.

Seit 11/2026 (Tims Wunsch: „Mit Passkey anmelden“ neben Passwort und Apple).
Der Server stellt die Challenge, merkt sie sich fünf Minuten und löst sie
genau einmal ein; er prüft Herkunft, RP-ID, Signatur, Nutzerverifikation und
Zähler mit ``py_webauthn`` gegen den öffentlichen Schlüssel aus
``web_passkeys``. Die Attestierung wird nicht verlangt (``none``) — wir
wollen wissen, dass es derselbe Passkey ist, nicht von welchem Hersteller.

**Die Notizen hängen am selben Passkey, aber nicht an diesem Modul.** Der
Browser fragt bei Registrierung und Anmeldung die Erweiterung PRF mit an; ihr
Ergebnis bleibt auf dem Gerät und schließt dort die Notizen auf
(``web/frontend/lib/passkey.ts``). Die Formen unten nehmen deshalb aus
``clientExtensionResults`` nichts an: Was der Browser dort mitschickt, wird
verworfen, bevor es irgendwo landet.

**RP-ID = Host der Seite**, wie bei den Notiz-Passkeys (dort setzt der
Browser sie von selbst) — sonst passten dieselben Passkeys nicht zu beidem.
Erlaubt sind die Herkunft aus ``APP_BASE_URL``, die aus ``CORS_ORIGINS`` und
lokal (``COOKIE_SECURE=false``) jedes ``localhost``.
"""
from __future__ import annotations

import base64
import json
import logging
import secrets
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from fastapi import HTTPException, Request, status
from webauthn import (generate_authentication_options, generate_registration_options, options_to_json,
                      verify_authentication_response, verify_registration_response)
from webauthn.helpers.structs import (AuthenticatorSelectionCriteria, AuthenticatorTransport,
                                      PublicKeyCredentialDescriptor, ResidentKeyRequirement,
                                      UserVerificationRequirement)

from kern.store import Store

from .config import get_settings

logger = logging.getLogger("ratslotse.web.passkeys")

RP_NAME = "Ratslotse"
CHALLENGE_TTL = timedelta(minutes=5)
TIMEOUT_MS = 120_000
#: Zwecke einer Challenge. Eine für die Anmeldung ausgestellte taugt nicht
#: zur Registrierung und umgekehrt.
ZWECKE = ("signup", "add", "login")

NICHT_BESTAETIGT = "Der Passkey ließ sich nicht bestätigen. Bitte versuch es noch einmal."
ABGELAUFEN = "Die Anfrage ist abgelaufen. Bitte versuch es noch einmal."


def b64url(roh: bytes) -> str:
    return base64.urlsafe_b64encode(roh).rstrip(b"=").decode()


def von_b64url(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _origin(url: str) -> str | None:
    teile = urlsplit(url or "")
    if teile.scheme not in ("http", "https") or not teile.hostname:
        return None
    return f"{teile.scheme}://{teile.netloc}".lower()


def _erlaubt(origin: str | None) -> bool:
    if not origin:
        return False
    settings = get_settings()
    erlaubt = {o for o in (_origin(settings.app_base_url), *(_origin(c) for c in settings.cors_origin_list)) if o}
    if origin in erlaubt:
        return True
    host = urlsplit(origin).hostname or ""
    return not settings.cookie_secure and host in ("localhost", "127.0.0.1")


def herkunft(request: Request) -> tuple[str, str]:
    """Herkunft und RP-ID für die Optionen: die Seite, von der die Anfrage
    kommt — wenn sie erlaubt ist, sonst die aus ``APP_BASE_URL``."""
    origin = _origin(request.headers.get("origin", ""))
    if not _erlaubt(origin):
        origin = _origin(get_settings().app_base_url) or "https://ratslotse.de"
    assert origin is not None
    return origin, urlsplit(origin).hostname or "ratslotse.de"


def _challenge_merken(store: Store, zweck: str, owner_id: int | None, payload: dict | None) -> bytes:
    roh = secrets.token_bytes(32)
    ablauf = (datetime.utcnow() + CHALLENGE_TTL).isoformat(timespec="seconds")
    store.put_webauthn_challenge(b64url(roh), zweck, ablauf, owner_id=owner_id, payload=payload)
    return roh


def _optionen(options: Any) -> dict[str, Any]:
    return json.loads(options_to_json(options))


def registrierungs_optionen(store: Store, request: Request, *, zweck: str, user_name: str,
                            display_name: str, user_handle: str, ausschliessen: list[str],
                            owner_id: int | None = None, payload: dict | None = None) -> dict[str, Any]:
    """``ausschliessen``: Kennungen, die das Gerät schon tragen könnte — es
    meldet sie dann als vorhanden, statt einen zweiten Passkey anzulegen oder
    einen alten still zu ersetzen."""
    _, rp_id = herkunft(request)
    challenge = _challenge_merken(store, zweck, owner_id, payload)
    return _optionen(generate_registration_options(
        rp_id=rp_id, rp_name=RP_NAME, user_name=user_name, user_display_name=display_name,
        user_id=von_b64url(user_handle), challenge=challenge, timeout=TIMEOUT_MS,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED, require_resident_key=True,
            user_verification=UserVerificationRequirement.REQUIRED),
        exclude_credentials=[PublicKeyCredentialDescriptor(id=von_b64url(c)) for c in ausschliessen],
    ))


def anmelde_optionen(store: Store, request: Request) -> dict[str, Any]:
    """Ohne ``allowCredentials``: Das Gerät bietet von selbst an, was es für
    diese Seite hat — niemand muss vorher seine Adresse tippen."""
    _, rp_id = herkunft(request)
    challenge = _challenge_merken(store, "login", None, None)
    return _optionen(generate_authentication_options(
        rp_id=rp_id, challenge=challenge, timeout=TIMEOUT_MS,
        user_verification=UserVerificationRequirement.REQUIRED))


def _client_data(client_data_json: str) -> dict:
    try:
        daten = json.loads(von_b64url(client_data_json))
    except (ValueError, TypeError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, NICHT_BESTAETIGT) from None
    if not isinstance(daten, dict):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, NICHT_BESTAETIGT)
    return daten


def _einloesen(store: Store, client_data_json: str, zweck: str) -> tuple[bytes, str, dict]:
    """Die Challenge aus ``clientDataJSON`` einlösen — genau einmal. Gibt
    Challenge, Herkunft und den gemerkten Eintrag zurück."""
    daten = _client_data(client_data_json)
    origin = _origin(str(daten.get("origin") or ""))
    if not _erlaubt(origin):
        logger.info("Passkey: Herkunft nicht erlaubt (%s)", daten.get("origin"))
        raise HTTPException(status.HTTP_400_BAD_REQUEST, NICHT_BESTAETIGT)
    challenge = str(daten.get("challenge") or "")
    now = datetime.utcnow().isoformat(timespec="seconds")
    eintrag = store.take_webauthn_challenge(challenge, zweck, now) if challenge else None
    if eintrag is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, ABGELAUFEN)
    assert origin is not None
    return von_b64url(challenge), origin, eintrag


def registrierung_pruefen(store: Store, credential: dict, zweck: str) -> tuple[dict, dict]:
    """Prüft eine Registrierung und gibt (neuer Passkey, gemerkter Eintrag)
    zurück — gespeichert wird beim Aufrufer, der das Konto kennt."""
    challenge, origin, eintrag = _einloesen(store, credential["response"]["clientDataJSON"], zweck)
    try:
        ok = verify_registration_response(
            credential=credential, expected_challenge=challenge, expected_origin=origin,
            expected_rp_id=urlsplit(origin).hostname or "", require_user_verification=True)
    except Exception as exc:  # noqa: BLE001 — jede Abweichung ist dasselbe „nicht bestätigt"
        logger.info("Passkey-Registrierung abgewiesen: %s", exc)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, NICHT_BESTAETIGT) from None
    erlaubt = {t.value for t in AuthenticatorTransport}
    neu = {
        "credential_id": b64url(ok.credential_id),
        "public_key": b64url(ok.credential_public_key),
        "sign_count": ok.sign_count,
        "transports": [t for t in credential["response"].get("transports") or [] if t in erlaubt],
        "backed_up": ok.credential_backed_up,
    }
    return neu, eintrag


def anmeldung_pruefen(store: Store, credential: dict) -> dict:
    """Prüft eine Anmeldung und gibt die Zeile aus ``web_passkeys`` zurück
    (Zähler und letzte Nutzung schon nachgezogen)."""
    challenge, origin, _ = _einloesen(store, credential["response"]["clientDataJSON"], "login")
    passkey = store.get_web_passkey(str(credential.get("rawId") or credential.get("id") or ""))
    if passkey is None:
        # Ein Passkey, den wir nicht kennen — meist ein Notiz-Passkey ohne
        # öffentlichen Schlüssel oder einer, der im Konto entfernt wurde.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Diesen Passkey kennt Ratslotse nicht. Melde dich anders an "
                            "und füge ihn im Konto hinzu.")
    handle = credential["response"].get("userHandle")
    if handle and handle != passkey["user_handle"]:
        logger.info("Passkey-Anmeldung: userHandle passt nicht zu Passkey %s", passkey["id"])
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, NICHT_BESTAETIGT)
    try:
        ok = verify_authentication_response(
            credential=credential, expected_challenge=challenge, expected_origin=origin,
            expected_rp_id=urlsplit(origin).hostname or "",
            credential_public_key=von_b64url(passkey["public_key"]),
            credential_current_sign_count=int(passkey["sign_count"]), require_user_verification=True)
    except Exception as exc:  # noqa: BLE001
        logger.info("Passkey-Anmeldung abgewiesen (Passkey %s): %s", passkey["id"], exc)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, NICHT_BESTAETIGT) from None
    store.touch_web_passkey(int(passkey["id"]), ok.new_sign_count, ok.credential_backed_up)
    return {**passkey, "sign_count": ok.new_sign_count}
