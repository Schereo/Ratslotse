"""Onboarding-Fortschritt („Erste Schritte mit Lotti") am Konto.

Serverseitig statt localStorage, damit der Kurs auf jedem Gerät denselben
Stand hat und nach Abschluss überall verschwindet. Schritte werden beim
bloßen Besuch der jeweiligen Seite als erledigt gemeldet (Frontend-Tracker),
nicht nur beim Klick auf die Kurs-Kachel.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from kern.store import Store

from ..antworten import Ok, OnboardingState, SetupState
from ..clients import client_kind
from ..deps import get_store, require_active
from ..schemas import OnboardingUpdate, SetupUpdate, TourUpdate

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

# Muss zu den Step-Ids im Dashboard passen (FirstSteps) — Unbekanntes wird
# still verworfen, damit die Spalte nicht mit Müll wächst. "thema" ist bewusst
# nicht mehr dabei: Der Schritt verlangte ein echtes Thema und war deshalb der
# einzige, den die Lotti-Tour nicht abhaken konnte. Schon gespeicherte "thema"-
# Einträge bleiben unangetastet, sie werden bei der Anzeige einfach ignoriert.
KNOWN_STEPS = {"frag", "beschluesse", "analyse", "karten"}


@router.get("")
def get_onboarding(user: dict = Depends(require_active),
                   store: Store = Depends(get_store)) -> OnboardingState:
    return store.get_onboarding(user["id"])


@router.post("")
def update_onboarding(
    payload: OnboardingUpdate,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> OnboardingState:
    steps = [s for s in payload.steps if s in KNOWN_STEPS]
    return store.update_onboarding(user["id"], steps=steps, celebrated=payload.celebrated)


@router.get("/setup")
def get_setup(
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> SetupState:
    """Resume the first-run setup on another device or after reinstalling."""
    return store.get_setup(user["id"])


@router.post("/setup")
def set_setup(
    payload: SetupUpdate,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> SetupState:
    """Erreichten Schritt festhalten.

    Am Konto statt nur im Gerät: Der Stand überlebt eine Neuinstallation, gilt
    auf jedem Gerät — und erst dadurch kann der Erinnerungs-Cron überhaupt
    erkennen, wer angefangen und nicht zu Ende gebracht hat.
    """
    # Obergrenze 4, seit der Browser einen eigenen Stadtteil-Schritt hat: 1
    # Gremien, 2 Stadtteil, 3 Themen, 4 Mitteilungen. Die App kennt weiter drei
    # (ohne den Stadtteil-Schritt) und schickt deshalb nie mehr als 3 — die
    # Grenze schneidet ihr nichts ab.
    #
    # Das Schema lässt die 4 erst seit 03.09.2026 durch. Vorher stand dort
    # `le=3`, und dieser Kommentar behauptete eine Grenze, die nie erreicht
    # wurde: Der letzte Schritt des Browsers kam als 422 zurück.
    store.set_setup_step(user["id"], max(0, min(4, payload.step)), done=payload.done)
    return store.get_setup(user["id"])


#: Die drei Stationen der Tour-Einladung → der Zähler in ``user_activity``.
#: Als feste Zuordnung und nicht als „tour_" + Wert: Die Spalte ``feature``
#: hat eine überschaubare Menge Werte, und die soll ein Client nicht erweitern
#: können.
TOUR_ZAEHLER = {
    "eingeladen": "tour_invite",
    "gestartet": "tour_started",
    "beendet": "tour_finished",
}


@router.post("/tour")
def tour_stand(
    payload: TourUpdate,
    request: Request,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> Ok:
    """Eine Station von Lottis Tour zählen.

    Nur ein Zähler, kein Zustand: Ob die Einladung schon beantwortet ist,
    entscheidet weiterhin die Marke im Browser (``lib/tour-einladung.ts``) —
    sie muss einen Tab überleben, der seit vor einem Deploy offen ist, und
    genau dafür ist sie da. Hier geht es allein um die Frage, ob der Moment
    nach der Einrichtung etwas bewirkt.
    """
    store.record_activity(user["id"], TOUR_ZAEHLER[payload.stand], client_kind(request))
    return {"ok": True}
