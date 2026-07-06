"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

/** Diagramm-Daten aus dem Answer-Payload (council/haushalt.py):
 *  bars = Balken je Bereich · share = Donut (Anteil) · trend = Jahresverlauf. */
export type QuizChartData = {
  type?: "bars" | "share" | "trend";
  title: string;
  unit: string;
  items: { label: string; value: number; highlight?: boolean }[];
};

const nf = new Intl.NumberFormat("de-DE");

/** Einstiegs-Animation: erst nach dem Mount auf Zielgröße wachsen (CSS-
 *  Transition; der globale prefers-reduced-motion-Block legt sie still). */
function useGrown() {
  const [grown, setGrown] = useState(false);
  useEffect(() => {
    const raf = requestAnimationFrame(() => setGrown(true));
    return () => cancelAnimationFrame(raf);
  }, []);
  return grown;
}

function Bars({ items }: { items: QuizChartData["items"] }) {
  const grown = useGrown();
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <ul className="mt-2 space-y-1.5">
      {items.map((it) => (
        <li key={it.label} className="flex items-center gap-2 text-xs">
          <span className={cn("w-32 shrink-0 truncate sm:w-40",
            it.highlight ? "font-semibold text-foreground" : "text-muted-foreground")}
            title={it.label}>
            {it.label}
          </span>
          <span className="h-2.5 flex-1 overflow-hidden rounded-full bg-muted">
            <span className={cn("block h-full rounded-full transition-[width] duration-700 ease-out-strong",
              it.highlight ? "bg-amber-500" : "bg-primary/60")}
              style={{ width: grown ? `${Math.max((it.value / max) * 100, 1.5)}%` : "0%" }} />
          </span>
          <span className={cn("w-12 shrink-0 text-right tabular-nums",
            it.highlight ? "font-semibold text-foreground" : "text-muted-foreground")}>
            {nf.format(it.value)}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Donut: erster (hervorgehobener) Eintrag als amberfarbenes Segment, Rest
 *  gedeckt — großer Prozentwert in der Mitte, Legende daneben. */
function Share({ items, unit }: { items: QuizChartData["items"]; unit: string }) {
  const grown = useGrown();
  const total = items.reduce((s, i) => s + i.value, 0) || 1;
  const main = items.find((i) => i.highlight) ?? items[0];
  const frac = main.value / total;
  const R = 34;
  const C = 2 * Math.PI * R;
  return (
    <div className="mt-2 flex flex-wrap items-center gap-4">
      <svg viewBox="0 0 96 96" className="h-28 w-28 shrink-0" role="img"
           aria-label={`${main.label}: ${nf.format(main.value)} ${unit}`}>
        <circle cx="48" cy="48" r={R} fill="none" strokeWidth="13" className="stroke-muted" />
        <circle cx="48" cy="48" r={R} fill="none" strokeWidth="13" strokeLinecap="round"
          className="stroke-amber-500 transition-[stroke-dasharray] duration-700 ease-out-strong"
          strokeDasharray={`${(grown ? frac : 0) * C} ${C}`}
          transform="rotate(-90 48 48)" />
        <text x="48" y="46" textAnchor="middle"
          className="fill-foreground text-[19px] font-bold tabular-nums">
          {nf.format(main.value)}
        </text>
        <text x="48" y="61" textAnchor="middle" className="fill-muted-foreground text-[9px]">
          {unit}
        </text>
      </svg>
      <ul className="min-w-0 flex-1 space-y-1.5">
        {items.map((it) => (
          <li key={it.label} className="flex items-center gap-2 text-xs">
            <span className={cn("h-2.5 w-2.5 shrink-0 rounded-sm",
              it.highlight ? "bg-amber-500" : "bg-muted-foreground/40")} />
            <span className={cn("min-w-0 truncate",
              it.highlight ? "font-semibold text-foreground" : "text-muted-foreground")}
              title={it.label}>
              {it.label}
            </span>
            <span className="ml-auto shrink-0 tabular-nums text-muted-foreground">
              {nf.format(it.value)} {unit === "Prozent" ? "%" : ""}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Trendlinie über Jahre: sanfte Fläche + Linie + Punkte, Endpunkt (aktuelles
 *  Jahr) hervorgehoben, Werte über den Punkten. */
function Trend({ items }: { items: QuizChartData["items"] }) {
  const grown = useGrown();
  const W = 340;
  const H = 120;
  const PAD_X = 22;
  const PAD_TOP = 22;
  const PAD_BOTTOM = 20;
  const vals = items.map((i) => i.value);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = Math.max(max - min, 1);
  const x = (i: number) => PAD_X + (i * (W - 2 * PAD_X)) / Math.max(items.length - 1, 1);
  const y = (v: number) => PAD_TOP + (1 - (v - min) / span) * (H - PAD_TOP - PAD_BOTTOM);
  const pts = items.map((it, i) => [x(i), y(it.value)] as const);
  const line = pts.map(([px, py]) => `${px},${py}`).join(" ");
  const area = `${PAD_X},${H - PAD_BOTTOM} ${line} ${W - PAD_X},${H - PAD_BOTTOM}`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mt-2 w-full" role="img"
         aria-label={items.map((i) => `${i.label}: ${nf.format(i.value)}`).join(", ")}>
      <polygon points={area} className="fill-primary/10" />
      <polyline points={line} fill="none" strokeWidth="2.5" strokeLinejoin="round"
        strokeLinecap="round" pathLength={1}
        className="stroke-primary transition-[stroke-dashoffset] duration-1000 ease-out-strong"
        strokeDasharray="1" strokeDashoffset={grown ? 0 : 1} />
      {items.map((it, i) => (
        <g key={it.label}>
          <circle cx={x(i)} cy={y(it.value)} r={it.highlight ? 4.5 : 3}
            className={cn("transition-opacity duration-700",
              it.highlight ? "fill-amber-500" : "fill-primary",
              grown ? "opacity-100" : "opacity-0")} />
          <text x={x(i)} y={y(it.value) - 8} textAnchor="middle"
            className={cn("tabular-nums text-[10px] transition-opacity duration-700",
              it.highlight ? "fill-foreground font-semibold" : "fill-muted-foreground",
              grown ? "opacity-100" : "opacity-0")}>
            {nf.format(it.value)}
          </text>
          <text x={x(i)} y={H - 6} textAnchor="middle" className="fill-muted-foreground text-[10px]">
            {it.label}
          </text>
        </g>
      ))}
    </svg>
  );
}

/** Diagramm in der Quiz-Auflösung — rendert je nach `type` Balken, Donut oder
 *  Trendlinie in einem gemeinsamen Rahmen (Titel + Einheiten-Fußnote). */
export function QuizChart({ chart, className }: { chart: QuizChartData; className?: string }) {
  if (!chart.items?.length) return null;
  const type = chart.type ?? "bars";
  return (
    <div className={cn("rounded-lg border border-border bg-background/60 p-3", className)}>
      <p className="text-xs font-semibold text-foreground">{chart.title}</p>
      {type === "share" ? <Share items={chart.items} unit={chart.unit} />
        : type === "trend" ? <Trend items={chart.items} />
        : <Bars items={chart.items} />}
      <p className="mt-1.5 text-[11px] text-muted-foreground">Angaben in {chart.unit}</p>
    </div>
  );
}
