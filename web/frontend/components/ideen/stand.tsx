/**
 * Der Stand in Oldenburg — dieselben vier Stufen auf Einzelkarte, Bewegung
 * und Ideen-Seite.
 *
 * Die Töne kommen aus derselben Palette wie „vertagt" und „umstritten"
 * (`council-goals.tsx`, `decision-ui.tsx`) — Anzeigetafel-Tönung, nie eine
 * dunkle Karte im Hellmodus. `bg-warning` gibt es in diesem Projekt nicht;
 * die erste Fassung der Ideen-Seite benutzte es, und die Marke blieb
 * ungetönt.
 */
import { cn } from "@/lib/utils";

export const STAND: Record<string, { text: string; kurz: string; ton: string }> = {
  missing: {
    text: "In Oldenburg nicht gefunden",
    kurz: "fehlt",
    ton: "border-primary/25 bg-primary/10 text-primary",
  },
  partial: {
    text: "Teilweise vorhanden",
    kurz: "teilweise",
    ton: "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/15 dark:text-amber-300",
  },
  present: {
    text: "Oldenburg hat das",
    kurz: "vorhanden",
    ton: "border-transparent bg-muted text-muted-foreground",
  },
  // Nicht „fehlt", sondern „kann hier gar nicht greifen": Eine fahrrad-
  // freundliche Gestaltung von Stadtbahngleisen setzt eine Stadtbahn voraus.
  not_applicable: {
    text: "Für Oldenburg nicht anwendbar",
    kurz: "nicht anwendbar",
    ton: "border-transparent bg-muted text-muted-foreground",
  },
};

export function StandPille({ status, className }: { status: string; className?: string }) {
  const s = STAND[status];
  if (!s) return null;
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        s.ton,
        className,
      )}
    >
      {s.text}
    </span>
  );
}
