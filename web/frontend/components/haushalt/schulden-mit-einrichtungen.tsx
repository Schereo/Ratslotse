"use client";

// „Schulden samt eigenen Einrichtungen" — Block auf /haushalt/vergleich
// (Plan Haushalt-Datenquellen, PR 7). Quelle: Regionaldatenbank, Tabellen
// 71327-Z-02 und -Z-07 (council/regionalstatistik.py).
//
// DIE ANTWORT AUF DEN KERN DER SEITE: Ein Vergleich von Kernhaushalten misst
// zuerst die Auslagerung. Diese Tabelle der Statistik führt je Stadt beides —
// den Kernhaushalt und die Einrichtungen, die ihm ganz gehören. Deshalb steht
// je Stadt EIN Balken aus zwei Teilen: Wer nur den dunklen Teil liest, sieht
// die Organisationsform; der ganze Balken ist das, was die Stadt samt ihren
// Betrieben schuldet (ohne Beteiligungen unter 100 %).
//
// KEIN RANG, KEINE BEWERTUNGSFARBE: alphabetisch, beide Teile aus derselben
// neutralen Rampe, Oldenburg nur durch den fetten Namen hervorgehoben.

import { useState } from "react";
import { useFetch } from "@/lib/use-fetch";
import type { ApiAntwort } from "@/lib/vertrag";
import { deZahl } from "@/components/grafik/format";
import { Beleg } from "@/components/haushalt/source";
import { cn } from "@/lib/utils";

type Antwort = ApiAntwort<"/council/budget/debt-comparison">;

const euro = (v: number | null | undefined) => (v == null ? "—" : `${deZahl(v, 0)} €`);

export function SchuldenMitEinrichtungen() {
  const { data } = useFetch<Antwort>("/council/budget/debt-comparison");
  const [gewaehlt, setGewaehlt] = useState<number | null>(null);
  if (!data || data.years.length === 0) return null;
  const jahr = data.years.find((y) => y.year === gewaehlt) ?? data.years[0];
  const max = Math.max(...jahr.cities.map((c) => (c.core_per_capita ?? 0) + (c.entities_per_capita ?? 0)), 1);
  const ol = jahr.cities.find((c) => c.is_oldenburg);
  const olGesamt = ol ? (ol.core_per_capita ?? 0) + (ol.entities_per_capita ?? 0) : null;
  const fehlend = [2019, 2020, 2021, 2022, 2023, 2024, 2025]
    .filter((j) => j >= Math.min(...data.years.map((y) => y.year)) && !data.years.some((y) => y.year === j));

  return (
    <section className="@container/schulden rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-2">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Schulden samt eigenen Einrichtungen · 31.12.{jahr.year}
        </p>
        <div role="group" aria-label="Jahr wählen" className="flex flex-wrap gap-1">
          {[...data.years].reverse().map((y) => (
            <button key={y.year} type="button" aria-pressed={y.year === jahr.year}
              onClick={() => setGewaehlt(y.year)}
              className={cn(
                "min-h-[28px] rounded-full border px-2.5 font-mono text-[11px] tabular-nums",
                y.year === jahr.year ? "border-primary bg-primary/10 text-primary"
                  : "border-border text-muted-foreground hover:border-primary/40")}>
              {y.year}
            </button>
          ))}
        </div>
      </div>
      <h2 className="mt-1.5 font-display text-lg font-bold tracking-tight">
        Bei den Schulden lässt sich die Auslagerung herausrechnen
      </h2>
      <p className="mt-1.5 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
        Die Schuldenstatistik führt je Stadt nicht nur den Kernhaushalt, sondern auch die
        Einrichtungen, die ihr ganz gehören — Eigenbetriebe und hundertprozentige
        Gesellschaften<Beleg q="regionalstatistik" />.
        {ol && olGesamt != null && (
          <> Oldenburg schuldete Ende {jahr.year} im Kernhaushalt {euro(ol.core_per_capita)} je
            Einwohner*in, zusammen mit seinen Einrichtungen {euro(olGesamt)}.</>
        )}
      </p>

      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-4 rounded-sm" style={{ background: "var(--hh-aus-6)" }} />Kernhaushalt
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-4 rounded-sm" style={{ background: "var(--hh-aus-3)" }} />eigene Einrichtungen (100 %)
        </span>
      </div>

      <ul className="mt-3 flex flex-col gap-2">
        {jahr.cities.map((c) => {
          const kern = c.core_per_capita ?? 0;
          const einr = c.entities_per_capita ?? 0;
          return (
            <li key={c.key} className="grid grid-cols-[7.5rem_1fr] items-center gap-3 @xl/schulden:grid-cols-[9rem_1fr_9rem]"
              aria-label={`${c.city}: Kernhaushalt ${euro(kern)}, eigene Einrichtungen ${euro(einr)} je Einwohner*in`}>
              <span className={cn("truncate text-[12.5px]", c.is_oldenburg ? "font-bold text-foreground" : "text-foreground/85")}>
                {c.city}
              </span>
              <span className="flex h-3.5 min-w-0 overflow-hidden rounded-sm bg-muted/40">
                <span style={{ width: `${(kern / max) * 100}%`, background: "var(--hh-aus-6)" }} />
                <span style={{ width: `${(einr / max) * 100}%`, background: "var(--hh-aus-3)" }} />
              </span>
              <span className="col-span-2 -mt-1 font-mono text-[10.5px] tabular-nums text-muted-foreground @xl/schulden:col-span-1 @xl/schulden:mt-0 @xl/schulden:text-right">
                {euro(kern)} + {euro(einr)}
              </span>
            </li>
          );
        })}
      </ul>

      <p className="mt-3 max-w-[76ch] text-[11.5px] leading-relaxed text-muted-foreground">
        Je Einwohner*in am 30.06., Schulden zum 31.12. Oldenburgs Kernhaushalt stimmt in jedem
        gezeigten Jahr auf den Euro mit den eigenen Zahlen der Stadt überein — der Schuldenreihe
        des Statistischen Jahrbuchs, wo sie fehlt der Schuldenübersicht im Haushaltsplan
        {fehlend.length > 0 && <> — {fehlend.join(", ")} fehlt, weil sich das dort nicht prüfen lässt</>}.
        Für die Einrichtungen gibt es keine solche Gegenprobe; sie stehen, wie die Statistik sie
        führt. Beteiligungen unter 100 % (etwa an Energieversorgern) sind nicht dabei.
      </p>
    </section>
  );
}
