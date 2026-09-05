"""Revision-bound, human-editable rejection explanation drafting.

The evaluator sees only :class:`RejectionDraftInput`. For reports stopped by
local privacy/safety rules, that projection deliberately contains no report
text at all.
"""
from __future__ import annotations

import json
import logging
import os
import secrets
from dataclasses import dataclass
from typing import Any, Protocol

from buergerportal.domain import PROBLEM_CATEGORIES, SCOPE_KINDS
from buergerportal.reports import (
    EXTERNAL_AI_SCREENING_REASONS,
    EXTERNAL_AI_SCREENING_VERDICTS,
    LOCAL_SCREENING_REASONS,
    REJECTION_DRAFT_VERSION,
    PrivateReportStore,
    RejectionDraftInput,
    RejectionDraftSuggestion,
    normalize_external_ai_model_identifier,
)
from kern import llm, prompts

_LOGGER = logging.getLogger(__name__)
_MAX_SUGGESTION_LENGTH = 1000


@dataclass(frozen=True)
class RejectionDraftEvaluatorResult:
    suggestion: str
    model_identifier: str


class RejectionDraftEvaluator(Protocol):
    def evaluate(
        self,
        drafting_input: RejectionDraftInput,
    ) -> RejectionDraftEvaluatorResult:
        """Return a bounded editable suggestion, never a decision."""
        ...


class InvalidRejectionDraftResponse(ValueError):
    """The external drafter did not return the strict bounded contract."""


_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "civic_report_rejection_draft",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "suggestion": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": _MAX_SUGGESTION_LENGTH,
                }
            },
            "required": ["suggestion"],
            "additionalProperties": False,
        },
    },
}


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for key, value in pairs:
        if key in parsed:
            raise InvalidRejectionDraftResponse("Duplicate JSON key")
        parsed[key] = value
    return parsed


def _validate_input(drafting_input: RejectionDraftInput) -> None:
    if (
        drafting_input.category not in PROBLEM_CATEGORIES
        or drafting_input.scope_kind not in SCOPE_KINDS
        or any(reason not in LOCAL_SCREENING_REASONS for reason in drafting_input.local_reason_codes)
        or len(set(drafting_input.local_reason_codes)) != len(drafting_input.local_reason_codes)
        or drafting_input.ai_verdict not in (*EXTERNAL_AI_SCREENING_VERDICTS, None)
        or drafting_input.ai_reason_code not in (*EXTERNAL_AI_SCREENING_REASONS, None)
    ):
        raise InvalidRejectionDraftResponse("Invalid controlled drafting input")
    if drafting_input.local_reason_codes:
        if (
            drafting_input.observation_texts
            or drafting_input.ai_verdict is not None
            or drafting_input.ai_reason_code is not None
        ):
            raise InvalidRejectionDraftResponse("Locally blocked input contains private text")
    elif not drafting_input.observation_texts or any(
        not isinstance(text, str) or not text.strip()
        for text in drafting_input.observation_texts
    ):
        raise InvalidRejectionDraftResponse("Cleared input requires observation text")


class OpenRouterRejectionDraftEvaluator:
    """Strict central-LLM adapter that only drafts editable German wording."""

    def __init__(self, *, model: str | None = None):
        selected_model = model or os.environ.get(
            "RATSLOTSE_CIVIC_REPORT_REJECTION_DRAFT_MODEL",
            "openai/gpt-4o-mini",
        )
        self.model = normalize_external_ai_model_identifier(selected_model)

    def evaluate(
        self,
        drafting_input: RejectionDraftInput,
    ) -> RejectionDraftEvaluatorResult:
        _validate_input(drafting_input)
        payload = json.dumps(
            {
                "observation_texts": list(drafting_input.observation_texts),
                "category": drafting_input.category,
                "scope_kind": drafting_input.scope_kind,
                "local_reason_codes": list(drafting_input.local_reason_codes),
                "ai_verdict": drafting_input.ai_verdict,
                "ai_reason_code": drafting_input.ai_reason_code,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        response = llm.chat_complete(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": prompts.get("civic_report_rejection_draft_system"),
                },
                {"role": "user", "content": payload},
            ],
            response_format=_RESPONSE_FORMAT,
            extra_body=llm.strict_privacy_routing_extra_body(),
            temperature=0,
            max_tokens=300,
            timeout=30.0,
            _feature="civic_report_rejection_drafting",
        )
        try:
            content = response.choices[0].message.content
            if not isinstance(content, str) or not content.strip():
                raise InvalidRejectionDraftResponse("Empty drafting response")
            parsed = json.loads(content, object_pairs_hook=_reject_duplicate_json_keys)
        except InvalidRejectionDraftResponse:
            raise
        except (AttributeError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise InvalidRejectionDraftResponse("Malformed drafting response") from exc
        if not isinstance(parsed, dict) or set(parsed) != {"suggestion"}:
            raise InvalidRejectionDraftResponse("Unexpected drafting response fields")
        suggestion = parsed["suggestion"]
        if not isinstance(suggestion, str):
            raise InvalidRejectionDraftResponse("Drafting suggestion must be text")
        suggestion = suggestion.strip()
        if not suggestion or len(suggestion) > _MAX_SUGGESTION_LENGTH:
            raise InvalidRejectionDraftResponse("Drafting suggestion is out of bounds")
        return RejectionDraftEvaluatorResult(
            suggestion=suggestion,
            model_identifier=self.model,
        )


def draft_rejection_explanation(
    store: PrivateReportStore,
    *,
    report_id: int,
    expected_revision: int,
    reviewer_id: int,
    evaluator: RejectionDraftEvaluator,
) -> RejectionDraftSuggestion | None:
    """Return a cached suggestion or perform one claimed, fail-closed call."""
    current = store.get_current_rejection_draft(
        report_id,
        reviewer_id=reviewer_id,
    )
    if current is not None and current.content_revision == expected_revision:
        return current
    candidate = store.claim_rejection_draft(
        report_id,
        expected_revision=expected_revision,
        reviewer_id=reviewer_id,
        drafting_version=REJECTION_DRAFT_VERSION,
        claim_token=secrets.token_urlsafe(24),
    )
    if candidate is None:
        current = store.get_current_rejection_draft(
            report_id,
            reviewer_id=reviewer_id,
        )
        if current is not None and current.content_revision == expected_revision:
            return current
        return None
    try:
        drafting_input = store.start_claimed_rejection_draft(
            candidate,
            reviewer_id=reviewer_id,
        )
        if drafting_input is None:
            store.release_rejection_draft(candidate)
            return None
        result = evaluator.evaluate(drafting_input)
        return store.complete_rejection_draft(
            candidate,
            suggestion=result.suggestion,
            model_identifier=result.model_identifier,
        )
    except Exception:  # noqa: BLE001 — provider failure must leave human control intact
        try:
            store.release_rejection_draft(candidate)
        except Exception:  # noqa: BLE001 — keep failure logs data-free
            pass
        _LOGGER.warning("Rejection explanation drafting did not complete")
        return None
