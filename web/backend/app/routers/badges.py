"""Lotsen-Abzeichen (RL-U12, Design 10a/11a): Sammeln fürs ERKUNDEN.

Acht Abzeichen, kein Ranking, keine Verlust-Serien — einmal verdient bleibt
verdient. Ereignis-Abzeichen meldet das Frontend über POST /event (Frage
gestellt, Tagesordnung aufgeklappt, Ort geöffnet, Tour beendet); die übrigen
leitet der Server aus vorhandenen Daten ab (Themen, Quiz-Serie, Push-Gerät).
GET berechnet den Stand, persistiert neu Verdientes und liefert es EINMALIG
als ``newly_earned`` — der Konfetti-Moment des Frontends.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from nwz.store import Store

from ..deps import get_store, require_active

router = APIRouter(prefix="/api/badges", tags=["badges"])

KARTOGRAF_TARGET = 3
QUIZ_SERIE_TARGET = 5

BADGES: list[dict] = [
    {"id": "erste-frage", "title": "Erste Frage", "hint": "Stell dem Rat deine erste KI-Frage."},
    {"id": "themen-lotse", "title": "Themen-Lotse", "hint": "Lege dein erstes Thema an."},
    {"id": "quiz-serie", "title": "Quiz-Serie ×5", "hint": "Spiele das Quiz an 5 Tagen in Folge."},
    {"id": "kartograf", "title": "Kartograf", "hint": "Öffne 3 Orte auf der Stadtkarte."},
    {"id": "analyst", "title": "Analyst", "hint": "Erkunde die Analyse-Seite."},
    {"id": "sitzungsgast", "title": "Sitzungsgast", "hint": "Klapp eine Tagesordnung auf."},
    {"id": "fruehwarner", "title": "Frühwarner", "hint": "Aktiviere Push-Mitteilungen in der App."},
    {"id": "kompass", "title": "Kompass", "hint": "Mach die Lotti-Tour einmal ganz durch."},
]

EVENT_FLAGS = {"frage", "sitzung", "tour"}


class BadgeEvent(BaseModel):
    type: str
    key: str | None = None


def _compute(store: Store, user_id: int, state: dict) -> list[dict]:
    """Ist-Zustand aller Abzeichen (earned + Fortschritt), Reihenfolge wie BADGES."""
    flags = set(state["flags"])
    places = len(set(state["map_places"]))
    onboarding = store.get_onboarding(user_id)["steps"]
    result = []
    for b in BADGES:
        earned = False
        progress = None
        if b["id"] == "erste-frage":
            earned = "frage" in flags
        elif b["id"] == "themen-lotse":
            earned = len(store.get_topics(user_id)) > 0
        elif b["id"] == "quiz-serie":
            streak = store.quiz_streak(user_id)
            earned = streak >= QUIZ_SERIE_TARGET
            progress = {"current": min(streak, QUIZ_SERIE_TARGET), "target": QUIZ_SERIE_TARGET}
        elif b["id"] == "kartograf":
            earned = places >= KARTOGRAF_TARGET
            progress = {"current": min(places, KARTOGRAF_TARGET), "target": KARTOGRAF_TARGET}
        elif b["id"] == "analyst":
            earned = "analyse" in onboarding
        elif b["id"] == "sitzungsgast":
            earned = "sitzung" in flags
        elif b["id"] == "fruehwarner":
            earned = len(store.get_push_tokens_for_owner(user_id)) > 0
        elif b["id"] == "kompass":
            earned = "tour" in flags
        # Einmal verdient bleibt verdient (z. B. Quiz-Serie später gerissen,
        # Thema gelöscht, Push-Gerät abgemeldet).
        if b["id"] in state["earned"]:
            earned = True
        result.append({**b, "earned": earned, "progress": progress})
    return result


@router.get("")
def get_badges(user: dict = Depends(require_active), store: Store = Depends(get_store)) -> dict:
    state = store.get_badge_state(user["id"])
    badges = _compute(store, user["id"], state)
    newly = [
        {"id": b["id"], "title": b["title"]}
        for b in badges
        if b["earned"] and b["id"] not in state["earned"]
    ]
    if newly:
        state["earned"] = state["earned"] + [n["id"] for n in newly]
        store.save_badge_state(user["id"], state)
    earned_count = sum(1 for b in badges if b["earned"])
    next_badge = next((b for b in badges if not b["earned"]), None)
    return {
        "badges": badges,
        "earned_count": earned_count,
        "total": len(BADGES),
        "next": {"id": next_badge["id"], "title": next_badge["title"], "hint": next_badge["hint"]}
        if next_badge
        else None,
        "newly_earned": newly,
    }


@router.post("/event")
def badge_event(
    payload: BadgeEvent,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> dict:
    """Ereignis idempotent verbuchen; das Verdienen (inkl. newly_earned)
    passiert im nächsten GET — Unbekanntes wird still verworfen."""
    state = store.get_badge_state(user["id"])
    changed = False
    if payload.type in EVENT_FLAGS and payload.type not in state["flags"]:
        state["flags"].append(payload.type)
        changed = True
    elif payload.type == "map_place" and payload.key:
        key = payload.key.strip()[:120]
        if key and key not in state["map_places"]:
            state["map_places"].append(key)
            changed = True
    if changed:
        store.save_badge_state(user["id"], state)
    return {"ok": True}
