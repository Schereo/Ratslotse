"use client";

// Reiter-Gerüst der Bereichsseite.
//
// Warum Reiter und nicht einfach untereinander: Die Seite beantwortet drei
// verschiedene Fragen — was der Bereich ist und kostet, was am Jahresende
// wirklich daraus wurde, und woher wir das wissen. Als eine Rolle ist das auf
// 375 px eine sehr lange Strecke, an deren Ende die Quellenangaben stehen, die
// kaum jemand sucht, während der Vergleich Plan/Ist mittendrin untergeht.
//
// Was NICHT hinter einen Reiter gehört: der Brutto/Netto-Umschalter. Er ist
// das Lehrstück der Seite (der Grund, warum „größter Bereich" und „teuerster
// Bereich" nicht dasselbe sind) und steht deshalb im Überblick, also im ersten
// Blick. Ein Reiter „Alle Bereiche", hinter dem er verschwindet, wäre eine
// Aufräum-Entscheidung mit inhaltlichem Preis.
//
// Kein Zustand in der URL: Ein Reiterwechsel per `router.replace` setzt in
// Next die Scrollposition zurück — man tippt oben auf einen Reiter und landet
// wieder oben, nachdem man gerade gescrollt hatte. Der Reiter ist eine
// Ansichts-Einstellung, kein Ort.
//
// Bedienung nach WAI-ARIA (Tabs mit manueller Aktivierung): Pfeiltasten
// wandern, Pos1/Ende springen, Auswahl per Tastendruck. Nur der aktive Reiter
// liegt im Tab-Fokus (`tabIndex`), sonst hangelt man sich mit Tab durch alle.

import { useRef } from "react";
import { cn } from "@/lib/utils";

export type Reiter<T extends string> = { id: T; label: string };

export function BereichReiter<T extends string>({ reiter, aktiv, onChange, className }: {
  reiter: Reiter<T>[];
  aktiv: T;
  onChange: (id: T) => void;
  className?: string;
}) {
  const leiste = useRef<HTMLDivElement>(null);

  function taste(e: React.KeyboardEvent<HTMLButtonElement>, i: number) {
    const schritt = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
    let ziel: number | null = null;
    if (schritt) ziel = (i + schritt + reiter.length) % reiter.length;
    if (e.key === "Home") ziel = 0;
    if (e.key === "End") ziel = reiter.length - 1;
    if (ziel === null) return;
    e.preventDefault();
    onChange(reiter[ziel].id);
    // Der neue Reiter bekommt den Fokus mit — sonst bedient die Tastatur eine
    // Auswahl, die sie nicht mehr sieht.
    const knoepfe = leiste.current?.querySelectorAll("button");
    knoepfe?.[ziel]?.focus();
  }

  return (
    // Scrollzeile statt Umbruch: Vier Reiter passen auf 375 px nicht in eine
    // Zeile, und eine umgebrochene Reiterleiste liest sich als zwei Leisten.
    <div className={cn("scrollbar-none -mx-1 overflow-x-auto px-1", className)}>
      <div
        ref={leiste}
        role="tablist"
        aria-label="Ansichten dieses Bereichs"
        className="flex w-max min-w-full items-stretch gap-0.5 border-b border-border"
      >
        {reiter.map((r, i) => {
          const an = r.id === aktiv;
          return (
            <button
              key={r.id}
              type="button"
              role="tab"
              id={`reiter-${r.id}`}
              aria-selected={an}
              aria-controls={`tafel-${r.id}`}
              tabIndex={an ? 0 : -1}
              onClick={() => onChange(r.id)}
              onKeyDown={(e) => taste(e, i)}
              className={cn(
                "whitespace-nowrap border-b-2 px-3 py-2.5 text-[13px] transition-colors",
                an
                  ? "border-primary font-semibold text-primary"
                  : "border-transparent text-foreground/70 hover:text-foreground",
              )}
            >
              {r.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** Die zugehörige Tafel. `tabIndex={0}`, weil ihr Inhalt scrollbar sein kann
 *  und sonst mit der Tastatur nicht erreichbar wäre. */
export function ReiterTafel({ id, aktiv, children, className }: {
  id: string;
  aktiv: string;
  children: React.ReactNode;
  className?: string;
}) {
  if (id !== aktiv) return null;
  return (
    <div
      role="tabpanel"
      id={`tafel-${id}`}
      aria-labelledby={`reiter-${id}`}
      tabIndex={0}
      className={cn("outline-none", className)}
    >
      {children}
    </div>
  );
}
