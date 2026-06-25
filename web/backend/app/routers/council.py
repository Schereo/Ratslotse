"""Ratsinformationssystem: browse and search sessions, agenda items, committees."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from council.store import CouncilStore
from council.topics import POLICY_FIELDS
from council.goals import GOALS
from council.parties import normalize_party, order_key
from council import qa

from ..deps import get_council_store, require_active

router = APIRouter(prefix="/api/council", tags=["council"])

BASE_URL = "https://buergerinfo.oldenburg.de"


def _ratsinfo_url(ksinr: int) -> str:
    return f"{BASE_URL}/si0057.php?__ksinr={ksinr}"


def _vorlage_url(kvonr: int) -> str:
    return f"{BASE_URL}/vo0050.php?__kvonr={kvonr}"


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
    session["url"] = _ratsinfo_url(ksinr)
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
    party: str = "",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> dict:
    total = store.count_decisions(q, committee, outcome, faction, date_from, date_to, kind, category, field, party)
    rows = store.search_decisions(q, committee, outcome, faction, date_from, date_to, kind, category,
                                  sort=sort, field=field, party=party, limit=limit, offset=offset)
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
    attendance = store.get_attendance(d["ksinr"])
    # Voting members present (for the "unanimous → these factions approved" hint).
    present = {normalize_party(a["party"]) for a in attendance
               if (a.get("role") or "mitglied") in ("vorsitz", "mitglied")}
    out: dict = {
        "decision": d,
        "attendance": attendance,
        "present_parties": sorted((p for p in present if p), key=order_key),
        "ratsinfo_url": _ratsinfo_url(d["ksinr"]),
        "sub_votes": [],
        "vorlage_journey": [],
        "similar": store.get_similar(decision_id, limit=5),
    }
    if d.get("kind") == "decision" and d.get("item_number"):
        out["sub_votes"] = store.get_subvotes(d["ksinr"], d["item_number"])
    if d.get("vorlage_nr"):
        out["vorlage_journey"] = store.vorlage_journey(d["vorlage_nr"])
        out["vorlage_url"] = _vorlage_url(d["kvonr"]) if d.get("kvonr") else None
    return out


@router.get("/analysis")
def analysis(_user: dict = Depends(require_active), store: CouncilStore = Depends(get_council_store)) -> dict:
    """Party behaviour: topic heatmap, success rates, contention, alliances."""
    data = store.party_analysis()
    data["field_labels"] = {k: POLICY_FIELDS[k][0] for k in data["topic_matrix"]["fields"]}
    return data


_EMPTY_GOAL = {"voran": 0, "bremst": 0, "neutral": 0, "total": 0}


@router.get("/goals")
def goals(_user: dict = Depends(require_active), store: CouncilStore = Depends(get_council_store)) -> dict:
    """City goals with how many decisions advance / hinder / are neutral toward them."""
    summary = store.goal_summary()
    out = [{"key": key, "label": g["label"], "description": g["description"],
            **summary.get(key, _EMPTY_GOAL)} for key, g in GOALS.items()]
    return {"goals": out}


@router.get("/goal/{key}")
def goal_detail(key: str, _user: dict = Depends(require_active),
                store: CouncilStore = Depends(get_council_store)) -> dict:
    g = GOALS.get(key)
    if not g:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ziel nicht gefunden.")
    return {
        "key": key, "label": g["label"], "description": g["description"],
        "summary": store.goal_summary().get(key, _EMPTY_GOAL),
        "decisions": store.goal_detail(key),
    }


class AskBody(BaseModel):
    question: str


@router.post("/ask")
def ask(body: AskBody, _user: dict = Depends(require_active),
        store: CouncilStore = Depends(get_council_store)) -> dict:
    """Answer a free-text question from the decisions, with cited sources.
    Retrieves candidates semantically (embeddings) when available, else by keyword."""
    q = body.question.strip()
    if len(q) < 4:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bitte eine etwas längere Frage stellen.")
    candidates, mode = None, "keyword"
    try:
        from council import embeddings as emb
        hits = emb.search(store, q, top_k=20)
        if hits:
            candidates = store.get_decisions_by_ids([h[0] for h in hits])
            mode = "semantisch"
    except Exception:  # noqa: BLE001 — fastembed missing/any failure → keyword fallback
        candidates = None
    if not candidates:
        candidates = store.get_goal_candidates(qa.extract_keywords(q), limit=20)
    answer, cited = qa.answer_question(q, candidates)
    return {"answer": answer, "mode": mode, "sources": store.get_decisions_by_ids(cited)}


@router.get("/decision-stats")
def decision_stats(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> dict:
    return store.protocol_stats()
