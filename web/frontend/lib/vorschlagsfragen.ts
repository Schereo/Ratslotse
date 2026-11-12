/* Vorschlagsfragen unter „Frag den Rat" (Schalter `vorschlagsfragen`,
   `council/vorschlagsfragen.py`): Die erste Frage bleibt fest, die übrigen
   kommen vom Modell — passend zu genau dieser Seite. Solange sie fehlen
   (Schalter aus, erster Aufruf läuft noch, Modell lieferte nichts), stehen die
   festen Fragen der Seite da. */

import { useFeature } from "@/lib/features";
import { useFetch } from "@/lib/use-fetch";
import type { ApiAntwort } from "@/lib/vertrag";

export const ERSTE_FRAGE = "Worum geht es dabei in einfachen Worten?";

/** Feste erste Frage, dann die des Modells — sonst die festen Rückfälle. */
export function mischeVorschlaege(modell: string[] | null | undefined, rueckfall: string[], max = 4): string[] {
  const rest = modell && modell.length ? modell : rueckfall.filter((q) => q !== ERSTE_FRAGE);
  return [ERSTE_FRAGE, ...rest.filter((q) => q !== ERSTE_FRAGE)].slice(0, max);
}

export function useVorschlagsfragen(pfad: string | null, rueckfall: string[], max = 4): string[] {
  const an = useFeature("vorschlagsfragen");
  const { data } = useFetch<ApiAntwort<"/council/page-questions">>(an ? pfad : null, { quiet: true });
  return mischeVorschlaege(data?.questions, rueckfall, max);
}
