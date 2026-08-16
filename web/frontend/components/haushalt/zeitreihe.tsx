"use client";

// Zeitreihen-Modul (Design H-07): genau eine Aussage — die Schere zwischen
// Einnahmen und Ausgaben. Fehlende Jahre folgen der Lücken-Konvention:
// schraffierter Kasten, Linie BRICHT AB (gepunktete, halbtransparente
// Stummel), Jahr bleibt in Signal-Orange stehen, Wert = „?" — nie
// interpoliert. Die Nicht-Chart-Entsprechung ist die aufklappbare Tabelle.

import { useEffect, useRef, useState } from "react";
import { HaushaltDaten, deMio, fehlendeJahre, jahreSortiert, mio, summe } from "@/lib/haushalt";

// saldo aus den ROHWERTEN gerundet, nicht aus den gerundeten Mio. — sonst
// driftet er um 0,1 (693,9 − 728,2 = −34,3, tatsächlich sind es −34,2).
type Punkt = { jahr: number; ein: number; aus: number; saldo: number };

const W = 660, H = 272, X0 = 46, X1 = 620, Y0 = 236, PAD = 26;

export function Zeitreihe({ daten }: { daten: HaushaltDaten }) {
  const [tabelleOffen, setTabelleOffen] = useState(false);
  // Auf schmalen Bildschirmen skaliert das SVG die Schrift mit herunter, bis
  // die Achsen unlesbar sind (Tim, 16.08.). Dort dieselbe Grafik mit weniger
  // Beschriftungen und größerer Schrift — nicht dieselbe, nur kleiner.
  const box = useRef<HTMLDivElement>(null);
  const [schmal, setSchmal] = useState(false);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const pruefe = () => setSchmal(el.clientWidth < 520);
    pruefe();
    const ro = new ResizeObserver(pruefe);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const fs = schmal ? { achse: 15, jahr: 16, saldo: 15, legende: 15 } : { achse: 9.5, jahr: 10, saldo: 10, legende: 11 };

  const jahre = jahreSortiert(daten);
  const punkte: Punkt[] = jahre
    .map((jahr) => {
      const s = summe(daten.jahre[String(jahr)] ?? []);
      const ein = mio(s?.ertraege), aus = mio(s?.aufwendungen);
      const saldo = mio((s?.ertraege ?? 0) - (s?.aufwendungen ?? 0));
      return ein != null && aus != null && saldo != null ? { jahr, ein, aus, saldo } : null;
    })
    .filter((p): p is Punkt => p !== null);
  if (punkte.length < 2) return null;

  const luecken = fehlendeJahre(punkte.map((p) => p.jahr));
  const alleJahre: number[] = [];
  for (let y = punkte[0].jahr; y <= punkte[punkte.length - 1].jahr; y++) alleJahre.push(y);

  // Skala: runde 100er-Gitterlinien um den Wertebereich.
  const werte = punkte.flatMap((p) => [p.ein, p.aus]);
  const lo = Math.floor(Math.min(...werte) / 100) * 100;
  const hi = Math.ceil(Math.max(...werte) / 100) * 100;
  const x = (jahr: number) =>
    X0 + 8 + ((jahr - alleJahre[0]) / Math.max(alleJahre.length - 1, 1)) * (X1 - X0 - 40);
  const y = (v: number) => Y0 - PAD - ((v - lo) / (hi - lo)) * (Y0 - 2 * PAD - 14);

  const gitter: number[] = [];
  for (let v = lo; v <= hi; v += 100) gitter.push(v);

  // Liniensegmente: an jeder Lücke neu ansetzen (Konvention: kein Durchziehen).
  const segmente: Punkt[][] = [];
  let akt: Punkt[] = [];
  for (const jahr of alleJahre) {
    const p = punkte.find((q) => q.jahr === jahr);
    if (p) akt.push(p);
    else if (akt.length) { segmente.push(akt); akt = []; }
  }
  if (akt.length) segmente.push(akt);

  const pfad = (seg: Punkt[], key: "ein" | "aus") =>
    seg.map((p, i) => `${i ? "L" : "M"}${x(p.jahr)} ${y(p[key])}`).join(" ");

  const letzter = punkte[punkte.length - 1];
  const groessteLuecke = punkte.reduce((best, p) => (p.saldo < best.saldo ? p : best), punkte[0]);

  return (
    <div ref={box}>
      <div className="mb-1.5 flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:justify-between sm:gap-3">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Einnahmen und Ausgaben · geplant
        </p>
        <span className="font-mono text-[10px] uppercase text-muted-foreground">
          {alleJahre[0]}–{alleJahre[alleJahre.length - 1]} · {punkte.length} von {alleJahre.length} Jahren
        </span>
      </div>
      {groessteLuecke.saldo < 0 && (
        <p className="mb-2.5 max-w-[70ch] text-sm leading-relaxed text-foreground/90">
          {punkte[0].ein >= punkte[0].aus ? "Anfangs plante die Stadt mit einem kleinen Plus. " : ""}
          Inzwischen liegen die Ausgaben über den Einnahmen —{" "}
          <strong>{groessteLuecke.jahr} war die Lücke mit {deMio(-groessteLuecke.saldo)}&#8239;Mio.&nbsp;€ am größten</strong>.
        </p>
      )}

      <svg viewBox={`0 0 ${W} ${H}`} className="block w-full" role="img"
        aria-label={`Geplante Einnahmen und Ausgaben ${alleJahre[0]} bis ${alleJahre[alleJahre.length - 1]} in Mio. Euro. ${
          punkte.map((p) => `${p.jahr}: ${deMio(p.ein)} zu ${deMio(p.aus)}`).join(", ")}${
          luecken.length ? `. ${luecken.join(", ")}: keine Daten` : ""}`}>
        {gitter.map((v) => (
          <g key={v} className="text-muted-foreground">
            <line x1={X0} y1={y(v)} x2={X1} y2={y(v)} className="stroke-border/60" />
            <text x={X0 - 6} y={y(v) + 3} textAnchor="end" fontSize={fs.achse} className="fill-muted-foreground font-mono">{v}</text>
          </g>
        ))}

        {/* Lücken-Kästen */}
        {luecken.map((jahr) => {
          const xl = x(jahr) - 42, xr = x(jahr) + 42;
          return (
            <g key={jahr}>
              <foreignObject x={xl} y={14} width={xr - xl} height={Y0 - 14}>
                <div className="hh-schraffur h-full w-full opacity-60" />
              </foreignObject>
              <rect x={xl} y={14} width={xr - xl} height={Y0 - 14} fill="none"
                strokeDasharray="4 3" className="stroke-signal" />
              <text x={x(jahr)} y={(Y0 + 14) / 2} textAnchor="middle" fontSize={10} className="fill-signal font-mono">DATEN</text>
              <text x={x(jahr)} y={(Y0 + 14) / 2 + 13} textAnchor="middle" fontSize={10} className="fill-signal font-mono">FEHLEN</text>
            </g>
          );
        })}

        {/* Linien: Ausgaben (Schiefer) über Einnahmen (Hafenblau) */}
        {segmente.map((seg, i) => (
          <g key={i} strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" fill="none">
            <path d={pfad(seg, "aus")} style={{ stroke: "var(--hh-aus-0)" }} />
            <path d={pfad(seg, "ein")} style={{ stroke: "var(--hh-ein-0)" }} />
          </g>
        ))}
        {/* Gepunktete Stummel zu beiden Seiten jeder Lücke */}
        {luecken.map((jahr) => {
          const vor = punkte.filter((p) => p.jahr < jahr).pop();
          const nach = punkte.find((p) => p.jahr > jahr);
          return (
            <g key={`st-${jahr}`} strokeWidth={2.5} strokeDasharray="1 5" strokeLinecap="round" opacity={0.45} fill="none">
              {vor && <>
                <path d={`M${x(vor.jahr)} ${y(vor.aus)} L${x(jahr) - 42} ${y(vor.aus)}`} style={{ stroke: "var(--hh-aus-0)" }} />
                <path d={`M${x(vor.jahr)} ${y(vor.ein)} L${x(jahr) - 42} ${y(vor.ein)}`} style={{ stroke: "var(--hh-ein-0)" }} />
              </>}
              {nach && <>
                <path d={`M${x(jahr) + 42} ${y(nach.aus)} L${x(nach.jahr)} ${y(nach.aus)}`} style={{ stroke: "var(--hh-aus-0)" }} />
                <path d={`M${x(jahr) + 42} ${y(nach.ein)} L${x(nach.jahr)} ${y(nach.ein)}`} style={{ stroke: "var(--hh-ein-0)" }} />
              </>}
            </g>
          );
        })}

        {/* Punkte; letztes Jahr gefüllt */}
        {punkte.map((p) => (
          <g key={p.jahr}>
            <circle cx={x(p.jahr)} cy={y(p.ein)} r={p.jahr === letzter.jahr ? 5 : 3.5}
              className={p.jahr === letzter.jahr ? "" : "fill-card"} strokeWidth={2}
              style={{ stroke: "var(--hh-ein-0)", fill: p.jahr === letzter.jahr ? "var(--hh-ein-0)" : undefined }} />
            <circle cx={x(p.jahr)} cy={y(p.aus)} r={p.jahr === letzter.jahr ? 5 : 3.5}
              className={p.jahr === letzter.jahr ? "" : "fill-card"} strokeWidth={2}
              style={{ stroke: "var(--hh-aus-0)", fill: p.jahr === letzter.jahr ? "var(--hh-aus-0)" : undefined }} />
          </g>
        ))}
        <text x={x(letzter.jahr) + 12} y={y(letzter.ein) + 4} fontSize={fs.legende} fontWeight={600} style={{ fill: "var(--hh-ein-0)" }}>ein</text>
        <text x={x(letzter.jahr) + 12} y={y(letzter.aus) + 4} fontSize={fs.legende} fontWeight={600} style={{ fill: "var(--hh-aus-0)" }}>aus</text>

        {/* Jahres-Achse + Saldo-Zeile (die Ergebniswerte direkt an der Achse) */}
        {alleJahre.map((jahr, idx) => {
          const p = punkte.find((q) => q.jahr === jahr);
          const saldo = p?.saldo ?? null;
          const fehlt = !p;
          // Schmal: nur jedes zweite Jahr plus das letzte — sonst kleben die
          // Beschriftungen aneinander, sobald die Schrift lesbar groß ist.
          const zeigen = !schmal || idx % 2 === 0 || idx === alleJahre.length - 1;
          if (!zeigen) return null;
          return (
            <g key={`ax-${jahr}`} textAnchor="middle">
              <text x={x(jahr)} y={252} fontSize={fs.jahr}
                className={fehlt ? "fill-signal font-mono" : jahr === letzter.jahr ? "fill-foreground font-mono" : "fill-muted-foreground font-mono"}>
                {jahr}
              </text>
              <text x={x(jahr)} y={schmal ? 269 : 266} fontSize={fs.saldo}
                className={fehlt || (saldo ?? 0) < 0 ? "fill-signal" : "fill-muted-foreground"}
                fontWeight={jahr === letzter.jahr ? 600 : 400}>
                {fehlt ? "?" : `${(saldo ?? 0) > 0 ? "+" : ""}${deMio(saldo)}`}
              </text>
            </g>
          );
        })}
      </svg>

      <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-border/60 pt-2.5">
        <span className="inline-flex items-center gap-1.5 text-[11.5px] text-foreground/80">
          <span className="h-[2.5px] w-[18px] rounded" style={{ background: "var(--hh-ein-0)" }} />Einnahmen
        </span>
        <span className="inline-flex items-center gap-1.5 text-[11.5px] text-foreground/80">
          <span className="h-[2.5px] w-[18px] rounded" style={{ background: "var(--hh-aus-0)" }} />Ausgaben
        </span>
        {luecken.length > 0 && (
          <span className="inline-flex items-center gap-1.5 text-[11.5px] text-foreground/80">
            <span className="hh-schraffur h-3 w-[18px] rounded-[2px] border border-dashed border-signal" />Datenlücke
          </span>
        )}
        <button type="button" onClick={() => setTabelleOffen((o) => !o)}
          className="ml-auto text-[12px] font-semibold text-primary">
          {tabelleOffen ? "Zahlen ausblenden" : "Zahlen anzeigen"}
        </button>
      </div>

      {tabelleOffen && (
        <div className="mt-2.5 grid grid-cols-[auto_1fr_1fr_1fr] text-[11.5px] tabular-nums">
          <span className="py-1 font-mono text-[10px] uppercase tracking-[0.09em] text-muted-foreground">Jahr</span>
          <span className="py-1 text-right font-mono text-[10px] uppercase tracking-[0.09em] text-muted-foreground">Ein</span>
          <span className="py-1 text-right font-mono text-[10px] uppercase tracking-[0.09em] text-muted-foreground">Aus</span>
          <span className="py-1 text-right font-mono text-[10px] uppercase tracking-[0.09em] text-muted-foreground">Ergebnis</span>
          {alleJahre.map((jahr) => {
            const p = punkte.find((q) => q.jahr === jahr);
            const saldo = p?.saldo ?? null;
            return (
              <div key={jahr} className="contents">
                <span className={`border-t border-border/60 py-1 ${p ? "" : "text-signal"}`}>{jahr}</span>
                <span className="border-t border-border/60 py-1 text-right" title={p ? undefined : "nicht auslesbar"}>{p ? deMio(p.ein) : "—"}</span>
                <span className="border-t border-border/60 py-1 text-right">{p ? deMio(p.aus) : "—"}</span>
                <span className={`border-t border-border/60 py-1 text-right ${(saldo ?? 0) < 0 ? "text-signal" : "text-[#15803d] dark:text-[#4ade80]"}`}>
                  {p ? `${(saldo ?? 0) > 0 ? "+" : ""}${deMio(saldo)}` : "—"}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
