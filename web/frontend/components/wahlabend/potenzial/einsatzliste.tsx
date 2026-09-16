"use client";

// Die Einsatzliste: die Stadtbezirke in der Reihenfolge, in der sie sich
// lohnen — netto je Regler-Stand, mit den Bezirken dahinter und einem Haken
// „übernommen" je Bezirk. Die Haken liegen im Browser (localStorage): Die
// Seite hat kein Konto, und wer sie sieht, hat den Link. Wer die Liste ans
// Team gibt, druckt sie — alles außer ihr ist im Druck ausgeblendet.

import { useEffect, useMemo, useState } from "react";
import { ChevronDown, Printer } from "lucide-react";
import { KICKER } from "@/components/wahlabend/bausteine";
import { STRATEGIE, STRATEGIE_FARBE, uebernommenLesen, uebernommenSchreiben, type PotenzialBezirk, type PotenzialBuendel } from "@/lib/potenzial";
import { cn } from "@/lib/utils";
import { prozent, zahl } from "@/lib/wahlabend";

function netto(n: number): string {
  const r = Math.round(n);
  return `${r >= 0 ? "+" : "−"}${zahl(Math.abs(r))}`;
}

export function Einsatzliste({ buendel, bezirke }: { buendel: PotenzialBuendel[]; bezirke: PotenzialBezirk[] }) {
  const [offen, setOffen] = useState<Set<string>>(new Set());
  const [haken, setHaken] = useState<Set<number>>(new Set());
  const [alleOffen, setAlleOffen] = useState(false);

  // Erst nach dem Einhängen lesen — der Server kennt den Speicher nicht,
  // und ein Haken im ersten Bild wäre ein Hydration-Fehler.
  useEffect(() => {
    if (typeof window !== "undefined") setHaken(uebernommenLesen(window.localStorage));
  }, []);

  const nachName = useMemo(() => {
    const m = new Map<string, PotenzialBezirk[]>();
    for (const z of bezirke) {
      const l = m.get(z.district_name) ?? [];
      l.push(z);
      m.set(z.district_name, l);
    }
    for (const l of m.values()) l.sort((a, b) => (b.yield_per_1000 ?? 0) - (a.yield_per_1000 ?? 0));
    return m;
  }, [bezirke]);

  const setzen = (nr: number, an: boolean) => {
    setHaken((alt) => {
      const neu = new Set(alt);
      if (an) neu.add(nr); else neu.delete(nr);
      if (typeof window !== "undefined") uebernommenSchreiben(window.localStorage, neu);
      return neu;
    });
  };
  const umschalten = (name: string) => {
    setOffen((alt) => {
      const neu = new Set(alt);
      if (neu.has(name)) neu.delete(name); else neu.add(name);
      return neu;
    });
  };
  const drucken = () => {
    setAlleOffen(true);
    setTimeout(() => window.print(), 50);
  };

  const gesamt = bezirke.length;
  return (
    <section data-testid="einsatzliste" className="mt-10">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className={KICKER}>Einsatzliste</div>
          <h2 className="mt-1 font-display text-[22px] font-bold tracking-tight">Die Stadtbezirke, nach Ertrag</h2>
          <p className="mt-1 max-w-2xl text-[13.5px] leading-relaxed text-muted-foreground print:hidden">
            Was ein Team an einem Nachmittag schafft, ist ein Stadtbezirk — deshalb sind die Bezirke so gebündelt. Netto
            heißt: so viele Stimmen Vorsprung gewinnt Rohr dort mit den Reglern von oben. Der Haken merkt sich, was
            vergeben ist — in diesem Browser.
          </p>
        </div>
        <div className="flex items-center gap-2 print:hidden">
          <span className="font-mono text-[12px] tabular-nums text-muted-foreground">{haken.size} von {gesamt} übernommen</span>
          <button type="button" onClick={() => setAlleOffen((a) => !a)}
            className="inline-flex min-h-9 items-center rounded-full border border-border bg-card px-3.5 text-[13px] font-medium hover:bg-primary/5">
            {alleOffen ? "Alle zuklappen" : "Alle aufklappen"}
          </button>
          <button type="button" onClick={drucken}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-full border border-border bg-card px-3.5 text-[13px] font-medium hover:bg-primary/5">
            <Printer className="h-3.5 w-3.5" aria-hidden />
            Drucken
          </button>
        </div>
      </div>

      <ol className="mt-4 space-y-2">
        {buendel.map((b, i) => {
          const zeilen = nachName.get(b.district_name) ?? [];
          const ist = alleOffen || offen.has(b.district_name);
          const erledigt = zeilen.filter((z) => haken.has(z.number)).length;
          return (
            <li key={b.district_name} data-buendel={b.district_name} className="rounded-2xl border border-border bg-card">
              <button
                type="button"
                onClick={() => umschalten(b.district_name)}
                aria-expanded={ist}
                className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-primary/5 print:hover:bg-transparent"
              >
                <span className="w-6 flex-none font-mono text-[12px] text-muted-foreground">{i + 1}.</span>
                <span className="min-w-0 flex-1">
                  <span className="block text-[15px] font-semibold">{b.district_name}</span>
                  <span className="block text-[12px] text-muted-foreground">
                    {b.districts} Bezirke · {zahl(b.eligible)} Wahlberechtigte · Rohr {prozent(b.rohr_pct_of_two, 0)} · {zahl(b.non_voters)} nicht gekommen
                  </span>
                </span>
                <span className="flex-none text-right">
                  <span className="block font-mono text-[15px] font-semibold tabular-nums">{netto(b.net_total)}</span>
                  <span className={KICKER}>netto</span>
                </span>
                <span className="hidden flex-none text-right sm:block">
                  <span className="block font-mono text-[15px] font-semibold tabular-nums">{b.yield_per_1000?.toFixed(0) ?? "–"}</span>
                  <span className={KICKER}>je 1.000</span>
                </span>
                <span className="hidden w-14 flex-none text-right font-mono text-[12px] tabular-nums text-muted-foreground sm:block print:hidden">
                  {erledigt}/{zeilen.length}
                </span>
                <ChevronDown className={cn("h-4 w-4 flex-none text-muted-foreground transition-transform print:hidden", ist && "rotate-180")} aria-hidden />
              </button>
              {ist ? (
                <ul className="border-t border-border">
                  {zeilen.map((z) => {
                    const an = haken.has(z.number);
                    return (
                      <li key={z.number} className={cn("flex items-center gap-3 px-4 py-2 text-[13px]", an && "opacity-60")}>
                        <input
                          type="checkbox"
                          checked={an}
                          onChange={(e) => setzen(z.number, e.target.checked)}
                          aria-label={`Bezirk ${z.number} übernommen`}
                          className="h-4 w-4 flex-none accent-[hsl(var(--primary))]"
                        />
                        <span className="w-9 flex-none font-mono text-[12px] text-muted-foreground">{z.number}</span>
                        <span className={cn("min-w-0 flex-1 truncate", an && "line-through")}>{z.name}</span>
                        <span className="hidden flex-none rounded-full px-2 py-0.5 text-[11px] font-medium sm:inline"
                          style={{ background: STRATEGIE_FARBE[z.strategy] ?? "hsl(var(--muted))" }}>
                          {STRATEGIE[z.strategy]?.title ?? z.strategy}
                        </span>
                        <span className="w-14 flex-none text-right font-mono text-[12px] tabular-nums">{netto(z.net_total)}</span>
                        <span className="hidden w-10 flex-none text-right font-mono text-[12px] tabular-nums sm:block">{z.yield_per_1000?.toFixed(0) ?? "–"}</span>
                      </li>
                    );
                  })}
                </ul>
              ) : null}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
