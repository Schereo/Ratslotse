"""Eigentümergebundene HTTP-Grenze für private Bürgerportal-Meldungen."""
from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status

from buergerportal.reports import (
    DraftContent,
    IdempotencyConflict,
    InvalidReportTransition,
    PrivateReport,
    PrivateReportNotFound,
    PrivateReportStore,
    ReporterNotEligible,
)

from ..antworten import PrivateReportOut
from ..deps import get_private_report_store, require_verified_reporter
from ..schemas import (
    Ortsbezug,
    PrivateDraftContentIn,
    PrivateDraftCreateIn,
    PrivateDraftUpdateIn,
    PrivateSubmitIn,
    Problemkategorie,
)

router = APIRouter(prefix="/api/meldungen", tags=["meldungen"])


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


def _private_report_out(report: PrivateReport) -> PrivateReportOut:
    return {
        "id": report.id,
        "draft_text": report.draft_text,
        "confirmed_text": report.confirmed_text,
        "category": cast(Problemkategorie, report.category),
        "scope_kind": cast(Ortsbezug, report.scope_kind),
        "observed_on": report.observed_on,
        "location_label": report.location_label,
        "latitude": report.latitude,
        "longitude": report.longitude,
        "state": report.state,
        "content_revision": report.content_revision,
        "submitted_at": report.submitted_at,
        "created_at": report.created_at,
        "updated_at": report.updated_at,
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


@router.post("/entwuerfe", status_code=status.HTTP_201_CREATED)
def create_draft(
    body: PrivateDraftCreateIn,
    user: dict = Depends(require_verified_reporter),
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
    user: dict = Depends(require_verified_reporter),
    store: PrivateReportStore = Depends(get_private_report_store),
) -> PrivateReportOut:
    report = store.get_owned_report(report_id, reporter_id=int(user["id"]))
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Meldung nicht gefunden.")
    return _private_report_out(report)


@router.put("/{report_id}/entwurf")
def update_draft(
    report_id: int,
    body: PrivateDraftUpdateIn,
    user: dict = Depends(require_verified_reporter),
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
    user: dict = Depends(require_verified_reporter),
    store: PrivateReportStore = Depends(get_private_report_store),
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
    return _private_report_out(report)
