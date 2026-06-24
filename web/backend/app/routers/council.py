"""Ratsinformationssystem: browse and search sessions, agenda items, committees."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from council.store import CouncilStore

from ..deps import get_council_store, require_active

router = APIRouter(prefix="/api/council", tags=["council"])

BASE_URL = "https://buergerinfo.oldenburg.de"


@router.get("/committees")
def committees(_user: dict = Depends(require_active), store: CouncilStore = Depends(get_council_store)) -> dict:
    return {"committees": store.get_all_committee_names()}


@router.get("/sessions")
def sessions(
    q: str = "",
    committee: str = "",
    date_from: str = "",
    date_to: str = "",
    scope: str = Query("all", pattern="^(all|upcoming|recent)$"),
    limit: int = Query(50, ge=1, le=200),
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> dict:
    if scope == "upcoming":
        rows = store.upcoming_sessions(limit=limit)
    elif scope == "recent":
        rows = store.recent_sessions(limit=limit)
    else:
        rows = store.search_sessions(q, committee, date_from, date_to, limit=limit)
    return {"count": len(rows), "sessions": rows}


@router.get("/session/{ksinr}")
def session_detail(
    ksinr: int,
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> dict:
    session = store.get_session(ksinr)
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sitzung nicht gefunden.")
    session["agenda_items"] = store.agenda_items(ksinr)
    # Past sessions may have a parsed protocol → enrich with decisions + attendance.
    session["decisions"] = store.get_decisions(ksinr)
    session["attendance"] = store.get_attendance(ksinr)
    session["has_protocol"] = store.has_protocol(ksinr)
    session["url"] = f"{BASE_URL}/si0057.php?__ksinr={ksinr}"
    return session


@router.get("/decisions")
def decisions(
    q: str = "",
    committee: str = "",
    outcome: str = Query("", pattern="^(|angenommen|abgelehnt|vertagt|zur_kenntnis|kein_beschluss)$"),
    faction: str = "",
    date_from: str = "",
    date_to: str = "",
    kind: str = Query("", pattern="^(|decision|subvote)$"),
    category: str = Query("", pattern="^(|vote|report)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> dict:
    total = store.count_decisions(q, committee, outcome, faction, date_from, date_to, kind, category)
    rows = store.search_decisions(q, committee, outcome, faction, date_from, date_to, kind, category, limit, offset)
    return {"total": total, "decisions": rows}


@router.get("/decision-stats")
def decision_stats(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> dict:
    return store.protocol_stats()
