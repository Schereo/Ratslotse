# Vortrag: Ratslotse

Eine Präsentation über Ratslotse für Gespräche mit Hochschulen, Verwaltungen
oder anderen Städten: wie das Projekt entstanden ist, wie die KI antwortet
(RAG), was Daten, Antwortqualität, Datenschutz und Recht im Alltag verlangen
und was sich auf andere Städte übertragen lässt. Erstmals gehalten am
26.11.2026, danach von allem befreit, was nur zu diesem Termin gehörte.

## Öffnen und vortragen

`index.html` im Browser öffnen. Es braucht Internet: reveal.js 5.1.0 und die
Schriften kommen vom CDN.

| Taste | Wirkung |
|---|---|
| → / ← | blättern, auf manchen Folien Schritt für Schritt |
| S | Sprechernotizen im eigenen Fenster |
| Esc | Übersicht aller Folien |
| F | Vollbild |

Die Folien tragen Stichworte, die Erklärungen stehen in den Sprechernotizen,
dazu jeweils, woher eine Zahl kommt.

## Zahlen nachziehen

Die Zahlen stehen fest im HTML und sind ein Stand vom 23. bis 26.11.2026.
Wer den Vortrag später wieder hält, sollte sie vorher nachziehen:

| Folie | Zahl | Quelle |
|---|---|---|
| Die Idee | Sitzungen, Vorlagen, Anlagen, Beschlüsse, Wortbeiträge, Pressemitteilungen | `council.sqlite`: `council_sessions`, `council_templates`, `council_attachments`, `council_decisions`, `council_speeches`, `council_press` |
| Wie Ratslotse gewachsen ist | Versionen, Änderungen | `CHANGELOG.md`, `git rev-list --count HEAD` |
| Was das möglich gemacht hat | KI-Kosten im Monat, je Frage | `llm_usage` in `ratslotse.sqlite` auf Prod, nur lesend |
| Messen statt schätzen | 62 %, Faktencheck 12/14 | [`docs/gold-messbuch.md`](../gold-messbuch.md), [ADR 0002](../../docs-site/src/content/docs/adr/0002-dsgvo-provider-routing.md) |
| Übertragbar auf andere Städte? | OParl 162 offen / 141 abgeschaltet | eigene Erhebung vom 10.09.2026 |

Für die Kosten zählen nur die Kernfunktionen: alles außer `cities_*`,
`quality_judge`, `live_top_tracker`, `qa_belegnotizen` und `social_*`. Je
Frage heißt: Summe der Fragen-Features (`qa_*`, `party_opinions`, `deep_*`)
geteilt durch die Zahl der `qa_analysis`-Aufrufe, weil `llm_usage` keine
Anfrage-Kennung kennt. Die Anbieter rechnen in Dollar; umgerechnet wurde mit
1 $ ≈ 0,90 €.

## Bilder

`img/` enthält die Lotti-Standbilder und die Marke aus `web/frontend/public/`,
ein Standbild aus dem Release-Clip `neuigkeiten/3.0.0/akte.mp4` und einen
Screenshot der Vorlage 22/0905 im Ratsinformationssystem der Stadt.

Farben, Schriften und Bausteine folgen
[`web/frontend/DESIGNSPRACHE.md`](../../web/frontend/DESIGNSPRACHE.md).
