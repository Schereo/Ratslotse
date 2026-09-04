"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  Loader2,
  MapPin,
  MessageSquareText,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  clearProblemReportSession,
  loadProblemReportSession,
  oldenburgTodayISO,
  saveProblemReportSession,
  scheduleProblemReportSessionExpiry,
  type PrivateReport,
  type ReportCategory,
  type ReportContent,
  type ReportScope,
  type ReportStage,
} from "@/lib/problem-report-session";
import { PROBLEM_KATEGORIEN, PROBLEM_MELDEBEZUEGE } from "@/lib/probleme";
import { Button, Card, Input, Label, Select, Spinner, Textarea } from "@/components/ui";

const LocationPicker = dynamic(
  () => import("@/components/problem-report-location-picker").then((module) => module.ProblemReportLocationPicker),
  {
    ssr: false,
    loading: () => <div className="h-72 motion-safe:animate-pulse rounded-xl border border-border bg-muted" />,
  },
);

const CATEGORIES = Object.entries(PROBLEM_KATEGORIEN) as [ReportCategory, string][];
const STAGE_NUMBER: Record<Exclude<ReportStage, "review">, number> = {
  scope: 1,
  location: 2,
  date: 3,
  category: 4,
  description: 5,
};

type CompleteReportContent = Omit<ReportContent, "category" | "scope_kind"> & {
  category: ReportCategory;
  scope_kind: ReportScope;
};

function emptyContent(): ReportContent {
  return {
    text: "",
    category: "",
    scope_kind: null,
    observed_on: oldenburgTodayISO(),
    location_label: "",
    latitude: null,
    longitude: null,
  };
}

function freshIdempotencyKey(): string {
  return crypto.randomUUID();
}

function contentFromReport(report: PrivateReport): CompleteReportContent {
  return {
    text: report.draft_text,
    category: report.category,
    scope_kind: report.scope_kind,
    observed_on: report.observed_on,
    location_label: report.location_label,
    latitude: report.latitude,
    longitude: report.longitude,
  };
}

type ContentErrors = {
  date: string | null;
  location: string | null;
  description: string | null;
};

function validISODate(value: string): boolean {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match || Number(match[1]) < 1) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.valueOf()) && parsed.toISOString().slice(0, 10) === value;
}

function validateReportContent(content: ReportContent): {
  normalized: CompleteReportContent | null;
  errors: ContentErrors;
} {
  const text = content.text.trim();
  const location = content.location_label.trim();
  const errors: ContentErrors = {
    date: !content.observed_on
      ? "Gib ein Beobachtungsdatum an."
      : !validISODate(content.observed_on)
        ? "Gib ein gültiges Beobachtungsdatum an."
        : content.observed_on > oldenburgTodayISO() ? "Das Datum darf nicht in der Zukunft liegen." : null,
    location: content.scope_kind === "citywide"
      ? null
      : !location
        ? "Gib den privaten Ort an."
        : content.latitude === null || content.longitude === null
          ? "Markiere die private Lage auf der Karte."
          : null,
    description: !text
      ? "Beschreibe deine eigene Beobachtung."
      : text.length > 4000 ? "Die Beschreibung darf höchstens 4000 Zeichen lang sein." : null,
  };
  if (!content.scope_kind || !content.category || Object.values(errors).some(Boolean)) {
    return { normalized: null, errors };
  }
  return {
    errors,
    normalized: {
      ...content,
      text,
      category: content.category,
      scope_kind: content.scope_kind,
      location_label: content.scope_kind === "citywide" ? "" : location,
      latitude: content.scope_kind === "citywide" ? null : content.latitude,
      longitude: content.scope_kind === "citywide" ? null : content.longitude,
    },
  };
}

function sameContent(left: CompleteReportContent, right: CompleteReportContent): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function friendlyError(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

function Question({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-3">
      <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
        <MessageSquareText className="h-4 w-4" aria-hidden />
      </span>
      <div className="min-w-0 flex-1 rounded-2xl rounded-tl-sm border border-border bg-card px-4 py-3 text-sm leading-relaxed shadow-sm">
        {children}
      </div>
    </div>
  );
}

function BackButton({ onClick, disabled = false }: { onClick: () => void; disabled?: boolean }) {
  return (
    <Button type="button" variant="ghost" onClick={onClick} disabled={disabled}>
      <ArrowLeft aria-hidden /> Zurück
    </Button>
  );
}

export function ProblemReportFlow() {
  const { user } = useAuth();
  const [content, setContent] = useState<ReportContent>(emptyContent);
  const [stage, setStage] = useState<ReportStage>("scope");
  const [idempotencyKey, setIdempotencyKey] = useState("");
  const [reportId, setReportId] = useState<number | null>(null);
  const [creationContent, setCreationContent] = useState<ReportContent | null>(null);
  const [serverReport, setServerReport] = useState<PrivateReport | null>(null);
  const [submitted, setSubmitted] = useState<PrivateReport | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const [recovering, setRecovering] = useState(false);
  const [busy, setBusy] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const completionHeadingRef = useRef<HTMLHeadingElement>(null);
  const previousStage = useRef<ReportStage>(stage);
  const recoveryAttempt = useRef<number | null>(null);
  const focusAfterRecovery = useRef(false);

  const resetLocal = useCallback((message?: string) => {
    clearProblemReportSession();
    setContent(emptyContent());
    setStage("scope");
    setIdempotencyKey(freshIdempotencyKey());
    setReportId(null);
    setCreationContent(null);
    setServerReport(null);
    setSubmitted(null);
    setConfirmed(false);
    setConflict(false);
    setError(null);
    setNotice(message ?? null);
  }, []);

  useEffect(() => {
    if (!user) return;
    if (user.role === "admin") {
      setHydrated(true);
      return;
    }
    setHydrated(false);
    recoveryAttempt.current = null;
    const saved = loadProblemReportSession(user.id);
    if (saved) {
      setContent(saved.content);
      setStage(saved.reportId === null ? saved.stage : "review");
      setIdempotencyKey(saved.idempotencyKey);
      setReportId(saved.reportId);
      setCreationContent(saved.creationContent);
      setServerReport(null);
      setSubmitted(null);
      setNotice(null);
    } else {
      setContent(emptyContent());
      setStage("scope");
      setIdempotencyKey(freshIdempotencyKey());
      setReportId(null);
      setCreationContent(null);
      setServerReport(null);
      setSubmitted(null);
    }
    setHydrated(true);
  }, [user]);

  const loadServerReport = useCallback(async (id: number) => {
    focusAfterRecovery.current = true;
    setRecovering(true);
    setError(null);
    setConflict(false);
    try {
      const report = await api.get<PrivateReport>(`/meldungen/${id}`);
      setCreationContent(null);
      if (report.state === "submitted") {
        clearProblemReportSession();
        setSubmitted(report);
        setServerReport(report);
        return;
      }
      setContent(contentFromReport(report));
      setServerReport(report);
      setStage("review");
      setReportId(report.id);
      setConfirmed(false);
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 404) {
        resetLocal("Der gespeicherte Entwurf ist nicht mehr verfügbar. Du kannst neu beginnen.");
      } else {
        setError(friendlyError(caught, "Der Entwurf konnte nicht geladen werden."));
      }
    } finally {
      setRecovering(false);
    }
  }, [resetLocal]);

  useEffect(() => {
    if (!hydrated || reportId === null || serverReport || submitted) return;
    if (recoveryAttempt.current === reportId) return;
    recoveryAttempt.current = reportId;
    void loadServerReport(reportId);
  }, [hydrated, loadServerReport, reportId, serverReport, submitted]);

  useEffect(() => {
    if (!hydrated || !user || user.role === "admin" || !idempotencyKey || submitted) return;
    const savedAt = Date.now();
    saveProblemReportSession({
      version: 1,
      ownerId: user.id,
      savedAt,
      stage,
      idempotencyKey,
      reportId,
      content,
      creationContent,
    });
    return scheduleProblemReportSessionExpiry(savedAt);
  }, [content, creationContent, hydrated, idempotencyKey, reportId, stage, submitted, user]);

  useEffect(() => {
    if (previousStage.current === stage) return;
    previousStage.current = stage;
    headingRef.current?.focus();
  }, [stage]);

  useEffect(() => {
    if (!focusAfterRecovery.current || recovering || !headingRef.current) return;
    headingRef.current.focus();
    focusAfterRecovery.current = false;
  }, [recovering, serverReport, stage]);

  useEffect(() => {
    completionHeadingRef.current?.focus();
  }, [submitted]);

  const patchContent = (patch: Partial<ReportContent>) => {
    setContent((current) => ({ ...current, ...patch }));
    setConfirmed(false);
    setError(null);
    setConflict(false);
  };

  const chooseScope = (scope: ReportScope) => {
    patchContent({
      scope_kind: scope,
      ...(scope === "citywide" ? { location_label: "", latitude: null, longitude: null } : {}),
    });
    setStage(scope === "citywide" ? "date" : "location");
  };

  const prepareReview = async () => {
    const complete = validateReportContent(content).normalized;
    if (!complete) {
      setError("Bitte vervollständige deine Angaben, bevor du den Entwurf prüfst.");
      return;
    }
    if (serverReport) {
      setStage("review");
      return;
    }
    const firstAttempt = creationContent ? validateReportContent(creationContent).normalized : complete;
    if (!firstAttempt) {
      setCreationContent(null);
      setError("Der frühere Anlegeversuch ist nicht mehr gültig. Bitte versuche es erneut.");
      return;
    }
    if (!creationContent) setCreationContent(firstAttempt);
    setBusy(true);
    setError(null);
    try {
      const report = await api.post<PrivateReport>("/meldungen/entwuerfe", {
        ...firstAttempt,
        idempotency_key: idempotencyKey,
      });
      setReportId(report.id);
      setCreationContent(null);
      setServerReport(report);
      setContent(complete);
      if (report.state === "submitted") {
        clearProblemReportSession();
        setSubmitted(report);
      } else {
        setStage("review");
      }
    } catch (caught) {
      if (caught instanceof ApiError && caught.status >= 400 && caught.status < 500 && caught.status !== 409) {
        setCreationContent(null);
      }
      setError(friendlyError(caught, "Der private Entwurf konnte nicht angelegt werden."));
    } finally {
      setBusy(false);
    }
  };

  const submitReport = async () => {
    const complete = validateReportContent(content).normalized;
    if (!confirmed || !complete || !serverReport || reportId === null) {
      setError("Bitte prüfe und bestätige zuerst alle Angaben.");
      return;
    }
    setBusy(true);
    setError(null);
    setConflict(false);
    try {
      let currentReport = serverReport;
      if (!sameContent(complete, contentFromReport(serverReport))) {
        currentReport = await api.put<PrivateReport>(`/meldungen/${reportId}/entwurf`, {
          ...complete,
          expected_revision: serverReport.content_revision,
        });
        setServerReport(currentReport);
      }
      const result = await api.post<PrivateReport>(`/meldungen/${reportId}/absenden`, {
        expected_revision: currentReport.content_revision,
        confirmed_text: complete.text,
      });
      clearProblemReportSession();
      setServerReport(result);
      setSubmitted(result);
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409) {
        setConflict(true);
        setError("Auf dem Server liegt inzwischen ein neuerer Stand. Deine Eingabe wurde nicht überschrieben.");
      } else {
        setError(friendlyError(caught, "Die Meldung konnte nicht abgesendet werden."));
      }
    } finally {
      setBusy(false);
    }
  };

  if (!user || !hydrated) {
    return <Spinner label="Meldeweg wird geladen…" className="min-h-[420px]" />;
  }

  if (user.role === "admin") {
    return (
      <Card className="p-6 text-center sm:p-8">
        <ShieldCheck className="mx-auto h-10 w-10 text-primary" aria-hidden />
        <h2 className="mt-4 font-display text-xl font-bold text-foreground">Persönliche Meldungen sind Bürgerkonten vorbehalten</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Admin-Konten moderieren getrennt und können deshalb keine eigene Meldung abgeben.
        </p>
        <Button asChild variant="secondary" className="mt-5"><Link href="/probleme">Zur Problemübersicht</Link></Button>
      </Card>
    );
  }

  if (submitted) {
    return (
      <Card className="px-6 py-10 text-center sm:px-10">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-green-100 text-green-700 dark:bg-green-950/40 dark:text-green-300">
          <CheckCircle2 className="h-6 w-6" aria-hidden />
        </span>
        <h2 ref={completionHeadingRef} tabIndex={-1} className="mt-4 font-display text-xl font-bold text-foreground outline-none">Meldung privat eingegangen</h2>
        <p className="mx-auto mt-2 max-w-lg text-sm leading-relaxed text-muted-foreground">
          Sie ist nicht automatisch öffentlich.
        </p>
        <Button asChild variant="secondary" className="mt-5"><Link href="/probleme">Zur Problemübersicht</Link></Button>
      </Card>
    );
  }

  if (recovering) {
    return <Spinner label="Privater Entwurf wird geladen…" className="min-h-[420px] rounded-xl border border-border bg-card" />;
  }

  const step = stage === "review" ? null : STAGE_NUMBER[stage];
  const contentErrors = validateReportContent(content).errors;

  return (
    <div className="space-y-4">
      {notice && <p role="status" className="rounded-xl border border-primary/20 bg-primary/5 px-4 py-3 text-sm text-foreground">{notice}</p>}
      {step !== null && (
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
          Schritt {step} von 5
        </p>
      )}

      <Card className="overflow-hidden bg-muted/35 p-4 sm:p-6">
        {stage === "scope" && (
          <QuestionStage headingRef={headingRef} title="Worauf bezieht sich deine Beobachtung?">
            <div className="grid gap-2 sm:grid-cols-2">
              {PROBLEM_MELDEBEZUEGE.map((scope) => (
                <button
                  key={scope.value}
                  type="button"
                  onClick={() => chooseScope(scope.value)}
                  className="min-h-16 rounded-xl border border-primary/25 bg-card px-4 py-3 text-left transition-colors hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <strong className="block text-sm text-foreground">{scope.label}</strong>
                  <span className="mt-0.5 block text-xs leading-relaxed text-muted-foreground">{scope.hint}</span>
                </button>
              ))}
            </div>
          </QuestionStage>
        )}

        {stage === "location" && (
          <QuestionStage headingRef={headingRef} title="Wo genau ist das Problem?">
            <div className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="report-location">Ortsangabe</Label>
                <Input
                  id="report-location"
                  value={content.location_label}
                  maxLength={200}
                  autoComplete="off"
                  placeholder="Straße, Abschnitt oder Einrichtung"
                  onChange={(event) => patchContent({ location_label: event.target.value })}
                />
                <p className="text-xs text-muted-foreground">Diese genaue Angabe bleibt Teil deiner privaten Meldung.</p>
              </div>
              <LocationPicker
                value={content.latitude === null || content.longitude === null
                  ? null
                  : { latitude: content.latitude, longitude: content.longitude }}
                onChange={(position) => patchContent(position)}
              />
              <div className="flex flex-wrap items-center justify-between gap-2">
                <BackButton onClick={() => setStage("scope")} />
                <Button
                  type="button"
                  disabled={contentErrors.location !== null}
                  onClick={() => setStage("date")}
                >
                  Ort übernehmen
                </Button>
              </div>
            </div>
          </QuestionStage>
        )}

        {stage === "date" && (
          <QuestionStage headingRef={headingRef} title="Wann hast du das selbst beobachtet?">
            <div className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="report-date">Beobachtungsdatum</Label>
                <Input
                  id="report-date"
                  type="date"
                  max={oldenburgTodayISO()}
                  value={content.observed_on}
                  onChange={(event) => patchContent({ observed_on: event.target.value })}
                />
                {content.observed_on && contentErrors.date && <p role="alert" className="text-sm text-destructive">{contentErrors.date}</p>}
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <BackButton onClick={() => setStage(content.scope_kind === "citywide" ? "scope" : "location")} />
                <Button
                  type="button"
                  disabled={contentErrors.date !== null}
                  onClick={() => setStage("category")}
                >
                  Datum übernehmen
                </Button>
              </div>
            </div>
          </QuestionStage>
        )}

        {stage === "category" && (
          <QuestionStage headingRef={headingRef} title="Worum geht es?">
            <div className="grid gap-2 sm:grid-cols-2">
              {CATEGORIES.map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => { patchContent({ category: value }); setStage("description"); }}
                  className="min-h-12 rounded-xl border border-primary/25 bg-card px-4 py-3 text-left text-sm font-medium text-foreground transition-colors hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="mt-3"><BackButton onClick={() => setStage("date")} /></div>
          </QuestionStage>
        )}

        {stage === "description" && (
          <QuestionStage headingRef={headingRef} title="Was hast du selbst beobachtet?">
            <div className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="report-observation">Eigene Beobachtung</Label>
                <Textarea
                  id="report-observation"
                  value={content.text}
                  maxLength={4000}
                  rows={7}
                  placeholder="Beschreibe konkret, was du gesehen oder erlebt hast."
                  onChange={(event) => patchContent({ text: event.target.value })}
                  disabled={busy}
                />
                <p className="text-right text-xs tabular-nums text-muted-foreground">{content.text.length} / 4000</p>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <BackButton onClick={() => setStage("category")} disabled={busy} />
                <Button type="button" disabled={contentErrors.description !== null || busy} onClick={() => void prepareReview()}>
                  {busy ? <><Loader2 className="animate-spin" aria-hidden /> Entwurf wird angelegt…</> : "Entwurf prüfen"}
                </Button>
              </div>
            </div>
          </QuestionStage>
        )}

        {stage === "review" && serverReport && (
          <Review
            headingRef={headingRef}
            content={content}
            confirmed={confirmed}
            busy={busy}
            onPatch={patchContent}
            onConfirm={setConfirmed}
            onBack={() => setStage("description")}
            onChooseLocation={() => setStage("location")}
            onSubmit={() => void submitReport()}
          />
        )}
      </Card>

      {error && (
        <div role="alert" className="rounded-xl border border-destructive/25 bg-destructive/5 px-4 py-3 text-sm text-foreground">
          <div className="flex items-start gap-2">
            <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden />
            <p className="flex-1">{error}</p>
          </div>
          {(conflict || !serverReport) && reportId !== null && (
            <Button type="button" variant="secondary" size="sm" className="mt-3" onClick={() => void loadServerReport(reportId)} disabled={recovering}>
              {conflict ? "Neueren Entwurf laden" : "Entwurf erneut laden"}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

function QuestionStage({
  headingRef,
  title,
  children,
}: {
  headingRef: React.RefObject<HTMLHeadingElement>;
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-5">
      <Question><h2 ref={headingRef} tabIndex={-1} className="font-display text-lg font-bold outline-none">{title}</h2></Question>
      <div className="ml-0 sm:ml-12">{children}</div>
    </div>
  );
}

function Review({
  headingRef,
  content,
  confirmed,
  busy,
  onPatch,
  onConfirm,
  onBack,
  onChooseLocation,
  onSubmit,
}: {
  headingRef: React.RefObject<HTMLHeadingElement>;
  content: ReportContent;
  confirmed: boolean;
  busy: boolean;
  onPatch: (patch: Partial<ReportContent>) => void;
  onConfirm: (confirmed: boolean) => void;
  onBack: () => void;
  onChooseLocation: () => void;
  onSubmit: () => void;
}) {
  const changeScope = (scope: ReportScope) => onPatch({
    scope_kind: scope,
    ...(scope === "citywide" ? { location_label: "", latitude: null, longitude: null } : {}),
  });
  const validation = validateReportContent(content);
  const complete = validation.normalized !== null;
  const { date: dateError, location: locationError, description: descriptionError } = validation.errors;

  return (
    <div className="space-y-5">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
          <ShieldCheck className="h-4 w-4" aria-hidden />
        </span>
        <div>
          <h2 ref={headingRef} tabIndex={-1} className="font-display text-lg font-bold text-foreground outline-none">Meldung prüfen</h2>
          <p className="mt-1 text-sm text-muted-foreground">Korrigiere alles, was noch nicht genau deiner Beobachtung entspricht.</p>
        </div>
      </div>

      <div className="grid gap-4 rounded-xl border border-border bg-card p-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="review-scope">Räumlicher Bezug</Label>
          <Select id="review-scope" value={content.scope_kind ?? ""} onChange={(event) => changeScope(event.target.value as ReportScope)} disabled={busy}>
            {PROBLEM_MELDEBEZUEGE.map((scope) => <option key={scope.value} value={scope.value}>{scope.label}</option>)}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="review-date">Beobachtungsdatum</Label>
          <Input
            id="review-date"
            type="date"
            max={oldenburgTodayISO()}
            value={content.observed_on}
            aria-invalid={!!dateError}
            aria-describedby={dateError ? "review-date-error" : undefined}
            onChange={(event) => onPatch({ observed_on: event.target.value })}
            disabled={busy}
          />
          {dateError && <p id="review-date-error" role="alert" className="text-sm text-destructive">{dateError}</p>}
        </div>
        <div className="space-y-1.5 sm:col-span-2">
          <Label htmlFor="review-category">Kategorie</Label>
          <Select id="review-category" value={content.category} onChange={(event) => onPatch({ category: event.target.value as ReportCategory })} disabled={busy}>
            {CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </Select>
        </div>
        {content.scope_kind !== "citywide" && (
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="review-location">Ortsangabe</Label>
            <Input
              id="review-location"
              value={content.location_label}
              maxLength={200}
              aria-invalid={!!locationError}
              aria-describedby={locationError ? "review-location-error" : undefined}
              onChange={(event) => onPatch({ location_label: event.target.value })}
              disabled={busy}
            />
            {locationError && <p id="review-location-error" role="alert" className="text-sm text-destructive">{locationError}</p>}
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1"><MapPin className="h-3.5 w-3.5" aria-hidden /> {content.latitude === null ? "Keine Lage markiert" : "Private Lage markiert"}</span>
              <button type="button" onClick={onChooseLocation} disabled={busy} className="min-h-10 rounded-lg px-2 font-medium text-primary hover:bg-primary/5 hover:underline disabled:pointer-events-none disabled:opacity-50">Ort auf der Karte ändern</button>
            </div>
          </div>
        )}
        <div className="space-y-1.5 sm:col-span-2">
          <Label htmlFor="review-description">Beschreibung</Label>
          <Textarea
            id="review-description"
            value={content.text}
            maxLength={4000}
            rows={7}
            aria-invalid={!!descriptionError}
            aria-describedby={descriptionError ? "review-description-error" : undefined}
            onChange={(event) => onPatch({ text: event.target.value })}
            disabled={busy}
          />
          {descriptionError && <p id="review-description-error" role="alert" className="text-sm text-destructive">{descriptionError}</p>}
          <p className="text-right text-xs tabular-nums text-muted-foreground">{content.text.length} / 4000</p>
        </div>
      </div>

      <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-primary/20 bg-primary/5 p-4 text-sm leading-relaxed text-foreground">
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(event) => onConfirm(event.target.checked)}
          disabled={busy}
          className="mt-0.5 h-5 w-5 shrink-0 rounded border-input accent-primary"
        />
        <span>Ich habe meine Angaben selbst geprüft. Der Text beschreibt meine eigene Beobachtung.</span>
      </label>

      <p className="text-xs leading-relaxed text-muted-foreground">
        Deine Meldung bleibt privat und wird durch das Absenden nicht automatisch veröffentlicht.
      </p>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <BackButton onClick={onBack} disabled={busy} />
        <Button type="button" disabled={!confirmed || !complete || busy} onClick={onSubmit}>
          {busy ? <><Loader2 className="animate-spin" aria-hidden /> Wird privat gesendet…</> : "Meldung privat absenden"}
        </Button>
      </div>
    </div>
  );
}

export function ProblemReportDisclosures() {
  return (
    <div className="space-y-3">
      <aside className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-relaxed text-amber-950 dark:border-amber-900 dark:bg-amber-950/35 dark:text-amber-100">
        <strong>Kein Notrufkanal.</strong> Bei akuter Gefahr wähle 112.
      </aside>
      <p className="text-center text-xs leading-relaxed text-muted-foreground">
        Ratslotse ist ein privates Bürgerprojekt und kein Angebot der Stadt Oldenburg.
      </p>
    </div>
  );
}
