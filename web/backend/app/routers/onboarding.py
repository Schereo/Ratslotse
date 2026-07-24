"""Onboarding-Fortschritt („Erste Schritte mit Lotti") am Konto.

Serverseitig statt localStorage, damit der Kurs auf jedem Gerät denselben
Stand hat und nach Abschluss überall verschwindet. Schritte werden beim
bloßen Besuch der jeweiligen Seite als erledigt gemeldet (Frontend-Tracker),
nicht nur beim Klick auf die Kurs-Kachel.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from nwz.store import Store

from ..deps import get_store, require_active
from ..schemas import OnboardingUpdate, SetupUpdate

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

# Muss zu den Step-Ids im Dashboard passen (FirstSteps) — Unbekanntes wird
# still verworfen, damit die Spalte nicht mit Müll wächst.
KNOWN_STEPS = {"frag", "beschluesse", "analyse", "karten", "thema"}


@router.get("")
def get_onboarding(user: dict = Depends(require_active), store: Store = Depends(get_store)) -> dict:
    return store.get_onboarding(user["id"])


@router.post("")
def update_onboarding(
    payload: OnboardingUpdate,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> dict:
    steps = [s for s in payload.steps if s in KNOWN_STEPS]
    return store.update_onboarding(user["id"], steps=steps, celebrated=payload.celebrated)


@router.get("/setup")
def get_setup(user: dict = Depends(require_active), store: Store = Depends(get_store)) -> dict:
    """Stand des Einrichtungs-Assistenten (Design 26a)."""
    return store.get_setup(user["id"])


@router.post("/setup")
def set_setup(
    payload: SetupUpdate,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> dict:
    """Erreichten Schritt festhalten.

    Am Konto statt nur im Gerät: Der Stand überlebt eine Neuinstallation, gilt
    auf jedem Gerät — und erst dadurch kann der Erinnerungs-Cron überhaupt
    erkennen, wer angefangen und nicht zu Ende gebracht hat.
    """
    store.set_setup_step(user["id"], max(0, min(3, payload.step)), done=payload.done)
    return store.get_setup(user["id"])
