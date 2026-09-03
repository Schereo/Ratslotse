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
Karte. Veröffentlichte Projektionen brauchen keinen zusätzlichen Freigabe- oder
Mehrfachmeldungs-Status in der Oberfläche: Karte, Auswahl und Rangliste zeigen
vorerst weder Statusfilter noch Status-Badges. Die exakte Meldezahl trägt die
Mengeninformation bereits selbst.

Der Tab „Rangliste“ ersetzt das frühere Status-Board; der kompatible Direktlink
bleibt `/probleme?view=meistgemeldet`. Die Rangliste enthält nur ungelöste
Projektionen und ordnet sie nach der lebenszeitlichen Gesamtzahl freigegebener
unabhängiger meldender Personen, absteigend. Gleichstände werden nach Titel und
dann ID aufgelöst. Jede Zeile nennt die exakte Zahl; sie zeigt Aufmerksamkeit,
nicht Wahrheit, Dringlichkeit, Schadenshöhe oder Betroffenenzahl. Alle Ränge
stehen auf Desktop und Mobil als gleich breite Zeilen untereinander. Ihre Balken
wachsen auf einer gemeinsamen Null-bis-Maximum-Schiene von links nach rechts;
die ersten drei unterscheiden sich kompakt durch Tönung, Schrift und Rangzahl,
nicht durch eine andere Kartenbreite. Die Quellenzeile bleibt direkt unter der
Rangliste sichtbar, die Projekt-/Amtlichkeitseinordnung im Pflicht-Fuß. Lotti ist
der eine kontextuelle Hilfezugang für Karte und Rangliste. Geschlossen ruht sie auf der
Karte beziehungsweise weist in der Rangliste auf den Inhalt, geöffnet erklärt
sie mit der zustandsgebundenen `erklaert`-Regung Skala, Zählgrenzen und fiktive
Beispiele. Sie ist ein echter Tastatur- und Touch-Button und feiert kein
ungelöstes Problem.

Die per Tastatur bedienbare Vorschau enthält ausschließlich die freigegebene
Zusammenfassung und Metadaten der öffentlichen Projektion. Punkte,
Einrichtungen, Routen, Polygone und MultiPolygone lassen sich nur mit gültiger
Geometrie auf der Karte fokussieren. Stadtweite und fehlerhafte Projektionen
bleiben in der Rangliste; die Vorschau erklärt, warum kein Kartenpunkt erfunden
wird. Bewegungen markieren den Eintritt in die Rangliste, Hover/Fokus, Aufklappen,
Lotti-Hilfe und Kartenfokus. Sie sind zustandsgebunden, laufen nicht zufällig
und entfallen bei `prefers-reduced-motion`.

`GET /api/probleme` liefert die moderierte Zusammenfassung, die exakte Zahl und
das Häufigkeitsband, aber niemals Identitäten, Rohtexte, einzelne Meldungen oder
private Moderationsdaten. Die Feature-Daten sind im Titel und in der Oberfläche
als frei erfundene Beispiele gekennzeichnet. Sie werden idempotent ausschließlich
in der separaten Feature-Datenbank erzeugt.

## Öffentliche Detailseite — Iteration 3

Die kanonische Web-Route `/probleme/[id]` zeigt dieselbe datensparsame
öffentliche Projektion wie die Übersicht: Titel, moderierte Zusammenfassung,
Kategorie, freigegebenen Ortsbezug, ehrliche Geometrie, exakte unabhängige
Meldezahl und Häufigkeitsband. `GET /api/probleme/{problem_id}` verwendet
identische Sichtbarkeits- und Projektionsregeln wie die Liste. Unveröffentlichte,
gelöste, meldungslose oder unbekannte IDs liefern keinen Datensatz.

Karte und Rangliste trennen „Auf der Karte zeigen“ von „Details ansehen“.
Ehrlich kartierbare Details fokussieren ihre Geometrie; stadtweite und ungültige
Geografien erklären knapp, warum keine Karte erscheint. Status-Badges und eine
aus Daten oder Statuswerten erfundene Zeitleiste bleiben aus. Lotti ist der eine
kontextuelle Hilfezugang für Zählgrenzen, Geografie und fiktive Beispiele. Die
Seite lässt sich über ihre kanonische Web-URL teilen und bleibt ohne Konto
lesbar.

Der statische Android-Export kann beliebige IDs nicht vorab erzeugen. Dort
öffnet `/probleme?problem=[id]` dieselbe Darstellung innerhalb der Übersicht;
eingehende Web-Links werden auf diesen Query-Pfad übersetzt. Auch negative IDs
der ausschließlich auf `feature` vorhandenen Beispiele sind gültig. Die native
iOS-App besitzt noch keine Bürgerportal-Ansicht und öffnet diese öffentlichen
Links deshalb im Web.

## Routen

| Route | Sichtbarkeit | Stand |
|---|---|---|
| `/probleme` | öffentlich | Iteration 2 |
| `/probleme/[id]` | öffentlich | Iteration 3 |
| `/probleme?problem=[id]` | öffentlich | Iteration 3, statischer App-Adapter |
| `/probleme/melden` | verifiziertes Nicht-Admin-Konto | späterer eigener Schnitt |
| `/meine-meldungen` | Eigentümer*in | reserviert |
| `/admin/meldungen` | Admin | reserviert |

Iteration 3 enthält keine private Meldung, öffentliche Zeitleiste,
Moderationsoberfläche, automatische Veröffentlichung oder KI-Funktion.
