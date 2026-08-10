# Ratslotse — Designsprache

Stand: 10.08.2026 · destilliert aus allen Design-Artboards dieses Projekts
(Ist-Screens, Kommunalwahl, Ratsgespräch 1a–8d). Referenz für Claude Code:
Bei jedem neuen Screen gegen diese Datei bauen; die Artboards zeigen die Anwendung.

## 1. Markenkern

- **Charakter:** ruhig, bürgernah, quellen-ehrlich. Amtliches wird lesbar, nie reißerisch.
- **Du-Form**, konkrete Verben, kurze Sätze. Kein KI-Vokabular: „Frag den Rat",
  „Gründliche Recherche" — nie „Prompt", „Agent", „Deep Research", „LLM".
- **Ehrlichkeit ist Designprinzip:** Disclaimer haben feste Orte (nicht wegklickbar,
  nicht aufdringlich); Paraphrasen kursiv ohne Anführungszeichen; keine erfundenen
  Grafiken (kein Stimmverhalten — das RIS kennt keins); Externes klar markiert.
- **Lotti (Maskottchen):** Beobachterin, nie Chat-Autorin. Erlaubt: Empty States,
  Ladezustände, „nichts gefunden", Consent-Momente. Posen via mascot.jsx:
  wave / search / confused / point. Antworten kommen „aus den Beschlüssen", nicht „von Lotti".

## 2. Farben

### Hell (Default)
| Rolle | Wert |
|---|---|
| Seite | hsl(204 45% 97.5%) |
| Tonfläche/Bühne (Container im Container) | hsl(205 42% 96.5%) |
| Karte | #fff |
| Rahmen | hsl(208 32% 89%) |
| Trennlinie (in Karten) | hsl(206 40% 94%) |
| Text | hsl(212 55% 11%) |
| Fließtext lange Antworten | hsl(212 55% 20%) |
| Sekundär | hsl(209 18% 42%) |
| Muted/Labels | hsl(209 18% 55%) |
| **Primär „Hafenblau"** | hsl(205 92% 34%) |
| **Signal-Orange** (nur Akzent: KI-Funken, Deltas, Marker) | hsl(19 92% 55%) |

### Dunkel
Seite hsl(213 50% 7%) · Karte hsl(212 42% 11%) · Rahmen hsl(211 36% 17%)
(interaktiv 21%) · Text hsl(204 40% 96%) · Sekundär hsl(208 22% 65%) ·
Primär hsl(202 90% 60%) (Text darauf dunkel!) · Signal hsl(19 95% 60%).

### Semantik (Tints, nie Vollfarben-Flächen)
- Erfolg/Angenommen: #dcfce7 / #15803d
- Fehler/Abgelehnt: #fef2f2 + Rahmen #fecaca / #b91c1c
- Warnung/Vertagt/Limits: #fffbeb + #fde68a / #92400e
- Neutral/Zur Kenntnis: hsl(206 40% 94%) / hsl(209 18% 42%)
- Primär-Tints: bg primary/4–10, Rahmen primary/16–30 (Nutzer-Bubble: bg /7, Rahmen /18)

### Parteifarben (nur 8-px-Dots & 9-px-Tags, nie Flächen)
SPD #e3000f · CDU #1a1a1a · Grüne #3d8f29 · FDP #ffe000 (heller Dot: Inset-Ring
rgba(0,0,0,.15)) · AfD #009ee0 · Linke #e6007e · BSW #7d254f · Gruppen: neutraler
Dot hsl(209 18% 65%), kombiniertes Label.

## 3. Typografie

- **Inter** 400/500/600/700 — UI und Fließtext. Antworten 14,5–15 / 1.7–1.75;
  UI-Labels 12–13,5; Meta 10–11.
- **Bricolage Grotesque** 600/700 — nur Titel, Abschnittsüberschriften (15–16),
  große Beträge (22–30, tabular-nums). Nie im Fließtext.
- **IBM Plex Mono** 400/500 — Kicker-Labels (9–11 px, VERSAL, letter-spacing
  0.10–0.11em), Datum · GREMIUM-Zeilen, Attributionen, Scores.
- Fußnote [n]: 16×16 Chip, Radius 4, bg primary/10, Text primary 10/700;
  zitiert-aktiv: gefüllt primary, Text weiß.

## 4. Flächen & Abstände

- Karten: Radius 12 (Bausteine) / 14–18 (Panels), Padding 12–18,
  Schatten 0 1px 2px rgba(0,0,0,0.04) — mehr Schatten nur für Overlays
  (Popover: 0 12–14px 32–36px -8…-10px rgba(2,32,71,0.25–0.3)).
- Pills/Chips: Radius 9999, Padding 4–7 × 10–12, Rahmen 1 px.
- Gestrichelt = „nicht von uns / noch nicht fertig": 1px dashed für Externes
  (Presse, oldenburg.de), 2px dashed für Lade-/Arbeitsbereiche.
- Abstände: Turn-Gap 24 (mobil) / 28 (Desktop) · Stack in Antwort 12–14 ·
  Chip-Gap 5–6 · Karten-Innenraster 7–12.
- Layout Desktop: Inhalt max 1420 zentriert; Chat-Bühne (Tonfläche, Radius 18,
  Höhe = Viewport − Kopf, Composer an Unterkante) + Belege-Spalte 320–330.
  Sidebar 230 mit Pflicht-Links im Fuß. Mobil: Geräterahmen ist der Container,
  Composer sticky über Tab-Bar (Safe-Area), Chips laufen in 40–56-px-Fade aus.
- Icons: Lucide, stroke-width 2, 11–22 px, currentColor.

## 5. Wiederkehrende Bausteine (Spez im Artboard „Ratsgespräch")

- **Mono-Kicker** über jedem Block: QUELLEN · AKTUELLES VON DER STADT · EXTERN ·
  AUS DEN RATSDEBATTEN · WIE ES WEITERGEHT · ZUM BEISPIEL — plus rechts eine
  ehrliche Zähl-/Zeitraum-Angabe („12 zitiert · 40 gefunden", „2019–2026").
- **Quellen-Pill/-Zeile** (RG-02): n-Badge 16 ⌀ + Titel ellipsiert (+ Jahr mobil /
  GREMIUM · DATUM Desktop); Rest hinter „Alle N Quellen".
- **Ergebnis-Badges** (RG-03): Angenommen / Abgelehnt / Vertagt / Zur Kenntnis
  in Semantik-Tints, Radius 9999, 10,5/600.
- **Zeitstrahl** (RG-03): 16-px-Rail, Punkte 10 ⌀, letzte Station = gefüllter
  Punkt mit Halo + primary/6-Box „AKTUELLER STAND".
- **Geld** (RG-04): Bricolage-Großbetrag + Vergleichszeilen (Label · Balken h 6 ·
  Betrag), Delta in Signal-Orange, jeder Betrag mit [n].
- **Parteien** (RG-09): Dot + Label 700 + Position 1–2 Sätze + Paraphrase kursiv
  „— Sprecher, Datum"; Badge „uneinheitlich" (Amber); Fußzeile „Paraphrasen,
  keine wörtlichen Zitate".
- **Presse-Block** (RG-06): max 3 Zeilen, gestrichelt, External-Link-Icon,
  nie Fußnoten-Ziel.
- **Composer**: h 48–52, Radius 16, Funken-Icon (Signal-Orange) links, Senden
  36–38 ⌀ primary (disabled: primary/35); Datenschutz-Zeile 10 px darunter, immer.
- **Turn-Fußzeile**: KI-Disclaimer 10,5–11 px + stille Icon-Aktionen 15 px
  (Teilen, Drucken, Vorlesen, 👍/👎) — keine gerahmten Buttons.

## 6. Interaktions-Grammatik

- Primäraktion = gefüllter primary-Button (Radius 10–11, h 32–38); Sekundär =
  weißer Ghost mit Rahmen; destruktiv = #b91c1c gefüllt nur im Bestätigungsdialog.
- Vorschlags-Chips (antippbare Fragen): primary-Rahmen /30 + bg /4 (auf Tonfläche
  weiß) + Pfeil/Icon; nur am jüngsten Turn.
- Hover legt Zeilen-Aktionen frei („Dazu fragen") — Fläche primary/5, Radius 9.
- Fortschritt: Häkchen grün ✓ → Spinner (12 px, primary) → gepunkteter Kreis
  (ausstehend); Playful-Zwischenwort erlaubt („Protokolle querlesen …").
- Fehler/Limits: immer mit Ausweg (Retry, „Als schnelle Frage", Countdown) und
  ohne Datenverlust („Frage steht wieder im Eingabefeld").
- Ehrliche Mengen: nie „viele", immer Zahl + Zeitraum.

## 7. Anti-Patterns

Keine Anführungszeichen um Paraphrasen · keine Stimm-/Abstimmungsgrafiken ·
kein Signal-Orange als Flächenfarbe · keine Parteifarben-Flächen · kein Emoji
im UI-Text · keine gerahmten Button-Reihen unter Antworten (stille Icons) ·
Bricolage nie im Fließtext · Externes nie wie Beschlüsse stylen · Footer nie
auf der Chat-Seite (Links im Sidebar-Fuß).
