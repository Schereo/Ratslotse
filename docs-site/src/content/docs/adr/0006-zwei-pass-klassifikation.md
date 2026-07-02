---
title: 0006 — Zwei-Pass-Klassifikation (überholt)
description: Historisch — die zweistufige NWZ-Artikel-Klassifikation wurde mit dem NWZ-Feature ausgegliedert.
sidebar:
  order: 6
  badge: Überholt
---

**Status:** Überholt (2026-07)

## Kontext

Diese Entscheidung betraf die frühere **NWZ-Zeitungs-Integration**: eine
zweistufige LLM-Klassifikation (breiter Sammel-Pass + paarweiser Verifier), um
Zeitungsartikel mit hoher Precision auf Nutzerthemen zu matchen.

## Warum überholt

Die NWZ-Integration (Scraping der Artikel und deren KI-Klassifikation) wurde aus
rechtlichen Gründen aus diesem Repository entfernt und in ein separates, privates
Repository ausgegliedert. Im Produkt bleibt nur ein **scraping-freier
NWZonline-Suchlink** zu Beschluss-Themen.

Das Muster selbst — breiter Recall-Pass, dann scharfer paarweiser Verifier — bleibt
als allgemeines Klassifikationsmuster gültig; im aktuellen Repo wird es aber nicht
mehr eingesetzt. Die verbleibenden LLM-Schritte (Ausschuss-Zusammenfassung,
Themen-Watcher, Beschluss-Klassifikation) sind in [KI-Pipeline](/docs/ki-pipeline/)
beschrieben.
