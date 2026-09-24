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

    monkeypatch.setenv("NWZ_OPENROUTER_ROUTING", "off")
    monkeypatch.setattr(llm, "get_client", lambda: _FakeClient())
    with pytest.raises(llm.EmptyResponseError):
        # __wrapped__ = ein Anlauf ohne die Wartezeiten von tenacity.
        llm._create.__wrapped__(model="openai/gpt-4o-mini", messages=[])


def test_chat_complete_erlaubt_expliziten_leerantwort_fallback(monkeypatch):
    """Der Opt-out ist nur für Aufrufer mit eigener Fachlogik; insbesondere
    darf sein privates Keyword nie an OpenRouter weitergereicht werden."""
    antwort = _AntwortOhneChoices({"message": "upstream timeout"})
    calls = []

    class _FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            return antwort

    class _FakeClient:
        chat = type("", (), {"completions": _FakeCompletions()})()

    monkeypatch.setenv("NWZ_OPENROUTER_ROUTING", "off")
    monkeypatch.setattr(llm, "get_client", lambda: _FakeClient())
    result = llm.chat_complete(
        _allow_empty_response=True,
        model="openai/gpt-4o-mini",
        messages=[],
    )
    assert result is antwort
    assert calls == [{
        "model": "openai/gpt-4o-mini",
        "messages": [],
        "extra_body": {"usage": {"include": True}},
    }]


# --------------------------------------------------------------------------- #
# Geduld und Ersatzmodelle (Batch-Jobs)
# --------------------------------------------------------------------------- #
class _Antwort:
    def __init__(self, text="ok"):
        self.choices = [type("C", (), {"message": type("M", (), {"content": text})()})()]
        self.usage = type("U", (), {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.0})()


def _stub_create(monkeypatch, plan):
    """``plan``: Liste von Ergebnissen je Aufruf — Exception-Instanz = werfen.
    Zeichnet die Modelle der Aufrufe auf und schaltet das Schlafen ab."""
    aufrufe, pausen = [], []
    def fake_create(**kwargs):
        aufrufe.append(kwargs["model"])
        ergebnis = plan.pop(0)
        if isinstance(ergebnis, BaseException):
            raise ergebnis
        return ergebnis
    monkeypatch.setattr(llm, "_create", fake_create)
    monkeypatch.setattr(llm.time, "sleep", lambda s: pausen.append(s))
    return aufrufe, pausen


def test_ohne_geduld_bleibt_alles_wie_es_war(monkeypatch):
    aufrufe, pausen = _stub_create(monkeypatch, [llm.EmptyResponseError("429 rate-limited")])
    with pytest.raises(llm.EmptyResponseError):
        llm.chat_complete(model="openai/gpt-5.6-luna", messages=[])
    assert aufrufe == ["openai/gpt-5.6-luna"] and pausen == []


def test_geduld_wartet_minuten_und_versucht_es_wieder(monkeypatch):
    aufrufe, pausen = _stub_create(monkeypatch, [
        llm.EmptyResponseError("429"), llm.EmptyResponseError("429"), _Antwort()])
    resp = llm.chat_complete(model="openai/gpt-5.6-luna", messages=[], _geduld=True)
    assert resp.choices[0].message.content == "ok"
    assert aufrufe == ["openai/gpt-5.6-luna"] * 3
    assert pausen == [30, 90]


def test_ersatzmodell_uebernimmt_nach_der_geduld(monkeypatch):
    aufgezeichnet = []
    monkeypatch.setattr(llm, "_record_usage", lambda f, m, u: aufgezeichnet.append((f, m)))
    plan = [llm.EmptyResponseError("429")] * 4 + [_Antwort("vom Ersatz")]
    aufrufe, pausen = _stub_create(monkeypatch, plan)
    resp = llm.chat_complete(model="openai/gpt-5.6-luna", messages=[], _geduld=True,
                             _ersatz=["deepseek/deepseek-v4-pro"], _feature="probe")
    assert resp.choices[0].message.content == "vom Ersatz"
    assert aufrufe == ["openai/gpt-5.6-luna"] * 4 + ["deepseek/deepseek-v4-pro"]
    assert pausen == [30, 90, 180]
    # Die Kosten stehen beim Modell, das WIRKLICH geantwortet hat.
    assert aufgezeichnet == [("probe", "deepseek/deepseek-v4-pro")]


def test_kein_ersatz_bei_dauerhaftem_fehler(monkeypatch):
    """Ein 400er ist kein Fall fürs Ersatzmodell — der Fehler liegt in der Anfrage."""
    aufrufe, _ = _stub_create(monkeypatch, [ValueError("kaputte Anfrage")])
    with pytest.raises(ValueError):
        llm.chat_complete(model="openai/gpt-5.6-luna", messages=[], _ersatz=["deepseek/deepseek-v4-pro"])
    assert aufrufe == ["openai/gpt-5.6-luna"]


def test_ersatz_fuer_kennt_luna_und_sonst_nichts():
    assert llm.ersatz_fuer("openai/gpt-5.6-luna")
    assert llm.ersatz_fuer("google/gemini-2.5-flash") == []
    assert llm.ersatz_fuer(None) == []


# --------------------------------------------------------------------------- #
# ZDR je Feature (Tims Entscheidung 22.09.2026)
# --------------------------------------------------------------------------- #

#: Features, die Text verarbeiten, den eine Nutzerin selbst geschrieben hat:
#: Fragen, Themen, Lottis Kontext. Sie dürfen NIE ohne ZDR laufen.
NUTZER_PFADE = ("qa_answer", "qa_simple", "qa_analysis", "qa_query_expansion",
                "deep_report", "deep_decomposition", "party_opinions",
                "assistant_explain", "topic_auto_description", "vagueness_check")


def test_nutzer_pfade_behalten_zdr(monkeypatch):
    monkeypatch.delenv("NWZ_OPENROUTER_ZDR", raising=False)
    for f in NUTZER_PFADE:
        assert llm.nutzereingabe(f), f
        assert f not in llm.OHNE_NUTZEREINGABE
        # Die EINE benannte Ausnahme: Tims ZDR-Verzicht vom 23.09.2026.
        assert llm.zdr_pflicht(f) is (f not in llm.ZDR_VERZICHT), f
    assert llm.zdr_pflicht(None), "ohne _feature bleibt es bei ZDR (der Watcher)"
    assert llm.zdr_pflicht("ein_neues_feature"), "unbekannt heißt ZDR"


def test_oeffentliche_daten_ohne_zdr_aber_ohne_training_und_china(monkeypatch):
    for var in ("NWZ_OPENROUTER_ROUTING", "NWZ_OPENROUTER_IGNORE", "NWZ_OPENROUTER_ZDR"):
        monkeypatch.delenv(var, raising=False)
    assert not llm.zdr_pflicht("impact_rating")
    assert not llm.zdr_pflicht("cities_fit")
    assert not llm.zdr_pflicht("eval_cities_fit"), "die Eval misst wie der Cron"
    provider = llm._routing_extra_body(zdr=False)["provider"]
    assert "zdr" not in provider
    assert provider["data_collection"] == "deny"
    assert {"deepseek", "baidu", "alibaba"} <= set(provider["ignore"])


def test_freigabeliste_nennt_nur_echte_features():
    """Ein Name in der Liste, den kein Aufruf trägt, ist ein Tippfehler oder
    ein Rest — beides soll auffallen, statt still mitzulaufen."""
    import re
    from pathlib import Path
    wurzel = Path(__file__).resolve().parent.parent
    code = "\n".join(p.read_text() for d in ("council", "scripts", "kern")
                     for p in (wurzel / d).rglob("*.py"))
    benutzt = set(re.findall(r'_feature="([a-z_]+)"', code))
    assert llm.OHNE_NUTZEREINGABE <= benutzt, llm.OHNE_NUTZEREINGABE - benutzt


def test_chat_complete_reicht_die_zdr_entscheidung_durch(monkeypatch):
    gesehen = []

    def fake_create(**kw):
        gesehen.append(kw.get("_zdr"))
        raise RuntimeError("stop")

    monkeypatch.setattr(llm, "_create", fake_create)
    # qa_answer steht seit 23.09.2026 in ZDR_VERZICHT; qa_analysis trägt
    # Nutzereingabe und hat keinen Verzicht.
    for feature, erwartet in (("impact_rating", False), ("qa_answer", False),
                              ("qa_analysis", True), (None, True)):
        with pytest.raises(RuntimeError):
            llm.chat_complete(model="x", messages=[], _feature=feature)
        assert gesehen[-1] is erwartet


# --------------------------------------------------------------------------- #
# Flex-Tarif (Messung 22.09.2026: halber Preis, gleiche Qualität, ohne ZDR)
# --------------------------------------------------------------------------- #
def _stub_create_kwargs(monkeypatch, plan):
    """Wie ``_stub_create``, zeichnet aber die vollständigen kwargs auf."""
    aufrufe = []
    def fake_create(**kwargs):
        aufrufe.append(kwargs)
        ergebnis = plan.pop(0)
        if isinstance(ergebnis, BaseException):
            raise ergebnis
        return ergebnis
    monkeypatch.setattr(llm, "_create", fake_create)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    return aufrufe


def test_flex_fuer_freigegebenes_feature(monkeypatch):
    """impact_rating steht in OHNE_NUTZEREINGABE → Flex, über den ZDR-Pfad
    von _create (``_zdr=False``), kein zweiter Routing-Weg."""
    aufrufe = _stub_create_kwargs(monkeypatch, [_Antwort()])
    llm.chat_complete(model="openai/gpt-6-luna", messages=[], _feature="impact_rating",
                      _tarif="flex", extra_body={"reasoning": {"effort": "low"}})
    (kw,) = aufrufe
    assert kw["_zdr"] is False
    assert kw["extra_body"] == {"reasoning": {"effort": "low"}, "service_tier": "flex"}
    assert "_tarif" not in kw


def test_flex_anfrage_traegt_routing_ohne_zdr(monkeypatch):
    """Durch das echte _create: Mit zdr=True ignoriert OpenRouter service_tier
    still (gemessen) — also fällt nur zdr weg, die übrigen Schranken bleiben."""
    for var in ("NWZ_OPENROUTER_ROUTING", "NWZ_OPENROUTER_IGNORE", "NWZ_OPENROUTER_ZDR"):
        monkeypatch.delenv(var, raising=False)
    gesendet = []

    class _FakeCompletions:
        def create(self, **kwargs):
            gesendet.append(kwargs)
            return _Antwort()

    class _FakeClient:
        chat = type("", (), {"completions": _FakeCompletions()})()

    monkeypatch.setattr(llm, "get_client", lambda: _FakeClient())
    monkeypatch.setattr(llm, "_record_usage", lambda f, m, u: None)
    llm.chat_complete(model="openai/gpt-6-luna", messages=[], _feature="impact_rating",
                      _tarif="flex")
    body = gesendet[0]["extra_body"]
    assert body["service_tier"] == "flex"
    assert "zdr" not in body["provider"]
    assert body["provider"]["data_collection"] == "deny"
    assert {"deepseek", "baidu", "alibaba"} <= set(body["provider"]["ignore"])


def test_flex_fuer_zdr_pflichtiges_feature_ist_ein_fehler(monkeypatch):
    """Nicht still im normalen Tarif laufen — wer Flex schreibt, rechnet mit
    der Hälfte des Preises. Ein Nutzerpfad und ein Aufruf ohne _feature."""
    aufrufe = _stub_create_kwargs(monkeypatch, [_Antwort()])
    for feature in ("qa_answer", None):
        with pytest.raises(llm.FlexNichtErlaubt):
            llm.chat_complete(model="openai/gpt-6-luna", messages=[], _feature=feature,
                              _tarif="flex")
    with pytest.raises(llm.FlexNichtErlaubt):
        llm.chat_complete(model="openai/gpt-6-luna", messages=[], _tarif="flex")
    assert aufrufe == []


def test_flex_abweisung_faellt_auf_den_normalen_tarif_zurueck(monkeypatch):
    aufgezeichnet = []
    monkeypatch.setattr(llm, "_record_usage", lambda f, m, u: aufgezeichnet.append((f, m)))
    aufrufe = _stub_create_kwargs(monkeypatch, [
        llm.EmptyResponseError("429 Resource Unavailable"), _Antwort("normal")])
    resp = llm.chat_complete(model="openai/gpt-6-luna", messages=[], _feature="impact_rating",
                             _tarif="flex")
    assert resp.choices[0].message.content == "normal"
    assert [(a.get("extra_body") or {}).get("service_tier") for a in aufrufe] == ["flex", None]
    # Der Rückfall behält die ZDR-Entscheidung des Features.
    assert [a["_zdr"] for a in aufrufe] == [False, False]
    assert aufgezeichnet == [("impact_rating", "openai/gpt-6-luna")]


def test_flex_abweisung_mit_geduld_faellt_geduldig_auf_normal_zurueck(monkeypatch):
    """`_geduld=True` zusammen mit `_tarif="flex"`: Die Flex-Abweisung fällt
    sofort auf den normalen Tarif zurück (kein Warten nötig, s.
    ``_create_flex``); scheitert AUCH der normale Tarif vorübergehend, wartet
    dieser Zweig wie jeder Batch-Job die ``GEDULD_PAUSEN`` ab, bevor er
    aufgibt. Anlass P5 (docs/plan-modellwechsel.md): Alle fünf umgestellten
    Cron-Features rufen mit `_geduld=True, _tarif="flex"` zusammen."""
    aufgezeichnet = []
    monkeypatch.setattr(llm, "_record_usage", lambda f, m, u: aufgezeichnet.append((f, m)))
    aufrufe = _stub_create_kwargs(monkeypatch, [
        llm.EmptyResponseError("429 Resource Unavailable"),  # Flex abgewiesen
        llm.EmptyResponseError("429 upstream"),               # normal, 1. Versuch
        _Antwort("normal nach Geduld"),                       # normal, nach einer Pause
    ])
    resp = llm.chat_complete(model="openai/gpt-6-luna", messages=[], _feature="impact_rating",
                             _tarif="flex", _geduld=True)
    assert resp.choices[0].message.content == "normal nach Geduld"
    assert [(a.get("extra_body") or {}).get("service_tier") for a in aufrufe] == ["flex", None, None]
    assert aufgezeichnet == [("impact_rating", "openai/gpt-6-luna")]


def test_ersatzmodell_bei_flex_bleibt_im_flex_tarif(monkeypatch):
    """Antwortet das gewünschte Modell (flex UND normal) gar nicht, übernimmt
    das Ersatzmodell — und zwar wieder ERST im Flex-Tarif, mit demselben
    Rückfallverhalten. Die fünf P5-Features rufen mit
    `_ersatz=llm.ersatz_fuer(MODEL)`; der Ersatz darf den Kostenvorteil von
    Flex nicht verlieren."""
    aufgezeichnet = []
    monkeypatch.setattr(llm, "_record_usage", lambda f, m, u: aufgezeichnet.append((f, m)))
    aufrufe = _stub_create_kwargs(monkeypatch, [
        llm.EmptyResponseError("429"),  # gpt-6-luna, flex
        llm.EmptyResponseError("429"),  # gpt-6-luna, normal
        _Antwort("vom Ersatz, flex"),   # gpt-5.6-luna (Ersatz), flex — sofort ok
    ])
    resp = llm.chat_complete(model="openai/gpt-6-luna", messages=[], _feature="impact_rating",
                             _tarif="flex", _ersatz=["openai/gpt-5.6-luna"])
    assert resp.choices[0].message.content == "vom Ersatz, flex"
    assert [a.get("model") for a in aufrufe] == ["openai/gpt-6-luna", "openai/gpt-6-luna",
                                                  "openai/gpt-5.6-luna"]
    assert [(a.get("extra_body") or {}).get("service_tier") for a in aufrufe] == ["flex", None, "flex"]
    assert aufgezeichnet == [("impact_rating", "openai/gpt-5.6-luna")]


def test_flex_rueckfall_nicht_bei_inhaltsfilter(monkeypatch):
    import httpx
    from openai import BadRequestError
    filter_fehler = BadRequestError(
        "content_filter", response=httpx.Response(400, request=_make_request()), body={})
    aufrufe = _stub_create_kwargs(monkeypatch, [filter_fehler, _Antwort()])
    with pytest.raises(BadRequestError):
        llm.chat_complete(model="openai/gpt-6-luna", messages=[], _feature="impact_rating",
                          _tarif="flex")
    assert len(aufrufe) == 1


def test_tarif_aus_der_umgebung_ist_nur_die_vorgabe(monkeypatch):
    """Der Messschalter des Prüfstands (``RATSLOTSE_LLM_TARIF``): wirkt ohne
    ``_tarif``, weicht einem ausdrücklichen, und bleibt bei ZDR-Pflicht ein
    Fehler — wie der Parameter, kein stiller Normaltarif."""
    monkeypatch.setenv(llm.TARIF_ENV, "flex")
    aufrufe = _stub_create_kwargs(monkeypatch, [_Antwort(), _Antwort()])
    llm.chat_complete(model="openai/gpt-6-luna", messages=[], _feature="impact_rating")
    llm.chat_complete(model="openai/gpt-6-luna", messages=[], _feature="impact_rating",
                      _tarif="normal")
    assert [(a.get("extra_body") or {}).get("service_tier") for a in aufrufe] == ["flex", None]
    for feature in ("qa_answer", None):
        with pytest.raises(llm.FlexNichtErlaubt):
            llm.chat_complete(model="openai/gpt-6-luna", messages=[], _feature=feature)
    assert len(aufrufe) == 2


def test_unbekannter_tarif_wird_abgewiesen(monkeypatch):
    _stub_create_kwargs(monkeypatch, [_Antwort()])
    with pytest.raises(ValueError, match="batch"):
        llm.chat_complete(model="openai/gpt-6-luna", messages=[], _tarif="batch")


def test_ohne_tarif_bleibt_der_aufruf_unveraendert(monkeypatch):
    aufrufe = _stub_create_kwargs(monkeypatch, [_Antwort()])
    llm.chat_complete(model="openai/gpt-6-luna", messages=[], _feature="impact_rating")
    assert "service_tier" not in (aufrufe[0].get("extra_body") or {})


def test_kein_aufruf_leert_das_routing():
    """Ein aufrufereigener ``provider``-Block ersetzt das Routing GANZ.

    Die Städte-Annotatoren schickten bis 23.09.2026 ``provider: {}``, um ZDR
    loszuwerden — und warfen damit den China-Ausschluss und das
    Trainingsverbot gleich mit weg. ZDR regelt jetzt ``zdr_pflicht``; wer
    einen eigenen Block braucht, baut ihn aus ``_routing_extra_body``.
    """
    import re
    from pathlib import Path
    wurzel = Path(__file__).resolve().parent.parent
    treffer = [f"{p.relative_to(wurzel)}"
               for d in ("council", "scripts", "kern", "eval", "web/backend/app")
               for p in (wurzel / d).rglob("*.py")
               if re.search(r'["\']provider["\']\s*:\s*\{\s*\}', p.read_text())]
    assert not treffer, treffer


# --------------------------------------------------------------------------- #
# Prompt-Mitschnitt (Messschalter der Fakten-Eval)
# --------------------------------------------------------------------------- #
def _zeilen(ordner, feature):
    import json
    pfad = ordner / f"{feature}.jsonl"
    return [json.loads(z) for z in pfad.read_text().splitlines()] if pfad.exists() else []


def _strom_teil(text, model=None):
    delta = type("D", (), {"content": text})()
    return type("K", (), {"choices": [type("C", (), {"delta": delta})()], "usage": None,
                          "model": model})()


def test_mitschnitt_aus_schreibt_nichts(monkeypatch, tmp_path):
    monkeypatch.delenv(llm.MITSCHNITT_ENV, raising=False)
    monkeypatch.chdir(tmp_path)
    _stub_create(monkeypatch, [_Antwort("hallo")])
    llm.chat_complete(model="m", messages=[{"role": "user", "content": "x"}], _feature="qa_answer")
    assert list(tmp_path.iterdir()) == []


def test_mitschnitt_haelt_prompt_modell_und_antwort_fest(monkeypatch, tmp_path):
    """Die Eval muss den ECHTEN Prompt sehen — Nachrichten, Modell, Antwort, je Feature."""
    monkeypatch.setenv(llm.MITSCHNITT_ENV, str(tmp_path))
    _stub_create(monkeypatch, [_Antwort("Die Antwort")])
    msgs = [{"role": "system", "content": "Kontext 336.994.000 €"},
            {"role": "user", "content": "Frage"}]
    llm.chat_complete(model="openai/gpt-6-luna", messages=msgs, _feature="assistant_explain")
    (z,) = _zeilen(tmp_path, "assistant_explain")
    assert z["model"] == "openai/gpt-6-luna"
    assert z["messages"] == msgs
    assert z["answer"] == "Die Antwort"
    assert z["aborted"] is False


def test_mitschnitt_auch_beim_strom(monkeypatch, tmp_path):
    monkeypatch.setenv(llm.MITSCHNITT_ENV, str(tmp_path))
    monkeypatch.setattr(llm, "_create", lambda **kw: iter([
        _strom_teil("Rund ", "google/gemini-2.5-flash"), _strom_teil("337 Mio. €")]))
    teile = list(llm.chat_stream(model="google/gemini-2.5-flash",
                                 messages=[{"role": "user", "content": "q"}],
                                 _feature="qa_answer"))
    assert "".join(teile) == "Rund 337 Mio. €"
    (z,) = _zeilen(tmp_path, "qa_answer")
    assert z["answer"] == "Rund 337 Mio. €"
    assert z["response_model"] == "google/gemini-2.5-flash"


def test_mitschnitt_haelt_einen_abgerissenen_strom_fest(monkeypatch, tmp_path):
    """Reißt der Strom, erzeugt der Router neu — die Eval muss beide Aufrufe sehen."""
    monkeypatch.setenv(llm.MITSCHNITT_ENV, str(tmp_path))

    def strom(**kw):
        yield _strom_teil("Anfang")
        raise RuntimeError("Strom weg")

    monkeypatch.setattr(llm, "_create", strom)
    with pytest.raises(RuntimeError):
        list(llm.chat_stream(model="m", messages=[], _feature="qa_answer"))
    (z,) = _zeilen(tmp_path, "qa_answer")
    assert z["aborted"] is True and z["answer"] == "Anfang"


def test_mitschnitt_fehler_bricht_den_aufruf_nicht_ab(monkeypatch, tmp_path):
    datei = tmp_path / "keinordner"
    datei.write_text("")  # eine DATEI, wo ein Ordner sein müsste
    monkeypatch.setenv(llm.MITSCHNITT_ENV, str(datei))
    _stub_create(monkeypatch, [_Antwort("ok")])
    resp = llm.chat_complete(model="m", messages=[], _feature="qa_answer")
    assert resp.choices[0].message.content == "ok"


def test_mitschnitt_steht_in_keiner_env_vorlage():
    """Der Schalter schreibt Nutzerfragen im Klartext auf die Platte — nie im Betrieb."""
    from pathlib import Path
    wurzel = Path(__file__).resolve().parent.parent
    for vorlage in wurzel.glob(".env*"):
        if vorlage.is_file():
            assert llm.MITSCHNITT_ENV not in vorlage.read_text(errors="ignore"), vorlage


def test_zdr_verzicht_ist_genau_die_benannte_liste():
    """Tims Entscheidung 23.09.2026: Lotti und „Frag den Rat“ auf GPT-6 Luna,
    ohne ZDR. Genau die Features, die ``COUNCIL_ASSISTANT_MODEL`` und
    ``COUNCIL_QA_MODEL`` lesen — die Analyse vor der Suche, der Watcher und
    die Themenbeschreibung behalten ZDR."""
    assert llm.ZDR_VERZICHT == {"assistant_explain", "qa_answer", "qa_simple",
                                "deep_report", "party_opinions"}
    assert llm.ZDR_VERZICHT <= set(NUTZER_PFADE)
    for f in ("qa_analysis", "qa_query_expansion", "deep_decomposition",
              "topic_auto_description", "vagueness_check", "council_watcher", None):
        assert llm.zdr_pflicht(f), f


def test_zdr_verzicht_behaelt_trainingsverbot_und_china_liste(monkeypatch):
    """Ohne ZDR heißt nicht ohne Schranken: ``data_collection: deny`` und die
    China-Liste gehen auch für Lotti und die Antwort mit — durch das echte
    ``_create``, Strom UND Einmal-Aufruf."""
    for var in ("NWZ_OPENROUTER_ROUTING", "NWZ_OPENROUTER_IGNORE", "NWZ_OPENROUTER_ZDR"):
        monkeypatch.delenv(var, raising=False)
    gesendet = []

    class _FakeCompletions:
        def create(self, **kwargs):
            gesendet.append(kwargs)
            return iter(()) if kwargs.get("stream") else _Antwort()

    class _FakeClient:
        chat = type("", (), {"completions": _FakeCompletions()})()

    monkeypatch.setattr(llm, "get_client", lambda: _FakeClient())
    monkeypatch.setattr(llm, "_record_usage", lambda f, m, u: None)
    # Ein Modell ohne EU-Weg (EU_ZUERST) zeigt das Verzicht-Routing direkt —
    # dasselbe, das bei GPT-6 Luna als Rückfall dient (s. die EU-Tests unten).
    llm.chat_complete(model="deepseek/deepseek-v4-pro", messages=[], _feature="assistant_explain")
    list(llm.chat_stream(model="deepseek/deepseek-v4-pro", messages=[], _feature="qa_answer"))
    llm.chat_complete(model="google/gemini-3.1-flash-lite", messages=[], _feature="qa_analysis")
    verzicht, strom, analyse = (g["extra_body"]["provider"] for g in gesendet)
    for provider in (verzicht, strom):
        assert "zdr" not in provider
        assert provider["data_collection"] == "deny"
        assert {"deepseek", "baidu", "alibaba"} <= set(provider["ignore"])
    assert analyse["zdr"] is True


def test_zdr_verzicht_gibt_flex_nicht_frei(monkeypatch):
    aufrufe = _stub_create_kwargs(monkeypatch, [_Antwort()])
    for feature in sorted(llm.ZDR_VERZICHT):
        with pytest.raises(llm.FlexNichtErlaubt):
            llm.chat_complete(model="openai/gpt-6-luna", messages=[], _feature=feature,
                              _tarif="flex")
    assert aufrufe == []


def test_web_denkaufwand_nur_fuer_die_gemessenen_modelle(monkeypatch):
    monkeypatch.delenv(llm.WEB_DENKAUFWAND_ENV, raising=False)
    for (modell, feature), stufe in llm.WEB_DENKAUFWAND.items():
        assert llm.web_denk_extra(modell, feature) == {"extra_body": {"reasoning": {"effort": stufe}}}
    assert llm.web_denk_extra("openai/gpt-6-luna", "qa_answer") == {}
    assert llm.web_denk_extra("deepseek/deepseek-v4-flash", "qa_answer") == {
        "extra_body": {"reasoning": {"enabled": False}}}
    assert llm.web_denk_extra("google/gemini-3.1-flash-lite", "qa_answer") == {}
    # NICHT über MODEL_PARAMS: Dort gälte es auch für die Luna-Crons.
    assert "extra_body" not in llm.MODEL_PARAMS.get("openai/gpt-6-luna", {})


def test_messschalter_ueberschreibt_den_denkaufwand(monkeypatch):
    monkeypatch.setenv(llm.WEB_DENKAUFWAND_ENV, "vorgabe")
    assert llm.web_denk_extra("openai/gpt-6-luna", "qa_answer") == {}
    monkeypatch.setenv(llm.WEB_DENKAUFWAND_ENV, "high")
    assert llm.web_denk_extra("openai/gpt-6-luna", "assistant_explain") == {
        "extra_body": {"reasoning": {"effort": "high"}}}


def test_lotti_und_antwort_fragen_luna_mit_dem_vorgabe_aufwand(monkeypatch):
    """Entschieden an der Fakten-Eval (P4a): ``low`` ließ bei Lotti 13 statt 10
    und bei Frag den Rat 31 statt 27 Pflichtangaben aus oder verfälschte sie —
    „Akkuratheit schlägt Geschwindigkeit“. Kein ``reasoning`` im Aufruf."""
    monkeypatch.delenv(llm.WEB_DENKAUFWAND_ENV, raising=False)
    from council import assistant, qa
    _, extra = assistant.explain_messages(assistant.Screen(route="/haushalt"), "Was?", {},
                                          model="openai/gpt-6-luna")
    assert "reasoning" not in (extra.get("extra_body") or {})
    _, extra = qa._answer_messages("Was?", [], "topic", "openai/gpt-6-luna")
    assert "reasoning" not in (extra.get("extra_body") or {})


def test_recherche_bericht_nimmt_den_denkaufwand_je_feature(monkeypatch):
    """Bis 23.09.2026 trug der Deep-Bericht nur DeepSeeks Aus-Schalter — ein
    Eintrag in ``WEB_DENKAUFWAND`` für ``deep_report`` wäre wirkungslos
    geblieben, und die Messung hätte zweimal dasselbe verglichen."""
    from council import qa
    monkeypatch.delenv(llm.WEB_DENKAUFWAND_ENV, raising=False)
    gestellt: dict = {}

    def merken(**kwargs):
        gestellt.update(kwargs)
        return iter(())

    monkeypatch.setattr(llm, "chat_stream", merken)
    monkeypatch.setitem(llm.WEB_DENKAUFWAND, ("openai/gpt-6-luna", "deep_report"), "high")
    list(qa.deep_bericht_stream("Frage?", [], model="openai/gpt-6-luna"))
    assert gestellt["_feature"] == "deep_report"
    assert gestellt["extra_body"] == {"reasoning": {"effort": "high"}}
    # Der Messschalter der Fakten-Eval erreicht den Bericht ebenso.
    monkeypatch.setenv(llm.WEB_DENKAUFWAND_ENV, "vorgabe")
    gestellt.clear()
    list(qa.deep_bericht_stream("Frage?", [], model="openai/gpt-6-luna"))
    assert "extra_body" not in gestellt
    # DeepSeek bleibt ohne Denken, wie bisher.
    gestellt.clear()
    list(qa.deep_bericht_stream("Frage?", [], model="deepseek/deepseek-v4-pro"))
    assert gestellt["extra_body"] == {"reasoning": {"enabled": False}}


def test_gpt6_sol_hat_den_boden_der_denkenden_modelle():
    """Sonst bekäme der Bericht die 4.000 Tokens der Aufrufstelle, und das
    Denken zehrte sie still auf (finish_reason ``length``)."""
    assert llm._with_model_params({"model": "openai/gpt-6-sol", "max_tokens": 4000})[
        "max_tokens"] >= llm.GPT56_MIN_MAX_TOKENS


def test_mitschnitt_haelt_ende_und_denk_tokens_fest(monkeypatch, tmp_path):
    """Der Nachweis gegen einen still abgeschnittenen Bericht: ``length`` im
    Mitschnitt, dazu die Denk-Tokens, die das Budget verbraucht haben."""
    monkeypatch.setenv(llm.MITSCHNITT_ENV, str(tmp_path))
    details = type("D", (), {"reasoning_tokens": 900})()
    verbrauch = type("U", (), {"prompt_tokens": 10, "completion_tokens": 1000, "cost": 0.0,
                               "completion_tokens_details": details})()
    ende = type("K", (), {"choices": [type("C", (), {
        "delta": type("D", (), {"content": ""})(), "finish_reason": "length"})()],
        "usage": None, "model": "m"})()
    nutzung = type("K", (), {"choices": [], "usage": verbrauch, "model": "m"})()
    monkeypatch.setattr(llm, "_create", lambda **kw: iter([_strom_teil("Text"), ende, nutzung]))
    assert "".join(llm.chat_stream(model="m", messages=[], _feature="deep_report")) == "Text"
    (z,) = _zeilen(tmp_path, "deep_report")
    assert z["finish_reason"] == "length"
    assert z["usage"] == {"prompt_tokens": 10, "completion_tokens": 1000,
                          "reasoning_tokens": 900}


# --------------------------------------------------------------------------- #
# EU zuerst (Tims Entscheidung 23.09.2026): GPT-6 Luna für Lotti und
# „Frag den Rat“ erst über azure/eu mit ZDR, bei Ausfall ohne ZDR.
# --------------------------------------------------------------------------- #
@pytest.fixture
def _eu_umgebung(monkeypatch):
    for var in ("NWZ_OPENROUTER_ROUTING", "NWZ_OPENROUTER_IGNORE", "NWZ_OPENROUTER_ZDR",
                llm.EU_ANBIETER_ENV, llm.MITSCHNITT_ENV):
        monkeypatch.delenv(var, raising=False)
    aufgezeichnet = []
    monkeypatch.setattr(llm, "_record_usage", lambda f, m, u: aufgezeichnet.append((f, m)))
    return aufgezeichnet


def _routing(kw):
    """Den Provider-Block, den ``_create`` aus den kwargs bauen würde."""
    return llm._routing_extra_body(kw.get("_zdr", True), kw.get("_only"))["provider"]


def _fehler(code, text="fehler"):
    import httpx
    from openai import APIStatusError, NotFoundError, RateLimitError
    antwort = httpx.Response(code, request=_make_request())
    klasse = {404: NotFoundError, 429: RateLimitError}.get(code, APIStatusError)
    return klasse(text, response=antwort, body={})


def test_eu_erster_weg_ok_nur_azure(_eu_umgebung, monkeypatch):
    aufrufe = _stub_create_kwargs(monkeypatch, [_Antwort("aus der EU")])
    resp = llm.chat_complete(model="openai/gpt-6-luna", messages=[], _feature="assistant_explain")
    assert resp.choices[0].message.content == "aus der EU"
    (kw,) = aufrufe
    provider = _routing(kw)
    assert provider["only"] == ["azure/eu"] and provider["zdr"] is True
    assert provider["data_collection"] == "deny"
    assert {"deepseek", "baidu", "alibaba"} <= set(provider["ignore"])
    assert _eu_umgebung == [("assistant_explain", "openai/gpt-6-luna")]


@pytest.mark.parametrize("fehler", [
    _fehler(429, "temporarily rate-limited upstream"),
    _fehler(503),
    _fehler(404, "No allowed providers are available for the selected model"),
    llm.EmptyResponseError("200 ohne choices"),
])
def test_eu_ausfall_faellt_einmal_auf_das_verzicht_routing(_eu_umgebung, monkeypatch, fehler):
    aufrufe = _stub_create_kwargs(monkeypatch, [fehler, _Antwort("aus den USA")])
    resp = llm.chat_complete(model="openai/gpt-6-luna", messages=[], _feature="qa_answer")
    assert resp.choices[0].message.content == "aus den USA"
    eu, verzicht = aufrufe
    assert _routing(eu)["only"] == ["azure/eu"] and _routing(eu)["zdr"] is True
    zweiter = _routing(verzicht)
    assert "only" not in zweiter and "zdr" not in zweiter
    assert zweiter["data_collection"] == "deny" and "deepseek" in zweiter["ignore"]
    # Gezählt als eigenes Modell — so steht es in llm_usage und im Admin-Panel.
    assert _eu_umgebung == [("qa_answer", "openai/gpt-6-luna" + llm.RUECKFALL_MARKE)]


def test_eu_leerantwort_faellt_auch_mit_eigener_leerregel_zurueck(_eu_umgebung, monkeypatch):
    """Die Partei-Meinungen behandeln Leerantworten selbst — aus der EU heißt
    leer trotzdem „Anbieter gestört“, der zweite Weg behält die Regel."""
    aufrufe = _stub_create_kwargs(monkeypatch, [_AntwortOhneChoices(), _Antwort("[]")])
    resp = llm.chat_complete(model="openai/gpt-6-luna", messages=[], _feature="party_opinions",
                             _allow_empty_response=True)
    assert resp.choices[0].message.content == "[]"
    assert [a.get("_only") for a in aufrufe] == [("azure/eu",), None]
    assert all(a["_allow_empty_response"] for a in aufrufe)


def test_eu_inhaltsfilter_faellt_nicht_zurueck(_eu_umgebung, monkeypatch):
    """Ein Filter-Treffer hängt am Text — ein Rückfall schickte genau diesen
    Text in die USA."""
    import httpx
    from openai import BadRequestError
    filter_fehler = BadRequestError(
        "content_filter: ResponsibleAIPolicyViolation",
        response=httpx.Response(400, request=_make_request()), body={})
    aufrufe = _stub_create_kwargs(monkeypatch, [filter_fehler, _Antwort()])
    with pytest.raises(BadRequestError):
        llm.chat_complete(model="openai/gpt-6-luna", messages=[], _feature="assistant_explain")
    assert len(aufrufe) == 1 and _eu_umgebung == []


def test_eu_anderer_client_fehler_faellt_nicht_zurueck(_eu_umgebung, monkeypatch):
    from openai import APIStatusError
    aufrufe = _stub_create_kwargs(monkeypatch, [_fehler(401, "bad key"), _Antwort()])
    with pytest.raises(APIStatusError):
        llm.chat_complete(model="openai/gpt-6-luna", messages=[], _feature="qa_answer")
    assert len(aufrufe) == 1


def test_eu_nur_fuer_zdr_verzicht_und_gemessene_modelle(_eu_umgebung, monkeypatch):
    """Außerhalb von ZDR_VERZICHT und für Modelle ohne EU-Weg bleibt alles, wie es war."""
    aufrufe = _stub_create_kwargs(monkeypatch, [_Antwort()] * 4)
    llm.chat_complete(model="openai/gpt-6-luna", messages=[], _feature="impact_rating")
    llm.chat_complete(model="openai/gpt-6-luna", messages=[], _feature="qa_analysis")
    llm.chat_complete(model="google/gemini-3.1-flash-lite", messages=[], _feature="qa_answer")
    llm.chat_complete(model="openai/gpt-6-luna", messages=[])
    assert [a.get("_only") for a in aufrufe] == [None] * 4
    assert [a["_zdr"] for a in aufrufe] == [False, True, False, True]
    assert llm.eu_zuerst("deep_report", "openai/gpt-6-sol") == ("azure/eu",)
    assert set(llm.EU_ZUERST) == {"openai/gpt-6-luna", "openai/gpt-6-sol"}


def test_eu_notausschalter_und_messschalter(_eu_umgebung, monkeypatch):
    monkeypatch.setenv(llm.EU_ANBIETER_ENV, "gibtsnicht/eu")
    assert llm.eu_zuerst("qa_answer", "openai/gpt-6-luna") == ("gibtsnicht/eu",)
    monkeypatch.setenv("NWZ_OPENROUTER_ROUTING", "off")
    assert llm.eu_zuerst("qa_answer", "openai/gpt-6-luna") is None


def test_eu_messschalter_steht_in_keiner_env_vorlage():
    from pathlib import Path
    wurzel = Path(__file__).resolve().parent.parent
    for vorlage in wurzel.glob(".env*"):
        if vorlage.is_file():
            assert llm.EU_ANBIETER_ENV not in vorlage.read_text(errors="ignore"), vorlage


def _strom_mit(monkeypatch, plan):
    """``plan`` je Aufruf: Liste von Chunks; eine Exception darin wird geworfen."""
    aufrufe = []

    def fake_create(**kw):
        aufrufe.append(kw)
        teile = plan.pop(0)

        def gen():
            for t in teile:
                if isinstance(t, BaseException):
                    raise t
                yield t
        return gen()

    monkeypatch.setattr(llm, "_create", fake_create)
    return aufrufe


def test_eu_strom_ok_nur_azure(_eu_umgebung, monkeypatch):
    aufrufe = _strom_mit(monkeypatch, [[_strom_teil("EU")]])
    assert "".join(llm.chat_stream(model="openai/gpt-6-luna", messages=[],
                                   _feature="qa_answer")) == "EU"
    (kw,) = aufrufe
    assert kw["_only"] == ("azure/eu",) and kw["_zdr"] is True


def test_eu_strom_fehler_vor_dem_ersten_token_faellt_zurueck(_eu_umgebung, monkeypatch, tmp_path):
    from openai import APIError
    monkeypatch.setenv(llm.MITSCHNITT_ENV, str(tmp_path))
    im_strom = APIError("Provider returned error", request=_make_request(), body=None)
    aufrufe = _strom_mit(monkeypatch, [[im_strom], [_strom_teil("US ", "m"), _strom_teil("Text")]])
    assert "".join(llm.chat_stream(model="openai/gpt-6-luna", messages=[],
                                   _feature="assistant_explain")) == "US Text"
    assert [(a["_zdr"], a["_only"]) for a in aufrufe] == [(True, ("azure/eu",)), (False, None)]
    (z,) = _zeilen(tmp_path, "assistant_explain")
    assert z["fallback"] is True and z["aborted"] is False


def test_eu_recherche_plus_mit_sol_geht_zuerst_nach_azure_eu(_eu_umgebung, monkeypatch):
    """Recherche Plus (#1506): ``deep_report`` läuft für ``premium_models`` auf
    GPT-6 Sol — auch dort zuerst azure/eu mit ZDR, erst dann ohne."""
    aufrufe = _strom_mit(monkeypatch, [[llm.EmptyResponseError("leer")], [_strom_teil("Bericht")]])
    assert "".join(llm.chat_stream(model="openai/gpt-6-sol", messages=[],
                                   _feature="deep_report")) == "Bericht"
    assert [(a["_zdr"], a["_only"]) for a in aufrufe] == [(True, ("azure/eu",)), (False, None)]
    assert _routing(aufrufe[0])["only"] == ["azure/eu"]


def test_eu_strom_verbindungsfehler_faellt_zurueck(_eu_umgebung, monkeypatch):
    aufrufe = []

    def fake_create(**kw):
        aufrufe.append(kw)
        if kw["_only"]:
            raise _fehler(429, "temporarily rate-limited upstream")
        return iter([_strom_teil("ok")])

    monkeypatch.setattr(llm, "_create", fake_create)
    assert "".join(llm.chat_stream(model="openai/gpt-6-luna", messages=[],
                                   _feature="deep_report")) == "ok"
    assert len(aufrufe) == 2


def test_eu_strom_fehler_nach_dem_ersten_token_reisst_wie_bisher(_eu_umgebung, monkeypatch):
    """Schon ausgeliefert → kein zweiter Weg (sonst zwei Antworten in einem
    Fenster); der Router erzeugt wie bisher neu."""
    from openai import APIError
    aufrufe = _strom_mit(monkeypatch, [[_strom_teil("Anfang"),
                                        APIError("weg", request=_make_request(), body=None)],
                                       [_strom_teil("nie")]])
    teile = []
    with pytest.raises(APIError):
        for t in llm.chat_stream(model="openai/gpt-6-luna", messages=[], _feature="qa_answer"):
            teile.append(t)
    assert teile == ["Anfang"] and len(aufrufe) == 1


def test_eu_strom_inhaltsfilter_faellt_nicht_zurueck(_eu_umgebung, monkeypatch):
    from openai import APIError
    treffer = APIError("The response was filtered due to content_filter",
                       request=_make_request(), body=None)
    aufrufe = _strom_mit(monkeypatch, [[treffer], [_strom_teil("nie")]])
    with pytest.raises(APIError):
        list(llm.chat_stream(model="openai/gpt-6-luna", messages=[], _feature="qa_answer"))
    assert len(aufrufe) == 1


def test_eu_strom_zaehlt_den_rueckfall(_eu_umgebung, monkeypatch):
    verbrauch = type("U", (), {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.0})()
    nutzung = type("K", (), {"choices": [], "usage": verbrauch, "model": "m"})()
    _strom_mit(monkeypatch, [[llm.EmptyResponseError("leer")], [_strom_teil("x"), nutzung]])
    list(llm.chat_stream(model="openai/gpt-6-luna", messages=[], _feature="qa_answer"))
    assert _eu_umgebung == [("qa_answer", "openai/gpt-6-luna" + llm.RUECKFALL_MARKE)]


def test_strom_ausserhalb_bleibt_ein_weg(_eu_umgebung, monkeypatch):
    aufrufe = _strom_mit(monkeypatch, [[llm.EmptyResponseError("leer")], [_strom_teil("nie")]])
    with pytest.raises(llm.EmptyResponseError):
        list(llm.chat_stream(model="openai/gpt-6-luna", messages=[], _feature="qa_analysis"))
    assert len(aufrufe) == 1 and aufrufe[0]["_only"] is None
