"""Private review boundary for explicit public-projection confirmation."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from buergerportal.projections import (
    ExistingProjection,
    NewCitywideProjection,
    ProblemAssignment,
    ProjectionCandidate,
    ProjectionCandidateSummary,
    ProjectionConflict,
    ProjectionStore,
    PublicProjectionTarget,
)
from buergerportal.reports import ReviewerNotEligible

from ..antworten import (
    ProjectionCandidateListOut,
    ProjectionCandidateOut,
    ProjectionCandidateSummaryOut,
    ProjectionConfirmationOut,
    ProjectionTargetOut,
)
from ..deps import (
    get_projection_store,
    require_buergerportal_feature,
    require_moderation_reviewer,
)
from ..schemas import (
    ExistingProjectionConfirmationIn,
    NewCitywideProjectionConfirmationIn,
)

router = APIRouter(
    prefix="/api/moderation/projektionen",
    tags=["moderation"],
    dependencies=[Depends(require_buergerportal_feature)],
)


def _summary_out(candidate: ProjectionCandidateSummary) -> ProjectionCandidateSummaryOut:
    return {
        "id": candidate.report_id,
        "content_revision": candidate.content_revision,
        "text_preview": candidate.text_preview,
        "category": candidate.category,
        "scope_kind": candidate.scope_kind,
        "observed_on": candidate.observed_on,
    }


def _detail_out(candidate: ProjectionCandidate) -> ProjectionCandidateOut:
    return {
        "id": candidate.report_id,
        "content_revision": candidate.content_revision,
        "category": candidate.category,
        "scope_kind": candidate.scope_kind,
        "observations": [
            {"text": observation.text, "observed_on": observation.observed_on}
            for observation in candidate.observations
        ],
    }


def _target_out(target: PublicProjectionTarget) -> ProjectionTargetOut:
    return {
        "problem_id": target.problem_id,
        "title": target.title,
        "summary": target.summary,
        "category": target.category,
        "scope_kind": target.scope_kind,
        "status": target.status,
        "independent_reports": target.independent_reports,
    }


def _confirmation_out(assignment: ProblemAssignment) -> ProjectionConfirmationOut:
    return {
        "report_id": assignment.report_id,
        "content_revision": assignment.content_revision,
        "problem_id": assignment.problem_id,
        "problem_title": assignment.problem_title,
    }


def _http_exception(error: ValueError) -> HTTPException:
    if isinstance(error, ReviewerNotEligible):
        return HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Dieses Konto darf öffentliche Projektionen nicht bestätigen.",
        )
    if isinstance(error, ProjectionConflict):
        return HTTPException(
            status.HTTP_409_CONFLICT,
            "Diese Meldung oder Projektion ist nicht mehr verfügbar.",
        )
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error))


@router.get("")
def list_candidates(
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0, le=2**63 - 1),
    reviewer: dict = Depends(require_moderation_reviewer),
    store: ProjectionStore = Depends(get_projection_store),
) -> ProjectionCandidateListOut:
    try:
        page = store.list_candidates(
            reviewer_id=int(reviewer["id"]),
            limit=limit,
            offset=offset,
        )
    except ValueError as error:
        raise _http_exception(error) from None
    return {
        "reports": [_summary_out(candidate) for candidate in page.reports],
        "total": page.total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{report_id}")
def get_candidate(
    report_id: int,
    reviewer: dict = Depends(require_moderation_reviewer),
    store: ProjectionStore = Depends(get_projection_store),
) -> ProjectionCandidateOut:
    try:
        candidate = store.get_candidate(report_id, reviewer_id=int(reviewer["id"]))
    except ValueError as error:
        raise _http_exception(error) from None
    if candidate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Meldung nicht gefunden.")
    return _detail_out(candidate)


@router.get("/{report_id}/ziele")
def list_targets(
    report_id: int,
    q: str = Query("", max_length=100),
    limit: int = Query(20, ge=1, le=50),
    reviewer: dict = Depends(require_moderation_reviewer),
    store: ProjectionStore = Depends(get_projection_store),
) -> list[ProjectionTargetOut]:
    try:
        candidate = store.get_candidate(report_id, reviewer_id=int(reviewer["id"]))
        if candidate is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Meldung nicht gefunden.")
        return [
            _target_out(target)
            for target in store.list_targets(
                reviewer_id=int(reviewer["id"]),
                query=q,
                limit=limit,
            )
        ]
    except HTTPException:
        raise
    except ValueError as error:
        raise _http_exception(error) from None


@router.post("/{report_id}/bestehendes-problem", status_code=status.HTTP_201_CREATED)
def assign_existing(
    report_id: int,
    body: ExistingProjectionConfirmationIn,
    reviewer: dict = Depends(require_moderation_reviewer),
    store: ProjectionStore = Depends(get_projection_store),
) -> ProjectionConfirmationOut:
    try:
        assignment = store.confirm_assignment(
            report_id,
            reviewer_id=int(reviewer["id"]),
            expected_revision=body.expected_revision,
            target=ExistingProjection(body.problem_id),
        )
    except ValueError as error:
        raise _http_exception(error) from None
    return _confirmation_out(assignment)


@router.post(
    "/{report_id}/neue-stadtweite-projektion",
    status_code=status.HTTP_201_CREATED,
)
def create_citywide(
    report_id: int,
    body: NewCitywideProjectionConfirmationIn,
    reviewer: dict = Depends(require_moderation_reviewer),
    store: ProjectionStore = Depends(get_projection_store),
) -> ProjectionConfirmationOut:
    try:
        assignment = store.confirm_assignment(
            report_id,
            reviewer_id=int(reviewer["id"]),
            expected_revision=body.expected_revision,
            target=NewCitywideProjection(title=body.title, summary=body.summary),
        )
    except ValueError as error:
        raise _http_exception(error) from None
    return _confirmation_out(assignment)
