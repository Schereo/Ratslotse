"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

/** iOS-artiger Schalter (RL-701, 5a/6a): 51×31, an = Primärblau, aus =
 *  hsl(208 25% 82) (dark: muted). Ein Button mit role=switch — kein Radix
 *  nötig, Fokus-Ring + Tastatur (Space/Enter) kommen vom Button. */
export function Switch({
  checked,
  onCheckedChange,
  disabled,
  className,
  "aria-label": ariaLabel,
}: {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  className?: string;
  "aria-label"?: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      disabled={disabled}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        "relative h-[31px] w-[51px] shrink-0 rounded-full transition-colors duration-200 ease-out-strong",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        "disabled:cursor-not-allowed disabled:opacity-50",
        checked ? "bg-primary" : "bg-[hsl(208_25%_82%)] dark:bg-muted",
        className,
      )}
    >
      <span
        aria-hidden
        className={cn(
          "absolute top-[2px] h-[27px] w-[27px] rounded-full bg-white shadow-sm transition-transform duration-200 ease-out-strong",
          checked ? "translate-x-[22px]" : "translate-x-[2px]",
        )}
        style={{ left: 0 }}
      />
    </button>
  );
}
