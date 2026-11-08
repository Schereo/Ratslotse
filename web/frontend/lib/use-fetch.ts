import { useCallback, useContext, useEffect, useState } from "react";
import { QueryClientContext } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { cachedShared, fetchShared, preloadShared } from "@/lib/shared-fetch";
import { toast } from "@/components/ui";

/** GET `path` on mount (and whenever it changes). Returns `{ data, loading,
 *  error, refetch }`. Toasts on non-404 errors; a 404 just leaves `data` null.
 *  Pass `null` to skip.
 *
 *  `error` gibt es seit 10/2026: Vorher kannte der Hook nur „Daten oder
 *  keine", und die Detailseiten machten aus einem 500er oder einem Funkloch
 *  ein „Diesen Beschluss finde ich nicht". Ob etwas fehlt oder nur nicht
 *  ankam, sagt `istNichtGefunden(error)`; für den zweiten Fall gibt es
 *  `<AbrufFehler>`.
 *
 *  `quiet` schaltet den Toast ab — für Abrufe, deren Ausbleiben die Seite
 *  bewusst verkraftet.
 *
 *  **Warum das nötig wurde.** Die Beschluss-Seite holt ihre Sitzung nur
 *  nebenbei (Nachbar-TOPs, Ziel für „Zurück"); fehlt sie, verhält sie sich wie
 *  vorher. Am 11.09.2026 antwortete `/council/session/4695` mit einem 500er,
 *  und der Nutzer sah auf einer vollständig gerenderten Seite den roten
 *  Hinweis „Da ist etwas schiefgegangen. Wir wissen davon." — eine Meldung
 *  über etwas, das er weder bemerkt hatte noch beheben konnte.
 *
 *  Still heißt NICHT unbemerkt: Der Server hält den 500er weiter in
 *  `request_errors` fest und meldet ihn beim ersten Mal per Mail. Unterdrückt
 *  wird nur die Beunruhigung dessen, der nichts davon hat.
 *
 *  `shared` (seit 11/2026) teilt den Abruf über `lib/shared-fetch.ts`: Zwei
 *  Komponenten mit derselben Adresse fragen einmal, eine Antwort gilt zehn
 *  Minuten, und was `usePreload` schon angestoßen hat, wird abgeholt statt
 *  neu gefragt. **Nur für Antworten, die für alle Berechtigten gleich sind** —
 *  nie für Persönliches (Begründung dort).
 */
export function useFetch<T>(
  path: string | null,
  { quiet = false, shared = false }: { quiet?: boolean; shared?: boolean } = {},
): { data: T | null; loading: boolean; error: unknown; refetch: () => void } {
  // Ohne QueryClientProvider (sollte es nicht geben) fällt `shared` still auf
  // den einzelnen Abruf zurück, statt die Seite zu sprengen.
  const client = useContext(QueryClientContext);
  const pool = shared ? client ?? null : null;
  const fromPool = (p: string | null): T | null =>
    pool && p !== null ? cachedShared<T>(pool, p) : null;

  const [data, setData] = useState<T | null>(() => fromPool(path));
  const [loading, setLoading] = useState(() => path !== null && fromPool(path) === null);
  const [error, setError] = useState<unknown>(null);
  const [runde, setRunde] = useState(0);
  const refetch = useCallback(() => setRunde((r) => r + 1), []);

  // Neuer Pfad = neuer Gegenstand. Ohne das Zurücksetzen blieb nach einem
  // gescheiterten Wechsel von Beschluss A auf B der Inhalt von A stehen —
  // unter der Adresse von B.
  const [letzterPfad, setLetzterPfad] = useState(path);
  if (letzterPfad !== path) {
    const cached = fromPool(path);
    setLetzterPfad(path);
    setData(cached);
    setError(null);
    setLoading(path !== null && cached === null);
  }

  useEffect(() => {
    if (path === null) return;
    let active = true;
    // Geteilt und noch gültig: kein Abruf, kein Ladezustand. Nur beim
    // ersten Durchlauf — ein `refetch` will ausdrücklich frische Daten.
    const cached = pool && runde === 0 ? cachedShared<T>(pool, path) : null;
    if (cached !== null) {
      setData(cached);
      setError(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    (pool ? fetchShared<T>(pool, path, { fresh: runde > 0 }) : api.get<T>(path))
      .then((d) => { if (active) setData(d); })
      .catch((e) => {
        if (!active) return;
        setError(e);
        if (!quiet && e instanceof ApiError && e.status !== 404) toast.error(e.message, { id: `abruf:${e.message}` });
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [path, quiet, runde, pool]);

  // Wieder online: einmal nachladen, was gescheitert war — sonst blieb die
  // Seite nach dem Funkloch leer, obwohl das Netz längst zurück ist.
  useEffect(() => {
    if (!error) return;
    const an = () => refetch();
    window.addEventListener("online", an);
    return () => window.removeEventListener("online", an);
  }, [error, refetch]);

  return { data, loading, error, refetch };
}

/** Stößt die geteilten Abrufe von `paths` an, sobald die Komponente steht —
 *  für Abschnitte, die erst nach den Hauptdaten montieren, deren Daten aber
 *  nicht von ihnen abhängen. Die Seite fragt so alles in EINER Welle; der
 *  Abschnitt holt sich später mit `useFetch(path, { shared: true })` die
 *  laufende oder fertige Antwort. `null`/`false` werden übersprungen.
 *
 *  Die Adressen müssen Zeichen für Zeichen die sein, die der Abschnitt
 *  fragt — deshalb exportieren die Abschnitte sie (`DATA_STATUS_URL` …),
 *  statt dass die Seite sie nachschreibt. */
export function usePreload(paths: readonly (string | null | false | undefined)[]): void {
  const client = useContext(QueryClientContext);
  const key = paths.filter((p): p is string => !!p).join("\n");
  useEffect(() => {
    if (!client || !key) return;
    for (const p of key.split("\n")) preloadShared(client, p);
  }, [client, key]);
}
