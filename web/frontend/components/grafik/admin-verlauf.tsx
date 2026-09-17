"use client";

import { scaleLinear } from "d3-scale";
import { line } from "d3-shape";
import { ChevronDown } from "lucide-react";
import { useBreite } from "@/lib/use-breite";
import { deZahl } from "./format";
import { AbleseBeschreibung, AbleseFlaeche, Ableseleiste, useAblesen, useAbleseId } from "./ablesen";

const datum = new Intl.DateTimeFormat("de-DE", { day: "numeric", month: "short", year: "numeric" });
const kurz = new Intl.DateTimeFormat("de-DE", { day: "numeric", month: "numeric" });
function tag(day: string) { return new Date(`${day}T12:00:00`); }

/** Dates and values come from the same server series. Zero is a zero-height
 * bar; it must never become the old sparkline's decorative minimum bar. */
export function AdminVerlauf({ days, values, label, mode = "bar", weekly = false, extras = [], height = 180 }: {
  days: string[];
  values: number[];
  label: string;
  mode?: "bar" | "line";
  weekly?: boolean;
  extras?: { label: string; values: number[] }[];
  height?: number;
}) {
  const { box, breite } = useBreite(640, 180);
  const steuerung = useAblesen(values.length, values.length - 1);
  const id = useAbleseId();
  const links = 38;
  const rechts = breite - 12;
  const unten = height - 30;
  const y = scaleLinear().domain([0, Math.max(1, ...values)]).nice(3).range([unten, 12]);
  const step = (rechts - links) / Math.max(values.length, 1);
  const x = (i: number) => links + step * (i + 0.5);
  const ticks = y.ticks(3).filter(Number.isInteger);
  const dateLabel = (day: string) => {
    if (!weekly) return datum.format(tag(day));
    const start = tag(day);
    start.setDate(start.getDate() - 6);
    return `${kurz.format(start)} – ${datum.format(tag(day))}`;
  };
  const stellen = days.map((day, i) => ({
    title: dateLabel(day),
    werte: [{ label, value: deZahl(values[i]), farbe: "hsl(var(--primary))" }, ...extras.map((extra) => ({ label: extra.label, value: deZahl(extra.values[i]) }))],
    vorlesen: `${dateLabel(day)}: ${deZahl(values[i])} ${label}${extras.map((e) => `, ${deZahl(e.values[i])} ${e.label}`).join("")}`,
  }));
  const achse = [...new Set(breite < 360 ? [0, days.length - 1] : [0, Math.floor((days.length - 1) / 2), days.length - 1])];

  return (
    <div ref={box} className="mt-4 min-w-0">
      {values.length === 0 || values.length !== days.length ? <p className="py-8 text-sm text-muted-foreground">Für diesen Zeitraum liegt kein Verlauf vor.</p> : <>
        <AbleseBeschreibung id={id}>{label} im Zeitverlauf. Mit Pfeiltasten, Maus oder Antippen einzelne Werte lesen. Die Tabelle enthält alle Werte.</AbleseBeschreibung>
        <svg width="100%" height={height} viewBox={`0 0 ${breite} ${height}`} role="group" aria-label={`${label} im Zeitverlauf`} aria-describedby={id}>
          <g aria-hidden>
            {ticks.map((n) => <g key={n}>
              <line x1={links} x2={rechts} y1={y(n)} y2={y(n)} className="stroke-border" strokeDasharray={n === 0 ? undefined : "3 4"} />
              <text x={links - 8} y={y(n) + 4} textAnchor="end" className="fill-muted-foreground text-xs tabular-nums">{deZahl(n)}</text>
            </g>)}
            {mode === "bar" ? values.map((v, i) => (
              <rect key={days[i]} x={x(i) - step * 0.34} y={y(v)} width={step * 0.68} height={Math.max(0, unten - y(v))} rx={Math.min(3, step / 5)}
                className="fill-primary transition-opacity" opacity={steuerung.aktiv === i ? 1 : 0.45} />
            )) : <>
              <path d={line<number>().x((_, i) => x(i)).y((v) => y(v))(values) ?? ""} fill="none" className="stroke-primary" strokeWidth={2.5} strokeLinejoin="round" />
              {values.length === 1 && <circle cx={x(0)} cy={y(values[0])} r={4} className="fill-primary" />}
            </>}
            {achse.map((i, n) => <text key={i} x={n === 0 ? links : n === achse.length - 1 ? rechts : x(i)} y={height - 5}
              textAnchor={n === 0 ? "start" : n === achse.length - 1 ? "end" : "middle"} className="fill-muted-foreground text-xs">{kurz.format(tag(days[i]))}</text>)}
          </g>
          <AbleseFlaeche stellen={stellen} steuerung={steuerung} x={x} xVon={links} xBis={rechts} yVon={12} hoehe={unten - 12}
            gruppe="Zeitpunkte" marken={mode === "line" ? (i) => [{ y: y(values[i]), farbe: "hsl(var(--primary))" }] : undefined} />
        </svg>
        <Ableseleiste stelle={stellen[steuerung.aktiv]} steuerung={steuerung} haftet={false} note="Antippen oder mit ← → ablesen" />
        <details className="group mt-2">
          <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
            <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" aria-hidden />Alle {values.length} Werte als Tabelle
          </summary>
          <div className="max-h-80 overflow-auto rounded-lg border border-border">
            <table className="w-full text-left text-sm tabular-nums">
              <caption className="sr-only">{label} – vollständiger Verlauf</caption>
              <thead className="sticky top-0 bg-muted"><tr><th className="p-3 font-medium">{weekly ? "Zeitraum" : "Datum"}</th><th className="p-3 text-right font-medium">{label}</th>{extras.map((e) => <th key={e.label} className="p-3 text-right font-medium">{e.label}</th>)}</tr></thead>
              <tbody>{days.map((day, i) => <tr key={day} className="border-t border-border"><td className="p-3">{dateLabel(day)}</td><td className="p-3 text-right">{deZahl(values[i])}</td>{extras.map((e) => <td key={e.label} className="p-3 text-right">{deZahl(e.values[i])}</td>)}</tr>)}</tbody>
            </table>
          </div>
        </details>
      </>}
    </div>
  );
}
