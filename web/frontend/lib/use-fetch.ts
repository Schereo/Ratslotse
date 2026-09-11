import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { toast } from "@/components/ui";

/** GET `path` on mount (and whenever it changes). Returns `{ data, loading }`.
 *  Toasts on non-404 errors; a 404 just leaves `data` null. Pass `null` to skip.
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
): { data: T | null; loading: boolean } {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(path !== null);

  useEffect(() => {
    if (path === null) return;
    let active = true;
    setLoading(true);
    api.get<T>(path)
      .then((d) => { if (active) setData(d); })
      .catch((e) => {
        if (active && !quiet && e instanceof ApiError && e.status !== 404) toast.error(e.message);
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [path, quiet]);

  return { data, loading };
}
