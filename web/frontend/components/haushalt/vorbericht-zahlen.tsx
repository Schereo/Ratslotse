"use client";

// Zahlen aus dem Vorbericht des Haushaltsplans (council/vorbericht_zahlen.py)
// — eine Karte für drei Seiten: je Steuerart auf /haushalt/steuer, der
// Personalaufwand samt Rückstellungen auf /haushalt/personal, das
// Jahresergebnis auf /haushalt/plan-ist.
//
// Was sonst nirgends steht, ist die PROGNOSE der Kämmerei für das laufende
// Jahr und die Finanzplanung je Steuerart. Die Spalten tragen deshalb ihre
// Art im Kopf („Plan 2025", „Prognose 2025", „Finanzplanung 2027"), nie nur
// das Jahr — ein nacktes „2025" wäre bei zwei Werten für dasselbe Jahr eine
// Einladung, den falschen zu lesen.
//
// Ein älterer Plan ist wählbar: Was die Kämmerei vor zwei Jahren für heute
// erwartet hat, ist dieselbe Frage wie „geplant gegen geworden".

import { useMemo, useState } from "react";
import { useFetch } from "@/lib/use-fetch";
import type { ApiAntwort } from "@/lib/vertrag";
import { deMio } from "@/lib/haushalt";
import { deZahl } from "@/components/grafik/format";
import { Beleg } from "@/components/haushalt/source";
import { BetragZelle, TextZelle, ZahlenTabelle } from "@/components/haushalt/zahlen-tabelle";
import { cn } from "@/lib/utils";

type Antwort = ApiAntwort<"/council/budget/preface-figures">;

const ART: Record<string, string> = {
  // „Entwurf", nicht „Ansatz": Der Vorbericht hängt am Verwaltungsentwurf,
  // der Rat ändert ihn noch (für 2026 von −89,3 auf −71,1 Mio. € im
  // Ergebnis). „Ansatz 2026" stand neben dem beschlossenen Plan der Startseite
  // wie dessen Zahl (Prüfung 24.09.2026).
  actual: "Ist", prior_budget: "Plan", forecast: "Prognose", budget: "Entwurf", financial_plan: "Finanzplanung",
};
const REIHENFOLGE = ["actual", "prior_budget", "forecast", "budget", "financial_plan"];

export function VorberichtZahlen({ reihen, titel, kicker, genau = false, children }: {
  /** Reihen-Schlüssel mit Zeilenbeschriftung, in Anzeigefolge. */
  reihen: { key: string; label: string }[];
  titel: string;
  kicker: string;
  /** Beträge auf den Euro statt in Mio. € (die Personaltabelle ist centgenau). */
  genau?: boolean;
  children?: React.ReactNode;
}) {
  const url = `/council/budget/preface-figures?${reihen.map((r) => `series=${r.key}`).join("&")}`;
  const { data } = useFetch<Antwort>(url);
  const [gewaehlt, setGewaehlt] = useState<number | null>(null);
  const plan = data?.plans.find((p) => p.plan_budget_year === gewaehlt) ?? data?.plans[0];
  const spalten = useMemo(() => {
    const s = new Map<string, { year: number; variant: string }>();
    for (const f of plan?.figures ?? []) s.set(`${f.year}-${f.variant}`, { year: f.year, variant: f.variant });
    const alle = [...s.values()].sort((a, b) => a.year - b.year
      || REIHENFOLGE.indexOf(a.variant) - REIHENFOLGE.indexOf(b.variant));
    // Höchstens drei Ist-Jahre: Das Ergebnis-Diagramm führt sechs, und elf
    // Spalten passen in keine Karte (gemessen: „Finanzplanung 2029" fiel bei
    // 1.440 px aus dem Rahmen). Die älteren Ist-Jahre stehen auf den Seiten,
    // die diese Karte tragen, ohnehin schon.
    const ist = alle.filter((x) => x.variant === "actual");
    const weg = new Set(ist.slice(0, Math.max(0, ist.length - 3)));
    return alle.filter((x) => !weg.has(x));
  }, [plan]);
  if (!data || !plan || spalten.length === 0) return null;
  const wert = (key: string, s: { year: number; variant: string }) =>
    plan.figures.find((f) => f.series === key && f.year === s.year && f.variant === s.variant)?.amount;
  const zeige = (v: number | undefined) =>
    v == null ? "—" : genau ? `${deZahl(v, 0)} €` : `${deMio(v / 1e6)} Mio. €`;
  const zeilen = reihen.filter((r) => plan.figures.some((f) => f.series === r.key));

  return (
    <section className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 max-w-[70ch]">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            {kicker} · Vorbericht zum Haushaltsplan {plan.plan_budget_year}
          </p>
          <h2 className="mt-1 text-[17px] font-semibold leading-snug text-foreground">
            {titel}<Beleg q="budget_preface" />
          </h2>
        </div>
        {data.plans.length > 1 && (
          <div role="group" aria-label="Haushaltsplan wählen" className="flex flex-wrap gap-1">
            {[...data.plans].reverse().map((p) => (
              <button key={p.plan_budget_year} type="button" aria-pressed={p === plan}
                onClick={() => setGewaehlt(p.plan_budget_year)}
                className={cn(
                  "min-h-[28px] rounded-full border px-2.5 font-mono text-[11px] tabular-nums",
                  p === plan ? "border-primary bg-primary/10 text-primary"
                    : "border-border text-muted-foreground hover:border-primary/40")}>
                {p.plan_budget_year}
              </button>
            ))}
          </div>
        )}
      </div>
      {children}
      <ZahlenTabelle spalten={[{ title: "" }, ...spalten.map((s) => ({
        title: `${ART[s.variant] ?? s.variant} ${s.year}`, zahl: true }))]}>
        {zeilen.map((r) => (
          <tr key={r.key}>
            <TextZelle><span className="font-semibold text-foreground">{r.label}</span></TextZelle>
            {spalten.map((s) => {
              const v = wert(r.key, s);
              return (
                <BetragZelle key={`${s.year}-${s.variant}`} euro={v ?? null}
                  label={`${ART[s.variant]} ${s.year}`} text={zeige(v)}
                  className={cn("text-foreground dark:text-foreground",
                    s.variant === "forecast" && "font-semibold",
                    (s.variant === "financial_plan" || s.variant === "prior_budget")
                      && "text-muted-foreground dark:text-muted-foreground")} />
              );
            })}
          </tr>
        ))}
      </ZahlenTabelle>
      <p className="max-w-[76ch] text-[11.5px] leading-relaxed text-muted-foreground">
        Aus dem Vorbericht, den die Verwaltung mit dem Entwurf einbringt: „Plan“ ist der Ansatz des
        laufenden Jahres, „Prognose“ die Erwartung der Kämmerei zum Zeitpunkt des Entwurfs,
        „Entwurf“ das kommende Jahr, wie die Verwaltung es einbringt — der Rat ändert es noch —,
        „Finanzplanung“ die Jahre danach. „Ist“ ist der Stand bei Drucklegung und kann vom
        späteren Jahresabschluss um einige Hunderttausend Euro abweichen. {genau ? "" : "Die Diagramme des Vorberichts runden auf 0,1 Mio. €."}
      </p>
    </section>
  );
}
