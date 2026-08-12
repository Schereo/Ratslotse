"use client";

import { useEffect, useRef, useState } from "react";

/** `useState`, das einen Tab-Wechsel überlebt (Tims iOS-Befund 12.08.).
 *
 *  Suchtext, Ausschuss-Filter und Zeitraum sind Arbeit, die man einmal macht
 *  — und die beim kurzen Abstecher auf einen anderen Tab verloren ging, weil
 *  der App-Router die Seite abbaut. Der Wert liegt zusätzlich in der
 *  sessionStorage (nicht localStorage: beim nächsten App-Start soll wieder
 *  der frische Zustand stehen, nicht die Suche von vorgestern).
 *
 *  Gelesen wird erst NACH dem Mount, damit der statische Export keine
 *  Hydration-Abweichung bekommt — der erste Frame zeigt den Startwert.
 */
export function useMerker<T>(schluessel: string, start: T): [T, (wert: T) => void] {
  const [wert, setWert] = useState<T>(start);
  const geladen = useRef(false);

  useEffect(() => {
    if (geladen.current) return;
    geladen.current = true;
    try {
      const roh = sessionStorage.getItem(`ratslotse:merker:${schluessel}`);
      if (roh != null) setWert(JSON.parse(roh) as T);
    } catch { /* privater Modus oder kaputter Eintrag — Startwert bleibt */ }
  }, [schluessel]);

  const setzen = (neu: T) => {
    setWert(neu);
    try {
      const leer = neu === "" || neu === null || neu === undefined;
      if (leer) sessionStorage.removeItem(`ratslotse:merker:${schluessel}`);
      else sessionStorage.setItem(`ratslotse:merker:${schluessel}`, JSON.stringify(neu));
    } catch { /* s. o. */ }
  };

  return [wert, setzen];
}
