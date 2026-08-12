"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { isNativeApp } from "@/lib/platform";
import { useAuth } from "@/lib/auth";

/** Der Parameter, der die Landing trotz Anmeldung stehen lässt. */
export const LANDING_HREF = "/?start=1";
const MERKER = "ratslotse:landing-gewollt";

/** Wer die Startseite gar nicht braucht, soll sie nicht sehen.
 *
 *  - In der nativen App ist die Marketing-Seite totes Gewicht (deep links
 *    gewinnen weiterhin: Capacitor navigiert nach diesem replace).
 *  - Im Browser springen ANGEMELDETE aufs Dashboard — wer eingeloggt
 *    „ratslotse.de" tippt, will fast immer seine Themen, nicht den Pitch.
 *
 *  Die Fluchttür: `/?start=1` zeigt die Startseite trotzdem und merkt sich
 *  das für die Sitzung (sonst würde jeder Klick aufs Logo wieder wegspringen).
 *  Der Link steht im Sidebar-/Menü-Fuß neben Impressum; Abmelden landet
 *  ohnehin hier, weil die Weiterleitung nur Angemeldete betrifft.
 *
 *  `replace` statt `push`: Sonst führte „Zurück" vom Dashboard sofort wieder
 *  in die Weiterleitung.
 */
export function NativeRedirect() {
  const router = useRouter();
  const sp = useSearchParams();
  const { user, loading } = useAuth();
  const gewollt = sp.get("start") != null;

  useEffect(() => {
    if (gewollt) {
      try { sessionStorage.setItem(MERKER, "1"); } catch { /* privater Modus */ }
      return;
    }
    if (isNativeApp()) {
      router.replace("/dashboard");
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
