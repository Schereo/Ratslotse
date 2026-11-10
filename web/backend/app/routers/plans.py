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

from ..antworten import PlanBudget, PlanDetail, Plans
from ..deps import get_council_store, require_active, require_permission

router = APIRouter(prefix="/api/council", tags=["council"])
#: Was im Haushalt den Plan nennt, sieht nur, wer den Haushalt sieht — die Sperre sitzt hier, und die
#: Route liegt deshalb unter /api/council/budget (tests/test_rollen.py hält beides zusammen).
require_budget = require_permission("budget")


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


@router.get("/budget/plan/{key}")
def plan_budget(key: str, _user: dict = Depends(require_budget),
                store: CouncilStore = Depends(get_council_store)) -> PlanBudget:
    """Haushaltsposten, deren eigener Text den Plan nennt — nur mit dem Recht ``budget``."""
    plan = plan_pages.register.PLANS.get(key)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan nicht gefunden.")
    return plan_pages.budget_block(store, plan)  # type: ignore[return-value]
