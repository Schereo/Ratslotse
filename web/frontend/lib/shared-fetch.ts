// Geteilte GET-Abrufe für `useFetch(path, { shared: true })` und `usePreload`.
//
// WOZU. `useFetch` holt jede Adresse beim Montieren — ohne Zwischenspeicher
// und ohne zu merken, dass eine zweite Komponente gerade dieselbe Adresse
// fragt. Im Haushalt-Bereich hieß das (Messung 08.11.2026):
//
//  * **Doppelte Abrufe.** `data-status` zweimal auf /haushalt (Datenstand und
//    Flussbild), `investments` zweimal auf /investitionen, `debt` zweimal auf
//    /schulden, `documents` zweimal auf /mitreden.
//  * **Eine zweite Anfragewelle.** Die Abschnitte unter den Hauptdaten
//    montieren erst, wenn die Hauptdaten da sind, und fragen dann. Ihre Daten
//    hängen aber gar nicht an den Hauptdaten — die Seite kann sie gleich zu
//    Beginn mit anfordern (`usePreload`), und der Abschnitt bekommt beim
//    Montieren die laufende oder fertige Antwort.
//  * **Jede Schritt-Seite holte das Belegverzeichnis neu** (383 KB entpackt),
//    beim Durchklicken der zwölf Schritte zwölfmal.
//
// WARUM ÜBER DEN QUERYCLIENT und nicht über eine eigene Modul-Map: Er
// fasst gleichzeitige Abrufe derselben Adresse schon zusammen, und — der
// wichtigere Teil — die Abmeldung leert ihn (`lib/auth.tsx`: `queryClient
// .clear()` bei `logout` und bei jedem 401). Was ein Konto geladen hat, liegt
// damit nie für das nächste im Tab. Das ist auch die Grenze der Verwendung:
// **Nur für Antworten, die für alle Berechtigten gleich sind** (die
// Haushaltsbestände). Persönliches — Konto, Lesezeichen, Gesehen-Marken —
// gehört nicht hier hinein, auch nicht zehn Minuten lang.
//
// Fehler werden nicht aufbewahrt: Eine gescheiterte Abfrage hat keine Daten,
// und der nächste Abruf fragt wieder (`fetchQuery` holt neu, solange es keine
// gültigen Daten gibt). Wiederholt wird bewusst nicht (`retry: false`) —
// `useFetch` hat nie wiederholt, und die Seiten zeigen ihren Fehler selbst.

import type { QueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

/** So lange gilt eine geteilte Antwort. Die Haushaltsbestände ändern sich nur
 *  mit dem nächtlichen Ingest; zehn Minuten sind dagegen kurz, und wer neu
 *  lädt, bekommt ohnehin frische Daten. */
export const SHARED_TTL_MS = 10 * 60_000;

function options<T>(path: string, staleTime: number) {
  return {
    queryKey: ["shared-fetch", path] as const,
    queryFn: () => api.get<T>(path),
    staleTime,
    gcTime: SHARED_TTL_MS,
    retry: false as const,
  };
}

/** Die gültige geteilte Antwort zu `path` — oder `null`, wenn es keine gibt
 *  oder sie älter als `SHARED_TTL_MS` ist. Synchron, damit eine Komponente,
 *  deren Daten schon da sind, gar nicht erst „wird geladen" zeigt. */
export function cachedShared<T>(client: QueryClient, path: string): T | null {
  const state = client.getQueryState<T>(["shared-fetch", path]);
  if (!state || state.data === undefined) return null;
  return Date.now() - state.dataUpdatedAt < SHARED_TTL_MS ? state.data : null;
}

/** Holt `path` einmal für alle: Läuft schon ein Abruf, kommt dessen Antwort;
 *  liegt eine gültige vor, kommt sie ohne Netz. `fresh` erzwingt einen neuen
 *  Abruf (das `refetch` von `useFetch`). */
export function fetchShared<T>(client: QueryClient, path: string,
  { fresh = false }: { fresh?: boolean } = {}): Promise<T> {
  return client.fetchQuery(options<T>(path, fresh ? 0 : SHARED_TTL_MS));
}

/** Stößt den Abruf an, ohne auf ihn zu warten. Ein Fehler bleibt hier still —
 *  die Komponente, die die Daten braucht, fragt dann selbst und meldet ihn. */
export function preloadShared(client: QueryClient, path: string): void {
  void client.prefetchQuery(options(path, SHARED_TTL_MS));
}
