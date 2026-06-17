"""Central LLM client: singleton OpenAI/OpenRouter instance + retried completion.

All modules that call the LLM should use chat_complete() from here rather than
constructing their own OpenAI instances. This centralises auth and base-url in
one place and retries transient errors (429, 5xx, network) automatically with
exponential back-off via tenacity — so a single rate-limit spike no longer
kills an entire cron run.
"""
from __future__ import annotations

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
    """True for errors worth retrying: rate-limit, server errors, network."""
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, APIStatusError) and exc.status_code >= 500:
        return True
    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        return True
    return False


@retry(
    retry=retry_if_exception(_is_transient),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(4),
    reraise=True,
)
def chat_complete(**kwargs: Any):
    """Call chat.completions.create() with automatic retry on transient errors.

    Retries up to 4 times with exponential back-off (2 s → 4 s → 8 s → 60 s cap)
    for 429 rate-limit, 5xx server errors, and network failures. Non-transient
    client errors (4xx other than 429) propagate immediately without retry.
    """
    return get_client().chat.completions.create(**kwargs)
