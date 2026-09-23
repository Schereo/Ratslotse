# Plan: Lotti als Assistentin — zweite Runde

> Fortsetzung von [plan-lotti-assistentin.md](plan-lotti-assistentin.md).
> Dort stehen Zielbild, Regeln (§ 3) und die acht gebauten PRs. Dieses
> Dokument trägt, was die **zweite Durchsicht am 21.09.2026 abends** ergeben
> hat — im Browser mit echten Daten, angemeldet als Ratsmitglied — und was
> für den Chat darüber hinaus sinnvoll wäre. Jeder Punkt ist ein eigener PR
> nach denselben Regeln wie in Plan 1: ein Auftrag, ein Branch, Bild vor dem
> Merge, gemessen statt geschätzt.

## 0. Wo wir stehen

Alle acht PRs des ersten Plans und die vier Korrektur-PRs der ersten
Durchsicht (#1449–#1452) liegen auf `dev`. Der Schalter `lotti-assistentin`
ist auf Prod **aus**. Beim zweiten Durchgehen im Browser ist eine
Korrektur direkt gebaut worden, weil sie ein eigener Fehler vom selben Tag
war: **#1453** — der Rechte-Riegel las `user["permissions"]`, ein Feld, das
es im Konto-Dict nie gab, und sperrte damit den Haushalts-Bereich für jedes
Konto. Alles Weitere steht hier als Plan.

## 1. Was die zweite Durchsicht ergeben hat

Geprüft wurde nicht der Code, sondern das Verhalten: Startseite,
Beschluss-Seite, Personen-Seite, Schulden-Seite mit Erklär-Modus,
Markierung, der Weg ins Archiv, die Gesprächsliste, die Handy-Ansicht.

### 1.1 Was passt

- **Die drei Wege ohne Modell** antworten in unter 5 ms: Seitenwissen auf
  „Heute", Kurzfassung auf der Beschluss-Seite, Glossar bei einer
  markierten Vokabel.
- **Die Personen-Seite** nennt jetzt ihre Person (Befund 4 der ersten
  Durchsicht): „Du siehst hier die Seite von Margrit Conty …" — und sagt
  von selbst, dass ein Stimmverhalten dort nicht steht.
- **Der Erklär-Modus** setzt Abzeichen und erklärt den angetippten Baustein
  mit Jahr und Zahlen aus dem Kontext („zum 31. Dezember 2024 … 43,7
  Millionen … 294,9 … 740,3").
- **Die Markierung** landet in der Kontext-Pille und im Prompt.
- **Gespeichert wird richtig**: Die Gespräche tragen `kind = lotti`, und
  die Ratsfrage aus dem Fenster liegt als vierte Runde im selben Gespräch.
- **Das Handy-Fenster** füllt die Fläche zwischen Kopfleiste und Knopf, der
  Composer ist sichtbar, der Knopf liegt darunter und nicht darin.
- **Der Verlauf überlebt den Seitenwechsel**, wie geplant.

### 1.2 Was nicht passt — nach Gewicht

**B1 — Der Weg ins Archiv verliert den Beschluss.** Auf der Beschluss-Seite
„Weitenmesser im Marschwegstadion (2020)" die Frage „Wer hat dagegen
gestimmt?" → Lotti reicht korrekt weiter → „Den Rat fragen" → die Antwort
handelt von einem **anderen** Beschluss: „Richtlinien … Nutzung des
Marschwegstadions … 15.12.2025 … bei zwei Gegenstimmen". Die Ratsfrage
bekommt den Bildschirm nur als Text (Route, Überschrift, Element), nicht
die **Kennung** — sie sucht dann nach Ähnlichkeit und findet den neueren
Beschluss über dasselbe Stadion. Genau die Frage, für die der Handoff
gebaut ist, bekommt so eine falsche Antwort mit richtigen Quellen.

**B2 — Der Anzeigename steht in der Überschrift.** Auf `/dashboard` ist die
`h1` „Moin, Ratsfrau!". Das Fenster schickt sie als `heading`, die
Kontext-Pille zeigt „Du bist auf: Moin, Ratsfrau!", der Prompt bekommt den
Namen, und das gespeicherte Gespräch heißt so. Regel 9 („Anzeigename nie")
ist damit auf der meistbesuchten Seite verletzt — nicht durch das Konto,
sondern durch die Seite.

**B3 — „Die Seite sagt nichts dazu" ist falsch.** „Wie viele haben dagegen
gestimmt?" auf der Beschluss-Seite → „Die Seite sagt nichts dazu". Die Seite
zeigt das Abstimmungsergebnis; `get_decision` liefert `no_votes` und
`abstentions`; der Gegenstands-Block reicht beide nicht durch.

**B4 — Lotti gibt es auf dem Einrichtungs-Assistenten.** Der Knopf steht im
DOM, ist mit Tab erreichbar, aber vom Assistenten verdeckt. Wer ihn per
Tastatur trifft, öffnet ein Fenster hinter der Fläche; wer den Assistenten
abbricht, sieht ein „Heute"-Wissen zu einer Seite, die gerade der
Assistent war. Dasselbe gilt für die Tour.

**B5 — Der Verlauf trägt fremde Seiten ohne Zäsur.** Auf der
Schulden-Seite steht als erste Runde noch die Erklärung der Personen-Seite.
Das ist gewollt (der Verlauf überlebt), aber es gibt keine sichtbare
Trennlinie „— jetzt auf: Schulden —", und die drei letzten Runden gehen als
Gedächtnis in den Prompt, auch wenn sie zu einer anderen Seite gehören.

**B6 — Das Fenster misst nichts zur Qualität.** Der Endpunkt
`/qa/feedback` nimmt seit PR 7 `source = lotti` an; im Fenster gibt es
keinen Daumen. Die Annahme wird gezählt, die Güte nicht.

**B7 — `glossary` aus dem Schluss-Rahmen wird nicht benutzt.** Das Fenster
speichert die Fachwörter je Runde und zeigt sie nirgends. Die Antwort selbst
trägt die Glossar-Unterstreichungen aus `AntwortText` — die Liste ist damit
kein Verlust, nur toter Zustand.

## 2. Die Pull Requests

Regeln: § 3 in Plan 1 gilt unverändert. Neu dazu, aus dieser Durchsicht:

- **Regel 12 — Mit dem echten Konto-Dict testen.** Die Attrappe in
  `test_assistant.py` trug ein Feld, das der Router nie bekommt. Ein Test,
  der die Form des Kontos erfindet, prüft die Form der Attrappe.
- **Regel 13 — Jeder PR, der eine Seite betrifft, wird auf dieser Seite im
  Browser mit echten Daten durchgeklickt**, nicht nur in Playwright gegen
  die leere Datenbank. B1 bis B4 fielen alle erst so auf.

### PR 9 — Der Gegenstand reist mit ins Archiv (B1)

**Was.** Die Ratsfrage aus dem Fenster bekommt die Kennung des Gegenstands
und behandelt ihn als gesetzt.

- `ScreenContext` (Router) bekommt `refs: ExplainRefs` — dieselbe Form wie
  bei `/explain`; das Fenster schickt sie mit (`panel.tsx::ratsfrageStellen`
  hat sie schon als `refs`).
- In `/ask`: Trägt der Bildschirm eine `decision_id`, wird dieser Beschluss
  **immer** in die Kandidaten aufgenommen und zuerst gereiht — vor dem
  Reranker, nicht nach ihm (das Retrieval darf ihn nicht verlieren; der
  Mechanismus für feste Kandidaten existiert: `only_ids` in `_qa_retrieve`,
  hier aber als „dazu", nicht als „nur"). Bei `ksinr` entsprechend die
  Sitzung. Der Prompt-Block `screen_block` in `qa.py` nennt ihn ausdrücklich:
  „Der Beschluss, den die Person gerade vor sich hat: „…" (Nr. …) — „das"
  und „dieser Beschluss" meinen ihn."
- **Nicht:** das Archiv auf ihn beschränken. „Gab es dazu frühere Anträge?"
  braucht die anderen.

**Tests.** `test_qa_screen_context.py`: mit `decision_id` steht der Beschluss
in den Kandidaten und an erster Stelle, auch wenn das Retrieval ihn nicht
gefunden hätte (Store-Attrappe ohne Treffer). Eval-Fall in
`cases_qa` (falls vorhanden) oder ein neuer Fall in `run_assistant.py` für
den Ratsweg: Weitenmesser-Seite + „Wer hat dagegen gestimmt?" →
`must_mention: ["weitenmesser"]`, `must_not: ["richtlinien"]`.

**Messen.** Dieselben drei Fragen wie in der Durchsicht auf drei
verschiedenen Beschluss-Seiten, je einmal, im PR-Text.

**Fertig, wenn:** die Frage von B1 den Weitenmesser beantwortet.

### PR 10 — Der Anzeigename kommt nicht aus der Seite (B2)

**Was.** Zwei Riegel, beide nötig:

1. **Client:** `ueberschriftenPfad` bekommt den Anzeigenamen des Kontos
   (`useAuth().user.display_name`) und entfernt ihn aus dem Pfad; ein Gruß
   („Moin, …!") wird ganz durch den Seitentitel aus `knowledge.PAGES`
   ersetzt — den kennt der Client nicht, also schickt er auf `/dashboard`
   schlicht `heading = ""`, und das Backend fällt auf `page_title` zurück
   (seit #1449 vorhanden).
2. **Server:** `_screen_block` und `_lotti_turn_speichern` bekommen den
   Anzeigenamen des Kontos als Tabu-Wort und streichen ihn aus Überschrift
   und Titel — der Riegel, der hält, wenn der Client vergisst. Kein neuer
   Prompt-Text: Der Name wird entfernt, nicht maskiert.

**Tests.** `test_assistant.py`: ein Konto mit Anzeigename, eine Überschrift,
die ihn trägt → weder im Prompt noch im Gesprächstitel. `assistentin.test.ts`
für den Client-Teil. Der bestehende Wortlaut-Test bleibt.

**Fertig, wenn:** die Kontext-Pille auf „Heute" „Du bist auf: Heute" zeigt.

### PR 11 — Das Abstimmungsergebnis gehört zum Gegenstand (B3)

**Was.** `_record_block` nennt Ja/Nein/Enthaltungen, wenn `get_decision`
sie liefert („Abstimmung: angenommen, 2 Gegenstimmen, 1 Enthaltung"), und
das Sitzungsdatum als Datum in Worten. Dazu die Prompt-Regel im
`assistant_explain`: Zahlen zur Abstimmung darf sie nennen, WER wie
gestimmt hat, steht nirgends — das bleibt Archivfrage (und dort steht es
auch nicht, s. Personen-Seite).

**Tests.** Eval-Fall `beschluss-wie-viele-dagegen` mit `must_mention` der
Zahl aus der Datenbank; `must_not: ["sagt nichts dazu"]`.

**Fertig, wenn:** „Wie viele haben dagegen gestimmt?" die Zahl nennt und
„Wer …" weiterhin weiterreicht.

### PR 12 — Kein Lotti-Knopf hinter Assistent und Tour (B4)

**Was.** `LottiInner` bekommt die Information, ob gerade ein
Vollbild-Ablauf läuft (Einrichtungs-Assistent, Tour), über denselben Weg,
den `BackToTop` benutzt — nachsehen, ob es dafür schon ein Signal gibt
(`data-onboarding` o. ä.), sonst ein `window`-Ereignis wie
`ratslotse:lotti-offen`. Dann: kein Knopf, kein Anstupser, kein Fenster.
Auf `/dashboard` mit fertigem Assistenten alles wie bisher.

**Tests.** Playwright: mit zurückgesetztem Onboarding ist `[data-lotti-knopf]`
nicht im DOM; nach „Überspringen" ist er da.

### PR 13 — Die Zäsur im Verlauf (B5)

**Was.** Wechselt die Seite, steht im Verlauf eine Trennzeile „Jetzt auf:
Schulden" (aus `PAGES[route].title`; der Client spiegelt die Titel nicht,
sondern zeigt die `h1` ohne Gruß — s. PR 10). Das Gedächtnis (`history`)
bekommt nur Runden **derselben Route**; Runden von anderen Seiten bleiben
sichtbar, gehen aber nicht in den Prompt. Beides ohne neue Zustände: `route`
steht bereits an jedem Turn (`kontext`), es fehlt das Feld selbst — also
`route: string` je `LottiTurn` (im `sessionStorage` abwärtskompatibel, alte
Turns ohne Route zählen als fremd).

**Tests.** `assistentin.test.ts` für die Filterung; Playwright: nach einem
Seitenwechsel steht die Trennzeile.

### PR 14 — Ein Daumen im Fenster (B6)

**Was.** Unter jeder Modell-Antwort zwei stille Icon-Aktionen wie im
Ratsgespräch (Designsprache „Turn-Fußzeile"), `POST /qa/feedback` mit
`source = "lotti"` — der Endpunkt nimmt das seit PR 7 an. Der Admin-Reiter
„Lotti" bekommt die Quote dazu. Deterministische Antworten bekommen keinen
Daumen: Sie sind geprüfter Text, ein Daumen dort bewertete das Glossar.

**Tests.** Playwright: Daumen sichtbar nach Modell-Antwort, nicht nach der
Kurzfassung; Backend-Test für die Zählung je Quelle.

### PR 15 — `glossary` benutzen oder streichen (B7)

**Was.** Streichen. Die Unterstreichungen in `AntwortText` leisten es
schon; ein zweiter Ort für dieselben Wörter ist Doppelung. Das Feld bleibt
im `done`-Rahmen (die App liest es nicht, das Web speichert es nicht mehr).
Wer es später als Chips will, hat den Rahmen noch.

## 3. Was für den Chat darüber hinaus sinnvoll wäre

Nach Nutzen für die Person geordnet. Alles ohne neues Sicherheitsmodell:
Lotti erklärt und zeigt, sie handelt nicht (Plan 1, § 6).

### PR 16 — „Zeig mir" — Lotti als Lotsin auf der Seite

**Die Idee.** Die häufigste Frage nach „Was ist das?" ist „Wo finde ich …?".
Die Anker (`data-erklaer`) sind eine Landkarte der Seite, die der Client
schon hat: Schlüssel und Titel je Baustein. Fragt jemand „Wo steht, was die
Stadt an Zinsen zahlt?", kann das Fenster **ohne Modell** die Anker-Titel
gegen die Frage halten (einfacher Wortabgleich, wie `generische_frage`) und
einen Chip „Zeig mir: Zinsen und Tilgung" anbieten, der zum Baustein scrollt
und ihn kurz hervorhebt (dieselbe Hervorhebung wie beim Abzeichen im
Erklär-Modus). Trifft nichts, geht die Frage wie bisher ans Modell — mit
der Anker-Liste (nur Titel, ≤ 20) im Kontext, damit die Antwort sagen
kann: „Das steht unter „Rate-Treppe", weiter unten."

**Warum das hierher gehört.** Es ist das Gegenstück zum Erklär-Modus: Dort
zeigt die Person auf die Seite, hier zeigt Lotti. Und es kostet nichts, wo
es deterministisch trifft.

**Grenzen.** Nur Anker, nie freie DOM-Suche. Kein Scrollen ohne Chip-Tipp.

### PR 17 — Anschlussfragen, die zur Seite passen

**Die Idee.** Nach einer Antwort zwei Chips, die weiterführen — wie die
Vorschläge im Ratsgespräch, aber **deterministisch** aus dem, was das
Fenster weiß: die Anker der Seite („Erklär mir: Rate-Treppe"), die
Fachwörter aus `glossary` („Was heißt Tilgung?") und, bei einer
Archivfrage, „Den Rat fragen" als Chip statt nur als Knopf. Kein zweiter
Modellaufruf für Vorschläge (das Ratsgespräch bezahlt dafür eine Runde;
hier wäre es bei 0,07 Cent je Antwort ein Verdoppeln).

### PR 18 — Der Erklär-Modus in der App

Plan 1 hat ihn für v1 ausgeklammert (PR 6). Der Weg: eine
Ankerkonvention je SwiftUI-Ansicht (`.lottiAnchor("schulden.rate-treppe",
titel:)`, ein ViewModifier, der Schlüssel und Titel in eine
`PreferenceKey` schreibt), das Blatt zeigt die Liste der Anker der
aktuellen Ansicht als antippbare Zeilen — **kein** Overlay mit Abzeichen
über der Liste (das wäre die Bauform des Web und passt nicht zu einer
`List`). Der Baustein-Text kommt aus derselben Quelle wie die Ansicht, nicht
aus einem DOM. Erst nach vier Wochen Web-Betrieb, mit den Zahlen aus dem
Admin-Reiter: Wird der Erklär-Modus dort überhaupt benutzt?

### PR 19 — Das Wahl-Wissen

`/wahlabend`, `/tipp`, `/wahlen` stehen in `OHNE_ERKLAERUNG` mit Grund
„später". Vor der nächsten Wahl bekommen sie Einträge in `PAGES` und das
Vokabular (Sainte-Laguë, Wahlbereiche, Stichwahl) ins Glossar. Ein PR, der
zwei Tage vor dem Wahltag fertig ist, kommt zu spät — Termin aus
`kommunalwahl/wahlen/`.

### PR 20 — Der Anstupser lernt aus seinen Zahlen

Nach vier Wochen: Liegt die Ja-Quote unter 5 %, wird die Lesezeit auf 90 s
und die Monatsgrenze auf zwei gesetzt — oder er fliegt raus (Tims
Entscheidung, `fertig_wenn` am Schalter). Liegt sie über 20 %, kommen die
Sitzungs- und Themen-Seiten der App dazu. Ohne Zahlen keine Änderung.

### Was NICHT gebaut werden soll

- **Kein „Frag Lotti" auf öffentlichen Seiten** (Landing, `/beschluss/…`
  ohne Konto). Jeder Aufruf kostet, und ohne Konto gibt es keinen Zähler.
- **Keine Sprachausgabe** im Fenster. Das Ratsgespräch hat sie in der App;
  dort ist die Antwort lang. Fünf Sätze liest man.
- **Kein Bild-Upload, kein Screenshot** (Plan 1, § 6).
- **Keine Handlungen** — auch nicht „Thema anlegen" aus dem Fenster heraus.
  Der Chip darf zur Themen-Seite führen, mehr nicht.

### PR 21 — Lotti kennt den ganzen Haushalt

**Tims Auftrag (22.09.2026):** „Die Leute werden nicht immer auf die richtige
Haushaltsseite gehen und ihre Fragen zum Haushalt vielleicht auf der falschen
stellen. Gerade hier ist es wichtig, dass Lotti auf die richtige
Haushaltsseite verweist."

Drei Teile, ein PR:

- **A — Der Wegweiser.** `knowledge.wegweiser("/haushalt", rechte)` gibt alle
  **fünfzehn** Haushalts-Seiten mit Titel, Adresse und dem ersten Satz ihres
  `what` (2,8 kZ). Vorher waren es sechs nackte Titel aus `verwandte()` —
  damit ließ sich nicht sagen, wo etwas nachzulesen ist. Auf Haushalts-Seiten
  löst der Wegweiser die alte Liste ab (zweimal dieselben Titel im selben
  Prompt sind keine zweite Auskunft); außerhalb bleibt sie unverändert.
- **B — Der Verweis wird ein Chip.** Zweites Ziel der Marke:
  `WEITER: seite /haushalt/schulden`. `split_next` prüft die Route
  deterministisch (in `PAGES`, im Haushalt, für dieses Konto erreichbar) und
  verwirft sie sonst; der `done`-Rahmen trägt `next_page: {route, title}`,
  das Fenster zeigt „Weiter zu: <Titel>". Vorrang der Chips: Archiv › Seite ›
  Anker › Fachwort, weiterhin höchstens zwei. Das Fenster bleibt offen, der
  Verlauf bekommt seine Zäsur.
- **C — Geld auch außerhalb des Haushalts.** Die Zahlen kommen jetzt auf
  jeder Seite, wenn das Konto `budget` hat **und die FRAGE** eine Geld-Facette
  aus `GELD_AUSSERHALB` auslöst. Der Bildschirmtext zählt dort nicht mit.

**Was dabei herauskam (alles gemessen, 22.09.2026):**

| Befund | Zahl |
|---|---|
| Eval gesamt | **39/39** ohne harten Befund (vorher 36/36), **7/7** Injektionen |
| drei neue Fälle | Gewerbesteuer auf `/haushalt/schulden` → Zahl + „Woher kommt das Geld?"; Stellenplan auf `/haushalt/mitreden` → „Wer macht die Arbeit?"; Schuldenstand auf `/dashboard` → Zahl + Schulden-Seite |
| Prompt je Haushalts-Frage | 2.777 → 3.695 Tokens (+918), rund +0,03 US-Cent Eingabekosten |
| `geld_facetten` ist für die KI-Frage gebaut, nicht für diesen Prompt | „Wie geht es mit dem Vorhaben weiter?" zog `measures` und riss auf einer Beschluss-Seite Zahlen + Wegweiser herein — der Injektions-Fall `injektion-ueberschrift` kippte **3 von 3** („BANANE"). Mit der kuratierten Liste `GELD_AUSSERHALB` wieder 3/3 grün. |
| Eine Regel, die nicht greift, kostet die Regel daneben | Die Verweis-Regel fest im Prompt kostete `ortsfrage-zinsen-anker` **3/3 → 0/3**. Sie steht jetzt als `prompts.WEGWEISER_REGEL` nur dort, wo auch der Wegweiser steht; ohne ihn ist der Prompt zeichengleich mit dem von vorher. |
| Der Wegweiser tritt bei einer Ortsfrage zurück | „Wo steht …?" meint einen Baustein DIESER Seite; die Zahlen bleiben, der Wegweiser geht (`assistant.ortsfrage`, dieselbe Regex wie im Client). |
| Der Prüfstand bestrafte die eigene Stil-Zusage | „rund 337 Millionen" gegen „336.994.000" im Kontext galt als erfundene Zahl. `erfundene_zahlen` rechnet jetzt die Rundung nach. |

**Nicht gebaut** (wie im Auftrag festgelegt): keine Kopie der redaktionellen
Seitentexte ins Backend, kein zweiter Retrieval-Weg, kein automatisches
Navigieren — der Chip ist ein Angebot. Die App bleibt unangetastet; sie
ignoriert `next_page`.

## 4. Reihenfolge

PR 9 zuerst — es ist der einzige Punkt, an dem Lotti heute mit Belegen
falsch antwortet. Dann PR 10 (Regel 9), dann 11 bis 15 in einem Zug (klein,
je unter 100 Zeilen). PR 16 und 17 sind die beiden, die den Chat spürbar
besser machen; 18 bis 20 warten auf Zahlen oder Termine.

Vor dem Prod-Schalter: PR 9 und 10 gemergt, Tims Gegenlesen der Bilder aus
allen PRs, und ein Blick in den Admin-Reiter nach einer Woche auf `dev`.

## 5. Stand der Umsetzung (22.09.2026, nachts)

Gebaut von Opus 5 in Folge, je ein PR, jeder mit Browsertests gegen echte
und gegen leere Daten, `pruefe.py` grün, Bilder an Tim:

| PR | Nummer | Was dabei zusätzlich herauskam |
|---|---|---|
| 9 Gegenstand ins Archiv | #1455 | `qa.answer_*` reichte `screen` nie an den Prompt durch — der Bildschirm-Block aus PR 7 hatte bis dahin keinen Prompt erreicht. Gemessen: erste Quelle vorher 0/3, nachher 3/3 der Beschluss der Seite. Die Eval hat jetzt einen Ratsweg-Arm. |
| 10 Anzeigename | #1456 | zwei Riegel (Client und Server), Namen kürzer als drei Zeichen bleiben, nur an Wortgrenzen; `/dashboard` hat jetzt den Tab-Titel „Heute" |
| 11 Abstimmung | #1457 | `vote = unanimous` braucht den Zusatz „also keine Gegenstimmen", sonst antwortete das Modell weiter „steht hier nicht"; Eval 34/34 |
| 12 Assistent/Tour | #1458 | neues Ereignis `ratslotse:vollbild` als Satz von Marken, weil Assistent und Tour-Einladung überlappen |
| 13 + 15 Zäsur, `glossary` | #1459 | je Turn `route` und `seite`; Gedächtnis nur aus Runden derselben Route (Netzmitschnitt: 1 → 0 fremde Runden) |
| 14 Daumen | #1460 | Schlüssel der Stimme ist die Antwort, nicht die Frage — „Was sehe ich hier?" steht unter jeder Seite, sonst gäbe es je Konto genau eine Lotti-Stimme |
| 16 „Zeig mir" | #1461 | 0 Netzaufrufe für die Lotsen-Runde; zwei Zeitreihen der Schulden-Seite trugen denselben Anker-Schlüssel; Eval 35/35 |
| 21 Haushalts-Wegweiser | siehe unten | Wegweiser, Seiten-Chip und Geld außerhalb des Haushalts; zwei Regressionen unterwegs gemessen und behoben (s. PR 21) |
| 17 Anschlussfragen | #1462 | Glossar-Chip antwortet ohne Modell (0 ms Serverzeit statt 1.028 ms) über `selection`; „Tilgung" fehlt im Glossar |

PR 18 bis 20 warten wie geplant auf Zahlen (vier Wochen Admin-Reiter) bzw.
auf den nächsten Wahltermin. Offen bleibt Tims Gegenlesen der Bilder und der
Prod-Schalter.

## Anhang — Was in der Durchsicht gemessen wurde

| Probe | Ergebnis |
|---|---|
| `/dashboard`, „Was sehe ich hier?" | Seitenwissen, 0 ms; Pille „Moin, Ratsfrau!" (B2) |
| `/council/decision?id=2982`, „Was sehe ich hier?" | Kurzfassung, 0 ms |
| dito, „Wie viele haben dagegen gestimmt?" | „Die Seite sagt nichts dazu" (B3) |
| dito, „Wer hat dagegen gestimmt?" → Den Rat fragen | Antwort zu Beschluss von 2025, 40 Quellen (B1) |
| `/council/person?slug=margrit-conty` | Person genannt, Grenzen genannt |
| `/haushalt/schulden`, Abzeichen „Drei Zählweisen" | vor #1453: 403; danach Zahlen mit Datum |
| Markierung „Kernhaushalt 43,7 …" | in Pille und Prompt |
| Gesprächsliste | drei Gespräche `kind = lotti`, Ratsfrage in derselben |
| Handy 375 × 812 | Fenster 72–668 px, Knopf ab 680 px, Composer sichtbar |
| Einrichtungs-Assistent | Knopf im DOM, verdeckt (B4) |
