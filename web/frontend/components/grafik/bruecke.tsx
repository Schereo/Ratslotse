"use client";

// <Bruecke> — von einem Wert über Schritte mit Vorzeichen zu einem anderen
// (GB-17). Der Wasserfall (GB-14) kennt nur Abzüge von einer positiven
// Summe; ein Haushaltsentwurf erklärt aber, wie aus −64,9 Mio. € Fehlbetrag
// −170,1 werden — mit Schritten in beide Richtungen und Summen unter null.
//
// Jeder Schritt hängt an der Laufsumme (`cumsum`, kein schwebender Balken
// von Hand). Die Summenprobe ist eingebaut: Geht die Brücke nicht auf, sagt
// die Grafik das, statt still eine falsche Lücke zu zeichnen (der Server
// prüft dasselbe, s. council/budget_findings.py).
//
// Farben ohne Bewertung: Start und Ende voll (Hafenblau über, Schiefer unter
// null), Schritte heller in der Rampe ihrer Richtung.

import { cumsum } from "d3-array";
import { deZahl, mitVorzeichen } from "@/components/grafik/format";
import { teilung } from "@/components/grafik/vorzeichen-saeulen";
import { useBreite } from "@/lib/use-breite";

export type BrueckenPunkt = { label: string; value: number };

const HOEHE = 240;
const OBEN = 20;
const UNTEN = 50;
const LINKS = 44;

export function Bruecke({ start, steps, end, unit, label }: {
  start: BrueckenPunkt;
  steps: BrueckenPunkt[];
  end: BrueckenPunkt;
  unit: string;
  label: string;
}) {
  const { box, breite } = useBreite(640, 300);
  const lauf = Array.from(cumsum([start.value, ...steps.map((s) => s.value)]));
  const geht = Math.abs(lauf[lauf.length - 1] - end.value) <= 0.15;
  const saeulen = [
    { label: start.label, von: 0, bis: start.value, summe: true },
    ...steps.map((s, i) => ({ label: s.label, von: lauf[i], bis: lauf[i + 1], summe: false })),
    { label: end.label, von: 0, bis: end.value, summe: true },
  ];
  const werte = saeulen.flatMap((s) => [s.von, s.bis]);
  const min = Math.min(0, ...werte);
  const max = Math.max(0, ...werte);
  const luft = (max - min || 1) * 0.1;
  const lo = min < 0 ? min - luft : 0;
  const hi = max > 0 ? max + luft : 0;
  const y = (v: number) => OBEN + ((hi - v) / (hi - lo)) * (HOEHE - OBEN - UNTEN);
  const band = (breite - LINKS - 8) / saeulen.length;
  const sw = Math.min(46, band * 0.66);

  return (
    <div ref={box} className="w-full min-w-0">
      {!geht && (
        <p className="mb-2 text-meta text-muted-foreground">Die Schritte ergeben zusammen nicht den Endwert — die Grafik ist unvollständig.</p>
      )}
      <svg viewBox={`0 0 ${breite} ${HOEHE}`} width={breite} height={HOEHE} role="img" aria-label={label}
        className="block h-auto max-w-full font-sans">
        {teilung(lo, hi).map((t) => (
          <g key={t}>
            <line x1={LINKS} x2={breite - 8} y1={y(t)} y2={y(t)} stroke="hsl(var(--border))" strokeWidth={1} />
            <text x={LINKS - 6} y={y(t) + 4} textAnchor="end" className="fill-muted-foreground text-[11px] tabular-nums">{deZahl(t, 0)}</text>
          </g>
        ))}
        {saeulen.map((s, i) => {
          const x = LINKS + band * i + (band - sw) / 2;
          const minus = s.summe ? s.bis < 0 : s.bis < s.von;
          const fill = s.summe ? `var(--hh-${minus ? "aus" : "ein"}-1)` : `var(--hh-${minus ? "aus" : "ein"}-3)`;
          const top = Math.min(y(s.von), y(s.bis));
          const h = Math.max(1.5, Math.abs(y(s.bis) - y(s.von)));
          const wert = s.summe ? deZahl(s.bis, 1) : mitVorzeichen(s.bis - s.von, 1);
          const zeilen = s.label.length > 14 && band < 90 ? umbrechen(s.label) : [s.label];
          return (
            <g key={`${s.label}-${i}`}>
              <rect x={x} y={top} width={sw} height={h} rx={2} fill={fill} className="gb-einblenden"
                style={{ animationDelay: `${i * 60}ms` }}>
                <title>{`${s.label}: ${wert} ${unit}`}</title>
              </rect>
              <text x={x + sw / 2} y={top - 4} textAnchor="middle" className="fill-foreground text-[11px] font-semibold tabular-nums">{wert}</text>
              {i < saeulen.length - 1 && (
                <line x1={x + sw} x2={x + band} y1={y(s.bis)} y2={y(s.bis)} stroke="hsl(var(--muted-foreground))" strokeDasharray="2 2" />
              )}
              {zeilen.map((z, k) => (
                <text key={k} x={x + sw / 2} y={HOEHE - UNTEN + 16 + k * 12} textAnchor="middle"
                  className={s.summe ? "fill-foreground text-[11px] font-medium" : "fill-muted-foreground text-[11px]"}>{z}</text>
              ))}
            </g>
          );
        })}
        <line x1={LINKS} x2={breite - 8} y1={y(0)} y2={y(0)} stroke="hsl(var(--foreground))" strokeWidth={1.2} />
      </svg>
    </div>
  );
}

/** Zwei Zeilen an einer Wortgrenze nahe der Mitte. */
function umbrechen(text: string): string[] {
  const woerter = text.split(" ");
  if (woerter.length < 2) return [text];
  let best = 1;
  for (let i = 1; i < woerter.length; i++) {
    const a = woerter.slice(0, i).join(" ").length;
    if (Math.abs(a - text.length / 2) < Math.abs(woerter.slice(0, best).join(" ").length - text.length / 2)) best = i;
  }
  return [woerter.slice(0, best).join(" "), woerter.slice(best).join(" ")];
}
