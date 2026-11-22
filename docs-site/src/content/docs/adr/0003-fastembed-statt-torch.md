---
title: 0003 — fastembed (ONNX) statt torch
description: Embeddings für „Ähnliche Beschlüsse“ mit fastembed und ONNX.
sidebar:
  order: 3
---

**Status:** Akzeptiert

## Kontext

Die Sektion „Ähnliche Beschlüsse" braucht semantische Embeddings
(`scripts/embed_decisions.py`, Tabelle `council_similar`). Die naheliegende
Bibliothek wäre `sentence-transformers`. Sie benötigt **torch**, ein Paket
von mehreren hundert MB. Das vergrößert das Image und verlängert Deploys
und Builds von Bot und Webdienst. Der Webdienst liest die vorab ermittelten
ähnlichen Beschlüsse aus der Datenbank und braucht dafür zur Laufzeit kein
Embedding-Modell.

## Entscheidung

Embeddings werden mit **fastembed** (ONNX-Runtime, kein torch) berechnet.
fastembed fehlt in `requirements.txt`, weil es nur für die Berechnung der
Embeddings erforderlich ist. Installiere es bei Bedarf manuell auf dem Server.
Der Embedding-Job läuft bei Bedarf manuell oder wöchentlich über
`weekly_enrich.py`.

## Konsequenzen

- **Plus:** Deploy und reguläre Builds von Webdienst und Bot benötigen
  kein torch. Dadurch bleiben sie schneller und kleiner.
- **Plus:** Der Webdienst hat zur Laufzeit keine ML-Abhängigkeit. Er liest
  die schon berechneten Ähnlichkeiten aus der Datenbank.
- **Minus:** Der Embedding-Schritt ist ein **separater, manueller** Vorgang
  (`pip install fastembed` auf prod). Wer das vergisst, bekommt veraltete
  „Ähnliche Beschlüsse". Dokumentiert in `CLAUDE.md`.
