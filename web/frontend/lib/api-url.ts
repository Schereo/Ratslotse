/** Die eine Stelle für die Adresse des Backends — ohne Abhängigkeiten, damit
 *  auch das Vorab-Skript im <head> (lib/early-auth.ts, Server-Komponente) sie
 *  benutzen kann. `lib/api.ts` reicht sie unverändert weiter. */
export function apiUrl(path: string): string {
  return `/api${path}`;
}
