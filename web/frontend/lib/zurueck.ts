"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "./auth";

/** „Zurück" auf den Detailseiten — und für wen der Knopf überhaupt Sinn ergibt.
 *
 *  Für Gäste (geteilter Link, kein Konto) gibt es kein sinnvolles „Zurück", und
 *  jede Variante geht daneben: `router.back()` führt bei einem frisch aus dem
 *  Messenger geöffneten Tab aus der Seite heraus (nachgemessen — die Seite war
 *  weg), und der Rückfall auf die Sitzungs-Übersicht landet an der
 *  Anmeldewand, die auf diesen Seiten gerade abgebaut wurde. Die Heuristik
 *  `window.history.length > 1` unterscheidet die Fälle nicht: Sie zählt auch
 *  Einträge, die gar nicht zu uns gehören.
 *
 *  Deshalb bekommen Gäste den Knopf nicht — der Zurück-Knopf des Browsers tut
 *  für sie ohnehin das Richtige und bringt sie dahin, wo der Link herkam.
 *
 *  Angemeldete behalten das Verhalten aus 28a/S2: History, sonst das
 *  übergebene Ziel. Der Rückfall kommt erst beim Klick, weil er meist von
 *  geladenen Daten abhängt (die Sitzung des Beschlusses) und Hooks nicht hinter
 *  den frühen `return`s der Ladezustände stehen dürfen.
 */
export function useZurueck(): { zeigen: boolean; zurueck: (fallback: string) => void } {
  const router = useRouter();
  const { user } = useAuth();
  return {
    zeigen: !!user,
    zurueck: (fallback: string) => {
      if (typeof window !== "undefined" && window.history.length > 1) {
        router.back();
        return;
      }
      router.push(fallback);
    },
  };
}
