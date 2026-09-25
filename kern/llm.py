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
import time
from collections.abc import Generator, Iterator
from typing import Any

from openai import (
    OpenAI,
    APIError,
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

# Die großen Geminis (Pro der 2.5/3.x-Reihe und 3.8-flash) denken ebenfalls —
# und anders als bei DeepSeek lässt sich das NICHT abschalten: OpenRouter
# antwortet auf `reasoning.enabled=false` mit HTTP 400 „Reasoning is mandatory
# for this endpoint". Gemessen am 22.09.2026 mit Lottis Budget von 350 Tokens
# (council/assistant.py::MAX_TOKENS): completion_tokens 346 von 350, sichtbarer
# Text 53 Zeichen — die Antwort war abgeschnitten, ohne Fehler. Bleibt nur der
# Boden. Beobachtet wurden 530–1.220 Denk-Tokens; 4.000 lassen Luft, und
# max_tokens ist eine Decke, keine Bestellung — bezahlt wird, was erzeugt wird.
GEMINI_DENK_MIN_MAX_TOKENS = int(os.environ.get("NWZ_GEMINI_DENK_MIN_MAX_TOKENS", "4000"))

MODEL_PARAMS: dict[str, dict[str, Any]] = {
    "openai/gpt-4o": {},
    "openai/gpt-4o-mini": {},
    "deepseek/deepseek-v4-pro": {"min_max_tokens": DEEPSEEK_MIN_MAX_TOKENS},
    "deepseek/deepseek-v4-flash": {"min_max_tokens": DEEPSEEK_MIN_MAX_TOKENS},
    # Die datierte Fassung fehlte hier bis 09/2026 — und ohne den Boden
    # verbraucht sie ihr Budget beim Denken und antwortet LEER (Status 200,
    # finish_reason='length'). Gemessen am Städte-Prüfstand: 84 % Lieferquote
    # statt 100 %, bei 38 statt 2 Minuten. Wer ein neues DeepSeek-Modell
    # benutzt, trägt es hier ein.
    "deepseek/deepseek-v4-flash-0731": {"min_max_tokens": DEEPSEEK_MIN_MAX_TOKENS},
    **{m: {"min_max_tokens": GPT56_MIN_MAX_TOKENS} for m in (
        "openai/gpt-5.6-luna", "openai/gpt-5.6-luna-pro",
        "openai/gpt-5.6-sol", "openai/gpt-5.6-sol-pro",
        "openai/gpt-5.6-terra", "openai/gpt-5.6-terra-pro",
    )},
    # Der Modellvergleich für Lottis Erklärungen (PR 29, Tabelle in
    # docs/plan-lotti-assistentin-3.md). Gemini 2.5 Flash braucht keinen
    # Eintrag — es denkt bei dieser Aufgabe nicht —, die drei hier schon.
    **{m: {"min_max_tokens": GEMINI_DENK_MIN_MAX_TOKENS} for m in (
        "google/gemini-3.1-pro-preview", "google/gemini-2.5-pro",
        "google/gemini-3.8-flash",
    )},
    # Claude Sonnet läuft ohne Sonderbehandlung (und schon als Zweitmodell der
    # OCR, council/ocr.py::MODEL_ZWEIT) — der leere Eintrag ist trotzdem
    # Pflicht: Er ist die Liste der Modelle, die hier je gemessen wurden.
    "anthropic/claude-sonnet-4.6": {},
    # Nachfolger-Kandidaten (Messung 22.09.2026, s. docs/plan-modellwechsel.md):
    # Gemini 2.5 Flash/Flash Lite laufen bei OpenRouter am 20.10.2026 aus.
    # Boden vorsorglich, bis gemessen ist, welche davon denken.
    **{m: {"min_max_tokens": GEMINI_DENK_MIN_MAX_TOKENS} for m in (
        "google/gemini-3-flash-preview", "google/gemini-3.5-flash",
    )},
    # Die beiden Flash-Lite-Modelle denken NICHT — gemessen 23.09.2026 (P4a)
    # ohne Boden mit 350 Tokens Budget: reasoning_tokens 0, 96–103
    # completion_tokens, finish_reason `stop`; in der Lotti-Eval höchstens
    # 800 Zeichen (≈ 200 Tokens) je Antwort. Der vorsorgliche Boden von 4.000
    # hob Lottis zweite Bremse (MAX_TOKENS 350) still auf. Der leere Eintrag
    # bleibt: Er sagt, dass hier gemessen wurde.
    "google/gemini-3.1-flash-lite": {},
    "google/gemini-3.5-flash-lite": {},
    # GPT-6 Sol denkt wie Luna: gemessen an der ausführlichen Recherche
    # (23.09.2026, eval/run_fakten.py --kanal deep) — ohne den Boden bekäme
    # der Bericht nur die 4.000 Tokens aus `qa.deep_bericht_stream`, von denen
    # das Denken zuerst zehrt.
    **{m: {"min_max_tokens": GPT56_MIN_MAX_TOKENS} for m in (
        "openai/gpt-6-luna", "openai/gpt-6-sol")},
}


#: Wie lange ein BATCH-Job bei einem vorübergehenden Fehler zusätzlich wartet,
#: nachdem die vier schnellen Anläufe von ``_create`` (2–8 s) verbraucht sind.
#: Gemessen am 06.09.2026: OpenRouters geteilter OpenAI-Zugang meldet Luna
#: minutenlang als „temporarily rate-limited upstream" — 37 von 39 Treffern in
#: den Prod-Logs seit dem 03.09. Eine Welle von Minuten überlebt kein
#: Sekunden-Retry; ein Cron darf dagegen ruhig fünf Minuten warten. Für
#: Web-Anfragen gilt das NICHT — dort bleibt es bei den schnellen Anläufen.
GEDULD_PAUSEN: tuple[int, ...] = (30, 90, 180)

#: Ersatzmodelle, wenn das gewünschte Modell auch nach der Geduld nicht
#: antwortet. Gemessen am Tragweite-Golden-Set (30 handbewertete Beschlüsse) —
#: Spearman über die Band-Mitten und Band-Trefferquote, dazu die Dauer:
#:
#:   openai/gpt-5.6-luna           ρ 0,833   27/30   14 s   (06.09.2026, scripts/eval_impact.py)
#:   google/gemini-2.5-flash       ρ 0,831   26/30   21 s   (06.09.2026, scripts/eval_impact.py)
#:   deepseek/deepseek-v4-pro      ρ 0,820   23/30   75 s   (06.09.2026, scripts/eval_impact.py)
#:   google/gemini-3.1-flash-lite  ρ 0,786   27/30    6 s   (06.09.2026, scripts/eval_impact.py)
#:   openai/gpt-6-luna             91,7 % ± 3,3 Band-Trefferquote — docs/modell-pruefstand.md (`tragweite`)
#:   deepseek/deepseek-v4-pro      90,0 % (27/30), 40 s p50, 0,81 ct/Aufruf (23.09.2026,
#:                                  eval/pruefstand.py --suite tragweite --modell deepseek/deepseek-v4-pro)
#:
#: **Gemini 2.5 Flash fliegt aus der 5.6-Luna-Kette** (P5,
#: docs/plan-modellwechsel.md): Es läuft bei OpenRouter am 20.10.2026 aus, ein
#: Ersatz, der selbst ausfällt, taugt nichts. An seine Stelle tritt Gemini
#: 3.1 Flash Lite (dieselbe 06.09.-Messung, ZDR-fähig wie 2.5 Flash) statt
#: GPT-6 Luna: **GPT-5.6 Luna ist auch Ersatz für den Watcher**
#: (``council/watcher.py``, Feature ``council_watcher``, ZDR-Pflicht), und
#: GPT-6 Luna hat GAR KEINEN ZDR-Endpunkt (s. ``OHNE_NUTZEREINGABE``) — als
#: Ersatz für ein ZDR-Feature würfe er sofort einen 404, statt weiterzureichen.
#: Die Kette hier ist pro MODELL, nicht pro Feature, also muss sie für ihren
#: strengsten Aufrufer stimmen.
#:
#: Für GPT-6 Luna selbst — nur an ZDR-freien Features im Einsatz (Social-Text,
#: Kritiker, Viertel, Tragweite, Ausschuss, s. P5) — kommt zuerst GPT-5.6 Luna
#: (anderer Anbieterpool: Azure statt OpenAI direkt/Bedrock, im Prüfstand
#: gleichauf), dann dieselbe frisch nachgemessene DeepSeek-Reserve.
#: Die anderen GPT-5.6-Varianten (sol, terra) hängen am selben Pool wie 5.6
#: Luna und taugen deshalb NICHT als Ersatz. Wer die Reihenfolge ändert, misst neu.
ERSATZ: dict[str, tuple[str, ...]] = {
    "openai/gpt-5.6-luna": ("google/gemini-3.1-flash-lite", "deepseek/deepseek-v4-pro"),
    "openai/gpt-6-luna": ("openai/gpt-5.6-luna", "deepseek/deepseek-v4-pro"),
}


#: Denkaufwand je Modell UND Feature für die Web-Antworten (Lotti, „Frag den
#: Rat“) — NICHT in ``MODEL_PARAMS``, weil derselbe Modellname dort auch für
#: die Crons gilt. Leer heißt: der Aufwand, den der Anbieter ohne Angabe wählt.
#:
#: **GPT-6 Luna läuft mit der Vorgabe, nicht mit ``low``** — entschieden an
#: der Fakten-Eval (``eval/run_fakten.py``, 233 Fälle, 23.09.2026, Stand nach
#: #1503/#1504, je ein Lauf; Regel: weniger ``modell_*``-Fehler gewinnt,
#: Auslassungen zählen, nur bei höchstens zwei Fällen Abstand gewinnt ``low``
#: wegen der Latenz):
#:
#:   Lotti (assistant_explain)   low 13 Modellfehler, p50 3,3 s — Vorgabe 10, p50 5,0 s
#:   Frag den Rat (qa_answer)    low 31 (5 falsch),  p50 5,6 s — Vorgabe 27 (3 falsch), p50 11,7 s
#:
#: Ein Vorlauf vor #1503/#1504 zeigte dieselbe Richtung bei der Antwort (33
#: gegen 27) und Gleichstand bei Lotti (8 gegen 9). Die Lotti-Eval
#: (``run_assistant``) sah bei ``low`` keinen Verlust — sie prüft Zusagen,
#: nicht Vollständigkeit; die Fakten-Eval zählt jede ausgelassene Pflicht-
#: Angabe. Tims Regel: „Akkuratheit schlägt Geschwindigkeit“.
WEB_DENKAUFWAND: dict[tuple[str, str], str] = {}

#: **Ein reiner Messschalter** wie ``TARIF_ENV``: überschreibt den Denkaufwand
#: aller Web-Antworten, damit die Fakten-Eval (``eval/run_fakten.py``, die ein
#: eigenes Backend startet) beide Stufen messen kann. ``vorgabe`` = der
#: Aufwand, den der Anbieter ohne Angabe wählt. In eine ``.env`` gehört er nicht.
WEB_DENKAUFWAND_ENV = "RATSLOTSE_WEB_DENKAUFWAND"


def web_denk_extra(model: str, feature: str) -> dict[str, Any]:
    """Die ``extra_body``-Einstellung zum Denken für eine Web-Antwort.

    DeepSeek ohne Denken (wie bisher an jeder Aufrufstelle), sonst der
    gemessene Aufwand aus :data:`WEB_DENKAUFWAND` je Modell UND Feature.
    """
    if "deepseek" in model:
        return {"extra_body": {"reasoning": {"enabled": False}}}
    aufwand: str | None = WEB_DENKAUFWAND.get((model, feature))
    mess = os.environ.get(WEB_DENKAUFWAND_ENV, "").strip()
    if mess:
        aufwand = None if mess == "vorgabe" else mess
    return {"extra_body": {"reasoning": {"effort": aufwand}}} if aufwand else {}


def ersatz_fuer(model: str | None) -> list[str]:
    """Die Ersatzmodelle zu ``model`` — leer, wenn keine gemessen sind."""
    return list(ERSATZ.get(model or "", ()))


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


#: Features, die NUR öffentliche Ratsdaten verarbeiten — keine Frage, kein
#: Thema, keinen Text, den eine Nutzerin selbst geschrieben hat. Für sie
#: entfällt die ZDR-Pflicht (Tims Entscheidung 22.09.2026: „für alles, was
#: keinen direkten User-Input verarbeitet, sind nicht-ZDR-Provider auch
#: fine"). Was bleibt: kein Training auf unseren Daten (`data_collection:
#: deny`) und kein Anbieter aus China.
#:
#: Anlass: GPT-6 Luna bieten bisher nur OpenAI direkt und Amazon Bedrock an,
#: beide ohne ZDR — unter der Pflicht endete jeder Aufruf mit 404 „No
#: endpoints found matching your data policy".
#:
#: **Die Liste ist eine Freigabe, keine Sperre.** Ein Feature, das hier
#: fehlt, bleibt bei ZDR — auch ein Aufruf ganz ohne `_feature` (der Watcher
#: trug bis heute keinen und verarbeitet die Themenbeschreibungen der
#: Nutzer*innen). Wer ein Feature einträgt, prüft vorher, was im Prompt
#: steht; `tests/test_llm.py` hält fest, dass die Nutzer-Pfade nie hier landen.
OHNE_NUTZEREINGABE: frozenset[str] = frozenset({
    # Bewertungen und Kurzfassungen von Beschlüssen und Tagesordnungen
    "impact_rating", "impact_rating_agenda", "interest_rating", "goal_rating",
    "simple_summary", "committee_summary", "topic_classification", "field_recap",
    "daily_find_story", "quiz_generation", "quiz_verify", "quiz_appeal", "quiz_motion_context",
    # Protokolle, Anlagen, Sitzungs-Mitschnitt
    "minutes_extraction", "attachment_ocr", "speeches", "video_results",
    "livestream_transcript", "live_top_tracker",
    # Entitäten, Orte, Viertel
    "entity_ner", "entity_duplicates", "entity_description", "decision_places",
    "district_projects",
    # Social-Texte über Beschlüsse
    "social_card_text", "social_critic",
    # Städtevergleich: fremde Ratsdokumente
    "cities_evidence_terms",
})

#: Die Städte-Annotatoren bilden ihren Namen als ``cities_<key>``
#: (``council/cities/annotators.py``); ``kern`` darf ihre Liste nicht
#: importieren (Schichtenregel). Alle verarbeiten fremde Ratsdokumente.
#: Ihre Evals (``eval/run_cities_*.py``) rechnen unter ``eval_cities_<…>``
#: ab, schicken aber dieselben Dokumente — und müssen unter demselben
#: Routing messen wie der Cron, sonst misst die Eval die ZDR-Lücke mit
#: (``gpt-5.6-luna``: 53 % Lieferquote mit ZDR, 100 % ohne).
_OHNE_NUTZEREINGABE_PRAEFIX = ("cities_", "eval_cities_")


#: Features MIT Nutzereingabe, die trotzdem ohne ZDR laufen dürfen — eine
#: ausdrückliche, benannte Ausnahme, keine Lockerung der Regel oben.
#:
#: **Tims Entscheidung 23.09.2026:** Lotti und die Antwort von „Frag den Rat“
#: laufen auf GPT-6 Luna, „auch wenn die kein Zero Data Retention haben —
#: das ist wenigstens kein chinesischer Anbieter“. Anlass war ein
#: Faktencheck an 14 echten Antworten, Aussage für Aussage gegen Kontext und
#: Datenbank: GPT-6 Luna in 12 von 14 fehlerfrei, Gemini 2.5 Flash in 5
#: von 14 („Akkuratheit schlägt Geschwindigkeit“). GPT-6 Luna bieten bei
#: OpenRouter nur OpenAI direkt und Amazon Bedrock an, beide ohne ZDR — unter
#: der Pflicht endete jeder Aufruf mit 404.
#:
#: Genau die Features, die ``COUNCIL_ASSISTANT_MODEL`` bzw.
#: ``COUNCIL_QA_MODEL`` lesen (Stand 23.09.2026): Lottis Erklärung, die
#: Antwort, die vereinfachte Antwort, der Deep-Research-Bericht und die
#: Partei-Meinungen. NICHT dabei ist die Analyse vor der Suche
#: (``qa_analysis``, ``qa_query_expansion``, ``deep_decomposition`` — sie
#: laufen auf ``COUNCIL_QA_EXPAND_MODEL`` und behalten ZDR), der Watcher und
#: die Themen-Beschreibung. **Was bleibt, auch hier:** kein Training
#: (``data_collection: deny``), kein Anbieter aus China, nie Flex/Batch
#: (:func:`nutzereingabe`). ``tests/test_llm.py`` hält alle drei fest.
#:
#: **Seit dem Abend des 23.09. nur noch der Rückfall:** Für die Modelle aus
#: :data:`EU_ZUERST` geht der erste Versuch an Azure EU mit ZDR.
ZDR_VERZICHT: frozenset[str] = frozenset({
    "assistant_explain", "qa_answer", "qa_simple", "deep_report", "party_opinions",
})


def nutzereingabe(feature: str | None) -> bool:
    """Trägt der Prompt dieses Features Text, den eine Nutzerin geschrieben hat?

    Unabhängig von :data:`ZDR_VERZICHT`: Der Verzicht betrifft nur ZDR. Für
    Flex/Batch und den Prüfstand bleibt ein solches Feature Nutzereingabe.
    """
    if not feature:
        return True
    return not (feature in OHNE_NUTZEREINGABE or feature.startswith(_OHNE_NUTZEREINGABE_PRAEFIX))


def zdr_pflicht(feature: str | None) -> bool:
    """Ob ein Aufruf dieses Features nur an ZDR-Anbieter gehen darf."""
    return nutzereingabe(feature) and feature not in ZDR_VERZICHT


#: **EU zuerst, mit ZDR** — für die Features aus :data:`ZDR_VERZICHT`, wenn
#: das Modell einen EU-Endpunkt mit ZDR hat. Erst dieser Weg; nur wenn er
#: ausfällt, derselbe Aufruf mit dem Verzicht-Routing (OpenAI direkt u. a.,
#: ohne ZDR). **Tims Entscheidung 23.09.2026**; der Verzicht von vorher gilt
#: seitdem nur noch als Rückfall.
#:
#: Anlass: OpenRouter führt GPT-6 Luna seit dem 23.09.2026 auch bei Azure,
#: mit dem Endpunkt ``azure/eu`` (ZDR). Gemessen mit ``zdr: true``,
#: ``data_collection: deny`` und ``only: ["azure/eu"]``: 20/20 Aufrufe ok, p50
#: 3,4 s, max 5,0 s. Mit ``zdr: true`` OHNE Anbietervorgabe kam einmal
#: „temporarily rate-limited upstream“ — deshalb die feste Vorgabe. ``only``
#: und ``ignore`` gehen zusammen (Probe 23.09.: Antwort von Azure).
#: ``azure/eu`` kostet 10 % mehr als OpenAI direkt (0,11 statt 0,10 $ je
#: Million Eingabe-Tokens). Fakten-Eval (233 Fälle, zwei Läufe gleichzeitig,
#: 23.09.): gleiche Qualität (177/34 gegen 176/37 ok/Modellfehler — ein
#: früherer Lauf über OpenAI hatte ebenfalls 176/37), p50 8,7 → 6,7 s, p95
#: 28,4 → 17,7 s; 0 Rückfälle bei 236 Luna-Aufrufen.
#:
#: GPT-6 Sol steht mit drin, weil es dieselben Features bedienen kann
#: (``COUNCIL_DEEP_MODEL``) und ``azure/eu`` ebenfalls anbietet (Probe
#: 23.09.: Antwort von Azure, Einmal-Aufruf und Strom). Ein Modell OHNE
#: Eintrag hier bleibt beim bisherigen Routing — ein EU-Versuch bei einem
#: Modell, das dort nicht angeboten wird, wäre ein sicherer 404 und würde
#: jeden Aufruf als Rückfall zählen.
EU_ZUERST: dict[str, tuple[str, ...]] = {
    "openai/gpt-6-luna": ("azure/eu",),
    "openai/gpt-6-sol": ("azure/eu",),
}

#: **Ein reiner Messschalter** wie ``TARIF_ENV``: ersetzt die Anbieterliste
#: aus :data:`EU_ZUERST` (kommagetrennt). Ein Anbieter, den es nicht gibt
#: (``gibtsnicht/eu``), erzwingt den Rückfall — so prüft man den zweiten Weg
#: am echten Codepfad. In eine ``.env`` gehört er nicht.
EU_ANBIETER_ENV = "RATSLOTSE_EU_ANBIETER"

#: So steht ein Rückfall in ``llm_usage.model`` — ein eigener Modellname, damit
#: er im Admin-Panel (``by_model`` je Feature: Aufrufe und Kosten) als eigene
#: Zeile auftaucht und sich zählen lässt:
#: ``SELECT COUNT(*) FROM llm_usage WHERE model LIKE '%@fallback-no-zdr'``.
RUECKFALL_MARKE = "@fallback-no-zdr"


def eu_zuerst(feature: str | None, model: str | None) -> tuple[str, ...] | None:
    """Die EU-Anbieter für den ersten Weg — ``None``: nur das bisherige Routing."""
    if feature not in ZDR_VERZICHT:
        return None
    if os.environ.get("NWZ_OPENROUTER_ROUTING", "on").strip().lower() == "off":
        return None
    anbieter = EU_ZUERST.get(model or "")
    if not anbieter:
        return None
    mess = os.environ.get(EU_ANBIETER_ENV, "").strip()
    if mess:
        anbieter = tuple(s.strip() for s in mess.split(",") if s.strip())
    return anbieter or None


def _routing_extra_body(zdr: bool = True, only: tuple[str, ...] | None = None) -> dict[str, Any]:
    if os.environ.get("NWZ_OPENROUTER_ROUTING", "on").strip().lower() == "off":
        return {}
    provider: dict[str, Any] = {"data_collection": "deny"}
    ignore = [s.strip() for s in os.environ.get("NWZ_OPENROUTER_IGNORE", _IGNORE_CN_DEFAULT).split(",") if s.strip()]
    if ignore:
        provider["ignore"] = ignore
    if zdr and os.environ.get("NWZ_OPENROUTER_ZDR", "1").strip().lower() not in ("0", "false", "off", "no"):
        provider["zdr"] = True
    if only:
        provider["only"] = list(only)
    return {"provider": provider}


def _with_routing(kwargs: dict[str, Any], zdr: bool = True,
                  only: tuple[str, ...] | None = None) -> dict[str, Any]:
    """Merge the OpenRouter provider-routing block into the request's extra_body
    (a caller-supplied 'provider' wins, so call sites can still override)."""
    rb = _routing_extra_body(zdr, only)
    if not rb:
        return kwargs
    extra_body = {**rb, **(kwargs.get("extra_body") or {})}
    return {**kwargs, "extra_body": extra_body}


# Flex-Tarif: derselbe Aufruf, halber Preis, dafür darf der Anbieter ihn bei
# Engpass abweisen. Gemessen am 22.09.2026 am Tragweite-Golden-Set (30
# Beschlüsse, je 5 Läufe; Tabelle in docs/modell-batch-flex.md):
#
#   gpt-5.6-luna   normal ρ 0,839  27,2/30  0,105 ct/Aufruf   flex ρ 0,866  27,8/30  0,055 ct
#   gpt-6-luna     normal ρ 0,810  26,5/30  0,048 ct/Aufruf   flex ρ 0,855  26,8/30  0,023 ct
#
# Gleiche Qualität, gleiche Dauer, keine einzige Abweisung in 24 Flex-Aufrufen.
# Zwei Bedingungen hängen daran:
#
# ① Flex-Endpunkte haben KEIN ZDR. Mit `zdr: true` im Routing-Block ignoriert
#   OpenRouter `service_tier` still (Luna 5.6 ging an Azure, `service_tier:
#   default`, voller Preis) oder findet gar keinen Endpunkt (GPT-6 Luna: 404).
#   Deshalb fällt `zdr` hier weg — und deshalb ist Flex nur für Features
#   ohne Nutzereingabe erlaubt (`nutzereingabe`, NICHT `zdr_pflicht`: Der
#   ZDR-Verzicht für Lotti und die Antwort gibt Flex nicht frei).
#   `data_collection: deny` und die China-Liste bleiben.
# ② Eine Abweisung darf keinen Stapel kosten: Dann läuft derselbe Aufruf im
#   normalen Tarif (und dessen Routing) noch einmal.
TARIFE = ("normal", "flex")

#: **Ein reiner Messschalter, nicht für den Betrieb.** Der Modell-Prüfstand
#: (``eval/pruefstand.py --tarif flex``) muss Aufrufe tief in ``council/``
#: umschalten, ohne jede Aufrufstelle anzufassen — er setzt diese Variable
#: im Unterprozess eines Messlaufs. Sie ist nur die VORGABE: Ein ausdrückliches
#: ``_tarif`` gewinnt, und für ein Feature mit Nutzereingabe wirft sie wie der
#: Parameter ``FlexNichtErlaubt``, statt still auf den Normaltarif zu fallen.
#: In eine ``.env`` gehört sie nicht: Dort stellte sie jedes Feature auf
#: einmal um, und jeder Nutzerpfad würfe den Fehler.
TARIF_ENV = "RATSLOTSE_LLM_TARIF"


class FlexNichtErlaubt(ValueError):
    """Flex für ein Feature mit Nutzereingabe (:func:`nutzereingabe`).

    Ein Fehler statt eines stillen Rückfalls: Wer ``_tarif="flex"`` schreibt,
    glaubt, die Hälfte zu sparen. Sähe er stattdessen den vollen Preis, fiele
    das erst in der Monatsabrechnung auf.
    """


def _flex_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Die Anfrage im Flex-Tarif: nur ``service_tier`` dazu.

    Das Routing ohne ZDR baut ``_create`` selbst (``_zdr=False``, von
    ``chat_complete`` aus ``zdr_pflicht`` gesetzt). Flex kommt nur für
    solche Features hierher, ein zweiter ZDR-Pfad wäre also doppelt.
    """
    extra_body = {**(kwargs.get("extra_body") or {}), "service_tier": "flex"}
    return {**kwargs, "extra_body": extra_body}


#: **Ein reiner Messschalter, nicht für den Betrieb** — wie ``TARIF_ENV``.
#: Gesetzt auf einen Ordner, schreibt jeder Aufruf von ``chat_complete`` und
#: ``chat_stream`` eine JSON-Zeile nach ``<ordner>/<feature>.jsonl``: die
#: ``messages``, das angefragte und das antwortende Modell, die Antwort.
#:
#: Anlass ist die Fakten-Eval (``eval/run_fakten.py``, 23.09.2026): Sie trennt
#: Kontextfehler von Modellfehlern, und dafür muss sie den Prompt sehen, den
#: das Modell WIRKLICH bekam. Den von Frag den Rat setzt der Router zusammen
#: (Retrieval, Presse, Haushaltszahlen, Verlauf) — nachbauen hieße, genau die
#: Stelle zu raten, an der der Fehler sitzen kann. Der Faktencheck davor
#: hatte Lottis Kontext rekonstruiert und fand trotzdem nur, was die
#: Rekonstruktion abbildete.
#:
#: In eine ``.env`` gehört er NIE: Er schriebe jede Nutzerfrage samt Kontext
#: im Klartext auf die Platte — also genau das, was ZDR beim Anbieter
#: ausschließen soll. Ein Schreibfehler hier bricht keinen Aufruf ab.
MITSCHNITT_ENV = "RATSLOTSE_PROMPT_MITSCHNITT"


def _mitschnitt(feature: str | None, kwargs: dict[str, Any], antwort: str | None, *,
                antwort_modell: str | None = None, abgebrochen: bool = False,
                finish_reason: str | None = None, usage_obj: Any = None,
                anbieter: str | None = None, rueckfall: bool = False) -> None:
    """Eine Zeile ins Mitschnitt-Protokoll — nur wenn der Messschalter gesetzt ist."""
    ordner = os.environ.get(MITSCHNITT_ENV, "").strip()
    if not ordner:
        return
    try:
        from pathlib import Path
        ziel = Path(ordner)
        ziel.mkdir(parents=True, exist_ok=True)
        zeile = {
            "ts": time.time(),
            "feature": feature,
            "model": kwargs.get("model"),
            # Wer wirklich geantwortet hat (OpenRouter trägt es in der Antwort) —
            # der Nachweis, dass die Umschaltung gewirkt hat.
            "response_model": antwort_modell,
            # Welcher Anbieter geantwortet hat (``Azure``, ``OpenAI`` …) und ob
            # der EU-Weg ausgefallen war (:data:`EU_ZUERST`) — die Fakten-Eval
            # zählt daraus die Rückfälle ihres Laufs.
            "provider": anbieter,
            "fallback": rueckfall,
            # Der Denkaufwand, der wirklich rausging — der Nachweis, dass
            # `WEB_DENKAUFWAND_ENV` im Mess-Backend angekommen ist (P4a).
            "reasoning": (kwargs.get("extra_body") or {}).get("reasoning"),
            "messages": kwargs.get("messages"),
            "answer": antwort,
            "aborted": abgebrochen,
            # `length` heißt: abgeschnitten, ohne Fehler. Bei denkenden
            # Modellen zehrt das Denken vom selben Budget — mehr Aufwand kann
            # den sichtbaren Text still kürzen (Messung Deep-Bericht, 23.09.).
            "finish_reason": finish_reason,
            "usage": _usage_kurz(usage_obj),
        }
        with open(ziel / f"{feature or 'ohne_feature'}.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(zeile, ensure_ascii=False, default=str) + "\n")
    except Exception:  # noqa: BLE001 — ein Messschalter bricht nie einen Aufruf ab
        pass


def _antworttext(resp: Any) -> str | None:
    try:
        return resp.choices[0].message.content
    except (AttributeError, IndexError, TypeError):
        return None


def _finish_reason(resp: Any) -> str | None:
    try:
        return resp.choices[0].finish_reason
    except (AttributeError, IndexError, TypeError):
        return None


def _usage_kurz(usage_obj: Any) -> dict | None:
    """Tokens eines Aufrufs für den Mitschnitt — samt Denk-Tokens."""
    if usage_obj is None:
        return None
    details = getattr(usage_obj, "completion_tokens_details", None)
    return {"prompt_tokens": getattr(usage_obj, "prompt_tokens", None),
            "completion_tokens": getattr(usage_obj, "completion_tokens", None),
            "reasoning_tokens": getattr(details, "reasoning_tokens", None) if details else None}


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
def _create(*, _allow_empty_response: bool = False, _zdr: bool = True,
            _only: tuple[str, ...] | None = None, **kwargs: Any):
    merged = _with_model_params(_with_routing(kwargs, _zdr, _only))
    # OpenRouter soll die ECHTEN Kosten des Aufrufs mitliefern (usage.cost, in
    # USD, inkl. Provider-Routing) — Modellpreise von Hand pflegen entfällt
    # damit dort, wo der Wert ankommt (Admin-Statistik, Eval-Kostenzeile).
    merged.setdefault("extra_body", {}).setdefault("usage", {"include": True})
    resp = get_client().chat.completions.create(**merged)
    # Beim Strom ist die erste Antwort ein Iterator, keine fertige Completion —
    # dort prüft chat_stream ohnehin jeden Chunk auf `choices`.
    # Wenige Aufrufer besitzen bereits eine bewusst andere Leerantwort-
    # Strategie (Chunk verwerfen, lokaler Retry oder optionaler Baustein).
    # Nur sie dürfen die rohe Antwort übernehmen; überall sonst bleibt der
    # zentrale, retried Fehler verbindlich.
    if not merged.get("stream") and not _allow_empty_response:
        _pruefe_choices(resp, merged.get("model"))
    return resp


def _inhaltsfilter(exc: BaseException) -> bool:
    """Inhaltsfilter-Treffer — auch als Fehler MITTEN im Strom.

    :func:`is_content_filter` kennt nur den 400er beim Verbindungsaufbau. Im
    Strom meldet OpenRouter Fehler als eigenes Ereignis, und das SDK wirft
    daraus ein nacktes ``APIError`` — dieselbe Textsuche, anderer Typ.
    """
    if is_content_filter(exc):
        return True
    if isinstance(exc, APIError) and not isinstance(exc, APIStatusError):
        blob = f"{getattr(exc, 'message', '')} {getattr(exc, 'body', '')} {exc}".lower()
        return "content_filter" in blob or "content management policy" in blob or "responsibleai" in blob
    return False


def _eu_rueckfall_erlaubt(exc: BaseException) -> bool:
    """Darf ein Fehler des EU-Wegs zum Verzicht-Routing führen?

    Ja bei allem, was am Anbieter hängt: Vorübergehendes (:func:`_is_transient`
    — 429, 5xx, Netz, 200er ohne ``choices``), ein 404 („No allowed providers“,
    wenn ``azure/eu`` das Modell nicht mehr führt) und ein Fehler-Ereignis im
    Strom. **Nein bei einem Inhaltsfilter-Treffer:** Der hängt am Text der
    Anfrage — Azures Filter ist strenger als OpenAIs, und ein Rückfall schickte
    genau den Text, den ein Anbieter gerade abgelehnt hat, in die USA.
    """
    if _inhaltsfilter(exc):
        return False
    if _is_transient(exc):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code == 404
    return isinstance(exc, APIError)  # Fehler-Ereignis im Strom


def _anbieter(obj: Any) -> str | None:
    """Welcher Anbieter geantwortet hat — OpenRouter trägt es als ``provider``."""
    extra = getattr(obj, "model_extra", None)
    wert = extra.get("provider") if isinstance(extra, dict) else None
    return wert if isinstance(wert, str) else getattr(obj, "provider", None)


def _melde_rueckfall(feature: str | None, model: str | None, exc: BaseException) -> None:
    """Der Rückfall steht im Log — die Zählung übernimmt ``llm_usage``."""
    print(f"  🇪🇺↩️ {feature}/{model}: EU-Weg ausgefallen ({exc!r}) — "
          "Rückfall auf das Routing ohne ZDR", flush=True)


def _eu_anlauf(kwargs: dict[str, Any]):
    """``_create`` für den EU-Weg — mit EINEM Anlauf, wenn der Aufrufer eine Frist setzt.

    Wer ``timeout=`` mitgibt, wartet vor einem Bildschirm (Lottis Fenster). Am
    24.09.2026 antwortete Azure EU unter einer Drosselung minutenlang gar
    nicht: vier Anläufe à Frist vor dem Rückfall waren vier Minuten Warten.
    Ein Anlauf, dann der Verzicht-Weg mit seinen eigenen Anläufen. Ohne Frist
    bleibt alles wie beschrieben (vier schnelle Anläufe).
    """
    if kwargs.get("timeout") is None:
        return _create
    return _create.retry_with(stop=stop_after_attempt(1))


def _create_eu_zuerst(kwargs: dict[str, Any], anbieter: tuple[str, ...],
                      feature: str | None, geduld: bool) -> tuple[Any, bool]:
    """Erst der EU-Weg mit ZDR, bei Ausfall derselbe Aufruf ohne ZDR.

    Gibt ``(Antwort, Rückfall?)`` zurück. Der EU-Weg ist das normale
    ``_create`` mit seinen vier schnellen Anläufen — keine Geduld, auch nicht
    im Batch: Pausen von Minuten vor einem Rückfall helfen niemandem, der auf
    eine Antwort wartet. **Was der EU-Weg im Fehlerfall höchstens kostet:**
    bei einem Fehler, den ``_is_transient`` kennt, 2 + 2 + 4 = 8 s Pause plus
    die Dauer der vier Anläufe (bei einem sofortigen 429 zusammen gut 9 s);
    ein 404 fällt ohne Anlauf sofort zurück (Probe: 0,1 s). Ein Anbieter,
    der gar nicht antwortet, läuft wie heute bis ins Zeitlimit des Clients —
    das gilt für den Verzicht-Weg genauso und ist nicht Teil dieser Änderung.

    Ein 200er ohne ``choices`` fällt auch dann zurück, wenn der Aufrufer
    Leerantworten selbst behandelt (``_allow_empty_response``, die
    Partei-Meinungen): Leer aus der EU heißt „Anbieter gestört“, nicht „das
    Modell hatte nichts zu sagen“. Der zweite Weg behält die Regel des
    Aufrufers.
    """
    eu = {**kwargs, "_zdr": True, "_only": anbieter}
    try:
        resp = _eu_anlauf(kwargs)(**eu)
        if getattr(resp, "choices", None):
            return resp, False
        grund: BaseException = EmptyResponseError(
            f"{kwargs.get('model')}: EU-Antwort ohne choices — {_antwort_fehlertext(resp)}")
    except Exception as exc:  # noqa: BLE001 — was zurückfällt, entscheidet _eu_rueckfall_erlaubt
        if not _eu_rueckfall_erlaubt(exc):
            raise
        grund = exc
    _melde_rueckfall(feature, kwargs.get("model"), grund)
    return (_create_geduldig(kwargs) if geduld else _create(**kwargs)), True


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
    LLM page (stripped before the API call; best-effort). ``_allow_empty_response``
    is reserved for callers that explicitly handle a response without
    ``choices``; the private flag is never sent upstream.

    **Für Batch-Jobs:** ``_geduld=True`` wartet bei vorübergehenden Fehlern
    zusätzlich ``GEDULD_PAUSEN`` (Minuten, nicht Sekunden), und
    ``_ersatz=[…]`` nennt Modelle, auf die der Aufruf ausweicht, wenn das
    gewünschte auch dann nicht antwortet (``ersatz_fuer(MODEL)``). Die
    Kostenzählung trägt das Modell, das wirklich geantwortet hat. Beides ist
    für Cron-Läufe gedacht — eine Web-Anfrage darf nicht minutenlang hängen.

    ``_tarif="flex"`` ruft im Flex-Tarif (halber Preis, s. ``TARIFE``). Nur
    für Features ohne ZDR-Pflicht — sonst ``FlexNichtErlaubt``. Weist der
    Anbieter ab, läuft derselbe Aufruf im normalen Tarif.
    """
    feature = kwargs.pop("_feature", None)
    kwargs["_zdr"] = zdr_pflicht(feature)
    geduld = bool(kwargs.pop("_geduld", False))
    ersatz = list(kwargs.pop("_ersatz", None) or [])
    tarif = kwargs.pop("_tarif", None) or os.environ.get(TARIF_ENV, "").strip() or "normal"
    if tarif not in TARIFE:
        raise ValueError(f"unbekannter Tarif {tarif!r} — erlaubt: {', '.join(TARIFE)}")
    # An `nutzereingabe`, nicht an `zdr_pflicht`: Der ZDR-Verzicht für Lotti
    # und die Antwort (ZDR_VERZICHT) ist keine Freigabe für Flex — das ist ein
    # Cron-Tarif mit Wartezeiten, und Tims Freigabe galt dem Modell, nicht dem
    # Tarif.
    if tarif == "flex" and nutzereingabe(feature):
        raise FlexNichtErlaubt(
            f"Flex für {feature or 'einen Aufruf ohne _feature'!r}: Das Feature trägt "
            "Nutzereingaben, und Flex ist nur für öffentliche Ratsdaten freigegeben.")
    modelle = [kwargs.get("model"), *ersatz]
    for i, model in enumerate(modelle):
        versuch = {**kwargs, "model": model}
        # Flex gibt es für die EU-Features nie (s. o., FlexNichtErlaubt).
        anbieter = eu_zuerst(feature, model) if tarif == "normal" else None
        rueckfall = False
        try:
            if tarif == "flex":
                resp = _create_flex(versuch, geduld)
            elif anbieter:
                resp, rueckfall = _create_eu_zuerst(versuch, anbieter, feature, geduld)
            else:
                resp = _create_geduldig(versuch) if geduld else _create(**versuch)
        except Exception as exc:  # noqa: BLE001 — nur Vorübergehendes wird ersetzt
            if i == len(modelle) - 1 or not _is_transient(exc):
                raise
            print(f"  ⚠️ {model}: {exc!r} — weiche auf {modelle[i + 1]} aus", flush=True)
            continue
        _record_usage(feature, f"{model}{RUECKFALL_MARKE}" if rueckfall else model,
                      getattr(resp, "usage", None))
        _mitschnitt(feature, versuch, _antworttext(resp),
                    antwort_modell=getattr(resp, "model", None),
                    finish_reason=_finish_reason(resp), usage_obj=getattr(resp, "usage", None),
                    anbieter=_anbieter(resp), rueckfall=rueckfall)
        return resp
    raise AssertionError("unerreichbar: kein Modell")  # pragma: no cover


def _create_flex(kwargs: dict[str, Any], geduld: bool):
    """Erst Flex, bei Abweisung derselbe Aufruf im normalen Tarif.

    Wie eine Abweisung aussieht, ließ sich am 22.09.2026 nicht provozieren
    (0 von 24 Aufrufen). OpenAI dokumentiert 429 „Resource Unavailable";
    OpenRouter kann ebenso 404 (kein Endpunkt) oder einen 200er ohne
    ``choices`` liefern. Deshalb fängt der Rückfall jeden Fehler — außer einem
    Inhaltsfilter-Treffer: Der hinge am Text und träfe den normalen Tarif
    genauso. Modelle ganz ohne Flex-Endpunkt (DeepSeek) beantwortet OpenRouter
    ohne Fehler im normalen Tarif; dort gibt es nichts zurückzufallen.
    """
    try:
        return _create(**_flex_kwargs(kwargs))
    except Exception as exc:  # noqa: BLE001 — Rückfall, s. o.
        if is_content_filter(exc):
            raise
        print(f"  ↩️ {kwargs.get('model')}: Flex abgewiesen ({exc!r}) — normaler Tarif",
              flush=True)
    return _create_geduldig(kwargs) if geduld else _create(**kwargs)


def _create_geduldig(kwargs: dict[str, Any]):
    """``_create`` mit langen Pausen dazwischen — für Batch-Jobs.

    Jeder Anlauf hier ist selbst schon die retried Fassung (vier Versuche,
    2–8 s); dazwischen liegen ``GEDULD_PAUSEN``. Nach der letzten Pause fliegt
    der Fehler — ``chat_complete`` greift dann zum Ersatzmodell, falls eins da
    ist.
    """
    for pause in (*GEDULD_PAUSEN, None):
        try:
            return _create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            if pause is None or not _is_transient(exc):
                raise
            print(f"  ⏳ {kwargs.get('model')}: {exc!r} — warte {pause} s", flush=True)
            time.sleep(pause)
    raise AssertionError("unerreichbar")  # pragma: no cover


def chat_stream(**kwargs: Any) -> Iterator[str]:
    """Stream content deltas as they are generated — used for the live "Frag den Rat"
    answer. Same per-model params and connect-time retry as chat_complete. Pass
    ``_feature="…"`` to record token usage (requests the usage chunk; best-effort).
    Yields non-empty text chunks."""
    for art, inhalt in chat_stream_events(**kwargs):
        if art == "text":
            yield inhalt


def _werkzeug_teile(sammel: dict[int, dict], deltas: Any) -> None:
    """Die Teilstücke eines Werkzeugaufrufs zusammensetzen.

    Im Strom kommt ein Aufruf in Scheiben: erst ``id`` und Name, dann die
    Argumente als JSON-Text in mehreren Stücken — zusammengehalten über
    ``index``."""
    for d in deltas or ():
        nr = getattr(d, "index", 0) or 0
        ziel = sammel.setdefault(nr, {"id": "", "name": "", "arguments": ""})
        if getattr(d, "id", None):
            ziel["id"] = d.id
        fn = getattr(d, "function", None)
        if fn is not None:
            if getattr(fn, "name", None):
                ziel["name"] += fn.name
            if getattr(fn, "arguments", None):
                ziel["arguments"] += fn.arguments


def chat_stream_events(**kwargs: Any) -> Generator[tuple[str, Any], None, None]:
    """Wie :func:`chat_stream`, meldet aber auch Werkzeugaufrufe.

    Liefert ``("text", str)`` je Textstück und — am Ende, falls das Modell
    Werkzeuge aufruft — einmal ``("tools", [{id, name, arguments}])``. Lottis
    Nachschlagen (``council/lotti_werkzeuge.py``, 25.09.2026) braucht beides
    im selben Strom: Antwortet das Modell direkt, fließt der Text ohne
    Umweg ans Fenster; ruft es ein Werkzeug, führt der Aufrufer es aus und
    fragt noch einmal. EU-zuerst, Rückfall, Kostenzählung und Mitschnitt
    sind dieselben wie bei ``chat_stream`` — es ist derselbe Code.
    """
    feature = kwargs.pop("_feature", None)
    if feature:
        kwargs.setdefault("stream_options", {"include_usage": True})
    # Der Mitschnitt sammelt nur, wenn der Messschalter gesetzt ist — sonst
    # bleibt der Strom, wie er war.
    mit = bool(os.environ.get(MITSCHNITT_ENV, "").strip())
    teile: list[str] = []
    werkzeuge: dict[int, dict] = {}
    antwort_modell: str | None = None
    antwort_anbieter: str | None = None
    grund: str | None = None
    verbrauch: Any = None
    fertig = False
    # Die Wege, der Reihe nach: für die EU-Features (EU_ZUERST) erst EU mit
    # ZDR, dann das Verzicht-Routing — sonst nur der eine Weg wie bisher.
    anbieter = eu_zuerst(feature, kwargs.get("model"))
    wege: list[tuple[bool, tuple[str, ...] | None]] = (
        [(True, anbieter), (False, None)] if anbieter else [(zdr_pflicht(feature), None)])
    rueckfall = False
    try:
        for nr, (zdr, only) in enumerate(wege):
            ausgeliefert = False
            try:
                erzeugen = _eu_anlauf(kwargs) if only else _create
                for chunk in erzeugen(stream=True, _zdr=zdr, _only=only, **kwargs):
                    if antwort_anbieter is None:
                        antwort_anbieter = _anbieter(chunk)
                    if mit and antwort_modell is None:
                        antwort_modell = getattr(chunk, "model", None)
                    if getattr(chunk, "usage", None):
                        verbrauch = chunk.usage
                        modell = kwargs.get("model")
                        _record_usage(feature, f"{modell}{RUECKFALL_MARKE}" if rueckfall else modell,
                                      chunk.usage)
                    if mit and chunk.choices and getattr(chunk.choices[0], "finish_reason", None):
                        grund = chunk.choices[0].finish_reason
                    if chunk.choices and getattr(chunk.choices[0].delta, "tool_calls", None):
                        _werkzeug_teile(werkzeuge, chunk.choices[0].delta.tool_calls)
                    if chunk.choices and chunk.choices[0].delta.content:
                        if mit:
                            teile.append(chunk.choices[0].delta.content)
                        ausgeliefert = True
                        yield ("text", chunk.choices[0].delta.content)
            except Exception as exc:  # noqa: BLE001 — Rückfall nur vor dem ersten Token
                # Ist schon Text beim Leser, hieße ein zweiter Weg eine zweite,
                # andere Antwort im selben Fenster. Dann reißt der Strom wie
                # bisher, und der Router erzeugt einmal neu (chat_complete —
                # das seinerseits wieder EU zuerst versucht).
                if ausgeliefert or nr == len(wege) - 1 or not _eu_rueckfall_erlaubt(exc):
                    raise
                _melde_rueckfall(feature, kwargs.get("model"), exc)
                rueckfall = True
                antwort_anbieter = antwort_modell = None
                werkzeuge.clear()
                continue
            break
        fertig = True
        if werkzeuge:
            yield ("tools", [werkzeuge[i] for i in sorted(werkzeuge)])
    finally:
        # Auch ein abgerissener Strom wird festgehalten: Der Router erzeugt
        # dann einmal neu (`chat_complete`, eigene Zeile), und die Eval muss
        # sehen, dass es zwei Aufrufe waren.
        if mit:
            _mitschnitt(feature, kwargs, "".join(teile), antwort_modell=antwort_modell,
                        abgebrochen=not fertig, finish_reason=grund, usage_obj=verbrauch,
                        anbieter=antwort_anbieter, rueckfall=rueckfall)
