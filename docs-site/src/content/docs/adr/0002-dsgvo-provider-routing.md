---
title: 0002 — DSGVO-Provider-Routing
description: China-Anbieter ausschließen und Zero-Data-Retention erzwingen.
sidebar:
  order: 2
---

**Status:** Akzeptiert

## Kontext

OpenRouter routet Anfragen dynamisch an wechselnde Upstream-Anbieter. Für ein
deutsches Produkt mit lokalpolitischen Inhalten ist das ein Datenschutzrisiko:
Anfragen könnten an Anbieter außerhalb der DSGVO-Reichweite (z. B. in China)
gehen oder bei Anbietern landen, die Eingaben zum Training speichern.

## Entscheidung

`nwz/llm.py` setzt ein **Provider-Routing** durch (per Env steuerbar):

- `NWZ_OPENROUTER_IGNORE` schließt bestimmte Anbieter-Slugs aus
  (Default: `deepseek,baidu,streamlake,siliconflow,alibaba`).
- `NWZ_OPENROUTER_ZDR=1` verlangt **Zero Data Retention** (keine Speicherung/kein
  Training auf den Daten).
- `NWZ_OPENROUTER_ROUTING=off` ist ein Notausschalter, der den Block komplett
  deaktiviert.

## Konsequenzen

- **Plus:** KI-Anfragen gehen nicht an ausgeschlossene Anbieter; ZDR reduziert das
  Risiko, dass Inhalte gespeichert oder zum Training genutzt werden.
- **Plus:** Über Env steuerbar — kein Code-Deploy nötig, um auf Anbieter-
  Änderungen zu reagieren.
- **Minus:** Die Anbieter-Auswahl schrumpft, was Verfügbarkeit/Preis verschlechtern
  kann. Der Ausschluss per Slug muss gepflegt werden, wenn neue Anbieter
  dazukommen.
- **Hinweis:** Die DeepSeek-Modelle, die als *Defaults* der Protokoll-Pipelines
  konfiguriert sind, werden über OpenRouter bei DSGVO-konformen Hostern geroutet —
  der Ausschluss betrifft den Anbieter-Slug `deepseek` (direktes Hosting), nicht
  das Modellgewicht als solches. Beim Tunen beider Stellschrauben aufeinander achten.
