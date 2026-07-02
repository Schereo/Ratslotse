---
title: 0006 — Zwei-Pass-Klassifikation
description: Breiter Sammel-Pass plus paarweiser Verifier für hohe Precision.
sidebar:
  order: 6
---

**Status:** Akzeptiert

## Kontext

Der NWZ-Digest soll Artikel zu Nutzerthemen matchen — mit **hoher Precision**
(keine Fehltreffer, sonst verliert der Nutzer Vertrauen) bei brauchbarem Recall.
Ein einzelner breiter LLM-Call über alle Themen × alle Artikel über-matched
systematisch: breite Themen ziehen Artikel über reine Stichwort-Überschneidung an
(z. B. ein Parteiname, der nur am Rand fällt).

## Entscheidung

Eine **zweistufige** Klassifikation (`nwz/classify.py`):

1. **Pass 1 — Sammeln (breit):** Ein einziger `gpt-4o`-Call über alle Themen ×
   alle Artikel (Text je auf ~900 Zeichen gekürzt), `temperature=0`, JSON-Mode.
   Liefert Kandidatenpaare. Optimiert auf Recall.
2. **Pass 2 — Verifizieren (scharf):** Für **jedes** Kandidatenpaar (Thema,
   Artikel) ein eigener `gpt-4o-mini`-Call (Text bis ~1500 Zeichen), der nur
   `{"relevant": bool}` zurückgibt. Filtert die Über-Matches von Pass 1 heraus.

Bei JSON-Parse-Fehlern im Verifier wird der Match **behalten** (fail-open) —
schützt Recall.

## Konsequenzen

- **Plus:** Deutlich höhere Precision als ein Einzel-Call, ohne Recall stark zu
  opfern. Das billige `gpt-4o-mini` trägt den teuren N-fachen Verify-Schritt.
- **Plus:** Klare Trennung der Verantwortlichkeiten — Pass 1 „findet", Pass 2
  „entscheidet".
- **Minus:** Pass 2 macht **N Einzel-Calls** (ein Call pro Paar) — der größte
  Kostentreiber der Pipeline. Batching/Caching sind als Optimierung notiert (siehe
  [KI-Pipeline](/docs/ki-pipeline/) → Roadmap).
- **Minus:** fail-open kann einzelne Fehltreffer durchlassen, wenn der Verifier
  ungültiges JSON liefert.
