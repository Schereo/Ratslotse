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

`kern/llm.py` setzt ein **Provider-Routing** durch (per Env steuerbar):

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

## Nachtrag 22.09.2026: ZDR nur, wo Nutzereingaben im Prompt stehen

Die ZDR-Pflicht galt bis hierhin für jeden Aufruf. Sie schützt aber nur
etwas, wenn der Prompt Text enthält, den eine Nutzerin selbst geschrieben
hat — eine Frage, ein Thema, Lottis Seitenkontext. Die meisten Crons lesen
ausschließlich öffentliche Ratsdokumente.

Anlass war ein gemessener Ausschluss: GPT-6 Luna bieten bisher nur OpenAI
direkt und Amazon Bedrock an, beide ohne ZDR; jeder Aufruf endete mit 404.
Dasselbe gilt für OpenAIs Flex-Tarif.

**Entscheidung (Tim):** Features, die nur öffentliche Daten verarbeiten,
dürfen an Anbieter ohne ZDR. Sie stehen einzeln in
`kern/llm.py::OHNE_NUTZEREINGABE` (dazu alle `cities_*`-Annotatoren). Die
Liste ist eine **Freigabe**: Ein Feature, das dort fehlt — auch ein Aufruf
ohne `_feature` —, bleibt bei ZDR. `data_collection: deny` (kein Training)
und der China-Ausschluss gelten für **alle** Aufrufe unverändert.
`tests/test_llm.py` hält fest, dass die Nutzer-Pfade (KI-Frage, Deep, Lotti,
Themen-Beschreibung, Vagheits-Prüfung) nie in der Liste landen.

## Nachtrag 22.09.2026: Flex- und Batch-Tarif

Beide Tarife kosten die Hälfte, und **beide vertragen sich nicht mit ZDR**.
Gemessen am 22.09.2026; die Einzelheiten stehen in `docs/modell-batch-flex.md`
im Repo.

- **Flex** (`service_tier: "flex"`): Flex-Endpunkte haben kein ZDR. Mit
  `zdr: true` ignoriert OpenRouter den Tarif still (voller Preis) oder findet
  keinen Endpunkt. `llm.chat_complete(_tarif="flex")` nimmt deshalb **nur**
  `zdr` aus dem Routing-Block. `data_collection: deny` und die China-Liste
  bleiben. Erlaubt ist das nur für Features aus `OHNE_NUTZEREINGABE`; bei allen
  anderen (auch ohne `_feature`) bricht der Aufruf mit einem
  Fehler ab. Nutzerpfade (KI-Frage, Lotti, Themen, Watcher) erreichen den
  Flex-Tarif also nie.
- **Batch** (`/api/v1/batches`): Die Schnittstelle nimmt nur `provider.only`
  an. `data_collection`, `ignore` und `zdr` weist sie mit 400 ab. Die
  China-Sperre ginge also nur als Positivliste. Eingaben und Ergebnisse
  liegen 30 Tage bei OpenRouter (Google Cloud Storage), außer man löscht
  den Stapel. Beim Upstream-Anbieter OpenAI ist das Löschen „unsupported“.
  Deshalb wird Batch derzeit nicht verwendet.
