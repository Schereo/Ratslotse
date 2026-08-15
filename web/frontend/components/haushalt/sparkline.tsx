"use client";

// Sparkline-Format (Design H-07, drei Zustände): vollständig / mit Lücke /
// ohne Reihe. Lücken als gestricheltes Kästchen + Punktlinie — dieselbe
// Konvention wie im großen Zeitreihen-Modul, nur 88×26.

import { fehlendeJahre } from "@/lib/haushalt";

export function Sparkline({ reihe, className }: {
  reihe: { jahr: number; wert: number }[];
  className?: string;
}) {
  if (reihe.length < 2) {
    return (
      <svg width="88" height="26" viewBox="0 0 88 26" className={className} aria-label="Zeitreihe folgt">
        <path d="M4 18 L26 16 L48 13" fill="none" strokeWidth={1.6} strokeDasharray="2 2" className="stroke-border" />
        <text x="54" y="17" fontSize={9} className="fill-muted-foreground font-mono">[folgt]</text>
      </svg>
    );
  }
  return <SparkSvg reihe={reihe} className={className} />;
}

/** Sparkline MIT Ankern (Tims Einwand 15.08.: ohne Achsen liest sich die
 *  Linie als Deko). Unter der Linie stehen Start- und Endjahr plus das
 *  Delta über den Zeitraum — die ehrliche Mindest-Beschriftung, ohne die
 *  Karte mit einem vollen Diagramm zu erschlagen. */
export function TrendMini({ reihe, className }: {
  reihe: { jahr: number; wert: number }[];
  className?: string;
}) {
  if (reihe.length < 2) return <Sparkline reihe={reihe} className={className} />;
  const delta = Math.round((reihe[reihe.length - 1].wert - reihe[0].wert) * 10) / 10;
  const deltaText = `${delta > 0 ? "+" : ""}${delta.toLocaleString("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}`;
  return (
    <div className={className}>
      <SparkSvg reihe={reihe} />
      <div className="mt-0.5 flex w-[88px] items-baseline justify-between font-mono text-[8.5px] leading-none text-muted-foreground">
        <span>’{String(reihe[0].jahr).slice(2)}</span>
        <span className="font-medium">{deltaText}</span>
        <span>’{String(reihe[reihe.length - 1].jahr).slice(2)}</span>
      </div>
    </div>
  );
}

function SparkSvg({ reihe, className }: {
  reihe: { jahr: number; wert: number }[];
  className?: string;
}) {

  const jahre = reihe.map((r) => r.jahr);
  const luecken = fehlendeJahre(jahre);
  const alle: number[] = [];
  for (let y = jahre[0]; y <= jahre[jahre.length - 1]; y++) alle.push(y);

  const werte = reihe.map((r) => r.wert);
  const lo = Math.min(...werte), hi = Math.max(...werte);
  const x = (jahr: number) => 4 + ((jahr - alle[0]) / Math.max(alle.length - 1, 1)) * 80;
  const y = (v: number) => hi === lo ? 13 : 21 - ((v - lo) / (hi - lo)) * 16;

  // Segmente an Lücken trennen (nie durchziehen).
  const segmente: { jahr: number; wert: number }[][] = [];
  let akt: { jahr: number; wert: number }[] = [];
  for (const jahr of alle) {
    const p = reihe.find((r) => r.jahr === jahr);
    if (p) akt.push(p);
    else if (akt.length) { segmente.push(akt); akt = []; }
  }
  if (akt.length) segmente.push(akt);
  const letzt = reihe[reihe.length - 1];

  return (
    <svg width="88" height="26" viewBox="0 0 88 26" className={className}
      aria-label={`Verlauf ${alle[0]}–${alle[alle.length - 1]}${luecken.length ? `, ${luecken.join(", ")}: keine Daten` : ""}`}>
      {luecken.map((jahr) => (
        <rect key={jahr} x={x(jahr) - 5} y={2} width={10} height={22} fill="none"
          strokeWidth={0.9} strokeDasharray="2 2" className="stroke-signal" />
      ))}
      {segmente.map((seg, i) => (
        <path key={i} d={seg.map((p, k) => `${k ? "L" : "M"}${x(p.jahr)} ${y(p.wert)}`).join(" ")}
          fill="none" strokeWidth={1.6} strokeLinecap="round" className="stroke-muted-foreground" />
      ))}
      {luecken.map((jahr) => {
        const vor = reihe.filter((p) => p.jahr < jahr).pop();
        const nach = reihe.find((p) => p.jahr > jahr);
        return (
          <g key={`s-${jahr}`} strokeWidth={1.6} strokeDasharray="1 3" opacity={0.7} fill="none" className="stroke-signal">
            {vor && <path d={`M${x(vor.jahr)} ${y(vor.wert)} L${x(jahr) - 5} ${y(vor.wert)}`} />}
            {nach && <path d={`M${x(jahr) + 5} ${y(nach.wert)} L${x(nach.jahr)} ${y(nach.wert)}`} />}
          </g>
        );
      })}
      <circle cx={x(letzt.jahr)} cy={y(letzt.wert)} r={2.6} style={{ fill: "var(--hh-ein-0)" }} />
    </svg>
  );
}
