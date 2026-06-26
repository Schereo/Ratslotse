"""Offline tests for nwz/llm.py: singleton client and _is_transient predicate."""
from __future__ import annotations

import pytest

from nwz import llm


@pytest.fixture(autouse=True)
def _reset_client():
    """Ensure the cached client singleton is cleared between tests."""
    saved = llm._client
    llm._client = None
    yield
    llm._client = saved


# --------------------------------------------------------------------------- #
# Singleton behaviour
# --------------------------------------------------------------------------- #

def test_get_client_is_singleton(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    c1 = llm.get_client()
    c2 = llm.get_client()
    assert c1 is c2


def test_get_client_uses_openrouter_base_url(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    client = llm.get_client()
    assert str(client.base_url).rstrip("/") == llm.OPENROUTER_BASE_URL.rstrip("/")


def test_get_client_reads_api_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "my-secret-key")
    client = llm.get_client()
    assert client.api_key == "my-secret-key"


# --------------------------------------------------------------------------- #
# _is_transient classification
# --------------------------------------------------------------------------- #

def _make_request():
    import httpx
    return httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")


def test_is_transient_rate_limit_error():
    import httpx
    from openai import RateLimitError
    resp = httpx.Response(429, request=_make_request())
    exc = RateLimitError("rate limited", response=resp, body={})
    assert llm._is_transient(exc)


def test_is_transient_5xx_status_error():
    import httpx
    from openai import APIStatusError
    for code in (500, 502, 503, 504):
        resp = httpx.Response(code, request=_make_request())
        exc = APIStatusError("server error", response=resp, body={})
        assert llm._is_transient(exc), f"Expected 5xx ({code}) to be transient"


def test_is_transient_4xx_non_429_not_transient():
    import httpx
    from openai import APIStatusError
    for code in (400, 401, 403, 404, 422):
        resp = httpx.Response(code, request=_make_request())
        exc = APIStatusError("client error", response=resp, body={})
        assert not llm._is_transient(exc), f"Expected 4xx ({code}) to NOT be transient"


def test_is_transient_connection_error():
    from openai import APIConnectionError
    exc = APIConnectionError(request=_make_request())
    assert llm._is_transient(exc)


def test_is_transient_timeout_error():
    from openai import APITimeoutError
    exc = APITimeoutError(request=_make_request())
    assert llm._is_transient(exc)


def test_is_transient_plain_exception_is_false():
    assert not llm._is_transient(ValueError("nope"))
    assert not llm._is_transient(RuntimeError("nope"))
    assert not llm._is_transient(KeyError("nope"))


# --------------------------------------------------------------------------- #
# chat_complete delegates to get_client()
# --------------------------------------------------------------------------- #

def test_chat_complete_delegates_to_get_client(monkeypatch):
    """chat_complete should call client.chat.completions.create with the kwargs."""
    calls = []

    class _FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            return "response"

    class _FakeClient:
        chat = type("", (), {"completions": _FakeCompletions()})()

    monkeypatch.setenv("NWZ_OPENROUTER_ROUTING", "off")  # test pure delegation, no routing block
    monkeypatch.setattr(llm, "get_client", lambda: _FakeClient())
    result = llm.chat_complete(model="openai/gpt-4o-mini", messages=[])
    assert result == "response"
    assert calls == [{"model": "openai/gpt-4o-mini", "messages": []}]


def test_provider_routing_excludes_china_and_requires_zdr(monkeypatch):
    for var in ("NWZ_OPENROUTER_ROUTING", "NWZ_OPENROUTER_IGNORE", "NWZ_OPENROUTER_ZDR"):
        monkeypatch.delenv(var, raising=False)
    provider = llm._routing_extra_body()["provider"]
    assert provider["zdr"] is True
    assert provider["data_collection"] == "deny"
    assert {"deepseek", "baidu", "alibaba"} <= set(provider["ignore"])


def test_provider_routing_disabled_by_env(monkeypatch):
    monkeypatch.setenv("NWZ_OPENROUTER_ROUTING", "off")
    assert llm._routing_extra_body() == {}
