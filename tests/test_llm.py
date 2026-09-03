"""Offline tests for kern/llm.py: singleton client and _is_transient predicate."""
from __future__ import annotations

import pytest

from kern import llm


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

    # Eine Antwort MIT choices — chat_complete prüft das seit dem Fund vom
    # 03.09.2026 (Provider-Fehler kommen bei OpenRouter als 200er ohne choices).
    antwort = type("R", (), {"choices": [object()], "usage": None})()

    class _FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            return antwort

    class _FakeClient:
        chat = type("", (), {"completions": _FakeCompletions()})()

    monkeypatch.setenv("NWZ_OPENROUTER_ROUTING", "off")  # test pure delegation, no routing block
    monkeypatch.setattr(llm, "get_client", lambda: _FakeClient())
    result = llm.chat_complete(model="openai/gpt-4o-mini", messages=[])
    assert result is antwort
    # usage.include ist gesetzter Standard: OpenRouter liefert damit die echten
    # Kosten des Aufrufs zurück (usage.cost) — Basis für Admin-Statistik und Eval.
    assert calls == [{"model": "openai/gpt-4o-mini", "messages": [],
                      "extra_body": {"usage": {"include": True}}}]


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


# --------------------------------------------------------------------------- #
# Antwort ohne choices (OpenRouter meldet Provider-Fehler mit HTTP 200)
# --------------------------------------------------------------------------- #

class _AntwortOhneChoices:
    """Was das SDK aus `{"error": {…}}` mit Status 200 baut: choices is None."""

    def __init__(self, fehler=None):
        self.choices = None
        if fehler is not None:
            self.error = fehler


def test_leere_antwort_wirft_mit_providertext():
    """Der Grund muss im Fehler stehen — sonst sucht man ihn wie am 03.09.2026
    als `TypeError: 'NoneType' object is not subscriptable` an der Aufrufstelle."""
    resp = _AntwortOhneChoices({"code": 502, "message": "Provider returned error",
                                "metadata": {"provider_name": "Azure"}})
    with pytest.raises(llm.EmptyResponseError) as exc:
        llm._pruefe_choices(resp, "openai/gpt-5.6-luna")
    text = str(exc.value)
    assert "openai/gpt-5.6-luna" in text and "502" in text
    assert "Provider returned error" in text and "Azure" in text


def test_leere_antwort_auch_ohne_fehlerfeld():
    with pytest.raises(llm.EmptyResponseError):
        llm._pruefe_choices(_AntwortOhneChoices(), "openai/gpt-4o-mini")


def test_gefuellte_antwort_geht_durch():
    resp = type("R", (), {"choices": [object()]})()
    llm._pruefe_choices(resp, "openai/gpt-4o-mini")  # wirft nicht


def test_is_transient_leere_antwort():
    """Ein 200er ohne choices ist fast immer ein überlasteter Endpunkt — die
    vier Anläufe von _create sollen greifen, statt den Cron-Lauf zu reißen."""
    assert llm._is_transient(llm.EmptyResponseError("leer"))


def test_create_prueft_die_antwort(monkeypatch):
    """Die Prüfung sitzt IN _create, damit sie unter dem Retry liegt."""
    class _FakeCompletions:
        def create(self, **kwargs):
            return _AntwortOhneChoices({"message": "upstream timeout"})

    class _FakeClient:
        chat = type("", (), {"completions": _FakeCompletions()})()

    monkeypatch.setattr(llm, "get_client", lambda: _FakeClient())
    with pytest.raises(llm.EmptyResponseError):
        # __wrapped__ = ein Anlauf ohne die Wartezeiten von tenacity.
        llm._create.__wrapped__(model="openai/gpt-4o-mini", messages=[])
