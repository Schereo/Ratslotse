---
title: 0001 — OpenRouter statt direkter OpenAI-API
description: Gründe für den zentralen LLM-Zugriff über OpenRouter.
sidebar:
  order: 1
---

**Status:** Akzeptiert

## Kontext

Die App nutzt LLMs für Ausschusszusammenfassungen, Themenabgleich und
die Extraktion von Beschlüssen aus Protokollen. Der Zugriff muss die
folgenden Anforderungen erfüllen.

- Modelle frei wählbar und pro Aufgabe austauschbar, ohne Code-Umbau.
- Kostenkontrolle und die Option, je Task ein günstigeres Modell zu nutzen.
- DSGVO-konformes Provider-Routing (siehe [ADR 0002](/docs/adr/0002-dsgvo-provider-routing/)).
- Kein Lock-in auf einen einzelnen Anbieter.

## Entscheidung

Alle LLM-Aufrufe laufen über **OpenRouter** mit dem offiziellen `openai`-SDK
(`base_url` auf den OpenRouter-Endpunkt, `OPENROUTER_API_KEY`). Modellnamen sind
über Umgebungsvariablen konfigurierbar (`COUNCIL_PROTOCOL_MODEL`,
`COUNCIL_TOPIC_MODEL`, …). Ohne Konfiguration gelten die Standardwerte.

## Konsequenzen

- **Plus:** Ein API-Key und ein SDK genügen für mehrere Modelle. Ein
  Modellwechsel erfordert nur eine Änderung der Umgebungsvariable. Die
  Regeln für das Provider-Routing (ADR 0002) gelten zentral.
- **Plus:** Ein Modellvergleich
  konnte ohne Integrationsaufwand mehrere Anbieter gegeneinander testen.
- **Minus:** Zusätzliche Abhängigkeit von OpenRouter als Vermittler (eine weitere
  mögliche Quelle für Ausfälle und zusätzliche Latenz). Manche
  OpenAI-spezifischen Funktionen wie Ausgaben mit striktem JSON-Schema
  hängen vom Anbieter ab. Die Pipeline nutzt daher nur den breit
  unterstützten JSON-Mode.
