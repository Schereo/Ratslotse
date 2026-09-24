"use client";

// „Was aus den Investitionen im Jahr wird" — Karte im Überblick von
// /haushalt/bereich (Plan Haushalt-Datenquellen, PR 8b).
//
// Quelle: die Budgetberichte an die Fachausschüsse (council/budgetberichte.py),
// viermal im Jahr, je Investitionsmaßnahme Ansatz und Prognose zum
// Jahresende, darunter die Begründung der Verwaltung im Wortlaut. Eingelesen
// sind Jugend und Familie (THH 11) und Schule und Bildung (THH 12); für die
// übrigen Bereiche bleibt die Karte weg.
//
// KEINE BEWERTUNGSFARBE: Eine Prognose über dem Ansatz ist meist Geld aus dem
// Vorjahr, das jetzt abfließt, keine Überschreitung — die Karte sagt das im
// Satz unter der Tabelle, statt es rot zu färben.

import { useMemo, useState } from "react";
import { useFetch } from "@/lib/use-fetch";
import type { ApiAntwort } from "@/lib/vertrag";
import { deMio } from "@/lib/haushalt";
import { deZahl } from "@/components/grafik/format";
import { Beleg } from "@/components/haushalt/source";
import { BetragZelle, TextZelle, ZahlenTabelle } from "@/components/haushalt/zahlen-tabelle";
import { cn } from "@/lib/utils";

type Antwort = ApiAntwort<"/council/budget/measures">;

const euro = (v: number | null | undefined) => (v == null ? "—" : `${deZahl(v, 0)} €`);
const datum = (iso: string) => `${iso.slice(8, 10)}.${iso.slice(5, 7)}.${iso.slice(0, 4)}`;

export function BudgetberichtBereich({ subBudget }: { subBudget: number }) {
  const [asOf, setAsOf] = useState<string | null>(null);
  const { data } = useFetch<Antwort>(
    `/council/budget/measures?sub_budget=${subBudget}${asOf ? `&as_of=${asOf}` : ""}`);
  // Je Haushaltsjahr der jüngste Bericht — vier Stichtage im Jahr wären als
  // Auswahl zu viel; der jüngste ist der mit der besten Prognose.
  const jahre = useMemo(() => {
    const m = new Map<number, string>();
    for (const r of data?.reports ?? []) if (!m.has(r.budget_year)) m.set(r.budget_year, r.as_of);
    return [...m.entries()].sort((a, b) => a[0] - b[0]);
  }, [data]);
  const [offen, setOffen] = useState<Set<number>>(new Set());
  if (!data || !data.as_of || data.measures.length === 0) return null;
  const bericht = data.reports.find((r) => r.as_of === data.as_of);
  const aus = data.measures.filter((m) => m.kind === "A");
  const ein = data.measures.filter((m) => m.kind === "E");

  return (
    <section className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 max-w-[70ch]">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Budgetbericht an den Fachausschuss · Stand {datum(data.as_of)}
          </p>
          <h2 className="mt-1 text-[17px] font-semibold leading-snug text-foreground">
            Was aus den Investitionen {bericht?.budget_year} wird<Beleg q="budget_measures" />
          </h2>
          {bericht && bericht.planned != null && bericht.forecast != null && (
            <p className="mt-2 text-[13px] leading-relaxed text-foreground/90">
              Geplant waren Auszahlungen von {deMio(bericht.planned / 1e6)}&#8239;Mio.&nbsp;€; die
              Verwaltung erwartet zum Stand {datum(data.as_of)} bis Jahresende{" "}
              {deMio(bericht.forecast / 1e6)}&#8239;Mio.&nbsp;€, verteilt auf {aus.length}{" "}
              {aus.length === 1 ? "Maßnahme" : "Maßnahmen"}.
            </p>
          )}
        </div>
        {jahre.length > 1 && (
          <div role="group" aria-label="Haushaltsjahr wählen" className="flex flex-wrap gap-1">
            {jahre.map(([j, stichtag]) => (
              <button key={j} type="button" aria-pressed={bericht?.budget_year === j}
                onClick={() => { setAsOf(stichtag); setOffen(new Set()); }}
                className={cn(
                  "min-h-[28px] rounded-full border px-2.5 font-mono text-[11px] tabular-nums",
                  bericht?.budget_year === j ? "border-primary bg-primary/10 text-primary"
                    : "border-border text-muted-foreground hover:border-primary/40")}>
                {j}
              </button>
            ))}
          </div>
        )}
      </div>

      <ZahlenTabelle spalten={[{ title: "Maßnahme" }, { title: "Ansatz", zahl: true },
        { title: "Prognose zum Jahresende", zahl: true }]}>
        {[...aus, ...ein].map((m) => {
          const lang = (m.note ?? "").length > 220;
          const auf = offen.has(m.seq);
          return (
            <tr key={m.seq}>
              <TextZelle>
                <span className="font-semibold text-foreground">{m.name}</span>
                {m.kind === "E" && (
                  <span className="ml-2 font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">Einzahlung</span>
                )}
                {m.measure_no && (
                  <span className="mt-0.5 block font-mono text-[10px] text-muted-foreground">
                    {m.measure_no}{m.measure_no_to ? ` bis ${m.measure_no_to}` : ""}
                  </span>
                )}
                {m.note && (
                  <span className="mt-1 block max-w-[75ch] text-[12px] leading-relaxed text-muted-foreground">
                    {lang && !auf ? `${m.note.slice(0, 220).replace(/\s+\S*$/, "")} …` : m.note}
                    {lang && (
                      <button type="button" className="ml-1 font-semibold text-primary"
                        onClick={() => setOffen((o) => {
                          const n = new Set(o);
                          if (n.has(m.seq)) n.delete(m.seq); else n.add(m.seq);
                          return n;
                        })}>
                        {auf ? "weniger" : "weiterlesen"}
                      </button>
                    )}
                  </span>
                )}
              </TextZelle>
              <BetragZelle euro={m.planned} label="Ansatz" text={euro(m.planned)}
                className="text-muted-foreground dark:text-muted-foreground" />
              <BetragZelle euro={m.forecast} label="Prognose" text={euro(m.forecast)}
                className="font-medium text-foreground dark:text-foreground" />
            </tr>
          );
        })}
      </ZahlenTabelle>

      <p className="max-w-[76ch] text-[11.5px] leading-relaxed text-muted-foreground">
        Aus dem Budgetbericht {bericht?.template_number ? `(Vorlage ${bericht.template_number}) ` : ""}
        an den Fachausschuss, Teilfinanzrechnung. Die Erläuterungen stehen so im Bericht. Eine
        Prognose über dem Ansatz ist meist Geld aus Vorjahren, das jetzt abfließt
        (Ermächtigungsübertragung) — keine Überschreitung des Plans. Die Maßnahmen ergeben die
        Summenzeile des Berichts; eingelesen sind die Berichte seit {jahre[0]?.[0]}.
      </p>
    </section>
  );
}
