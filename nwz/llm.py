"""Central LLM client: singleton OpenAI/OpenRouter instance + retried completion.

All modules that call the LLM should use chat_complete() from here rather than
constructing their own OpenAI instances. This centralises auth and base-url in
one place and retries transient errors (429, 5xx, network) automatically with
exponential back-off via tenacity — so a single rate-limit spike no longer
kills an entire cron run.
"""
from __future__ import annotations

import json
import os
from typing import Any

from openai import (
    OpenAI,
    RateLimitError,
    APIStatusError,
    APIConnectionError,
    APITimeoutError,
)
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Per-model request parameters, applied automatically by chat_complete() based on
# the `model` argument. This is the single place that stores HOW each model must
# be called, so switching the active model (e.g. classify.MODEL) just carries the
# right parameters with it — no call-site changes needed. Add an entry when
# introducing a new model.
#
# Recognised keys per model:
#   - "min_max_tokens": int — raise max_tokens to at least this (a floor, not an
#       override; the caller may ask for more).
#   - any other key — a chat.completions.create() kwarg merged UNDER the caller's
#       kwargs (caller wins); a nested "extra_body" dict is shallow-merged.
#
# Why the floor for deepseek: deepseek-v4 are reasoning models and their reasoning
# tokens count against the max_tokens output budget. The reasoning length varies
# wildly (observed up to ~8.5k tokens); if it does not fit, the response comes
# back finish_reason='length' with EMPTY content — the recurring "null content"
# failure on large editions. OpenRouter's reasoning.max_tokens cap is NOT honored
# by this provider, so instead we guarantee enough budget. max_tokens is only a
# ceiling — you are billed for tokens actually generated — so a generous floor is
# free unless the reasoning really grows.
DEEPSEEK_MIN_MAX_TOKENS = int(os.environ.get("NWZ_DEEPSEEK_MIN_MAX_TOKENS", "24000"))

MODEL_PARAMS: dict[str, dict[str, Any]] = {
    "openai/gpt-4o": {},
    "openai/gpt-4o-mini": {},
    "deepseek/deepseek-v4-pro": {"min_max_tokens": DEEPSEEK_MIN_MAX_TOKENS},
    "deepseek/deepseek-v4-flash": {"min_max_tokens": DEEPSEEK_MIN_MAX_TOKENS},
}


def _with_model_params(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Merge the stored params for kwargs['model'] into the caller's kwargs."""
    defaults = MODEL_PARAMS.get(kwargs.get("model", ""))
    if not defaults:
        return kwargs
    defaults = dict(defaults)
    floor = defaults.pop("min_max_tokens", None)
    merged = {**defaults, **kwargs}
    if "extra_body" in defaults and "extra_body" in kwargs:
        merged["extra_body"] = {**defaults["extra_body"], **kwargs["extra_body"]}
    if floor is not None:
        merged["max_tokens"] = max(kwargs.get("max_tokens") or 0, floor)
    return merged


_client: OpenAI | None = None


def get_client() -> OpenAI:
    """Return (and lazily create) the shared OpenRouter client."""
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.environ["OPENROUTER_API_KEY"],
            base_url=OPENROUTER_BASE_URL,
        )
    return _client


def _is_transient(exc: BaseException) -> bool:
    """True for errors worth retrying: rate-limit, server errors, network, or a
    malformed/truncated response body (provider returned non-JSON — seen
    intermittently with reasoning models on large requests)."""
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, APIStatusError) and exc.status_code >= 500:
        return True
    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        return True
    if isinstance(exc, json.JSONDecodeError):
        return True
    return False


@retry(
    retry=retry_if_exception(_is_transient),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(4),
    reraise=True,
)
def chat_complete(**kwargs: Any):
    """Call chat.completions.create() with per-model defaults + retry on errors.

    Stored MODEL_PARAMS for the requested model are merged in first (so e.g. the
    deepseek reasoning cap travels with the model), then the call is retried up to
    4 times with exponential back-off (2 s → 4 s → 8 s → 60 s cap) for 429
    rate-limit, 5xx server errors, and network failures. Non-transient client
    errors (4xx other than 429) propagate immediately without retry.
    """
    return get_client().chat.completions.create(**_with_model_params(kwargs))


def chat_stream(**kwargs: Any):
    """Stream content deltas as they are generated — used for the live "Frag den Rat"
    answer so the UI can render tokens as they arrive. Same per-model params and
    connect-time retry as chat_complete (the retried call returns the stream object;
    a mid-stream failure propagates without retry). Yields non-empty text chunks."""
    stream = chat_complete(stream=True, **kwargs)
    for chunk in stream:
        if not chunk.choices:
            continue
        text = chunk.choices[0].delta.content
        if text:
            yield text
