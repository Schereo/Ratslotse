# Umsetzungsplan: Breite Schirme nutzen (1440p und 21:9)

Stand: 24.09.2026. Geschrieben wie die übrigen `plan-*.md`: **ohne das
Gespräch dahinter ausführbar**. Jeder Abschnitt in §3 ist ein Pull Request
mit Dateien, Bauform, Prüfung und Fertig-Kriterium. Die Zahlen stammen aus
einer Messung gegen echte Daten (`lokale_daten.py`, Abzug dev vom
23.09.2026); der Befehl steht in Anhang A.

Wer das umsetzt, liest **vorher** vollständig: die Wurzel-`CLAUDE.md`,
`web/frontend/CLAUDE.md` und **`web/frontend/DESIGNSPRACHE.md`** — dort vor
allem die Abschnitte zu den Breakpoints (`breit`/`weit`/`desk`/`tab`),
„Karten-Raster: Container-Query statt Fenster-Stufe" und „Lesebreite: den
KASTEN deckeln, nicht den Text darin". Dieser Plan ändert keine dieser
Regeln, er wendet sie auf größere Schirme an.

**Jeder PR hier ist ein UI-PR.** Vor dem Merge gehen Bilder an Tim
(`SendUserFile`), in den Breiten 1920, 2560 und 3440 px — und auf sein
Gegenlesen wird gewartet, auch bei grüner CI.


## 0. Der Anlass

Tim am 24.09.2026, mit einem Bild von „Mein Viertel" auf seinem
1440p-Monitor:

> Ich habe hier einen 1440p-Bildschirm und der hat halt immer links und
> rechts so ein bisschen eine Kante, wo nichts angezeigt wird. Ähnlich bei
> der Arbeit, so ein 21:9. Wäre cool, wenn du überprüfen könntest, welche
> Views davon profitieren könnten, dass sie auf größeren Screens besonders
> angezeigt werden — mehr anzeigen, Sachen bis an die Ränder fließen lassen.

Die Vorgeschichte: Am 18.08. hat der Breakpoint `weit` (≥ 1680 px) den
Hüllen-Deckel von 1280 auf 1600 px angehoben — ausdrücklich für 21:9. Danach
ist nichts mehr passiert: Über 1680 px wächst **keine** Seite mehr mit.


## 1. Messung

Gemessen wurde die Außenkante des sichtbaren Inhalts in `#main` (alles mit
Hintergrund, Rahmen, Grafik oder Text), angemeldet als Admin, alle Schalter
an. „Genutzt" ist der Anteil der **Fensterbreite**, den Inhalt überspannt;
die Seitenleiste (240 px) zählt als nicht genutzt.

| Seite | 1920 px | 2560 px (1440p) | 3440 px (21:9) | Deckel heute |
|---|---:|---:|---:|---|
| Heute, Suche, Sitzungen, Analyse, Themen, Abos, Quiz, Admin, Ideen, Konto, Haushalt-Unterseiten | 80 % | 60 % | **45 %** | Hülle 1600 px |
| Haushalt-Übersicht | 90 % | 67 % | 50 % | Hülle 1600 px |
| Mein Viertel (`/karte`) | 89 % | 67 % | **50 %** | Hülle 1600 px (die Karte ist randlos *innerhalb* der Hülle) |
| Wahlabend (öffentlich) | 63 % | 47 % | 35 % | `max-w-7xl` im eigenen `main` |
| Beschluss | 53 % | 40 % | **30 %** | `max-w-5xl` in `council/decision/view.tsx` |
| Merkliste | 53 % | 40 % | 30 % | `max-w-5xl` |
| Sitzung (Tagesordnung) | 47 % | 35 % | 26 % | `max-w-4xl` |
| Person, Thema, Ort | 40 % | 30 % | **22 %** | `max-w-3xl` |

In Pixeln: Auf 1440p bleiben bei den Hüllen-Seiten links und rechts je
**392 px** leer, auf 21:9 je **832 px**. Beim Beschluss sind es 648 bzw.
1.088 px je Seite, bei der Person 776 bzw. 1.216 px.

Was die Zahlen nicht sagen: **Nicht jede leere Fläche ist ein Fehler.** Eine
Tagesordnung, deren Zeilen über 3.000 px laufen, liest sich schlechter als
eine mit Rand. Die Frage je Seite ist deshalb nicht „wie breit?", sondern
„was käme mit mehr Platz *zusätzlich* ins Bild?". Daraus die drei Bauformen
in §2.


## 2. Die drei Bauformen

**A. Bühne — randlos bis an die Kante.** Karten und Grafiken, deren Inhalt
selbst Fläche ist. Mehr Breite heißt mehr Stadt, mehr Zeitachse. Hier fällt
der Hüllen-Deckel ganz weg. Betroffen: Mein Viertel, die Wahlabend-Karte,
die Karten-Spielform im Quiz.

**B. Raster — mehr Spalten, nicht breitere Karten.** Seiten aus Karten
verschiedener Art. Mehr Breite heißt: eine Spalte mehr, also mehr auf einen
Blick über dem Falz. Der Deckel steigt, die einzelne Karte wird *nicht*
breiter als heute. Betroffen: Heute, Analyse, Haushalt, Admin, Konto.

**C. Detail — eine Spalte daneben, nicht eine breitere Spalte.** Seiten mit
Lesetext. Die Lesespalte behält ihre Breite; was heute *unter* ihr steht
(Ähnliche Beschlüsse, Beratungsfolge, Dokumente, Ämter-Grafik), zieht ab
genug Platz *neben* sie. Betroffen: Beschluss, Sitzung, Person, Thema, Ort,
Suche, Sitzungen-Liste.

### 2.1 Ein neuer Breakpoint und ein Ausweg aus der Hülle

- **`ultra`: `(min-width: 2200px)`** in `web/frontend/tailwind.config.ts`,
  neben `weit`, mit Kommentar im Stil der Nachbarn. Begründung der Zahl:
  2560 − 240 (Seitenleiste) − Polster ≈ 2250 px Inhalt; ab 2200 passt eine
  dritte 600-px-Spalte neben zwei heutige. Ein 1440p-Schirm mit 125 %
  Skalierung (2048 px CSS) bleibt bei `weit` — das ist gewollt, dort ist der
  Rand schmal genug.
- **Die Hülle bekommt einen zweiten Deckel**, nicht einen höheren:
  `ultra:max-w-[2200px]` in `app/(app)/layout.tsx`. Über 3440 px (5K, 32:9)
  bleibt also Rand stehen — eine Zeile über 3.000 px ist nirgends gewollt.
- **Seiten der Form A verlassen die Hülle ganz.** Heute macht `/karte` das
  mit negativen Rändern (`-mx-4 sm:-mx-6 lg:-mx-8`), bleibt aber im Deckel.
  Statt einer weiteren Sonderregel eine Liste in einem Ort:
  `lib/vollbreit.ts` mit `export const VOLLBREIT: readonly string[]` und
  `istVollbreit(pathname)`; das Layout lässt für diese Pfade `max-w-*` und
  Polster weg. **Nicht** über einen Kontext aus der Seite heraus — das Layout
  rendert zuerst, und die Seite spränge beim Laden von schmal auf breit.
- **DESIGNSPRACHE.md** bekommt im Breakpoint-Abschnitt einen Absatz zu
  `ultra` und zu den drei Bauformen; der Satz „Die Breite deckelt die Hülle
  (`max-w-7xl` im App-Layout)" wird auf den neuen Stand gezogen.

**Was sich dadurch allein noch nicht ändert**, und das ist Absicht: Eine
Seite, die heute nur eine Spalte kennt (Sitzungen-Liste, Suche), würde mit
dem höheren Deckel einfach breiter — genau das Falsche. Deshalb zieht PR 1
den Deckel nur für Seiten hoch, die ihn *anfordern* (§3, PR 1).


## 3. Die Pull Requests

Reihenfolge nach Nutzen je Aufwand. PR 1 ist Voraussetzung für alle
übrigen; ab PR 2 sind sie unabhängig voneinander.

### PR 1 — Hülle: `ultra`, Vollbreite-Liste, Anforderung pro Seite

- `tailwind.config.ts`: `ultra` wie in §2.1.
- `lib/vollbreit.ts` (neu): `VOLLBREIT` (anfangs `["/karte"]`) und
  `ULTRA_BREIT` (Seiten, die den 2200er-Deckel wollen; anfangs leer, jeder
  weitere PR trägt seine Seite ein). `breiteFuer(pathname): "voll" | "ultra"
  | "normal"`.
- `app/(app)/layout.tsx`: Klasse der Inhalts-Hülle aus `breiteFuer`.
  `/karte` verliert seine negativen Ränder (`app/(app)/karte/view.tsx:246`),
  weil es kein Polster mehr gibt, das sie ausgleichen müssten.
- Test `lib/vollbreit.test.ts`: jede eingetragene Route existiert als
  `app/(app)/<pfad>/page.tsx` — ein Tippfehler in der Liste wäre sonst
  dauerhaft wirkungslos und sähe aus wie „noch nicht umgestellt".
- **Fertig, wenn** `/karte` bei 3440 px von der Seitenleiste bis zur rechten
  Fensterkante reicht und alle anderen Seiten pixelgleich zu vorher sind
  (Anhang A vorher/nachher, Spalte „genutzt" unverändert außer `/karte`).

### PR 2 — Mein Viertel randlos und mit breiterer Schublade

Tims Ausgangsbild. Die Karte ist das Wertvollste, was mit Breite wächst.

- Nach PR 1 füllt die Karte die Fläche. Die rechte Spalte (heute fest um
  360 px) wird ab `weit` 420 px, ab `ultra` **zwei** Spalten à 400 px:
  links Übersicht + Haustür-Suche + Wahlergebnis, rechts „Gerade in der
  Stadt" + „Themen, die gerade laufen" + Ortsbereiche. Heute muss man für
  die Ortsbereiche-Liste scrollen, bei 1440p passt sie daneben.
- Wo die Spalte gebaut wird: `app/(app)/karte/view.tsx` ab Zeile 246; die
  Spalten sind Kinder mit `flex flex-col` (Designsprache: Spalten statt
  Zeilen, die Blöcke sind sehr verschieden hoch).
- Die Spalte liegt *neben* der Karte (Flex-Reihe), nicht über ihr — die
  Kartenfläche schrumpft also, wenn die Spalte wächst. Leaflet merkt das
  nicht von selbst: Nach dem Breitenwechsel `map.invalidateSize()` und den
  Stadt-Zuschnitt aus `components/stadt-karte.tsx:246` erneut anwenden
  (ein `ResizeObserver` auf dem Karten-Container), sonst steht Oldenburg
  nach dem Umschalten der Fensterbreite abgeschnitten.
- **Fertig, wenn** bei 2560 × 1440 die ganze Stadt, beide Spalten und die
  ersten zehn Ortsbereiche ohne Scrollen zu sehen sind.

### PR 3 — Heute: dritte Spalte

- `components/heute-widget.tsx:18`: `@3xl/widgets:grid-cols-2` bekommt
  `@[1800px]/widgets:grid-cols-3`. Heute in Zeilen gerastert — nach der
  Designsprache für verschieden hohe Karten auf **Spalten** umstellen
  (`flex flex-col` je Spalte); welche Karte wohin, entscheidet der Inhalt:
  links „Die Woche im Rat" (lang), Mitte Rückblick/Zahl der Woche/Fundstück,
  rechts Verlauf/Themen.
- `/dashboard` in `ULTRA_BREIT`.
- **Fertig, wenn** bei 2560 px keine Karte breiter ist als bei 1920 px und
  über dem Falz mindestens eine Karte mehr steht.

### PR 4 — Beschluss: Nebenspalte wird zur dritten Spalte

Heute `max-w-5xl` (1024 px): Lesespalte + „Auf einen Blick"-Spalte, darunter
Ähnliche Beschlüsse. Bei 1440p bleiben 1.296 px ungenutzt.

- `app/(app)/council/decision/view.tsx:674`: `max-w-5xl` → ab `weit`
  `max-w-[1480px]`, ab `ultra` `max-w-[1900px]`.
- Ab `weit` zieht **Ähnliche Beschlüsse** aus dem Fluss in eine eigene
  rechte Spalte, ab `ultra` zusätzlich die **Beratungsfolge** der Vorlage
  (heute weit unten). Die Lesespalte selbst bleibt bei ihrer Breite
  (`max-w-[76ch]`-Regel unverändert).
- Druckansicht (`print-hidden`, `@media print`) muss einspaltig bleiben —
  prüfen mit `page.emulateMedia({ media: "print" })`.
- `/council/decision` in `ULTRA_BREIT`.

### PR 5 — Sitzung: Tagesordnung links, Punkt rechts

Heute `max-w-4xl`, der Punkt klappt im Fluss auf. Ab `weit` wird daraus eine
Liste-plus-Vorschau: Tagesordnung links (die heutige Breite), der gewählte
Punkt rechts klebend (`sticky top-4`) mit Beschlusstext, Abstimmung,
Kurzfassung. Das spart auf dem großen Schirm jedes Auf- und Zuklappen.

- `app/(app)/council/sitzung/view.tsx:74` und die TOP-Komponente, die heute
  aufklappt. Der Zustand „welcher Punkt ist offen" steht schon im Link
  (`?top=`, `useTopsAusLink`) — die Vorschau liest denselben Wert, es gibt
  keinen zweiten.
- Unter `weit` bleibt alles, wie es ist.

### PR 6 — Person, Thema, Ort: Raster statt Einzelspalte

Heute `max-w-3xl`, also 768 px — bei 21:9 steht die Seite als schmaler
Streifen in der Mitte (22 % genutzt).

- **Person** (`council/person/view.tsx:170`, `:362`): ab `weit` zweispaltig
  — links Kopf, Aktuelle Ämter (die Balken gewinnen Zeitachse), rechts
  Zugehörigkeit, Präsenz je Gremium, Anträge. Die Ämter-Balken bekommen die
  Jahreszahlen, die heute fehlen, weil nur „2022 … heute" passt.
- **Thema** und **Ort** (`thema/view.tsx:88`, `ort/view.tsx:33`): ab `weit`
  Liste der Beschlüsse links, rechts Zeitleiste/Karte bzw. Ortskarte klebend.
- Alle drei in `ULTRA_BREIT` erst, wenn der Inhalt eine dritte Spalte trägt
  (Person: ja, Anträge; Thema/Ort: nein, dort genügt `weit`).

### PR 7 — Suche und Sitzungen-Liste: Vorschau-Spalte

Die Suche hat bei 21:9 Trefferzeilen von 1.536 px — schon heute zu lang zum
Lesen, und die Beschreibung ist nach zwei Zeilen abgeschnitten.

- Ab `ultra`: Trefferliste links (~900 px), rechts eine klebende Vorschau
  des angeklickten Beschlusses (Kopf, Kurzfassung, Wortlaut, Abstimmung), ein
  zweiter Klick bzw. „Öffnen" führt auf die volle Seite. Tastatur: ↑/↓
  wechselt die Vorschau. **Die Vorschau lädt über dieselbe Abfrage wie die
  Detailseite** (`/council/decision/{id}`, react-query-Schlüssel teilen),
  damit „Öffnen" danach sofort steht.
- Dasselbe für die Sitzungen-Liste (`?tab=sessions`): Liste links, rechts
  die Tagesordnung der gewählten Sitzung.
- **Größter Eingriff des Plans und eine Designentscheidung** — erst nach
  Tims Ja zu §5 Frage 2 bauen.

### PR 8 — Haushalt, Admin, Analyse: Deckel hoch

Reine Raster- und Tabellen-Seiten. Hier genügt meist, die Seite in
`ULTRA_BREIT` einzutragen und zu prüfen, dass die vorhandenen
Container-Queries die Spalten schon selbst vermehren.

- Je Seite ein Bild bei 2560 px; wo eine Karte dadurch über 1.200 px breit
  wird, ohne mehr zu zeigen, bleibt die Seite draußen.
- Tabellen (Admin *Web-Nutzer*innen*, Haushalt *Produkte*) gewinnen Spalten,
  die heute unter `hidden weit:table-cell` o. ä. verborgen sind — nachsehen,
  welche es gibt.
- Der Haushalts-Bereich ist dev-only (Gate im `haushalt/layout.tsx`), das
  ändert sich nicht.

### PR 9 — Wahlabend: Karte und Tabelle nebeneinander

`components/wahlabend/view.tsx:1048` und `kopf.tsx:14` deckeln auf
`max-w-7xl` (1280 px), unabhängig von der App-Hülle. Ab `ultra`: Karte links
groß, Sitze/Mehrheiten/Verlauf rechts. **Termin:** Die OB-Stichwahl ist am
27.09.2026 — dieser PR fährt **nicht** vor dem Wahlabend, eine Umstellung
der Seite am Abend selbst ist das Risiko nicht wert.


## 4. Was ausdrücklich nicht passiert

- **Kein Text wird breiter.** Jede Lesespalte behält ihren `ch`-Deckel. Wo
  ein Text in einer breiter gewordenen Karte steht, greift die bestehende
  Regel (Spalten ab `@3xl`, s. DESIGNSPRACHE § Lesebreite).
- **Fragen** bleibt, wie es ist: Die Seite nutzt `weit` schon für Antwort
  (980 px) plus Belege (420 px) und ist im Viewport verankert. Mehr Breite
  würde nur die Antwortzeilen verlängern.
- **Keine Seitenleiste, die mitwächst.** 240 px bleiben 240 px.
- **Das iPad ist nicht betroffen.** `ultra` liegt über jeder iPad-Breite;
  `weit` ebenfalls (größtes iPad quer: 1366 px).


## 5. Fragen an Tim, bevor gebaut wird

1. **Obergrenze 2200 px** für Raster- und Detailseiten, randlos nur für
   Karten — oder sollen auch die Raster bis an den Rand gehen?
2. **Vorschau-Spalte in der Suche** (PR 7): gewollt? Sie ändert, wie man auf
   dem großen Schirm sucht (Klick öffnet nicht mehr die Seite, sondern die
   Vorschau).
3. **Reihenfolge**: Vorschlag PR 1 → 2 → 4 → 3 → 6 → 5 → 8 → 7 → 9.


## Anhang A — Messung wiederholen

Voraussetzung: Backend mit echten Daten und allen Schaltern
(`FEATURE_FLAGS='*' python scripts/dev.py start`), Frontend mit
`NEXT_PUBLIC_RATSLOTSE_ENV=dev`, Konten aus `saat_konten.py`, und für
`chef@example.org` `setup_done_at` gesetzt — sonst steht der
Einrichtungs-Assistent vor jeder Seite und die Messung misst ihn.

Das Skript meldet sich an, lädt jede Route in jeder Breite, wartet 4 s und
bestimmt die äußerste linke und rechte Kante aller sichtbaren Elemente
unter `#main`, die schmaler als `#main` selbst sind (so zählt der
Seitenhintergrund nicht mit):

```js
// Kern der Messung, im Seitenkontext ausgeführt
const main = document.querySelector("#main") || document.body;
const mr = main.getBoundingClientRect();
let L = Infinity, R = -Infinity;
for (const el of main.querySelectorAll("*")) {
  const b = el.getBoundingClientRect();
  if (b.width < 4 || b.height < 4 || b.top > 3000 || b.width > mr.width - 2) continue;
  const cs = getComputedStyle(el);
  const sichtbar = cs.backgroundColor !== "rgba(0, 0, 0, 0)" || cs.borderTopWidth !== "0px"
    || ["IMG", "CANVAS", "svg"].includes(el.tagName)
    || [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
  if (sichtbar) { L = Math.min(L, b.left); R = Math.max(R, b.right); }
}
// genutzt = (R - L) / innerWidth
```

Breiten: 1920, 2560, 3440 bei 1100 px Höhe. Für die Bilder an Tim
zusätzlich 2048 (1440p mit 125 % Skalierung).
