"use client";

// Die Legende einer Grafik — als BILD, nicht als Satz. Tims Wunsch
// 28.09.2026: „bei allen Graphen die Legende visuell machen, also darstellen
// welche Linie was bedeutet". Vorher stand über den Wahl-Grafiken eine
// Zeile wie „durchgezogen: Zwischenstand · gestrichelt: Hochrechnung" — man
// musste das Wort ins Bild übersetzen. Jetzt steht neben jedem Wort das
// Zeichen, genau so gezeichnet wie in der Grafik (dieselbe Farbe, derselbe
// Strich, dieselbe Deckkraft).
//
// Rein darstellend; die Grafik bleibt für Vorlesehilfen über ihre eigene
// Beschreibung erklärt — die Marken hier sind `aria-hidden`, die Wörter
// werden gelesen.

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export type LegendMark =
  /** Durchgezogene Linie. */
  | "line"
  /** Durchgezogen, aber blasser — die zweite Linie neben einer kräftigen. */
  | "line-faint"
  /** Gestrichelte Linie. */
  | "dashed"
  /** Dünne graue Bezugslinie (etwa 50 %). */
  | "rule"
  /** Gestrichelte Bezugslinie in Signalfarbe (etwa die Mehrheit). */
  | "rule-dashed"
  /** Voller Punkt. */
  | "dot"
  /** Hohler Punkt (Ring). */
  | "ring"
  /** Fläche unter einer Linie. */
  | "area";

export type LegendItem = {
  mark: LegendMark;
  label: ReactNode;
  /** CSS-Farbe der Marke; ohne Angabe die Textfarbe bzw. das Grau der Achsen. */
  color?: string;
  /** Deckkraft der Marke, wenn die Grafik sie blasser zeichnet. */
  opacity?: number;
};

const W = 22;
const H = 12;

export function LegendSwatch({ mark, color, opacity }: { mark: LegendMark; color?: string; opacity?: number }) {
  const c = color ?? "currentColor";
  const mid = H / 2;
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} aria-hidden className="flex-none overflow-visible" opacity={opacity}>
      {mark === "line" && <line x1={1} y1={mid} x2={W - 1} y2={mid} stroke={c} strokeWidth={2.25} strokeLinecap="round" />}
      {mark === "line-faint" && (
        <line x1={1} y1={mid} x2={W - 1} y2={mid} stroke={c} strokeWidth={2} strokeOpacity={0.55} strokeLinecap="round" />
      )}
      {mark === "dashed" && <line x1={1} y1={mid} x2={W - 1} y2={mid} stroke={c} strokeWidth={2} strokeDasharray="4 3" />}
      {mark === "rule" && (
        <line x1={0} y1={mid} x2={W} y2={mid} stroke={color} className={color ? undefined : "stroke-foreground/50"} strokeWidth={1.25} />
      )}
      {mark === "rule-dashed" && (
        <line x1={0} y1={mid} x2={W} y2={mid} stroke={color} className={color ? undefined : "stroke-signal"} strokeWidth={1.5} strokeDasharray="4 3" />
      )}
      {mark === "dot" && <circle cx={W / 2} cy={mid} r={4.5} fill={c} />}
      {mark === "ring" && <circle cx={W / 2} cy={mid} r={4} fill="hsl(var(--card))" stroke={c} strokeWidth={2} />}
      {mark === "area" && (
        <>
          <rect x={1} y={mid - 1} width={W - 2} height={H - mid} fill={c} fillOpacity={0.18} />
          <line x1={1} y1={mid - 1} x2={W - 1} y2={mid - 1} stroke={c} strokeWidth={2} />
        </>
      )}
    </svg>
  );
}

export function ChartLegend({ items, className }: { items: LegendItem[]; className?: string }) {
  return (
    <ul
      aria-label="Legende"
      data-testid="grafik-legende"
      className={cn("flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[12px] leading-snug text-muted-foreground", className)}
    >
      {items.map((item, i) => (
        <li key={i} className="flex items-center gap-1.5">
          <LegendSwatch mark={item.mark} color={item.color} opacity={item.opacity} />
          <span>{item.label}</span>
        </li>
      ))}
    </ul>
  );
}

/** Eine Farbskala: blass für den kleinsten gezeigten Wert, kräftig für den
 *  größten — für Karten, die nach Stärke tönen statt nach Kategorie. Die
 *  beiden Enden tragen die echten Werte, sonst sagt „kräftig" nichts. */
export function ChartScale({ label, low, high, from, to, className }: {
  label: ReactNode;
  low: ReactNode;
  high: ReactNode;
  /** CSS-Farbe am schwachen und am starken Ende — dieselbe wie in der Karte. */
  from: string;
  to: string;
  className?: string;
}) {
  return (
    <div
      data-testid="grafik-skala"
      className={cn("flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] leading-snug text-muted-foreground", className)}
    >
      <span>{label}</span>
      <span className="inline-flex items-center gap-1.5 tabular-nums">
        {low}
        <span aria-hidden className="inline-block h-3 w-20 rounded-sm" style={{ background: `linear-gradient(to right, ${from}, ${to})` }} />
        {high}
      </span>
    </div>
  );
}
