"use client";

// Zahlen gleiten statt zu springen — Bewegungs-Grammatik der Designsprache:
// Übergänge statt Sprünge, höchstens 300 ms. Der ERSTE Wert steht sofort (der
// erste Auftritt bewegt sich nicht), `null` bleibt `null`, und wer weniger
// Bewegung will, bekommt den Endwert ohne Umweg. Eine Zahl zwischen zwei
// Zahlen braucht keine Bibliothek (d3-interpolate trägt keine Typen).

import { useEffect, useRef, useState } from "react";

export function useTween(ziel: number | null | undefined, ms = 300): number | null {
  const [wert, setWert] = useState<number | null>(ziel ?? null);
  const vorher = useRef<number | null>(ziel ?? null);
  useEffect(() => {
    const z = ziel ?? null;
    const v = vorher.current;
    vorher.current = z;
    if (z === null || v === null || v === z || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setWert(z);
      return;
    }
    const f = (e: number) => v + (z - v) * e;
    const t0 = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / ms);
      const e = 1 - Math.pow(1 - p, 3);
      setWert(p >= 1 ? z : f(e));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [ziel, ms]);
  return wert;
}

/** Wahr für `ms` Millisekunden, nachdem der Wert GESTIEGEN ist — nicht beim
 *  ersten Rendern. Für das kurze Aufleuchten eines frisch gemeldeten
 *  Wahlbereichs. */
export function useFrisch(wert: number | null | undefined, ms = 1600): boolean {
  const [frisch, setFrisch] = useState(false);
  const vorher = useRef<number | null | undefined>(wert);
  useEffect(() => {
    const v = vorher.current;
    vorher.current = wert;
    if (wert == null || v == null || wert <= v) return;
    setFrisch(true);
    const id = window.setTimeout(() => setFrisch(false), ms);
    return () => window.clearTimeout(id);
  }, [wert, ms]);
  return frisch;
}
