"""Der Rückblick auf Ergänzungen seit dem letzten sichtbaren Besuch."""
from datetime import datetime, UTC
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from council.store import CouncilStore
from kern.store import Store
from ..antworten import TodayUpdates, VisitWindow
from ..deps import get_council_store, get_store, require_active

router = APIRouter(prefix="/api/today", tags=["today"])

#: So viele Einträge trägt die erste Seite des Rückblicks.
FIRST_PAGE_LIMIT = 3


@router.post("/visit")
def visit(user: dict = Depends(require_active), store: Store = Depends(get_store)) -> VisitWindow:
    store.record_visit(user["id"])
    return VisitWindow(**store.visit_window(user["id"]))


@router.post("/visit/updates")
def visit_with_updates(
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
    council: CouncilStore = Depends(get_council_store),
) -> TodayUpdates:
    """Besuch aufzeichnen und gleich die erste Seite des Rückblicks liefern.

    Dasselbe wie ``POST /visit`` und danach ``GET /updates``, nur in EINEM
    Aufruf: Der Rückblick auf „Heute" wartete sonst eine ganze Netzlaufzeit auf
    den POST, bevor er überhaupt fragen konnte. Die Reihenfolge bleibt dieselbe
    — erst aufzeichnen (das setzt beim ersten Aufruf eines neuen Besuchs
    ``visit_previous_at``), dann das Fenster lesen.

    Ein eigener Pfad statt eines Schalters an ``/visit``: Den einfachen POST
    schickt die Hülle auf jeder Seite und alle fünf Minuten, und nur dieser hier
    braucht die Rats-Datenbank.
    """
    store.record_visit(user["id"])
    window = store.visit_window(user["id"])
    return TodayUpdates(**window, **council.updates_since(
        window["since"], window["until"], 0, FIRST_PAGE_LIMIT, None, None))


@router.get("/updates")
def updates(
    offset: int = Query(0, ge=0),
    limit: int = Query(FIRST_PAGE_LIMIT, ge=1, le=50),
    since: datetime | None = None,
    until: datetime | None = None,
    kind: Literal["protocol", "agenda", "agenda_change"] | None = None,
    committee: str | None = Query(None, max_length=300),
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
    council: CouncilStore = Depends(get_council_store),
) -> TodayUpdates:
    window = store.visit_window(user["id"])
    # Folgeseiten bleiben im selben Fenster, selbst wenn ein zweites Gerät
    # inzwischen einen neuen Besuch begonnen hat.
    if (since is None) != (until is None):
        raise HTTPException(422, "Der Zeitraum braucht Anfang und Ende.")
    if since is not None and until is not None:
        if since.tzinfo is None or until.tzinfo is None or since >= until:
            raise HTTPException(422, "Ungültiger Zeitraum.")
        window["since"] = since.astimezone(UTC).isoformat().replace("+00:00", "Z")
        window["until"] = until.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return TodayUpdates(**window, **council.updates_since(
        window["since"], window["until"], offset, limit, kind, committee))
