"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, ClipboardList, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PROBLEM_KATEGORIEN, PROBLEM_SCOPE_META } from "@/lib/probleme";
import {
  beginProblemReportContinuation,
  formatOldenburgDateTime,
  isEligiblePrivateReporter,
  privateReportDetailQueryKey,
  privateReportListQueryKey,
  PRIVATE_REPORT_QUERY_META,
} from "@/lib/problem-report-session";
import type { ApiAntwort } from "@/lib/vertrag";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Spinner,
  formatDate,
} from "@/components/ui";

type PrivateReportList = ApiAntwort<"/meldungen">;
type PrivateReportSummary = PrivateReportList["reports"][number];
type PrivateReport = ApiAntwort<"/meldungen/{report_id}">;

const PAGE_SIZE = 10;
const REPORT_STATE = {
  draft: "Entwurf",
  submitted: "Privat eingegangen",
} as const satisfies Record<PrivateReportSummary["state"], string>;

function reportState(report: Pick<PrivateReportSummary, "state" | "moderation_outcome">) {
  if (report.moderation_outcome === "rejected") return "Abgelehnt";
  if (report.moderation_outcome === "approved") return "Von Ratslotse geprüft";
  return REPORT_STATE[report.state];
}

export function MyReports() {
  const { user } = useAuth();
  const router = useRouter();
  const eligible = isEligiblePrivateReporter(user);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [continuationError, setContinuationError] = useState<string | null>(null);
  const reportButtons = useRef(new Map<number, HTMLButtonElement>());
  const listQuery = useInfiniteQuery({
    queryKey: privateReportListQueryKey(user?.id),
    queryFn: ({ pageParam }) => api.get<PrivateReportList>(
      `/meldungen?limit=${PAGE_SIZE}&offset=${pageParam}`,
    ),
    initialPageParam: 0,
    getNextPageParam: (lastPage) => {
      const nextOffset = lastPage.offset + lastPage.reports.length;
      return nextOffset < lastPage.total ? nextOffset : undefined;
    },
    enabled: eligible,
    retry: false,
    meta: PRIVATE_REPORT_QUERY_META,
  });

  if (!eligible || !user) {
    return (
      <Card className="p-6 text-center sm:p-8">
        <ShieldCheck className="mx-auto h-5 w-5 text-primary" aria-hidden />
        <h2 className="mt-4 font-display text-xl font-bold text-foreground">
          Persönliche Meldungen sind Bürgerkonten vorbehalten
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Dieses Konto kann keine persönlichen Meldungen öffnen.
        </p>
      </Card>
    );
  }

  if (listQuery.isPending) {
    return <Spinner label="Meine Meldungen werden geladen…" className="min-h-[360px]" />;
  }

  if (listQuery.isError) {
    return (
      <ErrorState
        title="Meine Meldungen konnten nicht geladen werden"
        hint="Deine privaten Meldungen bleiben gespeichert."
        onRetry={() => void listQuery.refetch()}
        busy={listQuery.isFetching}
      />
    );
  }

  const reports = listQuery.data.pages.flatMap((page) => page.reports);
  if (reports.length === 0) {
    return (
      <EmptyState
        icon={ClipboardList}
        title="Noch keine eigenen Meldungen"
        hint="Deine Entwürfe und privat eingegangenen Meldungen erscheinen hier."
        action={<Button asChild><Link href="/probleme/melden">Problem melden</Link></Button>}
      />
    );
  }

  const closeDetail = () => {
    const previousId = selectedId;
    setSelectedId(null);
    window.requestAnimationFrame(() => {
      if (previousId !== null) reportButtons.current.get(previousId)?.focus();
    });
  };

  return (
    <div className="space-y-5">
      <div className="space-y-3">
        {reports.map((report) => {
          const selected = selectedId === report.id;
          return (
            <ReportRow
              key={report.id}
              report={report}
              selected={selected}
              buttonRef={(button) => {
                if (button) reportButtons.current.set(report.id, button);
                else reportButtons.current.delete(report.id);
              }}
              onOpen={() => {
                setContinuationError(null);
                setSelectedId(report.id);
              }}
            >
              {selected && (
                <ReportDetail
                  reportId={report.id}
                  ownerId={user.id}
                  onClose={closeDetail}
                  onContinue={(privateReport) => {
                    if (!beginProblemReportContinuation(user.id, privateReport)) {
                      setContinuationError(
                        "Der Entwurf konnte nicht sicher geöffnet werden. Bitte versuche es erneut.",
                      );
                      return;
                    }
                    router.push("/probleme/melden");
                  }}
                />
              )}
            </ReportRow>
          );
        })}
      </div>

      {listQuery.hasNextPage && (
        <div className="flex justify-center">
          <Button
            type="button"
            variant="secondary"
            onClick={() => void listQuery.fetchNextPage()}
            disabled={listQuery.isFetchingNextPage}
          >
            <ChevronDown className={listQuery.isFetchingNextPage ? "animate-spin" : ""} aria-hidden />
            {listQuery.isFetchingNextPage ? "Ältere Meldungen werden geladen…" : "Ältere Meldungen laden"}
          </Button>
        </div>
      )}

      {continuationError && (
        <p role="alert" className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-foreground">
          {continuationError}
        </p>
      )}
    </div>
  );
}

function ReportRow({
  report,
  selected,
  buttonRef,
  onOpen,
  children,
}: {
  report: PrivateReportSummary;
  selected: boolean;
  buttonRef: (button: HTMLButtonElement | null) => void;
  onOpen: () => void;
  children?: ReactNode;
}) {
  return (
    <Card className={selected ? "border-primary/50" : undefined}>
      <button
        ref={buttonRef}
        type="button"
        aria-label={`${report.text_preview} öffnen`}
        aria-expanded={selected}
        aria-controls={selected ? `private-report-detail-${report.id}` : undefined}
        onClick={onOpen}
        className="flex w-full min-w-0 items-start gap-3 rounded-xl p-4 text-left transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 sm:p-5"
      >
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge color={report.moderation_outcome === "rejected" ? "red" : report.state === "submitted" ? "green" : "blue"}>
              {reportState(report)}
            </Badge>
            <span className="text-xs text-muted-foreground">
              Beobachtet am {formatDate(report.observed_on)}
            </span>
          </div>
          <p className="mt-2 line-clamp-2 break-words text-sm font-medium leading-relaxed text-foreground">
            {report.text_preview}
          </p>
          <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
            {PROBLEM_KATEGORIEN[report.category]}
            {" · "}
            {PROBLEM_SCOPE_META[report.scope_kind].publicLabel}
            {" · "}
            Zuletzt geändert {formatOldenburgDateTime(report.updated_at)}
          </p>
        </div>
        {selected ? (
          <ChevronDown className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
        ) : (
          <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
        )}
      </button>
      {children}
    </Card>
  );
}

function ReportDetail({
  reportId,
  ownerId,
  onClose,
  onContinue,
}: {
  reportId: number;
  ownerId: number;
  onClose: () => void;
  onContinue: (report: PrivateReport) => void;
}) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const detailQuery = useQuery({
    queryKey: privateReportDetailQueryKey(ownerId, reportId),
    queryFn: () => api.get<PrivateReport>(`/meldungen/${reportId}`),
    retry: false,
    meta: PRIVATE_REPORT_QUERY_META,
  });

  useEffect(() => {
    if (detailQuery.data) headingRef.current?.focus();
  }, [detailQuery.data]);

  const detailId = `private-report-detail-${reportId}`;

  if (detailQuery.isPending) {
    return (
      <div id={detailId} className="border-t border-border">
        <Spinner label="Meldungsdetails werden geladen…" className="min-h-64" />
      </div>
    );
  }

  if (detailQuery.isError) {
    return (
      <div id={detailId} className="border-t border-border p-4 sm:p-5">
        <ErrorState
          title="Die Meldung konnte nicht geöffnet werden"
          hint="Versuche, die privaten Details noch einmal zu laden."
          onRetry={() => void detailQuery.refetch()}
          busy={detailQuery.isFetching}
        />
      </div>
    );
  }

  const report = detailQuery.data;
  const description = report.state === "submitted"
    ? report.confirmed_text ?? report.draft_text
    : report.draft_text;
  const headingId = `${detailId}-heading`;

  return (
    <section id={detailId} className="border-t border-border p-5 sm:p-6" aria-labelledby={headingId}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <Badge color={report.moderation_outcome === "rejected" ? "red" : report.state === "submitted" ? "green" : "blue"}>
            {reportState(report)}
          </Badge>
          <h2
            id={headingId}
            ref={headingRef}
            tabIndex={-1}
            className="mt-2 font-display text-xl font-bold text-foreground outline-none"
          >
            Meldung im Detail
          </h2>
        </div>
        <Button type="button" variant="ghost" onClick={onClose}>Schließen</Button>
      </div>

      <div className="mt-5 space-y-5">
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Beschreibung</h3>
          <p className="mt-1 whitespace-pre-wrap break-words text-sm leading-relaxed text-foreground">{description}</p>
        </section>
        {report.moderation_outcome === "rejected" && report.rejection_explanation && (
          <section className="rounded-xl border border-destructive/20 bg-destructive/5 p-4">
            <h3 className="text-sm font-semibold text-foreground">Warum die Meldung abgelehnt wurde</h3>
            <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-relaxed text-foreground">
              {report.rejection_explanation}
            </p>
          </section>
        )}
        <dl className="grid gap-4 text-sm sm:grid-cols-2">
          <DetailFact label="Beobachtet am" value={formatDate(report.observed_on)} />
          <DetailFact label="Kategorie" value={PROBLEM_KATEGORIEN[report.category]} />
          <DetailFact label="Raumbezug" value={PROBLEM_SCOPE_META[report.scope_kind].publicLabel} />
          {report.location_label && <DetailFact label="Privater Ort" value={report.location_label} />}
          <DetailFact label="Stand" value={`Revision ${report.content_revision}`} />
          <DetailFact label="Zuletzt geändert" value={formatOldenburgDateTime(report.updated_at)} />
        </dl>
      </div>

      <div className="mt-6 border-t border-border pt-4">
        {report.state === "draft" ? (
          <Button type="button" onClick={() => onContinue(report)}>Entwurf fortsetzen</Button>
        ) : report.moderation_outcome === "rejected" ? (
          <p className="text-sm text-muted-foreground">
            Diese Entscheidung ist endgültig und schreibgeschützt. Antworten oder erneutes Absenden sind in diesem Schritt nicht möglich.
          </p>
        ) : report.moderation_outcome === "approved" ? (
          <p className="text-sm text-muted-foreground">
            Ratslotse hat diese Meldung geprüft. Sie ist dadurch noch nicht öffentlich und wurde nicht an die Stadt weitergegeben.
          </p>
        ) : (
          <p className="text-sm text-muted-foreground">
            Diese Meldung ist privat eingegangen und hier schreibgeschützt.
          </p>
        )}
      </div>
    </section>
  );
}

function DetailFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 break-words text-foreground">{value}</dd>
    </div>
  );
}
