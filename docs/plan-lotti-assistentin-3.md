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

### PR 30 — Der Baustein-Text der anderen Seite

**Was — nur, wenn PR 21 gemessen nicht reicht.** Lotti weiß seit PR 21, WO
etwas steht, nicht WAS dort steht. Wenn die Auswertung zeigt, dass Verweise
oft angeklickt und dann dieselbe Frage noch einmal gestellt wird, lohnt der
zweite Schritt: Die Haushalts-Seiten liefern ihre Bausteine (Titel + Text,
dieselben, die `data-erklaer` trägt) über einen Endpunkt, den Lotti bei
einer Frage mit klarem Seitenbezug nachlädt. Das ist der Punkt, an dem
Regel 6 aus Plan 1 („keine Kopie der Seitentexte") fällt — bewusst, mit
Zahlen, nicht vorher.

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
