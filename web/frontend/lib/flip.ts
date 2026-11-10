"use client";

import { useCallback, useLayoutEffect, useRef } from "react";

type Box = { left: number; top: number };

const NAME = "flip";

function reduced(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function cssTime(name: string, fallback: number): number {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const value = Number.parseFloat(raw);
  return Number.isFinite(value) ? value : fallback;
}

function cssCurve(name: string, fallback: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}

/** Elemente gleiten an ihren neuen Platz, statt dort zu erscheinen (FLIP).
 *
 *  Wer sortiert oder filtert, sieht sonst zwei Zustände und keinen Weg: Die
 *  Liste steht anders da, und man sucht die Zeile, die man eben noch im Blick
 *  hatte. Hier fährt jede Zeile von ihrem alten Platz zum neuen — das Auge
 *  nimmt sie mit (DESIGNSPRACHE § 7: Bewegung erklärt einen Zusammenhang).
 *
 *  Benutzung: `capture()` VOR der Zustandsänderung rufen, dann rendern lassen.
 *  Jedes Element, das wandern soll, trägt `data-flip="<stabiler Schlüssel>"`
 *  unterhalb von `root`. Bewegt wird nur `transform` (und `opacity` bei dem,
 *  was neu dazukommt).
 *
 *  Vier Dinge, die sonst schiefgehen:
 *  • Gemessen wird gegen die Wurzel, nicht gegen das Fenster: Ändert sich die
 *    Länge der Seite, rückt der Browser den Rollstand nach — die Zeilen sollen
 *    dann nicht um diese Strecke mitfahren.
 *  • Ohne `capture()` bewegt sich nichts. Der erste Auftritt hat keinen
 *    Vorgänger und damit keinen Weg.
 *  • Was vorher wie nachher außerhalb des Fensters liegt, bleibt stehen —
 *    vierzig unsichtbare Animationen kosten nur Akku.
 *  • Ein Weg länger als das Fenster wird gekappt: Die Zeile kommt vom Rand
 *    herein, statt in 260 ms über drei Bildschirme zu rasen.
 *  Bei `prefers-reduced-motion` steht sofort der Endstand. */
export function useFlip<T extends HTMLElement>(dep: unknown, takt: "weg" | "buehne" = "weg") {
  const root = useRef<T | null>(null);
  const before = useRef<Map<string, Box> | null>(null);

  const capture = useCallback(() => {
    const el = root.current;
    if (!el || reduced()) {
      before.current = null;
      return;
    }
    const base = el.getBoundingClientRect();
    const map = new Map<string, Box>();
    el.querySelectorAll<HTMLElement>("[data-flip]").forEach((node) => {
      const r = node.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) return;
      map.set(node.dataset.flip ?? "", { left: r.left - base.left, top: r.top - base.top });
    });
    before.current = map;
  }, []);

  useLayoutEffect(() => {
    const el = root.current;
    const old = before.current;
    before.current = null;
    if (!el || !old) return;
    const nodes = Array.from(el.querySelectorAll<HTMLElement>("[data-flip]"));
    // Erst alles Laufende beenden, dann messen — sonst misst man mitten im Weg.
    for (const node of nodes) {
      for (const a of node.getAnimations()) if (a.id === NAME) a.cancel();
    }
    const base = el.getBoundingClientRect();
    const height = window.innerHeight;
    const duration = cssTime(takt === "buehne" ? "--takt-buehne" : "--takt-weg", takt === "buehne" ? 340 : 260);
    const easing = cssCurve("--ease-in-out-strong", "cubic-bezier(0.77, 0, 0.175, 1)");
    const visible = (top: number, bottom: number) => bottom > -80 && top < height + 80;
    for (const node of nodes) {
      const r = node.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) continue;
      const was = old.get(node.dataset.flip ?? "");
      const now = visible(r.top, r.bottom);
      if (!was) {
        if (now) node.animate([{ opacity: 0 }, { opacity: 1 }], { duration, easing: "ease-out", id: NAME });
        continue;
      }
      const dx = was.left - (r.left - base.left);
      const dy = was.top - (r.top - base.top);
      if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) continue;
      const wasTop = was.top + base.top;
      if (!now && !visible(wasTop, wasTop + r.height)) continue;
      const far = Math.max(-height, Math.min(height, dy));
      node.animate([{ transform: `translate(${dx}px, ${far}px)` }, { transform: "translate(0, 0)" }],
        { duration, easing, id: NAME });
    }
  }, [dep, takt]);

  return { root, capture };
}
