"use client";

import { useEffect, useRef, useState } from "react";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, ClipboardCheck, ShieldCheck } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { canModerateReports } from "@/lib/account-capabilities";
import { PROBLEM_KATEGORIEN, PROBLEM_SCOPE_META } from "@/lib/probleme";
import type { ApiAntwort } from "@/lib/vertrag";
import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Label,
  Spinner,
  Textarea,
  formatDate,
} from "@/components/ui";

type Queue = ApiAntwort<"/moderation/meldungen">;
type QueueReport = Queue["reports"][number];
type Detail = ApiAntwort<"/moderation/meldungen/{report_id}">;
type Draft = ApiAntwort<"/moderation/meldungen/{report_id}/ablehnungsentwurf", "post">;
type Decision = ApiAntwort<"/moderation/meldungen/{report_id}/entscheidung", "post">;

type LocalReason = Detail["local_reason_codes"][number];
type AutomaticVerdict = NonNullable<Detail["ai_verdict"]>;
type AutomaticReason = NonNullable<Detail["ai_reason_code"]>;

const PAGE_SIZE = 20;
const LOCAL_REASONS: Record<LocalReason, string> = {
  potential_emergency: "Möglicher Notfallhinweis im Text",
  direct_contact_data: "Mögliche persönliche Kontaktdaten im Text",
  unsupported_text_format: "Text enthält nicht sicher verarbeitbare Zeichen",
};
const AUTOMATIC_VERDICTS: Record<AutomaticVerdict, string> = {
  suitable: "Automatischer Hinweis: wahrscheinlich geeignet",
  needs_human_review: "Automatischer Hinweis: genauer prüfen",
  unsuitable: "Automatischer Hinweis: wahrscheinlich ungeeignet",
};
const AUTOMATIC_REASONS: Record<AutomaticReason, string> = {
  municipal_problem: "Als kommunales Problem eingeschätzt",
  insufficient_information: "Angaben möglicherweise nicht ausreichend",
  non_municipal_matter: "Möglicherweise kein kommunales Anliegen",
  personal_or_identifying_content: "Mögliche personenbezogene Angaben",
  abusive_or_discriminatory_content: "Möglicherweise verletzender oder diskriminierender Inhalt",
  commercial_or_spam: "Möglicherweise Werbung oder Spam",
  possible_safety_context: "Möglicher Sicherheitsbezug",
  model_uncertain: "Automatische Einschätzung unsicher",
};

export function ReportModeration() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const authorized = canModerateReports(user);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const triggerRefs = useRef(new Map<number, HTMLButtonElement>());
  const queue = useInfiniteQuery({
    queryKey: ["private-report-moderation", user?.id],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => api.get<Queue>(
      `/moderation/meldungen?limit=${PAGE_SIZE}&offset=${pageParam}`,
    ),
    getNextPageParam: (lastPage, pages) => {
      const loaded = pages.reduce((count, page) => count + page.reports.length, 0);
      return loaded < lastPage.total ? loaded : undefined;
    },
    enabled: authorized,
    retry: false,
    meta: { privateData: true },
  });

  if (!authorized) {
    return (
      <Card className="p-6 text-center sm:p-8">
        <ShieldCheck className="mx-auto h-5 w-5 text-primary" aria-hidden />
        <h2 className="mt-4 font-display text-xl font-bold">Moderationsrechte erforderlich</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Dieses Konto darf private Meldungen nicht prüfen.
        </p>
      </Card>
    );
  }
  if (queue.isPending) {
    return <Spinner label="Prüfliste wird geladen…" className="min-h-[320px]" />;
  }
  if (queue.isError) {
    return (
      <ErrorState
        title="Die Prüfliste konnte nicht geladen werden"
        hint="Private Meldungen bleiben unverändert."
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
      {success && (
        <p role="status" className="rounded-xl border border-primary/30 bg-primary/5 px-4 py-3 text-sm text-foreground">
          {success}
        </p>
      )}
      {reports.length === 0 ? (
        <EmptyState
          icon={ClipboardCheck}
          title="Keine Meldung wartet auf Prüfung"
          hint="Neue private Meldungen erscheinen hier in Eingangsreihenfolge."
        />
      ) : (
        reports.map((report) => (
          <Card key={report.id} className={selectedId === report.id ? "border-primary/50" : undefined}>
            <button
              type="button"
              ref={(element) => {
                if (element) triggerRefs.current.set(report.id, element);
                else triggerRefs.current.delete(report.id);
              }}
              aria-label={`${report.text_preview} prüfen`}
              aria-expanded={selectedId === report.id}
              aria-controls={`moderation-detail-${report.id}`}
              onClick={() => {
                setSuccess(null);
                setSelectedId(report.id);
              }}
              className="flex w-full min-w-0 items-start gap-3 rounded-xl p-4 text-left transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary sm:p-5"
            >
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge color="blue">Offen zur Prüfung</Badge>
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
              <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
            </button>
            {selectedId === report.id && (
              <ModerationDetail
                report={report}
                onClose={() => closeDetail(report.id)}
                onDecided={async (outcome) => {
                  setSelectedId(null);
                  setSuccess(
                    outcome === "approved"
                      ? "Die Freigabe wurde gespeichert."
                      : "Die Ablehnung wurde gespeichert.",
                  );
                  await queryClient.invalidateQueries({
                    queryKey: ["private-report-moderation", user?.id],
                  });
                }}
              />
            )}
          </Card>
        ))
      )}
      {queue.hasNextPage && (
        <Button
          type="button"
          variant="secondary"
          className="w-full"
          disabled={queue.isFetchingNextPage}
          onClick={() => void queue.fetchNextPage()}
        >
          {queue.isFetchingNextPage ? "Weitere Meldungen werden geladen…" : "Weitere Meldungen laden"}
        </Button>
      )}
    </div>
  );
}

function ModerationDetail({
  report,
  onClose,
  onDecided,
}: {
  report: QueueReport;
  onClose: () => void;
  onDecided: (outcome: "approved" | "rejected") => Promise<void>;
}) {
  const queryClient = useQueryClient();
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [rejectionOpen, setRejectionOpen] = useState(false);
  const [explanation, setExplanation] = useState("");
  const explanationEdited = useRef(false);
  const [draftUnavailable, setDraftUnavailable] = useState(false);
  const [pendingDecision, setPendingDecision] = useState<"approved" | "rejected" | null>(null);
  const detail = useQuery({
    queryKey: ["private-report-moderation-detail", report.id],
    queryFn: () => api.get<Detail>(`/moderation/meldungen/${report.id}`),
    retry: false,
    meta: { privateData: true },
  });
  const draft = useMutation({
    mutationFn: (expectedRevision: number) => api.post<Draft>(
      `/moderation/meldungen/${report.id}/ablehnungsentwurf`,
      { expected_revision: expectedRevision },
    ),
    onSuccess: (result) => {
      if (result.suggestion && !explanationEdited.current) {
        setExplanation(result.suggestion);
      }
      setDraftUnavailable(!result.available);
    },
    onError: () => setDraftUnavailable(true),
  });
  const decision = useMutation({
    mutationFn: (input: {
      expected_revision: number;
      outcome: "approved" | "rejected";
      rejection_explanation: string | null;
    }) => api.post<Decision>(`/moderation/meldungen/${report.id}/entscheidung`, input),
    onSuccess: (result) => void onDecided(result.outcome),
  });

  useEffect(() => {
    if (detail.data) headingRef.current?.focus();
  }, [detail.data]);

  if (detail.isPending) {
    return <div className="border-t border-border"><Spinner label="Meldung wird geladen…" className="min-h-64" /></div>;
  }
  if (detail.isError) {
    return (
      <div className="border-t border-border p-5">
        <ErrorState
          title="Die Meldung ist nicht mehr prüfbar"
          hint="Vielleicht wurde sie bereits entschieden."
          onRetry={() => void detail.refetch()}
          busy={detail.isFetching}
        />
        <div className="mt-3 flex justify-center">
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              onClose();
              void queryClient.invalidateQueries({ queryKey: ["private-report-moderation"] });
            }}
          >
            Zur Prüfliste
          </Button>
        </div>
      </div>
    );
  }

  const current = detail.data;
  const error = decision.error instanceof ApiError ? decision.error.message : null;
  return (
    <section
      id={`moderation-detail-${report.id}`}
      className="min-w-0 border-t border-border p-5 sm:p-6"
      aria-labelledby={`moderation-${report.id}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">Private Meldung</p>
          <h2
            ref={headingRef}
            tabIndex={-1}
            id={`moderation-${report.id}`}
            className="mt-1 font-display text-xl font-bold outline-none"
          >
            Menschliche Prüfung
          </h2>
        </div>
        <Button type="button" variant="ghost" onClick={onClose}>Schließen</Button>
      </div>

      <div className="mt-5 space-y-4">
        {current.observations.map((observation, index) => (
          <section key={`${observation.observed_on}-${index}`} className="rounded-xl bg-muted/50 p-4">
            <h3 className="font-mono text-[10px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
              Beobachtung vom {formatDate(observation.observed_on)}
            </h3>
            <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-relaxed">
              {observation.text}
            </p>
          </section>
        ))}

        <section className="rounded-xl border border-border p-4">
          <h3 className="text-sm font-semibold">Automatische Hinweise</h3>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            Diese Hinweise unterstützen die Prüfung. Sie sind keine Wahrheit und keine automatische Entscheidung.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Badge color="slate">
              {current.local_outcome === "manual_review_only"
                ? "Nur manuell prüfen"
                : "Lokale Prüfung ohne Sperre"}
            </Badge>
            {current.ai_verdict && (
              <Badge color={current.ai_verdict === "suitable" ? "green" : "amber"}>
                {AUTOMATIC_VERDICTS[current.ai_verdict]}
              </Badge>
            )}
          </div>
          {current.ai_reason_code && (
            <p className="mt-3 text-sm text-muted-foreground">
              Begründung des automatischen Hinweises: {AUTOMATIC_REASONS[current.ai_reason_code]}
            </p>
          )}
          {current.local_reason_codes.length > 0 && (
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
              {current.local_reason_codes.map((reason) => (
                <li key={reason}>{LOCAL_REASONS[reason] ?? reason}</li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {rejectionOpen ? (
        <div className="mt-5 space-y-3 border-t border-border pt-5">
          <Label htmlFor={`rejection-${report.id}`}>Erklärung für die meldende Person</Label>
          <Textarea
            id={`rejection-${report.id}`}
            value={explanation}
            maxLength={1000}
            rows={5}
            onChange={(event) => {
              explanationEdited.current = true;
              setExplanation(event.target.value);
            }}
            placeholder="Schreibe eine sachliche, verständliche Erklärung."
          />
          <p className="text-xs text-muted-foreground">
            Die automatische Formulierungshilfe ist nur ein bearbeitbarer Entwurf. Du speicherst die endgültige Erklärung selbst.
          </p>
          {draft.isPending && <p role="status" className="text-sm text-muted-foreground">Entwurf wird erstellt…</p>}
          {draftUnavailable && (
            <p role="status" className="text-sm text-muted-foreground">
              Kein Entwurf verfügbar. Du kannst die Erklärung selbst schreiben oder erneut versuchen.
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="secondary"
              disabled={!explanation.trim() || decision.isPending}
              onClick={() => setPendingDecision("rejected")}
            >
              Ablehnung abschließend prüfen
            </Button>
            {draftUnavailable && (
              <Button type="button" variant="secondary" onClick={() => draft.mutate(current.content_revision)} disabled={draft.isPending}>
                Formulierungshilfe erneut versuchen
              </Button>
            )}
            <Button type="button" variant="ghost" onClick={() => setRejectionOpen(false)}>Abbrechen</Button>
          </div>
        </div>
      ) : (
        <div className="mt-5 flex flex-wrap gap-2 border-t border-border pt-5">
          <Button
            type="button"
            disabled={decision.isPending}
            onClick={() => setPendingDecision("approved")}
          >
            Als geprüft freigeben
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={() => {
              setRejectionOpen(true);
              draft.mutate(current.content_revision);
            }}
          >
            Ablehnung vorbereiten
          </Button>
        </div>
      )}

      {error && <p role="alert" className="mt-3 text-sm text-destructive">{error}</p>}
      <ConfirmDialog
        open={pendingDecision !== null}
        onOpenChange={(open) => !open && setPendingDecision(null)}
        title={pendingDecision === "rejected" ? "Meldung endgültig ablehnen?" : "Meldung freigeben?"}
        description={
          pendingDecision === "rejected"
            ? "Die Ablehnung und deine Erklärung sind endgültig. Die meldende Person kann danach nichts mehr ergänzen."
            : "Die Freigabe ist endgültig. Sie veröffentlicht, versendet und weist die Meldung nicht automatisch zu."
        }
        confirmLabel={pendingDecision === "rejected" ? "Ablehnung verbindlich speichern" : "Als geprüft freigeben"}
        variant={pendingDecision === "rejected" ? "danger" : "primary"}
        onConfirm={() => {
          if (!pendingDecision) return;
          decision.mutate({
            expected_revision: current.content_revision,
            outcome: pendingDecision,
            rejection_explanation: pendingDecision === "rejected" ? explanation.trim() : null,
          });
          setPendingDecision(null);
        }}
      />
    </section>
  );
}
