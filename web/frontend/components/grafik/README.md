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
| `d3-hierarchy` | `treemapSquarify` (Kachelfläche, s. `kachelflaeche.ts`) |

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

**Eine Lücke ist nicht dasselbe wie ein Stillstand.** Wo zwischen zwei
Punkten nichts fehlt, sondern nichts passiert ist — ein Hebesatz gilt, bis
der Rat ihn ändert —, gehört keine Lücke in die Reihe, sondern
`<Zeitreihe treppe>`: Der Wert hält bis zum nächsten Punkt und springt dort.
Beides sind Formen desselben Vorsatzes, nichts zu erfinden; die gerade
Verbindung dazwischen wäre in beiden Fällen die einzige Lüge.

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

## Bisher gebaute Grafiken

| Grafik | Datei | Vertrag (Kurzform) |
|---|---|---|
| `<Zeitreihe>` (GB-01) | `zeitreihe.tsx` | Linien-Zeitreihe: `reihe: JahrPunkt[]` · `einheit` · `titel?` (Kopfzeile mit gemessener Menge) · `zweitreihe?` (dünn, gestrichelt, breit am Endpunkt beschriftet) · `annotationen?` (ⓘ im Bild, `kurz?` daneben, Text IMMER darunter) · `spruenge?` (größter Anstieg/Rückgang, GERECHNET, Signal-Orange als Differenz-Marke — nie über eine Lücke hinweg) · `vorjahresdifferenz?` (Zeile in der Ableseleiste) · `tabelle?` (alle Werte zum Abschreiben) · `umschalter?` (kontrolliert, mobil full-width). `treppe?` (der Wert gilt bis zum nächsten Punkt und springt dort, `curveStepAfter`) · `d3-shape` mit `defined(vorhanden)` bricht die Linie an Lücken — Interpolation ist im Code unmöglich. Direktbeschriftung sparsam (Endwerte, größte Differenz), Rest über die Ableseleiste; Achse `d3-scale` nice ticks, mobil nur Dekaden. Einsatz: Schulden, Hebesatz-Treppe (Steuer-Steckbrief). |
| `<ZeitreiheMini>` (GB-01 mini) | `zeitreihe.tsx` | Karten-Sparkline: gleiche `defined()`-Lückenbrüche, Endpunkt-Beschriftung bleibt auf jedem Gerät (H4-11), Nulllinie bei Vorzeichenwechsel, `role="img"` mit ganzem Satz. Ohne Achsen und Ableseleiste — die große Kennzahl daneben ist die Auskunft. |
| `<NahtSaeulen>` (GB-02) | `naht-saeulen.tsx` | `jahre {jahr, teile[] \| fehlt}[] · naht? {zwischen, text} · gruppierungMobil · einheit`. Zwei Farbwelten links/rechts der Naht (aus-/ein-Rampe), erzwungen — keine Farb-Props. Stapel bündeln nach Größe (Desktop 3, mobil 2 Gruppen), die Ableseleiste trennt ALLE Arten. Trägt eine Reihe nur EINE Art je Jahr, fällt die Zeile „insgesamt" weg (sie stünde sonst zweimal dieselbe Zahl) und die Legende nennt statt der Arten die beiden Abgrenzungen. Lücken: volle Säule + `<LueckenFeld>`, von der Komponente gerendert. Keine Rechnung über die Naht. Die Jahresachse beschriftet immer das letzte Jahr und lässt ein Rasterjahr direkt davor weg (bei 54 Säulen stand dort sonst „2425"). Einsatz: Gebaut, Übersicht (lange Ausgabenreihe). |
| `<RanglisteSchiene>` (GB-03) | `rangliste-schiene.tsx` | `zeilen {label, wert, hervorgehoben?, zusatz?}[] · schiene ("null-bis-max" \| [min, max]) · einheit · mittelmarke?`. Schiene immer sichtbar (Null-Basis); `hervorgehoben` findet, bewertet nie — eine Grün/Rot-Prop existiert nicht. Mobil wandert das Label über den Balken (eingebaut, kein Prop). Einsatz: Investitionen (mobil, via Treemap). |
| `<MeldeRangbalken>` | `melde-rangbalken.tsx` | Schmale Null-bis-Max-Schiene der Bürgerportal-Rangzeile: `wert · maximum · haeufigkeit`. Die Fülllänge ist exakt proportional und hat bewusst keine Mindestbreite; die lesbare exakte Zahl steht daneben. Keine Animation. Einsatz: „Meistgemeldet“. |
| `<Gegenbalken>` (GB-04) | `gegenbalken.tsx` | Ein oder zwei 100-%-Leisten auf **einer** `basis` — asymmetrische 100 % sind nicht konstruierbar. `restLabel` benennt die Lücke zur Basis (Schraffur + Signal), `marke` den Differenz-Strich. Segmente < 10 % nie im Balken beschriftet; verbindlich ist die Legende darunter. `SegmentText` (gemessene Beschriftung) exportiert auch für den Tafel-Gegenbalken (`components/haushalt/gegenbalken.tsx`). Einsatz: Pflicht, Bereichs-Steckbrief (Kopf-Tafel). |
| `<Hantel>` (GB-05) | `hantel.tsx` | `zeilen {label, plan, ist, einordnung}[] · massstab ("prozent" \| "betrag") · sortierung ("abweichung" Default \| "alpha") · schwelle?`. `einordnung` ist Pflicht-FELD — eine Hantel ohne Erklärsatz kompiliert nicht (`null` = „Quelle erläutert nicht", ausgeschrieben). Verbindung immer Orange, Punkte nie farbcodiert; Achse trägt ihre Einheit selbst. Verallgemeinert aus der früheren `components/haushalt/hantel.tsx` — deren Kopfkommentar (Abweichungs-Achse, keine Log-Skala, **keine Bewertungsfarben**) ist mitgewandert und bleibt die Referenz des Bereichs. Einsatz: Plan-Ist, Bereichs-Steckbrief. |
| `<Waffel>` (GB-06) | `waffel.tsx` | `gesamt · proQuadrat · markiert {anzahl, grund, stichtag} · einheit · grundLabel`. Markierung immer Signal-**Umriss**, nie Fläche; Stichtag und Rundungszeile rendert die Komponente. 14 Quadrate je Reihe, mobil 10 à 13 px (CSS `.gb-waffel`). Nicht interaktiv, `role="img"`. Einsatz: Personal. |
| `<Flussbild>` (GB-07) | `flussbild.tsx` | Quellen → **ein** Topf (→ Empfänger). Bewusst KEIN Sankey — kein Band überquert die Mitte, `d3-sankey` bleibt draußen. Mobil kippt es senkrecht (Listen-Fassung, eingebaut); kleine Posten bündeln sich in einen aufklappbaren Sammelposten, Differenz-Bänder nie. Daten und Skala liefert die Seite (Haushalts-Adapter: `components/haushalt/flussbild.tsx`). Einsatz: Übersicht, Einnahmen (geplant). |
| `<Treemap>` (GB-08) | `treemap.tsx` | `knoten {key, name, wert, gruppe, zusatz?}[] · farbe(gruppe) · textFarbe?(gruppe) · buendelnAb · treffer? · aufRest? · nomen? · flaecheLabel? · verworfenSatz? · anteil?`. Fläche ∝ Gesamtsumme (Geometrie in `kachelflaeche.ts`, zur Laufzeit), Rest-Kachel ist Pflicht, **wo gebündelt wird** (neutral schraffiert — gebündelt ist keine Lücke); zerlegt die Fläche eine geschlossene Liste, rechnet die Seite den Schnitt mit `buendelGrenze()` und gibt `restZusatz` (die Aufzählung der gebündelten Posten — steht in Ablesezeile, Legende und Mobil-Zeile) sowie `anteil` mit, dann nennt die Ablesezeile den Prozentwert. Der Sammelposten selbst ist ablesbar wie jede Kachel: Hover, Fokus und (ohne `aufRest`) Antippen zeigen ihn in der Zeile unterm Bild. `textFarbe` ist Pflicht auf einer Karte: `--hh-seg-text` trägt nur das laute Ende der Rampe, den Rest sagt `rampenText()`. Die Wörter (`nomen`, `flaecheLabel`, `verworfenSatz`) kommen von der Seite — die Vorgaben sind der Investitionen-Fall. Nur positive Werte; Verworfenes steht als Satz. Unter 520 px Containerbreite rendert sie selbst eine `<RanglisteSchiene>` — gleiche Daten, gleiche Sortierung (H4-A). Einsatz: Investitionen-Explorer, Herkunftsseite des Flussbilds. |

| `<PunkteBilanz>` (GB-09) | `punkte-bilanz.tsx` | `zeilen {fraktion, farbe?, gremien {fa {ein, durch}, rat {ein, durch}}}[] · beleg?`. Verhandlungsbilanz: jeder Punkt eine Abstimmung über eine Änderungsliste, gefüllt = fand Mehrheit. **Fairness als API**: keine Prozent-Prop, Sortierung alphabetisch FEST in der Komponente, Punktgröße 11 px erzwungen, Fraktionsfarbe nur als 8-px-Identitätspunkt. Mobil je Fraktion eine Karte mit FA/RAT-Zeilen. Einsatz: Streit. |
| `<KettenMatrix>` (GB-10) | `ketten-matrix.tsx` | Feststellung × Jahr: `ketten` · `jahre` · `lueckenJahre` (rendern in JEDER Zeile + als `<LueckenFeld>` ÜBER der Matrix) · `marken` = Legende **aus der Quelle**, nie geraten. B/WB Signal-Orange (Abweichungs-Kategorie), H Rampen-Blau, K neutral. Mobil Karten-Liste mit Chip-Zeile, nie horizontal scrollen; Tastatur ↑/↓ je Kette, Enter klappt den Wortlaut (`detail`) auf. |
| `<Zeitstrahl>` (GB-11) | `zeitstrahl.tsx` | `stationen {label, von, bis?, gemessen, offen?, ungefaehr?, href?}[] · heute · termin? {label, datum, quelle: "kalender"}`. Liegender Verfahrens-Strahl (`scaleTime`, d3-time-Ticks) mit „Sie sind hier"-Pin. `gemessen` ist Pflicht je Station — der Strahl behauptet nichts Ungezähltes; `ungefaehr` = Lage aus früheren Jahrgängen gemessen („≈"), `termin` nur aus dem Ratskalender. Unter 744 px kippt er senkrecht, Pin und Termin sortieren sich als eigene Einträge ein (H4-A). Einsatz: Jahr. |
| `<SlopePaar>` (GB-12) | `slope-paar.tsx` | `paare {label, vorher, nachher, hervorgehoben?}[] · bruchLabel (Pflicht) · vonLabel · bisLabel · einheit`. Ein Slope über einen Systembruch ohne Label ist nicht baubar; „unverändert" wird ausgeschrieben, nie als flache Linie versteckt. Mobil automatisch Delta-Liste, der Bruch bleibt Trennzeile. Einsatz: Vergleich (Grundsteuer-Sprung). |
| `<Kassenzettel>` (GB-13) | `kassenzettel.tsx` | `posten` · `teiler` (Bezugsgröße + Stichtag + Quelle, sichtbar **unter** dem Zettel) · `bezahltMit` · `nichtAussagen` (**Pflicht** — der Bon reist nie ohne seinen Kasten). Rundungszeile automatisch. Einsatz: Übersicht (Pro-Kopf-Bon). |
| `<Wasserfall>` (GB-14) | `wasserfall.tsx` | `schritte {label, wert, art: start·abzug·ergebnis}` — Abzüge hängen per `cumsum` (d3-array) an der Laufsumme, kein „schwebender Balken" von Hand. Eingebaute Summenprobe meldet Rechenfehler der Seite; das Ergebnis ist nie rot (Zuschussbedarf ist Daseinsvorsorge). Einsatz: derzeit keiner — der Bereichs-Steckbrief zeigt seine Rechnung seit 24.08.2026 als GB-04 auf der Kopf-Tafel („dass ein Abzug an der Laufsumme hängt, muss man wissen", Tims Befund; die Form bleibt für Rechnungen mit MEHREREN Abzügen, wo GB-04 nicht trägt). |

## Kachelfläche (`kachelflaeche.ts`)

Dieselbe Bauart wie `skala.ts`: Was sich nachrechnen lässt, wohnt in einem
kopflosen Modul, damit `scripts/pruefe-kachelflaeche.mjs` es in der CI prüfen
kann. Drei Regeln, die typkorrekt falsch sein können und nur auf einem
Bildschirm auffallen:

- **`QUADRATISCH`** — `treemapSquarify.ratio(1)` statt des goldenen Schnitts.
  Auf φ bekam der kleinste Ertragsposten (1,8 von 788,6 Mio. €) bei 854 px
  Containerbreite eine Kachel von 100 × 5 px; ein 5-px-Streifen liest sich als
  Zeichenfehler, nicht als kleiner Anteil. Gemessen über 520–1200 px, beide
  Datensätze: Splitter unter 10 px 0,20 → 0,00 je Breite, unbeschriftete
  Kacheln 1,56 → 1,47 (Erträge) und 0,54 → 0,16 (Investitionen).
- **`namenszeilen(breite, hoehe)`** — wie viele Zeilen der Name bekommt.
  Ohne sie schnitt `overflow-hidden` mitten im Wort ab („Transferer-" mit
  angeschnittenem „träge" darunter). Jetzt klammert `-webkit-line-clamp` mit
  Auslassungszeichen; vollständig steht der Name in der Ablesezeile und in
  der Legende.
- **`buendelGrenze(werte)`** — ab welchem Rang der Sammelposten übernimmt:
  das größte `ab`, bei dem über die ganze Breitenspanne JEDE Kachel (die
  Rest-Kachel eingeschlossen) ihre Beschriftung trägt. Beide Richtungen können
  schiefgehen: ohne Bündeln stand „Eigenleistungen" (0,23 %) überall
  unbeschriftet da, ein zu später Schnitt macht die Rest-Kachel selbst zum
  Splitter (Rang 8 → 1,4 % → an 75 von 171 Breiten unlesbar). Die Probe prüft
  den Vertrag (beschriftet + maximal), nicht die konkrete Zahl.
- **`rampenText(rampe, stufe)`** — `--hh-seg-text` ist für die Anzeigetafel
  gemacht (Rampe endet bei 69 %). Auf einer KARTE läuft die Rampe bis 90 bzw.
  93 % weiter, und weißer Text landet dort auf fast Weiß: „Krippenausbau 2022"
  stand auf `--hh-aus-8` mit **1,25 : 1**. Die Grenze liegt bei Stufe 1 (ein)
  bzw. 2 (aus), danach `--foreground`; schlechteste Stelle 4,41 : 1 (ein,
  Stufe 1, hell) und 4,30 : 1 (aus, Stufe 3, dunkel) — beides die Mitte der
  Rampe, wo KEINE der beiden Farben 4,5 : 1 erreicht. Die Probe rechnet die
  Tabelle gegen `app/globals.css` nach und verlangt die bessere der beiden.

## Zahlen (`format.ts`)

`Intl.NumberFormat("de-DE")`, gecacht. `deZahl` (feste Nachkommastellen),
`mitVorzeichen` (Differenzen: „+12,4", Null ohne Plus), dazu `deMio` und
`betrag` aus `lib/haushalt`. Kein `toLocaleString` in Komponenten.

## Skala (`skala.ts`)

Zwei Regeln, die `<Zeitreihe>` aus dem Modul holt statt sie selbst zu rechnen —
damit `scripts/pruefe-skala.mjs` sie in der CI nachrechnen kann (Node liest die
`.ts` direkt; die Probe prüft das echte Modul, keine Kopie).

- **`ySpanne(werte, nullbasis)`** — `nullbasis` heißt „die Null gehört ins
  Bild", **nicht** „die Null ist unten". Vorher stand dort `[0, max]`; eine
  Reihe ganz im Minus bekam damit die umgedrehte Spanne `[0, −2,65]` und ihr
  eigenes Minimum lag außerhalb — die Kurve lief oben aus dem Bild. Gemischte
  Reihen brach dieselbe Zeile.
- **`achsenStellen(gitter)`** — Nachkommastellen aus dem **Raster**, nicht aus
  dem `nachkomma` der Reihe. Sonst stünde an der Schuldenkurve „300,0" statt
  „300", und unter einer Million dreimal „0" übereinander.

Beide Fehler waren typkorrekt und nur auf einem Bildschirm zu sehen. Wer hier
etwas ändert, lässt die Probe laufen: `node --experimental-strip-types
scripts/pruefe-skala.mjs`.

## Farben & Motion

- Haushaltsgrafiken verwenden nur die Rampen-Tokens `--hh-ein-*` /
  `--hh-aus-*` (app/globals.css) — hell/dunkel kommt gratis. Auf der
  Anzeigetafel (`.hh-tafel`) binden die Rampen an die FLÄCHE; Komponenten
  schreiben keine Sonderfarben. Der spezialisierte `<MeldeRangbalken>` nimmt
  ebenfalls keine Farb-Prop: Er verwendet dieselben zentralen
  `frequency-*`-Klassen wie die Problemkarte, weil genau diese gemeinsame,
  beschriftete Hafenblau-Skala Teil ihres Datenvertrags ist.
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

Der 744-px-Schwellwert steht in den Komponenten als arbiträre Variante
`[@media(min-width:744px)]:` — Tailwinds `min-[…]`-Kurzform ist in diesem
Projekt AUS, weil die `screens`-Konfiguration raw-Werte enthält (`breit`/
`desk`/`tab`) und Tailwind die Varianten dann nicht sortieren kann.

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
