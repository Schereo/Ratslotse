"""Kalender-Abo: die Sitzungen eines Kontos als ICS-Feed (``kern/calendar_feed.py``).

Zwei angemeldete Endpunkte liefern die Adresse und erneuern sie; der Feed
selbst ist **öffentlich** und über das Token in der Adresse autorisiert —
anders geht ein Kalender-Abo nicht, Apple Kalender und Google kennen keine
Anmeldung. Das Token ist deshalb ein eigenes Geheimnis (kein Sitzungs-Token):
Wer die Adresse weitergibt, verrät seine Termine, nicht sein Konto, und
„Neu erzeugen" macht die alte Adresse sofort ungültig.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from council.store import CouncilStore
from kern.calendar_feed import build_feed
from kern.store import Store

from ..antworten import CALENDAR_ICS, CalendarResponse, CalendarSubscription
from ..config import get_settings
from ..deps import get_council_store, get_store, require_active

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


def _subscription(user: dict, store: Store) -> CalendarSubscription:
    token = store.calendar_token(user["id"])
    base = get_settings().app_base_url.rstrip("/")
    url = f"{base}/api/calendar/{token}.ics"
    return {
        "url": url,
        # webcal:// öffnet auf dem Telefon direkt den Abo-Dialog der
        # Kalender-App — https:// lüde die Datei nur einmal herunter.
        "webcal_url": "webcal://" + url.split("://", 1)[1],
        "subscribed_committees": len(store.get_subscriptions(user["id"])),
    }


@router.get("/subscription")
def subscription(
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> CalendarSubscription:
    """Die Kalender-Adresse dieses Kontos — beim ersten Aufruf angelegt."""
    return _subscription(user, store)


@router.post("/subscription/rotate")
def rotate_subscription(
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> CalendarSubscription:
    """Neue Adresse; die alte antwortet ab sofort mit 404."""
    store.rotate_calendar_token(user["id"])
    return _subscription(user, store)


@router.get("/{token}.ics", response_class=CalendarResponse, responses=CALENDAR_ICS)
def feed(
    token: str,
    store: Store = Depends(get_store),
    council: CouncilStore = Depends(get_council_store),
) -> Response:
    """Der Feed — öffentlich, autorisiert über das Token in der Adresse.
    Ein unbekanntes oder erneuertes Token und ein nicht aktives Konto sehen
    gleich aus (404), damit die Adresse nichts über Konten verrät."""
    user = store.user_by_calendar_token(token)
    if not user or user.get("status") != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Diese Kalender-Adresse gibt es nicht.")
    body = build_feed(
        user=user, council=council, ratslotse=store,
        base_url=get_settings().app_base_url.rstrip("/"),
    )
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Cache-Control": "private, max-age=1800",
            "Content-Disposition": 'inline; filename="ratslotse.ics"',
        },
    )
