"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Bot, CheckCircle2, Loader2, MapPin, Send, ShieldCheck, Sparkles, UserRound } from "lucide-react";
import { ApiError, api } from "@/lib/api";
import { entwurfAbholen, entwurfMelden } from "@/lib/draft";
import {
  clearProblemReportDraft,
  PROBLEM_REPORT_DRAFT_STORAGE,
  scheduleProblemReportDraftExpiry,
} from "@/lib/problem-report-draft";
import { useAuth } from "@/lib/auth";
import { PROBLEM_KATEGORIEN, PROBLEM_SCOPE } from "@/lib/probleme";
import type { ProblemListResponse, ProblemScope, PublicProblemSummary } from "@/lib/types";
import { Badge, Button, Card, Input, Label, Textarea } from "@/components/ui";
import { cn } from "@/lib/utils";

const LocationPicker = dynamic(
  () => import("@/components/problem-location-picker").then((module) => module.ProblemLocationPicker),
  { ssr: false, loading: () => <div className="h-72 animate-pulse rounded-xl border border-border bg-muted" /> },
);

const SCOPES: { value: ProblemScope; label: string; hint: string }[] = [
  { value: "point", label: "Ein Ort", hint: "Querung, Kreuzung oder einzelner Platz" },
  { value: "facility", label: "Einrichtung", hint: "Schule, Kita, Haltestelle oder Gebäude" },
  { value: "route", label: "Straße oder Strecke", hint: "Abschnitt oder Verbindung" },
  { value: "area", label: "Gebiet", hint: "Quartier, Stadtteil oder größerer Bereich" },
  { value: "citywide", label: "Ganz Oldenburg", hint: "kein einzelner Ort wäre ehrlich" },
];

const STAGES = ["scope", "location", "match", "date", "consent", "chat", "review"] as const;
type ChatStage = (typeof STAGES)[number];
type Position = { latitude: number; longitude: number } | null;
type AssistantAnswer = { question: string; answer: string };
type ReportCategory = keyof typeof PROBLEM_KATEGORIEN;

type AssistantResponse = {
  kind: "question" | "ready";
  question: string | null;
  draft_text: string | null;
  category: ReportCategory | null;
  category_detail: string | null;
  redacted: boolean;
};

type SavedReportForm = {
  ownerId: number;
  savedAt: number;
  stage: ChatStage;
  step?: number;
  scope: ProblemScope | null;
  locationLabel: string;
  position: Position;
  category: string;
  categoryDetail: string;
  text: string;
  observedOn: string;
  suggestedProblem: PublicProblemSummary | null;
  noMatchingProblem: boolean;
  draftId: number | null;
  clientToken: string;
  assistantConsent: boolean;
  assistantQuestion: string;
  assistantInput: string;
  assistantAnswers: AssistantAnswer[];
  assistantRedacted: boolean;
};

type PrivateReport = {
  id: number;
  status: "draft" | "submitted" | "in_review" | "needs_information" | "accepted" | "rejected" | "withdrawn";
  confirmed_text: string | null;
};

function todayISO(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

function displayDate(value: string): string {
  if (!value) return "";
  return new Intl.DateTimeFormat("de-DE", { dateStyle: "long" }).format(new Date(`${value}T12:00:00`));
}

function segmentNear(
  point: { latitude: number; longitude: number },
  start: number[],
  end: number[],
): boolean {
  const px = point.longitude / 0.03;
  const py = point.latitude / 0.018;
  const ax = start[0] / 0.03;
  const ay = start[1] / 0.018;
  const bx = end[0] / 0.03;
  const by = end[1] / 0.018;
  const lengthSquared = (bx - ax) ** 2 + (by - ay) ** 2;
  const ratio = lengthSquared === 0
    ? 0
    : Math.max(0, Math.min(1, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / lengthSquared));
  return (px - (ax + ratio * (bx - ax))) ** 2 + (py - (ay + ratio * (by - ay))) ** 2 < 1;
}

function pointInRing(point: { latitude: number; longitude: number }, ring: number[][]): boolean {
  let inside = false;
  for (let index = 0, previous = ring.length - 1; index < ring.length; previous = index++) {
    const [x, y] = ring[index];
    const [previousX, previousY] = ring[previous];
    if (
      (y > point.latitude) !== (previousY > point.latitude)
      && point.longitude < ((previousX - x) * (point.latitude - y)) / (previousY - y) + x
    ) inside = !inside;
  }
  return inside;
}

function geometryNear(problem: PublicProblemSummary, position: NonNullable<Position>): boolean {
  const geometry = problem.geometry;
  if (geometry?.type === "LineString") {
    return geometry.coordinates.slice(1).some((end, index) =>
      segmentNear(position, geometry.coordinates[index] as number[], end as number[]));
  }
  const polygons = geometry?.type === "Polygon"
    ? [geometry.coordinates]
    : geometry?.type === "MultiPolygon" ? geometry.coordinates : [];
  return polygons.some((polygon) => {
    const outer = polygon[0] as number[][] | undefined;
    if (!outer) return false;
    return pointInRing(position, outer)
      || outer.slice(1).some((end, index) => segmentNear(position, outer[index], end));
  });
}

function nearby(problem: PublicProblemSummary, scope: ProblemScope, position: Position, label: string): boolean {
  if (scope === "citywide") return problem.scope_kind === "citywide";
  const normalized = label.trim().toLocaleLowerCase("de-DE");
  const labelMatch = normalized.length >= 3 && problem.location_label.toLocaleLowerCase("de-DE").includes(normalized);
  const coordinateMatch = position && (
    (
      problem.latitude !== null
      && problem.longitude !== null
      && Math.abs(problem.latitude - position.latitude) < 0.018
      && Math.abs(problem.longitude - position.longitude) < 0.03
    )
    || geometryNear(problem, position)
  );
  return Boolean(labelMatch || coordinateMatch);
}

function BotBubble({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-2.5">
      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
        <Bot className="h-4 w-4" aria-hidden />
      </span>
      <div className="max-w-[88%] rounded-2xl rounded-tl-sm border border-border bg-card px-4 py-3 text-sm leading-relaxed text-foreground shadow-sm">
        {children}
      </div>
    </div>
  );
}

function UserBubble({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start justify-end gap-2.5">
      <div className="max-w-[88%] rounded-2xl rounded-tr-sm bg-primary px-4 py-3 text-sm leading-relaxed text-primary-foreground">
        {children}
      </div>
      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <UserRound className="h-4 w-4" aria-hidden />
      </span>
    </div>
  );
}

export function ProblemReportFlow() {
  const { user } = useAuth();
  const [stage, setStage] = useState<ChatStage>("scope");
  const [scope, setScope] = useState<ProblemScope | null>(null);
  const [locationLabel, setLocationLabel] = useState("");
  const [position, setPosition] = useState<Position>(null);
  const [category, setCategory] = useState<string>("");
  const [categoryDetail, setCategoryDetail] = useState("");
  const [text, setText] = useState("");
  const [observedOn, setObservedOn] = useState(todayISO());
  const [suggestedProblem, setSuggestedProblem] = useState<PublicProblemSummary | null>(null);
  const [noMatchingProblem, setNoMatchingProblem] = useState(false);
  const [confirmedText, setConfirmedText] = useState<string | null>(null);
  const [draftId, setDraftId] = useState<number | null>(null);
  const [clientToken, setClientToken] = useState("");
  const [hydrated, setHydrated] = useState(false);
  const [submitted, setSubmitted] = useState<PrivateReport | null>(null);
  const [assistantConsent, setAssistantConsent] = useState(false);
  const [assistantQuestion, setAssistantQuestion] = useState("Erzähl mir kurz: Was hast du selbst beobachtet?");
  const [assistantInput, setAssistantInput] = useState("");
  const [assistantAnswers, setAssistantAnswers] = useState<AssistantAnswer[]>([]);
  const [assistantRedacted, setAssistantRedacted] = useState(false);
  const textRef = useRef(text);
  const stageHeadingRef = useRef<HTMLHeadingElement>(null);
  const previousStageRef = useRef(stage);
  textRef.current = text;

  const stageAtLeast = (candidate: ChatStage) => STAGES.indexOf(stage) >= STAGES.indexOf(candidate);

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(PROBLEM_REPORT_DRAFT_STORAGE);
      if (raw) {
        const saved = JSON.parse(raw) as Partial<SavedReportForm>;
        if (
          typeof saved.savedAt !== "number"
          || Date.now() - saved.savedAt > 30 * 60 * 1_000
          || saved.ownerId !== user?.id
        ) throw new Error("Ungültiger Meldeentwurf");
        if (saved.stage && STAGES.includes(saved.stage)) {
          setStage(saved.stage);
        } else if (saved.step === 2) {
          setStage("review");
        } else if (saved.step === 1) {
          setStage("chat");
        }
        if (saved.scope === null || SCOPES.some((item) => item.value === saved.scope)) setScope(saved.scope ?? null);
        if (typeof saved.locationLabel === "string") setLocationLabel(saved.locationLabel);
        if (saved.position === null || (
          typeof saved.position?.latitude === "number" && typeof saved.position?.longitude === "number"
        )) setPosition(saved.position ?? null);
        if (typeof saved.category === "string") setCategory(saved.category);
        if (typeof saved.categoryDetail === "string") setCategoryDetail(saved.categoryDetail);
        if (typeof saved.text === "string") setText(saved.text);
        if (typeof saved.observedOn === "string") setObservedOn(saved.observedOn);
        if (saved.suggestedProblem && typeof saved.suggestedProblem.id === "number") setSuggestedProblem(saved.suggestedProblem);
        setNoMatchingProblem(saved.noMatchingProblem === true);
        if (typeof saved.draftId === "number") setDraftId(saved.draftId);
        setAssistantConsent(saved.assistantConsent === true);
        if (typeof saved.assistantQuestion === "string" && saved.assistantQuestion) setAssistantQuestion(saved.assistantQuestion);
        if (typeof saved.assistantInput === "string") setAssistantInput(saved.assistantInput);
        if (Array.isArray(saved.assistantAnswers)) {
          setAssistantAnswers(saved.assistantAnswers.filter((answer): answer is AssistantAnswer =>
            typeof answer?.question === "string" && typeof answer?.answer === "string"));
        }
        setAssistantRedacted(saved.assistantRedacted === true);
        setClientToken(typeof saved.clientToken === "string" && saved.clientToken ? saved.clientToken : crypto.randomUUID());
      } else {
        const recovered = entwurfAbholen("private-problemmeldung");
        if (recovered) setText(recovered);
        setClientToken(crypto.randomUUID());
      }
    } catch {
      clearProblemReportDraft();
      setClientToken(crypto.randomUUID());
    }
    setHydrated(true);
    return entwurfMelden("private-problemmeldung", () => textRef.current);
  }, [user?.id]);

  useEffect(() => {
    if (!hydrated || submitted || !user) return;
    const snapshot: SavedReportForm = {
      ownerId: user.id,
      savedAt: Date.now(),
      stage,
      scope,
      locationLabel,
      position,
      category,
      categoryDetail,
      text,
      observedOn,
      suggestedProblem,
      noMatchingProblem,
      draftId,
      clientToken,
      assistantConsent,
      assistantQuestion,
      assistantInput,
      assistantAnswers,
      assistantRedacted,
    };
    try {
      sessionStorage.setItem(PROBLEM_REPORT_DRAFT_STORAGE, JSON.stringify(snapshot));
      scheduleProblemReportDraftExpiry();
    } catch { /* session recovery is optional */ }
  }, [
    hydrated, submitted, user, stage, scope, locationLabel, position, category,
    categoryDetail, text, observedOn, suggestedProblem, noMatchingProblem,
    draftId, clientToken, assistantConsent, assistantQuestion, assistantInput,
    assistantAnswers, assistantRedacted,
  ]);

  useEffect(() => {
    if (!hydrated) return;
    if (scope === null && stage !== "scope") {
      setStage("scope");
    } else if (
      scope !== null
      && scope !== "citywide"
      && STAGES.indexOf(stage) >= STAGES.indexOf("match")
      && (locationLabel.trim().length < 2 || position === null)
    ) {
      setStage("location");
    }
  }, [hydrated, scope, stage, locationLabel, position]);

  useEffect(() => {
    if (previousStageRef.current === stage) return;
    previousStageRef.current = stage;
    stageHeadingRef.current?.focus();
  }, [stage]);

  const publicProblems = useQuery({
    queryKey: ["public-problems-for-report"],
    queryFn: () => api.get<ProblemListResponse>("/probleme"),
    staleTime: 60_000,
    retry: 1,
  });
  const suggestions = useMemo(() => {
    if (!scope) return [];
    return (publicProblems.data?.problems ?? [])
      .filter((problem) => nearby(problem, scope, position, locationLabel))
      .slice(0, 3);
  }, [publicProblems.data, scope, position, locationLabel]);

  const assistant = useMutation({
    mutationFn: (answers: AssistantAnswer[]) => api.post<AssistantResponse>("/meldungen/assistenz", {
      category: category in PROBLEM_KATEGORIEN ? category : null,
      scope_kind: scope,
      answers,
    }),
    onSuccess: (result, answers) => {
      setAssistantAnswers(answers);
      setAssistantInput("");
      setAssistantRedacted((value) => value || result.redacted);
      if (result.kind === "question" && result.question) {
        setAssistantQuestion(result.question);
        return;
      }
      if (result.kind === "ready" && result.draft_text && result.category && result.category_detail) {
        setCategory(result.category);
        setCategoryDetail(result.category_detail);
        setText(result.draft_text);
        setStage("review");
      }
    },
  });

  const confirmationSnapshot = JSON.stringify({
    scope,
    locationLabel: locationLabel.trim(),
    position,
    category,
    categoryDetail: categoryDetail.trim(),
    text: text.trim(),
    observedOn,
    suggestedProblemId: suggestedProblem?.id ?? null,
  });
  const confirmed = confirmedText === confirmationSnapshot;
  const reviewComplete = scope !== null
    && (scope === "citywide" || (locationLabel.trim().length >= 2 && position !== null))
    && category in PROBLEM_KATEGORIEN
    && categoryDetail.trim().length >= 10
    && text.trim().length >= 20
    && observedOn.length > 0
    && observedOn <= todayISO();

  const submit = useMutation({
    mutationFn: async () => {
      if (!scope) throw new ApiError(422, "Der räumliche Bezug fehlt.");
      let id = draftId;
      if (id === null) {
        const draft = await api.post<PrivateReport>("/meldungen/entwuerfe", {
          text: text.trim(),
          category,
          scope_kind: scope,
          location_label: scope === "citywide" ? "" : locationLabel.trim(),
          latitude: scope === "citywide" ? null : position?.latitude ?? null,
          longitude: scope === "citywide" ? null : position?.longitude ?? null,
          observed_on: observedOn,
          category_detail: categoryDetail.trim(),
          suggested_problem_id: suggestedProblem?.id ?? null,
          client_token: clientToken,
        });
        id = draft.id;
        setDraftId(id);
      }
      return api.post<PrivateReport>(`/meldungen/${id}/absenden`, { confirmed_text: text.trim() });
    },
    onSuccess: (report) => {
      clearProblemReportDraft();
      setSubmitted(report);
    },
  });

  const chooseScope = (next: ProblemScope) => {
    setScope(next);
    setSuggestedProblem(null);
    setNoMatchingProblem(false);
    if (next === "citywide") {
      setLocationLabel("");
      setPosition(null);
      setStage("match");
    } else {
      setStage("location");
    }
  };

  const finishMatch = (problem: PublicProblemSummary | null) => {
    setSuggestedProblem(problem);
    setNoMatchingProblem(problem === null);
    setStage("date");
  };

  if (user?.role === "admin") {
    return (
      <Card className="mx-auto max-w-2xl p-6 text-center sm:p-8">
        <h1 className="font-display text-2xl font-bold text-foreground">Meldungen gehören zu persönlichen Konten</h1>
        <p className="mt-2 text-sm text-muted-foreground">Admin-Konten moderieren und können deshalb keine eigene Meldung einreichen.</p>
        <Button asChild variant="secondary" className="mt-5"><Link href="/probleme">Zur Problemkarte</Link></Button>
      </Card>
    );
  }

  if (!hydrated) {
    return <Card className="mx-auto h-48 max-w-3xl animate-pulse bg-muted" aria-label="Melde-Chat wird vorbereitet" />;
  }

  if (submitted) {
    return (
      <Card className="mx-auto max-w-2xl p-6 text-center sm:p-8" role="status">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300">
          <CheckCircle2 className="h-6 w-6" aria-hidden />
        </span>
        <h1 className="mt-4 font-display text-2xl font-bold text-foreground">Meldung privat eingegangen</h1>
        <p className="mx-auto mt-2 max-w-lg text-sm leading-relaxed text-muted-foreground">
          Sie ist noch nicht öffentlich. Zuerst folgen eine eigenständige Vorprüfung und danach die menschliche Entscheidung durch Ratslotse.
        </p>
        <div className="mt-6 flex flex-col justify-center gap-2 sm:flex-row">
          <Button asChild><Link href="/probleme">Zur Problemkarte</Link></Button>
          <Button asChild variant="secondary"><Link href="/dashboard">Zum Dashboard</Link></Button>
        </div>
      </Card>
    );
  }

  if (stage === "review") {
    return (
      <div className="mx-auto max-w-3xl space-y-5">
        <header>
          <p className="flex items-center gap-1.5 text-sm font-medium text-primary"><Sparkles className="h-4 w-4" aria-hidden /> Entwurf aus dem Melde-Chat</p>
          <h1 ref={stageHeadingRef} tabIndex={-1} className="mt-1 font-display text-2xl font-bold tracking-tight text-foreground outline-none sm:text-[30px]">Prüfen, korrigieren, freigeben</h1>
          <p className="mt-2 text-sm text-muted-foreground">Die KI schlägt nur vor. Du entscheidest über jedes Wort und sendest erst nach deiner Bestätigung.</p>
        </header>

        <Card className="space-y-5 p-4 sm:p-6">
          <div className="flex flex-wrap gap-2">
            <Badge>{scope ? PROBLEM_SCOPE[scope] : "Ort fehlt"}</Badge>
            {scope !== "citywide" && locationLabel && <Badge>{locationLabel.trim()}</Badge>}
            {suggestedProblem && <Badge>passt möglicherweise zu „{suggestedProblem.title}“</Badge>}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="report-category">Thema</Label>
              <select
                id="report-category"
                value={category}
                disabled={draftId !== null}
                onChange={(event) => setCategory(event.target.value)}
                className="flex h-11 w-full rounded-md border border-input bg-card px-3 py-2 text-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:text-sm"
              >
                <option value="">Bitte wählen</option>
                {Object.entries(PROBLEM_KATEGORIEN).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="report-observed-on">Zuletzt selbst beobachtet</Label>
              <Input id="report-observed-on" type="date" value={observedOn} max={todayISO()} disabled={draftId !== null} onChange={(event) => setObservedOn(event.target.value)} />
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between gap-3">
              <Label htmlFor="report-location-label">Ort</Label>
              <button
                type="button"
                disabled={draftId !== null}
                className="text-xs font-medium text-primary hover:underline disabled:cursor-not-allowed disabled:opacity-50"
                onClick={() => {
                  setSuggestedProblem(null);
                  setNoMatchingProblem(false);
                  setStage("scope");
                }}
              >
                Ort ändern
              </button>
            </div>
            <Input
              id="report-location-label"
              value={scope === "citywide" ? "Ganz Oldenburg" : locationLabel}
              disabled={scope === "citywide"}
              readOnly
              maxLength={160}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="report-category-detail">Wichtigste konkrete Beobachtung</Label>
            <Textarea id="report-category-detail" value={categoryDetail} disabled={draftId !== null} onChange={(event) => setCategoryDetail(event.target.value)} minLength={10} maxLength={500} rows={3} />
          </div>

          <div className="space-y-2">
            <Label htmlFor="report-confirmed-text">Finaler Meldetext</Label>
            <Textarea
              id="report-confirmed-text"
              value={text}
              onChange={(event) => setText(event.target.value)}
              minLength={20}
              maxLength={2_000}
              rows={8}
              disabled={draftId !== null}
            />
            <p className="text-right text-xs tabular-nums text-muted-foreground">{text.trim().length}/2000</p>
          </div>

          <label className="flex items-start gap-3 rounded-xl border border-primary/20 bg-primary/5 p-4 text-sm leading-relaxed text-foreground">
            <input
              type="checkbox"
              checked={confirmed}
              disabled={!reviewComplete}
              onChange={(event) => setConfirmedText(event.target.checked ? confirmationSnapshot : null)}
              className="mt-0.5 h-4 w-4 rounded border-input accent-primary"
            />
            <span>
              Ich habe Ort, Einordnung und Meldetext selbst geprüft. Der genaue Eingabeort und die private Meldung bleiben nichtöffentlich. Nur eine später menschlich freigegebene Zusammenfassung kann öffentlich erscheinen. <Link href="/datenschutz" className="font-medium text-primary hover:underline">Datenschutz</Link>
            </span>
          </label>
          <div className="flex items-start gap-2 text-xs leading-relaxed text-muted-foreground">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            Keine Fotos oder Anhänge. Bitte entferne Namen, Kontaktdaten, Notfälle, Straftaten und persönliche Vorwürfe.
          </div>
          {submit.isError && (
            <p className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive" role="alert">
              {submit.error instanceof ApiError ? submit.error.message : "Die Meldung konnte nicht abgesendet werden."}
              {draftId !== null && " Der private Entwurf ist gesichert; du kannst erneut absenden."}
            </p>
          )}
          <div className="flex justify-end">
            <Button
              type="button"
              variant="signal"
              className="min-h-11 px-5 text-base"
              disabled={!confirmed || !reviewComplete || submit.isPending}
              onClick={() => submit.mutate()}
            >
              {submit.isPending ? "Wird privat gesendet…" : draftId !== null ? "Erneut absenden" : "Geprüfte Meldung privat absenden"}
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  const selectedScope = scope ? SCOPES.find((item) => item.value === scope) : null;
  const locationComplete = scope === "citywide" || (locationLabel.trim().length >= 2 && position !== null);

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <header>
        <p className="flex items-center gap-1.5 text-sm font-medium text-primary"><Sparkles className="h-4 w-4" aria-hidden /> KI-gestützter Melde-Chat</p>
        <h1 ref={stageHeadingRef} tabIndex={-1} className="mt-1 font-display text-2xl font-bold tracking-tight text-foreground outline-none sm:text-[30px]">Problem melden</h1>
        <p className="mt-2 text-sm text-muted-foreground">Antworte im Chat. Sobald die Angaben reichen, erscheint dein korrigierbarer Entwurf.</p>
      </header>

      <Card className="overflow-hidden">
        <div className="flex items-center justify-between border-b border-border bg-muted/35 px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground"><Bot className="h-4 w-4" aria-hidden /></span>
            <div>
              <p className="text-sm font-semibold text-foreground">Ratslotse Meldehilfe</p>
              <p className="text-xs text-muted-foreground">fragt nach, erfindet nichts</p>
            </div>
          </div>
          <Badge>{stage === "chat" ? "im Gespräch" : "Angaben sammeln"}</Badge>
        </div>

        <div className="space-y-4 bg-muted/15 p-4 sm:p-6" aria-live="polite">
          <BotBubble>
            Hallo! Ich helfe dir, aus deiner Beobachtung eine klare private Meldung zu machen. Zuerst: <strong>Welchen räumlichen Bezug hat das Problem?</strong>
          </BotBubble>

          {stage === "scope" && (
            <div className="ml-10 grid gap-2 sm:grid-cols-2" role="group" aria-label="Räumlicher Bezug">
              {SCOPES.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => chooseScope(item.value)}
                  className="rounded-xl border border-border bg-card p-3 text-left transition-colors hover:border-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <span className="block text-sm font-semibold text-foreground">{item.label}</span>
                  <span className="mt-0.5 block text-xs text-muted-foreground">{item.hint}</span>
                </button>
              ))}
            </div>
          )}

          {scope && scope !== "citywide" && stageAtLeast("location") && <UserBubble>{selectedScope?.label}</UserBubble>}

          {scope && scope !== "citywide" && stageAtLeast("location") && (
            <>
              <BotBubble>Wie heißt der Ort? Benenne ihn kurz und markiere die ungefähre Lage auf der Karte.</BotBubble>
              {stage === "location" ? (
                <div className="ml-10 space-y-3 rounded-2xl border border-border bg-card p-4">
                  <div className="space-y-2">
                    <Label htmlFor="report-location-label">Ort kurz benennen</Label>
                    <Input
                      id="report-location-label"
                      value={locationLabel}
                      maxLength={160}
                      onChange={(event) => setLocationLabel(event.target.value)}
                      placeholder="z. B. Theaterwall an der Querung"
                      autoComplete="street-address"
                    />
                  </div>
                  <LocationPicker value={position} onChange={setPosition} />
                  <div className="flex justify-end">
                    <Button type="button" disabled={!locationComplete} onClick={() => setStage("match")}>
                      Ort übernehmen <Send className="h-4 w-4" aria-hidden />
                    </Button>
                  </div>
                </div>
              ) : (
                <UserBubble><MapPin className="mr-1 inline h-4 w-4" aria-hidden />{locationLabel}</UserBubble>
              )}
            </>
          )}

          {scope === "citywide" && stageAtLeast("match") && <UserBubble>Das Problem betrifft ganz Oldenburg.</UserBubble>}

          {scope && stageAtLeast("match") && (
            <>
              <BotBubble>Ich prüfe kurz, ob bereits ein passendes öffentliches Problem existiert. Die Zuordnung entscheidet später trotzdem ein Mensch.</BotBubble>
              {stage === "match" && (
                <div className="ml-10 rounded-2xl border border-border bg-card p-4">
                  {publicProblems.isLoading ? (
                    <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Öffentliche Probleme werden verglichen…</p>
                  ) : publicProblems.isError ? (
                    <div className="space-y-3">
                      <p className="text-sm text-muted-foreground">Der Vergleich ist gerade nicht erreichbar. Das blockiert deine private Meldung nicht.</p>
                      <div className="flex flex-wrap gap-2">
                        <Button type="button" size="sm" variant="secondary" onClick={() => void publicProblems.refetch()}>Erneut versuchen</Button>
                        <Button type="button" size="sm" onClick={() => finishMatch(null)}>Trotzdem weiter</Button>
                      </div>
                    </div>
                  ) : suggestions.length > 0 ? (
                    <div className="space-y-2">
                      <p className="mb-3 text-sm font-medium text-foreground">Passt eines davon?</p>
                      {suggestions.map((problem) => (
                        <button
                          key={problem.id}
                          type="button"
                          onClick={() => finishMatch(problem)}
                          className="flex w-full items-start gap-2 rounded-lg border border-border p-3 text-left hover:border-primary/50"
                        >
                          <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden />
                          <span><span className="block text-sm font-medium text-foreground">{problem.title}</span><span className="block text-xs text-muted-foreground">{problem.location_label || PROBLEM_SCOPE[problem.scope_kind]}</span></span>
                        </button>
                      ))}
                      <button type="button" onClick={() => finishMatch(null)} className="mt-1 w-full rounded-lg border border-border px-3 py-2 text-left text-sm font-medium text-foreground hover:border-primary/50">
                        Nein, etwas anderes melden
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <p className="text-sm text-muted-foreground">Ich finde hier noch kein passendes öffentliches Problem.</p>
                      <Button type="button" size="sm" onClick={() => finishMatch(null)}>Neue Meldung fortsetzen</Button>
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {stageAtLeast("date") && (
            <>
              {stage !== "date" && <UserBubble>{suggestedProblem ? `Das passt möglicherweise zu „${suggestedProblem.title}“.` : "Das ist eine neue Beobachtung."}</UserBubble>}
              <BotBubble>Wann hast du das Problem zuletzt selbst beobachtet?</BotBubble>
              {stage === "date" ? (
                <div className="ml-10 flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 sm:flex-row sm:items-end">
                  <div className="flex-1 space-y-2">
                    <Label htmlFor="report-observed-on">Beobachtungsdatum</Label>
                    <Input id="report-observed-on" type="date" value={observedOn} max={todayISO()} onChange={(event) => setObservedOn(event.target.value)} />
                  </div>
                  <Button
                    type="button"
                    disabled={!observedOn || observedOn > todayISO()}
                    onClick={() => setStage(text && categoryDetail ? "review" : "consent")}
                  >
                    Datum übernehmen
                  </Button>
                </div>
              ) : (
                <UserBubble>{displayDate(observedOn)}</UserBubble>
              )}
            </>
          )}

          {stageAtLeast("consent") && (
            <>
              <BotBubble>
                Jetzt frage ich nur noch nach den Tatsachen, die für eine gute Meldung fehlen. Konto, Ortsname, Kartenpunkt und Datum gehen nicht an den KI-Dienst. Direkte Kontaktdaten und genaue Adressen werden vorher lokal entfernt.
              </BotBubble>
              {stage === "consent" && (
                <div className="ml-10 space-y-3 rounded-2xl border border-primary/20 bg-primary/5 p-4">
                  <label className="flex items-start gap-2 text-xs leading-relaxed text-muted-foreground">
                    <input
                      type="checkbox"
                      checked={assistantConsent}
                      onChange={(event) => setAssistantConsent(event.target.checked)}
                      className="mt-0.5 h-4 w-4 rounded border-input accent-primary"
                    />
                    <span>Ich möchte den externen KI-Melde-Chat nutzen und trage keine Namen, Kontaktdaten oder sensiblen persönlichen Angaben ein.</span>
                  </label>
                  <Button type="button" disabled={!assistantConsent} onClick={() => setStage("chat")}>
                    <Sparkles className="h-4 w-4" aria-hidden /> Gespräch starten
                  </Button>
                </div>
              )}
            </>
          )}

          {stage === "chat" && (
            <>
              {assistantAnswers.map((answer, index) => (
                <div key={`${answer.question}-${index}`} className="contents">
                  <BotBubble>{answer.question}</BotBubble>
                  <UserBubble>{answer.answer}</UserBubble>
                </div>
              ))}
              <BotBubble>{assistantQuestion}</BotBubble>
              <div className="ml-10 rounded-2xl border border-primary/30 bg-card p-3">
                <Label htmlFor="report-assistant-answer" className="sr-only">Antwort an die Meldehilfe</Label>
                <Textarea
                  id="report-assistant-answer"
                  value={assistantInput}
                  onChange={(event) => setAssistantInput(event.target.value)}
                  maxLength={1_000}
                  rows={4}
                  placeholder="Schreibe in deinen Worten – nur selbst beobachtete Fakten"
                  autoFocus
                />
                <div className="mt-2 flex items-center justify-between gap-2">
                  <span className="text-xs text-muted-foreground">{assistantAnswers.length + 1}/6 mögliche Antworten</span>
                  <Button
                    type="button"
                    disabled={assistantInput.trim().length < 2 || assistant.isPending || assistantAnswers.length >= 6}
                    onClick={() => assistant.mutate([
                      ...assistantAnswers,
                      { question: assistantQuestion, answer: assistantInput.trim() },
                    ])}
                  >
                    {assistant.isPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Send className="h-4 w-4" aria-hidden />}
                    {assistant.isPending ? "Entwurf wird geprüft…" : "Antwort senden"}
                  </Button>
                </div>
              </div>
              {assistantRedacted && <p className="ml-10 text-xs text-muted-foreground">Direkte personenbezogene Angaben wurden vor dem KI-Aufruf lokal entfernt.</p>}
              {assistant.isError && (
                <div className="ml-10 space-y-2 rounded-xl border border-destructive/30 bg-destructive/5 p-3" role="alert">
                  <p className="text-sm text-destructive">{assistant.error instanceof ApiError ? assistant.error.message : "Die KI-Meldehilfe ist gerade nicht erreichbar."}</p>
                  <Button type="button" size="sm" variant="secondary" disabled={assistantInput.trim().length < 2} onClick={() => assistant.mutate([
                    ...assistantAnswers,
                    { question: assistantQuestion, answer: assistantInput.trim() },
                  ])}>Noch einmal versuchen</Button>
                </div>
              )}
            </>
          )}
        </div>
      </Card>

      <p className="flex items-start gap-2 text-xs leading-relaxed text-muted-foreground">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
        Die Unterhaltung und der Entwurf bleiben privat. Absenden kannst nur du – nach einer eigenen Schlussprüfung.
      </p>
    </div>
  );
}
