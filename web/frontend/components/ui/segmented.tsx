import * as React from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Segment-Umschalter (Pill-Gruppe auf muted-Grund) — vorher fünfmal leicht
 * unterschiedlich handgebaut (Suchen/KI-Frage, Beschlüsse/Berichte/Alle,
 * Ergebnis-Filter, Sitzungs-Zeitraum, Analyse-Subtabs), jetzt eine Komponente.
 *
 * `tone` steuert die aktive Fläche: "card" für Ansichts-/Subtab-Wechsel,
 * "primary" für inhaltliche Filter. `value` darf leer sein (nichts aktiv,
 * z. B. wenn eine Suche den Zeitraum-Filter außer Kraft setzt).
 */
export type SegmentedOption<T extends string> = {
  value: T;
  label: React.ReactNode;
  icon?: LucideIcon;
  tour?: string;
  /** Dezenter Glanz-Lockruf (Sweep + funkelndes Icon), solange die Option
   *  NICHT aktiv ist — für Features, die entdeckt werden wollen (KI-Frage). */
  sparkle?: boolean;
};

export function Segmented<T extends string>({
  value,
  onChange,
  options,
  className,
  tone = "card",
}: {
  value?: T;
  onChange: (v: T) => void;
  options: SegmentedOption<T>[];
  className?: string;
  tone?: "card" | "primary";
}) {
  return (
    <div className={cn("flex gap-1 rounded-md bg-muted p-1", className)} role="group">
      {options.map((o) => {
        const active = o.value === value;
        const Icon = o.icon;
        const twinkle = !!o.sparkle && !active;
        return (
          <button
            key={o.value}
            type="button"
            onClick={() => onChange(o.value)}
            aria-pressed={active}
            data-tour={o.tour}
            className={cn(
              // Press-Feedback wie beim Button — Segment-Wechsel ist eine der
              // häufigsten Berührungen der App (Tabs, Filter).
              "inline-flex flex-1 items-center justify-center gap-1.5 whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium transition-[color,background-color,transform] duration-150 ease-out-strong active:scale-[0.97]",
              active
                ? tone === "primary"
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "bg-card text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
              twinkle && "qa-glint",
            )}
          >
            {Icon && <Icon className={cn("h-4 w-4", twinkle && "qa-sparkle text-signal")} />}
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
