"""Onboarding-Fortschritt („Erste Schritte mit Lotti") am Konto.

Serverseitig statt localStorage, damit der Kurs auf jedem Gerät denselben
Stand hat und nach Abschluss überall verschwindet. Schritte werden beim
bloßen Besuch der jeweiligen Seite als erledigt gemeldet (Frontend-Tracker),
nicht nur beim Klick auf die Kurs-Kachel.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from kern.store import Store

from ..antworten import OnboardingState, SetupState
from ..deps import get_store, require_active
from ..schemas import OnboardingUpdate, SetupUpdate

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
