---
title: KI-Pipeline
description: Wie das Ratsinfo-Matching und die Beschluss-Aufbereitung per LLM funktionieren.
---

> Stand: 2026-07. Dieses Dokument beschreibt die KI-gestützten Schritte rund um das
> **Ratsinformationssystem** (Oldenburger Stadtrat): Ausschuss-Zusammenfassungen,
> Themen-Matching (Watcher) und die Beschluss-Aufbereitung. Alles läuft über
> **OpenRouter** (OpenAI-SDK).

---

## 1. Überblick

Die Pipeline-Qualität entscheidet über den Produktwert: Sie bestimmt, wie zuverlässig
relevante Tagesordnungspunkte und Beschlüsse zu den Themen der Nutzer gefunden werden —
bei hoher **Precision** (keine Fehltreffer) *und* brauchbarer **Recall**.

Wichtig vorab: **Das Scraping selbst nutzt kein LLM.** Tagesordnungen und Protokolle
werden per BeautifulSoup aus dem HTML des Bürgerinfo-Portals geparst
(`council/scraper.py`, `council/protocols.py`). Das LLM kommt **erst beim Matching,
Zusammenfassen und Klassifizieren** zum Einsatz, nicht bei der Strukturextraktion.

| Pipeline | Quelle | Trigger |
|----------|--------|---------|
| **Ausschuss-Zusammenfassung** | Tagesordnungen | `check_committees.py` (07:00) |
| **Watcher (Themen-Matching)** | Tagesordnungen | `check_council.py` (08:00, 14:00) |
| **Protokoll-Extraktion + Beschluss-Klassifikation** | Sitzungsprotokolle | `check_protocols.py` (09:00) |
| **Wöchentliche Anreicherung** (Entitäten, Embeddings, Themenfeld-Rückblicke) | Beschlüsse | `weekly_enrich.py` (So 03:00) |

---

## 2. Ausschuss-Zusammenfassungen (`check_committees.py`, 07:00)

- Ausschussliste aktualisieren, kommende Sitzungen (3 Monate voraus) scannen.
- Pro Sitzung mit Tagesordnung: **SHA-256-Hash der Agenda** (`_agenda_hash`) →
  dient Caching *und* Änderungserkennung (neue vs. geänderte Tagesordnung).
- `summarize_agenda()` (`council/committee_summary.py`): filtert Routine-TOPs +
  „Fragestunde" bereits **im Code** vor, dann das LLM (JSON-Mode).
  Ergebnis wird per `CouncilStore.save_summary(ksinr, agenda_hash, summary)`
  **gecacht** — der zentrale LLM-Output-Cache der App.

## 3. Watcher / Themen-Matching (`check_council.py`, 08:00 & 14:00)

- Pro Nutzer `run_watcher(...)` (`council/watcher.py`); klassifiziert nur
  **zukünftige** Sitzungen mit Agenda, die noch nicht gesehen wurden.
- `_classify_agenda()`: öffentliche TOPs + nummerierte Themenliste → LLM (JSON-Mode).
  Liefert `{"matches":[{topic_index, item_numbers}]}`. Alerts werden dedupliziert.
- Der Prompt liegt in `nwz/prompts.py` (`council_watcher_*`) und ist über das
  Admin-UI editierbar.

## 4. Protokolle & Beschluss-Klassifikation (`check_protocols.py`, 09:00)

- Neu veröffentlichte Sitzungsprotokolle parsen (`council/protocols.py`), Beschlüsse
  extrahieren und je Beschluss per LLM in **Themenfelder** einordnen
  (`classify_decisions.py`). Grundlage für Filter, Analyse und die Themenfeld-Rückblicke.

## 5. Wöchentliche Anreicherung (`weekly_enrich.py`, So 03:00)

Zieht die schwereren LLM-/Embedding-Backfills nach, damit Themen-Seiten, Karten und
„Ähnliche Beschlüsse" frisch bleiben: Entitäten-Extraktion → Beschreibungen → Geocoding
→ Embeddings/Ähnliche → Themen↔Beschlüsse-Matching → Themenfeld-Rückblicke.

---

## 6. LLM-Integration

| Aspekt | Status |
|--------|--------|
| Provider | OpenRouter via `openai`-SDK, mit DSGVO-Provider-Routing (s. ADR 0002) |
| Structured Output | JSON-Mode (`response_format={"type":"json_object"}`) |
| Caching | Ausschuss-Zusammenfassungen per Agenda-Hash |
| Prompts | zentral in `nwz/prompts.py`, admin-editierbar (DB-Overrides über Defaults) |

---

## 7. Evaluation

Das Eval-Harness (`eval/harness.py` + Runner, `eval/README.md`) misst die
Ratsinfo-Suiten:

- **`watcher`** — Tagesordnung → Thema (mengenbasiertes Precision/Recall/F1-Scoring
  über `(Thema, TOP)`-Paare).
- **`committee`** — der Routine-Filter der Ausschuss-Zusammenfassungen.

`python eval/run_all.py` liefert ein Scoreboard; `--save`/`--compare` ermöglichen
Baseline-Tracking pro Suite.

---

## 8. Bekannte Verbesserungspunkte

1. **Kein Schema-Enforcement** → JSON-Mode garantiert nur *gültiges JSON*, nicht die
   *erwartete Struktur*. Pydantic-Validierung + einmaliger Retry bei Schema-Verletzung
   würde stille Fehler eliminieren.
2. **Keine Retries/Backoff** → ein transienter OpenRouter-/Rate-Limit-Fehler kann einen
   Cron-Lauf crashen. Ein zentraler `nwz/llm.py`-Helper mit `tenacity`-Retry würde das
   beheben.
3. **Eval-Baseline** → Live-Baseline pro Suite einchecken (braucht `OPENROUTER_API_KEY`)
   und Fälle aus echten False Positives/Negatives wachsen lassen.

---

## Quellen (Best-Practice-Recherche)

- [A Guide to LLM Evals — ByteByteGo](https://blog.bytebytego.com/p/a-guide-to-llm-evals)
- [LLM-as-a-judge: a complete guide — Evidently AI](https://www.evidentlyai.com/llm-guide/llm-as-a-judge)
- [Multi-stage LLM Pipelines Can Outperform GPT-4o in Relevance Assessment (arXiv 2501.14296)](https://arxiv.org/pdf/2501.14296)
- [PARSE: LLM-Driven Schema Optimization for Reliable Entity Extraction (arXiv 2510.08623)](https://arxiv.org/pdf/2510.08623)
