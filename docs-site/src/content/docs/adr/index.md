---
title: Architekturentscheidungen (ADRs)
description: Die wichtigen Technik-Weichen des Projekts und warum sie so gestellt wurden.
sidebar:
  order: 0
---

Ein **Architecture Decision Record** (ADR) hält eine einzelne, folgenreiche
technische Entscheidung fest: den Kontext, die getroffene Wahl und die
Konsequenzen. Ziel ist, dass spätere Mitlesende (oder das eigene Ich in sechs
Monaten) das *Warum* nachvollziehen können — nicht nur das *Was*.

Jeder Eintrag folgt dem Schema **Status · Kontext · Entscheidung · Konsequenzen**.

| # | Entscheidung | Status |
|---|--------------|--------|
| [0001](/docs/adr/0001-openrouter/) | OpenRouter statt direkter OpenAI-API | Akzeptiert |
| [0002](/docs/adr/0002-dsgvo-provider-routing/) | DSGVO-Provider-Routing (China-Ausschluss + ZDR) | Akzeptiert |
| [0003](/docs/adr/0003-fastembed-statt-torch/) | fastembed (ONNX) statt torch für Embeddings | Akzeptiert |
| [0004](/docs/adr/0004-caddy-statt-nginx/) | Caddy auf der Edge-VM statt lokalem nginx | Akzeptiert |
| [0005](/docs/adr/0005-sqlite-fts5/) | SQLite + FTS5 als einzige Datenbank | Akzeptiert |
| [0007](/docs/adr/0007-long-polling/) | Long-Polling statt Webhook für den Bot | Abgelöst |
| [0008](/docs/adr/0008-deploy-nur-bei-merge/) | Deploy nur bei gemergtem PR | Akzeptiert |

> Neue Entscheidung? Neue Datei `NNNN-kurz-titel.md` mit demselben Schema und
> einer Zeile in dieser Tabelle. ADRs werden nicht gelöscht — überholte werden
> auf „Ersetzt durch …" gesetzt.
