"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { ArrowUp } from "lucide-react";
import { cn, pfad } from "@/lib/utils";

/**
 * Schwebender „Nach oben"-Button — erscheint nach ~2 Bildschirmhöhen Scrollen.
 * Auf Mobil über der Bottom-Nav, auf Desktop über dem Sticky-Footer.
 * NICHT im Ratsgespräch (/fragen): Dort klebt der Composer an der
 * Tab-Bar, der Knopf schwebte genau über dem Senden-Pfeil — und gebraucht
 * wird er da nicht, das Gespräch hat seinen eigenen Sprung-Pfeil
 * (Tims TestFlight-Feedback 11.08.).
 */
export function BackToTop() {
  const [show, setShow] = useState(false);
  const imGespraech = pfad(usePathname()) === "/fragen";

  useEffect(() => {
    const onScroll = () => setShow(window.scrollY > window.innerHeight * 1.5);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  if (imGespraech) return null;

  const toTop = () => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
  };

  return (
    <button
      type="button"
      onClick={toTop}
      aria-label="Nach oben scrollen"
      className={cn(
        // Über dem Lotti-Knopf, nicht neben ihm: Der schwebt seit 09/2026 in
        // derselben Ecke (components/assistentin/knopf.tsx, 56 px hoch). Die
        // Höhen stehen als Variablen da, damit hier keine dritte Zahl entsteht.
        "fixed right-4 z-40 flex h-10 w-10 items-center justify-center rounded-full border border-border bg-card text-muted-foreground shadow-lifted transition-[opacity,transform,color] duration-200 ease-out-strong hover:text-foreground active:scale-95 desk:right-6 print:hidden",
        "bottom-[calc(var(--rl-unten,0px)+var(--rl-composer,0px)+5.25rem)]",
        "desk:bottom-[calc(var(--rl-composer,0px)+5.5rem)]",
        show ? "translate-y-0 opacity-100" : "pointer-events-none translate-y-3 opacity-0",
      )}
    >
      <ArrowUp className="h-4 w-4" />
    </button>
  );
}
