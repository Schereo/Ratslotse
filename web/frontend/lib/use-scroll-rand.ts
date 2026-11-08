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

/** Dasselbe senkrecht, für ein Blatt, das in sich scrollt (der Assistent):
 *  `verdeckt` heißt, unter dem sichtbaren Teil liegt noch Inhalt — mehr als
 *  die `luft` am Ende; `oben` heißt, es ist noch nicht gescrollt worden.
 *
 *  Anlass (Tim, 08.11.2026): Endete die letzte sichtbare Gremien-Kachel
 *  zufällig genau über der Fußleiste, sah die Liste fertig aus. Die halb
 *  abgeschnittene nächste Kachel, die sonst verrät, dass es weitergeht, gab
 *  es auf genau diesen Schirmhöhen nicht. Die Luft ist der Innenabstand am
 *  Ende des Inhalts: Liegt nur noch er verdeckt, fehlt niemandem etwas. */
export function useScrollRestUnten(
  ref: RefObject<HTMLElement | null>,
  luft = 40,
): { verdeckt: boolean; oben: boolean } {
  const [stand, setStand] = useState({ verdeckt: false, oben: true });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let laeuft = 0;
    const messen = () => {
      laeuft = 0;
      const verdeckt = el.scrollHeight - el.scrollTop - el.clientHeight > luft;
      const oben = el.scrollTop <= 8;
      setStand((alt) => (alt.verdeckt === verdeckt && alt.oben === oben ? alt : { verdeckt, oben }));
    };
    const anstossen = () => {
      if (!laeuft) laeuft = window.requestAnimationFrame(messen);
    };
    messen();
    el.addEventListener("scroll", anstossen, { passive: true });
    // Das Blatt behält seine Höhe, wenn der Inhalt wächst (Gremien geladen,
    // Bilder da) — gemessen wird deshalb auch das erste Kind.
    const beobachter = typeof ResizeObserver !== "undefined" ? new ResizeObserver(anstossen) : null;
    beobachter?.observe(el);
    if (el.firstElementChild) beobachter?.observe(el.firstElementChild);
    const kinder = typeof MutationObserver !== "undefined" ? new MutationObserver(anstossen) : null;
    kinder?.observe(el, { childList: true, subtree: true });
    return () => {
      el.removeEventListener("scroll", anstossen);
      beobachter?.disconnect();
      kinder?.disconnect();
      if (laeuft) window.cancelAnimationFrame(laeuft);
    };
  }, [ref, luft]);

  return stand;
}
