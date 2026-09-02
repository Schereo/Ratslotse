# Regeln für `web/frontend/`

Next.js. Derselbe Code wird zusätzlich als statischer Export in die
Capacitor-Hülle gebaut — die meisten Fallen hier kommen daher.

**Pflichtlektüre vor UI-Arbeit:** [`DESIGNSPRACHE.md`](DESIGNSPRACHE.md).
Grafiken zusätzlich: [`components/grafik/README.md`](components/grafik/README.md).
Allgemeines: [`../../CLAUDE.md`](../../CLAUDE.md).

## Ans Backend nur über `lib/api.ts`

`api.get/post/put/del` setzt die Basis-URL, die Anmeldeform (Cookie im Web,
Bearer in der App), übersetzt Validierungsfehler in deutsche Sätze und
behandelt 401 zentral.

**Ein nacktes `fetch("/api/…")` ist ein Fehler**, auch wenn es im Browser
funktioniert: In der nativen App läuft das Bundle unter `capacitor://localhost`,
der relative Pfad zeigt dort ins Nichts. Wo der Wrapper wirklich nicht passt
(Streams), nimm `apiUrl()` und `authHeaders()` aus demselben Modul.

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
- **Ein Umgebungs-Gate braucht auch seine Einstiegspunkte.** Seite gesperrt,
  Navigation und Metadaten aber nicht — dann stehen die Links auf Prod weiter
  da und führen ins Leere.

## Was die Prüfungen NICHT sehen

`tsc --noEmit` fängt Typfehler, sonst nichts: keine CSS-Klasse, kein Layout,
keinen `next build`, keine Export-Variante. Die beiden Grafik-Proben rechnen
Skalen und Kachelgeometrie nach, weil beide Fehler typkorrekt waren. Ein Bild
vor dem Merge ersetzt keine dieser Prüfungen — und keine von ihnen ersetzt das
Bild.
