---
title: 0008 — Deploy nur bei gemergtem PR
description: Merge eines Pull Requests als regulärer Auslöser für den Produktionsdeploy.
sidebar:
  order: 8
---

**Status:** Akzeptiert

## Kontext

Wenn jeder Push auf `main` einen Deploy auslöst, kann ein kurzfristiger
Fix ungetestet in die Produktionsumgebung gelangen. Tests sollen
weiterhin bei jedem Push laufen, damit Regressionen früh auffallen.

## Entscheidung

Der Deploy-Workflow (`.github/workflows/deploy.yml`) reagiert auf
`pull_request: types:[closed]` und prüft die Bedingung `merged == true`.

- **Nur ein gemergter Pull Request nach `main`** löst den Deploy aus (rsync der
  Dateien auf `app-server`, Service-Restarts, Frontend-Build).
- Ein direkter Push auf `main` startet nur die Tests (`test.yml`).

Der reguläre Weg ist also immer: **Branch → PR → Merge.**

## Konsequenzen

- **Plus:** Jeder Deploy ging durch einen PR (CI-Tests + Möglichkeit zum Review).
  Kein versehentliches Ausliefern per Hotfix-Push.
- **Plus:** Der PR-Merge ist ein klarer, auditierbarer Auslöser; die
  CHANGELOG-/PR-Nummern bilden die Deploy-Historie ab.
- **Minus:** Auch ein dringender Hotfix braucht einen Pull Request,
  der entsprechend klein ausfallen kann. Ein direkter Push scheidet
  für die Veröffentlichung aus. Das ist Teil der Entscheidung.
- Beim rsync ausgespart: `.env`, `data/`, `.venv/`, Frontend-`node_modules`/`.next`.
