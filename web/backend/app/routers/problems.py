"""Öffentliche Lese-API für den unabhängigen kommunalen Problemtracker."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from buergerportal.domain import PROBLEM_CATEGORIES, PROBLEM_STATUSES
from buergerportal.store import ProblemStore

from ..antworten import PublicProblemList, PublicProblemSummary
from ..deps import get_problem_store

router = APIRouter(prefix="/api/probleme", tags=["probleme"])


@router.get("")
def public_problems(
    category: str | None = Query(default=None, max_length=80),
    problem_status: str | None = Query(default=None, alias="status", max_length=80),
    store: ProblemStore = Depends(get_problem_store),
) -> PublicProblemList:
    """Ungelöste öffentliche Projektionen nach unabhängigen Meldungen."""
    if category is not None and category not in PROBLEM_CATEGORIES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Unbekannte Problemkategorie.",
        )
    if problem_status is not None and problem_status not in PROBLEM_STATUSES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Unbekannter Problemstatus.",
        )
    problems = store.list_public_problems(category=category, status=problem_status)
    return {"problems": problems, "total": len(problems)}


@router.get("/{problem_id}")
def public_problem(
    problem_id: int,
    store: ProblemStore = Depends(get_problem_store),
) -> PublicProblemSummary:
    """Eine veröffentlichte Projektion über ihre stabile ID lesen."""
    problem = store.get_public_problem(problem_id)
    if problem is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Problem nicht gefunden.")
    return problem
