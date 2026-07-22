"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

/** Verlaufs-Sparkline mit Gradient-Fläche + Linie (Design 20a/21a). Skaliert die
 *  Werte selbst auf die Box; `preserveAspectRatio=none`, damit die Kurve die
 *  volle Breite füllt. Farbe als CSS-Farbwert (z. B. token-Variable). */
export function AreaSparkline({
  values,
  color = "hsl(var(--primary))",
  className,
  height = 64,
}: {
  values: number[];
  color?: string;
  className?: string;
  height?: number;
}) {
  const id = React.useId().replace(/:/g, "");
  const W = 280;
  const H = 80;
  const max = Math.max(1, ...values);
  const n = values.length;
  const pts = values.map((v, i) => {
    const x = n <= 1 ? W : (i / (n - 1)) * W;
    const y = H - 6 - (v / max) * (H - 12); // 6px Rand oben/unten
    return [Math.round(x * 100) / 100, Math.round(y * 100) / 100] as const;
  });
  const line = pts.map(([x, y], i) => `${i ? "L" : "M"}${x},${y}`).join(" ");
  const area = `${line} L${W},${H} L0,${H} Z`;
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      className={cn("block w-full", className)}
      style={{ height }}
      aria-hidden
    >
      <defs>
        <linearGradient id={`sp${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={color} stopOpacity="0.22" />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#sp${id})`} />
      <path d={line} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/** Balkenreihe (Design 20a WAU / Nutzer-Verlauf): letzter Balken hervorgehoben. */
export function MiniBars({
  values,
  className,
  height = 70,
  highlightLast = true,
}: {
  values: number[];
  className?: string;
  height?: number;
  highlightLast?: boolean;
}) {
  const max = Math.max(1, ...values);
  return (
    <div className={cn("flex items-end gap-1.5", className)} style={{ height }} aria-hidden>
      {values.map((v, i) => (
        <span
          key={i}
          className={cn(
            "flex-1 rounded-t-[4px]",
            highlightLast && i === values.length - 1 ? "bg-primary" : "bg-primary/50",
          )}
          style={{ height: `${Math.max(4, (v / max) * 100)}%` }}
        />
      ))}
    </div>
  );
}

/** Kicker-Zeile über Kennzahlen (Design 20a/21a): 12px, uppercase, tracking. */
export function StatKicker({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs font-semibold uppercase tracking-[0.05em] text-muted-foreground">{children}</p>
  );
}
