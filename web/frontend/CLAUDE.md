# Regeln für `web/frontend/`

Next.js. Derselbe Code wird zusätzlich als statischer Export in die
Capacitor-Hülle gebaut — die meisten Fallen hier kommen daher.

**Pflichtlektüre vor UI-Arbeit:** [`DESIGNSPRACHE.md`](DESIGNSPRACHE.md).
Grafiken zusätzlich: [`components/grafik/README.md`](components/grafik/README.md).
Allgemeines: [`../../CLAUDE.md`](../../CLAUDE.md).

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

`api.get/post/put/del` setzt die Basis-URL, die Anmeldeform (Cookie im Web,
Bearer in der App), übersetzt Validierungsfehler in deutsche Sätze und
behandelt 401 zentral.

**Ein nacktes `fetch("/api/…")` ist ein Fehler**, auch wenn es im Browser
funktioniert: In der nativen App läuft das Bundle unter `capacitor://localhost`,
der relative Pfad zeigt dort ins Nichts. Wo der Wrapper wirklich nicht passt
(Streams), nimm `apiUrl()` und `authHeaders()` aus demselben Modul.

Seit 09/2026 ist das keine Bitte mehr, sondern eine ESLint-Regel
(`no-restricted-syntax` in `.eslintrc.json`) und damit Teil von `npm run lint`
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

## Der statische Export bricht an anderen Dingen als der Server

- `generateMetadata` darf `searchParams` nur im Server-Build anfassen; jede
  Hülle beginnt deshalb mit der Kurzschlusszeile für den Export.
- `useSearchParams` zwingt die Seite in eine Suspense-Grenze, an der der
  Export abbricht. Wo es unvermeidlich ist, muss die Grenze wirklich da sein.
- Detailseiten arbeiten mit Query-Parametern statt dynamischer Pfadsegmente,
  damit der Bereich sich überhaupt exportieren lässt.
- `trailingSlash` ist an: Ein exakter Pfadvergleich (`pathname === "/council"`)
  ist in der App blind. Dafür gibt es genau eine Hilfsfunktion, benutze sie.
- `redirects` und `headers` aus `next.config.mjs` gibt es im Export **nicht**.
  Ein Redirect ersetzt also nie das Nachziehen der internen Links.

## Gemessene Fallen

- **Der Dev-Server baut in ein eigenes Verzeichnis.** Ein `next build` neben
  einem laufenden Dev-Server überschreibt dessen Chunks; die Seite liefert
  danach für jede Chunk-URL eine 404-Seite. Das sieht aus wie ein Fehler im
  Code und ist keiner. Die Konfiguration ist deshalb eine Funktion über die
  Phase — nicht zu einem Objekt zurückbauen.
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
keinen `next build`, keine Export-Variante. Die beiden Grafik-Proben rechnen
Skalen und Kachelgeometrie nach, weil beide Fehler typkorrekt waren. Ein Bild
vor dem Merge ersetzt keine dieser Prüfungen — und keine von ihnen ersetzt das
Bild.


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
npx playwright test                       # alles
npx playwright test tests/e2e/09-konto    # eine Datei
E2E_PORT=3010 E2E_API_PORT=8012 npx playwright test   # auf freien Ports
```

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
| `14-layout` | Keine Seite scrollt seitwärts (390 px und 320 px) |

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

**Ein bekannter Befund steht als `test.fail()` drin.** Die Startseite ist bei
320 px 14 px zu breit. Das ist Gestaltung, keine Mechanik — deshalb nicht
nebenbei repariert, sondern sichtbar festgehalten: Der Test meldet sich,
sobald jemand es behebt, und dann fliegt die Markierung raus. So verschwindet
ein Befund nicht in einer Liste, die niemand liest.
