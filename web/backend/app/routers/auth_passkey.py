"""Mit Passkey registrieren und anmelden; Passkeys im Konto (seit 11/2026).

Die Prüfung selbst steht in ``app/passkeys.py``. Hier geht es um Konten:

- **Registrieren** läuft durch dieselben Prüfungen wie mit Passwort (Name,
  Wegwerf-Adresse, Dublette — ``auth.anmeldedaten_pruefen``) und legt das
  Konto genauso an: unbestätigt, bis Link oder Code aus der Mail eingelöst
  sind (Tims Entscheidung 11.11.2026). Im Passwort-Hash steht ein Zufallswert;
  das Konto gilt als passwortlos wie ein Apple-Konto, ein Passwort lässt sich
  über „Passwort vergessen“ nachrüsten.
- **Anmelden** fragt keine Adresse ab: Das Gerät bietet an, was es für diese
  Seite hat, und der Passkey sagt selbst, zu welchem Konto er gehört.
- **Im Konto** braucht Hinzufügen und Entfernen eine volle Anmeldung (kein
  Anmeldelink); ein neuer Passkey meldet sich per Mail an die bestätigte
  Adresse — wer eine offen liegende Sitzung nutzt, um sich einen Weg zurück
  ins Konto zu legen, bleibt so nicht unbemerkt. Der letzte Weg ins Konto
  (kein Passwort, kein Apple, nur dieser Passkey) lässt sich nicht entfernen.

Alles steht hinter dem Schalter ``passkey-anmeldung`` (aus: 404).
"""
from __future__ import annotations

import html as _html
import logging
import secrets
import sqlite3

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from kern import features
from kern.digest_email import knopf, render_html_email
from kern.email import send_email
from kern.store import Store

from ..antworten import AccountPasskey, AccountPasskeyList, PasskeyOptions
from ..config import get_settings
from ..deps import get_store, require_active, require_volle_anmeldung
from ..mailprotokoll import protokolliere
from ..passkeys import anmelde_optionen, anmeldung_pruefen, b64url, registrierung_pruefen, registrierungs_optionen
from ..ratelimit import login_limiter, reauth_limiter, register_limiter
from ..schemas import (PasskeyAddRequest, PasskeyLoginRequest, PasskeySignupOptionsRequest, PasskeySignupRequest,
                       UserOut)
from ..security import hash_password
from .auth import _app_access_token, _set_auth_cookie, _to_out, anmeldedaten_pruefen, konto_anlegen

logger = logging.getLogger("ratslotse.web.auth_passkey")

router = APIRouter(prefix="/api/auth/passkey", tags=["auth"])
account_router = APIRouter(prefix="/api/account/passkeys", tags=["account"])

SCHALTER = "passkey-anmeldung"
#: Mehr braucht niemand für die eigenen Geräte.
MAX_PASSKEYS = 10
SCHON_DA = "Diesen Passkey gibt es schon."


def _an() -> None:
    if not features.an(SCHALTER):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nicht gefunden.")


def _liste(store: Store, owner_id: int) -> AccountPasskeyList:
    notizen = {p["credential_id"] for p in store.get_note_passkeys(owner_id)}
    eintraege: list[AccountPasskey] = [{
        "id": int(p["id"]), "credential_id": p["credential_id"], "label": p["label"],
        "created_at": p["created_at"], "last_used_at": p["last_used_at"],
        "backed_up": bool(p["backed_up"]), "notes": p["credential_id"] in notizen,
    } for p in store.list_web_passkeys(owner_id)]
    return {"passkeys": eintraege}


# ---- Registrieren und anmelden -------------------------------------------------

@router.post("/signup/options", responses={409: {"description": "Adresse schon registriert"}})
def signup_options(request: Request, body: PasskeySignupOptionsRequest,
                   store: Store = Depends(get_store)) -> PasskeyOptions:
    """Die Prüfungen der Registrierung VOR der Abfrage am Gerät — wer eine
    vergebene Adresse tippt, soll nicht erst Face ID bemühen müssen."""
    _an()
    try:
        register_limiter.check(request)
    except HTTPException:
        store.record_signup_rejection("rate_limit")
        raise
    geprueft = anmeldedaten_pruefen(request, store, str(body.email), body.display_name)
    if isinstance(geprueft, JSONResponse):
        return geprueft  # pyright: ignore[reportReturnType] — wie /api/health
    email, name = geprueft
    # Eine neue, zufällige Kennung: Das Konto gibt es noch nicht.
    handle = b64url(secrets.token_bytes(16))
    return {"public_key": registrierungs_optionen(
        store, request, zweck="signup", user_name=email, display_name=name, user_handle=handle,
        ausschliessen=[], payload={"email": email, "display_name": name, "user_handle": handle})}


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED,
             responses={409: {"description": "Adresse oder Passkey schon vergeben"}})
def signup(request: Request, body: PasskeySignupRequest, response: Response, background: BackgroundTasks,
           store: Store = Depends(get_store)) -> UserOut:
    _an()
    login_limiter.check(request)
    neu, eintrag = registrierung_pruefen(store, body.credential.model_dump(), "signup")
    daten = eintrag["payload"]
    email, name, handle = str(daten.get("email") or ""), str(daten.get("display_name") or ""), str(daten.get("user_handle") or "")
    if not (email and name and handle):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Die Anfrage ist unvollständig. Bitte noch einmal.")
    # Zwischen Optionen und Abschluss liegen bis zu fünf Minuten.
    if store.get_web_user_by_email(email):
        raise HTTPException(status.HTTP_409_CONFLICT, "E-Mail ist bereits registriert.")
    if store.get_web_passkey(neu["credential_id"]):
        raise HTTPException(status.HTTP_409_CONFLICT, SCHON_DA)
    try:
        user = konto_anlegen(request, background, store, email, name,
                             hash_password(secrets.token_urlsafe(32)), mit_passwort=False)
    except sqlite3.IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "E-Mail ist bereits registriert.") from None
    store.add_web_passkey(int(user["id"]), neu["credential_id"], neu["public_key"], neu["sign_count"], handle,
                          neu["transports"], neu["backed_up"], body.label.strip())
    _set_auth_cookie(response, user, request)
    return _to_out(user, _app_access_token(request, user))


@router.post("/login/options")
def login_options(request: Request, store: Store = Depends(get_store)) -> PasskeyOptions:
    """Auch für die Bestätigung beim Löschen und beim Adresswechsel."""
    _an()
    login_limiter.check(request)
    return {"public_key": anmelde_optionen(store, request)}


@router.post("/login", response_model=UserOut, responses={401: {"description": "Passkey unbekannt oder ungültig"}})
def login(request: Request, body: PasskeyLoginRequest, response: Response,
          store: Store = Depends(get_store)) -> UserOut:
    _an()
    login_limiter.check(request)
    passkey = anmeldung_pruefen(store, body.credential.model_dump())
    user = store.get_web_user_by_id(int(passkey["owner_id"]))
    if user is None:  # pragma: no cover — die Löschung räumt web_passkeys mit
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Konto nicht gefunden.")
    _set_auth_cookie(response, user, request)
    return _to_out(user, _app_access_token(request, user))


# ---- Im Konto ------------------------------------------------------------------

@account_router.get("")
def list_passkeys(user: dict = Depends(require_active), store: Store = Depends(get_store)) -> AccountPasskeyList:
    _an()
    return _liste(store, int(user["id"]))


@account_router.post("/options", dependencies=[Depends(require_volle_anmeldung)],
                     responses={409: {"description": "Höchstzahl erreicht"}})
def add_options(request: Request, user: dict = Depends(require_active),
                store: Store = Depends(get_store)) -> PasskeyOptions:
    _an()
    reauth_limiter.check(request, subject=user["id"])
    owner = int(user["id"])
    vorhanden = store.list_web_passkeys(owner)
    if len(vorhanden) >= MAX_PASSKEYS:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Höchstens {MAX_PASSKEYS} Passkeys je Konto.")
    # Auch die Notiz-Passkeys: Mit derselben Kennung ersetzte das Gerät einen
    # davon sonst still — und die Notizen verlören ihren Schlüssel.
    ausschliessen = sorted({p["credential_id"] for p in vorhanden}
                           | {p["credential_id"] for p in store.get_note_passkeys(owner)})
    handle = store.passkey_user_handle(owner)
    return {"public_key": registrierungs_optionen(
        store, request, zweck="add", user_name=str(user["email"]),
        display_name=str(user.get("display_name") or user["email"]), user_handle=handle,
        ausschliessen=ausschliessen, owner_id=owner, payload={"user_handle": handle})}


@account_router.post("", dependencies=[Depends(require_volle_anmeldung)],
                     responses={409: {"description": "Passkey schon vorhanden"}})
def add_passkey(request: Request, body: PasskeyAddRequest, background: BackgroundTasks,
                user: dict = Depends(require_active), store: Store = Depends(get_store)) -> AccountPasskeyList:
    _an()
    reauth_limiter.check(request, subject=user["id"])
    owner = int(user["id"])
    neu, eintrag = registrierung_pruefen(store, body.credential.model_dump(), "add")
    if eintrag["owner_id"] != owner:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Die Anfrage gehört zu einem anderen Konto.")
    if store.get_web_passkey(neu["credential_id"]):
        raise HTTPException(status.HTTP_409_CONFLICT, SCHON_DA)
    handle = str(eintrag["payload"].get("user_handle") or store.passkey_user_handle(owner))
    label = body.label.strip()
    store.add_web_passkey(owner, neu["credential_id"], neu["public_key"], neu["sign_count"], handle,
                          neu["transports"], neu["backed_up"], label)
    if user.get("email_verified"):
        background.add_task(_send_passkey_notice, str(user["email"]), label, user.get("display_name"), owner)
    return _liste(store, owner)


@account_router.delete("/{passkey_id}", dependencies=[Depends(require_volle_anmeldung)],
                       responses={404: {"description": "Unbekannt"}, 409: {"description": "Letzter Weg ins Konto"}})
def delete_passkey(passkey_id: int, request: Request, user: dict = Depends(require_active),
                   store: Store = Depends(get_store)) -> AccountPasskeyList:
    """Nur die Anmeldung — schließt derselbe Passkey auch die Notizen auf,
    bleibt das (dort entfernen)."""
    _an()
    reauth_limiter.check(request, subject=user["id"])
    owner = int(user["id"])
    ergebnis = store.delete_web_passkey(owner, passkey_id)
    if ergebnis == "fehlt":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Diesen Passkey gibt es nicht.")
    if ergebnis == "letzter":
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Das ist dein einziger Weg ins Konto. Leg vorher einen weiteren Passkey "
                            "oder über „Passwort vergessen“ ein Passwort an.")
    return _liste(store, owner)


def _send_passkey_notice(email: str, label: str, display_name: str | None, owner_id: int) -> None:
    """Background task: Hinweis, dass ein Passkey zum Anmelden dazukam."""
    settings = get_settings()
    if not settings.resend_api_key:
        return
    konto_url = f"{settings.app_base_url.rstrip('/')}/account"
    subject = "Ratslotse – neuer Passkey für dein Konto"
    geraet = f" ({_html.escape(label)})" if label else ""
    body = render_html_email(
        subject,
        f"<p style='margin:0'>Für dein Ratslotse-Konto wurde gerade ein Passkey{geraet} "
        "hinzugefügt. Mit ihm kann man sich ohne Passwort anmelden.</p>"
        "<p style='margin:10px 0 0'><b>Warst du das nicht?</b> Dann entferne ihn in deinem "
        "Konto und ändere dein Passwort.</p>"
        + knopf(konto_url, "Zum Konto"),
        anlass="passkey_added",
        greeting_name=display_name,
        held="passwort",
        kicker="Dein Konto",
        title="Neuer Passkey",
        fusszeile="Diese E-Mail kommt bei jedem neuen Passkey, damit dir keiner entgeht.",
    )
    text = (
        f"Für dein Ratslotse-Konto wurde gerade ein Passkey{(' (' + label + ')') if label else ''} hinzugefügt.\n\n"
        f"Warst du das nicht? Dann entferne ihn in deinem Konto und ändere dein Passwort: {konto_url}\n"
    )
    try:
        mid = send_email(email, subject, body, text=text,
                         api_key=settings.resend_api_key, sender=settings.email_from)
        protokolliere(owner_id, "passkey_added", subject, message_id=mid)
    except Exception:  # noqa: BLE001 — ein Hinweis, kein Muss
        logger.exception("passkey notice failed for %s", email)
        protokolliere(owner_id, "passkey_added", subject, ok=False)
