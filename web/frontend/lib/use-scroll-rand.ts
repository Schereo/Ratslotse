"use client";

import { useEffect, useState, type RefObject } from "react";

/** Welche Ränder einer waagerecht scrollbaren Zeile gerade Inhalt verdecken.
 *
 *  Chip-Reihen und Segment-Schalter scrollen auf dem Handy seit jeher
 *  (`overflow-x-auto`, ohne Rollbalken) — nur sah man es ihnen nicht an: Der
 *  letzte Chip war einfach abgeschnitten, und nichts sagte, dass dahinter
 *  noch etwas kommt (Durchsicht 02.09.2026, fünf Seiten). Die Designsprache
 *  (§ 6) verlangt an Scroll-Zeilen eine CSS-**Maske**, die den Inhalt am
 *  Ende ausblendet — und zwar nur dort, wo wirklich etwas verdeckt ist:
 *  Eine Zeile, die hineinpasst, bekommt keinen Schleier.
 *
 *  Gemessen wird am Element selbst (Scrollposition und Breite), neu nach
 *  jedem Scrollen und jeder Größenänderung. Das Ergebnis ist eine Klasse
 *  aus `globals.css` (`gb-maske-rechts`, `-links`, `-beide`) oder nichts. */
export function useScrollRand(ref: RefObject<HTMLElement | null>): string | undefined {
  const [rand, setRand] = useState<{ links: boolean; rechts: boolean }>({ links: false, rechts: false });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let laeuft = 0;
    const messen = () => {
      laeuft = 0;
      const links = el.scrollLeft > 2;
      const rechts = el.scrollLeft + el.clientWidth < el.scrollWidth - 2;
      setRand((alt) => (alt.links === links && alt.rechts === rechts ? alt : { links, rechts }));
    };
    const anstossen = () => {
      if (!laeuft) laeuft = window.requestAnimationFrame(messen);
    };
    messen();
    el.addEventListener("scroll", anstossen, { passive: true });
    const beobachter = typeof ResizeObserver !== "undefined" ? new ResizeObserver(anstossen) : null;
    beobachter?.observe(el);
    // Kinder, die später laden (Chips aus einer Antwort), ändern die
    // Scrollbreite, ohne dass sich das Element selbst vergrößert.
    const kinder = typeof MutationObserver !== "undefined" ? new MutationObserver(anstossen) : null;
    kinder?.observe(el, { childList: true, subtree: true });
    return () => {
      el.removeEventListener("scroll", anstossen);
      beobachter?.disconnect();
      kinder?.disconnect();
      if (laeuft) window.cancelAnimationFrame(laeuft);
    };
  }, [ref]);

  if (rand.links && rand.rechts) return "gb-maske-beide";
  if (rand.rechts) return "gb-maske-rechts";
  if (rand.links) return "gb-maske-links";
  return undefined;
}
