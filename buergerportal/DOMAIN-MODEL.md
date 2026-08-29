# Domänenmodell und Zugriffsgrenzen des Bürgerportals

Dieses Dokument konkretisiert die bestätigten Regeln aus `BUERGERPORTAL-BACKLOG.md` für den P0-Persistenzschnitt.

## Beziehungen und Invarianten

- Ein Ratslotse-Konto besitzt beliebig viele Meldeentwürfe und Meldungen.
- Ein Meldeentwurf wird genau einmal bewusst abgesendet und damit zur Meldung.
- Eine Meldung gehört genau einem Konto und enthält eine oder mehrere Beobachtungen desselben Kontos.
- Eine Meldung kann durch Moderation höchstens einem öffentlichen Problem zugeordnet werden.
- Ein Konto kann einem Problem höchstens eine Meldung beitragen. Spätere Beobachtungen werden an dieser Meldung ergänzt.
- Viele Meldungen verschiedener Konten können demselben Problem zugeordnet sein.
- Eine Moderationsentscheidung ist ein unveränderlicher Audit-Eintrag mit Admin-Konto, Ergebnis, Begründungscode, privater Notiz, getrennter Mitteilung an die Reporter*in und Zeitpunkt.
- Zu jeder Moderationsentscheidung kann höchstens eine erneute Prüfung angefordert werden; Anfrage und Ergebnis bleiben privat nachvollziehbar.
- Korrekturen an Kategorie oder geografischem Bezug halten vorherige und neue Werte strukturiert in der Moderationsentscheidung fest.
- Ein Problemstatus beschreibt nur belegbare Tatsachen. Externe Aussagen benötigen Quelle und Rollenlabel.
- Ein geografischer Bezug ist ein Punkt, eine Einrichtung, eine Route, ein Gebiet oder das gesamte Stadtgebiet. Punkte und Einrichtungen benötigen Koordinaten.
- Die konkrete Geometrie für Routen und Gebiete bleibt eine offene Produktentscheidung. Der private P0-Schnitt speichert dafür noch keine frei gewählte Geometriestruktur.

## Lebensläufe

Ein Meldeentwurf beginnt als `draft`. Bewusstes Absenden führt zu `submitted`; Moderation kann `in_review`, `needs_information`, `accepted` oder `rejected` ergeben. Ein zulässiger Rückzug führt zu `withdrawn`. Der bestätigte deutsche Text wird beim ersten Absenden als erste Beobachtung festgehalten.

Ein Problem verwendet ausschließlich belegbare Zustände: `new`, `multiple_reports`, `verified`, `persists` und `apparently_resolved`. Amtliche Bearbeitung ist kein eigener Zustand ohne überprüfbare städtische Quelle.

## Trennung privater Daten und öffentlicher Projektion

| Private Schreibseite | Öffentliche Projektion |
|---|---|
| Meldeentwurf und bestätigter Meldetext | Moderierter Titel und Zusammenfassung |
| Konto-ID der Reporter*in | Aggregierte Meldehäufigkeit |
| Einzelne Beobachtungen | Freigegebene aggregierte Kennzahlen |
| Moderationsnotiz und Begründung | Ausdrücklich veröffentlichte Statusereignisse |
| Nicht veröffentlichte Geografie | Freigegebener geografischer Bezug |

`ReportStore` besitzt die private Schreibseite und bietet eigentumsgebundene Leseoperationen. `ProblemStore` besitzt ausschließlich die öffentliche Projektion. Beide verwenden getrennte Tabellen und Interfaces, auch wenn sie in derselben SQLite-Datei liegen. Die öffentliche Projektion wird niemals aus Rohmeldungen serialisiert.

Konto-IDs werden bewusst nur referenziert und nicht durch einen datenbankweiten Fremdschlüssel gekoppelt: Die Konto- und Bürgerportal-Module haben getrennte Migrationen und Lebenszyklen. Konto-Löschung und Aufbewahrung werden deshalb vor P3 als expliziter Anwendungsablauf umgesetzt und getestet.

## Autorisierungsmatrix

| Fähigkeit | Öffentlich | Aktives, verifiziertes Konto | Eigentümer*in | Admin |
|---|:---:|:---:|:---:|:---:|
| Öffentliche Problemliste und freigegebene Details lesen | ja | ja | ja | ja |
| Meldeentwurf anlegen und absenden | nein | nur für sich | ja | nein |
| Private Meldung und Beobachtungen lesen | nein | nein | ja | zur Moderation |
| Eigene Meldung aktualisieren oder zurückziehen | nein | nein | ja | nein |
| Fremde Meldung ändern | nein | nein | nein | nur durch protokollierte Moderationsentscheidung |
| Moderieren, zuordnen, freigeben oder ablehnen | nein | nein | nein | ja |
| Moderationsnotizen lesen | nein | nein | nur freigegebene Mitteilung | ja |

Die spätere HTTP-Schreibseite muss `require_active` für Reporter*innen und `require_admin` für Moderation verwenden. Ressourcenzugriffe von Reporter*innen gehen zusätzlich immer über eine eigentumsgebundene Store-Operation; eine erratene Meldungs-ID allein gewährt keinen Zugriff.

## Migrationen

Private Tabellen werden vor Benutzung über fortlaufende Versionen in `civic_report_schema_migrations` angelegt. Jede Version läuft atomar und nur einmal. Das Öffnen der privaten Schreibseite verändert oder löscht keine bestehende öffentliche Projektion. Migrationstests öffnen eine bereits befüllte Problemprojektion, migrieren sie und prüfen die öffentlichen Daten anschließend über das öffentliche Interface.
