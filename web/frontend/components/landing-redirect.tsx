"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { LANDING_PARAM, LANDING_WANTED_KEY } from "@/lib/landing-wanted";

/** Die Adresse, die die Landing trotz Anmeldung stehen lässt. */
export const LANDING_HREF = `/?${LANDING_PARAM}=1`;
const MERKER = LANDING_WANTED_KEY;

/** Wer die Startseite gar nicht braucht, soll sie nicht sehen: ANGEMELDETE
 *  springen aufs Dashboard — wer eingeloggt „ratslotse.de" tippt, will fast
 *  immer seine Themen, nicht den Pitch.
 *
 *  Die Fluchttür: `/?start=1` zeigt die Startseite trotzdem und merkt sich
 *  das für die Sitzung (sonst würde jeder Klick aufs Logo wieder wegspringen).
 *  Der Link steht im Sidebar-/Menü-Fuß neben Impressum; Abmelden landet
 *  ohnehin hier, weil die Weiterleitung nur Angemeldete betrifft.
 *
 *  `replace` statt `push`: Sonst führte „Zurück" vom Dashboard sofort wieder
 *  in die Weiterleitung.
 *
 *  Seit 11/2026 leitet bei einem ganzen Seitenaufruf schon der Server um
 *  (`proxy.ts`, `lib/landing-redirect.ts`), bevor die Landing samt
 *  3D-Lotti lädt. Diese Komponente bleibt der Rückfall für alles, was dort
 *  durchgeht: Client-Navigation, ein langsames Backend. Die Fluchttür merkt
 *  sich der Server zusätzlich als Cookie — `sessionStorage` sieht er nicht.
 *
 *  Den Merker setzt bei einem ganzen Seitenaufruf schon ein Skript im <head>
 *  (`lib/landing-wanted.ts`), nicht erst der Effekt hier: Der läuft nach dem
 *  Hydrieren, und wer vorher weiterging, sprang doch aufs Dashboard.
 */
export function LandingRedirect() {
  const router = useRouter();
  const sp = useSearchParams();
  const { user, loading } = useAuth();
  const gewollt = sp.get(LANDING_PARAM) != null;

  useEffect(() => {
    if (gewollt) {
      try { sessionStorage.setItem(MERKER, "1"); } catch { /* privater Modus */ }
      return;
    }
    if (loading || !user) return;
    try {
      if (sessionStorage.getItem(MERKER) === "1") return;
    } catch { /* siehe oben */ }
    router.replace("/dashboard");
  }, [router, user, loading, gewollt]);

  return null;
}
