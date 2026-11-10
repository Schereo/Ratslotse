// VERWANDTE PLÄNE: Pläne mit ähnlichem Inhalt — ohne Sprachmodell
// vorgeschlagen (Nähe der Kernpunkte im selben Themenfeld), von Hand
// durchgesehen (scripts/plan_verwandt.py). Die Seite nennt sie ohne Grad und
// ohne Begründung: „verwandt“ ist ein Wegweiser, keine Aussage über die Pläne.
// Vorgänger und Nachfolger stehen nicht hier, sondern im Kopf.

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { Kicker } from "@/components/plans/parts";
import { planHref } from "@/lib/routes";
import type { PlanDetail } from "@/lib/plans";

export function Related({ plans }: { plans: PlanDetail["related"] }) {
  if (plans.length === 0) return null;
  return (
    <section aria-labelledby="plan-related" className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <Kicker className="mb-1 text-[11px] font-medium tracking-[0.1em]"><span id="plan-related">Verwandte Pläne</span></Kicker>
      <ul className="divide-y divide-border/70">
        {plans.map((plan) => (
          <li key={plan.key}>
            <Link href={planHref(plan.key)} prefetch={false}
              className="group flex min-h-11 items-center gap-2 py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring">
              <span className="min-w-0 flex-1">
                <span className="block break-words text-[14px] font-medium leading-snug text-foreground group-hover:text-primary">{plan.title}</span>
                <span className="block text-meta text-muted-foreground">
                  {plan.status === "running" ? plan.field_label : `${plan.field_label} · ${plan.status_label}`}
                </span>
              </span>
              <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-fluss ease-out-strong group-hover:translate-x-0.5" aria-hidden />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
