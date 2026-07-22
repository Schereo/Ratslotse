"use client";

import { useEffect, useState } from "react";

/** Zahl zählt beim Einblenden hoch (RL-1104, extrahiert aus LiveStats).
 *  Ease-out-cubic über requestAnimationFrame; bei reduzierter Bewegung
 *  (prefers-reduced-motion) steht sofort der Endwert. */
export function useCountUp(target: number, run: boolean, ms = 1300): number {
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!run || target <= 0) { setN(target); return; }
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setN(target); return; }
    let raf = 0;
    let startT = 0;
    const tick = (t: number) => {
      if (!startT) startT = t;
      const p = Math.min(1, (t - startT) / ms);
      setN(Math.round((1 - Math.pow(1 - p, 3)) * target)); // ease-out cubic
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, run, ms]);
  return n;
}
