"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, CalendarDays, CheckCircle2, ExternalLink, MapPin } from "lucide-react";
import { ApiError, api } from "@/lib/api";
import type { PublicProblem, PublicProblemEvent } from "@/lib/types";
import {
  PROBLEM_ANGEBOT,
  PROBLEM_CONFIDENCE,
  PROBLEM_KATEGORIEN,
  PROBLEM_SCOPE,
  PROBLEM_STATUS,
  VORSCHAU_PROBLEME,
} from "@/lib/probleme";
import { Badge, Button, Card, EmptyState, ErrorState, Spinner, formatDate } from "@/components/ui";

export default function DetailView({ problemId, vorschau }: { problemId: number; vorschau: boolean }) {
  const query = useQuery({
    queryKey: ["public-problem", problemId],
    queryFn: () => api.get<PublicProblem>(`/probleme/${problemId}`),
    enabled: !vorschau,
    staleTime: 60_000,
  });
  const problem = vorschau
    ? VORSCHAU_PROBLEME.find((entry) => entry.id === problemId) ?? null
    : query.data ?? null;
  const notFound = vorschau
    ? problem === null
    : query.error instanceof ApiError && query.error.status === 404;

  if (notFound) {
    return (
      <EmptyState
        title="Problem nicht gefunden"
        hint="Es wurde nicht veröffentlicht, archiviert oder der Link ist nicht mehr gültig."
        mascot="search"
        action={<Button asChild variant="secondary"><Link href="/probleme">Zur Problemkarte</Link></Button>}
      />
    );
  }
  if (!vorschau && query.isLoading) return <Spinner className="min-h-[24rem]" />;
  if (!problem) {
    return (
      <ErrorState
        title="Problem konnte nicht geladen werden"
        hint="Die öffentliche Detailseite ist gerade nicht erreichbar."
        onRetry={() => void query.refetch()}
        busy={query.isFetching}
      />
    );
  }

  const status = PROBLEM_STATUS[problem.status];
  return (
    <article className="mx-auto max-w-4xl space-y-5">
      <Link href="/probleme" className="inline-flex items-center gap-1.5 rounded-md text-sm font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
        <ArrowLeft className="h-4 w-4" aria-hidden /> Zur Problemkarte
      </Link>

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
        <h1 className="mt-3 font-display text-2xl font-bold tracking-tight text-foreground sm:text-[30px] sm:leading-9">{problem.title}</h1>
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

      <Card className="p-5 sm:p-6">
        <h2 className="text-sm font-semibold text-foreground">Bestätigungsstand</h2>
        <dl className="mt-4 grid grid-cols-3 gap-2 text-center">
          <Metric label="Reporter*innen" value={problem.unique_reporters} />
          <Metric label="Aktuelle Beobachtungen" value={problem.current_observations} />
          <Metric label="Beobachtungen insgesamt" value={problem.total_observations} />
        </dl>
        <dl className="mt-5 grid gap-3 border-t border-border pt-4 text-sm sm:grid-cols-2">
          <DateValue label="Erste Beobachtung" value={problem.first_observed_at} />
          <DateValue label="Letzte Beobachtung" value={problem.last_observed_at} />
        </dl>
        {problem.tags.length > 0 && (
          <div className="mt-5 flex flex-wrap gap-2 border-t border-border pt-4" aria-label="Schlagwörter">
            {problem.tags.map((tag) => <Badge key={tag}>{tag}</Badge>)}
          </div>
        )}
      </Card>

      <Card className="p-5 sm:p-6">
        <h2 className="text-lg font-semibold text-foreground">Öffentliche Zeitleiste</h2>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
          Nur moderierte, belegbare Ereignisse. Ratslotse zeigt keine amtlichen Bearbeitungsstände ohne überprüfbare Quelle.
        </p>
        {problem.events && problem.events.length > 0 ? (
          <ol className="mt-5 space-y-5">
            {problem.events.map((event, index) => (
              <TimelineEvent key={`${event.event_at}-${event.kind}-${index}`} event={event} />
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

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt className="text-[11px] leading-snug text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-xl font-bold tabular-nums text-foreground">{value}</dd>
    </div>
  );
}

function DateValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 sm:block">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium text-foreground sm:mt-1">{formatDate(value)}</dd>
    </div>
  );
}

function TimelineEvent({ event }: { event: PublicProblemEvent }) {
  const sourceUrl = safeHttpUrl(event.source_url);
  return (
    <li className="relative pl-7">
      <CheckCircle2 className="absolute left-0 top-0.5 h-4 w-4 text-primary" aria-hidden />
      <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
        <h3 className="font-medium text-foreground">{event.title}</h3>
        <time dateTime={event.event_at} className="shrink-0 text-xs text-muted-foreground">{formatDate(event.event_at)}</time>
      </div>
      {event.detail && <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{event.detail}</p>}
      {(event.source_kind || sourceUrl) && (
        <p className="mt-2 text-xs text-muted-foreground">
          {event.source_kind && <span>{event.source_kind}</span>}
          {event.source_kind && sourceUrl && " · "}
          {sourceUrl && (
            <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-medium text-primary hover:underline">
              Quelle öffnen <ExternalLink className="h-3 w-3" aria-hidden />
            </a>
          )}
        </p>
      )}
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
