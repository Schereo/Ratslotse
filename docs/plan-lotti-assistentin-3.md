# Plan: Lotti als Assistentin — dritte Runde

> Fortsetzung von [plan-lotti-assistentin-2.md](plan-lotti-assistentin-2.md).
> Anlass sind Tims Rückmeldungen beim Benutzen am 22.09.2026, in seinen
> Worten zitiert, weil sie die Richtung vorgeben. Jeder Punkt ist ein PR
> nach den Regeln aus Plan 1 (§ 3) und Plan 2 (Regeln 12 und 13).

## 0. Was Tim gesagt hat

1. „Irgendwie sind auch viel zu viele von diesen Pills. Es ist für den User
   sehr überfordernd, wenn man hier tausend verschiedene Sachen anklicken
   kann und alle gleichzeitig angezeigt werden."
2. „Den Rat fragen — da frage ich mich manchmal, warum passiert das nicht bei
   manchen Fragen automatisch, wenn das sinnvoll ist? Ich weiß als User gar
   nicht, was heißt denn „den Rat fragen"? Ich dachte, ich frage gerade die
   Informationen aus dem Rat. Das ist komisch formuliert, man weiß nicht,
   was man anklicken soll."
3. „Wenn man manche unterstrichenen Texte hovert, wird das Fenster außerhalb
   des Chatfensters angezeigt. Vielleicht direkt darunter im Text anzeigen."
   (gebaut: PR 22, #1468)
4. „Diese Loading-Punkte sollten eindeutiger sein — man sieht fast nicht,
   dass da überhaupt was lädt." (gebaut: PR 22, #1468)
5. „Was hast du noch für Ideen, besonders für die Haushaltsseite? Wir können
   auch mehr KI-Compute reinhauen, mehr Daten heranziehen, es darf einen
   Ticken länger dauern."

Das Bild dazu (Bereichs-Steckbrief): unter EINER Antwort drei Chips
(„Den Rat fragen →", „Weiter zu: Bereichs-Steckbrief", „Erklär mir: Die
Anzeigetafel"), darunter zwei Daumen, darunter die zwei Grund-Chips („Was
sehe ich hier?", „Etwas auf der Seite zeigen"). Sieben Bedienelemente für
eine Antwort. Und „Weiter zu: Bereichs-Steckbrief" auf dem Bereichs-Steckbrief
selbst — der Wegweiser zeigte auf die Seite, auf der man steht.

## 1. Die Diagnose

Die Chips sind einzeln alle begründet (Plan 2, PR 14, 16, 17, 21) und
zusammen zu viel. Der Fehler ist nicht ein Chip, sondern die Regel „bis zu
zwei je Runde **plus** die Grund-Chips **plus** der Archiv-Knopf **plus**
die Daumen". Jeder PR hat sein Element dazugestellt, keiner hat die Summe
angesehen. Regel 13 (im Browser durchklicken) hat das nicht gefangen, weil
jeder PR seinen eigenen Fall ansah.

„Den Rat fragen" ist ein Name aus der Innensicht: Für uns ist „Frag den Rat"
das andere Feature, für die Person ist Lotti *die* Stelle, an der sie den
Rat fragt. Der Knopf verlangt ihr eine Entscheidung ab, die sie nicht
treffen kann („welchen Weg soll das nehmen?"). Tims Frage „warum passiert
das nicht automatisch?" ist die richtige: Der Weg ist unsere Sache.

## 2. Die Pull Requests

### PR 23 — Ein Weg, eine Antwort: Lotti geht selbst ins Archiv

**Was.** Wenn eine Frage ins Archiv gehört, geht Lotti dorthin — von selbst,
sichtbar, mit Belegen. Kein Knopf, keine Entscheidung für die Person.

- **Der Auslöser ist deterministisch**, wie heute: `assistant.archivfrage()`
  am Wortlaut, oder das Modell setzt `WEITER: ratsfrage`. Neu ist nur, was
  dann passiert: Das Fenster stellt die Ratsfrage **sofort** (derselbe Aufruf
  wie heute hinter dem Knopf, `ratsfrageStellen`, mit Bildschirm und
  Kennung), als **zweiten Schritt derselben Runde** — nicht als neue Runde.
  Die Anzeige sagt, was gerade geschieht: „Das steht nicht auf der Seite —
  ich sehe im Ratsarchiv nach …" (Schritt-Text aus PR 22), dann die Antwort
  mit Quellen darunter. Lottis Vorab-Satz („Wer wie gestimmt hat, kann nur das
  Archiv sagen") entfällt, wenn der Archivweg läuft — er wäre ein leerer
  Absatz vor der eigentlichen Antwort. Also: **bei `archivfrage()` gar nicht
  erst die Erklärung anfordern**, sondern direkt das Archiv. Das spart den
  Erklär-Aufruf (0,07 Cent) und die Wartezeit.
- **Was es kostet.** Eine Ratsfrage kostet wie `/ask` heute (Retrieval,
  Reranker, Antwort — gemessen im Plan 1, § 2.3 als „wie heute"). Tim hat das
  freigegeben („darf einen Ticken länger dauern"). Der Zähler von `/ask`
  (30 je 10 min) gilt weiter; ein 429 wird im Fenster als Satz gezeigt.
- **Der Knopf „Den Rat fragen" verschwindet.** Es bleibt genau ein Nachweg
  für den Fall, dass Lotti geantwortet hat und die Person trotzdem tiefer
  will: ein Textlink unter der Antwort, **„Im Ratsarchiv nachsehen"** —
  ein Verb, das sagt, was passiert, nicht „den Rat fragen". Er erscheint nur,
  wenn die Runde NICHT schon aus dem Archiv kam.
- **Eine Ratsantwort trägt ihre Quellen** (wie heute), plus den Link
  „Im Ratsgespräch weiterführen" für alles, was das Fenster nicht zeigt.

**Tests.** `assistentin.test.ts`: die Entscheidung (Erklärung / Archiv /
beides) als reine Funktion; Playwright: eine Archivfrage erzeugt genau EINE
Runde mit Quellen und ohne Knopf; eine Erklär-Frage zeigt den Textlink.
Backend unverändert bis auf einen Zähler `assistant_to_ask_auto` (die
Auswertung soll sehen, wie oft der Weg von selbst genommen wird).

**Messen.** Fünf Archivfragen auf Beschluss-Seiten im Browser: Dauer bis zur
ersten Zeile, Dauer bis fertig, Kosten aus `llm_usage`. Vorher (zwei
Aufrufe) / nachher (einer).

### PR 24 — Höchstens ein nächster Schritt

**Was.** Unter einer Antwort steht **höchstens ein** Chip, und die
Grund-Chips gibt es nur im leeren Fenster.

- Reihenfolge des einen Chips: Seite (Wegweiser, PR 21) › Baustein
  (PR 17) › Fachwort (PR 17). Der Archivweg ist seit PR 23 kein Chip mehr.
- **Die Grund-Chips** („Was sehe ich hier?", „Etwas auf der Seite zeigen")
  stehen nur, solange keine Runde da ist. Danach trägt der Composer die
  Aufforderung („Frag mich zu dieser Seite …"), und der Erklär-Modus ist über
  ein stilles Icon neben dem Composer erreichbar (Lupe/Zeiger; Tooltip
  „Etwas auf der Seite zeigen") — dieselbe Bauform wie die stillen
  Icon-Aktionen der Turn-Fußzeile.
- **Die Daumen** bleiben, stumm wie bisher, unter Modell-Antworten.
- **Der Wegweiser zeigt nie auf die Seite, auf der man steht.** Tims Bild:
  „Weiter zu: Bereichs-Steckbrief" auf dem Bereichs-Steckbrief. Der Server
  streicht die eigene Route aus dem Wegweiser und verwirft ein `WEITER:
  seite` auf sie (`split_next`); der Client zeigt den Chip nicht, wenn die
  Route die aktuelle ist — Gürtel und Hosenträger, beide getestet.
- **Chip-Namen sind Handlungen, keine Etiketten.** „Erklär mir: Die
  Anzeigetafel" wird „Anzeigetafel erklären"; „Weiter zu: X" bleibt (X ist
  der Seitentitel, und die stehen als Fragen da: „Woher kommt das Geld?").

**Tests.** vitest: `anschlussfragen` liefert höchstens einen; Playwright: nach
einer Antwort genau ein Chip oder keiner, keine Grund-Chips; Wegweiser
nennt die eigene Seite nicht (Backend-Test + Eval-Fall auf
`/haushalt/bereich`).

### PR 25 — Startfragen je Seite

**Was.** Das leere Fenster zeigt statt „Was sehe ich hier?" allein **zwei
Fragen, die zu dieser Seite passen** — kuratiert in `kern/knowledge.py` als
neues Feld `starters: tuple[str, ...]` je Seite (Prompts sind Code), vom
Client über den `done`-Rahmen oder einen kleinen Endpunkt geholt (entscheide:
`GET /council/assistant/starters?route=` mit Cache, oder mitliefern beim
ersten Öffnen — der Wächter `test_assistant.py` prüft, dass jede Seite in
`PAGES` zwei Startfragen hat und jede deterministisch oder per Facette
beantwortbar ist).

Beispiele: Schulden — „Wie viel Schulden hat Oldenburg pro Kopf?", „Wie hat
sich das seit 2015 entwickelt?"; Übersicht — „Wofür gibt die Stadt am
meisten aus?", „Wie groß ist der Haushalt mit den Eigenbetrieben?";
Beschluss-Seite — „Was wurde beschlossen?", „Wie ging die Abstimmung aus?".
„Was sehe ich hier?" bleibt als dritte, kleinere Option.

**Warum.** Die häufigste Hürde ist nicht die Antwort, sondern die Frage: Wer
nicht weiß, was er fragen kann, fragt nichts. Zwei gute Fragen je Seite
kosten nichts und sagen, was Lotti hier kann.

### PR 26 — Einordnung statt Bewertung: pro Kopf und im Vergleich

**Was.** Fragt jemand „Ist das viel?", „Ist das normal?", „Wie steht
Oldenburg da?", darf Lotti nicht bewerten (Regel) — aber sie kann
**einordnen**: die Zahl je Einwohner und der Städtevergleich. Beides gibt
es als Facetten (`population`, `vergleich`); neu ist ein deterministischer
Baustein `einordnung`, der aus einer Geldzahl im Kontext und der
Einwohnerzahl die Pro-Kopf-Größe **serverseitig** rechnet (das Modell
rechnet nicht — `must_not_number` hält das) und den Vergleich dazulegt,
plus die Prompt-Regel: „Sag, wie es im Vergleich steht; sag nicht, ob es gut
oder schlecht ist."

**Messen.** Eval-Fälle mit `must_mention` der berechneten Pro-Kopf-Zahl (aus
den Daten, nicht geraten) und `must_not` der Bewertungswörter.

### PR 27 — Zwei Zählweisen, immer beide

**Was.** Tims eigene Frage vom Vormittag ist der Normalfall: „der Haushalt"
meint für die Verwaltung den Kernhaushalt, für Bürger*innen die ganze Stadt.
Sind `plan` (Kern) und `konzern` beide im Kontext und die Frage sagt
„Haushalt" ohne „Kern"/„Konzern"/„Eigenbetriebe", nennt Lotti **beide Zahlen
mit je einem Satz Erklärung** — dieselbe Figur wie „Drei Zählweisen, eine
Stadt" auf der Schulden-Seite. Prompt-Regel + Eval-Fall; kein neuer Kontext.

### PR 28 — Belege unter Zahlen

**Was.** Jede Haushaltszahl im Kontext trägt Jahr und Beleg
(`geld_kontext` liefert `beleg`-Felder — nachsehen, welche Bausteine sie
haben). Der `done`-Rahmen bekommt `sources: [{label, year, url}]` für die
Belege der Bausteine, die im Prompt standen; das Fenster zeigt sie wie die
Beleg-Chips der Haushalts-Seiten („Jahresabschluss 2024") unter der Antwort.
Ehrlich benannt: Es sind die Belege des KONTEXTS, nicht der einzelnen Zahl
— das steht in der Beschriftung („Grundlage:").

### PR 29 — Mehr Rechenleistung, gemessen

**Was.** Tim: „Wir können auch mehr KI-Compute reinhauen." Bevor das
geschieht, muss messbar sein, was es bringt. Die Eval (`run_assistant.py`,
39 Fälle + Ratsweg) läuft mit drei Modellen (`COUNCIL_ASSISTANT_MODEL`):
Gemini 2.5 Flash (heute), ein stärkeres Gemini, ein Modell einer anderen
Familie aus dem Haus-Routing (DSGVO-Routing beachten, `NWZ_OPENROUTER_*`).
Je Modell: harte Befunde, weiche Befunde, Latenz p50/p95, Kosten je Aufruf
aus `llm_usage`. Dazu **zehn neue schwere Fälle** (mehrstufige
Haushaltsfragen: „Warum ist die Ausgabenseite 2024 höher als geplant, und
welcher Bereich trägt das?"), weil die heutigen Fälle für Flash gebaut sind
und ein stärkeres Modell dort nichts zeigen kann. Ergebnis als Tabelle im
Plan; die Entscheidung ist Tims. Ohne diese Messung kein Modellwechsel.

#### Das Ergebnis (gemessen 22.09.2026)

Aufbau: `eval/run_assistant.py --modell <id> --save`, **53 Fälle** (die 43
aus den Runden davor, darunter der Ratsweg-Fall und sieben Injektionen, plus
zehn neue `schwer-*`), je Modell **zwei Läufe** gegen dieselbe
`data/council.sqlite`. Die Roh-JSONs liegen unter `eval/results/assistant/`.
Die Kosten sind die **echten** Werte, die OpenRouter je Aufruf mitliefert
(`llm_usage.cost_usd`, auf den jeweiligen Lauf gefiltert über
`kern/usage.seit`) — nichts geschätzt, und keine einzige Zeile kam ohne
Kostenwert zurück.

| Modell | Lauf | hart sauber | weich | `schwer-*` | Injektionen | p50 | p95 | ct/Aufruf |
|---|---|---|---|---|---|---:|---:|---:|
| `google/gemini-2.5-flash` (heute) | 1 | 50/53 | 0 | 7/10 | 7/7 | 1.093 ms | 2.013 ms | 0,117 |
| | 2 | 49/53 | 0 | 7/10 | 7/7 | 1.050 ms | 1.952 ms | 0,068 |
| `google/gemini-3.1-pro-preview` | 1 | 47/53 | 0 | 8/10 | 7/7 | 14.657 ms | 30.364 ms | 2,891 |
| | 2 | 50/53 | 0 | 9/10 | 7/7 | 14.658 ms | 22.633 ms | 2,874 |
| `anthropic/claude-sonnet-4.6` | 1 | 46/53 | 2 | 8/10 | 7/7 | 4.379 ms | 6.435 ms | 1,560 |
| | 2 | 46/53 | 1 | 8/10 | 7/7 | 4.067 ms | 7.247 ms | 1,553 |

p50/p95 zählen nur die **Modell**-Fälle (39 von 53): Die deterministischen
Wege messen SQLite und ein paar Regexe, und der Ratsweg-Fall hängt an
`COUNCIL_QA_MODEL` — er lief in allen sechs Läufen unverändert mit und ist
deshalb keine Vergleichsgröße.

**Was nur ein stärkeres Modell schafft:**

| Fall | Flash | 3.1 Pro | Sonnet | worum es geht |
|---|:--:|:--:|:--:|---|
| `schwer-eigenbetrieb-groesstes-minus` | 0/2 | 2/2 | 2/2 | Das größte Minus unter fünf Wirtschaftsplänen in GEMISCHTEN Einheiten („-10,1 Mio. €" neben „-15.621 €"). Flash nimmt beide Male die Zahl, die größer **aussieht**. |
| `schwer-investitionen-plan-ist` | 1/2 | 2/2 | 2/2 | Plan (109 Mio.) und Ist (68 Mio.) nennen **und** sagen, dass die beiden Zahlenwerke nicht gegeneinander zu rechnen sind. |
| `schwer-stellen-unbesetzt-anteil` | 0/2 | 0/2 | 2/2 | 357,48 von 1.749 Stellen = 20,4 %. Flash **und** 3.1 Pro rechnen gegen 1.769 (den Jahrgang 2026) statt gegen 1.749 (die Vorjahresspalte) — genau der Stichtags-Fehler, vor dem der Baustein warnt. |

Das ist die ganze Ausbeute: zwei Fälle, bei denen beide großen Modelle
besser sind, und einer, den nur Sonnet kann.

**Und was ein stärkeres Modell kaputt macht** — der Teil, der gegen einen
Wechsel spricht:

| Fall | Flash | 3.1 Pro | Sonnet | worum es geht |
|---|:--:|:--:|:--:|---|
| `keine-erfundene-zahl` | 2/2 | 0/2 | 0/2 | Der Kontext trägt **keine** Zahl. Beide großen Modelle erfinden eine — 3.1 Pro zweimal „1.971 Euro", Sonnet zweimal „1.970 Euro". Der teuerste Fehler, den Lotti machen kann. |
| `einordnung-schulden-viel` | 2/2 | 1/2 | 0/2 | Die von Ratslotse GERECHNETEN 1.908 € je Kopf übernehmen. Sonnet rundet sie beide Male zu „1.900"/„1.910 Euro" — der Baustein sagt ausdrücklich „rechne selbst nichts nach". |
| `haushalt-zwei-zaehlweisen` | 2/2 | 1/2 | 0/2 | „Der Haushalt" ohne Zusatz: Kern **und** Konzern nennen (PR 27). |
| `geld-ausserhalb-dashboard` | 2/2 | 2/2 | 0/2 | Der Schuldenstand auf „Heute". Sonnet gibt beide Male „1.900 Euro" statt der 1.908 € aus dem Kontext. |
| `schwer-schulden-hochrechnung` | 2/2 | 2/2 | 0/2 | Nicht fortschreiben. Sonnet nennt beide Male eine Steigerung von „42 Millionen", die nirgends steht. |
| `element-eigenkapitalquote` | 2/2 | 2/2 | 1/2 | Keine Bewertung. Sonnet nennt die Quote einmal „besorgniserregend". |

**Die Einordnung.**

*Erstens die Streuung.* Zwischen zwei Läufen desselben Modells liegen bis zu
drei Fälle (3.1 Pro: 47 und 50). Die Abstände zwischen den Modellen auf den
43 alten Fällen liegen in derselben Größenordnung — **auf dem Bestandskorpus
misst diese Eval keinen Modellunterschied, sondern Rauschen.** Aussagekräftig
sind allein die `schwer-*`-Fälle, und dort steht es 7 : 8–9 : 8. Ein Gewinn
von ein bis zwei Fällen von zehn.

*Zweitens die Latenz.* Lotti **streamt** ins Fenster. Flash antwortet nach
gut einer Sekunde, 3.1 Pro nach knapp fünfzehn — und der größte Teil davon
ist Denken, bei dem nichts ankommt: 73.291 Completion-Tokens im Lauf gegen
3.352 bei Flash, also 22-mal so viel erzeugter Text, von dem die Nutzerin
keine Zeile sieht. Tim hat gesagt, es dürfe „einen Ticken länger dauern";
ein p95 von 22–30 Sekunden ist kein Ticken, das ist ein Ladebalken. Sonnet
liegt mit gut vier Sekunden dazwischen — und ist dabei das schlechteste der
drei.

*Drittens das Geld.* 0,07–0,12 ct je Aufruf heute gegen 2,87 ct (3.1 Pro)
und 1,56 ct (Sonnet), also das 25- bis 43-Fache. Bei 5.000 Erklärungen im
Monat wären das 144 $ statt 5 $ — gemessen am Monatsbudget von 40 $
(`usage.dashboard`) ist das der ganze Topf für ein Feature. Die Kasse ist
damit **doch** ein Argument, aber nicht das erste: Latenz und erfundene
Zahlen sind es.

**Empfehlung — die Entscheidung ist Tims:** bei `google/gemini-2.5-flash`
bleiben. Die Fälle, die ein stärkeres Modell zusätzlich schafft, sind
Rechenfehler an gemischten Einheiten und an zwei Stichtagen. Beides ist im
**Baustein** lösbar — die Wirtschaftspläne in einer Einheit ausgeben, den
Anteil unbesetzter Stellen vorrechnen, so wie PR 26 es mit der Pro-Kopf-Zahl
gemacht hat —, und zwar für null Millisekunden und null Cent. Ein Modell,
das dafür vierzehn Sekunden braucht und dabei anfängt, Pro-Kopf-Zahlen zu
erfinden, ist der teurere Weg zum schlechteren Ergebnis. Wenn mehr Compute,
dann nicht hier: Lotti sucht nicht, sie liest vor, was im Prompt steht.
Der Ratsweg (`COUNCIL_QA_MODEL`) sucht wirklich — dort wäre es zu messen.

**Zwei Befunde nebenbei.**

1. Die großen Geminis (Pro der 2.5/3.x-Reihe, 3.8-flash) **denken zwingend**:
   `reasoning.enabled=false` beantwortet OpenRouter mit HTTP 400 „Reasoning
   is mandatory for this endpoint". Mit Lottis Budget von 350 Tokens
   (`assistant.MAX_TOKENS`) kam die Antwort abgeschnitten zurück —
   completion_tokens 346, sichtbarer Text 53 Zeichen, **ohne Fehler**. Sie
   brauchen deshalb einen Token-Boden in `MODEL_PARAMS`
   (`GEMINI_DENK_MIN_MAX_TOKENS`, 4.000, in diesem PR eingetragen). Wer eins
   von ihnen einstellt, ohne den Eintrag zu haben, bekommt kaputte Antworten
   und keinen Hinweis darauf.
2. Alle drei Modelle liefen unter dem Haus-Routing
   (`NWZ_OPENROUTER_ROUTING=on`, ZDR-Pflicht, China-Anbieter ausgeschlossen)
   ohne eine einzige Ausnahme. Keins fiel mangels ZDR-Anbieter aus der Wahl,
   und keine Zeile blieb ohne Kostenwert.

**Was die Zahlen NICHT hergeben.** Zwei rote Fälle hängen an der Wortwahl,
nicht am Verhalten: `sitzung-tagesordnung` verlangt das Wort „Gremien", und
3.1 Pro schreibt stattdessen „Gruppen" — also genau das, was der Prompt mit
„kein Fachwort ohne Erklärung" verlangt. Die Erwartung stammt aus einer
früheren Runde und bleibt hier unangetastet, damit der Vergleich gegen die
bekannte Basislinie gilt; wer sie anfasst, misst neu.

### PR 30 — Der Baustein-Text der anderen Seite

**Was — nur, wenn PR 21 gemessen nicht reicht.** Lotti weiß seit PR 21, WO
etwas steht, nicht WAS dort steht. Wenn die Auswertung zeigt, dass Verweise
oft angeklickt und dann dieselbe Frage noch einmal gestellt wird, lohnt der
zweite Schritt: Die Haushalts-Seiten liefern ihre Bausteine (Titel + Text,
dieselben, die `data-erklaer` trägt) über einen Endpunkt, den Lotti bei
einer Frage mit klarem Seitenbezug nachlädt. Das ist der Punkt, an dem
Regel 6 aus Plan 1 („keine Kopie der Seitentexte") fällt — bewusst, mit
Zahlen, nicht vorher.

### PR 31 — Markieren statt Modus (gebaut 23.09.2026, Branch `claude/lotti-markieren`)

**Anlass.** Tim am 23.09.2026: „Dieses ‚Frag mich zu dieser Seite‘ und dann
kann man irgendwas anklicken — das ist so mega komisch, keiner versteht, wie
das funktioniert, selbst bei mir hat es gedauert. An ein paar Orten tauchen
Fragezeichen auf … Und dieses Kleine unten in der Mitte ‚Auf dieser Seite
kann ich gerade nichts einzeln erklären‘ sollte nicht angezeigt werden."

**Was.** Der Erklär-Modus ist weg — der Chip „Etwas auf der Seite zeigen",
sein Icon am Composer, die „?"-Abzeichen, der Hinweis unten. Ebenso der Chip
„Markiertes erklären": Er tat dasselbe wie der neue Knopf, nur weiter weg.
Neu ist ein kleiner Knopf **„Lotti fragen" an der Markierung**
(`components/assistentin/markier-knopf.tsx`, Logik in `lib/markieren.ts`):
Er steht unter dem Ende der Auswahl, fragt beim Klick sofort „Was bedeutet
das?" und zeigt die Markierung im Verlauf als Zitat. Der Baustein um die
Markierung (nächster `data-erklaer`-Vorfahr) geht als Kontext mit; das
Zitat reist im Gedächtnis mit, damit „und warum so viel?" danach ein „das"
hat.

**Behalten:** die `data-erklaer`-Anker. Sie tragen weiter die Landkarte für
„Wo finde ich …?", die Anschluss-Chips „… erklären" und jetzt den
Baustein-Kontext einer Markierung.

**Nebenbei behoben:** Eine Frage aus dem Modus ging verloren, wenn die
Einwilligungs-Karte noch offen war; die Markier-Frage wartet jetzt auf sie.
Eine Auswahl in einem `<input>` meldet Chromium mit dem Eltern-Element als
Anker — geprüft wird deshalb zusätzlich der Fokus. (Die 422 bei langen
Bausteinen, auf die die ersten Bilder dieses PRs liefen, hat #1512
parallel an `kuerze` behoben.)

**iOS:** Die App hatte nie einen Erklär-Modus (`AssistantSheet.swift`); dort
ist nichts nachzuziehen.

## 3. Reihenfolge

PR 23 und 24 zusammen zuerst — sie sind die Antwort auf Tims Hauptpunkte
und ändern die Bedienung. Bild vor dem Merge, mit denselben Seiten wie in
Tims Screenshot. Dann 25 und 27 (klein, kein neuer Kontext), dann 26 und 28,
dann 29 als Messung. 30 wartet auf Zahlen.

## Anhang — Was aus Runde 2 hier eingeflossen ist

| Befund (Runde 2) | Stand |
|---|---|
| Glossar-Popover ragt aus dem Fenster | PR 22: inline aufklappen |
| Ladeanzeige kaum sichtbar | PR 22: Punkte mit Bewegung + Schritt-Text aus `step` |
| Zu viele Chips | PR 24 |
| „Den Rat fragen" unverständlich, nicht automatisch | PR 23 |
| Wegweiser zeigt auf die eigene Seite | PR 24 |
