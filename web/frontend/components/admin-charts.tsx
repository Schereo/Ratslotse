"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

const AXIS_DAY = new Intl.DateTimeFormat("de-DE", { day: "numeric", month: "numeric" });
const AXIS_MONTH = new Intl.DateTimeFormat("de-DE", { month: "short", year: "2-digit" });

/** ISO-Tag → lokales Date (ohne den UTC-Versatz von `new Date("2026-07-22")`). */
function parseDay(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, (m || 1) - 1, d || 1);
}

/** Datumsachse unter einem Verlauf: wenige Stützpunkte, exakt über ihrem
 *  Datenpunkt (`point`) bzw. Balken (`bar`). Format richtet sich nach der
 *  Spanne — Tage bei kurzen Zeiträumen, Monate ab ~4 Monaten. */
export function ChartAxis({
  days,
  max = 4,
  mode = "point",
  className,
}: {
  days: string[];
  max?: number;
  mode?: "point" | "bar";
  className?: string;
}) {
  const n = days.length;
  if (n < 2) return null;
  const span = (parseDay(days[n - 1]).getTime() - parseDay(days[0]).getTime()) / 86_400_000;
  const fmt = span > 120 ? AXIS_MONTH : AXIS_DAY;
  const count = Math.max(2, Math.min(max, n));
  const ticks = [...new Set(Array.from({ length: count }, (_, k) => Math.round((k * (n - 1)) / (count - 1))))];
  return (
    <div
      className={cn("relative mt-1.5 h-3.5 text-[10.5px] leading-none tabular-nums text-muted-foreground/70", className)}
      aria-hidden
    >
      {ticks.map((i, k) => {
        const pos = mode === "bar" ? ((i + 0.5) / n) * 100 : (i / (n - 1)) * 100;
        const style: React.CSSProperties =
          k === 0 ? { left: 0 }
          : k === ticks.length - 1 ? { right: 0 }
          : { left: `${pos}%`, transform: "translateX(-50%)" };
        return (
          <span key={i} className="absolute whitespace-nowrap" style={style}>
            {fmt.format(parseDay(days[i]))}
          </span>
        );
      })}
    </div>
  );
}

/** Verlaufs-Sparkline mit Gradient-Fläche + Linie (Design 20a/21a). Skaliert die
 *  Werte selbst auf die Box; `preserveAspectRatio=none`, damit die Kurve die
 *  volle Breite füllt. Farbe als CSS-Farbwert (z. B. token-Variable). `days`
 *  (ISO, gleiche Länge wie `values`) blendet die Datumsachse darunter ein. */
export function AreaSparkline({
  values,
  color = "hsl(var(--primary))",
  className,
  height = 64,
  days,
  axisTicks = 4,
}: {
  values: number[];
  color?: string;
  className?: string;
  height?: number;
  days?: string[];
  axisTicks?: number;
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
    <div className={className}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        className="block w-full"
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
      {days?.length === values.length && <ChartAxis days={days} max={axisTicks} />}
    </div>
  );
}

/** Balkenreihe (Design 20a WAU / Nutzer-Verlauf): letzter Balken hervorgehoben.
 *  `days` (ISO je Balken) blendet die Datumsachse darunter ein. */
export function MiniBars({
  values,
  className,
  height = 70,
  highlightLast = true,
  days,
  axisTicks = 4,
}: {
  values: number[];
  className?: string;
  height?: number;
  highlightLast?: boolean;
  days?: string[];
  axisTicks?: number;
}) {
  const max = Math.max(1, ...values);
  return (
    <div className={className}>
      <div className="flex items-end gap-1.5" style={{ height }} aria-hidden>
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
      {days?.length === values.length && <ChartAxis days={days} max={axisTicks} mode="bar" />}
    </div>
  );
}

/** Kicker-Zeile über Kennzahlen (Design 20a/21a): 12px, uppercase, tracking. */
export function StatKicker({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs font-semibold uppercase tracking-[0.05em] text-muted-foreground">{children}</p>
  );
}
