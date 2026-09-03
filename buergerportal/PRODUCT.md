# Produktvertrag „Probleme in Oldenburg“

## Identität und Sprache

Der Bereich heißt **Probleme in Oldenburg**, in knapper Navigation
**Probleme**. **Problemkarte** bezeichnet nur die Kartenansicht. Das Angebot ist
ein unabhängiges Ratslotse-Bürgerprojekt und kein amtliches Meldesystem der
Stadt Oldenburg.

Amtlich klingende Wörter wie Ticket, Fallnummer, Mängelmelder oder unbelegter
Bearbeitungsstand werden nicht verwendet. Karten- und Ranglistenfarben folgen derselben beschrifteten Hafenblau-Skala
für die Meldehäufigkeit: 1, 2–4, 5–9 oder 10 und mehr.

## Öffentliche Übersicht — Iteration 2

`/probleme` ist ohne Anmeldung lesbar und auf der Feature-Umgebung freigeschaltet.
Die Karte ist die Standardansicht. Direkt erreichbare Themenchips filtern die
Karte. Ein kompakter Statusfilter bleibt in Karte und Rangliste erhalten; Status
bestimmt aber nicht mehr das Layout.

„Meistgemeldet“ ersetzt das frühere Status-Board. Die Rangliste enthält nur
ungelöste Projektionen und ordnet sie nach der lebenszeitlichen Gesamtzahl
freigegebener unabhängiger meldender Personen, absteigend. Gleichstände werden
nach Titel und dann ID aufgelöst. Jede Zeile nennt die exakte Zahl; sie zeigt
Aufmerksamkeit, nicht Wahrheit, Dringlichkeit, Schadenshöhe oder Betroffenenzahl.
Die ersten drei Zeilen sind ruhig hervorgehoben. Lotti weist mit der an diesen
Zustand gebundenen Zeigegeste auf Platz 1 hin, ohne ein ungelöstes Problem zu
feiern.

Die per Tastatur bedienbare Vorschau enthält ausschließlich die freigegebene
Zusammenfassung und Metadaten der öffentlichen Projektion. Punkte,
Einrichtungen, Routen, Polygone und MultiPolygone lassen sich nur mit gültiger
Geometrie auf der Karte fokussieren. Stadtweite und fehlerhafte Projektionen
bleiben in der Rangliste; die Vorschau erklärt, warum kein Kartenpunkt erfunden
wird. Bewegungen markieren nur Aufklappen und Kartenfokus und entfallen bei
`prefers-reduced-motion`.

`GET /api/probleme` liefert die moderierte Zusammenfassung, die exakte Zahl und
das Häufigkeitsband, aber niemals Identitäten, Rohtexte, einzelne Meldungen oder
private Moderationsdaten. Die Feature-Daten sind im Titel und in der Oberfläche
als frei erfundene Beispiele gekennzeichnet. Sie werden idempotent ausschließlich
in der separaten Feature-Datenbank erzeugt.

## Routen

| Route | Sichtbarkeit | Stand |
|---|---|---|
| `/probleme` | öffentlich | Iteration 2 |
| `/probleme/[id]` | öffentlich | späterer eigener Schnitt |
| `/probleme/melden` | verifiziertes Nicht-Admin-Konto | späterer eigener Schnitt |
| `/meine-meldungen` | Eigentümer*in | reserviert |
| `/admin/meldungen` | Admin | reserviert |

Iteration 2 enthält keine Detailseite, private Meldung, Moderationsoberfläche,
automatische Veröffentlichung oder KI-Funktion.
