---
title: 0005 — SQLite + FTS5 als einzige Datenbank
description: Gründe für SQLite als Datenbank und FTS5 als Volltextindex.
sidebar:
  order: 5
---

**Status:** Akzeptiert

## Kontext

Die App speichert Ratssitzungen, Protokolle, Beschlüsse, Vorlagen-Volltexte,
Nutzerkonten, Themen und daraus berechnete Daten. Die Datenbank muss eine
Volltextsuche mit Unterstützung für deutsche Umlaute bieten und sich mit
geringem Betriebsaufwand deployen lassen. Die Last ist moderat. Die App
läuft auf einem Server, und Schreibzugriffe kommen vor allem von geplanten
Jobs.

## Entscheidung

Ratslotse verwendet **SQLite** mit zwei Datenbankdateien. Eine speichert
Konten und Themen, die andere Ratsdaten (`council.sqlite`). Der
**FTS5**-Volltextindex verwendet den Tokenizer `unicode61 remove_diacritics 2`
für deutsche Umlaute. Ein separater Datenbankserver ist nicht erforderlich.

## Konsequenzen

- **Plus:** Null Betriebsaufwand für die DB — keine eigene DB-Instanz, kein
  Netzwerk, kein Connection-Pooling. Backups sind einfache Dateikopien
  (`backup_db.py`, 7 Generationen).
- **Plus:** FTS5 liefert die Volltextsuche (Beschlüsse, Vorlagen, KI-Frage-Recall)
  ohne Zusatzkomponente; `remove_diacritics 2` macht Umlaut-Suche robust.
- **Plus:** Geplante Jobs und Web-Service teilen sich dieselben Dateien direkt —
  kein API-Hop nur für Daten.
- **Minus:** Nur ein Schreibzugriff zur selben Zeit ist möglich.
  Derzeit ist das kein Engpass. Für den Betrieb auf mehreren Knoten
  oder unter hoher Last wäre ein Wechsel auf PostgreSQL nötig.
- **Minus:** Die DB-Dateien werden per rsync vom Deploy **ausgespart** (`data/`),
  liegen also nur auf dem Server; lokal entstehen sie leer beim ersten Lauf.
