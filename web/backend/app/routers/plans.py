"""Pläne der Stadt (docs/plan-ziele-plaene.md): Übersicht und Detailseite.

Gebaut wird beides in ``council/plan_pages.py`` — hier steht nur der Zugang.
Angemeldet wie die alte Ziel-Seite (``/council/goals``), die bis zum
App-Build mit „Pläne“ daneben stehen bleibt (Plan § 4). Der Schalter
``plaene`` regelt nur die Oberfläche; die Daten sind nicht geheim.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from council import plan_pages
from council.store import CouncilStore

from ..antworten import PlanDetail, Plans
from ..deps import get_council_store, require_active

router = APIRouter(prefix="/api/council", tags=["council"])


@router.get("/plans")
def plans_overview(_user: dict = Depends(require_active),
                   store: CouncilStore = Depends(get_council_store)) -> Plans:
    """Alle Pläne im Register: laufend, in Arbeit, abgelaufen oder abgelöst."""
    return plan_pages.overview(store)  # type: ignore[return-value]


@router.get("/plan/{key}")
def plan_detail(key: str, _user: dict = Depends(require_active),
                store: CouncilStore = Depends(get_council_store)) -> PlanDetail:
    """Ein Plan mit Beschluss, Laufzeit, Berichten und den Beschlüssen dazu."""
    out = plan_pages.detail(store, key)
    if out is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan nicht gefunden.")
    return out  # type: ignore[return-value]
