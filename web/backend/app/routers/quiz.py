"""Oldenburg-Quiz: Gebiets-Katalog, Runden, Auswertung, Bewertung, Statistik.

Fragen liegen in council.sqlite (generiert), Punkte/Bewertungen in nwz.sqlite
(pro Konto). Der Router nutzt daher beide Stores. Wahlbereiche sind ein
View auf ihre Stadtteile (keine eigenen Fragen) — der Filter expandiert sie.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from council import geo
from council.store import CouncilStore
from nwz.store import Store

from ..deps import get_council_store, get_store, require_active, require_admin
from ..schemas import QuizAnswerIn, QuizRateIn

router = APIRouter(prefix="/api/quiz", tags=["quiz"])

CATEGORIES = ["geschichte", "orte", "menschen", "ratspolitik", "schaetzen"]
_POINTS = {"leicht": 1, "mittel": 2, "schwer": 3}


def _expand(areas: list[str]) -> list[tuple[str, str]]:
    """„type:key"-Strings in (area_type, area_key)-Paare; Wahlbereiche auf ihre
    Stadtteile aufgelöst."""
    out: list[tuple[str, str]] = []
    for a in areas:
        typ, _, key = a.partition(":")
        if typ == "wahlbereich" and key.isdigit():
            out += [("stadtteil", n) for n in geo.stadtteile_im_wahlbereich(int(key))]
        elif typ in ("stadtteil", "thema") and key:
            out.append((typ, key))
    # dedup, Reihenfolge egal
    return list(dict.fromkeys(out))


@router.get("/areas")
def areas(user: dict = Depends(require_active),
          store: Store = Depends(get_store),
          council: CouncilStore = Depends(get_council_store)) -> dict:
    """Katalog: Wahlbereiche, Stadtteile, Themen — je mit Fragenzahl und meinen
    Punkten. Leere Gebiete (noch keine Fragen) werden weggelassen."""
    counts = council.quiz_area_counts()          # {(type, key): n}
    points = store.quiz_points_by_area(user["id"])  # {(type, key): points}

    stadtteile = []
    for name in geo.stadtteile():
        n = counts.get(("stadtteil", name), 0)
        if n:
            stadtteile.append({"key": name, "wahlbereich": geo.wahlbereich_of(name),
                               "questions": n, "points": points.get(("stadtteil", name), 0)})
    wahlbereiche = []
    for wb in geo.WAHLBEREICHE:
        members = geo.stadtteile_im_wahlbereich(wb)
        n = sum(counts.get(("stadtteil", m), 0) for m in members)
        if n:
            wahlbereiche.append({"key": str(wb), "label": f"Wahlbereich {wb}", "stadtteile": members,
                                 "questions": n,
                                 "points": sum(points.get(("stadtteil", m), 0) for m in members)})
    themen = []
    for t in council.quiz_themes():
        themen.append({"key": t["area_key"], "label": t["label"],
                       "questions": counts.get(("thema", t["area_key"]), 0),
                       "points": points.get(("thema", t["area_key"]), 0)})
    return {"wahlbereiche": wahlbereiche, "stadtteile": stadtteile, "themen": themen,
            "categories": CATEGORIES}


@router.get("/round")
def round_(areas: str = Query(..., description="komma-separiert, z. B. wahlbereich:3,stadtteil:Osternburg"),
           categories: str = "", n: int = Query(10, ge=1, le=30),
           user: dict = Depends(require_active),
           store: Store = Depends(get_store),
           council: CouncilStore = Depends(get_council_store)) -> dict:
    """Eine Runde Fragen — bevorzugt noch nicht beantwortete, OHNE Lösung."""
    pairs = _expand([a for a in areas.split(",") if a.strip()])
    if not pairs:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Kein gültiges Gebiet gewählt.")
    cats = [c for c in categories.split(",") if c in CATEGORIES]
    questions = council.pick_quiz_questions(
        pairs, cats or None, store.quiz_answered_ids(user["id"]), n)
    return {"questions": questions}


@router.post("/answer")
def answer(payload: QuizAnswerIn,
           user: dict = Depends(require_active),
           store: Store = Depends(get_store),
           council: CouncilStore = Depends(get_council_store)) -> dict:
    """Antwort auswerten, Punkte buchen, Lösung + Erklärung + Quelle zurückgeben."""
    q = council.get_quiz_question(payload.question_id)
    if not q:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Frage nicht gefunden.")
    correct = payload.selected_index == q["correct_index"]
    pts = _POINTS.get(q["difficulty"], 1) if correct else 0
    store.record_quiz_answer(user["id"], q["id"], q["area_type"], q["area_key"],
                             q["category"], correct, pts)
    return {"correct": correct, "correct_index": q["correct_index"], "points": pts,
            "explanation": q.get("explanation"),
            "source_type": q.get("source_type"), "source_ref": q.get("source_ref")}


@router.post("/rate")
def rate(payload: QuizRateIn,
         user: dict = Depends(require_active),
         store: Store = Depends(get_store),
         council: CouncilStore = Depends(get_council_store)) -> dict:
    """Frage bewerten (Qualitäts-Feedback). Idempotent (eine Wertung je Nutzer)."""
    if not council.get_quiz_question(payload.question_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Frage nicht gefunden.")
    store.rate_quiz_question(user["id"], payload.question_id, payload.verdict, payload.comment)
    return {"ok": True}


@router.get("/stats")
def stats(user: dict = Depends(require_active), store: Store = Depends(get_store)) -> dict:
    """Fortschritt je Gebiet + Gesamt — Grundlage des „meine Schwächen"-Dashboards."""
    return store.quiz_stats(user["id"])


# ---- Admin: schlecht bewertete Fragen sichten & ausmustern ----
admin_router = APIRouter(prefix="/api/admin/quiz", tags=["admin"])


@admin_router.get("/flagged")
def flagged(_user: dict = Depends(require_admin),
            store: Store = Depends(get_store),
            council: CouncilStore = Depends(get_council_store)) -> dict:
    """Fragen mit Schlecht-Bewertungen (schlechteste zuerst), mit Fragentext."""
    flags = store.quiz_flagged_questions(min_bad=1)
    by_id = {q["id"]: q for q in council.quiz_questions_by_ids([f["question_id"] for f in flags])}
    out = []
    for f in flags:
        q = by_id.get(f["question_id"])
        if q:
            out.append({**f, "question": q["question"], "area_type": q["area_type"],
                        "area_key": q["area_key"], "options": q["options"],
                        "correct_index": q["correct_index"]})
    return {"flagged": out}


@admin_router.post("/{question_id}/retire")
def retire(question_id: int, _user: dict = Depends(require_admin),
           council: CouncilStore = Depends(get_council_store)) -> dict:
    council.retire_quiz_question(question_id)
    return {"ok": True}
