---
title: Architekturentscheidungen (ADRs)
description: Technische Entscheidungen des Projekts mit Kontext und Begründung.
sidebar:
  order: 0
---

Ein **Architecture Decision Record** (ADR) dokumentiert eine technische
Entscheidung mit ihrem Kontext und ihren Konsequenzen. So bleibt die
Begründung auch für spätere Mitwirkende nachvollziehbar.

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
| [0009](/docs/adr/0009-zentraler-ortskatalog/) | Zentraler Ortskatalog statt vermeintlich amtlicher Stadtteile | Akzeptiert |
| [0010](/docs/adr/0010-doku-aus-dem-code/) | Doku aus dem Code erzeugen und gegen ihn prüfen | Akzeptiert |

> Lege für eine neue Entscheidung eine Datei `NNNN-kurz-titel.md` nach
> diesem Schema an und ergänze die Tabelle. Überholte ADRs bleiben mit
> dem Status „Ersetzt durch …" erhalten.
