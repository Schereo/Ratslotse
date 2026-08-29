# Domänenmodell und Zugriffsgrenzen des Bürgerportals

Dieses Dokument konkretisiert die bestätigten Regeln aus `BUERGERPORTAL-BACKLOG.md` für den P0-Persistenzschnitt.

## Beziehungen und Invarianten

- Ein Ratslotse-Konto besitzt beliebig viele Meldeentwürfe und Meldungen.
- Ein Meldeentwurf wird genau einmal bewusst abgesendet und damit zur Meldung.
- Eine Meldung gehört genau einem Konto und enthält eine oder mehrere Beobachtungen desselben Kontos.
- Eine meldende Person kann im Entwurf ein bereits öffentliches Problem als Zuordnung vorschlagen. Dieser private Vorschlag ist keine Zuordnung und bindet die Moderation nicht.
- Eine Meldung kann durch Moderation höchstens einem öffentlichen Problem zugeordnet werden.
- Ein Konto kann einem Problem höchstens eine Meldung beitragen. Spätere Beobachtungen werden an dieser Meldung ergänzt.
- Viele Meldungen verschiedener Konten können demselben Problem zugeordnet sein.
- Eine KI-Vorprüfung ist ein unveränderliches privates Eignungsurteil mit Modellkennung, Begründungscode, Inhaltsrevision und Zeitpunkt. Jede neue Beobachtung macht das alte Urteil für eine Freigabe ungültig.
- Eine Moderationsentscheidung ist ein unveränderlicher menschlicher Audit-Eintrag mit Admin-Konto, Ergebnis, Begründungscode, privater Notiz, getrennter Mitteilung an die meldende Person und Zeitpunkt.
- Eine Meldung darf erst nach einem geeigneten KI-Urteil zur aktuellen Inhaltsrevision und der abschließenden menschlichen Freigabe einer öffentlichen Projektion zugeordnet werden. Keiner der beiden Schritte veröffentlicht selbstständig Daten; die öffentliche Projektion prüft beide Nachweise erneut.
- Zu jeder Moderationsentscheidung kann höchstens eine erneute Prüfung angefordert werden; Anfrage und Ergebnis bleiben privat nachvollziehbar.
- Korrekturen an Kategorie oder geografischem Bezug halten vorherige und neue Werte strukturiert in der Moderationsentscheidung fest.
- Ein Problemstatus beschreibt nur belegbare Tatsachen. Externe Aussagen benötigen Quelle und Rollenlabel.
- Ein geografischer Bezug ist ein Punkt, eine Einrichtung, eine Route, ein Gebiet oder das gesamte Stadtgebiet. Nicht stadtweite private Eingaben benötigen einen ungefähren Kartenpunkt innerhalb der konservativen Oldenburger Begrenzung; der genaue Eingabeort bleibt privat.
- Jeder neue Entwurf beantwortet zusätzlich eine kontrollierte, von der Oberkategorie abhängige Mindestfrage. Diese strukturierte Ergänzung bleibt privat.
- Öffentliche Routen verwenden GeoJSON `LineString`; öffentliche Gebiete verwenden `Polygon` oder `MultiPolygon`. Positionen folgen GeoJSON als `[Längengrad, Breitengrad]`, Linien benötigen mindestens zwei Positionen und Polygonringe sind geschlossen.
- Der private Meldeschnitt speichert für Routen und Gebiete zunächst nur Kartenanker und Ortsbezeichnung, keine frei gezeichnete Geometrie. Die Moderation bestimmt die veröffentlichbare Form.
- Stadtweite Probleme tragen keine künstliche Geometrie. Sensible Orte werden vor der Freigabe vergröbert oder nicht veröffentlicht.

## Lebensläufe

Ein Meldeentwurf beginnt als `draft`. Bewusstes Absenden führt zu `submitted`; die KI-Vorprüfung führt zu `in_review`, veröffentlicht aber nichts. Nur ein geeignetes KI-Urteil kann anschließend menschlich als `accepted` freigegeben werden. Weitere menschliche Ergebnisse sind `needs_information` oder `rejected`. Ein zulässiger Rückzug führt zu `withdrawn`. Der bestätigte deutsche Text wird beim ersten Absenden als erste Beobachtung festgehalten.

Ein Problem verwendet ausschließlich belegbare Zustände: `new`, `multiple_reports`, `verified`, `persists` und `apparently_resolved`. Amtliche Bearbeitung ist kein eigener Zustand ohne überprüfbare städtische Quelle.

## Trennung privater Daten und öffentlicher Projektion

| Private Schreibseite | Öffentliche Projektion |
|---|---|
| Meldeentwurf und bestätigter Meldetext | Moderierter Titel und Zusammenfassung |
| Konto-ID der meldenden Person | Zahl unabhängiger Meldungen |
| Einzelne Beobachtungen | Freigegebene aggregierte Kennzahlen |
| KI-Urteil, Moderationsnotiz und Begründung | Ausdrücklich veröffentlichte Statusereignisse |
| Nicht veröffentlichte Geografie | Freigegebener geografischer Bezug |

`ReportStore` besitzt die private Schreibseite und bietet eigentumsgebundene Leseoperationen. `ProblemStore` besitzt ausschließlich die öffentliche Projektion. Beide verwenden getrennte Tabellen und Interfaces, auch wenn sie in derselben SQLite-Datei liegen. Die öffentliche Projektion wird niemals aus Rohmeldungen serialisiert.

Konto-IDs werden bewusst nur referenziert und nicht durch einen datenbankweiten Fremdschlüssel gekoppelt: Die Konto- und Bürgerportal-Module haben getrennte Migrationen und Lebenszyklen. Bei einer Konto-Löschung werden aktive Meldungen zurückgezogen und Kontozuordnung, Rohtexte, Beobachtungen, kategorienabhängige Angaben und genaue Geografie irreversibel redigiert. Eine bereits erzeugte KI- oder Moderations-Prüfspur bleibt wegen ihrer strukturellen Unveränderlichkeit ohne Kontobezug erhalten; Freitexte, Prüfbitten und genaue Geografien darin werden bei der Konto-Löschung ebenfalls redigiert. Betroffene öffentliche Kennzahlen werden über eine persistente Warteschlange neu berechnet.

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

Die HTTP-Schreibseite verwendet `require_verified_reporter` für aktive, verifizierte Nicht-Admin-Konten; die spätere Moderations-API muss `require_admin` verwenden. Eigentumsgebundene Ressourcenzugriffe gehen zusätzlich immer über eine eigentumsgebundene Store-Operation; eine erratene Meldungs-ID allein gewährt keinen Zugriff.

## Migrationen

Private Tabellen werden vor Benutzung über fortlaufende Versionen in `civic_report_schema_migrations` angelegt. Jede Version läuft atomar und nur einmal. Seit Version 8 kann ein Entwurf die ID eines öffentlich gefundenen Problems als unverbindlichen `suggested_problem_id` tragen; die bestätigte `problem_id` bleibt ausschließlich Ergebnis der Moderation. Version 9 ergänzt die private Antwort auf die kategorienabhängige Mindestfrage als `category_detail`. Version 10 bindet wiederholte Erstellversuche über einen kontogebundenen `client_token` an denselben Entwurf und führt eine dauerhafte Warteschlange für neu zu berechnende öffentliche Kennzahlen ein. Das Öffnen der privaten Schreibseite verändert oder löscht keine bestehende öffentliche Projektion. Migrationstests öffnen eine bereits befüllte Problemprojektion, migrieren sie und prüfen die öffentlichen Daten anschließend über das öffentliche Interface.
