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

## Nachtrag 23.09.2026: ZDR-Verzicht für Lotti und „Frag den Rat“

**Entscheidung (Tim):** Lotti und die Antwort von „Frag den Rat“ laufen auf
GPT-6 Luna, „auch wenn die kein Zero Data Retention haben — das ist
wenigstens kein chinesischer Anbieter“. Anlass war ein Faktencheck an 14
echten Antworten, Aussage für Aussage gegen Kontext und Datenbank: GPT-6
Luna in 12 von 14 fehlerfrei, Gemini 2.5 Flash (das bisherige Modell, bei
OpenRouter ab 20.10.2026 abgeschaltet) in 5 von 14. GPT-6 Luna bieten nur
OpenAI direkt und Amazon Bedrock an, beide ohne ZDR.

Umgesetzt als **benannte Ausnahme**, nicht als Lockerung:
`kern/llm.py::ZDR_VERZICHT` nennt genau die Features, die diese beiden
Modelle lesen (`assistant_explain`, `qa_answer`, `qa_simple`, `deep_report`,
`party_opinions`). Alles andere mit Nutzereingabe — die Frage-Analyse vor der
Suche, der Watcher, die Themen-Beschreibung, die Vagheits-Prüfung und jeder
Aufruf ohne `_feature` — behält ZDR. Für die Ausnahme gelten weiter
`data_collection: deny` und der China-Ausschluss, und sie gibt **nicht** den
Flex-Tarif frei (der hängt an `llm.nutzereingabe`, nicht an der ZDR-Pflicht).
`tests/test_llm.py` hält alle drei Punkte fest. Die Datenschutzerklärung nennt
seitdem Lotti ausdrücklich und sagt, dass für dieses Modell keine ZDR-Zusage
besteht.

Dazu kommt eine Schutzschicht, die nicht vom Anbieter abhängt:
`kern/foreign_text.py` nimmt Sätze aus Seiten- und Vorlagentext heraus, die
sich an ein KI-System wenden, bevor Lotti oder die Antwort sie sehen.

## Nachtrag 23.09.2026: erst Azure EU mit ZDR, OpenAI nur als Rückfall

Am selben Tag hat OpenRouter GPT-6 Luna auch bei Microsoft Azure
aufgenommen, darunter den Endpunkt `azure/eu` mit ZDR. Gemessen mit
`zdr: true`, `data_collection: deny` und `only: ["azure/eu"]`: 20 von 20
Aufrufen ok, p50 3,4 s. Ohne die feste Anbietervorgabe kam einmal
„temporarily rate-limited upstream“.

**Entscheidung (Tim):** Für die Features aus `ZDR_VERZICHT` geht der erste
Versuch an `azure/eu`, mit ZDR, Trainingsverbot und China-Liste. Fällt
dieser Weg aus, läuft derselbe Aufruf einmal mit dem Routing aus dem
vorigen Nachtrag, also ohne ZDR (in der Regel OpenAI direkt, USA). Der
Verzicht gilt damit nur noch für den Rückfall.

- **Welche Modelle:** `kern/llm.py::EU_ZUERST` nennt sie, GPT-6 Luna und
  GPT-6 Sol. Beide haben `azure/eu`, geprüft am 23.09. Für ein Modell ohne
  Eintrag bleibt das bisherige Routing. Ein EU-Versuch dort wäre ein
  sicherer 404, und jeder Aufruf würde als Rückfall gezählt.
- **Wann zurückgefallen wird:** bei allem, was `_is_transient` als
  vorübergehend kennt (429, 5xx, Netz, 200er ohne `choices`), bei einem 404
  und bei einem Fehler-Ereignis im Strom. **Nicht** bei einem
  Inhaltsfilter-Treffer. Der hängt am Text, und ein Rückfall schickte genau
  diesen Text in die USA. Im Strom wird nur zurückgefallen, solange noch
  kein Token beim Leser ist.
- **Was der erste Weg im Fehlerfall kostet:** Er ist das normale `_create`
  mit vier schnellen Anläufen, ohne Geduld. Bei einem vorübergehenden
  Fehler sind das 2 + 2 + 4 = 8 s Pause plus die Anläufe selbst, bei einem
  sofortigen 429 zusammen gut 9 s. Ein 404 fällt ohne Anlauf zurück
  (gemessen 0,1 s).
- **Gezählt:** Ein Rückfall steht in `llm_usage` unter dem Modellnamen mit
  `@fallback-no-zdr`. Im Admin-Panel (*LLM-Kosten*) steht er damit als
  eigenes Modell des Features, mit Zahl der Aufrufe und Kosten. Dazu kommt
  eine Zeile im Dienst-Log. Wie oft Anfragen die EU
  verlassen haben, zeigt
  `SELECT feature, COUNT(*) FROM llm_usage WHERE model LIKE '%@fallback-no-zdr' GROUP BY feature`.
- **Preis:** `azure/eu` kostet 10 % mehr als OpenAI direkt (0,11 statt
  0,10 $ je Million Eingabe-Tokens).
- **Gemessen** mit der Fakten-Eval (`eval/run_fakten.py`, alle 233 Fälle,
  GPT-6 Luna, 23.09.2026). Beide Läufe liefen gleichzeitig, einer mit dem
  alten Routing, einer mit dem neuen. Qualität gleich: vorher 177 ok und
  34 Modellfehler, nachher 176 ok und 37 Modellfehler. Das liegt in der
  Streuung, ein früherer Lauf mit dem alten Routing hatte ebenfalls 176 und
  37. Es waren dieselben Gewichte und derselbe Denkaufwand. Schneller wurde
  es trotzdem: p50 6,7 s statt 8,7 s, p95 17,7 s statt 28,4 s. Bei Lotti
  sank der p50 von 6,0 auf 4,2 s, bei Frag den Rat von 13,6 auf 9,0 s.
  Rückfälle im Lauf: 0 von 236 Luna-Aufrufen, alle gingen an Azure.

Die Datenschutzerklärung sagt seitdem: im Regelfall EU ohne Speicherung,
bei einer Störung ausnahmsweise OpenAI in den USA ohne diese Zusage.
