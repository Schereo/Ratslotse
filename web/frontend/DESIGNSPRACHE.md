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
- **Turn-Fußzeile**: KI-Disclaimer 10,5–11 px + stille Icon-Aktionen 15 px
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

## 7. Anti-Patterns

Keine Anführungszeichen um Paraphrasen · keine Stimm-/Abstimmungsgrafiken ·
kein Signal-Orange als Flächenfarbe · keine Parteifarben-Flächen · kein Emoji
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
