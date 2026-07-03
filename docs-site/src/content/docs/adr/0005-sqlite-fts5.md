---
title: 0005 — SQLite + FTS5 als einzige Datenbank
description: Warum SQLite mit FTS5 statt PostgreSQL o. ä.
sidebar:
  order: 5
---

**Status:** Akzeptiert

## Kontext

Die App speichert Ratssitzungen, Protokolle, Beschlüsse, Vorlagen-Volltexte,
Nutzerkonten, Themen und vorberechnete Ableitungen. Gebraucht werden:
Volltextsuche mit deutscher Umlaut-Behandlung, einfache Deploys und geringer
Betriebsaufwand. Die Last ist moderat (Single-Node-Betrieb, Schreibzugriffe
v. a. durch geplante Jobs, kein Hochlast-Multi-Writer-Szenario).

## Entscheidung

**SQLite** als einzige Datenbank — zwei Dateien: eine für Konten & Themen, eine
für die Ratsdaten (`council.sqlite`) — mit **FTS5**-Volltextindex (Tokenizer
`unicode61 remove_diacritics 2` für deutsche Umlaute). Kein separater
DB-Server.

## Konsequenzen

- **Plus:** Null Betriebsaufwand für die DB — keine eigene DB-Instanz, kein
  Netzwerk, kein Connection-Pooling. Backups sind einfache Dateikopien
  (`backup_db.py`, 7 Generationen).
- **Plus:** FTS5 liefert die Volltextsuche (Beschlüsse, Vorlagen, KI-Frage-Recall)
  ohne Zusatzkomponente; `remove_diacritics 2` macht Umlaut-Suche robust.
- **Plus:** Geplante Jobs und Web-Service teilen sich dieselben Dateien direkt —
  kein API-Hop nur für Daten.
- **Minus:** Begrenzte Schreib-Nebenläufigkeit (ein Writer zur Zeit). Bei
  zukünftigem Multi-Node-/Hochlast-Betrieb wäre ein Wechsel auf PostgreSQL nötig
  — derzeit kein Engpass.
- **Minus:** Die DB-Dateien werden per rsync vom Deploy **ausgespart** (`data/`),
  liegen also nur auf dem Server; lokal entstehen sie leer beim ersten Lauf.
