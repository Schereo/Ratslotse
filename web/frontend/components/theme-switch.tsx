"use client";

import { useEffect, useState } from "react";
import { applyTheme, isDarkNow, THEME_EVENT } from "@/lib/theme";
import { cn } from "@/lib/utils";

/**
 * RL-U09 (Design 9a): „Tag & Nacht im Hafen" — binärer Himmel-Schalter, 56×28.
 * Track = Hafenhimmel (Tag: Sonne rechts · Nacht: Mond + Sterne links),
 * Daumen = Lotti-Kopf mit Kapitänsmütze — Augen offen/zu, nachts ein „z".
 * Ein Klick speichert explizit hell/dunkel; bestehende System-Nutzer werden
 * damit beim ersten Klick migriert, der Erststart ohne gespeicherten Wert
 * folgt weiter prefers-color-scheme (initTheme). Slide + Crossfade 300 ms,
 * nur transform/opacity — springt bei reduzierter Bewegung.
 */
export function LottiThemeSwitch({ className }: { className?: string }) {
  // Ist-Zustand erst nach dem Mount lesen (SSR-Hydration) und mit anderen
  // Theme-Reglern (Konto-Karte, ⌘K-Palette) synchron bleiben.
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const sync = () => setDark(isDarkNow());
    sync();
    window.addEventListener(THEME_EVENT, sync);
    return () => window.removeEventListener(THEME_EVENT, sync);
  }, []);
  const fade = "transition-opacity duration-300 ease-out-strong motion-reduce:transition-none";
  return (
    <button
      type="button"
      role="switch"
      aria-checked={dark}
      aria-label="Dunkles Design"
      onClick={() => {
        const next = !dark;
        setDark(next);
        applyTheme(next ? "dark" : "light");
      }}
      className={cn(
        "relative h-7 w-14 shrink-0 overflow-hidden rounded-full shadow-[inset_0_1px_3px_rgba(2,32,71,0.18)]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        className,
      )}
    >
      {/* Himmel: Tag liegt unten, die Nacht crossfadet darüber. */}
      <span aria-hidden className="absolute inset-0 bg-[linear-gradient(105deg,#bfe3f7,#e8f5fd)]" />
      <span aria-hidden className={cn("absolute inset-0 bg-[linear-gradient(105deg,#0E2B46,#17385c)]", fade, dark ? "opacity-100" : "opacity-0")} />
      {/* Sonne (Tag, rechts) */}
      <svg width="11" height="11" viewBox="0 0 14 14" aria-hidden className={cn("absolute right-2 top-[8.5px]", fade, dark && "opacity-0")}>
        <circle cx="7" cy="7" r="4.2" fill="#F2B441" />
        <g stroke="#F2B441" strokeWidth="1.4" strokeLinecap="round">
          <path d="M7 0.8v1.6" /><path d="M7 11.6v1.6" /><path d="M0.8 7h1.6" /><path d="M11.6 7h1.6" />
        </g>
      </svg>
      {/* Mond + zwei Sterne (Nacht, links) */}
      <svg width="10" height="10" viewBox="0 0 12 12" aria-hidden className={cn("absolute left-2 top-[9px]", fade, !dark && "opacity-0")}>
        <path d="M9.8 7.6A4.6 4.6 0 0 1 4.4 2.2a4.6 4.6 0 1 0 5.4 5.4z" fill="#F2B441" />
      </svg>
      <span aria-hidden className={cn("absolute left-[21px] top-[6px] h-[2px] w-[2px] rounded-full bg-[#BFE3F7]", fade, !dark && "opacity-0")} />
      <span aria-hidden className={cn("absolute left-[27px] top-[14px] h-[1.5px] w-[1.5px] rounded-full bg-[#BFE3F7]", fade, !dark && "opacity-0")} />
      {/* Daumen: Lotti-Kopf — ein SVG mit beiden Augen-Gruppen (Opacity-Wechsel). */}
      <span
        className={cn(
          "absolute left-[2px] top-[2px] h-6 w-6 rounded-full bg-white shadow-[0_2px_5px_rgba(2,32,71,0.3)]",
          "transition-transform duration-300 ease-out-strong motion-reduce:transition-none",
          dark && "translate-x-[28px]",
        )}
      >
        <svg viewBox="0 0 30 30" aria-hidden className="absolute inset-0 h-full w-full">
          <path d="M7,11 C7,5.5 10.5,3 15,3 C19.5,3 23,5.5 23,11 C20.5,9.8 17.8,9.2 15,9.2 C12.2,9.2 9.5,9.8 7,11 Z" fill="#143A5C" />
          <path d="M6.6,10.2 C9.2,9 12,8.4 15,8.4 C18,8.4 20.8,9 23.4,10.2 C23.8,11.1 23.8,12 23.4,12.9 C20.8,11.7 18,11.1 15,11.1 C12,11.1 9.2,11.7 6.6,12.9 C6.2,12 6.2,11.1 6.6,10.2 Z" fill="#0E2B46" />
          <g className={cn(fade, dark && "opacity-0")}>
            <circle cx="11.2" cy="17.5" r="1.9" fill="#122A40" /><circle cx="18.8" cy="17.5" r="1.9" fill="#122A40" />
            <circle cx="10.5" cy="16.8" r="0.7" fill="#fff" /><circle cx="18.1" cy="16.8" r="0.7" fill="#fff" />
          </g>
          <g className={cn(fade, !dark && "opacity-0")}>
            <path d="M9.4,17.8 C10.1,18.8 12.3,18.8 13,17.8" stroke="#122A40" strokeWidth="1.3" strokeLinecap="round" fill="none" />
            <path d="M17,17.8 C17.7,18.8 19.9,18.8 20.6,17.8" stroke="#122A40" strokeWidth="1.3" strokeLinecap="round" fill="none" />
          </g>
          <path d="M15,20.6 C16.7,20.6 17.8,21.3 17.8,22 C17.8,22.8 16.6,23.3 15,23.3 C13.4,23.3 12.2,22.8 12.2,22 C12.2,21.3 13.3,20.6 15,20.6 Z" fill="#F66623" />
        </svg>
        <span aria-hidden className={cn("absolute -right-px top-0 font-display text-[8px] font-bold leading-none text-[#8CA6BC]", fade, !dark && "opacity-0")}>
          z
        </span>
      </span>
    </button>
  );
}
