"""Private, data-minimal HTTP boundary for human report moderation."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from buergerportal.rejection_drafting import (
    RejectionDraftEvaluator,
    draft_rejection_explanation,
)
from buergerportal.reports import (
    HumanModerationDecision,
    ModerationConflict,
    ModerationReport,
    ModerationReportSummary,
    PrivateReportNotFound,
    PrivateReportStore,
    ReviewerNotEligible,
)

from ..antworten import (
    ModerationDecisionOut,
    ModerationReportListOut,
    ModerationReportOut,
    ModerationReportSummaryOut,
    RejectionDraftOut,
)
from ..deps import (
    get_private_report_store,
    get_rejection_draft_evaluator,
    require_moderation_reviewer,
)
from ..ratelimit import civic_report_rejection_draft_limiter
from ..schemas import ModerationDecisionIn, RejectionDraftRequestIn

router = APIRouter(prefix="/api/moderation/meldungen", tags=["moderation"])


def _summary_out(report: ModerationReportSummary) -> ModerationReportSummaryOut:
    return {
        "id": report.id,
        "text_preview": report.text_preview,
        "category": report.category,
        "scope_kind": report.scope_kind,
        "observed_on": report.observed_on,
        "local_outcome": report.local_outcome,
        "local_reason_codes": list(report.local_reason_codes),
        "ai_verdict": report.ai_verdict,
        "ai_reason_code": report.ai_reason_code,
    }


def _detail_out(report: ModerationReport) -> ModerationReportOut:
    return {
        "id": report.id,
        "category": report.category,
        "scope_kind": report.scope_kind,
        "content_revision": report.content_revision,
        "observations": [
            {
                "text": observation.text,
                "observed_on": observation.observed_on,
            }
            for observation in report.observations
        ],
        "local_outcome": report.local_outcome,
        "local_reason_codes": list(report.local_reason_codes),
        "ai_verdict": report.ai_verdict,
        "ai_reason_code": report.ai_reason_code,
    }


def _decision_out(decision: HumanModerationDecision) -> ModerationDecisionOut:
    return {
        "report_id": decision.report_id,
        "content_revision": decision.content_revision,
        "outcome": decision.outcome,
        "rejection_explanation": decision.rejection_explanation,
        "decided_at": decision.decided_at,
    }


def _http_exception(error: ValueError) -> HTTPException:
    if isinstance(error, PrivateReportNotFound):
        return HTTPException(status.HTTP_404_NOT_FOUND, "Meldung nicht gefunden.")
    if isinstance(error, ModerationConflict):
        return HTTPException(
            status.HTTP_409_CONFLICT,
            "Für diese Meldungsfassung liegt bereits eine Entscheidung vor.",
        )
    if isinstance(error, ReviewerNotEligible):
        return HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Dieses Konto darf private Meldungen nicht moderieren.",
        )
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error))


@router.get("")
def list_reports(
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0, le=2**63 - 1),
    reviewer: dict = Depends(require_moderation_reviewer),
    store: PrivateReportStore = Depends(get_private_report_store),
) -> ModerationReportListOut:
    try:
        page = store.list_reports_for_moderation(
            reviewer_id=int(reviewer["id"]),
            limit=limit,
            offset=offset,
        )
    except ValueError as error:
        raise _http_exception(error) from None
    return {
        "reports": [_summary_out(report) for report in page.reports],
        "total": page.total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{report_id}")
def get_report(
    report_id: int,
    reviewer: dict = Depends(require_moderation_reviewer),
    store: PrivateReportStore = Depends(get_private_report_store),
) -> ModerationReportOut:
    try:
        report = store.get_report_for_moderation(
            report_id,
            reviewer_id=int(reviewer["id"]),
        )
    except ValueError as error:
        raise _http_exception(error) from None
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Meldung nicht gefunden.")
    return _detail_out(report)


@router.post("/{report_id}/ablehnungsentwurf")
def draft_rejection(
    report_id: int,
    body: RejectionDraftRequestIn,
    request: Request,
    reviewer: dict = Depends(require_moderation_reviewer),
    store: PrivateReportStore = Depends(get_private_report_store),
    evaluator: RejectionDraftEvaluator = Depends(get_rejection_draft_evaluator),
) -> RejectionDraftOut:
    reviewer_id = int(reviewer["id"])
    try:
        detail = store.get_report_for_moderation(
            report_id,
            reviewer_id=reviewer_id,
        )
    except ValueError as error:
        raise _http_exception(error) from None
    if detail is None or detail.content_revision != body.expected_revision:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Meldung nicht gefunden.")
    civic_report_rejection_draft_limiter.check(request, subject=reviewer_id)
    suggestion = draft_rejection_explanation(
        store,
        report_id=report_id,
        expected_revision=body.expected_revision,
        reviewer_id=reviewer_id,
        evaluator=evaluator,
    )
    return {
        "content_revision": body.expected_revision,
        "suggestion": suggestion.suggestion if suggestion is not None else None,
        "available": suggestion is not None,
    }


@router.post("/{report_id}/entscheidung")
def decide_report(
    report_id: int,
    body: ModerationDecisionIn,
    reviewer: dict = Depends(require_moderation_reviewer),
    store: PrivateReportStore = Depends(get_private_report_store),
) -> ModerationDecisionOut:
    try:
        decision = store.decide_report(
            report_id,
            reviewer_id=int(reviewer["id"]),
            expected_revision=body.expected_revision,
            outcome=body.outcome,
            rejection_explanation=body.rejection_explanation,
        )
    except ValueError as error:
        raise _http_exception(error) from None
    return _decision_out(decision)
