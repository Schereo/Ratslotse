---
title: 0005 — SQLite + FTS5 als einzige Datenbank
description: Warum SQLite mit FTS5 statt PostgreSQL o. ä.
sidebar:
  order: 5
---

**Status:** Akzeptiert

## Kontext

Die App speichert Zeitungsausgaben, Artikel-Volltexte, Ratssitzungen, Themen,
Nutzer und vorberechnete Ableitungen. Gebraucht werden: Volltextsuche mit
deutscher Umlaut-Behandlung, einfache Deploys und geringer Betriebsaufwand. Die
Last ist moderat (ein Single-Node-Bot + Web-Frontend, Schreibzugriffe v. a. durch
Cron-Jobs, kein Hochlast-Multi-Writer-Szenario).

## Entscheidung

**SQLite** als einzige Datenbank — zwei Dateien (`data/nwz.sqlite`,
`data/council.sqlite`) — mit **FTS5**-Volltextindex (Tokenizer
`unicode61 remove_diacritics 2` für deutsche Umlaute). Kein separater
DB-Server.

## Konsequenzen

- **Plus:** Null Betriebsaufwand für die DB — keine eigene DB-Instanz, kein
  Netzwerk, kein Connection-Pooling. Backups sind einfache Dateikopien
  (`backup_db.py`, 7 Generationen).
- **Plus:** FTS5 liefert die Volltextsuche (`/suche`, Follow-up-Recall) ohne
  Zusatzkomponente; `remove_diacritics 2` macht Umlaut-Suche robust.
- **Plus:** Bot und Web-Service teilen sich dieselben Dateien direkt — kein API-
  Hop nur für Daten.
- **Minus:** Begrenzte Schreib-Nebenläufigkeit (ein Writer zur Zeit). Bei
  zukünftigem Multi-Node-/Hochlast-Betrieb wäre ein Wechsel auf PostgreSQL nötig
  — derzeit kein Engpass.
- **Minus:** Die DB-Dateien werden per rsync vom Deploy **ausgespart** (`data/`),
  liegen also nur auf dem Server; lokal gibt es keine realen Daten (siehe
  [KI-Pipeline](/docs/ki-pipeline/) → Seeder).
