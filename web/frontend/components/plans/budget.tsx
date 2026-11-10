"use client";

// IM HAUSHALT: Posten, deren eigener Text den Plan beim Namen nennt
// (council/plan_pages.py::budget_block, Verweise in council/plan_budget.json).
// Nur für Konten mit dem Recht `budget` — die Sperre sitzt am Endpunkt, hier
// wird nur höflich nicht gefragt (lib/rechte.ts).
//
// Beträge so, wie sie in der Zeile stehen; gerundet wird genau hier, einmal,
// und jeder Euro-Wert trägt sein €. Kein Gesamtbetrag: Was der Plan kostet,
// steht so nirgends im Haushalt.

import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { Kicker } from "@/components/plans/parts";
import { useAuth } from "@/lib/auth";
import { darfHaushalt } from "@/lib/rechte";
import { useFetch } from "@/lib/use-fetch";
import type { ApiAntwort } from "@/lib/vertrag";

type PlanBudget = ApiAntwort<"/council/budget/plan/{key}">;

const KIND_LABEL: Record<PlanBudget["items"][number]["kind"], string> = {
  product: "Produkt", investment: "Investition", change: "Änderung",
};

/** „3.680.862 €“ — ganze Euro, echtes Minuszeichen. */
export function euro(value: number): string {
  const whole = Math.round(value);
  const digits = Math.abs(whole).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return `${whole < 0 ? "−" : ""}${digits} €`;
}

export function Budget({ planKey }: { planKey: string }) {
  const { user, loading } = useAuth();
  const allowed = !loading && darfHaushalt(user);
  const { data } = useFetch<PlanBudget>(allowed ? `/council/budget/plan/${encodeURIComponent(planKey)}` : null, { quiet: true });
  if (!allowed || !data || data.items.length === 0) return null;
  return (
    <section aria-labelledby="plan-budget" className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <Kicker className="text-[11px] font-medium tracking-[0.1em]"><span id="plan-budget">Im Haushalt</span></Kicker>
        <Link href="/haushalt" prefetch={false} className="text-meta text-primary hover:underline">Zum Haushalt</Link>
      </div>
      <p className="mb-2 max-w-[76ch] text-hinweis text-muted-foreground">{data.note}</p>
      <ul className="divide-y divide-border/70">
        {data.items.map((item, i) => (
          <li key={`${item.kind}-${item.number}-${item.title}-${i}`} className="py-2.5">
            <p className="font-mono text-[10.5px] uppercase tracking-[0.08em] text-muted-foreground">
              {[KIND_LABEL[item.kind], item.number, item.context].filter(Boolean).join(" · ")}
            </p>
            <p className="mt-0.5 break-words text-[14px] font-medium leading-snug text-foreground">{item.title}</p>
            <dl className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-meta">
              {item.amounts.map((a) => (
                <div key={a.label} className="flex gap-1.5">
                  <dt className="text-muted-foreground">{a.label}</dt>
                  <dd className="font-medium tabular-nums text-foreground">{euro(a.value)}</dd>
                </div>
              ))}
            </dl>
            {/* Nennt schon der Titel den Plan („Kita-Ausbau, 4. Fortschreibung, 2023“), wäre das Zitat nur ein Echo. */}
            {item.quote.replace(/^…|…$/g, "").trim() !== item.title.trim() && (
              <p className="mt-1 break-words border-l-2 border-border pl-2.5 text-hinweis text-muted-foreground">„{item.quote}“</p>
            )}
            {item.source_url && (
              <a href={item.source_url} target="_blank" rel="noopener noreferrer" className="mt-0.5 inline-flex items-center gap-1 text-meta text-primary hover:underline">
                Dokument öffnen <ExternalLink className="h-3 w-3" aria-hidden />
              </a>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
