"use client";

import { useEffect, useState } from "react";

/** Das heutige Datum — aber erst NACH dem Mount.
 *
 *  Zwei Gründe für den Umweg: Der statische Export (App) rendert die Seiten
 *  zur Build-Zeit; ein dort berechnetes „morgen“ wäre eine Woche später
 *  schlicht falsch und gäbe beim Hydrieren eine Abweichung. Und eine App, die
 *  über Mitternacht offen bleibt (auf dem Handy die Regel, nicht die
 *  Ausnahme), zeigte sonst weiter „heute“ für gestern — deshalb der Blick auf
 *  die Uhr, wenn die App wieder in den Vordergrund kommt, plus ein stündlicher
 *  Takt als Rückfall.
 *
 *  Vor dem Mount kommt `null` zurück: Aufrufer zeigen dann das absolute Datum.
 */
export function useHeute(): Date | null {
  const [heute, setHeute] = useState<Date | null>(null);
  useEffect(() => {
    const pruefen = () => setHeute((alt) => {
      const jetzt = new Date();
      return alt && alt.toDateString() === jetzt.toDateString() ? alt : jetzt;
    });
    pruefen();
    const id = setInterval(pruefen, 3600_000);
    document.addEventListener("visibilitychange", pruefen);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", pruefen);
    };
  }, []);
  return heute;
}
