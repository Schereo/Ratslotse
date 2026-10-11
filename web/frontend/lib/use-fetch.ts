import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
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
 */
export function useFetch<T>(
  path: string | null,
  { quiet = false }: { quiet?: boolean } = {},
): { data: T | null; loading: boolean; error: unknown; refetch: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(path !== null);
  const [error, setError] = useState<unknown>(null);
  const [runde, setRunde] = useState(0);
  const refetch = useCallback(() => setRunde((r) => r + 1), []);

  // Neuer Pfad = neuer Gegenstand. Ohne das Zurücksetzen blieb nach einem
  // gescheiterten Wechsel von Beschluss A auf B der Inhalt von A stehen —
  // unter der Adresse von B.
  const [letzterPfad, setLetzterPfad] = useState(path);
  if (letzterPfad !== path) {
    setLetzterPfad(path);
    setData(null);
    setError(null);
    setLoading(path !== null);
  }

  useEffect(() => {
    if (path === null) return;
    let active = true;
    setLoading(true);
    setError(null);
    api.get<T>(path)
      .then((d) => { if (active) setData(d); })
      .catch((e) => {
        if (!active) return;
        setError(e);
        if (!quiet && e instanceof ApiError && e.status !== 404) toast.error(e.message, { id: `abruf:${e.message}` });
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [path, quiet, runde]);

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
