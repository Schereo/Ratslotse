"""Revision-bound external AI pre-screening for private civic reports.

The module owns the narrow boundary between private report persistence and an
injected evaluator. An evaluator receives only :class:`ExternalAiScreeningInput`;
report identity and claim metadata never cross that boundary.
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
    EXTERNAL_AI_SCREENING_ASSESSMENT_VERSION,
    EXTERNAL_AI_SCREENING_REASONS,
    EXTERNAL_AI_SCREENING_VERDICTS,
    ExternalAiScreening,
    ExternalAiScreeningInput,
    ExternalAiScreeningReason,
    ExternalAiScreeningVerdict,
    PrivateReportStore,
    normalize_external_ai_model_identifier,
    validate_external_ai_screening_result,
)
from kern import llm, prompts

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class EvaluatorResult:
    verdict: ExternalAiScreeningVerdict
    reason_code: ExternalAiScreeningReason
    model_identifier: str


class ExternalAiEvaluator(Protocol):
    """Evaluate only the deliberately minimized report projection."""

    def evaluate(self, screening_input: ExternalAiScreeningInput) -> EvaluatorResult:
        """Return one controlled assessment result or raise on failure."""
        ...


class InvalidEvaluatorResponse(ValueError):
    """The external evaluator did not return the strict controlled contract."""


_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "civic_report_screening",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "verdict": {
                    "type": "string",
                    "enum": list(EXTERNAL_AI_SCREENING_VERDICTS),
                },
                "reason_code": {
                    "type": "string",
                    "enum": list(EXTERNAL_AI_SCREENING_REASONS),
                },
            },
            "required": ["verdict", "reason_code"],
            "additionalProperties": False,
        },
    },
}


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for key, value in pairs:
        if key in parsed:
            raise InvalidEvaluatorResponse("Duplicate JSON key")
        parsed[key] = value
    return parsed


class OpenRouterCivicReportEvaluator:
    """Strict OpenRouter adapter using the project's central safeguarded client."""

    def __init__(self, *, model: str | None = None):
        selected_model = model or os.environ.get(
            "RATSLOTSE_CIVIC_REPORT_SCREENING_MODEL",
            "openai/gpt-4o-mini",
        )
        self.model = normalize_external_ai_model_identifier(selected_model)

    def evaluate(self, screening_input: ExternalAiScreeningInput) -> EvaluatorResult:
        if (
            screening_input.category not in PROBLEM_CATEGORIES
            or screening_input.scope_kind not in SCOPE_KINDS
            or not screening_input.observation_texts
            or any(
                not isinstance(text, str) or not text.strip()
                for text in screening_input.observation_texts
            )
        ):
            raise InvalidEvaluatorResponse("Invalid minimized screening input")
        report_data = json.dumps(
            {
                "observation_texts": list(screening_input.observation_texts),
                "category": screening_input.category,
                "scope_kind": screening_input.scope_kind,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        response = llm.chat_complete(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": prompts.get("civic_report_screening_system"),
                },
                {"role": "user", "content": report_data},
            ],
            response_format=_RESPONSE_FORMAT,
            extra_body=llm.strict_privacy_routing_extra_body(),
            temperature=0,
            max_tokens=120,
            timeout=30.0,
            _feature="civic_report_screening",
        )
        try:
            content = response.choices[0].message.content
            if not isinstance(content, str) or not content.strip():
                raise InvalidEvaluatorResponse("Empty evaluator response")
            parsed = json.loads(
                content,
                object_pairs_hook=_reject_duplicate_json_keys,
            )
        except InvalidEvaluatorResponse:
            raise
        except (AttributeError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise InvalidEvaluatorResponse("Malformed evaluator response") from exc
        if not isinstance(parsed, dict) or set(parsed) != {"verdict", "reason_code"}:
            raise InvalidEvaluatorResponse("Unexpected evaluator response fields")
        verdict = parsed["verdict"]
        reason_code = parsed["reason_code"]
        if not isinstance(verdict, str) or not isinstance(reason_code, str):
            raise InvalidEvaluatorResponse("Evaluator values must be strings")
        try:
            controlled_verdict, controlled_reason = (
                validate_external_ai_screening_result(verdict, reason_code)
            )
        except ValueError as exc:
            raise InvalidEvaluatorResponse("Uncontrolled evaluator result") from exc
        return EvaluatorResult(
            verdict=controlled_verdict,
            reason_code=controlled_reason,
            model_identifier=self.model,
        )


def screen_report_with_external_ai(
    store: PrivateReportStore,
    *,
    report_id: int,
    expected_revision: int,
    evaluator: ExternalAiEvaluator,
) -> ExternalAiScreening | None:
    """Claim, evaluate, and persist one current revision, failing closed."""
    current = store.get_current_external_ai_screening(report_id)
    if current is not None and current.content_revision == expected_revision:
        return current

    candidate = store.claim_external_ai_screening(
        report_id,
        expected_revision=expected_revision,
        assessment_version=EXTERNAL_AI_SCREENING_ASSESSMENT_VERSION,
        claim_token=secrets.token_urlsafe(24),
    )
    if candidate is None:
        current = store.get_current_external_ai_screening(report_id)
        if current is not None and current.content_revision == expected_revision:
            return current
        return None

    try:
        screening_input = store.start_claimed_external_ai_screening(candidate)
        if screening_input is None:
            store.release_external_ai_screening(candidate)
            return None
        if not screening_input.observation_texts or any(
            not text.strip() for text in screening_input.observation_texts
        ):
            store.release_external_ai_screening(candidate)
            return None
        result = evaluator.evaluate(screening_input)
        return store.complete_external_ai_screening(
            candidate,
            verdict=result.verdict,
            reason_code=result.reason_code,
            model_identifier=result.model_identifier,
        )
    except Exception:  # noqa: BLE001 - provider failure must not affect submission
        try:
            store.release_external_ai_screening(candidate)
        except Exception:  # noqa: BLE001 - failure remains closed and log stays generic
            pass
        _LOGGER.warning("External AI pre-screening did not complete")
        return None
