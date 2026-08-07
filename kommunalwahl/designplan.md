# Designplan — Wahlprogramm-Vergleich Oldenburg 2026

**Gegenstand:** 16 Wahlvorschläge zur Ratswahl Oldenburg, 13.09.2026.
**Publikum:** politisch interessierte Oldenburger:innen, Volt-Aktive im Wahlkampf.
**Aufgabe der Seite:** nachvollziehbar zeigen, wer zu welchem Thema was sagt — und wie nah
sich zwei Listen stehen.

Das ist ein **Werkzeug, kein Dokument**: Informationsdesign führt, Typografie stützt.
Harte Randbedingung: In den Daten stecken bereits 16 Parteifarben. Die Oberfläche muss
deshalb fast monochrom bleiben, sonst wird die Seite ein Jahrmarkt.

## Leitbild: „Der Stimmzettel"

Der niedersächsische Stimmzettel ist das eine Objekt, das am 13.09. jede:r in der Hand hält:
großes Blatt, nummerierte Zeilen, Haarlinien-Raster, amtliche Ziffern, drei Stimmen.
Übernommen wird seine **Struktur** (nummerierte Zeilen, Haarlinien, Drei-Stimmen-Motiv,
tabellarischer Ziffernsatz) — nicht seine Optik als Pastiche.

## Farbe

| Token | hell | dunkel | Rolle |
|---|---|---|---|
| `--papier` | `#FCFBF9` | `#14161A` | Grund (minimal warmes Papierweiß / tiefes Schiefer-Schwarz) |
| `--flaeche` | `#FFFFFF` | `#1B1E23` | Karten, Tabellenflächen |
| `--tinte` | `#1A1D21` | `#E8E6E1` | Text |
| `--akzent` | `#2D6E7E` | `#5AA6B8` | Petrol (Hunte/Nordsee) — **einziger** Interaktionsakzent |
| `--warm` | `#B0801F` | `#D6A63C` | Oldenburger Ocker (Schloss/Wappen) — nur Auswahl-Highlight |

Neutralgraus leicht ins Petrol gebogen statt Grau von der Stange.
Petrol bewusst gewählt: kollidiert **weder** mit der Ampel **noch** mit Volt-Lila — die Seite
ist neutrale Wahlinformation und darf nicht wie ein Volt-Werbemittel aussehen.

**Ampel = eigene semantische Skala**, nie Deko:
`--gruen #2E7D5B` · `--gelb #C1861B` · `--rot #B04434`
Immer zusammen mit Prozentzahl **und** Glyphe, damit sie ohne Farbwahrnehmung lesbar bleibt.
Parteifarben ausschließlich in Datenmarken.

## Typografie

Keine Webfonts (CSP blockt CDNs; kein Silent Fallback riskieren) → belastbare Stacks:

- **Display:** `"Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif`
  → gedruckt-amtliches Register, klar abgesetzt vom üblichen Grotesk-Default.
- **Fließtext/UI:** System-Sans-Stack — neutral, überall verfügbar.
- **Daten/Labels:** `ui-monospace, "SF Mono", Menlo, Consolas, monospace`,
  `font-variant-numeric: tabular-nums`, Versal-Eyebrows mit `letter-spacing`.

Laufweite Fließtext ~65–68 Zeichen, feste Typoskala, `text-wrap: balance` auf Überschriften.

## Layout

Einspaltiges Dokument (max ~1180 px) mit vollbreiten Datenblöcken, schmale Sticky-Navigation.
Breite Tabellen/Matrizen scrollen in eigenem `overflow-x: auto`-Container — der Body nie.

1. **Kopf** — Titel, Datum, Kennzahlenstreifen (52 Sitze · 383 Kandidierende · 16 Wahlvorschläge · 3 Stimmen)
2. **Datenlage** — ehrlich zuerst: wer hat ein echtes Programm, wer nur Stichpunkte, wer nichts. Das ist selbst ein Befund.
3. **Themenfelder** — welches Thema deckt wie viele Programme ab (Rangliste)
4. **Themen-Explorer** — Thema wählen → Positionen aller Listen nebeneinander
5. **Ähnlichkeit** — Matrix mit Prozent + Ampel; Zelle klicken → Detail mit Themen-Ampeln und den Thesen, die den Wert treiben
6. **Selbsttest** — Nutzer:in beantwortet die Thesen selbst und bekommt die eigene Rangliste (der eigentliche Wahlkampfnutzen)
7. **Parteiprofile** — Charakter, Kernforderungen, Besonderheiten, Quelle
8. **Methodik** — Rechenweg, Grenzen, Quellen, Stand

## Methodik der Ähnlichkeit

Thesen-Matrix nach Wahl-O-Mat-Logik, symmetrisch zwischen zwei Listen:
Position je These `+1 / 0 / −1 / keine Aussage`; gewertet nur Thesen, zu denen **beide** eine
Position haben; Übereinstimmung je These `1 − |a−b|/2`; Ähnlichkeit = Mittelwert × 100.
`n` (Zahl gemeinsamer Thesen) wird **immer** mit ausgewiesen; unter `n = 5` gilt der Wert als
nicht belastbar und wird als solcher markiert statt beschönigt.
