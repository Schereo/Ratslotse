"""Account self-service: delivery channel, password, account deletion."""
from __future__ import annotations

import hashlib
import logging
import secrets
import sqlite3
from datetime import datetime, timedelta

from pydantic import BaseModel, Field
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status

from kern.digest_email import render_html_email
from kern.email import send_email
from kern.store import Store
from council.store import CouncilStore

from ..config import get_settings
from ..antworten import NotifySettings, Ok, TestDelivery
from ..deps import get_council_store, get_current_user, get_store, ist_admin, require_active
from ..ratelimit import change_email_limiter
from ..schemas import (ChangeEmailRequest, ChangePasswordRequest, DeleteAccountRequest,
                       DeliveryUpdate, NotifyPrefsIn, UserOut)
from ..security import hash_password, verify_password
from .auth import (_VERIFY_TTL_HOURS, _app_access_token, _send_email_change_link,
                   _send_email_change_notice, _set_auth_cookie, _to_out)

logger = logging.getLogger("ratslotse.web.account")

router = APIRouter(prefix="/api/account", tags=["account"])


def _send_goodbye_email(email: str) -> None:
    """Best-effort: schriftliche Bestätigung der Löschung (Nachweis für die
    Person, Warnung bei Fremdauslösung). Läuft nach der Löschung — ein
    Mail-Fehler ändert nichts mehr."""
    settings = get_settings()
    if not settings.resend_api_key or not email or email.endswith("@local"):
        return
    body = render_html_email(
        "Konto gelöscht",
        "<p style='margin:0'>Dein Ratslotse-Konto und alle zugehörigen Daten "
        "(Themen, Treffer, Abos, Geräte) wurden endgültig gelöscht.</p>"
        "<p style='margin:10px 0 0'>Danke, dass du dabei warst — du bist jederzeit "
        "wieder willkommen.</p>",
        held="abschied",
        kicker="Dein Konto",
        title="Tschüss — und danke!",
        fusszeile="Falls du diese Löschung nicht selbst ausgelöst hast, "
                  "antworte bitte umgehend auf diese E-Mail.",
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


def _frisch(store: Store, user_id: int) -> dict:
    """Das Konto neu aus der Datenbank — mit gesicherter Nicht-Null-Zusage.

    ``get_web_user_by_id`` gibt ``dict | None`` zurück. Hier kann es nicht
    ``None`` sein: Der Request ist durch ``get_current_user`` gekommen, die
    Zeile lag also gerade noch vor. Bliebe sie offen, schleppte jeder Aufrufer
    einen Fall mit, den es nicht gibt — und pyright zählte ihn mit.
    """
    konto = store.get_web_user_by_id(user_id)
    if konto is None:  # pragma: no cover — nur bei Löschung mitten im Request
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Konto nicht gefunden.")
    return konto


def _reauth(user: dict, current_password: str, apple_identity_token: str) -> None:
    """Frische Bestätigung der Identität — oder ``HTTPException``.

    Der gemeinsame Kern von „Konto löschen" und „Adresse ändern": Beides sind
    Schritte, die eine offen liegende Sitzung allein nicht auslösen können
    darf (fremdes Gerät, gestohlenes Cookie). Konten mit Passwort bestätigen
    mit dem Passwort, Apple-only-Konten mit einem frischen Apple-Identity-Token,
    dessen ``sub`` zu genau diesem Konto gehören muss.

    Der Widerruf der Apple-Autorisierung gehört NICHT hierher — er ist nur beim
    Löschen richtig, und ein Adresswechsel würde damit die Anmeldung kappen.
    """
    if apple_identity_token and user.get("apple_sub"):
        from .auth_apple import verify_apple_identity_token
        claims = verify_apple_identity_token(apple_identity_token)
        if str(claims.get("sub")) != str(user["apple_sub"]):
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                "Apple-Bestätigung gehört zu einem anderen Konto.")
        return
    if not verify_password(current_password, user["password_hash"]):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Aktuelles Passwort ist falsch." if user.get("password_set", 1)
            else "Dieses Konto nutzt Apple — bitte in der App per Apple bestätigen "
                 "oder zuerst über „Passwort vergessen“ ein Passwort setzen.")


class DisplayNameIn(BaseModel):
    display_name: str | None = Field(default=None, max_length=60)


@router.post("/display-name")
def set_display_name(
    body: DisplayNameIn,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> Ok:
    """Anzeigename setzen/ändern — auch für Apple-Konten und Alt-Bestand,
    die bei der Registrierung keinen angeben konnten."""
    store.set_display_name(user["id"], body.display_name)
    return {"ok": True}


@router.put("/delivery", response_model=UserOut)
def set_delivery(
    body: DeliveryUpdate,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> UserOut:
    """Wohin Benachrichtigungen gehen: ``email``, ``push``, ``both`` — oder
    ``off`` für gar nicht.

    ``off`` räumt zusätzlich die Warteschlange leer. Was dort liegt, war für
    ein Einverständnis gedacht, das gerade widerrufen wurde; es später
    nachzuliefern wäre genau das, was man mit dem Abschalten verhindern wollte.
    """
    channel = body.delivery_channel
    if channel in ("email", "both"):
        email = str(user.get("email", ""))
        if email.startswith("tg-") and email.endswith("@local"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Keine E-Mail-Adresse hinterlegt.")
    store.set_delivery_channel(user["id"], channel)
    if channel == "off":
        store.drop_pending_notifications(user["id"])
    return _to_out(store.get_web_user_by_id(user["id"]))


@router.get("/notifications")
def get_notifications(
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> NotifySettings:
    """Was diese Person wovon hören will (Design 30a/E).

    Liefert die Anlässe mitsamt Beschriftung und Vorgabe, damit die Oberfläche
    keine zweite Liste pflegen muss — eine vergessene Art fällt sonst erst auf,
    wenn sich jemand über eine unabschaltbare Meldung ärgert.
    """
    from kern.notify import (NACHTRUHE_AB, NACHTRUHE_BIS, NOTIFY_DEFAULTS,
                             NOTIFY_LABELS, NOTIFY_PARENT, TAGESGRENZE, vorgaben_fuer)

    gesetzt = store.get_notify_prefs(user["id"])
    # Vorgaben je Konto, nicht je Deployment: Ein Ratsmandat schaltet die
    # Tagesordnungen ab Werk an (kern.notify.vorgaben_fuer).
    vorgaben = vorgaben_fuer(store, user["id"])
    return {
        "kinds": [
            {"key": k, "label": NOTIFY_LABELS[k][0], "hint": NOTIFY_LABELS[k][1],
             "default": vorgaben[k], "enabled": bool(gesetzt.get(k, vorgaben[k])),
             # Unter-Option: wirkt nur, solange der Eltern-Anlass an ist — die
             # Oberfläche rückt sie ein und graut sie entsprechend aus.
             "parent": NOTIFY_PARENT.get(k)}
            for k in NOTIFY_DEFAULTS
        ],
        "limits": {"per_day": TAGESGRENZE, "quiet_from": NACHTRUHE_AB, "quiet_to": NACHTRUHE_BIS},
    }


@router.put("/notifications")
def set_notifications(
    body: NotifyPrefsIn,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> NotifySettings:
    store.set_notify_prefs(user["id"], body.prefs)
    return get_notifications(user=user, store=store)


@router.post("/change-password", response_model=UserOut)
def change_password(
    request: Request,
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
    # Browser bekommen weiter nur das httpOnly-Cookie. Native Clients brauchen
    # nach der token_version-Erhöhung sofort einen neuen Bearer-Token; der alte
    # ist ab dieser Zeile absichtlich ungültig.
    return _to_out(updated, _app_access_token(request, updated))


@router.post("/change-email", response_model=UserOut)
def change_email(
    request: Request,
    body: ChangeEmailRequest,
    background: BackgroundTasks,
    # Bewusst `get_current_user` statt `require_active`: Der häufigste echte
    # Fall ist der Tippfehler bei der Registrierung — also genau das
    # unbestätigte Konto, das `require_active` aussperrt. Der Status wird
    # deshalb hier von Hand geprüft.
    user: dict = Depends(get_current_user),
    store: Store = Depends(get_store),
) -> UserOut:
    """Einen Adresswechsel anstoßen: Passwort jetzt, Link an die neue Adresse.

    Bis der Link geklickt ist, ändert sich **nichts** — Anmeldung,
    Benachrichtigungen und „Passwort vergessen“ laufen weiter über die
    bisherige Adresse. Das ist der Grund, warum die alte Adresse schon jetzt
    eine Warnung bekommt: Solange der Wechsel schwebt, kann sie das Konto noch
    selbst zurückholen.
    """
    change_email_limiter.check(request, subject=user["id"])
    # Unbestätigt darf wechseln (der Tippfehler bei der Registrierung),
    # abgeschaltet nicht. Seit die beiden Wartezustände getrennte Werte haben,
    # steht das hier als das, was es ist — vorher war es ein Umkehrschluss
    # über `email_verified`. Geprüft wird gegen „nicht aktiv und nicht
    # unbestätigt": Ein Konto, das die Migration auf `disabled` verfehlt hat,
    # bleibt damit ebenfalls draußen.
    if not ist_admin(user) and user.get("status") not in ("active", "pending"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Dein Konto ist derzeit deaktiviert.")
    if not ist_admin(user) and user.get("status") == "pending" and user.get("email_verified"):
        # Alt-Bestand vor der Trennung: bestätigt UND pending hieß abgeschaltet.
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Dein Konto ist derzeit deaktiviert.")
    _reauth(user, body.current_password, body.apple_identity_token)

    neu = str(body.new_email).lower().strip()
    alt = str(user.get("email", ""))
    if neu == alt:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Das ist bereits deine Adresse.")
    if neu.endswith("@local"):
        # `…@local` sind die synthetischen Adressen des Telegram-Altbestands.
        # Sie haben kein Postfach — ein Konto dorthin zu wechseln hieße, es
        # unerreichbar zu machen.
        #
        # Heute kommt hier nichts an: `EmailStr` weist eine Domain ohne Punkt
        # schon mit 422 ab. Der Riegel bleibt trotzdem stehen, weil die
        # Erreichbarkeit des Kontos nicht still an einer fremden
        # Validierungsregel hängen soll — er kostet nichts und beschreibt die
        # Absicht an der Stelle, an der sie gilt.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Diese Adresse ist nicht zulässig.")
    if store.get_web_user_by_email(neu):
        raise HTTPException(status.HTTP_409_CONFLICT, "E-Mail ist bereits registriert.")

    settings = get_settings()
    if not settings.resend_api_key:
        # Ohne Mail-Versand gibt es keinen Bestätigungslink — dieselbe Regel
        # wie bei der Registrierung (dort: `verified = not can_send_email`).
        # Sonst ließe sich der Wechsel auf dev, auf feature und in den
        # Browsertests überhaupt nicht ausprobieren.
        try:
            store.update_email(user["id"], neu)
        except sqlite3.IntegrityError:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                "E-Mail ist bereits registriert.") from None
        return _to_out(_frisch(store, user["id"]), _app_access_token(request, user))

    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    expires = (datetime.utcnow() + timedelta(hours=_VERIFY_TTL_HOURS)).isoformat(timespec="seconds")
    store.create_email_verification(int(user["id"]), token_hash, expires, new_email=neu)
    background.add_task(_send_email_change_link, neu, raw, user.get("display_name"))
    if alt and not alt.endswith("@local"):
        background.add_task(_send_email_change_notice, alt, neu, user.get("display_name"))
    return _to_out(user, _app_access_token(request, user), pending_email=neu)


@router.delete("/change-email", response_model=UserOut)
def cancel_change_email(
    request: Request,
    user: dict = Depends(get_current_user),
    store: Store = Depends(get_store),
) -> UserOut:
    """Einen schwebenden Adresswechsel verwerfen — der Link wird ungültig.

    Braucht keine erneute Bestätigung: Abbrechen stellt den Zustand her, der
    ohnehin gilt, und wer die Sitzung hat, könnte den Link sowieso nie
    einlösen (er liegt im fremden Postfach).
    """
    store.cancel_email_change(int(user["id"]))
    return _to_out(_frisch(store, user["id"]), _app_access_token(request, user))


@router.post("/test-notification")
def test_notification(
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> TestDelivery:
    """RL-702: Test-Benachrichtigung über die aktiven Kanäle — damit man prüfen
    kann, ob E-Mail/Push wirklich ankommen. Nutzt exakt den Cron-Versandpfad
    (deliver_message); ohne RESEND_API_KEY wird E-Mail still übersprungen."""
    from kern.delivery import deliver_message
    owner = {
        "email": user["email"],
        "delivery_channel": user.get("delivery_channel") or "email",
        "push_tokens": store.get_push_tokens_for_owner(user["id"]),
    }
    sent = deliver_message(
        owner,
        "<p>Moin! Das ist eine <b>Test-Benachrichtigung</b> von Ratslotse — "
        "genau so sehen Hinweise zu deinen Themen und Tagesordnungen aus.</p>",
        email_subject="Ratslotse – Test-Benachrichtigung",
    )
    return {"sent": sent}


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    body: DeleteAccountRequest,
    response: Response,
    background: BackgroundTasks,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
    council: CouncilStore = Depends(get_council_store),
) -> None:
    """Permanently delete the account and all data keyed to it (DSGVO right to
    erasure). Verlangt eine frische Bestätigung — eine Session allein (offener
    Laptop, gestohlenes Cookie) darf das Konto nicht zerstören können:
    Passwort-Konten bestätigen mit dem Passwort, Apple-only-Konten mit einem
    frischen Apple-Identity-Token (Re-Auth in der App, RL-1002).

    Geräumt werden **beide** Datenbanken. Zwischen ihnen gibt es keine
    Fremdschlüssel, und in ``council.sqlite`` steht mit
    ``committee_notifications``/``session_followups_sent``, welche Sitzungen
    diesem Konto gemeldet wurden — eine Verhaltensspur, die mit weg muss."""
    _reauth(user, body.current_password, body.apple_identity_token)
    # Nur beim Löschen: Apple die Autorisierung zurückgeben. Steht bewusst
    # außerhalb von `_reauth` — beim Adresswechsel würde derselbe Aufruf die
    # Anmeldung des Kontos kappen, das gerade weiterlaufen soll.
    if body.apple_identity_token and user.get("apple_sub") and body.apple_authorization_code:
        from .auth_apple import revoke_apple_authorization_code
        background.add_task(
            revoke_apple_authorization_code,
            body.apple_authorization_code,
            get_settings().apple_bundle_id,
        )
    email = str(user.get("email", ""))
    council.delete_owner_data(user["id"])
    store.delete_web_user(user["id"])
    background.add_task(_send_goodbye_email, email)
    settings = get_settings()
    response.delete_cookie("access_token", path="/", httponly=True,
                           secure=settings.cookie_secure, samesite="lax")
