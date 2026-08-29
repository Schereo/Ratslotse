"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { ArrowLeft, CalendarDays, CheckCircle2, ExternalLink, MapPin, MessageCircle, X } from "lucide-react";
import type { PublicProblem, PublicProblemEvent } from "@/lib/types";
import {
  isProblemMappable,
  PROBLEM_ANGEBOT,
  PROBLEM_CONFIDENCE,
  PROBLEM_KATEGORIEN,
  PROBLEM_SCOPE,
  PROBLEM_STATUS,
  unabhaengigeMeldungen,
} from "@/lib/probleme";
import { Badge, Card, formatDate } from "@/components/ui";

const ProblemMap = dynamic(
  () => import("@/components/problem-map").then((module) => module.ProblemMap),
  { ssr: false, loading: () => <div className="h-72 animate-pulse rounded-xl border border-border bg-muted sm:h-80" /> },
);

export function PublicProblemDetail({
  problem,
  vorschau = false,
  backHref,
  onClose,
  headingLevel = 1,
}: {
  problem: PublicProblem;
  vorschau?: boolean;
  backHref?: string;
  onClose?: () => void;
  headingLevel?: 1 | 2;
}) {
  const status = PROBLEM_STATUS[problem.status];
  const Heading = headingLevel === 1 ? "h1" : "h2";
  const SectionHeading = headingLevel === 1 ? "h2" : "h3";
  const eventHeadingLevel = headingLevel === 1 ? 3 : 4;
  return (
    <article className="mx-auto max-w-4xl space-y-5">
      {(backHref || onClose) && (
        <div className="flex items-center justify-between gap-3">
          {backHref ? (
            <Link href={backHref} className="inline-flex items-center gap-1.5 rounded-md text-sm font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
              <ArrowLeft className="h-4 w-4" aria-hidden /> Zur Problemkarte
            </Link>
          ) : <span />}
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="inline-flex min-h-10 items-center gap-1.5 rounded-lg px-2 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <X className="h-4 w-4" aria-hidden /> Details schließen
            </button>
          )}
        </div>
      )}

      {vorschau && (
        <p className="rounded-lg border border-amber-300/70 bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-950 dark:border-amber-700/60 dark:bg-amber-950/35 dark:text-amber-100" role="status">
          <strong>Vorschau:</strong> Dieses Problem und alle Zahlen sind frei erfunden.
        </p>
      )}

      <header>
        <div className="flex flex-wrap items-center gap-2">
          <Badge color={status.color}>{status.label}</Badge>
          <Badge>{PROBLEM_KATEGORIEN[problem.category as keyof typeof PROBLEM_KATEGORIEN] ?? problem.category}</Badge>
          <span className="text-xs text-muted-foreground">{PROBLEM_CONFIDENCE[problem.confidence]}</span>
        </div>
        <Heading className="mt-3 font-display text-2xl font-bold tracking-tight text-foreground sm:text-[30px] sm:leading-9">{problem.title}</Heading>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">{problem.summary}</p>
        <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-sm text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <MapPin className="h-4 w-4" aria-hidden />
            {problem.location_label || PROBLEM_SCOPE[problem.scope_kind]} · {PROBLEM_SCOPE[problem.scope_kind]}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <CalendarDays className="h-4 w-4" aria-hidden />
            Zuletzt beobachtet {formatDate(problem.last_observed_at)}
          </span>
        </div>
      </header>

      {isProblemMappable(problem) && (
        <section aria-labelledby={`problem-location-${problem.id}`}>
          <SectionHeading id={`problem-location-${problem.id}`} className="mb-2 text-lg font-semibold text-foreground">
            Ort
          </SectionHeading>
          <ProblemMap
            problems={[problem]}
            selectedId={problem.id}
            onSelect={() => undefined}
            interactive={false}
            className="h-72 sm:h-80"
          />
        </section>
      )}

      <Card className="p-4 sm:p-5">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
            <MessageCircle className="h-5 w-5" aria-hidden />
          </span>
          <p className="font-semibold tabular-nums text-foreground">
            {unabhaengigeMeldungen(problem.independent_reports)}
          </p>
        </div>
        {problem.tags.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2 border-t border-border pt-4" aria-label="Schlagwörter">
            {problem.tags.map((tag) => <Badge key={tag}>{tag}</Badge>)}
          </div>
        )}
      </Card>

      <Card className="p-5 sm:p-6">
        <SectionHeading className="text-lg font-semibold text-foreground">Öffentliche Zeitleiste</SectionHeading>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
          Belegt und moderiert – kein amtlicher Bearbeitungsstand.
        </p>
        {problem.events && problem.events.length > 0 ? (
          <ol className="mt-5 space-y-5">
            {problem.events.map((event, index) => (
              <TimelineEvent key={`${event.event_at}-${event.kind}-${index}`} event={event} headingLevel={eventHeadingLevel} />
            ))}
          </ol>
        ) : (
          <p className="mt-5 rounded-lg border border-dashed border-border p-5 text-sm text-muted-foreground">
            Noch keine öffentlichen Statusereignisse.
          </p>
        )}
      </Card>

      <p className="text-xs leading-relaxed text-muted-foreground">
        {PROBLEM_ANGEBOT.name} ist ein unabhängiges Ratslotse-Angebot. Einzelne Meldungen, Identitäten und Moderationsnotizen bleiben privat.
      </p>
    </article>
  );
}

function TimelineEvent({ event, headingLevel }: { event: PublicProblemEvent; headingLevel: 3 | 4 }) {
  const sourceUrl = safeHttpUrl(event.source_url);
  const Heading = headingLevel === 3 ? "h3" : "h4";
  return (
    <li className="relative pl-7">
      <CheckCircle2 className="absolute left-0 top-0.5 h-4 w-4 text-primary" aria-hidden />
      <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
        <Heading className="font-medium text-foreground">{event.title}</Heading>
        <time dateTime={event.event_at} className="shrink-0 text-xs text-muted-foreground">{formatDate(event.event_at)}</time>
      </div>
      {event.detail && <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{event.detail}</p>}
      <p className="mt-2 text-xs text-muted-foreground">
        <span>{event.source_kind}</span>
        {sourceUrl && (
          <>
            {" · "}
            <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-medium text-primary hover:underline">
              Quelle öffnen <ExternalLink className="h-3 w-3" aria-hidden />
            </a>
          </>
        )}
      </p>
    </li>
  );
}

function safeHttpUrl(value: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : null;
  } catch {
    return null;
  }
}
