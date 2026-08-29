"""Private Schreib-API für Meldungen an das Bürgerportal."""
from __future__ import annotations

from datetime import date, datetime, time, timezone
import sqlite3
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, model_validator

from buergerportal.domain import OLDENBURG_BOUNDS
from buergerportal.reports import ReportStore
from buergerportal.store import ProblemStore
from ..deps import get_problem_store, get_report_store, require_verified_reporter
from ..ratelimit import report_draft_limiter

router = APIRouter(prefix="/api/meldungen", tags=["meldungen"])
_OLDENBURG = ZoneInfo("Europe/Berlin")

Category = Literal[
    "mobility",
    "public_space",
    "education",
    "childcare",
    "housing",
    "environment",
    "accessibility",
    "administration",
    "other",
]
ScopeKind = Literal["point", "facility", "route", "area", "citywide"]
ReportStatus = Literal[
    "draft",
    "submitted",
    "in_review",
    "needs_information",
    "accepted",
    "rejected",
    "withdrawn",
]


class ReportDraftInput(BaseModel):
    text: str = Field(min_length=20, max_length=2_000)
    category: Category
    scope_kind: ScopeKind
    location_label: str = Field(default="", max_length=160)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    observed_on: date
    category_detail: str = Field(min_length=10, max_length=500)
    suggested_problem_id: int | None = Field(default=None, gt=0)
    client_token: UUID

    @model_validator(mode="after")
    def validate_private_location(self) -> "ReportDraftInput":
        self.text = self.text.strip()
        self.location_label = self.location_label.strip()
        self.category_detail = self.category_detail.strip()
        if len(self.text) < 20:
            raise ValueError("Bitte beschreibe die Beobachtung mit mindestens 20 Zeichen.")
        if len(self.category_detail) < 10:
            raise ValueError("Bitte beantworte auch die Frage zu diesem Thema.")
        if self.observed_on > datetime.now(_OLDENBURG).date():
            raise ValueError("Das Beobachtungsdatum darf nicht in der Zukunft liegen.")
        if self.scope_kind == "citywide":
            if self.latitude is not None or self.longitude is not None:
                raise ValueError("Stadtweite Meldungen verwenden keinen Kartenpunkt.")
            return self
        if not self.location_label:
            raise ValueError("Bitte beschreibe den Ort kurz.")
        if self.latitude is None or self.longitude is None:
            raise ValueError("Bitte markiere die ungefähre Lage auf der Karte.")
        if not (
            OLDENBURG_BOUNDS["south"] <= self.latitude <= OLDENBURG_BOUNDS["north"]
            and OLDENBURG_BOUNDS["west"] <= self.longitude <= OLDENBURG_BOUNDS["east"]
        ):
            raise ValueError("Die markierte Lage liegt außerhalb von Oldenburg.")
        return self


class SubmitReportInput(BaseModel):
    confirmed_text: str = Field(min_length=20, max_length=2_000)

    @model_validator(mode="after")
    def validate_confirmed_text(self) -> "SubmitReportInput":
        self.confirmed_text = self.confirmed_text.strip()
        if len(self.confirmed_text) < 20:
            raise ValueError("Bitte bestätige einen Meldetext mit mindestens 20 Zeichen.")
        return self


class PrivateReport(BaseModel):
    id: int
    problem_id: int | None
    text: str
    confirmed_text: str | None
    category: Category
    scope_kind: ScopeKind
    location_label: str
    latitude: float | None
    longitude: float | None
    observed_at: str
    suggested_problem_id: int | None
    category_detail: str
    client_token: str | None
    status: ReportStatus
    submitted_at: str | None
    withdrawn_at: str | None
    created_at: str
    updated_at: str


def _same_draft(report: dict, body: ReportDraftInput) -> bool:
    return (
        report["text"] == body.text
        and report["category"] == body.category
        and report["scope_kind"] == body.scope_kind
        and report["location_label"] == body.location_label
        and report["latitude"] == body.latitude
        and report["longitude"] == body.longitude
        and report["observed_at"][:10] == body.observed_on.isoformat()
        and report["category_detail"] == body.category_detail
        and report["suggested_problem_id"] == body.suggested_problem_id
    )


def _owned_report_or_404(store: ReportStore, report_id: int, owner_id: int) -> dict:
    report = store.get_owned_report(report_id, reporter_id=owner_id)
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Meldung nicht gefunden.")
    return report


@router.post("/entwuerfe", response_model=PrivateReport, status_code=status.HTTP_201_CREATED)
def create_report_draft(
    request: Request,
    body: ReportDraftInput,
    user: dict = Depends(require_verified_reporter),
    reports: ReportStore = Depends(get_report_store),
    problems: ProblemStore = Depends(get_problem_store),
) -> dict:
    owner_id = int(user["id"])
    client_token = str(body.client_token)
    existing = reports.get_owned_report_by_client_token(
        client_token,
        reporter_id=owner_id,
    )
    if existing:
        if not _same_draft(existing, body):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Dieser Entwurfsschlüssel wurde bereits für andere Angaben verwendet.",
            )
        return existing
    report_draft_limiter.check(request, key=f"reporter:{owner_id}")
    if body.suggested_problem_id is not None and not problems.get_public_problem(
        body.suggested_problem_id
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Das vorgeschlagene Problem ist nicht öffentlich verfügbar.",
        )
    observed_at = datetime.combine(
        body.observed_on, time(hour=12), tzinfo=timezone.utc
    ).isoformat(timespec="seconds")
    try:
        report_id = reports.create_draft(
            reporter_id=owner_id,
            text=body.text,
            category=body.category,
            scope_kind=body.scope_kind,
            location_label=body.location_label,
            latitude=body.latitude,
            longitude=body.longitude,
            observed_at=observed_at,
            suggested_problem_id=body.suggested_problem_id,
            category_detail=body.category_detail,
            client_token=client_token,
        )
    except sqlite3.IntegrityError as exc:
        concurrent = reports.get_owned_report_by_client_token(
            client_token,
            reporter_id=owner_id,
        )
        if concurrent and _same_draft(concurrent, body):
            return concurrent
        raise HTTPException(status.HTTP_409_CONFLICT, "Der Entwurf wurde bereits angelegt.") from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return _owned_report_or_404(reports, report_id, owner_id)


@router.get("/{report_id}", response_model=PrivateReport)
def private_report(
    report_id: int,
    user: dict = Depends(require_verified_reporter),
    reports: ReportStore = Depends(get_report_store),
) -> dict:
    return _owned_report_or_404(reports, report_id, int(user["id"]))


@router.post("/{report_id}/absenden", response_model=PrivateReport)
def submit_private_report(
    report_id: int,
    body: SubmitReportInput,
    user: dict = Depends(require_verified_reporter),
    reports: ReportStore = Depends(get_report_store),
) -> dict:
    owner_id = int(user["id"])
    owned = _owned_report_or_404(reports, report_id, owner_id)
    if owned["status"] != "draft":
        if (
            owned["status"] == "submitted"
            and owned["confirmed_text"] == body.confirmed_text
        ):
            return owned
        raise HTTPException(status.HTTP_409_CONFLICT, "Diese Meldung wurde bereits abgesendet.")
    try:
        return reports.submit_owned_report(
            report_id,
            reporter_id=owner_id,
            confirmed_text=body.confirmed_text,
        )
    except ValueError as exc:
        if "bereits abgesendet" in str(exc):
            current = _owned_report_or_404(reports, report_id, owner_id)
            if (
                current["status"] == "submitted"
                and current["confirmed_text"] == body.confirmed_text
            ):
                return current
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
