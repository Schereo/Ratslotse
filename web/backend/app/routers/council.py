"""Ratsinformationssystem: browse and search sessions, agenda items, committees."""
from __future__ import annotations

import json
import math
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from council.store import CouncilStore
from council.topics import POLICY_FIELDS
from council.goals import GOALS
from council.parties import normalize_party, order_key
from council import qa
from council import importance
from council import sitzungspause as pause_mod
from council import vorlagen as vorlagen_mod

from nwz.store import Store

from ..deps import get_council_store, get_store, require_active
from ..ratelimit import qa_limiter

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
    user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
    nwz: Store = Depends(get_store),
) -> dict:
    if scope == "upcoming":
        rows = store.upcoming_sessions(limit=limit)
    elif scope == "recent":
        rows = store.recent_sessions(limit=limit)
    else:
        rows = store.search_sessions(q, committee, date_from, date_to, limit=limit)

    # RL-902: „n TOPs zu deinen Themen" — Treffer der Tagesordnungs-
    # Klassifikation für die eingeloggte Nutzer:in (eine Batch-Abfrage).
    ksinrs = [r["ksinr"] for r in rows if r.get("ksinr")]
    mine = nwz.agenda_matches_for_owner(user["id"], ksinrs)
    for r in rows:
        matches = mine.get(r.get("ksinr") or 0)
        if matches:
            r["my_topic_items"] = matches

    return {"count": len(rows), "sessions": rows}


@router.get("/sitzungspause")
def sitzungspause(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> dict:
    """Läuft gerade eine Sitzungspause (Schulferien / Wahl-Übergang)?

    Der Rat pausiert laut Stadt in den Schulferien; die Übersicht zeigt dann
    ein Banner, damit sich niemand über ausbleibende neue Sitzungen wundert.
    """
    upcoming = store.upcoming_sessions(limit=1)
    next_date: date | None = None
    if upcoming:
        try:
            next_date = date.fromisoformat(str(upcoming[0]["session_date"])[:10])
        except ValueError:
            next_date = None
    return pause_mod.sitzungspause(date.today(), next_date)


# 15-Minuten-Cache für die öffentliche Heute-Leiste (RL-901) — ein Dict statt
# Infrastruktur: der Endpoint ist public und würde sonst je Landing-Aufruf
# Agenda-Zeilen lesen.
_HEUTE_CACHE: dict = {"at": 0.0, "data": None}


@router.get("/heute")
def heute(store: CouncilStore = Depends(get_council_store)) -> dict:
    """RL-901: „Heute im Rat" für die Landing — public (wie public-stats).
    Drei Zustände: Sitzung heute (mit 2 Top-TOPs + Restzähler) · nächste
    Sitzung · Sitzungspause. Cache 15 min."""
    import time
    now = time.time()
    if _HEUTE_CACHE["data"] is not None and now - _HEUTE_CACHE["at"] < 900:
        return _HEUTE_CACHE["data"]

    today = date.today().isoformat()
    upcoming = store.upcoming_sessions(limit=10)
    sessions_today = [s for s in upcoming if str(s["session_date"])[:10] == today]
    if sessions_today:
        s = sessions_today[0]
        # Terminierte Sitzungen (aus dem Kalender) haben noch keinen ksinr.
        items = [i for i in store.agenda_items(s["ksinr"]) if i.get("is_public")] if s.get("ksinr") else []
        data = {
            "state": "heute",
            "committee": s["committee"],
            "session_time": s.get("session_time") or "",
            "tops": [str(i.get("title") or "")[:90] for i in items[:2]],
            "rest": max(len(items) - 2, 0),
            "n_sessions_today": len(sessions_today),
        }
    elif upcoming:
        s = upcoming[0]
        data = {
            "state": "naechste",
            "committee": s["committee"],
            "session_date": s["session_date"],
            "session_time": s.get("session_time") or "",
        }
    else:
        p = pause_mod.sitzungspause(date.today(), None)
        data = {"state": "pause", "label": p["label"], "until": p["until"]}

    _HEUTE_CACHE.update(at=now, data=data)
    return data


@router.get("/diese-woche")
def diese_woche(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> dict:
    """RL-U15 (13a-A): interessantester Beschluss der letzten 7 Tage — die
    „Diese Woche im Rat"-Karte, wenn es keine persönlichen Treffer gibt.
    Der interest_reason-Satz ist die „Warum spannend"-Zeile."""
    d = store.most_interesting_recent(days_back=7)
    if not d:
        return {"found": False}
    return {
        "found": True,
        "decision_id": d["id"],
        "title": d["title"],
        "outcome": d["outcome"],
        "committee": d["committee"],
        "session_date": d["session_date"],
        "interest_reason": d.get("interest_reason") or "",
    }


@router.get("/fundstueck")
def fundstueck(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> dict:
    """RL-U11: Fundstück des Tages — kuratierter Archiv-Fund für die Übersicht
    (Pipeline: scripts/rate_interest.py + scripts/generate_fundstuecke.py).
    {"found": false} statt 404: ohne Karte des Tages lässt das Frontend die
    Kachel schlicht weg."""
    f = store.get_fundstueck(date.today().isoformat())
    if not f:
        return {"found": False}
    return {
        "found": True,
        "kicker": f["kicker"],
        "story": f["story"],
        "decision_id": f["decision_id"],
        "title": f["title"],
        "outcome": f["outcome"],
        "vote": f["vote"],
        "committee": f["committee"],
        "session_date": f["session_date"],
    }


@router.get("/zahl-der-woche")
def zahl_der_woche(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> dict:
    """RL-905: größter Beschluss-Betrag der letzten 7 Tage (Fallback 30);
    ganz ohne Treffer zählt die Karte die Beschlüsse der Woche. Die Satz-
    Formulierung übernimmt das Frontend — hier nur Rohdaten."""
    from datetime import timedelta
    today = date.today()
    for days in (7, 30):
        top = store.top_amount_since((today - timedelta(days=days)).isoformat())
        if top:
            return {"kind": "betrag", "amount_eur": top["amount_eur"],
                    "decision_id": top["id"], "title": top["title"],
                    "session_date": top["session_date"], "window_days": days}
    return {"kind": "anzahl",
            "count": store.count_decisions_since((today - timedelta(days=7)).isoformat()),
            "window_days": 7}


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
    sort: str = Query("date_desc", pattern="^(date_desc|date_asc|faction|importance|interest)$"),
    field: str = "",
    party: str = "",
    # Design 23a: Standard blendet Änderungsanträge (subvotes) aus der Trefferliste
    # aus — sie hängen als Kontext am Ursprungsbeschluss. Rechercheure können sie
    # per Filter „Änderungsanträge einzeln zeigen" wieder einblenden.
    include_subvotes: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> dict:
    total = store.count_decisions(q, committee, outcome, faction, date_from, date_to, kind, category, field, party,
                                  include_subvotes=include_subvotes)
    rows = store.search_decisions(q, committee, outcome, faction, date_from, date_to, kind, category,
                                  sort=sort, field=field, party=party, limit=limit, offset=offset,
                                  include_subvotes=include_subvotes)
    # Design 23a: je Beschluss die kompakte Änderungsantrags-Zusammenfassung
    # anhängen (Anzahl · Fraktion · Ergebnis) für die Karten-Unterzeile.
    pairs = [(r["ksinr"], r["item_number"]) for r in rows
             if r.get("kind") == "decision" and r.get("item_number")]
    summaries = store.subvote_summaries(pairs)
    for r in rows:
        s = summaries.get((r.get("ksinr"), r.get("item_number")))
        if s:
            r["subvote_summary"] = s
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
        "news": store.get_news_for_decision(decision_id),
        "entities": store.entities_for_decision(decision_id),
    }
    # Wichtigkeits-Aufschlüsselung (welche Signale trieben den Score) — erklärt
    # transparent, warum ein Beschluss als wichtig gilt.
    n_ber = len(store.get_beratungen(d["kvonr"])) if d.get("kvonr") else None
    out["importance_breakdown"] = importance.importance_breakdown(d, n_beratungen=n_ber)
    # RL-U16: gleiche 50/50-Mischung wie beim persistierten Wichtig-Wert —
    # sonst zeigten Liste (DB) und Detail (Live-Heuristik) verschiedene Zahlen.
    # impact_reason erklärt den Meter („Warum wichtig: …", Design 13a-B).
    if d.get("impact") is not None:
        out["importance_breakdown"]["score"] = round(
            (out["importance_breakdown"]["score"] + int(d["impact"])) / 2
        )
        if d.get("impact_reason"):
            out["importance_breakdown"]["impact_reason"] = d["impact_reason"]
    if d.get("kind") == "decision" and d.get("item_number"):
        out["sub_votes"] = store.get_subvotes(d["ksinr"], d["item_number"])
    if d.get("vorlage_nr"):
        out["vorlage_journey"] = store.vorlage_journey(d["vorlage_nr"])
        out["vorlage_url"] = _vorlage_url(d["kvonr"]) if d.get("kvonr") else None
        # Ingested Vorlage text (Sachverhalt/Begründung) — the why behind the
        # decision. Also our only kvonr source: protocols never carry one.
        v = store.get_vorlage_by_nr(d["vorlage_nr"])
        if v:
            out["vorlage"] = {
                "vorlage_nr": v.get("vorlage_nr"), "title": v.get("title"),
                "art": v.get("art"), "document_url": v.get("document_url"),
                "n_pages": v.get("n_pages"),
                "excerpt": vorlagen_mod.excerpt(v.get("raw_text") or "", 2600) or None,
            }
            if not out["vorlage_url"] and v.get("kvonr"):
                out["vorlage_url"] = _vorlage_url(v["kvonr"])
        out["anlagen"] = store.anlagen_for_vorlage_nr(d["vorlage_nr"])
        # Offizielle Beratungsfolge aus dem Ratsinfo — reicher als die aus
        # unseren Tagesordnungen abgeleitete Journey (Ergebnis je Station,
        # geplante künftige Beratungen). Die Journey bleibt der Fallback.
        kv = d.get("kvonr") or (v.get("kvonr") if v else None)
        if kv:
            today = date.today().isoformat()
            out["beratungsfolge"] = [
                {**b, "future": bool(b["datum"] and b["datum"] > today)}
                for b in store.get_beratungen(kv)
            ]
    return out


@router.get("/analysis")
def analysis(_user: dict = Depends(require_active), store: CouncilStore = Depends(get_council_store)) -> dict:
    """Party behaviour: topic heatmap, success rates, contention, alliances —
    plus Erfolgsquoten der eingereichten Fraktions-Anträge (aus den Anlagen)."""
    data = store.party_analysis()
    data["field_labels"] = {k: POLICY_FIELDS[k][0] for k in data["topic_matrix"]["fields"]}
    data["antrag_stats"] = store.antrag_stats()
    return data


@router.get("/finance")
def finance(_user: dict = Depends(require_active), store: CouncilStore = Depends(get_council_store)) -> dict:
    """Largest € decisions + recognised volume per policy field (excl. accounting reports)."""
    by_field = store.money_by_field()
    return {
        "decisions": store.largest_financial_decisions(limit=25),
        "by_field": by_field,
        "field_labels": {r["field"]: POLICY_FIELDS[r["field"]][0] for r in by_field},
    }


@router.get("/trends")
def trends(_user: dict = Depends(require_active), store: CouncilStore = Depends(get_council_store)) -> dict:
    """Council activity over time: decisions + € volume per quarter by field, emerging tags."""
    data = store.activity_trends()
    data["field_labels"] = {k: POLICY_FIELDS[k][0] for k in data["fields"]}
    return data


@router.get("/field-recaps")
def field_recaps(_user: dict = Depends(require_active), store: CouncilStore = Depends(get_council_store)) -> dict:
    """Auto-generated plain-language recaps per policy field ("Was bewegte den Rat im Bereich X?")."""
    recaps = store.get_field_recaps()
    for r in recaps:
        r["field_label"] = POLICY_FIELDS.get(r["policy_field"], (r["policy_field"],))[0]
    return {"recaps": recaps}


@router.get("/entities")
def entities_list(kind: str = "", _user: dict = Depends(require_active),
                  store: CouncilStore = Depends(get_council_store)) -> dict:
    """Directory of named entities (projects/places/organizations), most-referenced first."""
    return {"entities": store.list_entities(limit=400, kind=kind)}


@router.get("/entities-map")
def entities_map(_user: dict = Depends(require_active),
                 store: CouncilStore = Depends(get_council_store)) -> dict:
    """All geocoded entities (points) for the city-wide map."""
    return {"entities": store.list_entities_geo()}


@router.get("/public-stats")
def public_stats(store: CouncilStore = Depends(get_council_store)) -> dict:
    """Aggregate headline counts for the public landing page — no auth, no content."""
    return store.public_stats()


@router.get("/entity/{slug}")
def entity(slug: str, _user: dict = Depends(require_active),
           store: CouncilStore = Depends(get_council_store)) -> dict:
    """An entity ('Themen-') page: all its decisions plus money/parties/field aggregates."""
    data = store.entity_detail(slug)
    if not data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thema nicht gefunden.")
    data["field_labels"] = {f["field"]: POLICY_FIELDS[f["field"]][0]
                            for f in data["fields"] if f["field"] in POLICY_FIELDS}
    return data


@router.get("/members")
def members(_user: dict = Depends(require_active),
            store: CouncilStore = Depends(get_council_store)) -> dict:
    """Directory of council members (from attendance): party, sessions, committees."""
    return {"members": store.list_members()}


@router.get("/person/{slug}")
def person(slug: str, _user: dict = Depends(require_active),
           store: CouncilStore = Depends(get_council_store)) -> dict:
    """A council member's profile: party, sessions, active span, committees, recent sessions."""
    data = store.member_detail(slug)
    if not data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ratsmitglied nicht gefunden.")
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


# Q&A sizing: show up to QA_TOP_K reranked decisions as sources, feed the most
# relevant QA_ANSWER_N to the LLM for a focused, cited answer. QA_MIN_SCORE drops
# the near-irrelevant tail from the displayed sources (sigmoid relevance).
QA_TOP_K = 40
QA_ANSWER_N = 20
QA_MIN_SCORE = 0.2
# jina-reranker-v2 logits are negative-centred (a clearly relevant match still scores
# below 0), so a raw sigmoid under-sells good hits (~50 % for the top result). Shift by
# a fixed bias so a relevant decision reads as a high-but-honest relevance.
QA_RERANK_BIAS = 1.5


def _qa_retrieve(store: CouncilStore, q: str, expanded: str) -> tuple[list[dict], str]:
    """Hybrid retrieval + cross-encoder rerank → candidates in relevance order, each
    with an *absolute* relevance score: the sigmoid of the reranker logit, NOT a
    min-max normalisation (which forced the weakest hit to a misleading 0 %). Falls
    back to keyword retrieval when embeddings/the reranker are unavailable."""
    try:
        from council import embeddings as emb
        hits = emb.hybrid_search(store, q, expanded, top_k=QA_TOP_K, pool=55)
        if hits:
            candidates = store.get_decisions_by_ids([h[0] for h in hits])  # preserves order
            score = {h[0]: h[1] for h in hits}
            for c in candidates:
                logit = score.get(c["id"])
                c["score"] = round(1.0 / (1.0 + math.exp(-(logit + QA_RERANK_BIAS))), 3) if logit is not None else None
            return [c for c in candidates if (c.get("score") or 0) >= QA_MIN_SCORE] or candidates, "semantisch"
    except Exception:  # noqa: BLE001 — fastembed missing/any failure → keyword fallback
        pass
    cands = store.get_goal_candidates(qa.extract_keywords(q), limit=QA_TOP_K)
    return store.get_decisions_by_ids([c["id"] for c in cands]), "keyword"


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _qa_source(c: dict) -> dict:
    return {
        "id": c["id"], "title": c.get("title"), "summary": c.get("summary"),
        "policy_field": c.get("policy_field"), "outcome": c.get("outcome"),
        "session_date": c.get("session_date"), "committee": c.get("committee"),
        "score": c.get("score"),
    }


@router.post("/ask")
def ask(body: AskBody, request: Request, user: dict = Depends(require_active),
        store: CouncilStore = Depends(get_council_store),
        nwz: Store = Depends(get_store)) -> StreamingResponse:
    """Answer a free-text question from the decisions, streamed as Server-Sent Events:
    progress steps → the ranked source decisions (the moment retrieval+rerank finish)
    → the answer token-by-token → a final event with the cited ids. Streaming makes
    the wait feel far shorter (sources show in ~2 s) and degrades gracefully if a
    proxy buffers it (the client then renders the same final state at once)."""
    qa_limiter.check(request)  # LLM-Kosten pro Aufruf — nicht unbegrenzt feuern lassen
    nwz.record_activity(user["id"], "ki_frage")  # Admin-Statistik (20a)
    q = body.question.strip()
    if len(q) < 4:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bitte eine etwas längere Frage stellen.")

    def gen():
        try:
            yield _sse({"type": "step", "step": "expand"})
            expanded = qa.expand_query(q)
            yield _sse({"type": "step", "step": "search"})
            candidates, mode = _qa_retrieve(store, q, expanded)
            yield _sse({"type": "sources", "mode": mode, "sources": [_qa_source(c) for c in candidates]})
            yield _sse({"type": "step", "step": "answer"})
            if not candidates:
                yield _sse({"type": "token", "text": "Dazu habe ich keine passenden Beschlüsse gefunden."})
                yield _sse({"type": "done", "cited": []})
                return
            ctx = candidates[:QA_ANSWER_N]
            try:  # Vorlagen-Auszüge (Sachverhalt) beilegen — best-effort
                texts = store.vorlage_texts_for([c.get("vorlage_nr") or "" for c in ctx])
                for c in ctx:
                    t = texts.get((c.get("vorlage_nr") or "").strip())
                    if t:
                        c["vorlage_excerpt"] = vorlagen_mod.excerpt(t, 350)
            except Exception:  # noqa: BLE001
                pass
            parts: list[str] = []
            try:
                for delta in qa.answer_stream(q, ctx):
                    parts.append(delta)
                    yield _sse({"type": "token", "text": delta})
            except Exception:  # noqa: BLE001 — streaming failed mid-way → one-shot fallback
                if not parts:
                    ans, _ = qa.answer_question(q, ctx)
                    parts.append(ans)
                    yield _sse({"type": "token", "text": ans})
            _, cited = qa.resolve_citations("".join(parts), {c["id"] for c in candidates})
            yield _sse({"type": "done", "cited": cited})
        except Exception:  # noqa: BLE001 — surface a terminal error to the client
            yield _sse({"type": "error", "message": "Frage fehlgeschlagen."})

    return StreamingResponse(
        gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/decision-stats")
def decision_stats(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> dict:
    return store.protocol_stats()
