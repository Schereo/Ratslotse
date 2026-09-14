"use client";

// Die drei kleinen Bausteine, die jede Wahlabend-Ansicht braucht — standen
// bis 09/2026 in view.tsx und wären mit der Kandidaten-Rangliste zum
// Ringimport geworden (view lädt kandidaten, kandidaten bräuchte view).

import type { StatusTon } from "@/lib/wahlabend";
import { cn } from "@/lib/utils";

export const KICKER = "font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground";

export const TON: Record<StatusTon, string> = {
  seated: "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
  shaky: "bg-amber-50 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200",
  projected: "bg-primary/10 text-primary",
  close: "bg-amber-50 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200",
  open: "bg-muted text-muted-foreground",
  out: "bg-muted text-muted-foreground",
  unknown: "border border-dashed border-border text-muted-foreground",
};

/** Der 8-px-Punkt in Listenfarbe — die einzige Form, in der eine Parteifarbe
 *  hier vorkommt (Designsprache: Punkte, nie Flächen). */
export function Punkt({ color, dark, className }: { color: string; dark: string; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn("inline-block h-2 w-2 flex-none rounded-full bg-[var(--dot)] ring-1 ring-inset ring-black/10 dark:bg-[var(--dot-dark)]", className)}
      style={{ "--dot": color, "--dot-dark": dark } as React.CSSProperties}
    />
  );
}
