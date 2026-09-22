# Ratslotse — Designsprache

Stand: 11.09.2026 · destilliert aus allen Design-Artboards dieses Projekts
(Ist-Screens, Kommunalwahl, Ratsgespräch 1a–8d). Referenz für Claude Code:
Bei jedem neuen Screen gegen diese Datei bauen; die Artboards zeigen die Anwendung.

## 1. Markenkern

- **Charakter:** ruhig, bürgernah, quellen-ehrlich. Amtliches wird lesbar, nie reißerisch.
- **Du-Form**, konkrete Verben, kurze Sätze. Kein KI-Vokabular: „Frag den Rat",
  „Gründliche Recherche" — nie „Prompt", „Agent", „Deep Research", „LLM".
- **Ehrlichkeit ist Designprinzip:** Disclaimer haben feste Orte (nicht wegklickbar,
  nicht aufdringlich); Paraphrasen kursiv ohne Anführungszeichen; keine erfundenen
  Grafiken (kein Stimmverhalten — das RIS kennt keins); Externes klar markiert.
- **Lotti (Maskottchen):** Beobachterin und **Erklärerin**, nie Autorin einer
  Ratsauskunft. Sie erklärt, was auf dem Bildschirm steht — ein Fachwort, eine
  Zahl, einen Baustein, eine Seite — und reicht Ratsfragen an „Frag den Rat"
  weiter; deren Antworten kommen weiterhin „aus den Beschlüssen", nicht „von
  Lotti". Erlaubt bleiben Empty States, Ladezustände, „nichts gefunden",
  Consent-Momente und die Tour. **Ihr Fenster öffnet sich nie von selbst.**
  Posen via mascot.tsx: wave / search / confused / point — feiner über `regung`
  aus dem Sprite-Katalog (/lotti/katalog.html). **Jede Regung ist an einen
  Zustand gebunden:** Was etwas bedeutet (jongliert = Recherche läuft, erklärt =
  Erklär-Kasten, schreibt = Lotti antwortet gerade, klatscht = geschafft), darf
  nie zufällig passieren — von selbst blinzelt und nickt die Figur nur.

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
| Sekundär / Muted / Labels | hsl(207 18% 38.5%) · iOS #506474 |
| **Primär „Hafenblau"** | hsl(205 92% 34%) |
| **Signal-Orange** (nur Akzent: KI-Funken, Marker und Deltas ohne Wertung) | hsl(19 92% 55%) |

### Dunkel
Seite hsl(213 50% 7%) · Karte hsl(212 42% 11%) · Rahmen hsl(211 36% 17%)
(interaktiv 21%) · Text hsl(204 40% 96%) · Muted hsl(206 23% 72.5%)
(iOS #A9BBC9) ·
Primär hsl(202 90% 60%) (Text darauf dunkel!) · Signal hsl(19 95% 60%).

### Semantik (Tints, nie Vollfarben-Flächen)
- Erfolg/Angenommen: #dcfce7 / #15803d
- Fehler/Abgelehnt: #fef2f2 + Rahmen #fecaca / #b91c1c
- Warnung/Vertagt/Limits: #fffbeb + #fde68a / #92400e
- Neutral/Zur Kenntnis: hsl(206 40% 94%) / hsl(209 18% 42%)
- Primär-Tints: bg primary/4–10, Rahmen primary/16–30 (Nutzer-Bubble: bg /7, Rahmen /18)
- **Admin-Vergleiche:** günstige Entwicklung grün, ungünstige rot, ohne eindeutige
  Wertung gelb; „unverändert“ neutral. Pfeil und Vorzeichen bleiben zusätzlich
  sichtbar. Bei „Antworten ohne Quelle“ und „Rückfragen statt Antwort“ ist
  weniger günstig. Die Farben gelten für Änderungs-Chips, nicht für Balken.

### Parteifarben (nur 8-px-Dots & 9-px-Tags, nie Flächen)
SPD #e3000f · CDU #1a1a1a · Grüne #3d8f29 · FDP #ffe000 (heller Dot: Inset-Ring
rgba(0,0,0,.15)) · AfD #009ee0 · Linke #e6007e · BSW #7d254f · Gruppen: neutraler
Dot hsl(209 18% 65%), kombiniertes Label.

**Die eine Ausnahme: die Karte der Stichwahl** (`stichwahl-karte.tsx`, Tims
Entscheidung 15.09.2026). Zwei Namen auf einem Stimmzettel, eine Frage je
Bezirk — „wer liegt hier vorn" — und die beantwortet eine Fläche in der Farbe
der Person: Prange in SPD-Rot, Rohr in Orange (#e8590c / #ff8a3d), nicht in
Grün, weil er parteilos antritt und Rot neben Grün die Ampel wäre. Die
Deckkraft trägt den Vorsprung (50 % = kaum Farbe), offene Bezirke halb so
kräftig und gestrichelt. Bei Listenwahlen mit sieben Farben bleibt es bei
der Primärtönung.

## 3. Typografie

- **Inter** 400/500/600/700 — UI und Fließtext. Die Leserollen unten gelten
  für Beschlussdetails, Antworten, Quellen und Verarbeitungshinweise.
- **Bricolage Grotesque** 600/700 — nur Titel, Abschnittsüberschriften (15–16),
  große Beträge (22–30, tabular-nums). Nie im Fließtext.
- **IBM Plex Mono** 400/500 — Kicker, Datum · GREMIUM-Zeilen, Attributionen,
  Scores. Inhaltliche Metadaten 13; Kicker mit zurückhaltender Laufweite
  (etwa 0.06–0.08em), lange Angaben dürfen umbrechen.
- Fußnote [n]: 16×16 Chip, Radius 4, bg primary/10, Text primary 10/700;
  zitiert-aktiv: gefüllt primary, Text weiß.

### Leserollen (Web und iOS)

| Zweck | Web-Utility | iOS `RatsFont` | Grundgröße / Zeilenhöhe Web |
|---|---|---|---|
| Kurzfassung, amtlicher Wortlaut, Antwort, Begründung | `text-lese` | `reading()` | 17 / 1.6 |
| Quellentitel, Dokumentnamen | `text-quelle` | `sourceTitle()` | 16 / 1.5 |
| Datum, Gremium, Vorlagennummer | `text-meta` | `metadata()` | 13 / 1.5 |
| KI-, Verarbeitungs- und Quellenhinweis | `text-hinweis` | `notice()` | 14 / 1.6 |

Die Webgrößen stehen in `tailwind.config.ts` in **rem**; iOS verwendet
skalierende Custom Fonts mit Dynamic Type. Kein Schrumpfen per
`minimumScaleFactor`, um Inhalt in eine zu kleine Zeile zu pressen.

**Weniger wichtig heißt nicht schlechter lesbar.** Relevanter Text trägt
deckende Farbe; kein zusätzliches `/60`, `/70` oder `opacity` auf Hinweis,
Metadaten oder ganzer Quellenzeile. Der gedämpfte Text hält auf Karte,
Seite und Tonfläche in beiden Themes mindestens 4,5:1; #506474 auf Weiß
liegt bei etwa 6,15:1. Orange Beschriftung braucht die dunklere Textfarbe
(Web `orange-800` / dunkel `orange-300`, iOS `signalInk`).

**Mehr Schrift braucht Höhe.** Quellentitel und ihre Metadaten werden
vollständig umbrochen, auch in schmalen Belegespalten. Textauszüge dürfen
eine Vorschau bleiben, wenn die Quelle erreichbar ist; ein langer
Begründungstext behält „Mehr anzeigen“. Hinweise werden nie abgeschnitten.
Auswahlknöpfe umbrechen oder stapeln sich, Text-Dialoge scrollen bei Bedarf.
Abnahme: echte lange Titel, Hell/Dunkel, doppelte Web-Schriftgröße und große
iOS-Schrift.

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
- **Anzeigetafel (`.hh-tafel`) — die abgesetzte Fläche.** Neben der *Bühne*
  (Tonfläche, s. o.) gibt es eine zweite Sonderfläche: der Blickfang, auf dem
  die eine Zahl steht, um die es auf einer Seite geht (Haushalts-Einstieg;
  seit 24.08. auch der Kopf des Bereichs-Steckbriefs — Titel, drei Summen in
  der Tafel-Type, darunter das Kern-Visual).
  Sie war bis 16.08. in **beiden** Themes dunkel — im Hellmodus ein
  schwarzblaues Feld über die halbe Seite, „sieht sehr dunkel aus" (Tim).
  Jetzt folgt sie dem Theme. Drei Regeln, sonst wird sie falsch:
  - **Nie die Farbe der Seite, immer plus Rand.** Hell hsl(205 52% 92%) auf
    einer Seite von 97,5 % (Rand hsl(206 38% 82%)), dunkel hsl(212 44% 12%)
    auf 7 % (Rand hsl(211 36% 19%)). Gleich wie die Seite hieße: Die Kernzahl
    steht im Nichts. Der Unterschied zur Bühne ist der Zweck — die Bühne
    trägt einen Container, die Tafel eine Aussage.
  - **Datengrafiken binden ihre Farbrampe an die FLÄCHE, nicht ans Theme.**
    Die Rampen `--hh-ein-*`/`--hh-aus-*` gelten für Grafiken auf einer
    **Karte**. Die Tafel ist keine Karte: Im Hellmodus endet die Karten-Rampe
    bei 90–93 % Helligkeit und läge ein bis zwei Punkte neben ihrem Grund,
    im Dunkelmodus lagen die Enden 3–6 Punkte über der Fläche. `.hh-tafel`
    setzt deshalb nicht nur den Hintergrund, sondern auch `--card`,
    `--border`, `--muted-foreground`, `--primary`, `--signal` und beide
    Rampen neu — je Theme einmal. Wer eine Grafik auf eine solche Fläche
    stellt, schreibt keine Sonderfarben in die Komponente, sondern verlässt
    sich auf die Token — und prüft die Fläche in beiden Themes.
  - **Zwei Maße, beide messen, keines schätzen.** Das ferne Rampenende hält
    mindestens **14 Helligkeitspunkte** Abstand zum Grund *und* mindestens
    **1,65 : 1** WCAG-Kontrast. Die zweite Zahl braucht es, weil dieselbe
    Punktzahl am hellen Ende viel weniger Kontrast bedeutet als am dunklen:
    Ist heute dunkel 14 Punkte / 1,65 : 1, hell 23 Punkte / 1,81 : 1. Und
    Segmente, die eine Beschriftung tragen können, halten gegen
    `--hh-seg-text` 4,5 : 1 — das sind hell die sechs dunkelsten Stufen der
    Ausgaben-Rampe (unter 48 % Helligkeit, weißer Text), dunkel die vier
    hellsten (über 55 %, dunkler Text).
  Die Fuge zwischen Feldern einer Grafik ist `--hh-raster` (die Farbe der
  Fläche), nicht `--card`: Auf der Tafel sind das zwei verschiedene Farben.
- **Ebenen & Abdunkler:** Fünf benannte Stufen, definiert in `app/globals.css`
  (`--ebene-huelle` 40 · `--ebene-schwebend` 60 · `--ebene-flaeche` 100 ·
  `--ebene-dialog` 110 · `--ebene-meldung` 120) — eine neue Ebene wird dort
  eingetragen, nicht als freie Zahl in die Komponente geschrieben. Der
  Abdunkler unter jedem Dialog ist die Klasse `.scrim` (schwarz 50 % / dunkel
  62 %), nie eine handgemischte Farbe: `rgba(9,17,27,0.42)` im Blatt „Thema
  anpassen" war exakt die dunkle Seitenfarbe und dunkelte im Dunkelmodus
  nichts ab (4,7 von 255 Stufen statt 98) — Kopfzeile und Tab-Leiste
  behielten ihren Glas-Look und standen scheinbar VOR dem Dialog. Ein
  mittiger Dialog lässt die App-Hülle frei (Kopfzeile und Tab-Leiste sind je
  ~61 px + Sicherheitszone hoch); ein Blatt an der Unterkante deckt die
  Tab-Leiste bewusst ab.
- **Zwei getrennte Fragen: „Wie viel Platz?" und „Womit bedient?".** Dafür gibt
  es drei Breakpoints, und sie dürfen nicht vermischt werden:
  - `breit` (`min-width: 1024px`) — **Platz.** Alles, was nur Breite braucht:
    Spaltenraster, Belege-Spalte neben der Antwort, mehrspaltige Formulare.
  - `desk` (`(pointer: fine) and (min-width: 1024px)`) — **Maus.** Alles, was
    zur Seitenleiste gehört: Kopfzeile mobil, Tab-Leiste, statischer Composer,
    viewport-gebundene Chat-Bühne, Pflicht-Links im Fuß.
  - `tab` (`(pointer: coarse) and (min-width: 1024px)`) — **breites Touch-
    Gerät.** Für das, was nur dort zu klären ist: Ausrichtung des fixierten
    Composers auf die Lesespalte, Abstand zur Tab-Leiste.
  - `maus` (`(pointer: fine)`) — **nur Eingabegerät, ohne Breiten-Gate.** Für
    Bedienhilfen, die einen Präzisions-Zeiger voraussetzen und die Touch nie
    braucht: die Blätter-Pfeile an Chip-Zeile und Steckbrief-Karussell. Ein
    Desktop-Fenster in halber Breite behält sie, ein iPad bekommt sie nie.

  Ein iPad ist quer 1180–1366 px breit und bekäme die Seitenleiste sonst allein
  wegen seiner Breite — dort gehört die Navigation aber an den Daumen (Tims
  Befund 14.08.). Umgekehrt bekam es lange gar nichts von der Breite ab: Der
  Gespräche-Knopf hing mobil an `md:hidden`, sein Ersatz an `desk:` — zwischen
  768 px und Maus zeigte **keiner** von beiden, und die Quellen standen im
  Textfluss statt daneben (Tims iPad-Befunde 15.08.). Deshalb die Dreiteilung:
  Wer eine Regel schreibt, fragt zuerst, ob sie am Platz oder am Eingabegerät
  hängt. `desk` und `tab` schließen einander aus, damit keine Regel von
  Tailwinds Ausgabereihenfolge abhängt.
- **Karten-Raster: Container-Query statt Fenster-Stufe — und Spalten statt
  Zeilen.** Am Desktop liegt ein Raster neben der 240-px-Seitenleiste, auf dem
  iPad nicht: Dieselbe Fensterbreite meint zwei verschiedene Platzangebote.
  Spaltenzahlen hängen deshalb an `@container` (Schwelle 768 px = zwei
  Spalten), nicht an `lg:`. Und ein `grid` füllt ZEILEN — jede Zeile wird so
  hoch wie ihre höchste Karte, unter der kurzen Nachbarin bleibt also Leere
  stehen. Wo Karten sehr verschieden hoch sind, sind die Rasterkinder darum
  **Spalten** (`flex flex-col gap-6`), die je für sich stapeln; welche Karte
  in welche Spalte gehört, entscheidet der Inhalt, nicht die Höhe (Konto-Seite,
  Tims iPad-Befund 16.08.: 459 × 494 px Leerfläche neben einer Karte, die
  weiter unten noch lange nicht zu Ende war). Die
  Breite deckelt die Hülle (`max-w-7xl` im App-Layout) — ein eigenes
  `max-w-*` auf einem Raster verschenkt genau den Platz, den das Gerät hat.
- **Lesebreite: den KASTEN deckeln, nicht den Text darin.** Ein `max-w-[76ch]`
  an einem Absatz in einer 1.496 px breiten Karte lässt rechts 870 px leer, und
  eine halb gefüllte Kiste sieht nicht nach Absicht aus, sondern nach Fehler
  (Tim, 21.08.: „hier ist der ganze rechte Bereich frei, das sieht absolut
  scheiße aus"). Der Deckel ist trotzdem richtig — ohne ihn läuft Fließtext auf
  einem breiten Schirm über 145 Zeichen je Zeile (gemessen bei 976 px Karte,
  13 px Text; auf 21:9 sind es 220), und dort verliert das Auge beim Rücksprung
  die Zeile. Er gehört nur an eine andere Stelle. Fünf Fälle, fünf Antworten:
  - **Ein Einschub** (`aside`, „Lotti erklärt's einfach") deckelt sich SELBST.
    Der Leerraum liegt dann außerhalb des Kastens — er ist Seitenrand statt
    Loch, und dass ein Einschub schmaler steht als der Fluss, sagt genau das
    Richtige über ihn aus.
  - **Eine Aufzählung** in einer breiten Karte („Was diese Zahlen nicht
    hergeben") läuft in ZWEI Spalten (`@3xl:grid-cols-2` am `<ul>`,
    `@container` an der Sektion). Fläche gefüllt, Zeile lesbar. Das gilt auch
    für eine Folge kurzer **beschrifteter Absätze** (`dl` aus `dt`/`dd`) —
    untereinander sind vier davon vier halbe Zeilen, nebeneinander eine
    gefüllte Karte (Zuwendungs-Block auf `/haushalt/einnahmen`, Tim 24.08.:
    „der Text ist auch hier nur halbseitig"). Ein Stück, das eine Liste
    mitbringt, spannt sich dabei über beide Spalten (`col-span-2`).
  - **Ein langer Fließtext, der SELBST der Inhalt der Karte ist**, läuft
    ebenfalls in Spalten — dann aber als Textfluss, nicht als Raster:

    ```
    <section className="@container rounded-2xl … p-4">
      <p className="max-w-[76ch] @3xl:max-w-none @3xl:columns-2
                    @3xl:gap-x-8 @6xl:columns-3">
    ```

    Der Deckel bleibt für die schmale Karte stehen, oberhalb der Schwelle
    übernehmen die Spalten. Gemessen über alle Kartenbreiten hält das die
    Zeile zwischen **rund 56 und 95 Zeichen** und lässt nie ein Loch (am
    schmalsten direkt an einer Schwelle, wo die neue Spalte gerade erst
    hineinpasst):

    | Karteninhalt | Spalten | Zeichen (13 px) | Zeichen (11,5 px) |
    |---|---|---|---|
    | 566 px | 1 | 89 | 95 |
    | 736 px | 1 | 95 | 95 |
    | 942 px | 2 | 70 | 79 |
    | 1.118 px | 2 | 82 | 95 |
    | 1.366 px | 3 | 64 | 76 |

    Die Schwelle misst den **Innen**raum der Karte, nicht ihre Außenkante:
    Eine Karte mit `p-4` und 1 px Rahmen braucht 802 px Außenmaß, damit innen
    die 768 px von `@3xl` zusammenkommen — wer die Schwelle am Fenster
    nachrechnet, liegt um Polster und Rahmen daneben (nachgemessen: bei
    800 px Karte greift sie noch nicht).
    Zwei Bedingungen, sonst wird es schlechter statt besser: Der Text braucht
    **mindestens sechs Zeilen** (sonst stehen zwei Stummel nebeneinander), und
    die Karte muss wirklich breit werden können — in einer Rasterspalte
    (`breit:grid-cols-2`) ist sie es nie, dort greift die Regel von allein nicht.
  - **Ein einzelner Absatz** neben Grafik, Tabelle oder Liste in derselben
    Karte bleibt gedeckelt. Die Karte ist dann nicht leer, und ein Absatz, der
    kürzer ist als die Tabelle darunter, ist normaler Satz.
  - **Eine Grafik füllt den Rest der Zeile nicht, nur weil er da ist.** Eine
    Sparkline neben einer Kennzahl bekam die volle Restbreite und lief über
    700 px bei 46 px Höhe — acht Jahrgänge als flacher Draht. Sie gehört unter
    ihre Zahl; die frei gewordene Spalte trägt Text, der etwas erklärt. Ein
    leeres Feld ist ein Fehler, ein gedehntes Bild aber auch.

- **`ch` ist keine Zeichenzahl. Zwei Umrechnungen, beide gemessen (24.08.2026).**
  Die Zahl in `max-w-[76ch]` sagt nicht, wie viele Zeichen in einer Zeile
  stehen — sie sagt es um rund ein Viertel zu niedrig. Wer eine Lesebreite
  festlegen will, rechnet zweimal um:

  **① `ch` = Breite der Ziffer 0 in der Schrift DIESES Elements.** Nicht der
  Schrift des Textes darin, und nicht 1 em. Gemessen (`measureText`) an unseren
  beiden Schriften, unabhängig von der Größe:

  | Schrift | Gewicht | 1 ch | 1 ch bei 11,5 / 12,5 / 13 / 15 px |
  |---|---|---|---|
  | Inter (`font-sans`, Fließtext) | 400 | 0,631 em | 7,26 · 7,89 · 8,20 · 9,46 px |
  | Inter | 500 | 0,645 em | 7,42 · 8,07 · 8,39 · 9,68 px |
  | Inter | 700 | 0,674 em | 7,75 · 8,43 · 8,76 · 10,11 px |
  | Bricolage (`font-display`, h1–h3) | 700 | 0,665 em | 7,65 · 8,32 · 8,65 · 9,98 px |

  Also: `76ch` an einem `<p class="text-[13px]">` sind 623 px. Dieselben `76ch`
  an einem Kasten **ohne** Größenangabe messen die geerbten 16 px des Body und
  sind 767 px — 23 % mehr, obwohl in der Klasse dieselbe Zahl steht.

  **② Ein `ch` ist 1,26 gerenderte Zeichen.** Die Ziffer 0 ist breiter als ein
  durchschnittliches Prosa-Zeichen: In Inter 400 ist sie 0,631 em breit, das
  mittlere Zeichen unserer deutschen Seitentexte 0,484 em (gemessen über 36.000
  Zeichen echten Haushalts-Textes). Rechnerisch sind das 1,30 Zeichen je `ch`;
  im echten Umbruch bleibt am Zeilenende ein Wort liegen, gemessen über 500
  volle Zeilen im Browser sind es **1,257** — und zwar bei jeder Schriftgröße
  gleich, der Faktor ist reine Geometrie:

  | Klasse | gerenderte Zeichen | Klasse | gerenderte Zeichen |
  |---|---|---|---|
  | `46ch` | 57 | `70ch` | 88 |
  | `52ch` | 65 | `72ch` | 91 |
  | `56ch` | 70 | `74ch` | 93 |
  | `58ch` | 72 | `76ch` | **95** |
  | `62ch` | 78 | `80ch` | 101 |
  | `66ch` | 83 | `86ch` | 108 |
  | `68ch` | 85 | `88ch` | 111 |

  Rückwärts: **gewünschte Zeichen × 0,80 = die Zahl in der Klasse.**

  **Der Haushalts-Bereich steht bei `76ch` ≙ rund 95 Zeichen je Zeile** — das
  ist der gelebte Wert, an dem sich neue Bausteine ausrichten. Die Zahlen 74/76
  tragen die 115 Fließtext-Stellen des Bereichs; wer eine neue schreibt, nimmt
  `76ch` und nicht eine frei gewählte Zahl.

  **Wo der Deckel am Kasten sitzt, trägt der Kasten die Schriftgröße seines
  Textes** — auch wenn sich nichts vererbt, weil jedes Kind seine Größe selbst
  setzt: `<ul class="max-w-[74ch] text-[13px]">`. Ohne die Angabe misst er die
  geerbten 16 px des Body, und dieselbe Zahl bedeutet ein Viertel mehr Breite.
  (Am Text-Element selbst — dem üblichen Fall, 241 der 270 Deckel im Frontend
  — stimmt ① von allein.) Genau daran hingen am 24.08.2026 vier Stellen: Der
  Stations-Fließtext lief auf 122 Zeichen, die Leistungsliste auf 114, der
  Lotti-Kasten auf 101, während der Bereich um sie herum bei 95 stand.

  Und: **nachmessen, nicht nachrechnen.** Rezept im Browser — `Range` über den
  Textknoten legen, `getClientRects().length` sind die Zeilen, per Binärsuche
  den Startoffset der letzten Zeile suchen; `Offset / (Zeilen − 1)` ist die
  Zeichenzahl der vollen Zeilen. Die Zahlen oben stammen genau daher.

## 5. Wiederkehrende Bausteine (Spez im Artboard „Ratsgespräch")

- **Mono-Kicker** über jedem Block: QUELLEN · AKTUELLES VON DER STADT · EXTERN ·
  AUS DEN RATSDEBATTEN · WIE ES WEITERGEHT · ZUM BEISPIEL — plus rechts eine
  ehrliche Zähl-/Zeitraum-Angabe („12 zitiert · 40 gefunden", „2019–2026").
- **Quellen-Zeile** (RG-02): n-Badge + vollständiger Titel in Leserolle
  `quelle`, darunter Gremium · Datum in `meta`; in allen Breiten mehrzeilig.
  Nicht zitierte Treffer bleiben hinter „Alle N Quellen“ / „Weitere“.
  Die kleinen Zitat-Chips im Antworttext bleiben Verweise auf diese Zeilen.
- **Stichwörter am Beschluss:** Themenfeld, Schlagwörter und verknüpfte Themen
  stehen auf dem Handy zunächst hinter einer neutralen Zeile „6 Stichwörter“
  (Web unter 640 px, iOS bei kompakter Breite). Ein Tippen zeigt alle Einträge;
  Themenlinks bleiben bedienbar. Auf großen Displays bleiben die kleinen Tags
  sichtbar. Die Zeile hat mindestens 44 px/pt Bedienfläche, Schriftrolle `meta`.
- **Ergebnis-Badges** (RG-03): Angenommen / Abgelehnt / Vertagt / Zur Kenntnis
  in Semantik-Tints, Radius 9999, 10,5/600. **Badge oder Punkt hängt an der
  Länge der Liste, nicht am Seitentyp** (Tim, 28.08.2026): Die lange, zum
  Überfliegen gedachte Trefferliste der Suche bleibt bei Punkt + Wort
  (`OutcomeDot`) — dort wären zwanzig gefüllte Flächen untereinander Lärm. Wo
  eine Liste kurz und gedeckelt ist und das Ergebnis zur Aussage gehört,
  steht das gefüllte Badge (`OutcomeBadge`): so auf der Themen-Karte, die
  höchstens fünf Beschlüsse zeigt. Beide kommen aus `components/decision-ui.tsx`
  und teilen sich `OUTCOME_META` — die Farben gehen nie auseinander.
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
  36–38 ⌀ primary (disabled: primary/35); ein Verarbeitungshinweis verwendet
  die Leserolle `hinweis`.
- **Composer als Andock-Panel (`tab`)**: Auf breiten Touch-Geräten ist der
  fixierte Balken kein durchgehender Riegel mehr. Er wird durchsichtig und
  klick-durchlässig; sichtbar ist nur ein Panel genau auf der Lesespalte —
  oben gerundet (Radius 16), Rahmen, `bg-card/[0.96]` mit Unschärfe, weicher
  Schatten nach oben, unten bündig auf der Tab-Leiste. Zwei Regeln dahinter:
  Was hinter dem Eingabefeld durchscrollt, muss **gedeckt** sein (rein
  durchsichtig scheitert daran, `/90` ließ im Hellmodus die Karten-Attribution
  durchschimmern), und die Belege-Spalte daneben darf der Balken nicht
  anschneiden (Tims iPad-Befund 16.08.: „der ganze Bereich wird von dieser
  Fläche verdeckt"). Die Andockkante ist `TABLEISTE_HOEHE` aus
  `components/nav.tsx` — nie eine eigene Zahl.
- **Lotti-Knopf und Lotti-Fenster**: Der Knopf schwebt unten rechts auf jeder
  angemeldeten Seite, 56 px rund, darin der **Kopf der 3D-Lotti**
  (`public/lotti/kopf.png`, aus der Ruhe-Pose geschnitten) auf Hafenblau,
  `shadow-lifted`, `z-50`. Das Bild ist größer als der Kreis und wird von ihm
  beschnitten wie ein Porträt; die runde Fläche kommt aus dem CSS und nicht
  aus dem Bild, damit sie im Dunkelmodus den dortigen Primärton nimmt. Er liegt
  über Tab-Leiste und Andock-Composer, deren Höhen als Variablen
  (`--rl-unten`, `--rl-composer`) in seiner Position stehen, nie als eigene
  Zahl. Offen wird er zum Schließen-Kreuz. **Design 9a③ steht dem nicht
  entgegen:** Es hat den *Navigations*-FAB aus der Tab-Leiste genommen; ein
  Chat-Knopf ist keine Navigation, sondern die Bauform, die man von
  Hilfe-Seiten kennt (Tim, 21.09.2026). `BackToTop` rückt über ihn, das
  Küken hält die rechte Ecke frei.
  **Unter dem Zeiger schaut Lotti auf**: Der Knopf hebt sich 2 px, der
  Schatten öffnet sich (`shadow-knopf-hover`), und der Kopf darin richtet sich
  auf — aus seinen +3 px auf 0, 6° geneigt, 5 % größer; `duration-fluss`,
  `ease-out-strong`. Nur unter `maus:` (Touch lässt den Hover kleben) und die
  Bewegung nur unter `motion-safe:` — Farbe und Schatten bleiben auch bei
  reduzierter Bewegung, sonst wäre der Knopf dort gar nicht mehr als
  anklickbar erkennbar. Der Fokus-Ring bleibt der lauteste Zustand; er sitzt
  in `--tw-ring-shadow` und wird vom Hover-Schatten nicht verdrängt.
  Das Fenster sitzt über dem Knopf (Schreibtisch 384 px × max 40 rem, **nicht
  modal**, kein Scrim — die Seite bleibt lesbar und bedienbar; Handy: die
  Fläche zwischen Kopfleiste und Knopf). Anatomie von oben: Kopfzeile (Lotti
  32 px mit Regung nach Zustand · „Lotti" Bricolage 16/700 · Neu anfangen) →
  **Kontext-Pille** in Leserolle `meta` („Du bist auf: … · markiert: …") →
  Verlauf (Frage als Bubble rechts, bg primary/7 + Rahmen /18; Antwort links
  in 13,5 px mit Lotti 24 px daneben; **Tipp-Anzeige** = drei 8-px-Punkte in
  Signal-Orange, die sich mit 160 ms Versatz um 3,5 px heben und senken
  (`lotti-tippt`, 1,1 s, `ease-in-out`), **daneben der Schritt** in
  `text-hinweis`/Muted — „Lotti liest die Seite …", dann „Lotti schreibt …";
  auf dem Ratsweg die drei Schritte der KI-Frage. Die Texte stehen in
  `lib/qa-schritte.ts`, die Schritte selbst meldet der Server als SSE-Rahmen
  `step`. Bis 22.09.2026 waren es 6-px-Punkte mit `animate-pulse` und kein
  Text — „man sieht fast nicht, dass da was lädt" (Tim). Bei reduzierter
  Bewegung blinkt nur die Deckkraft. `role="status"`) → **höchstens ein
  Chip** unter der letzten Antwort → Turn-Fußzeile (Daumen, Textlink) →
  Composer (s. u.).
  **Was unter einer Antwort steht — und was nicht.** Seit 22.09.2026 ist das
  eine Entscheidung über die SUMME, nicht je Element: **ein** Chip mit dem
  nächsten Schritt (Wegweiser › Baustein › Fachwort, `anschlussfragen`),
  darunter die zwei Daumen und — nur unter einer Antwort, die nicht schon aus
  dem Archiv kam — der stille Textlink „Im Ratsarchiv nachsehen". Alles
  gehört der **letzten** Runde auf dieser Seite; ältere tragen nichts.
  Chip-Namen sind Handlungen („Anzeigetafel erklären", „Weiter zu: Woher
  kommt das Geld?"), keine Etiketten. Die **Grund-Chips** („Was sehe ich
  hier?", „Etwas auf der Seite zeigen") stehen nur im leeren Fenster; danach
  trägt der Composer-Platzhalter die Aufforderung und der Erklär-Modus wohnt
  als stilles Icon (`MousePointerClick`) an seiner linken Seite. „Markiertes
  erklären" bleibt, solange etwas markiert ist — er antwortet auf eine
  Handlung, er ist kein Dauerangebot.
  **Und was es NICHT mehr gibt: den Knopf „Den Rat fragen".** Er stand
  gefüllt unter jeder Runde, die ins Archiv weiterreichte. Tims Bild vom
  Bereichs-Steckbrief zeigte ihn zusammen mit zwei weiteren Chips, zwei
  Daumen und zwei Grund-Chips — sieben Bedienelemente für eine Antwort, jedes
  einzeln begründet („Es ist für den User sehr überfordernd"). Und er
  verlangte eine Entscheidung, die niemand treffen kann: „Ich dachte, ich
  frage gerade die Informationen aus dem Rat." Gehört eine Frage ins Archiv,
  geht Lotti seither **von selbst** dorthin — sichtbar (Schritt-Text „Das
  steht nicht auf der Seite — ich sehe im Ratsarchiv nach"), als eine Runde,
  mit Belegen.
  **Darunter nichts mehr.** Bis 22.09.2026 stand dort eine feste Fußzeile
  („Erklärt aus Glossar, Seite und Haushaltsdaten. Keine Rechtsberatung, keine
  Bewertung."); sie ist ersatzlos weg — zwei Zeilen plus Trennlinie kosteten
  dauerhaft gut 30 px Verlaufshöhe für einen Satz, den man einmal liest (Tim,
  22.09.2026). Der **rechtliche** Hinweis hing nie daran: Dass Frage und
  Auszüge extern verarbeitet werden, sagt die Einwilligungs-Karte (einmal,
  vor der ersten Frage, auch in diesem Fenster), dauerhaft nachlesbar die
  Konto-Karte „Gespräche" und die Datenschutzseite. Dass Lotti nicht bewertet
  und nicht berät, setzt der Prompt durch, nicht das Kleingedruckte.
  **Zäsur im Verlauf**: Weil der Verlauf den Seitenwechsel überlebt, steht vor
  der ersten Runde einer neuen Seite eine stille Zwischenzeile „Jetzt auf:
  Schulden" — mono 10 px, Versalien, `tracking-[0.1em]`, Muted, zentriert
  unter einer `border`-dünnen Linie; dieselbe Bauform wie die Kontextzeile an
  einer Frage. Die Linie steht OBEN, nicht links und rechts daneben: Ein
  Beschlusstitel füllt die 384 px allein. Sie ordnet ein, sie ruft nicht:
  keine Farbe, kein Abzeichen, kein Datum; der Name wird bei 60 Zeichen
  gekappt.
  **Fachwörter klappen hier auf, statt zu überlagern.** Ein erklärter Begriff
  (`glossary-text.tsx`) zeigt seine Erklärung sonst als Popover am Wort,
  `absolute left-0 top-full`, bis zu 17 rem breit. Das ist die Form für breite
  Flächen — Haushalts-Seiten, Ratsgespräch. **In Lottis Fenster nicht**: 384 px
  mit `overflow-hidden` schneiden jede Ebene ab, die rechts übersteht, und ein
  Begriff am rechten Rand ist dort halb zu lesen (Tim, 22.09.2026,
  „Wirtschaftsplan"). Ein nach links ausgerichteter Popover löst das nicht —
  beschnitten wird am Fenster, nicht am Wort. Deshalb: `GlossarAufklappBereich`
  um die Antwort, und ein Tipp/Klick (am Zeigergerät auch der Hover nach
  220 ms) klappt **unter dem Absatz** einen stillen Block auf — Radius 8,
  `bg-muted/40`, Rahmen `border`, Begriff fett in Foreground, Erklärung in
  12 px Muted; dieselbe Typo wie im Popover. Höchstens **einer je Antwort**:
  ein zweites Wort ersetzt das erste. Esc schließt ihn (und nur ihn, nicht
  gleich das Fenster), `aria-expanded` sagt, woran man ist. Faustregel: unter
  ~28 rem Textbreite klappt es auf, darüber überlagert es.
  **Anschlussfragen**: In derselben Chip-Reihe stehen unter der LETZTEN
  Antwort höchstens **zwei** weiterführende Angebote — „Erklär mir: <der
  nächste Baustein der Seite, der noch nicht erklärt wurde>" und „Was heißt
  <Fachwort aus der Antwort>?", in diesem Vorrang und nie zweimal dasselbe.
  Reicht die Antwort ins Archiv weiter, ist das gefüllte „Den Rat fragen"
  selbst der erste der beiden, und es bleibt genau ein Chip daneben. Der
  Baustein-Name wird bei 38 Zeichen und am ersten `·` gekappt — ein
  zweizeiliger Chip ist keiner. Die Vorschläge entstehen im Browser aus
  Ankern und Glossar, **nicht aus einem zweiten Modellaufruf**; unter einer
  Fehler-Runde und unter der „Zeig mir"-Runde steht keiner.
  Kein Emoji, kein KI-Vokabular — in der Oberfläche heißt sie nur „Lotti".
  **Kein Zähler und kein Abzeichen am geschlossenen Knopf.**
- **Erklär-Abzeichen**: 28 px rund, `bg-card`, Rahmen primary/30, „?" in
  primary, oben rechts am Baustein (4 px eingerückt), `z-40`. Erscheint im
  Erklär-Modus mit `--takt-fluss`, verschwindet mit `Esc` oder nach der Wahl.
  **Nur auf Elementen mit `data-erklaer`** (`lib/erklaer-anker.ts`) — kein
  Fallback auf „die nächste Karte": Ein geratener Ausschnitt sieht aus, als
  wüsste Lotti, worauf gezeigt wurde. Abzeichen statt Zeigerhand, weil das
  Handy kein Hover hat und eine Zeigerhand ohne Ziel gegen § 6 verstößt. Der
  Modus schließt das Fenster: Die Abzeichen stehen auf der Seite, und mobil
  deckt das Fenster genau sie ab.
- **Anstupser**: eine Sprechblase über dem Lotti-Knopf, max 16 rem, `bg-card`,
  Rahmen, Radius 16, `shadow-lifted`; Lotti 32 px mit `hebt-hand`, der Satz in
  `text-hinweis` („Hast du eine Frage zu dem, was du siehst?"), darunter
  **Ja, frag Lotti** (primary, gefüllt) und oben rechts ein **×**.
  `role="status"` — sie meldet sich, ohne den Fokus zu nehmen. Sie verschwindet
  nach 15 s oder nach 300 px Scrollen von selbst, und **das zählt nicht als
  Ablehnung**: Wer nicht hinsieht, hat nicht Nein gesagt. Kein Ton, keine
  Vibration, kein Zähler am Knopf. **Ihre Grenzen stehen im Code, nicht im
  Ermessen** (`lib/anstupser.ts`): nur auf Leseseiten, nach 45 s sichtbarer
  Lesezeit, nicht in den ersten zwei Seitenaufrufen einer Sitzung, höchstens
  einmal am Tag und dreimal in 30 Tagen, nach zwei × 60 Tage Pause, nach einem
  Ja 14 Tage.
- **Turn-Fußzeile**: KI-Hinweis 14 px + stille Icon-Aktionen 15 px
  (Teilen, Drucken, Vorlesen, 👍/👎) — keine gerahmten Buttons.
- **Schritt-Zeichen (Haushalt)**: Jeder Schritt des Haushalts-Wegs trägt ein
  festes Lucide-Zeichen, definiert EINMAL am Schritt selbst
  (`components/haushalt/wegweiser.tsx`, Feld `zeichen`) und an zwei Stellen
  gezeigt: klein (14 px, muted) in der Wegweiser-Zeile und 15 px im
  „Weiter"-Link am Fuß. Die 64-px-Zeichen-Kachel im Seitenkopf gab es nur vom
  24. bis 26.08.2026 — sie wiederholte das Zeichen groß und sagte sonst
  nichts („hässlich", Tim); an ihrer Stelle steht der Schritt-Pfad (s. u.).
  Kein erfundenes Zeichen: Seiten ohne Schritt (Steckbriefe) bekommen keins.
- **Schritt-Pfad (Haushalt, H5-09)**: oben rechts im Kopf jeder Schritt-Seite
  (`schritt-pfad.tsx`). Zwölf Punkte in den vier Etappen-Gruppen des
  Wegweisers (Gruppen-Lücke 7 px, Punkt-Lücke 3 px): besuchte Seiten gefüllt
  (Lesestand aus `lib/haushalt-fortschritt.ts`, gefüllt = aufgerufen), die
  aktuelle als 8-px-Ring mit Halo (primary/14), offene als Border-Punkt.
  Darunter mono 9 px „SCHRITT N VON 12 · ETAPPE". Der Pfad ist ein Link zum
  Wegweiser (`/haushalt#wegweiser`), verschwindet unter 640 px ersatzlos und
  rendert auf Steckbriefen nichts.
- **Seitenbühne (Haushalt, H5-02/H5-09)**: der Kopf-Blickfang jeder
  Schritt-Seite (`components/haushalt/seitenbuehne.tsx`, Fläche
  `.hh-seitenbuehne` in `app/globals.css`) — die dritte benannte Fläche neben
  Tonfläche und Anzeigetafel, eine Stufe leiser als die Tafel, die exklusiv
  der Übersicht bleibt (Hierarchie Bereich → Seite). Anatomie: Mono-Kicker →
  EINE gemessene Zahl (27/32 px Bricolage, tabular) im bestehenden
  gerechneten Satz der Seite → eine Zeile Einordnung; rechts (224 px, unter
  ~512 px Container gestapelt) das **Minibild**: die verkleinerte Hauptform
  der Seite (Waffel, Treppe, Städte-Leiter …, Töne `--sb-voll/-mittel/-blass`,
  Lücken gestrichelt `--sb-strich`), als Link zum Original-Abschnitt. Die
  Zahl zählt beim ersten Sichtkontakt (600 ms, ease-out³, einmal je
  Seitenaufruf; Sequenzen nur, wo die Reihenfolge die Aussage trägt —
  Schulden-Staffel); bei `prefers-reduced-motion` steht sofort der Endwert.
  Keine Bewertung, keine erfundene Zahl: Ohne Datengrundlage entfällt die
  Bühne. Ausnahmen: das Labor (Werkzeug, keine Lektüre) und der
  Bereichs-Steckbrief (trägt seit 24.08. die Anzeigetafel).

## 6. Interaktions-Grammatik

### Kopf einer einzelnen Sitzung

Der Sitzungskopf bildet eine gemeinsame Karte: leiser Kicker „Sitzung“ und
Anzahl der Tagesordnungspunkte, darunter der Kurzname als einzige Hauptüberschrift.
Der amtliche Name steht bei Abweichung separat in Inter 13, ohne Abschneiden
und ohne die fette Titelschrift zu erben. Eine abgesetzte Informationszeile
ordnet „Termin“ und „Ort“ mit kleinen Icons; das Datum erscheint einmal vollständig,
die Uhrzeit darunter. Adressen bleiben vollständig lesbar. Fehlende Angaben
werden benannt. Breite und Schriftgröße bestimmen, ob die zwei Angaben neben-
oder untereinander stehen.

Kalender, Merken und Teilen stehen gleichwertig in einer abgetrennten
Aktionsleiste; der externe Ratsinfo-Link folgt am Ende. Alle Aktionen haben
mindestens 44 px Bedienhöhe. Mobil passen zwei in eine Zeile, bei großer Schrift
eine. Die Rücknavigation liegt oberhalb der Karte.

### Allgemeine Aktionen

- Primäraktion = gefüllter primary-Button (Radius 10–11, h 32–38); Sekundär =
  weißer Ghost mit Rahmen; destruktiv = #b91c1c gefüllt nur im Bestätigungsdialog.
- Vorschlags-Chips (antippbare Fragen): primary-Rahmen /30 + bg /4 (auf Tonfläche
  weiß) + Pfeil/Icon; nur am jüngsten Turn.
- Hover legt Zeilen-Aktionen frei („Dazu fragen") — Fläche primary/5, Radius 9.
- Horizontales Blättern: Touch wischt, `maus:` bekommt stille runde
  Blätter-Pfeile (24 px, Rahmen + bg-card + Schatten). An Scroll-Zeilen
  schweben sie über den Enden, der Inhalt fadet dort per CSS-**Maske** aus
  (40–56 px) — nie per Farb-Verlauf, der stimmt nicht auf jedem Untergrund.
  An Snap-Karussells stehen sie neben den Indikator-Punkten und werden am
  Anschlag gedimmt, nicht versteckt (sonst springt der Indikator).
- Fortschritt: Häkchen grün ✓ → Spinner (12 px, primary) → gepunkteter Kreis
  (ausstehend); Playful-Zwischenwort erlaubt („Protokolle querlesen …").
- Fehler/Limits: immer mit Ausweg (Retry, „Als schnelle Frage", Countdown) und
  ohne Datenverlust („Frage steht wieder im Eingabefeld").
- Ehrliche Mengen: nie „viele", immer Zahl + Zeitraum.

## 7. Bewegung

Bis 09/2026 stand hier nichts, und entsprechend sah es aus: ein paar sehr
sorgfältige Einzelstücke (Onboarding-Auftakt, Abzeichen-Feier, Lotti) und
dazwischen eine Oberfläche, in der Zustände einfach umsprangen. Die Regeln
unten sind der gemeinsame Nenner; die Bausteine dazu stehen in
`app/globals.css` unter „Bewegung: die gemeinsamen Bausteine".

- **Bewegung erklärt einen Zusammenhang oder sie fällt weg.** Sie zeigt, wo
  etwas herkommt (die Markierung fährt vom alten Ziel zum neuen), dass etwas
  eine Schublade ist (das Blatt fährt von unten ein) oder in welcher
  Reihenfolge etwas gemeint ist (Listen laufen gestaffelt ein). Bewegung, die
  nur hübsch ist, kostet Aufmerksamkeit ohne Gegenwert — und Aufmerksamkeit
  gehört hier den Inhalten.
- **Vier Dauern, keine fünfte.** `--takt-tipp` (120 ms, Zustand unter dem
  Finger) · `--takt-fluss` (180 ms, der Normalfall) · `--takt-weg` (260 ms,
  eine sichtbare Strecke) · `--takt-buehne` (340 ms, etwas betritt die Seite).
  Als Utilities `duration-tipp/-fluss/-weg/-buehne`. Der Abgang ist mit
  `--takt-abgang` (200 ms) kürzer als der Auftritt: Wer schließt, hat sich
  entschieden und wartet nur noch.
- **Vier Kurven, dieselbe Logik.** `ease-out-strong` für Eintritte und
  Feedback, `ease-in-out-strong` für Bewegung auf dem Schirm, `ease-drawer`
  für Blätter, `ease-back-out` (Überschwinger) nur für Kleinteile bis etwa
  40 px — größer wirkt Überschwingen wie Wackelpudding.
- **Nur `transform` und `opacity`.** Alles andere löst Layout oder Paint aus
  und ruckelt auf dem Telefon. Eine Fläche, die breiter wird, skaliert; eine
  Liste, die einläuft, verschiebt sich — keine animierten `width`, `height`,
  `top`, `margin`. **Die eine Ausnahme ist das Aufklappen**
  (`components/aufklapp.tsx`): Was Platz schafft, muss den Fluss darunter
  mitnehmen, das geht per Definition nicht ohne Layout. Es läuft über
  `grid-template-rows: 0fr ↔ 1fr` — Rasterspuren sind animierbar, `height:
  auto` ist es nicht, und eine geschätzte `max-height` läuft entweder zu früh
  aus oder lange leer nach.
- **Was nachlädt, fährt erst auf, wenn es da ist.** Sonst klappt der Bereich
  auf Spinner-Höhe auf und springt beim Eintreffen des Inhalts ein zweites Mal
  (gemessen an der Sitzungs-Tagesordnung: 118 → 1.262 px in einem Bild). Der
  Fortschritt gehört dorthin, wo getippt wurde — an der Sitzungskarte ersetzt
  ein Spinner den Aufklapp-Pfeil, bis die Punkte da sind.
- **Was schon dasteht, bleibt beim Nachladen stehen.** Eine Liste durch ein
  Skelett zu ersetzen, ändert die Seitenhöhe zweimal statt einmal, und ein
  gleichzeitig laufender Scroll arbeitet dagegen („ein hässlicher reload …
  wodurch alles zuckt", Tim 03.09.2026). Beim Blättern und Filtern wird die
  alte Liste nur leiser gestellt (`.liste-laedt`); ein Skelett gibt es nur,
  wenn es nichts gibt, was stehen bleiben könnte.
- **Der erste Auftritt bewegt sich nicht.** Eine Markierung, die beim
  Seitenaufruf aus der Ecke hereinfliegt, behauptet einen Weg, den niemand
  gegangen ist. Gefahren wird erst, wenn es einen Vorgängerstand gibt
  (`components/gleit-marker.tsx`).
- **Ein gehaltenes `transform` ist ein Containing Block.** Jede Animation mit
  `fill-mode: both` hält ihren Endframe fest; ein Element mit `transform` —
  auch der Identität — wird dadurch zum Bezugsrahmen für jedes
  `position: fixed` darin. Deshalb endet `fade-up` auf `transform: none` und
  der Seiten-Einstieg (`page-in`) blendet nur ein, statt anzuheben: Der
  Chat-Composer hing sonst die ersten 0,34 s jeder Navigation 164 px zu hoch
  (Tims Befund 15.08.). Wer eine neue Ein-Animation schreibt, prüft beides.
- **Gestaffelt heißt gedeckelt.** Der Versatz endet bei der sechsten Zeile
  (`components/staffel.tsx`); ohne Deckel käme die 40. Zeile einer
  Trefferliste 1,8 s nach der ersten und die Seite wirkte lahm statt lebendig.
- **Endlos laufende Bewegung braucht eine Pause.** Der Glanz über dem
  KI-Frage-Segment ruht ~70 % seines Loops, das Maskottchen atmet und blinzelt
  in Abständen von Sekunden. Ein Dauer-Flackern im Blickfeld macht den Text
  daneben unlesbar.
- **`prefers-reduced-motion` ist keine Kür.** Der globale Block in
  `app/globals.css` legt Dauern still; wer eine Bewegung baut, deren
  Endzustand nicht von allein steht (Sichtbarkeit per JS, gestaffelte
  Verzögerungen), sorgt selbst dafür, dass dort sofort der Endwert steht — so
  wie `Reveal` und `.staffel-auf` es tun.

## Admin: vom Überblick zur Untersuchung

Fünf Hauptbereiche: Überblick, Nutzung, Menschen, Betrieb und Inhalte.
Unterpunkte erscheinen nur im gewählten Bereich. Hash-Links halten die
Auswahl bei Neuladen und Zurücknavigation, auch im statischen App-Export.
Kennzahlen im Überblick sind Einstiege in die vollständigen Auswertungen;
Zeitraum und Grundgesamtheit stehen jeweils direkt an der Zahl.

Neue Konten werden nach Registrierungswoche untersucht. Einrichtung, frühe
Abos und erste Fragen sind unabhängige Merkmale, keine aufeinanderfolgenden
Trichterstufen. Rückkehr hat einen eigenen Umschalter (2/7/30 Tage) und zeigt
erreicht, nicht erreicht und noch nicht auswertbar getrennt. Fehlende
Grundlage ist „–“, niemals 0 %. Tabellen halten sämtliche Einzelwerte bereit.
Betreiber-/Testkonten werden nur dort als ausgeschlossen beschriftet, wo die
zugrunde liegende Abfrage sie tatsächlich ausschließt.

Verläufe verwenden den gemeinsamen Ablese-Baustein für Maus, Touch und
Tastatur. Nullwerte bekommen keine dekorative Mindesthöhe. Betriebsprobleme
tragen einen ausgeschriebenen Status; ein fehlender Lauf gilt als unbekannt.

### Admin: E-Mails und Kontodetails

Unter Menschen → E-Mails stehen Versand, fehlgeschlagene Versuche und anonyme
Mail-Link-Aufrufe nebeneinander. Aufrufe sind weder Personen noch eine Öffnungs-
oder Klickquote. Anlass-Zeilen bleiben auch bei ausschließlich fehlgeschlagenem
Versand oder Aufrufen älterer Mails erhalten. Der Tagesverlauf füllt Kalendertage
ohne erfassten Versand mit Null und kennzeichnet die angeschnittenen Randtage.

Die Empfängerliste führt direkt zur Mailhistorie des Kontos. Aktivität, E-Mails
und Verwaltung haben eigene, per URL erreichbare Detailansichten. Auf schmalen
Bildschirmen ersetzt das ausgewählte Detail die Kontenliste; ein Zurück-Link
führt wieder zur Auswahl. Betreffzeilen werden vollständig umgebrochen, ältere
Mails nachgeladen. Der heutige Benachrichtigungskanal löscht keine Historie.
Aktivität am Versandtag ist als zeitliches Zusammentreffen beschriftet, ohne
eine Wirkung der einzelnen Mail zu behaupten.

## 8. Anti-Patterns

Keine Lotti-Sprechblase außerhalb der Anstupser-Grenzen (§ 5) · kein Zähler
oder Abzeichen am geschlossenen Lotti-Knopf ·
keine Anführungszeichen um Paraphrasen · keine Stimm-/Abstimmungsgrafiken ·
kein Signal-Orange als Flächenfarbe · keine Parteifarben-Flächen (Ausnahme:
Stichwahl-Karte, s. § 2) · kein Emoji
im UI-Text · keine gerahmten Button-Reihen unter Antworten (stille Icons) ·
Bricolage nie im Fließtext · Externes nie wie Beschlüsse stylen · Footer nie
auf der Chat-Seite (Links im Sidebar-Fuß).

**Und keine Selbstvergewisserung.** Dass unsere Zahlen stimmen, ist kein
Seiteninhalt. Eine Tabelle, in der acht Jahre lang zweimal dieselbe Zahl und
daneben „unter 1 Tsd. € Unterschied" steht, beruhigt uns und erklärt
niemandem etwas („du musst nicht beweisen anhand von einer Tabelle, dass
deine Zahlen richtig sind", Tim 16.08.). Die Prüfung gehört in Tests und in
die Technik-Doku und bleibt dort auch bestehen; auf die Seite gehören die
**Quelle** (welches Dokument, welcher Abschnitt, Link aufs Original), der
Hinweis, wenn eine Zahl **unsere Rechnung** ist, und die **Grenzen** dessen,
was sie hergibt. Das ist der Unterschied zwischen quellen-ehrlich (§ 1) und
selbstbezogen.

### Widgets auf „Heute“

Die Seite setzt eigenständige Bausteine zusammen: Web `HeuteWidget`, iOS
`RatsWidget` geben Kopf, Inhalt und optionalen Abschluss vor. Die Überschrift
darf umbrechen. Daten, Lade- und Fehlerzustände sowie Aktionen gehören in den
jeweiligen Baustein; die Seite bestimmt Platz und Reihenfolge. Stabile Kennungen
(etwa `seit-besuch`) bereiten eine spätere persönliche Auswahl vor. Eine
Auswahl oder Sortierung der Widgets gibt es derzeit noch nicht.

Alle sechs Web-Widgets verwenden `HeuteWidget`: Rückblick, Woche, Zahl,
Viertel, Verlauf und Fundstück. Der Kopf hat links ein Lucide-Icon (20 px),
daneben Bricolage 16/700, darunter eine durchgezogene Trennlinie. Kopf und
Inhalt haben 16 px seitlichen und 12 px vertikalen Abstand; der optionale
Abschluss hat 16 × 8 px. Zwischen Karten liegen 16 px. Keine eigenen
Kartenfarben, Kopf-Polsterungen oder rechts stehenden Ersatz-Icons; Farbe
hebt einzelne Informationen hervor, etwa die Kennzahl. Inhalt folgt den
Leserollen: Titel 16, Hinweis 14, Metadaten 13 — als rem.

`HeuteWidgetGrid` bietet ab ausreichender Rasterbreite zwei Spalten.
`size="normal"` belegt eine, `size="wide"` beide. Die Größen sind zunächst
Vorgaben im Seitenlayout; es gibt noch keine persönliche Größenauswahl.
Die Karte misst ihre **eigene Inhaltsbreite**, relativ zur Schriftgröße:
unter 28 rem `compact`, ab 28 rem `standard`, ab 56,25 rem `expanded`.
`useWidgetDetail()` bzw. die Render-Funktion des Inhalts liefert diese Stufe.
Eine breite Vorgabe auf dem Telefon bleibt kompakt. Kein fester Höhenrahmen,
der große Schrift abschneidet.

Größe verändert den Inhalt: Die Woche zeigt ein/zwei/drei Punkte je Sitzung
und breit zusätzliche Erläuterungen; weitere Punkte bleiben aufklappbar.
Wochentag und Datum stehen als kompakter Zweizeiler untereinander. Die
Datumsspalte ist 3,5 rem breit, mit 0,75 rem Abstand zu den Sitzungsinhalten.
Mobil bilden Datum und Gremium eine Kopfzeile, die Punkte nutzen darunter
die volle Breite. Nur horizontale Sitzungstrenner, keine seitliche Linie
oder dekorativen Aufzählungspunkte.
Der breite Rückblick kann zwei Sitzungen als direkte Vorschau zeigen.
„Mein Viertel“ zeigt pro gewähltem Viertel die jüngste belegte Entwicklung:
Vorhaben, kurze Erklärung, Stand und ausdrücklich das Datum der letzten
Ratsberatung. Eine Beratung in den nächsten 14 Tagen bekommt Vorrang und
führt direkt zum Tagesordnungspunkt. Das Indexdatum ist kein Neuigkeitsdatum.
Zahlen heißen immer „Vorhaben“. Kompakt zunächst zwei Viertel, sonst drei,
weitere auf Knopfdruck; die jüngsten Ratsstände zuerst. Breit stehen die
Viertel nebeneinander, schmal untereinander. Ortsnamen als leiser Kicker,
Vorhabentitel als Hauptinformation, Stand als kleines beschriftetes Abzeichen.
Details erst für sichtbare Viertel laden; sie teilen den Cache der Stadtkarte.
Der Verlauf zeigt kompakt drei Einträge mit Nachladen, breit bis zu fünf
mit längeren Titeln. Das Fundstück ergänzt breit die vollständige Erzählung
und Quellenangaben. Nicht jede Kennzahl braucht künstlich mehr Information,
nur weil Platz da ist. Die beiden kompakten Überblickskarten stehen vor der
breiten Woche; weitere Widgets folgen im selben Raster.

„Seit deinem letzten Besuch“ ersetzt die frühere Themen-Karte auf Heute.
Der Rückblick zeigt allgemeine Ergänzungen, unabhängig von Abos: neue und
geänderte Tagesordnungen sowie erstmals ergänzte Protokolle mit Ergebnissen.
Beim ersten Besuch heißt er „Neu bei Ratslotse“ und nennt ausdrücklich sieben
Tage. Der Zeitraum bleibt während eines Besuchs stabil, auch beim Nachladen;
ein neuer Besuch beginnt nach 30 Minuten ohne sichtbare Nutzung.

Hierarchie: Zeitraum → höchstens drei aufklappbare Arten → Gremien → Sitzungen.
Tagesordnungen erscheinen nur für Sitzungen ab heute; ältere Protokolle bleiben
relevant. Neue Tagesordnungen und Änderungen derselben Sitzung zählen nicht
doppelt. Protokolle zeigen die jüngste Sitzung zuerst, Tagesordnungen den
nächsten Termin. Auch bei monatelanger Abwesenheit bleibt die Übersicht
eingeklappt. Je Art erscheinen zunächst vier Gremien, je Gremium drei
Sitzungen; weitere werden auf Wunsch geöffnet bzw. nachgeladen. Bei nur einer
Sitzung führt das Gremium direkt zum Inhalt. Die Datenspanne hält nachträglich
importierte Archiv-Protokolle von vermeintlich aktuellen Sitzungen unterscheidbar.
Der Fokus folgt beim Nachladen der ersten neuen Sitzung. Keine Tags und keine
konkurrierende zweite Themen-Karte.

Animationen erklären Zustandswechsel: neue Zeilen blenden über 220 ms mit
vier Pixeln Bewegung ein, Hover hebt die Zeile leicht hervor und bewegt nur
den Richtungspfeil. Reduzierte Bewegung schaltet diese Effekte aus. Große
Schrift darf mehr Höhe beanspruchen; Metadaten und Aktionen bleiben lesbar.
Ein Ladefehler erhält vorhandene Inhalte und bietet Wiederholen; er wird
niemals als „keine Neuigkeiten“ dargestellt.
