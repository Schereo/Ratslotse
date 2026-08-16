"use client";

// Randmarken des Rechnungsprüfungsamts als Pille.
//
// KEINE BEWERTUNGSFARBEN — im Haushalts-Bereich durchgehend, hier aber mit
// besonderem Grund: Das sind Beanstandungen gegen die eigene Verwaltung. Rot
// für „Beanstandung" würde die Seite zur Anklage machen, und zwar mit einem
// Mittel, das dem Bericht fremd ist: Er selbst arbeitet mit zwei Buchstaben
// am Seitenrand, ohne Farbe und ohne Ausrufezeichen.
//
// Unterschieden wird deshalb über Gewicht statt Farbe: Beanstandungen (B, WB)
// tragen einen kräftigeren Rahmen und fette Schrift, Hinweise und Korrekturen
// stehen ruhiger da. Was die Marke bedeutet, sagt der Bericht selbst — der
// Text kommt aus seiner Legende, nicht von uns.

import { cn } from "@/lib/utils";

const SCHWER = new Set(["B", "WB"]);

export function MarkePille({ marke, name, klein = false, className }: {
  marke: string;
  /** Name aus der Legende des jeweiligen Jahrgangs („Wiederholte Beanstandung"). */
  name?: string | null;
  klein?: boolean;
  className?: string;
}) {
  const schwer = SCHWER.has(marke);
  return (
    <span
      title={name ?? undefined}
      className={cn(
        "inline-flex flex-none items-center gap-1.5 rounded-full border bg-card",
        klein ? "px-2 py-0.5" : "px-2.5 py-1",
        schwer ? "border-foreground/25" : "border-border",
        className,
      )}
    >
      <span className={cn(
        "font-mono uppercase tracking-[0.08em]",
        klein ? "text-[9.5px]" : "text-[10px]",
        schwer ? "font-semibold text-foreground" : "text-muted-foreground",
      )}>
        {marke}
      </span>
      {name && (
        <span className={cn(
          klein ? "text-[10.5px]" : "text-[11.5px]",
          schwer ? "font-semibold text-foreground" : "text-muted-foreground",
        )}>
          {name}
        </span>
      )}
    </span>
  );
}
