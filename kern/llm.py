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
    BadRequestError,
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

# Die GPT-5.6-Familie sind ebenfalls Reasoning-Modelle: Auch hier zählen die
# Denk-Tokens gegen max_tokens. Gemessen an den Tragweite-Batches (27.08.26)
# waren es nur 180–430 Tokens, aber der Wert ist nicht garantiert — derselbe
# großzügige Floor wie bei DeepSeek kostet nichts und verhindert die stille
# finish_reason='length'-Leere.
GPT56_MIN_MAX_TOKENS = int(os.environ.get("NWZ_GPT56_MIN_MAX_TOKENS", "16000"))

MODEL_PARAMS: dict[str, dict[str, Any]] = {
    "openai/gpt-4o": {},
    "openai/gpt-4o-mini": {},
    "deepseek/deepseek-v4-pro": {"min_max_tokens": DEEPSEEK_MIN_MAX_TOKENS},
    "deepseek/deepseek-v4-flash": {"min_max_tokens": DEEPSEEK_MIN_MAX_TOKENS},
    **{m: {"min_max_tokens": GPT56_MIN_MAX_TOKENS} for m in (
        "openai/gpt-5.6-luna", "openai/gpt-5.6-luna-pro",
        "openai/gpt-5.6-sol", "openai/gpt-5.6-sol-pro",
        "openai/gpt-5.6-terra", "openai/gpt-5.6-terra-pro",
    )},
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


# OpenRouter provider routing (DSGVO). DeepSeek is an open-weights model served by many
# providers; by default OpenRouter may pick the cheapest — DeepSeek's own China API. The
# "Frag den Rat" user question is the sensitive payload, so we never route to China-based
# providers and prefer endpoints that neither retain nor train on prompts (zdr +
# data_collection=deny). The same open weights then run at a Western provider (e.g.
# GMICloud/DeepInfra) — still cheap, no China transfer. Tunable without a deploy:
# NWZ_OPENROUTER_IGNORE (comma-separated slugs), NWZ_OPENROUTER_ZDR=0 to drop the ZDR
# requirement, NWZ_OPENROUTER_ROUTING=off to disable the block entirely (emergency valve
# if the routing ever empties the endpoint pool).
_IGNORE_CN_DEFAULT = "deepseek,baidu,streamlake,siliconflow,alibaba"


def _routing_extra_body() -> dict[str, Any]:
    if os.environ.get("NWZ_OPENROUTER_ROUTING", "on").strip().lower() == "off":
        return {}
    provider: dict[str, Any] = {"data_collection": "deny"}
    ignore = [s.strip() for s in os.environ.get("NWZ_OPENROUTER_IGNORE", _IGNORE_CN_DEFAULT).split(",") if s.strip()]
    if ignore:
        provider["ignore"] = ignore
    if os.environ.get("NWZ_OPENROUTER_ZDR", "1").strip().lower() not in ("0", "false", "off", "no"):
        provider["zdr"] = True
    return {"provider": provider}


def _with_routing(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Merge the OpenRouter provider-routing block into the request's extra_body
    (a caller-supplied 'provider' wins, so call sites can still override)."""
    rb = _routing_extra_body()
    if not rb:
        return kwargs
    extra_body = {**rb, **(kwargs.get("extra_body") or {})}
    return {**kwargs, "extra_body": extra_body}


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


def is_content_filter(exc: BaseException) -> bool:
    """True, wenn der Provider die Anfrage wegen seiner Content-Policy abgelehnt
    hat (HTTP 400, code ``content_filter`` — z. B. Azures Jailbreak-Erkennung).

    Solche Fehler hängen am *Inhalt* der Anfrage, nicht am System: Ein einzelner
    vergifteter Nutzertext (etwa ein als Prompt-Injection getarnter Themenname)
    löst sie aus. Der Aufrufer sollte dann diesen einen Datensatz überspringen,
    nicht den ganzen Lauf abbrechen. Wir prüfen den Text der Fehlermeldung, weil
    OpenRouter den Provider-Code in die verschachtelte ``metadata.raw`` packt,
    die das SDK nicht strukturiert ausliest."""
    if not isinstance(exc, BadRequestError):
        return False
    # message trägt beim OpenAI-SDK meist den vollen Fehlerkörper, der Provider-
    # Code kann aber auch nur in body/metadata.raw stecken — beides absuchen.
    blob = f"{getattr(exc, 'message', '')} {getattr(exc, 'body', '')} {exc}".lower()
    return "content_filter" in blob or "content management policy" in blob or "responsibleai" in blob


class EmptyResponseError(RuntimeError):
    """OpenRouter hat mit HTTP 200 geantwortet, aber ohne ``choices``.

    Der Fehler des Upstream-Providers (Timeout, 5xx, überlastete Endpunkte)
    kommt bei OpenRouter nicht immer als HTTP-Status zurück, sondern als
    Körper ``{"error": {…}}`` mit Status 200. Das OpenAI-SDK baut daraus ein
    ChatCompletion, dessen ``choices`` schlicht ``None`` ist — jede Aufrufstelle
    lief damit in ein ``TypeError: 'NoneType' object is not subscriptable``,
    Hunderte Zeilen vom eigentlichen Grund entfernt (so am 03.09.2026 in
    ``check_council``). Hier fällt der Fall EINMAL auf, mit dem Providertext
    im Klartext, und gilt als vorübergehend — die vier Anläufe von ``_create``
    holen den nächsten, gesunden Endpunkt.
    """


def _antwort_fehlertext(resp: Any) -> str:
    """Den Fehler aus einer ``choices``-losen Antwort lesbar machen."""
    fehler = getattr(resp, "error", None)
    if fehler is None:
        fehler = (getattr(resp, "model_extra", None) or {}).get("error")
    if isinstance(fehler, dict):
        teile = [str(fehler.get(k)) for k in ("code", "message") if fehler.get(k) is not None]
        # Der Providername steckt eine Ebene tiefer und sagt beim Nachschauen
        # im OpenRouter-Log am meisten.
        anbieter = (fehler.get("metadata") or {}).get("provider_name")
        if anbieter:
            teile.append(f"provider={anbieter}")
        if teile:
            return " ".join(teile)
    if fehler:
        return str(fehler)
    return "keine Angabe des Providers"


def _pruefe_choices(resp: Any, model: str | None) -> None:
    """Raise EmptyResponseError, wenn die Antwort keine ``choices`` trägt."""
    if getattr(resp, "choices", None):
        return
    raise EmptyResponseError(
        f"{model or 'unbekanntes Modell'}: Antwort ohne choices — {_antwort_fehlertext(resp)}")


def _is_transient(exc: BaseException) -> bool:
    """True for errors worth retrying: rate-limit, server errors, network, a
    malformed/truncated response body (provider returned non-JSON — seen
    intermittently with reasoning models on large requests), or a 200er ohne
    ``choices`` (Provider-Fehler im Körper statt im Status)."""
    if isinstance(exc, EmptyResponseError):
        return True
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
def _create(**kwargs: Any):
    merged = _with_model_params(_with_routing(kwargs))
    # OpenRouter soll die ECHTEN Kosten des Aufrufs mitliefern (usage.cost, in
    # USD, inkl. Provider-Routing) — Modellpreise von Hand pflegen entfällt
    # damit dort, wo der Wert ankommt (Admin-Statistik, Eval-Kostenzeile).
    merged.setdefault("extra_body", {}).setdefault("usage", {"include": True})
    resp = get_client().chat.completions.create(**merged)
    # Beim Strom ist die erste Antwort ein Iterator, keine fertige Completion —
    # dort prüft chat_stream ohnehin jeden Chunk auf `choices`.
    if not merged.get("stream"):
        _pruefe_choices(resp, merged.get("model"))
    return resp


# Kosten-Zähler je Prozess: die Eval-Suite bildet daraus Deltas je Frage.
# (calls_ohne zählt Antworten, deren Provider keinen usage.cost lieferte —
# dann ist die Summe eine Untergrenze und der Bericht sagt das dazu.)
_session_cost = {"usd": 0.0, "calls_mit": 0, "calls_ohne": 0}


def session_cost() -> dict:
    """Aufsummierte echte LLM-Kosten dieses Prozesses (Kopie)."""
    return dict(_session_cost)


def _record_usage(feature: str | None, model: str | None, usage_obj: Any) -> None:
    """Best-effort: log this call's token usage + echte Kosten under ``feature``
    (for the admin LLM page). Never raises — usage tracking must not affect the
    LLM call itself."""
    if usage_obj is None:
        return
    cost = None
    try:
        raw = getattr(usage_obj, "cost", None)  # OpenRouter-Extra-Feld
        cost = float(raw) if raw is not None else None
    except (TypeError, ValueError):
        cost = None
    if cost is not None:
        _session_cost["usd"] += cost
        _session_cost["calls_mit"] += 1
    else:
        _session_cost["calls_ohne"] += 1
    if not feature:
        return
    try:
        from kern import usage
        usage.record(feature, model,
                     getattr(usage_obj, "prompt_tokens", 0) or 0,
                     getattr(usage_obj, "completion_tokens", 0) or 0,
                     cost_usd=cost)
    except Exception:  # noqa: BLE001
        pass


def chat_complete(**kwargs: Any):
    """Call chat.completions.create() with per-model defaults + retry on errors.

    Stored MODEL_PARAMS for the requested model are merged in first (so e.g. the
    deepseek reasoning cap travels with the model), then the call is retried up to
    4 times with exponential back-off (2 s → 4 s → 8 s → 60 s cap) for 429
    rate-limit, 5xx server errors, and network failures. Non-transient client
    errors (4xx other than 429) propagate immediately without retry.

    Pass ``_feature="…"`` to record this call's token usage per feature for the admin
    LLM page (stripped before the API call; best-effort).
    """
    feature = kwargs.pop("_feature", None)
    resp = _create(**kwargs)
    _record_usage(feature, kwargs.get("model"), getattr(resp, "usage", None))
    return resp


def chat_stream(**kwargs: Any):
    """Stream content deltas as they are generated — used for the live "Frag den Rat"
    answer. Same per-model params and connect-time retry as chat_complete. Pass
    ``_feature="…"`` to record token usage (requests the usage chunk; best-effort).
    Yields non-empty text chunks."""
    feature = kwargs.pop("_feature", None)
    if feature:
        kwargs.setdefault("stream_options", {"include_usage": True})
    for chunk in _create(stream=True, **kwargs):
        if getattr(chunk, "usage", None):
            _record_usage(feature, kwargs.get("model"), chunk.usage)
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
