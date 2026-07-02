---
title: 0008 — Deploy nur bei gemergtem PR
description: Ausgeliefert wird nur über einen gemergten Pull Request, nicht per Push.
sidebar:
  order: 8
---

**Status:** Akzeptiert

## Kontext

Ein direkter Deploy bei jedem Push auf `main` ist riskant: ein schneller Fix-Push
kann ungetestet auf prod landen. Gleichzeitig sollen Tests bei jedem Push laufen,
damit Regressionen früh auffallen.

## Entscheidung

Die Deploy-Action (`.github/workflows/deploy.yml`) triggert auf
`pull_request: types:[closed]` mit der Bedingung `merged == true`. Das heißt:

- **Nur ein gemergter Pull Request nach `main`** löst den Deploy aus (rsync der
  Dateien auf `app-server`, Service-Restarts, Frontend-Build).
- Ein **direkter Push auf `main` deployt nicht** — er läuft nur durch die Tests
  (`test.yml`).

Der reguläre Weg ist also immer: **Branch → PR → Merge.**

## Konsequenzen

- **Plus:** Jeder Deploy ging durch einen PR (CI-Tests + Möglichkeit zum Review).
  Kein versehentliches Ausliefern per Hotfix-Push.
- **Plus:** Der PR-Merge ist ein klarer, auditierbarer Auslöser; die
  CHANGELOG-/PR-Nummern bilden die Deploy-Historie ab.
- **Minus:** Ein echter Notfall-Hotfix braucht trotzdem einen (ggf. kleinen) PR —
  es gibt keinen „Push und sofort live"-Pfad. Bewusst in Kauf genommen.
- Beim rsync ausgespart: `.env`, `data/`, `.venv/`, Frontend-`node_modules`/`.next`.
