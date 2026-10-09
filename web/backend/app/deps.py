"""Request-scoped dependencies: DB stores and the authenticated user."""
from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from datetime import date

from fastapi import Depends, HTTPException, Request, status

from .clients import client_kind
from .config import get_settings
from .security import decode_access_token

from kern import roles as rollen
from kern.store import Store
from council.cities.store import CitiesStore
from council.store import CouncilStore


def get_store() -> Iterator[Store]:
    settings = get_settings()
    # `einmal`: Schema nur beim ersten Öffnen je Prozess einrichten
    # (kern/einrichtung.py) — die Einrichtung kostete je Anfrage mehr als
    # die meisten Antworten selbst.
    store = Store(settings.ratslotse_db, einmal=True)
    try:
        yield store
    finally:
        store.close()


def get_council_store() -> Iterator[CouncilStore]:
    settings = get_settings()
    store = CouncilStore(settings.council_db, einmal=True)
    try:
        yield store
    finally:
        store.close()


def get_cities_store() -> Iterator[CitiesStore]:
    """Der Städte-Speicher. Legt die Datei leer an, wenn es sie nicht gibt —
    ein Endpunkt, der ihn liest, antwortet dann mit leeren Listen statt mit
    einem Fehler."""
    settings = get_settings()
    store = CitiesStore(settings.cities_db)
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
    # Aktivität fürs Admin-Dashboard (20a). Best-effort — darf den Request
    # nie brechen, und seit 10/2026 auch nicht mehr aufhalten (s. unten).
    _sitzung_zaehlen(store, user["id"], client_kind(request))
    return user


# Der Sitzungs-Zähler schrieb bis 10/2026 bei JEDER angemeldeten Anfrage in
# ratslotse.sqlite — mit Commit. Eine Seite schickt 11–19 Anfragen; hielt
# irgendwer die Schreibsperre (ein Cron, eine Löschung), wartete jede davon
# den vollen busy_timeout von 5 s ab, und der Threadpool lief voll. Gemessen
# am 09.10.2026: angemeldete Beschluss-Seite 5,4 s, anonyme daneben 6,0 s.
#
# Jetzt: Die erste Anfrage je Konto/Tag/Client schreibt sofort (damit „heute
# aktiv" stimmt), danach höchstens einmal je Minute, mit dem aufgelaufenen
# Zähler. Ist die Datei gesperrt, wird nicht gewartet, sondern nachgetragen.
_SITZUNG_TAKT_S = 60.0
_sitzung_sperre = threading.Lock()
_sitzung_offen: dict[tuple[int, str, str], int] = {}
_sitzung_zuletzt: dict[tuple[int, str, str], float] = {}


def sitzungen_vergessen() -> None:
    """Für Tests: Drosselung zurücksetzen."""
    with _sitzung_sperre:
        _sitzung_offen.clear()
        _sitzung_zuletzt.clear()


def _sitzung_zaehlen(store: Store, owner_id: int, client: str) -> None:
    tag = date.today().isoformat()
    key = (owner_id, tag, client)
    jetzt = time.monotonic()
    with _sitzung_sperre:
        n = _sitzung_offen.pop(key, 0) + 1
        if jetzt - _sitzung_zuletzt.get(key, -_SITZUNG_TAKT_S) < _SITZUNG_TAKT_S:
            _sitzung_offen[key] = n
            return
        _sitzung_zuletzt[key] = jetzt
        # Gestrige Schlüssel räumen, sonst wächst das über Wochen.
        if len(_sitzung_zuletzt) > 5000:
            for k in [k for k in _sitzung_zuletzt if k[1] != tag]:
                _sitzung_zuletzt.pop(k, None)
                _sitzung_offen.pop(k, None)
    if not store.record_activity(owner_id, "session", client, anzahl=n, warten=False):
        with _sitzung_sperre:
            _sitzung_offen[key] = _sitzung_offen.get(key, 0) + n


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
        # Der Text hängt am STATUS, nicht mehr am Umkehrschluss über
        # `email_verified`: `disabled` sagt selbst, dass ein Admin
        # abgeschaltet hat. Ein Konto aus der Zeit vor dieser Trennung, das
        # die Migration nicht erwischt hat, fällt in den zweiten Zweig — auch
        # dann steht dort nicht die falsche Aufforderung.
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Bitte bestätige zuerst deine E-Mail-Adresse."
            if user.get("status") == "pending" and not user.get("email_verified")
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
