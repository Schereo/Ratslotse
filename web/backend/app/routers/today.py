"""Der Rückblick auf Ergänzungen seit dem letzten sichtbaren Besuch."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from council.store import CouncilStore
from kern.store import Store
from ..antworten import TodayUpdates, VisitWindow
from ..deps import get_council_store, get_store, require_active

router = APIRouter(prefix="/api/today", tags=["today"])


@router.post("/visit")
def visit(user: dict = Depends(require_active), store: Store = Depends(get_store)) -> VisitWindow:
    store.record_visit(user["id"])
    return VisitWindow(**store.visit_window(user["id"]))


@router.get("/updates")
def updates(
    offset: int = Query(0, ge=0),
    limit: int = Query(3, ge=1, le=50),
    since: datetime | None = None,
    until: datetime | None = None,
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
        window["since"] = since.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        window["until"] = until.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return TodayUpdates(**window, **council.updates_since(window["since"], window["until"], offset, limit))
