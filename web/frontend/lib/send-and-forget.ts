/**
 * Eine Anfrage abschicken, deren Antwort niemand braucht — und sie trotzdem
 * zu Ende lesen.
 *
 * **Warum nicht einfach `void fetch(…)`.** So stand es bis 10/2026 an fünf
 * Stellen (Seitenzähler, Fehler-Melder, Lotti-Ereignisse, Daumen, „Bericht
 * gesehen"). Der Server antwortet darauf mit 200 und einem kleinen Körper —
 * aber wenn die Seite den Körper nie liest, schließt Chromium die Anfrage in
 * gut jedem zehnten Fall nicht ab: Kopf und Daten kommen an
 * (`Network.responseReceived`, `Network.dataReceived`), das
 * `Network.loadingFinished` bleibt aus, auch nach 15 Sekunden.
 *
 * Für die Seite ist das folgenlos. Für jede Prüfung, die auf ein ruhiges Netz
 * wartet, nicht: Playwrights `networkidle` zählt die Anfrage als offen und
 * wartet bis zum Test-Timeout. Genau daran scheiterte `14-layout.spec.ts` in
 * der CI wechselnd auf /council, /account, /haushalt, /bookmarks … — in PRs,
 * die gar kein Frontend anfassten. Gemessen am 17.10.2026 über je 72
 * Seitenaufrufe: 8–9 Hänger, jedes Mal genau der `POST /api/page-views`;
 * mit gelesenem Körper 0. Auch `keepalive` war es nicht — ohne blieb es bei 9.
 *
 * Gelesen wird mit `arrayBuffer()` statt `body.cancel()`: Ein Abbruch endete
 * als „fehlgeschlagene Anfrage" in den Entwicklerwerkzeugen, und die Antworten
 * sind ohnehin nur ein paar Byte groß.
 *
 * **Wirft nie**, auch nicht asynchron: Ein Zähler oder Melder, der selbst
 * einen Fehler auslöst, wäre schlimmer als keiner.
 */
export function sendAndForget(url: string, init: RequestInit): void {
  try {
    void fetch(url, init)
      .then((res) => res.arrayBuffer())
      .catch(() => {
        /* Eine gescheiterte Meldung ist kein Ereignis. */
      });
  } catch {
    /* dito — etwa ein `fetch`, das es in dieser Umgebung nicht gibt */
  }
}
