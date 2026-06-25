"""Ratsinformationssystem: browse and search sessions, agenda items, committees."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from council.store import CouncilStore
from council.topics import POLICY_FIELDS

from ..deps import get_council_store, require_active

router = APIRouter(prefix="/api/council", tags=["council"])

BASE_URL = "https://buergerinfo.oldenburg.de"


@router.get("/committees")
def committees(_user: dict = Depends(require_active), store: CouncilStore = Depends(get_council_store)) -> dict:
    return {"committees": store.get_all_committee_names()}


@router.get("/fields")
def fields(_user: dict = Depends(require_active), store: CouncilStore = Depends(get_council_store)) -> dict:
    """Policy fields that have at least one classified decision, with label + count."""
    counts = {r["field"]: r["count"] for r in store.policy_field_stats()}
    out = [
        {"key": key, "label": POLICY_FIELDS[key][0], "count": counts[key]}
        for key in POLICY_FIELDS if counts.get(key)
    ]
    out.sort(key=lambda f: f["count"], reverse=True)
    return {"fields": out}


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
    sort: str = Query("date_desc", pattern="^(date_desc|date_asc|faction)$"),
    field: str = "",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> dict:
    total = store.count_decisions(q, committee, outcome, faction, date_from, date_to, kind, category, field)
    rows = store.search_decisions(q, committee, outcome, faction, date_from, date_to, kind, category,
                                  sort=sort, field=field, limit=limit, offset=offset)
    return {"total": total, "decisions": rows}


@router.get("/decision/{decision_id}")
def decision_detail(
    decision_id: int,
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> dict:
    d = store.get_decision(decision_id)
    if not d:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Beschluss nicht gefunden.")
    out: dict = {
        "decision": d,
        "attendance": store.get_attendance(d["ksinr"]),
        "ratsinfo_url": f"{BASE_URL}/si0057.php?__ksinr={d['ksinr']}",
        "sub_votes": [],
        "vorlage_journey": [],
    }
    if d.get("kind") == "decision" and d.get("item_number"):
        out["sub_votes"] = store.get_subvotes(d["ksinr"], d["item_number"])
    if d.get("vorlage_nr"):
        out["vorlage_journey"] = store.vorlage_journey(d["vorlage_nr"])
        out["vorlage_url"] = f"{BASE_URL}/vo0050.php?__kvonr={d['kvonr']}" if d.get("kvonr") else None
    return out


@router.get("/decision-stats")
def decision_stats(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> dict:
    return store.protocol_stats()
