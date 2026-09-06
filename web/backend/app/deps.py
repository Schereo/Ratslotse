"""Request-scoped dependencies: DB stores and the authenticated user."""
from __future__ import annotations

from collections.abc import Callable, Iterator

from fastapi import Depends, HTTPException, Request, status

from .clients import client_kind
from .config import get_settings
from .security import decode_access_token

from kern import roles as rollen
from kern.store import Store
from council.store import CouncilStore


def get_store() -> Iterator[Store]:
    settings = get_settings()
    store = Store(settings.ratslotse_db)
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
    if not ist_admin(user) and user.get("status") != "active":
        return None
    return user


def require_active(user: dict = Depends(get_current_user)) -> dict:
    """Account must be active: email confirmed and not suspended by an admin
    (admins are always active)."""
    if not ist_admin(user) and user.get("status") != "active":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Bitte bestätige zuerst deine E-Mail-Adresse."
            if not user.get("email_verified")
            else "Dein Konto ist derzeit deaktiviert.",
        )
    return user


def require_admin(user: dict = Depends(require_active)) -> dict:
    """Adminrechte. Bewusst eigene Meldung statt `require_permission("admin")`
    — „Adminrechte erforderlich" sagt mehr als „Fehlende Berechtigung", und die
    ausgelieferte iOS-App zeigt den Text unverändert an."""
    if not ist_admin(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Adminrechte erforderlich.")
    return user


def require_permission(permission: str) -> Callable[[dict], dict]:
    """Eine Dependency, die genau EIN Recht verlangt.

    Der Rückgabewert ist selbst eine Dependency — gedacht als Modul-Konstante
    neben dem Router::

        require_budget = Depends(require_permission("budget"))

    Geprüft wird gegen das Recht, nie gegen einen Rollennamen: Welche Rollen
    das Recht tragen, steht in ``kern/roles.py`` und nur dort. Wer hier
    ``roles`` abfragte, müsste bei jeder neuen Rolle jeden Endpunkt anfassen.

    Die Prüfung setzt auf ``require_active`` auf: Ein gesperrtes oder
    unbestätigtes Konto kommt gar nicht erst bis hierher, und die 403-Meldung
    erklärt dann den echten Grund statt „fehlende Rechte".

    403, nicht 404: Wer angemeldet ist und das Recht nicht hat, soll erfahren,
    dass es die Fläche gibt und wem sie gehört. Die Frontends machen daraus
    ihre eigene Antwort (das Web ein 404 auf der Seite selbst).
    """
    if permission not in rollen.PERMISSIONS:
        # Ein Tippfehler im Rechtenamen ergäbe eine Dependency, die NIEMAND je
        # erfüllt — ein für alle gesperrter Endpunkt, der beim Start nichts
        # sagt. Deshalb hier, zur Importzeit, laut.
        raise ValueError(f"Unbekanntes Recht {permission!r} — bekannt: {rollen.PERMISSIONS}")

    def pruefen(user: dict = Depends(require_active)) -> dict:
        if permission not in rollen.permissions_for(user.get("roles")):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Dieser Bereich ist Ratsmitgliedern vorbehalten."
                if permission == "budget" else "Fehlende Berechtigung.",
            )
        return user

    # Der Name landet in Fehlermeldungen und — wichtiger — im Wächter
    # `tests/test_endpunkt_schutz.py`, der die Abhängigkeiten eines Endpunkts
    # über ihre `__name__` einsammelt. Ohne ihn hießen alle Rechteprüfungen
    # gleich („pruefen"), und man sähe der Liste nicht an, WELCHES Recht hängt.
    pruefen.__name__ = f"require_permission_{permission}"
    return pruefen


def ist_admin(user: dict | None) -> bool:
    """Ob dieses Konto die Adminrolle trägt — die eine Stelle, die das prüft."""
    return bool(user) and "admin" in rollen.known_roles(user.get("roles"))
