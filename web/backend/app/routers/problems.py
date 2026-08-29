"""Öffentliche Lese-API für den unabhängigen kommunalen Problemtracker."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from buergerportal.store import PROBLEM_CATEGORIES, PROBLEM_STATUSES, ProblemStore
from ..deps import get_problem_store

router = APIRouter(prefix="/api/probleme", tags=["probleme"])


class PublicProblemEvent(BaseModel):
    kind: str
    title: str
    detail: str
    source_kind: Literal[
        "Stadtverwaltung", "Ratsmitglied", "Fraktion", "Ratslotse-Prüfung"
    ] | None = None
    source_url: str | None = None
    event_at: str


class PublicProblemSummary(BaseModel):
    """Map/board projection: exact metrics stay behind the detail endpoint."""

    id: int
    title: str
    category: str
    scope_kind: Literal["point", "facility", "route", "area", "citywide"]
    location_label: str
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    geometry: dict[str, Any] | None = None
    status: Literal[
        "new", "multiple_reports", "verified", "persists", "apparently_resolved"
    ]
    frequency: Literal["once", "several", "many", "very_many"]


class PublicProblem(PublicProblemSummary):
    summary: str
    tags: list[str]
    confidence: Literal["unconfirmed", "supported", "verified"]
    unique_reporters: int = Field(ge=0)
    current_observations: int = Field(ge=0)
    total_observations: int = Field(ge=0)
    first_observed_at: str
    last_observed_at: str
    published_at: str
    updated_at: str
    events: list[PublicProblemEvent] | None = None


class PublicProblemList(BaseModel):
    problems: list[PublicProblemSummary]
    total: int


@router.get("", response_model=PublicProblemList)
def public_problems(
    category: str | None = Query(default=None, max_length=80),
    problem_status: str | None = Query(default=None, alias="status"),
    store: ProblemStore = Depends(get_problem_store),
) -> dict:
    if category and category not in PROBLEM_CATEGORIES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unbekannte Problemkategorie.")
    if problem_status and problem_status not in PROBLEM_STATUSES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unbekannter Problemstatus.")
    problems = store.list_public_problems(category=category, status=problem_status)
    return {"problems": problems, "total": len(problems)}


@router.get("/{problem_id}", response_model=PublicProblem)
def public_problem(
    problem_id: int,
    store: ProblemStore = Depends(get_problem_store),
) -> dict:
    problem = store.get_public_problem(problem_id)
    if not problem:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Problem nicht gefunden.")
    return problem
