# Regeln für `web/frontend/`

Next.js 16 (App Router, Turbopack) mit React 19, nur die Webanwendung. Bis
11/2026 wurde derselbe Code zusätzlich als statischer Export in eine
Capacitor-Hülle gebaut (Android, nie veröffentlicht); einige Konventionen
unten stammen daher und gelten weiter.

**Pflichtlektüre vor UI-Arbeit:** [`DESIGNSPRACHE.md`](DESIGNSPRACHE.md).
Grafiken zusätzlich: [`components/grafik/README.md`](components/grafik/README.md).
Allgemeines: [`../../CLAUDE.md`](../../CLAUDE.md).

**Die Doku zur installierten Next-Fassung liegt im Paket:**
`node_modules/next/dist/docs/` (nach `npm ci`). Next 16 weicht an vielen
Stellen von dem ab, was man aus 14 kennt (`params` und `searchParams` sind
Promises, `middleware.ts` heißt `proxy.ts`, `next lint` gibt es nicht mehr) —
dort nachlesen, bevor eine Next-API aus dem Gedächtnis benutzt wird. `next dev`
würde denselben Hinweis von sich aus in eine `AGENTS.md` schreiben; das ist in
`next.config.mjs` abgeschaltet (`agentRules: false`), die Regeln stehen hier.

## Vorher: echte Daten holen

Eine Oberfläche gegen eine leere Datenbank zu bauen heißt, an den Daten vorbei
zu bauen. Eine Liste, die nie mehr als drei Einträge sieht, bekommt keine
Paginierung. Ein Titel, der nie lang wird, bricht erst auf dem Server um. Ein
Feld, das lokal immer `null` ist, fällt niemandem auf.

```bash
python scripts/lokale_daten.py hol    # Ratsdaten von dev, ~220 MB, ~25 s
python scripts/lokale_daten.py setz   # in data/ DIESES Worktrees
python scripts/saat_konten.py         # erfundene Konten dazu
```

Danach steht der Bestand: rund 8.200 Beschlüsse, 870 Sitzungen, 42.000
Wortbeiträge, dazu ein Konto mit Themen und Treffern. Anmelden als
`nutzerin@example.org`, `chef@example.org` (Admin-Bereich) oder
`ratsfrau@example.org` — nur die kommt in den **Haushalt**, er hängt am Recht
`budget`. Passwort überall `password123`. `stand` sagt, wie alt der Abzug ist.

Der Abzug trägt **keine** Konten und keine Personendaten; Näheres in der
Wurzel-[`CLAUDE.md`](../../CLAUDE.md).

## Ans Backend nur über `lib/api.ts`

`api.get/post/put/del` setzt die Adresse, schickt das Sitzungs-Cookie mit,
übersetzt Validierungsfehler in deutsche Sätze, setzt eine Zeitgrenze und
behandelt 401 zentral.

**Ein nacktes `fetch("/api/…")` ist ein Fehler**, auch wenn es funktioniert:
Es umgeht all das. Wo der Wrapper wirklich nicht passt (Streams), nimm
`apiUrl()` aus demselben Modul. Entstanden ist die Regel, weil der relative
Pfad in der Capacitor-Hülle ins Nichts zeigte; sie bleibt, weil eine Stelle
für die Adresse besser ist als achtzig.

Seit 09/2026 ist das keine Bitte mehr, sondern eine ESLint-Regel
(`no-restricted-syntax` in `eslint.config.mjs`) und damit Teil von `npm run lint`
und `pruefe.py`. Sie trifft genau den Fehler — ein Zeichenketten- oder
Template-Literal, das mit `/api/` beginnt — und lässt `apiUrl(…)` und absolute
URLs in Ruhe. Eingeführt wurde sie mit **null** Verstößen im Bestand; sie
räumt nichts auf, sie hält.

## Antworttypen aus dem Vertrag ziehen

`lib/api-schema.ts` ist generiert (`npm run api:typen`), `lib/vertrag.ts` macht
daraus benutzbare Typen: `ApiAntwort<"/council/decision/{decision_id}">` —
Pfad **ohne** `/api`, das hängt `api.get()` selbst an.

Einen Antworttyp in `lib/types.ts` nachzutippen ist eine zweite Wahrheit neben
dem Backend. Sie veraltet lautlos, und zwar in jedem Frontend einzeln. Neue
Typen also aus `lib/vertrag.ts`; die verbliebenen Handtypen sind Restschuld,
kein Vorbild.

## Konventionen aus der Zeit des statischen Exports

Der Export ist weg, diese Regeln bleiben:

- `useSearchParams` zwingt die Seite in eine Suspense-Grenze; ohne sie bricht
  `next build` beim Vorrendern ab. Wo es unvermeidlich ist, muss die Grenze
  wirklich da sein — sonst `window.location` nach dem Mount.
- Detailseiten arbeiten mit Query-Parametern statt dynamischer Pfadsegmente
  (`lib/routes.ts`). Mails, geteilte Links und die iOS-App kennen diese
  Adressen; ein Umbau bräuchte für jede eine Weiterleitung.
- Pfade werden über `pfad()` aus `lib/utils.ts` verglichen, nicht roh
  (`pathname === "/council"`): Ein Schluss-Schrägstrich machte den exakten
  Vergleich schon einmal blind.
- Ein Redirect in `next.config.mjs` ersetzt nie das Nachziehen der internen
  Links.

## Gemessene Fallen

- **Der Dev-Server baut in ein eigenes Verzeichnis.** Ein `next build` neben
  einem laufenden Dev-Server überschreibt dessen Chunks; die Seite liefert
  danach für jede Chunk-URL eine 404-Seite. Das sieht aus wie ein Fehler im
  Code und ist keiner. Die Konfiguration ist deshalb eine Funktion über die
  Phase — nicht zu einem Objekt zurückbauen. (Next 16 trennt Dev und Build
  inzwischen selbst, der Dev-Server schreibt nach `<distDir>/dev`, hier also
  `.next-dev/dev`. Die eigene Trennung bleibt, weil die Deploys daran hängen.)
- **Turbopack schreibt keinen Cache auf die Platte**, weder beim Bauen noch im
  Dev-Server (beide Schalter in `next.config.mjs`). Der Dev-Cache wog nach
  einem Nachmittag 1,4 GB je Worktree und hielt einen Fehler fest, der keiner
  war — auch ein neu gestarteter Dev-Server meldete ihn. Wer den Cache
  einschaltet, liest vorher die Begründung dort.
- **Der Deploy baut ebenfalls daneben.** Dasselbe Bild traf den alten
  `next start` auf den Servern: jede Seite ungestaltet, bis zum Neustart.
  Die Deploys bauen deshalb mit `NEXT_DIST_DIR=.next-build` (wirkt nur in der
  Build-Phase) und schalten erst unmittelbar vor `systemctl restart` um;
  `tests/test_pruefe_build_chunks.py` hält die Reihenfolge in beiden
  Deploy-Workflows fest.
- **Die Typprüfung des Builds liest auch `.next/types` — die Typen des
  Builds, der gerade ausliefert.** Die `tsconfig.json` schließt alle drei
  Bauverzeichnisse ein (sonst schreibt Next sie bei jedem Lauf um), und Next
  legt dort je Route eine Prüfzeile ab. Passt die nicht zum neuen Stand — eine
  Route gelöscht oder umgezogen, ein anderes Next —, scheitert der Build an
  Dateien, die nicht seine sind (22.11.2026 auf dev: „Cannot find module
  'next/types.js'"). Die Deploys räumen `.next/types` deshalb vor dem Build
  weg; `next start` braucht es nicht. **Kein `exclude` in der tsconfig
  dafür:** Der gewöhnliche Build nach `.next` prüft dann die Seiten-Exporte
  gar nicht mehr und meldet trotzdem Erfolg. Lokal dasselbe Bild nach einem
  Zweigwechsel: `rm -rf .next/types`.
- **Tailwinds `min-[…]`-Kurzform ist in diesem Projekt aus.** Die Klasse steht
  im DOM, CSS gibt es keins. Benannte Breakpoints benutzen.
- **Breiten mit `getBoundingClientRect()` messen**, nicht `clientWidth` — das
  rundet, und zwar sichtbar auf genau den Fensterbreiten, auf denen niemand
  testet.
- **Der Kartenkachel-Parameter heißt `key`, nicht `api_key`.** Ein falscher
  Name liefert Status 200 samt Wasserzeichen; der Fehler sieht aus wie „Key
  wirkt nicht". Die URL entsteht zentral in `lib/basemap.ts`.
- **Ein Gate braucht auch seine Einstiegspunkte.** Seite gesperrt, Navigation
  und Metadaten aber nicht — dann stehen die Links weiter da und führen ins
  Leere. Gilt unverändert für das Rechte-Gate: Wer einen Bereich sperrt,
  sperrt jeden Anker darauf mit.

## Rechte prüfen, nicht Rollen

`user.role === "admin"` stand bis 09/2026 an sechs Stellen. Ein Konto trägt
inzwischen **mehrere** Rollen, und jede neue hätte alle sechs gebraucht — die
vergessene Stelle meldet sich nicht, sie lässt jemanden rein oder sperrt ihn
aus. Deshalb geht jede Prüfung über [`lib/rechte.ts`](lib/rechte.ts):

```ts
import { darfHaushalt, darfAdmin, hatRecht } from "@/lib/rechte";
```

Die Rechte kommen als `user.permissions` aus dem Vertrag; welche Rolle welches
trägt, weiß nur der Server (`kern/roles.py`). Eine neue Rolle wirkt damit ohne
Frontend-Release. **Ein Rollenname im Frontend ist der Rückschritt** — auch in
einer Auswahl: Das Admin-Panel baut seine aus `GET /admin/roles`.

Zwei Dinge, die daran hängen:

- **Auf `loading` warten, bevor gesperrt wird.** `useAuth()` kennt die Rechte
  erst nach `/auth/me`; ein `notFound()` davor trifft jede berechtigte Person
  beim ersten Aufruf und bei jedem Neuladen.
- **Das Gate im Frontend ist Höflichkeit, nicht Schutz.** Die Sperre sitzt an
  den Endpunkten. Ein Bereich, dessen Seiten gegatet sind und dessen Routen
  offen, ist offen.

## Was die Prüfungen NICHT sehen

`tsc --noEmit` fängt Typfehler, sonst nichts: keine CSS-Klasse, kein Layout,
keinen `next build`. Die beiden Grafik-Proben rechnen Skalen und
Kachelgeometrie nach, weil beide Fehler typkorrekt waren. Ein Bild vor dem
Merge ersetzt keine dieser Prüfungen — und keine von ihnen ersetzt das Bild.


## Logik in `lib/` gehört unter Test

Seit 09/2026 läuft `npx vitest run` (auch über `pruefe.py` und die CI). Die
Testdateien liegen **neben** ihrem Modul: `lib/live.ts` → `lib/live.test.ts`.

**Was hierher gehört:** reine Funktionen — rechnen, formatieren, Adressen
bauen, Text zerlegen. Der Grenzfall ist hier eine Zeile; im Browsertest ist er
oft gar nicht herstellbar („16:29 gegen 16:30" im Live-Fenster bräuchte eine
gestellte Systemuhr).

**Was NICHT hierher gehört:** Komponenten. Ein Test, der JSX rendert, prüft am
Ende meist die eigene Fixture (s. [`../../tests/CLAUDE.md`](../../tests/CLAUDE.md))
und braucht eine DOM-Nachbildung, die mit jeder React-Fassung nachgezogen
werden will. Flüsse durch die Oberfläche prüfen die Browsertests
(`npx playwright test`).

**vitest 5 (seit 11/2026) verhält sich an drei Stellen anders als ältere
Beispiele.** Der Aufrufverlauf jedes Mocks wird vor jedem Test geleert
(`clearMocks` ist ab Werk an): Ein `vi.fn()` auf Modulebene bringt keine
Aufrufe aus dem Test davor mit. `vi.mock(…)` und `vi.hoisted(…)` stehen auf
oberster Ebene der Datei, sonst bricht der Lauf ab, statt zu warnen. Und ein
`expect(p).rejects…` ohne `await` lässt den Test scheitern. Verlangt wird
Node ≥ 22.12. vite kommt nur als Peer von vitest in den Baum — Next baut mit
Turbopack und braucht es nicht. Die Konfiguration heißt `vitest.config.mts`;
warum `.mts` und warum der Pool dort festgeschrieben ist, steht in der Datei.

**Browser-Speicher ohne jsdom.** `lib/__testhilfen/speicher.ts` liefert einen
`localStorage`/`sessionStorage`-Ersatz samt Schalter „gesperrt" — der echte
Fall im privaten Fenster. Eine ganze DOM-Nachbildung dafür zu laden kostet
Sekunden je Lauf.

**Nicht auf Ausgaben der Sprachdatenbank festnageln.** `toLocaleDateString`
liefert je nach ICU-Fassung „Mi." oder „Mi". Ein Test auf die genaue
Schreibweise geht beim nächsten Node-Sprung kaputt, ohne dass jemand einen
Fehler gemacht hat — prüfe die Zusage (welcher Tag, wie lang), nicht das
Zeichen.


## Browsertests: was sie abdecken und wie man sie startet

```bash
npx playwright test tests/e2e/09-konto    # eine Datei — der Normalfall lokal
E2E_PORT=3010 E2E_API_PORT=8012 npx playwright test tests/e2e/09-konto   # auf freien Ports
npx playwright test $(node tests/shard-specs.mjs 2 8)   # genau das, was Teil 2 der CI fährt
npx playwright test                       # alles — lokal 15–20 Minuten, s. u.
```

**Lokal nur die Dateien zur Änderung, die ganze Suite fährt die CI.** Seriell
auf einem Rechner braucht sie 15–20 Minuten (gemessen 22.11.2026: 19 min für
426 Tests), in der CI auf acht Läufern rund fünf. Wer lokal „zur Sicherheit"
alles startet, wartet also viermal so lang auf dasselbe Ergebnis. Lokal
gehören die Spec-Dateien dazu, die den geänderten Bereich prüfen — und
`12-navigation` plus `14-layout`, sobald die Hülle (Navigation, Layout,
`globals.css`) angefasst ist. Für alles, was neue Tests mitbringt, einmal
gegen die leere Datenbank (s. u.).

**In der CI läuft die Suite auf acht Läufern**, verteilt nach gemessener Dauer
je Datei (`tests/shard-specs.mjs`, Zahlen in `tests/e2e-durations.json`, s.
`e2e.yml`). Jeder bringt sein eigenes Backend auf einer eigenen
Wegwerf-Datenbank mit, die Teile teilen also nichts. Eine neue Spec-Datei
läuft von selbst mit — ohne Eintrag mit mittlerem Gewicht. Laufen die Teile
sichtbar auseinander: `python scripts/e2e_durations.py --write` zieht die
Dauern aus dem jüngsten grünen Lauf.

**Was lokal NICHT geht: mehrere Teile gleichzeitig starten.** Verschiedene
Ports reichen dafür nicht — alle `next dev` eines Worktrees teilen sich
**dasselbe `.next-dev/`**. Seit Next 16 startet der zweite gar nicht erst:

```
⨯ Another next dev server is already running.
- Local:        http://localhost:3410
- PID:          39577
```

Das gilt auch für einen Dev-Server, der noch von der Arbeit an einer Seite
läuft: Playwright startet seinen eigenen (`npm run dev -- --port …`) und
scheitert daran. Vorher den EIGENEN anhalten (die PID steht in der Meldung).
Bis Next 15 starteten beide und zerlegten sich gegenseitig den Webpack-Cache.
Das Ergebnis sah aus wie ein echter Befund und war keiner: 21 Fehlschläge
über vier gleichzeitige Teile, dieselbe Suite seriell 140/140 grün, jeder Teil
einzeln grün (gemessen 07.09.2026). Wer die Teile wirklich parallel messen will,
braucht je einen eigenen Worktree — oder lässt es und misst sie nacheinander.

**Die Ports sind einstellbar, und das braucht man wirklich.** Dieses Repo wird
in mehreren `git worktree`s gleichzeitig bearbeitet, und dort läuft fast immer
schon ein `next dev` auf 3000. Playwright bricht dann mit „is already used" ab
— und der naheliegende Ausweg, den fremden Prozess abzuschießen, trifft die
Arbeit einer anderen Sitzung. Erst `lsof -ti :3000` fragen, dann einen freien
Port nehmen.

**Die Ratsdatenbank ist in der CI LEER.** Lokal zieht `tests/start-backend.sh`
den Abzug aus `~/.cache/ratslotse`, in der CI gibt es ihn nicht. Ein Test, der
auf einen bestimmten Beschluss zeigt, ist dort also blind — entweder mockt er
seine Daten (`page.route`) oder er prüft eine Zusage, die in beiden Fällen
gilt („die Seite bietet ein Spiel an ODER sagt, dass gerade keins da ist").
**Vor dem Push einmal gegen leer laufen lassen:**

```bash
mkdir -p /tmp/leer && XDG_CACHE_HOME=/tmp/leer npx playwright test
```

Genau so ist der einzige Test aufgefallen, der nur mit Daten grün war.

**Abgedeckt sind (Stand 09/2026):**

| Datei | Worum es geht |
|---|---|
| `01-auth` | Registrieren, Anmelden, Abmelden, Passwort-Sichtbarkeit |
| `02-dashboard` | „Heute" |
| `03-oeffentlich` | Was OHNE Konto geht — und was nicht |
| `04-council` | Beschlüsse, Sitzungen, Filter, geteilte Sitzung |
| `05-topics` | Eigene Themen |
| `06-visual-pages` | Screenshots aller Hauptseiten, mobil und am Schreibtisch |
| `07-qa-feedback` | Daumen an der KI-Antwort |
| `08-haushalt` | Das Rechte-Gate und alle 15 Haushaltsseiten |
| `09-konto` | Anzeigename, Passwort, Erscheinungsbild, Löschung, Abmelden |
| `10-merkliste-abos` | Merkliste (Gruppen, Suche, Entfernen) und Ausschuss-Abos |
| `11-quiz-admin` | Quiz und die Admin-Grenze (drei Konten, drei Rechte) |
| `12-navigation` | Jeder Navigationspunkt, der aktive Zustand, Deep-Links |
| `13-einrichtung` | Der Assistent — den alle anderen absichtlich überspringen |
| `14-layout` | Keine Seite scrollt seitwärts (390 px und 320 px); die Antwort samt Parteien-Baustein gestubbt bei 375 und 320 px |
| `36-barrierefreiheit` | axe (WCAG 2.2 AA + Best Practices) auf allen Hauptseiten, hell und dunkel, **null Befunde**; Fokus nie unter einer festen Leiste (390 px) |

**Barrierefreiheit: Ausnahmen stehen am Element.** Was bewusst nicht passt
(die Haushalts-Leiste ist so schmal wie ihr Betrag), trägt
`data-a11y-ausnahme="<regel>"`, die Begründung steht in
`tests/e2e/a11y-ausnahmen.json`; `tests/test_a11y_ausnahmen.py` hält beide
Richtungen. Kein Abschalten einer Regel für eine ganze Seite — ein neuer
Befund daneben fiele sonst durch.

**Der Assistent ist der Sonderfall.** `einrichtungUeberspringen()` schaltet ihn
über den Server ab, weil seine Fläche (`fixed inset-0`) jeden Klick abfängt:
Der Abmelde-Knopf ist dahinter sichtbar UND unerreichbar. Wer den Assistenten
selbst prüft, ruft den Helfer NICHT auf — und braucht je Test ein **frisches**
Konto, denn ein eingerichtetes bekommt ihn nie wieder zu sehen.


## Layout-Invarianten statt Pixelvergleich

`14-layout.spec.ts` prüft **eine** Zusage, und zwar auf jeder Seite: Die Seite
scrollt nicht seitwärts. Auf dem Handy ist das der häufigste Layout-Fehler —
eine breite Tabelle, ein langes Wort ohne Trennmöglichkeit, ein `min-w` zu
viel —, und am Schreibtisch fällt er nie auf.

**Warum kein Pixelvergleich.** Er meldet jede beabsichtigte Änderung als
Fehler und wird nach dem dritten Mal weggeklickt. Was Gestaltung ist, gehört
vor Tims Augen (Bild per `SendUserFile`, Gegenlesen abwarten); was Mechanik
ist, gehört in einen Test, der nur bei echtem Bruch anschlägt.

**Ein Element DARF überstehen**, wenn es oder ein Vorfahr selbst scrollt —
genau so gehören breite Tabellen gebaut (`overflow-x: auto`). Der Test
berücksichtigt das; er meldet nur, was das FENSTER schiebt.

**Ein bekannter Befund gehört als `test.fail()` hinein**, nicht in eine Liste,
die niemand liest: Der Test meldet sich, sobald jemand ihn behebt, und dann
fliegt die Markierung raus. So stand bis 10/2026 die Startseite drin (bei
320 px 14 px zu breit); seit dem Review sind sie und fünf weitere Seiten in
der Breite und werden bei 320 px ausdrücklich geprüft.
