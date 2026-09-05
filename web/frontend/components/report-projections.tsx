"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Globe2, ShieldCheck } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { canModerateReports } from "@/lib/account-capabilities";
import {
  PROBLEM_KATEGORIEN,
  PROBLEM_SCOPE_META,
  problemAppDetailHref,
  problemDetailHref,
  reportCountLabel,
} from "@/lib/probleme";
import { isNativeApp } from "@/lib/platform";
import type { ApiAntwort } from "@/lib/vertrag";
import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Input,
  Label,
  Spinner,
  Textarea,
  formatDate,
} from "@/components/ui";

type Queue = ApiAntwort<"/moderation/projektionen">;
type QueueReport = Queue["reports"][number];
type Detail = ApiAntwort<"/moderation/projektionen/{report_id}">;
type Target = ApiAntwort<"/moderation/projektionen/{report_id}/ziele">[number];
type Confirmation = ApiAntwort<
  "/moderation/projektionen/{report_id}/neue-stadtweite-projektion",
  "post"
>;

const PAGE_SIZE = 20;

type PendingConfirmation =
  | { kind: "existing"; target: Target }
  | { kind: "new"; title: string; summary: string }
  | null;

export function ReportProjections() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const authorized = canModerateReports(user);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [success, setSuccess] = useState<Confirmation | null>(null);
  const [native, setNative] = useState(false);
  const triggerRefs = useRef(new Map<number, HTMLButtonElement>());
  const headingRef = useRef<HTMLHeadingElement>(null);
  const queue = useInfiniteQuery({
    queryKey: ["private-report-projections", user?.id],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => api.get<Queue>(
      `/moderation/projektionen?limit=${PAGE_SIZE}&offset=${pageParam}`,
    ),
    getNextPageParam: (lastPage, pages) => {
      const loaded = pages.reduce((count, page) => count + page.reports.length, 0);
      return loaded < lastPage.total ? loaded : undefined;
    },
    enabled: authorized,
    retry: false,
    meta: { privateData: true },
  });

  useEffect(() => setNative(isNativeApp()), []);
  useEffect(() => {
    if (success) headingRef.current?.focus();
  }, [success]);

  if (!authorized) {
    return (
      <Card className="p-6 text-center sm:p-8">
        <ShieldCheck className="mx-auto h-5 w-5 text-primary" aria-hidden />
        <h2 className="mt-4 font-display text-xl font-bold">Moderationsrechte erforderlich</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Dieses Konto darf keine öffentlichen Projektionen bestätigen.
        </p>
      </Card>
    );
  }
  if (queue.isPending) {
    return <Spinner label="Projektionsliste wird geladen…" className="min-h-[320px]" />;
  }
  if (queue.isError) {
    return (
      <ErrorState
        title="Die Projektionsliste konnte nicht geladen werden"
        hint="Freigegebene Meldungen und öffentliche Probleme bleiben unverändert."
        onRetry={() => void queue.refetch()}
        busy={queue.isFetching}
      />
    );
  }

  const reports = queue.data.pages.flatMap((page) => page.reports);
  const closeDetail = (reportId: number) => {
    setSelectedId(null);
    requestAnimationFrame(() => triggerRefs.current.get(reportId)?.focus());
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <Button asChild variant="secondary"><Link href="/moderation/meldungen">Meldungen prüfen</Link></Button>
        <Button asChild><Link href="/moderation/projektionen" aria-current="page">Öffentlich zuordnen</Link></Button>
      </div>

      {success && (
        <Card className="border-primary/30 bg-primary/5 p-4 sm:p-5" role="status">
          <h2 ref={headingRef} tabIndex={-1} className="font-display text-lg font-bold outline-none">
            Öffentliche Projektion bestätigt
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Die private Meldung wurde datensparsam mit „{success.problem_title}“ verbunden.
          </p>
          <Button asChild variant="secondary" className="mt-3">
            <Link href={native ? problemAppDetailHref(success.problem_id) : problemDetailHref(success.problem_id)}>
              Öffentliche Ansicht öffnen
            </Link>
          </Button>
        </Card>
      )}

      {reports.length === 0 ? (
        <EmptyState
          icon={Globe2}
          title="Keine freigegebene Meldung wartet"
          hint="Eine Meldung erscheint hier erst nach einer menschlichen Freigabe."
        />
      ) : (
        <div className="space-y-3">
          {reports.map((report) => {
            const selected = selectedId === report.id;
            return (
              <Card key={report.id} className={selected ? "border-primary/50" : undefined}>
                <button
                  ref={(button) => {
                    if (button) triggerRefs.current.set(report.id, button);
                    else triggerRefs.current.delete(report.id);
                  }}
                  type="button"
                  aria-label={`${report.text_preview} öffentlich zuordnen`}
                  aria-expanded={selected}
                  aria-controls={selected ? `projection-detail-${report.id}` : undefined}
                  onClick={() => {
                    setSuccess(null);
                    setSelectedId(report.id);
                  }}
                  className="flex w-full min-w-0 items-start gap-3 rounded-xl p-4 text-left transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 sm:p-5"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge color="green">Menschlich freigegeben</Badge>
                      <span className="text-xs text-muted-foreground">
                        Beobachtet am {formatDate(report.observed_on)}
                      </span>
                    </div>
                    <p className="mt-2 line-clamp-2 break-words text-sm font-medium leading-relaxed">
                      {report.text_preview}
                    </p>
                    <p className="mt-2 text-xs text-muted-foreground">
                      {PROBLEM_KATEGORIEN[report.category]} · {PROBLEM_SCOPE_META[report.scope_kind].publicLabel}
                    </p>
                  </div>
                  {selected
                    ? <ChevronDown className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                    : <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />}
                </button>
                {selected && (
                  <ProjectionDetail
                    report={report}
                    onClose={() => closeDetail(report.id)}
                    onConfirmed={(confirmation) => {
                      setSelectedId(null);
                      setSuccess(confirmation);
                      void queryClient.invalidateQueries({ queryKey: ["private-report-projections"] });
                      void queryClient.invalidateQueries({ queryKey: ["public-problems"] });
                      void queryClient.invalidateQueries({ queryKey: ["private-reports"] });
                    }}
                  />
                )}
              </Card>
            );
          })}
        </div>
      )}

      {queue.hasNextPage && (
        <div className="flex justify-center">
          <Button
            type="button"
            variant="secondary"
            onClick={() => void queue.fetchNextPage()}
            disabled={queue.isFetchingNextPage}
          >
            {queue.isFetchingNextPage ? "Weitere werden geladen…" : "Weitere Freigaben laden"}
          </Button>
        </div>
      )}
    </div>
  );
}

function ProjectionDetail({
  report,
  onClose,
  onConfirmed,
}: {
  report: QueueReport;
  onClose: () => void;
  onConfirmed: (confirmation: Confirmation) => void;
}) {
  const queryClient = useQueryClient();
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [mode, setMode] = useState<"existing" | "new" | null>(null);
  const [search, setSearch] = useState("");
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [pending, setPending] = useState<PendingConfirmation>(null);
  const [error, setError] = useState<string | null>(null);
  const detail = useQuery({
    queryKey: ["private-report-projection-detail", report.id],
    queryFn: () => api.get<Detail>(`/moderation/projektionen/${report.id}`),
    retry: false,
    meta: { privateData: true },
  });
  const targets = useQuery({
    queryKey: ["public-projection-targets", report.id, search],
    queryFn: () => api.get<Target[]>(
      `/moderation/projektionen/${report.id}/ziele?q=${encodeURIComponent(search)}&limit=20`,
    ),
    enabled: mode === "existing" && detail.isSuccess,
    retry: false,
    meta: { privateData: true },
  });
  const confirmation = useMutation({
    mutationFn: async (choice: Exclude<PendingConfirmation, null>) => {
      if (choice.kind === "existing") {
        return api.post<Confirmation>(
          `/moderation/projektionen/${report.id}/bestehendes-problem`,
          { expected_revision: detail.data!.content_revision, problem_id: choice.target.problem_id },
        );
      }
      return api.post<Confirmation>(
        `/moderation/projektionen/${report.id}/neue-stadtweite-projektion`,
        {
          expected_revision: detail.data!.content_revision,
          title: choice.title,
          summary: choice.summary,
        },
      );
    },
    onSuccess: onConfirmed,
    onError: (reason) => {
      setError(
        reason instanceof ApiError && reason.status === 409
          ? "Die Meldung oder das Ziel ist nicht mehr verfügbar. Lade die Liste neu."
          : reason instanceof Error ? reason.message : "Die Projektion konnte nicht bestätigt werden.",
      );
    },
  });

  useEffect(() => {
    if (detail.data) headingRef.current?.focus();
  }, [detail.data]);

  if (detail.isPending) {
    return <div className="border-t border-border"><Spinner label="Freigabe wird geladen…" className="min-h-64" /></div>;
  }
  if (detail.isError) {
    return (
      <div className="border-t border-border p-4 sm:p-5">
        <ErrorState
          title="Die Freigabe ist nicht mehr verfügbar"
          hint="Vielleicht wurde sie bereits öffentlich zugeordnet."
          onRetry={() => void detail.refetch()}
          busy={detail.isFetching}
        />
        <div className="mt-3 flex justify-center">
          <Button type="button" variant="ghost" onClick={() => {
            onClose();
            void queryClient.invalidateQueries({ queryKey: ["private-report-projections"] });
          }}>Zur Projektionsliste</Button>
        </div>
      </div>
    );
  }

  const current = detail.data;
  return (
    <section id={`projection-detail-${report.id}`} className="border-t border-border p-5 sm:p-6" aria-labelledby={`projection-heading-${report.id}`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <Badge color="green">Menschlich freigegeben</Badge>
          <h2 id={`projection-heading-${report.id}`} ref={headingRef} tabIndex={-1} className="mt-2 font-display text-xl font-bold outline-none">
            Öffentliche Zuordnung vorbereiten
          </h2>
        </div>
        <Button type="button" variant="ghost" onClick={onClose}>Schließen</Button>
      </div>

      <div className="mt-5 space-y-5">
        <section>
          <h3 className="font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">Private Beobachtungen</h3>
          <div className="mt-2 space-y-3">
            {current.observations.map((observation, index) => (
              <div key={`${observation.observed_on}-${index}`} className="rounded-xl bg-muted/60 p-3">
                <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">{observation.text}</p>
                <p className="mt-1 text-xs text-muted-foreground">Beobachtet am {formatDate(observation.observed_on)}</p>
              </div>
            ))}
          </div>
        </section>
        <p className="rounded-xl border border-primary/20 bg-primary/5 p-4 text-sm leading-relaxed">
          Private Texte werden nicht automatisch veröffentlicht. Erst deine bestätigte Zuordnung macht ausschließlich Titel, Zusammenfassung und öffentliche Metadaten sichtbar. Das ist keine Annahme, Zuordnung oder Bearbeitung durch die Stadt und keine Aussage über Dringlichkeit oder Lösung.
        </p>

        {mode === null && (
          <div className="flex flex-wrap gap-2">
            <Button type="button" onClick={() => setMode("existing")}>Bestehendem Problem zuordnen</Button>
            {current.scope_kind === "citywide" && (
              <Button type="button" variant="secondary" onClick={() => setMode("new")}>Neue stadtweite Projektion</Button>
            )}
          </div>
        )}

        {mode === "existing" && (
          <section className="space-y-3" aria-labelledby={`existing-heading-${report.id}`}>
            <h3 id={`existing-heading-${report.id}`} className="font-display text-lg font-bold">Öffentliches Problem auswählen</h3>
            <div>
              <Label htmlFor={`projection-search-${report.id}`}>Nach öffentlichem Titel suchen</Label>
              <Input id={`projection-search-${report.id}`} value={search} maxLength={100} onChange={(event) => setSearch(event.target.value)} />
            </div>
            {targets.isPending && <Spinner label="Öffentliche Probleme werden geladen…" className="min-h-32" />}
            {targets.isError && (
              <ErrorState title="Öffentliche Probleme konnten nicht geladen werden" onRetry={() => void targets.refetch()} busy={targets.isFetching} />
            )}
            {targets.data?.length === 0 && <p className="text-sm text-muted-foreground">Kein passendes öffentliches Problem gefunden.</p>}
            <div className="space-y-2">
              {targets.data?.map((target) => (
                <button
                  key={target.problem_id}
                  type="button"
                  onClick={() => setPending({ kind: "existing", target })}
                  className="w-full rounded-xl border border-border p-4 text-left hover:border-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                >
                  <span className="font-semibold">{target.title}</span>
                  <span className="mt-1 block text-sm text-muted-foreground">{target.summary}</span>
                  <span className="mt-2 block text-xs text-muted-foreground">
                    {PROBLEM_KATEGORIEN[target.category]} · {PROBLEM_SCOPE_META[target.scope_kind].publicLabel} · {reportCountLabel(target.independent_reports)}
                  </span>
                </button>
              ))}
            </div>
            <Button type="button" variant="ghost" onClick={() => setMode(null)}>Zurück</Button>
          </section>
        )}

        {mode === "new" && (
          <section className="space-y-4" aria-labelledby={`new-heading-${report.id}`}>
            <div>
              <h3 id={`new-heading-${report.id}`} className="font-display text-lg font-bold">Neue stadtweite Projektion</h3>
              <p className="mt-1 text-sm text-muted-foreground">Formuliere eigenständig auf Deutsch, sachlich und neutral. Diese Angaben werden öffentlich.</p>
            </div>
            <div>
              <Label htmlFor={`projection-title-${report.id}`}>Öffentlicher Titel</Label>
              <Input id={`projection-title-${report.id}`} value={title} maxLength={120} onChange={(event) => setTitle(event.target.value)} />
            </div>
            <div>
              <Label htmlFor={`projection-summary-${report.id}`}>Öffentliche Zusammenfassung</Label>
              <Textarea id={`projection-summary-${report.id}`} value={summary} maxLength={600} rows={5} onChange={(event) => setSummary(event.target.value)} />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                disabled={!title.trim() || !summary.trim()}
                onClick={() => setPending({ kind: "new", title: title.trim(), summary: summary.trim() })}
              >Veröffentlichung abschließend prüfen</Button>
              <Button type="button" variant="ghost" onClick={() => setMode(null)}>Zurück</Button>
            </div>
          </section>
        )}
      </div>

      {error && <p role="alert" className="mt-4 text-sm text-destructive">{error}</p>}
      <ConfirmDialog
        open={pending !== null}
        onOpenChange={(open) => !open && setPending(null)}
        title="Öffentliche Projektion verbindlich bestätigen?"
        description={pending?.kind === "existing"
          ? `Die private Meldung wird mit „${pending.target.title}“ verbunden. Die unabhängige Meldezahl kann sich öffentlich ändern.`
          : "Titel und Zusammenfassung werden öffentlich. Private Texte, Identität und genauer Ort bleiben ausgeschlossen."}
        confirmLabel="Öffentlich zuordnen"
        variant="primary"
        onConfirm={() => {
          if (pending) confirmation.mutate(pending);
          setPending(null);
        }}
      />
    </section>
  );
}
