"""Eigentümergebundene HTTP-Grenze für private Bürgerportal-Meldungen."""
from __future__ import annotations

import logging

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)

from buergerportal.projections import OwnerPublicAssignment, ProjectionStore
from buergerportal.reports import (
    DraftContent,
    IdempotencyConflict,
    InvalidReportTransition,
    PrivateReport,
    PrivateReportNotFound,
    PrivateReportSummary,
    PrivateReportStore,
    ReporterNotEligible,
)

from ..antworten import (
    PrivateReportListOut,
    PrivateReportOut,
    PrivateReportSummaryOut,
)
from ..deps import (
    get_external_ai_screening_scheduler,
    get_owner_projection_store,
    get_private_report_store,
    require_eligible_reporter,
)
from ..ratelimit import civic_report_screening_limiter
from ..report_screening import BackgroundExternalAiScreeningScheduler
from ..schemas import (
    PrivateDraftContentIn,
    PrivateDraftCreateIn,
    PrivateDraftUpdateIn,
    PrivateSubmitIn,
)

router = APIRouter(prefix="/api/meldungen", tags=["meldungen"])
_LOGGER = logging.getLogger(__name__)


def _content(body: PrivateDraftContentIn) -> DraftContent:
    return DraftContent(
        text=body.text,
        category=body.category,
        scope_kind=body.scope_kind,
        observed_on=body.observed_on,
        location_label=body.location_label,
        latitude=body.latitude,
        longitude=body.longitude,
    )


def _public_projection_out(
    assignment: OwnerPublicAssignment | None,
) -> dict[str, int | str] | None:
    if assignment is None:
        return None
    return {"id": assignment.problem_id, "title": assignment.title}


def _private_report_summary_out(
    report: PrivateReportSummary,
    assignment: OwnerPublicAssignment | None = None,
) -> PrivateReportSummaryOut:
    return {
        "id": report.id,
        "text_preview": report.text_preview,
        "category": report.category,
        "scope_kind": report.scope_kind,
        "observed_on": report.observed_on,
        "state": report.state,
        "content_revision": report.content_revision,
        "submitted_at": report.submitted_at,
        "updated_at": report.updated_at,
        "moderation_outcome": report.moderation_outcome,
        "rejection_explanation": report.rejection_explanation,
        "public_projection": _public_projection_out(assignment),
    }


def _private_report_out(
    report: PrivateReport,
    assignment: OwnerPublicAssignment | None = None,
) -> PrivateReportOut:
    return {
        "id": report.id,
        "draft_text": report.draft_text,
        "confirmed_text": report.confirmed_text,
        "category": report.category,
        "scope_kind": report.scope_kind,
        "observed_on": report.observed_on,
        "location_label": report.location_label,
        "latitude": report.latitude,
        "longitude": report.longitude,
        "state": report.state,
        "content_revision": report.content_revision,
        "submitted_at": report.submitted_at,
        "created_at": report.created_at,
        "updated_at": report.updated_at,
        "moderation_outcome": report.moderation_outcome,
        "rejection_explanation": report.rejection_explanation,
        "public_projection": _public_projection_out(assignment),
    }


def _http_exception(error: ValueError) -> HTTPException:
    if isinstance(error, PrivateReportNotFound):
        return HTTPException(status.HTTP_404_NOT_FOUND, "Meldung nicht gefunden.")
    if isinstance(error, (IdempotencyConflict, InvalidReportTransition)):
        return HTTPException(
            status.HTTP_409_CONFLICT,
            "Die Meldung wurde zwischenzeitlich geändert oder bereits abgesendet.",
        )
    if isinstance(error, ReporterNotEligible):
        return HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Dieses Konto kann keine privaten Meldungen abgeben.",
        )
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error))


@router.get("")
def list_reports(
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0, le=2**63 - 1),
    user: dict = Depends(require_eligible_reporter),
    store: PrivateReportStore = Depends(get_private_report_store),
    projections: ProjectionStore | None = Depends(get_owner_projection_store),
) -> PrivateReportListOut:
    try:
        page = store.list_owned_reports(
            reporter_id=int(user["id"]),
            limit=limit,
            offset=offset,
        )
    except ValueError as error:
        raise _http_exception(error) from None
    public_assignments = (
        projections.list_owner_assignments(
            reporter_id=int(user["id"]),
            report_ids=[report.id for report in page.reports],
        )
        if projections is not None
        else {}
    )
    return {
        "reports": [
            _private_report_summary_out(report, public_assignments.get(report.id))
            for report in page.reports
        ],
        "total": page.total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/entwuerfe", status_code=status.HTTP_201_CREATED)
def create_draft(
    body: PrivateDraftCreateIn,
    user: dict = Depends(require_eligible_reporter),
    store: PrivateReportStore = Depends(get_private_report_store),
) -> PrivateReportOut:
    try:
        report = store.create_owned_draft_idempotent(
            reporter_id=int(user["id"]),
            idempotency_key=body.idempotency_key,
            content=_content(body),
        )
    except ValueError as error:
        raise _http_exception(error) from None
    return _private_report_out(report)


@router.get("/{report_id}")
def get_report(
    report_id: int,
    user: dict = Depends(require_eligible_reporter),
    store: PrivateReportStore = Depends(get_private_report_store),
    projections: ProjectionStore | None = Depends(get_owner_projection_store),
) -> PrivateReportOut:
    reporter_id = int(user["id"])
    report = store.get_owned_report(report_id, reporter_id=reporter_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Meldung nicht gefunden.")
    assignment = (
        projections.list_owner_assignments(
            reporter_id=reporter_id,
            report_ids=[report.id],
        ).get(report.id)
        if projections is not None
        else None
    )
    return _private_report_out(report, assignment)


@router.put("/{report_id}/entwurf")
def update_draft(
    report_id: int,
    body: PrivateDraftUpdateIn,
    user: dict = Depends(require_eligible_reporter),
    store: PrivateReportStore = Depends(get_private_report_store),
) -> PrivateReportOut:
    try:
        report = store.update_owned_draft(
            report_id,
            reporter_id=int(user["id"]),
            content=_content(body),
            expected_revision=body.expected_revision,
        )
    except ValueError as error:
        raise _http_exception(error) from None
    return _private_report_out(report)


@router.post("/{report_id}/absenden")
def submit_draft(
    report_id: int,
    body: PrivateSubmitIn,
    background_tasks: BackgroundTasks,
    request: Request,
    user: dict = Depends(require_eligible_reporter),
    store: PrivateReportStore = Depends(get_private_report_store),
    screening_scheduler: BackgroundExternalAiScreeningScheduler = Depends(
        get_external_ai_screening_scheduler
    ),
) -> PrivateReportOut:
    try:
        report = store.submit_owned_draft(
            report_id,
            reporter_id=int(user["id"]),
            confirmed_text=body.confirmed_text,
            expected_revision=body.expected_revision,
        )
    except ValueError as error:
        raise _http_exception(error) from None
    try:
        civic_report_screening_limiter.check(request, subject=int(user["id"]))
        screening_scheduler.schedule(
            background_tasks,
            report_id=report.id,
            expected_revision=report.content_revision,
        )
    except HTTPException:
        _LOGGER.warning("External AI pre-screening quota is exhausted")
    except Exception:  # noqa: BLE001 - private submission remains authoritative
        _LOGGER.warning("External AI pre-screening could not be scheduled")
    return _private_report_out(report)
