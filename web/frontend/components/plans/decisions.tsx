"use client";

// BESCHLÜSSE ZUM PLAN, nach Beziehung getrennt (Plan § 3.2 Nr. 6). Erwähnungen
// bleiben hinter „Weitere“: Eine Nennung ist keine Umsetzung.

import { useState } from "react";
import Link from "next/link";
import { ChevronDown } from "lucide-react";
import { Aufklapp } from "@/components/aufklapp";
import { OutcomeDot } from "@/components/decision-ui";
import { Kicker } from "@/components/plans/parts";
import { decisionHref } from "@/lib/routes";
import { formatDate, type PlanDecisionGroup, type PlanDetail } from "@/lib/plans";
import { cn } from "@/lib/utils";

/** So viele Einträge einer Gruppe stehen offen; der Rest hinter einem Knopf. */
const OPEN = 5;

function Entries({ group }: { group: PlanDecisionGroup }) {
  const [showAll, setShowAll] = useState(false);
  const rest = group.entries.length - OPEN;
  // Ein einzelner Rest-Eintrag steht gleich da — ein Knopf für eine Zeile spart nichts.
  const shown = showAll || rest <= 1 ? group.entries : group.entries.slice(0, OPEN);
  return (
    <>
      <ul className="divide-y divide-border/70">
        {shown.map((entry) => (
          <li key={`${entry.template_number ?? entry.title}-${entry.date}`} className="py-2.5">
            <p className="break-words text-[14px] font-medium leading-snug text-foreground">
              {entry.decision_id != null ? (
                <Link href={decisionHref(entry.decision_id)} className="hover:text-primary hover:underline">{entry.title}</Link>
              ) : entry.title}
            </p>
            <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-meta text-muted-foreground">
              {entry.outcome && <OutcomeDot outcome={entry.outcome} />}
              <span>{[entry.committee, formatDate(entry.date)].filter(Boolean).join(" · ")}</span>
              {entry.template_number && <span className="font-mono">{entry.template_number}</span>}
              {entry.deliberations > 1 && <span>{entry.deliberations} Beratungen</span>}
            </p>
          </li>
        ))}
      </ul>
      {shown.length < group.entries.length && (
        <button type="button" onClick={() => setShowAll(true)}
          className="inline-flex min-h-11 items-center gap-1 text-[13px] font-medium text-primary hover:underline">
          <ChevronDown className="h-3.5 w-3.5 shrink-0" aria-hidden /> {rest} weitere zeigen
        </button>
      )}
    </>
  );
}

export function Decisions({ plan }: { plan: PlanDetail }) {
  const [showMentions, setShowMentions] = useState(false);
  const main = plan.decision_groups.filter((g) => g.key !== "mentions");
  const mentions = plan.decision_groups.find((g) => g.key === "mentions");
  if (main.length === 0 && !mentions) return null;
  return (
    <section aria-labelledby="plan-decisions" className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <Kicker className="mb-3 text-[11px] font-medium tracking-[0.1em]"><span id="plan-decisions">Beschlüsse zum Plan</span></Kicker>
      <div className="space-y-4">
        {main.map((g) => (
          <div key={g.key}>
            <h3 className="text-[13px] font-semibold text-foreground">
              {g.label} <span className="font-normal text-muted-foreground">· {g.entries.length}</span>
            </h3>
            <Entries group={g} />
          </div>
        ))}
        {mentions && (
          <div>
            <button type="button" onClick={() => setShowMentions((w) => !w)} aria-expanded={showMentions}
              className="inline-flex min-h-11 items-center gap-1 text-left text-[13px] font-medium text-primary hover:underline">
              <ChevronDown className={cn("h-3.5 w-3.5 shrink-0 transition-transform duration-weg ease-in-out-strong", showMentions && "rotate-180")} aria-hidden />
              Weitere: {mentions.entries.length} {mentions.entries.length === 1 ? "Beschluss erwähnt" : "Beschlüsse erwähnen"} den Plan
            </button>
            <Aufklapp offen={showMentions}>
              <p className="text-hinweis text-muted-foreground">
                Ihre Vorlage nennt die Nummer des Plans. Eine Erwähnung ist keine Umsetzung.
              </p>
              <Entries group={mentions} />
            </Aufklapp>
          </div>
        )}
      </div>
    </section>
  );
}
