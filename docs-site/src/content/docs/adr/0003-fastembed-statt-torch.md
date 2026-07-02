---
title: 0003 — fastembed (ONNX) statt torch
description: Embeddings für „Ähnliche Beschlüsse" ohne schwere torch-Abhängigkeit.
sidebar:
  order: 3
---

**Status:** Akzeptiert

## Kontext

Die Sektion „Ähnliche Beschlüsse" braucht semantische Embeddings
(`scripts/embed_decisions.py`, Tabelle `council_similar`). Die naheliegende
Bibliothek wäre `sentence-transformers` — die zieht aber **torch** mit, ein sehr
großes Paket (mehrere hundert MB), das Deploy-Zeit, Image-Größe und die
Build-Dauer von Bot und Web-Service unnötig aufbläht. Der Web-Service liest die
Nachbarn nur **vorberechnet** aus der DB; er braucht zur Laufzeit gar kein
Embedding-Modell.

## Entscheidung

Embeddings werden mit **fastembed** (ONNX-Runtime, kein torch) berechnet.
fastembed steht **bewusst nicht** in `requirements.txt` — es wird nur bei Bedarf
manuell auf dem Server installiert und der Embedding-Job von Hand bzw. im
wöchentlichen `weekly_enrich.py` ausgeführt.

## Konsequenzen

- **Plus:** Deploy und der reguläre Web-/Bot-Build bleiben schlank und schnell —
  keine torch-Abhängigkeit im kritischen Pfad.
- **Plus:** Der Web-Service hat zur Laufzeit keine ML-Abhängigkeit; er liest nur
  die vorberechnete Nachbarschaftstabelle.
- **Minus:** Der Embedding-Schritt ist ein **separater, manueller** Vorgang
  (`pip install fastembed` auf prod). Wer das vergisst, bekommt veraltete
  „Ähnliche Beschlüsse". Dokumentiert in `CLAUDE.md`.
