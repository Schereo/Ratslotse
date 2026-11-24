"use client";

// <VorzeichenSaeulen> — Säulen über und unter einer Nulllinie, je Säule mit
// ihrer ART (GB-16): Ist, Prognose, Plan oder Finanzplanung.
//
// Gebaut für „Was der Haushaltsentwurf zeigt“ (Tim, 23.11.2026, nach dem
// Prototyp „die grafiken gefallen mir gut“). Ein Haushaltsentwurf mischt in
// EINER Reihe gezählte Jahre, eine Schätzung fürs laufende Jahr und Pläne für
// fünf Jahre — sähen alle Säulen gleich aus, läse man den Plan 2030 wie ein
// Ergebnis. Deshalb trägt jede Säule ihre Art sichtbar:
//
//   Ist            voll
//   Prognose       schraffiert
//   Plan           heller, mit Rand
//   Finanzplanung  am hellsten
//
// Überschüsse stehen in der Hafenblau-Rampe, Fehlbeträge in der Schiefer-
// Rampe — dieselben Rampen wie Einnahmen und Ausgaben im Haushalt. KEINE
// Bewertungsfarbe: Ein Fehlbetrag ist nicht rot (GB-03, Regel des Bereichs).
// Signal-Orange markiert nur die hervorgehobenen Kategorien, von denen der
// Satz spricht.
//
// Die viewBox folgt der gemessenen Breite (`useBreite`, Faktor 1): Schrift
// bleibt 11 px, auf dem Telefon wie am Schreibtisch.

import { useId } from "react";
import { deZahl } from "@/components/grafik/format";
import { useBreite } from "@/lib/use-breite";

export type SaeulenArt = "actual" | "forecast" | "plan" | "financial_plan";

export const ART_LABEL: Record<SaeulenArt, string> = {
  actual: "Ist",
  forecast: "Prognose",
  plan: "Plan",
  financial_plan: "Finanzplanung",
};

export type SaeulenReihe = { name: string; values: (number | null)[] };

const HOEHE = 220;
const OBEN = 22;
const UNTEN = 34;
const LINKS = 44;

/** Hübsche Achsenteilung: 1-2-2,5-5 je Zehnerpotenz. */
export function teilung(min: number, max: number, n = 4): number[] {
  const roh = (max - min) / n || 1;
  const p = 10 ** Math.floor(Math.log10(roh));
  const schritt = [1, 2, 2.5, 5, 10].map((x) => x * p).find((x) => x >= roh) ?? roh;
  const out: number[] = [];
  for (let v = Math.ceil(min / schritt) * schritt; v <= max + 1e-9; v += schritt) out.push(Number(v.toFixed(6)));
  return out;
}

function fuellung(art: SaeulenArt | null, minus: boolean, muster: string): { fill: string; stroke?: string } {
  const rampe = minus ? "aus" : "ein";
  switch (art) {
    case "actual": return { fill: `var(--hh-${rampe}-1)` };
    case "forecast": return { fill: `url(#${muster}-${minus ? "minus" : "plus"})` };
    case "plan": return { fill: `var(--hh-${rampe}-4)`, stroke: `var(--hh-${rampe}-0)` };
    case "financial_plan": return { fill: `var(--hh-${rampe}-${minus ? 7 : 5})` };
    default: return { fill: `var(--hh-${rampe}-2)` };
  }
}

export function VorzeichenSaeulen({ categories, kinds, series, stacked = false, highlight = [], unit, label }: {
  categories: string[];
  /** Art je Kategorie, vom Server gesetzt; `null` zeichnet neutral. */
  kinds?: (SaeulenArt | string | null)[];
  series: SaeulenReihe[];
  stacked?: boolean;
  /** Kategorien, von denen der Satz spricht — Signal-Marke unter der Achse. */
  highlight?: number[];
  unit: string;
  /** Ganzer Satz für Bildschirmleser (`role="img"`). */
  label: string;
}) {
  const { box, breite } = useBreite(640, 300);
  const muster = useId().replace(/:/g, "");
  const n = categories.length;
  if (!n || !series.length) return null;

  const summen = categories.map((_, i) => series.reduce((s, r) => s + (r.values[i] ?? 0), 0));
  const alle = stacked
    ? categories.flatMap((_, i) => {
        const pos = series.reduce((s, r) => s + Math.max(r.values[i] ?? 0, 0), 0);
        const neg = series.reduce((s, r) => s + Math.min(r.values[i] ?? 0, 0), 0);
        return [pos, neg];
      })
    : series.flatMap((r) => r.values.filter((v): v is number => v != null));
  const min = Math.min(0, ...alle);
  const max = Math.max(0, ...alle);
  const spanne = max - min || 1;
  const luft = spanne * 0.12;
  const lo = min < 0 ? min - luft : 0;
  const hi = max > 0 ? max + luft : 0;
  const y = (v: number) => OBEN + ((hi - v) / (hi - lo)) * (HOEHE - OBEN - UNTEN);
  const rechts = 8;
  const band = (breite - LINKS - rechts) / n;
  const gruppen = stacked ? 1 : series.length;
  const sw = Math.max(4, Math.min(34, (band * 0.72) / gruppen));
  const nachkomma = (v: number) => (Math.abs(v) >= 100 ? 0 : 1);
  const schmal = band < 34;
  const art = (i: number) => (kinds?.[i] ?? null) as SaeulenArt | null;
  // Achsenbeschriftung: das Jahr — und, wo ein Jahr zweimal vorkommt („2026
  // Plan“ neben „2026 Prognose“), darunter das Wort, das sie unterscheidet.
  const jahr = (k: string) => k.match(/\d{4}/)?.[0] ?? k;
  const doppelt = new Set(categories.map(jahr).filter((j, i, a) => a.indexOf(j) !== i));
  const zusatz = (k: string) => (doppelt.has(jahr(k)) ? k.replace(jahr(k), "").trim() : "");

  return (
    <div ref={box} className="w-full min-w-0">
      <svg viewBox={`0 0 ${breite} ${HOEHE}`} width={breite} height={HOEHE} role="img" aria-label={label}
        className="block h-auto max-w-full font-sans">
        <defs>
          {(["plus", "minus"] as const).map((s) => (
            <pattern key={s} id={`${muster}-${s}`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="6" height="6" fill={`var(--hh-${s === "minus" ? "aus" : "ein"}-${s === "minus" ? 6 : 5})`} />
              <line x1="0" y1="0" x2="0" y2="6" stroke={`var(--hh-${s === "minus" ? "aus" : "ein"}-1)`} strokeWidth="2" />
            </pattern>
          ))}
        </defs>
        {teilung(lo, hi).map((t) => (
          <g key={t}>
            <line x1={LINKS} x2={breite - rechts} y1={y(t)} y2={y(t)} stroke="hsl(var(--border))" strokeWidth={1} />
            <text x={LINKS - 6} y={y(t) + 4} textAnchor="end" className="fill-muted-foreground text-[11px] tabular-nums">
              {deZahl(t, 0)}
            </text>
          </g>
        ))}
        {categories.map((kat, i) => {
          const mitte = LINKS + band * i + band / 2;
          let fussPlus = 0;
          let fussMinus = 0;
          const hervor = highlight.includes(i);
          return (
            <g key={`${kat}-${i}`}>
              {series.map((r, j) => {
                const v = r.values[i];
                if (v == null) return null;
                const von = stacked ? (v >= 0 ? fussPlus : fussMinus) : 0;
                const bis = von + v;
                if (stacked) { if (v >= 0) fussPlus = bis; else fussMinus = bis; }
                const x = stacked ? mitte - sw / 2 : mitte - (gruppen * sw) / 2 + j * sw + 1;
                const top = Math.min(y(von), y(bis));
                const h = Math.max(1, Math.abs(y(bis) - y(von)));
                const f = fuellung(art(i), v < 0, muster);
                const a = art(i);
                return (
                  <g key={j}>
                    <rect x={x} y={top} width={Math.max(2, sw - 2)} height={h} rx={2}
                      fill={f.fill} stroke={f.stroke ?? "none"} strokeWidth={f.stroke ? 1.5 : 0}
                      className="gb-saeule-auf" style={{ animationDelay: `${i * 30}ms`, transformOrigin: `0 ${y(0)}px` }}>
                      <title>{`${kat}${series.length > 1 ? ` · ${r.name}` : ""}: ${deZahl(v, nachkomma(v))} ${unit}${a ? ` (${ART_LABEL[a]})` : ""}`}</title>
                    </rect>
                    {!stacked && !schmal && (
                      <text x={x + (sw - 2) / 2} y={v >= 0 ? top - 4 : top + h + 12} textAnchor="middle"
                        className={hervor ? "fill-foreground text-[11px] font-semibold tabular-nums" : "fill-muted-foreground text-[11px] tabular-nums"}>
                        {deZahl(v, nachkomma(v))}
                      </text>
                    )}
                  </g>
                );
              })}
              {stacked && !schmal && (
                <text x={mitte} y={y(Math.max(fussPlus, 0)) - 4} textAnchor="middle"
                  className={hervor ? "fill-foreground text-[11px] font-semibold tabular-nums" : "fill-muted-foreground text-[11px] tabular-nums"}>
                  {deZahl(summen[i], nachkomma(summen[i]))}
                </text>
              )}
              <text x={mitte} y={HOEHE - UNTEN + 16} textAnchor="middle"
                className={hervor ? "fill-foreground text-[11px] font-semibold" : "fill-muted-foreground text-[11px]"}>
                {schmal && /^\d{4}$/.test(jahr(kat)) ? jahr(kat).slice(2) : jahr(kat)}
              </text>
              {zusatz(kat) && (
                <text x={mitte} y={HOEHE - UNTEN + 28} textAnchor="middle" className="fill-muted-foreground text-[10px]">
                  {schmal ? zusatz(kat).slice(0, 4) + "." : zusatz(kat)}
                </text>
              )}
              {hervor && (
                <line x1={mitte - Math.min(band * 0.35, 14)} x2={mitte + Math.min(band * 0.35, 14)}
                  y1={HOEHE - UNTEN + (zusatz(kat) ? 33 : 22)} y2={HOEHE - UNTEN + (zusatz(kat) ? 33 : 22)}
                  stroke="hsl(var(--signal))" strokeWidth={2.5} strokeLinecap="round" />
              )}
            </g>
          );
        })}
        <line x1={LINKS} x2={breite - rechts} y1={y(0)} y2={y(0)} stroke="hsl(var(--foreground))" strokeWidth={1.2} />
      </svg>
    </div>
  );
}

/** Die Legende der Arten, die in dieser Grafik vorkommen — in fester Folge. */
export function ArtLegende({ kinds, minus }: { kinds: (string | null)[]; minus: boolean }) {
  const da = (Object.keys(ART_LABEL) as SaeulenArt[]).filter((a) => kinds.includes(a));
  if (da.length < 2) return null;
  const r = minus ? "aus" : "ein";
  const stil: Record<SaeulenArt, React.CSSProperties> = {
    actual: { background: `var(--hh-${r}-1)` },
    forecast: { background: `repeating-linear-gradient(45deg, var(--hh-${r}-1) 0 2px, var(--hh-${r}-${minus ? 6 : 5}) 2px 5px)` },
    plan: { background: `var(--hh-${r}-4)`, boxShadow: `inset 0 0 0 1.5px var(--hh-${r}-0)` },
    financial_plan: { background: `var(--hh-${r}-${minus ? 7 : 5})` },
  };
  return (
    <ul className="flex flex-wrap gap-x-3.5 gap-y-1 text-meta text-muted-foreground" aria-label="Legende">
      {da.map((a) => (
        <li key={a} className="inline-flex items-center gap-1.5">
          <span aria-hidden className="inline-block h-3 w-3 rounded-[3px]" style={stil[a]} />
          {ART_LABEL[a]}
        </li>
      ))}
    </ul>
  );
}
