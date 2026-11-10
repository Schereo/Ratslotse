"use client";

// WAS DER PLAN FESTLEGT: ein Satz zum Zweck, darunter drei bis sechs
// Kernpunkte. Steht direkt unter dem Kopf — wer die Seite öffnet, soll den
// Plan in zwanzig Sekunden verstehen, ohne die Beschlüsse zu lesen.
//
// Die Sätze hat ein Sprachmodell entworfen; gezeigt wird nur, was als
// wörtliches Zitat in der Quelle steht (council/plan_judge.py). Deshalb
// trägt jeder Satz seinen Beleg: ein Tipp klappt das Zitat auf, der Link
// führt zum Dokument. Wo ein späterer Beschluss den Punkt gesetzt hat,
// steht dessen Datum dabei — der Satz gilt ab dann, nicht seit dem Plan.

import { useState } from "react";
import Link from "next/link";
import { ChevronDown, ExternalLink } from "lucide-react";
import { Aufklapp } from "@/components/aufklapp";
import { Kicker } from "@/components/plans/parts";
import { decisionHref } from "@/lib/routes";
import type { PlanContent, PlanContentStatement } from "@/lib/plans";
import { cn } from "@/lib/utils";

/** „Rahmenkonzept …, S. 5“ · „Beschluss des Rates vom 16.12.2019“ · „Vorlage der Verwaltung 19/0943“.
 *  `dated`: Das Datum steht schon im Abzeichen daneben. */
export function sourceLine(source: PlanContentStatement["source"], dated = false): string {
  if (source.kind === "attachment") return source.page ? `${source.label}, S. ${source.page}` : source.label;
  if (source.kind === "decision") return source.date_label && !dated ? `${source.label} vom ${source.date_label}` : source.label;
  return `${source.label} ${source.template_number}`;
}

function Evidence({ statement }: { statement: PlanContentStatement }) {
  const { source } = statement;
  return (
    <div className="pb-3 pl-0 pr-7">
      <blockquote className="border-l-2 border-border pl-3 text-[14px] leading-relaxed text-foreground">
        „{statement.quote}“
      </blockquote>
      <p className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 pl-3 text-meta text-muted-foreground">
        {source.decision_id != null && (
          <Link href={decisionHref(source.decision_id)} prefetch={false} className="font-medium text-primary hover:underline">
            Beschluss ansehen
          </Link>
        )}
        {source.url && (
          <a href={source.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
            {source.kind === "attachment" ? "Dokument öffnen" : `Vorlage ${source.template_number}`}
            <ExternalLink className="ml-1 inline h-3 w-3 -translate-y-px" aria-hidden />
          </a>
        )}
        {source.kind === "attachment" && <span className="font-mono">Anlage zu {source.template_number}</span>}
      </p>
    </div>
  );
}

function Statement({ statement, lead = false }: { statement: PlanContentStatement; lead?: boolean }) {
  const [open, setOpen] = useState(false);
  // Wo ein späterer Beschluss den Punkt gesetzt hat, steht dessen Datum vorn: Der Satz gilt ab dann.
  const dated = statement.amended && !!statement.source.date_label;
  return (
    <div>
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}
        className="grid min-h-11 w-full grid-cols-[minmax(0,1fr)_auto] items-start gap-x-3 py-2.5 text-left hover:bg-primary/[0.03]">
        <span className="min-w-0">
          <span className={cn("block break-words text-foreground",
            lead ? "text-[16px] font-medium leading-snug sm:text-[17px]" : "text-[14.5px] leading-snug")}>
            {statement.text}
          </span>
          <span className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-meta text-muted-foreground">
            {dated && (
              <span className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">
                Stand {statement.source.date_label}
              </span>
            )}
            <span className="min-w-0 break-words">{sourceLine(statement.source, dated)}</span>
          </span>
        </span>
        <span className="mt-0.5 flex items-center gap-1 text-meta text-muted-foreground">
          <span className="hidden sm:inline">{open ? "Zitat zu" : "Zitat"}</span>
          <ChevronDown className={cn("h-4 w-4 shrink-0 transition-transform duration-weg ease-in-out-strong", open && "rotate-180")} aria-hidden />
        </span>
      </button>
      <Aufklapp offen={open}><Evidence statement={statement} /></Aufklapp>
    </div>
  );
}

export function Content({ content }: { content: PlanContent }) {
  return (
    <section aria-labelledby="plan-content" className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <Kicker className="mb-1 text-[11px] font-medium tracking-[0.1em]"><span id="plan-content">{content.heading}</span></Kicker>
      <div className="max-w-[76ch]">
        <Statement statement={content.purpose} lead />
        <ul className="mt-1 divide-y divide-border/70 border-y border-border/70">
          {content.points.map((point) => (
            <li key={point.text}><Statement statement={point} /></li>
          ))}
        </ul>
        <p className="mt-3 text-hinweis text-muted-foreground">{content.note}</p>
      </div>
    </section>
  );
}
