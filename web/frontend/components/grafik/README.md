# Grafik-Baukasten (`components/grafik/`)

Eine Komponente je redaktioneller Form (Boards GB-00–GB-15). Seiten
**komponieren** Grafiken aus diesem Ordner — sie zeichnen nicht selbst.
Diese Datei ist die Kurzfassung des Vertrags; die Artboards zeigen die
Anwendung, `DESIGNSPRACHE.md` bleibt Pflichtlektüre.

## d3: Rechner ja, Renderer nein

Installiert sind genau vier kopflose Pakete (~15–25 KB gz zusammen):

| Paket | Wofür |
|---|---|
| `d3-scale` | Skalen + `ticks()` für Achsen (Band, Linear, Time) |
| `d3-shape` | Linien/Flächen/Kurven — `defined()` bricht Linien an Lücken |
| `d3-array` | `cumsum` (Wasserfall), `bisectCenter` (Ableseleiste) |
| `d3-hierarchy` | `treemapSquarify` (Investitionen) |

Gratis dabei (Abhängigkeiten, offiziell nutzbar): `d3-interpolate`
(Zahlen-Tweens mit rAF, ≤300 ms) und `d3-time` (Monats-/Jahres-Ticks).

**Verboten — nicht installieren, nicht importieren:**

- **`d3` (Gesamtpaket)** — wir nehmen vier Rechner, nicht den Kosmos.
- **`d3-selection` / `d3-transition` / `d3-axis`** — imperatives DOM neben
  React = zwei Wahrheiten über den Baum. React rendert, CSS animiert,
  Achsen bauen wir aus `scale.ticks()`.
- **`d3-zoom` / `d3-brush` / `d3-drag`** — unsere Charts zeigen immer
  ALLES (31 Jahre, 22 Säulen); der einzige Regler ist ein natives
  `input[range]`.
- **`d3-sankey` / `d3-chord`** — Quer-Bänder behaupten Zuordnungen, die
  der Haushalt nicht hergibt (keine Einnahme „gehört" zu einer Ausgabe,
  GB-07). Das Flussbild endet in EINEM Topf.
- **`d3-force`** — wackelig und nicht-deterministisch; 15 Knoten mit
  Formen-Chips sind lesbarer.
- **`d3-format` / `d3-time-format`** — deutsche Zahlen macht `Intl`
  besser: `components/grafik/format.ts` benutzen, sonst nichts.
- **`d3-scale-chromatic`** — fremde Farbrampen; unsere zwei Rampen +
  Signal-Orange sind Gesetz.

Merksatz: **Rechner (Skalen, Formen, Hierarchien, Suche, Interpolation)
nehmen, Renderer und Regisseure (selection, transition, zoom, force)
liegen lassen** — genau an der Naht, an der React übernimmt.

## Daten-Vertrag (`daten.ts`)

Reihen sind `{jahr, wert}`, Listen `{label, wert}`. **Lücken sind Daten**:
`{jahr: 2019, fehlt: "Grund"}` steht IN der Reihe. Jede Komponente rendert
sie beschriftet (`<LueckenFeld>`), keine interpoliert — `vorhanden()` ist
das `defined`-Prädikat für d3-shape, damit Linien an Lücken abreißen.

## Die gemeinsamen Teile (GB-00)

| Baustein | Datei | Rolle |
|---|---|---|
| `<BelegChip>` | `beleg-chip.tsx` | Pflicht-Slot jeder Grafik: jede Zahl trägt ihren Beleg. Re-Export des Quellen-Systems (`components/haushalt/quelle.tsx`) — Grafiken nehmen ihn als Slot (`beleg?: ReactNode`), die SEITE wählt die Quelle (sie kennt ihren `Quellenkontext`). |
| `<LueckenFeld>` | `luecken-feld.tsx` | Eine Lücke mit Grund und Datum. Rendert die GRAFIK, nie die Seite. **Nie einklappbar.** |
| `<Ableseleiste>` | `ablesen.tsx` | Ersetzt Tooltips überall: Desktop Hover, mobil sticky Tap-Wertzeile, immer Pfeiltasten (`useAblesen` + `AbleseFlaeche` + `Ableseleiste`). Zeigt IMMER eine Stelle, nie leer. |
| `<Einordnung>` | `einordnung.tsx` | Der Satz unter der Zahl: `satz`, `gemessen` („7 von 8 Jahren"), `nichtAussagen` („Was diese Zahl nicht sagt"). **Nie einklappbar, nie abgeschnitten.** |

**Pflicht-Props:** Wo der Karten-Vertrag `einordnung` (Hantel,
Beteiligungen), `nichtAussagen` (Kassenzettel/Pro-Kopf) oder `gemessen`
(Zeitstrahl) führt, sind das Pflicht-Props der Grafik — eine Hantel ohne
Erklärsatz kompiliert nicht. Gerendert werden sie über `<Einordnung>`.

## Zahlen (`format.ts`)

`Intl.NumberFormat("de-DE")`, gecacht. `deZahl` (feste Nachkommastellen),
`mitVorzeichen` (Differenzen: „+12,4", Null ohne Plus), dazu `deMio` und
`betrag` aus `lib/haushalt`. Kein `toLocaleString` in Komponenten.

## Farben & Motion

- Nur die Rampen-Tokens `--hh-ein-*` / `--hh-aus-*` (app/globals.css) —
  hell/dunkel kommt gratis. Auf der Anzeigetafel (`.hh-tafel`) binden die
  Rampen an die FLÄCHE; Komponenten schreiben keine Sonderfarben.
- **Signal-Orange nur für Abweichungen/Differenzen** (und die
  Lücken-Konvention: Schraffur `hh-schraffur` + gestrichelte Signal-Kante).
  **Keine Bewertungsfarben** — kein Grün/Rot, keine „gut/schlecht"-Props;
  ein Zuschuss ist Daseinsvorsorge, keine Schwäche.
- Animation: nur CSS-Transitions auf SVG-Attribute, ≤300 ms,
  `prefers-reduced-motion` respektiert. Keine Library-Animationen.

## Breakpoints (H4-A): eingebaut, kein Prop

Jede Grafik-Form hat genau EIN Tablet- und EIN Mobil-Verhalten — es steckt
IN der Komponente. Die Schwellen: `desk:` = pointer fine **und** ≥1024 px
(ein iPad quer ist KEIN Desktop), Tablet 744–1023 px bzw. coarse, Mobil
< 744 px (Entwurf 390, Minimum 375, Hit-Targets ≥ 44 px). Die wichtigsten
Regeln:

- Zeilen-Tabellen: mobil Karten + Sortier-Select; ab 8 Zeilen Top 5 +
  „alle N zeigen". Weglassen heißt „hinter einen Auslöser", nie ersatzlos —
  Lücken-Hinweise und „Bewusst nicht"-Chips bleiben IMMER sichtbar.
- Gegenbalken: mobil Legende unterm Balken; Maßstab (beide = 100 %) gilt
  überall. Zeitreihe: mobil 180 px, nur Endwerte + Dekaden, Leiste sticky.
- Rangliste: Label wandert ÜBER den Balken. Hantel: nie zweispaltig.
- Treemap: mobil ERSETZT durch Rangliste (gleiche Daten und Sortierung).
- Matrix: mobil Karten-Liste, nie horizontal scrollen. Zeitstrahl: mobil
  senkrecht. Jahr-Pills: mobil Scrollband mit Fade, NIE ein Dropdown.
- Punkte-Bilanz: gleiche Punktgröße, alphabetisch — Fairness gilt auf
  jedem Gerät.

## Sonst noch Vertrag

- Direktbeschriftung sparsam (Endwerte, größte Differenz); alles andere
  über die Ableseleiste. Kein Tooltip — was nur beim Hovern existiert,
  fehlt im Ausdruck, im Screenshot und in der Vorlesehilfe.
- SVG: viewBox = gemessene Containerbreite (`lib/use-breite.ts`), Faktor
  1,0. `role="group"` (nicht `img`) + `AbleseBeschreibung` als sr-only.
- Gendern mit Sternchen („Einwohner*in"). Ehrliche Mengen: nie „viele",
  immer Zahl + Zeitraum.
- Der Bereich liegt hinterm Umgebungs-Gate (`lib/haushalt-frei.ts`) — die
  Seiten prüfen es, die Komponenten nicht.
