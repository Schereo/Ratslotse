# Produktvertrag „Probleme in Oldenburg“

## Identität und Sprache

Der Bereich heißt **Probleme in Oldenburg**, in knapper Navigation
**Probleme**. **Problemkarte** bezeichnet nur die Kartenansicht. Das Angebot ist
ein unabhängiges Ratslotse-Bürgerprojekt und kein amtliches Meldesystem der
Stadt Oldenburg.

Amtlich klingende Wörter wie Ticket, Fallnummer, Mängelmelder oder unbelegter
Bearbeitungsstand werden nicht verwendet. Kartenfarben zeigen nur die grobe
Meldehäufigkeit: einmal, 2–4, 5–9 oder 10 und mehr.

## Öffentliche Übersicht — Iteration 1

`/probleme` ist ohne Anmeldung lesbar und auf der Feature-Umgebung freigeschaltet.
Die Karte ist die Standardansicht. Direkt erreichbare Themenchips filtern nur
die Karte. Das Status-Board bleibt vollständig und ordnet alle veröffentlichten
Projektionen in belegbare Zustände:

- Neu
- Mehrfach gemeldet
- Geprüft
- Weiterhin vorhanden
- Offenbar behoben

Punkte, Einrichtungen, Routen, Polygone und MultiPolygone erscheinen nur mit
gültiger Geometrie. Stadtweite und fehlerhafte Altprojektionen stehen im Board,
nie an einem erfundenen Kartenpunkt. Die Listen-API `GET /api/probleme` liefert
keine exakte Meldezahl, Rohtexte oder private Moderationsdaten.

Die Feature-Daten sind im Titel und in der Oberfläche als frei erfundene
Beispiele gekennzeichnet. Sie werden idempotent ausschließlich in der separaten
Feature-Datenbank erzeugt.

## Routen

| Route | Sichtbarkeit | Stand |
|---|---|---|
| `/probleme` | öffentlich | Iteration 1 |
| `/probleme/[id]` | öffentlich | späterer eigener Schnitt |
| `/probleme/melden` | verifiziertes Nicht-Admin-Konto | späterer eigener Schnitt |
| `/meine-meldungen` | Eigentümer*in | reserviert |
| `/admin/meldungen` | Admin | reserviert |

Iteration 1 enthält keine Detailseite, private Meldung, Moderationsoberfläche,
automatische Veröffentlichung oder KI-Funktion.
