// RÜCKBLICK: was aus einem abgelaufenen oder abgelösten Plan geworden ist
// (docs/plan-ziele-plaene.md § 3.3).
//
// Ein fester Aufbau, kein freier Text — und keine Bewertung: was vorgesehen
// war, was die Verwaltung selbst meldet, welche Grenzen sie selbst nennt,
// was weiterläuft. Die Sätze der Verwaltung stehen wörtlich da, mit ihrer
// Vorlage. Findet Ratslotse keine Auswertung, steht genau das da — „nicht
// gefunden“, nicht „gibt es nicht“.

import Link from "next/link";
import { ArrowRight, ExternalLink } from "lucide-react";
import { Kicker } from "@/components/plans/parts";
import { planHref } from "@/lib/routes";
import type { PlanDetail } from "@/lib/plans";

type Review = NonNullable<PlanDetail["review"]>;

function Part({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="border-t border-border/70 pt-3 first:border-t-0 first:pt-0">
      <dt className="font-mono text-[10.5px] uppercase tracking-[0.08em] text-muted-foreground">{label}</dt>
      <dd className="mt-1.5 text-[14px] leading-relaxed text-foreground">{children}</dd>
    </div>
  );
}

function Statements({ statements }: { statements: Review["statements"] }) {
  return (
    <ul className="space-y-2">
      {statements.map((s) => (
        <li key={s.text}>
          <blockquote className="border-l-2 border-border pl-3 text-foreground">„{s.text}“</blockquote>
          <p className="mt-0.5 pl-3 text-meta text-muted-foreground">
            {s.source_label}{s.template_number && <span className="font-mono"> · {s.template_number}</span>}
          </p>
        </li>
      ))}
    </ul>
  );
}

export function Review({ review }: { review: Review }) {
  const results = review.statements.filter((s) => s.kind === "result");
  const limits = review.statements.filter((s) => s.kind === "limit");
  const evaluation = review.evaluation;
  return (
    <section aria-labelledby="plan-review" className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <Kicker className="text-[11px] font-medium tracking-[0.1em]"><span id="plan-review">Rückblick</span></Kicker>
        <p className="font-mono text-meta text-muted-foreground">Nach Angaben der Verwaltung</p>
      </div>
      <dl className="max-w-[76ch] space-y-3">
        {review.planned.length > 0 && (
          <Part label="Was vorgesehen war">
            {review.planned.map((fact) => `${fact.label}: ${fact.value}`).join(" · ")}
          </Part>
        )}
        <Part label="Was die Verwaltung meldet">
          {evaluation ? (
            <p>
              Ausgewertet in: {evaluation.title ?? evaluation.template_number}{" "}
              {evaluation.url ? (
                <a href={evaluation.url} target="_blank" rel="noopener noreferrer"
                  className="inline-flex items-center gap-0.5 whitespace-nowrap font-mono text-meta text-primary hover:underline">
                  {evaluation.template_number} <ExternalLink className="h-3 w-3" aria-hidden />
                </a>
              ) : <span className="font-mono text-meta">{evaluation.template_number}</span>}
            </p>
          ) : (
            <p className="text-muted-foreground">{review.no_evaluation_note}</p>
          )}
          {results.length > 0 && <div className="mt-2"><Statements statements={results} /></div>}
          {review.has_status && (
            <p className="mt-2 text-hinweis text-muted-foreground">
              Die Verteilung aus der Auswertung steht unter <a href="#plan-city-status" className="text-primary hover:underline">Stand laut Stadt</a>.
            </p>
          )}
        </Part>
        {limits.length > 0 && (
          <Part label="Grenzen, die der Bericht selbst nennt"><Statements statements={limits} /></Part>
        )}
        <Part label="Was weitergeführt wird">
          {review.continued_by ? (
            <Link href={planHref(review.continued_by.key)} prefetch={false}
              className="inline-flex items-center gap-1 font-medium text-primary hover:underline">
              {review.continued_by.title} <ArrowRight className="h-3.5 w-3.5" aria-hidden />
              {!review.continued_by.adopted && <span className="font-normal text-muted-foreground">(in Arbeit)</span>}
            </Link>
          ) : (
            <p className="text-muted-foreground">Kein Nachfolger im Register der Pläne.</p>
          )}
        </Part>
      </dl>
    </section>
  );
}
