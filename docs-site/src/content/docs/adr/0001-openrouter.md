---
title: 0001 — OpenRouter statt direkter OpenAI-API
description: Warum alle LLM-Calls über OpenRouter statt direkt gegen OpenAI laufen.
sidebar:
  order: 1
---

**Status:** Akzeptiert

## Kontext

Die App braucht LLM-Inferenz an mehreren Stellen (NWZ-Digest, Ausschuss-
Zusammenfassung, Topic-Matching, Protokoll-Extraktion). Anforderungen:

- Modelle frei wählbar und pro Aufgabe austauschbar, ohne Code-Umbau.
- Kostenkontrolle und die Option, je Task ein günstigeres Modell zu nutzen.
- DSGVO-konformes Provider-Routing (siehe [ADR 0002](/docs/adr/0002-dsgvo-provider-routing/)).
- Kein Lock-in auf einen einzelnen Anbieter.

## Entscheidung

Alle LLM-Aufrufe laufen über **OpenRouter** mit dem offiziellen `openai`-SDK
(`base_url` auf den OpenRouter-Endpunkt, `OPENROUTER_API_KEY`). Modellnamen sind
über Env-Variablen konfigurierbar (`COUNCIL_PROTOCOL_MODEL`, `COUNCIL_TOPIC_MODEL`,
…), Defaults greifen ohne Konfiguration.

## Konsequenzen

- **Plus:** Ein einziger Key, ein SDK, viele Modelle. Modellwechsel ist eine
  Env-Änderung, kein Deploy von Code. Provider-Routing-Regeln (ADR 0002) lassen
  sich zentral durchsetzen.
- **Plus:** Der Modellvergleich (siehe [Modellvergleich](/docs/modellvergleich/))
  konnte ohne Integrationsaufwand mehrere Anbieter gegeneinander testen.
- **Minus:** Zusätzliche Abhängigkeit von OpenRouter als Vermittler (eine weitere
  Ausfall-/Latenzquelle). Einige OpenAI-spezifische Features (z. B. strikte
  JSON-Schema-Outputs) sind je nach geroutetem Anbieter nicht garantiert — die
  Pipeline nutzt daher nur den breit unterstützten JSON-Mode.
