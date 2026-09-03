"use client";

// „Wie viel Geld ist auf dem Konto?" — der Block auf der Schulden-Seite vor
// dem Rahmen der Haushaltssatzung (§ 4, Höchstbetrag der Liquiditätskredite).
//
// Die Skizze ist die Form der letzten drei Jahre, ohne Achsen: Die große
// Zahl daneben ist die Auskunft, die Linie zeigt nur, wie stark der Stand im
// Jahr schwankt. Tief und Hoch der letzten zwölf Monate stehen als Zahlen
// dabei; die Dezember-Stände tragen den Vergleich über die Jahre.

import { Beleg } from "@/components/haushalt/source";
import { Fundstelle } from "@/components/haushalt/fundstelle";
import { deMio } from "@/lib/haushalt";
import { deMonat, letzteMonate, type LiquiditaetsDaten } from "@/lib/haushalt-liquiditaet";

function Skizze({ punkte }: { punkte: { month: string; amount: number }[] }) {
  if (punkte.length < 2) return null;
  const W = 280, H = 56, X0 = 2, X1 = W - 2, Y0 = 46, YTOP = 6;
  const werte = punkte.map((p) => p.amount / 1e6);
  const lo = Math.min(0, ...werte), hi = Math.max(...werte);
  const x = (i: number) => X0 + (i / (punkte.length - 1)) * (X1 - X0);
  const y = (v: number) => (hi === lo ? (Y0 + YTOP) / 2 : Y0 - ((v - lo) / (hi - lo)) * (Y0 - YTOP));
  const d = werte.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const iMin = werte.indexOf(Math.min(...werte)), iMax = werte.indexOf(hi);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="block w-full" role="img"
      aria-label={`Kontostand am Monatsende, ${deMonat(punkte[0].month)} bis ${deMonat(punkte[punkte.length - 1].month)}`}>
      {lo < 0 && <line x1={X0} y1={y(0)} x2={X1} y2={y(0)} strokeWidth={1} className="stroke-border" strokeDasharray="2 3" />}
      <path d={d} fill="none" strokeWidth={1.8} stroke="var(--hh-aus-0)" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={x(iMax)} cy={y(werte[iMax])} r={2.4} fill="var(--hh-aus-0)" />
      <circle cx={x(iMin)} cy={y(werte[iMin])} r={2.4} fill="var(--hh-aus-0)" />
      <text x={Math.min(x(iMax), W - 40)} y={Math.max(y(werte[iMax]) - 5, 8)} className="fill-muted-foreground" fontSize={8} fontFamily="ui-monospace, monospace">
        {deMio(werte[iMax])}
      </text>
      <text x={Math.min(x(iMin), W - 40)} y={Math.min(y(werte[iMin]) + 11, H - 1)} className="fill-muted-foreground" fontSize={8} fontFamily="ui-monospace, monospace">
        {deMio(werte[iMin])}
      </text>
    </svg>
  );
}

export function LiquiditaetsBlock({ daten, hoechstbetrag }: {
  daten: LiquiditaetsDaten | null;
  /** § 4 der Haushaltssatzung des jüngsten Jahrgangs, Euro — die Grenze fürs Minus. */
  hoechstbetrag?: number | null;
}) {
  if (!daten?.latest) return null;
  const lt = daten.latest;
  const h = lt.herkunft_id != null ? daten.provenance[String(lt.herkunft_id)] ?? null : null;
  const dez = daten.year_ends.slice(-4);
  const verlauf = letzteMonate(daten, 36);
  return (
    <section id="liquiditaet" className="scroll-mt-20 rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Wie viel Geld am Monatsende auf dem Konto ist<Beleg q="liquidity" h={h} />
        </p>
        <span className="font-mono text-[10px] uppercase text-muted-foreground">
          Monatlich seit {daten.coverage.from?.slice(0, 4)} · {daten.coverage.months} Monate
        </span>
      </div>
      <div className="mt-2 grid gap-4 sm:grid-cols-[minmax(0,1fr)_280px] sm:items-end">
        <div>
          <p className="font-display text-[26px] font-extrabold leading-none tracking-tight text-foreground">
            {deMio(lt.amount / 1e6)}&#8239;Mio.&nbsp;€
          </p>
          <p className="mt-1.5 max-w-[60ch] text-[12.5px] leading-relaxed text-muted-foreground">
            Stand Ende {deMonat(lt.month)}.
            {daten.last_12.min && daten.last_12.max && (
              <> In den letzten zwölf Monaten zwischen{" "}
                <span className="tabular-nums">{deMio(daten.last_12.min.amount / 1e6)}</span>
                {" "}({deMonat(daten.last_12.min.month)}) und{" "}
                <span className="tabular-nums">{deMio(daten.last_12.max.amount / 1e6)}</span>
                {" "}({deMonat(daten.last_12.max.month)}) Mio.&nbsp;€.</>
            )}
          </p>
        </div>
        <Skizze punkte={verlauf} />
      </div>
      {dez.length > 1 && (
        <p className="mt-3 border-t border-dashed border-border pt-3 text-[12.5px] leading-relaxed text-foreground/85">
          <strong>Jeweils Ende Dezember:</strong>{" "}
          {dez.map((r, i) => (
            <span key={r.month}>{i > 0 && " · "}{r.year} <span className="tabular-nums">{deMio(r.amount / 1e6)}</span></span>
          ))}{" "}Mio.&nbsp;€
        </p>
      )}
      <p className="mt-2.5 max-w-[68ch] text-[12px] leading-relaxed text-muted-foreground">
        {daten.scope_note}
        {hoechstbetrag != null && hoechstbetrag > 0 && (
          <> Die Satzung des jüngsten Jahrgangs erlaubt Liquiditätskredite bis{" "}
            {deMio(hoechstbetrag / 1e6)}&#8239;Mio.&nbsp;€ — siehe den Rahmen darunter.</>
        )}
        {lt.revised_from != null && (
          <> Den Wert für {deMonat(lt.month)} hat die Verwaltung in einer späteren Grafik
            korrigiert (zuvor {deMio(lt.revised_from / 1e6)}&#8239;Mio.&nbsp;€).</>
        )}
      </p>
      <Fundstelle h={h} className="mt-3" />
    </section>
  );
}
