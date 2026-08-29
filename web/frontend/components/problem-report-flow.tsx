"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, CheckCircle2, ChevronLeft, ChevronRight, Loader2, MapPin, Send, ShieldCheck, Sparkles } from "lucide-react";
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
  { value: "point", label: "Ein Ort", hint: "zum Beispiel eine Querung oder Kreuzung" },
  { value: "facility", label: "Einrichtung", hint: "zum Beispiel Schule, Kita oder Haltestelle" },
  { value: "route", label: "Straße oder Strecke", hint: "ein Abschnitt oder eine Verbindung" },
  { value: "area", label: "Gebiet", hint: "Quartier, Stadtteil oder größerer Bereich" },
  { value: "citywide", label: "Ganz Oldenburg", hint: "kein einzelner Ort wäre ehrlich" },
];

const CATEGORY_QUESTIONS: Record<string, string> = {
  mobility: "Was genau erschwert die Fortbewegung – und für wen?",
  public_space: "Was fehlt oder funktioniert im öffentlichen Raum nicht?",
  education: "Welche konkrete Auswirkung hat das Problem im Schulalltag?",
  childcare: "Welche Betreuung fehlt, wann und in welchem Umfang?",
  housing: "Welche kommunal beeinflussbare Wohnsituation beobachtest du?",
  environment: "Was ist vor Ort sichtbar und seit wann?",
  accessibility: "Welche Barriere besteht und wer kann den Ort dadurch nicht gut nutzen?",
  administration: "Welcher kommunale Ablauf funktioniert konkret nicht?",
  other: "Was sollte die Stadt beeinflussen können und was beobachtest du konkret?",
};

type Position = { latitude: number; longitude: number } | null;

type AssistantAnswer = { question: string; answer: string };
type AssistantResponse = {
  kind: "question" | "ready";
  question: string | null;
  draft_text: string | null;
  redacted: boolean;
};

type SavedReportForm = {
  ownerId: number;
  savedAt: number;
  step: number;
  scope: ProblemScope;
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
  assistantActive: boolean;
  assistantConsent: boolean;
  assistantQuestion: string;
  assistantAnswers: AssistantAnswer[];
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

export function ProblemReportFlow() {
  const { user } = useAuth();
  const [step, setStep] = useState(0);
  const [scope, setScope] = useState<ProblemScope>("point");
  const [locationLabel, setLocationLabel] = useState("");
  const [position, setPosition] = useState<Position>(null);
  const [category, setCategory] = useState("");
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
  const [assistantActive, setAssistantActive] = useState(false);
  const [assistantConsent, setAssistantConsent] = useState(false);
  const [assistantQuestion, setAssistantQuestion] = useState("");
  const [assistantInput, setAssistantInput] = useState("");
  const [assistantAnswers, setAssistantAnswers] = useState<AssistantAnswer[]>([]);
  const [assistantRedacted, setAssistantRedacted] = useState(false);
  const textRef = useRef(text);
  const stepHeadingRef = useRef<HTMLHeadingElement>(null);
  const previousStepRef = useRef(step);
  textRef.current = text;

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(PROBLEM_REPORT_DRAFT_STORAGE);
      if (raw) {
        const saved = JSON.parse(raw) as Partial<SavedReportForm>;
        if (
          typeof saved.savedAt !== "number"
          || Date.now() - saved.savedAt > 30 * 60 * 1_000
          || saved.ownerId !== user?.id
        ) {
          throw new Error("Gespeicherter Meldeentwurf ist abgelaufen oder gehört zu einem anderen Konto.");
        }
        if (saved.step === 0 || saved.step === 1 || saved.step === 2) setStep(saved.step);
        if (SCOPES.some((item) => item.value === saved.scope)) setScope(saved.scope!);
        if (typeof saved.locationLabel === "string") setLocationLabel(saved.locationLabel);
        if (saved.position === null || (
          typeof saved.position?.latitude === "number"
          && typeof saved.position?.longitude === "number"
        )) setPosition(saved.position ?? null);
        if (typeof saved.category === "string") setCategory(saved.category);
        if (typeof saved.categoryDetail === "string") setCategoryDetail(saved.categoryDetail);
        if (typeof saved.text === "string") setText(saved.text);
        if (typeof saved.observedOn === "string") setObservedOn(saved.observedOn);
        if (saved.suggestedProblem && typeof saved.suggestedProblem.id === "number") {
          setSuggestedProblem(saved.suggestedProblem);
        }
        setNoMatchingProblem(saved.noMatchingProblem === true);
        if (typeof saved.draftId === "number") setDraftId(saved.draftId);
        setAssistantActive(saved.assistantActive === true);
        setAssistantConsent(saved.assistantConsent === true);
        if (typeof saved.assistantQuestion === "string") setAssistantQuestion(saved.assistantQuestion);
        if (Array.isArray(saved.assistantAnswers)) {
          setAssistantAnswers(saved.assistantAnswers.filter((answer): answer is AssistantAnswer =>
            typeof answer?.question === "string" && typeof answer?.answer === "string"));
        }
        setClientToken(typeof saved.clientToken === "string" && saved.clientToken
          ? saved.clientToken
          : crypto.randomUUID());
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
    if (!hydrated || submitted) return;
    if (!user) return;
    const snapshot: SavedReportForm = {
      ownerId: user.id,
      savedAt: Date.now(),
      step,
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
      assistantActive,
      assistantConsent,
      assistantQuestion,
      assistantAnswers,
    };
    try {
      sessionStorage.setItem(PROBLEM_REPORT_DRAFT_STORAGE, JSON.stringify(snapshot));
      scheduleProblemReportDraftExpiry();
    } catch { /* optional */ }
  }, [
    hydrated, submitted, step, scope, locationLabel, position, category,
    categoryDetail, text, observedOn, suggestedProblem, noMatchingProblem,
    draftId, clientToken, user, assistantActive, assistantConsent,
    assistantQuestion, assistantAnswers,
  ]);

  useEffect(() => {
    if (previousStepRef.current === step) return;
    previousStepRef.current = step;
    stepHeadingRef.current?.focus();
  }, [step]);

  const publicProblems = useQuery({
    queryKey: ["public-problems-for-report"],
    queryFn: () => api.get<ProblemListResponse>("/probleme"),
    staleTime: 60_000,
  });
  const suggestions = useMemo(
    () => (publicProblems.data?.problems ?? [])
      .filter((problem) => nearby(problem, scope, position, locationLabel))
      .slice(0, 3),
    [publicProblems.data, scope, position, locationLabel],
  );

  const locationComplete = scope === "citywide"
    || (locationLabel.trim().length >= 2 && position !== null);
  const locationReady = locationComplete && (
    publicProblems.isError
    || (publicProblems.isSuccess && (suggestedProblem !== null || noMatchingProblem))
  );
  const detailsComplete = category in PROBLEM_KATEGORIEN
    && categoryDetail.trim().length >= 10
    && text.trim().length >= 20
    && observedOn.length > 0
    && observedOn <= todayISO();
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

  const assistant = useMutation({
    mutationFn: (answers: AssistantAnswer[]) => api.post<AssistantResponse>("/meldungen/assistenz", {
      category,
      scope_kind: scope,
      answers,
    }),
    onSuccess: (result, answers) => {
      setAssistantAnswers(answers);
      setAssistantInput("");
      setAssistantRedacted((value) => value || result.redacted);
      setCategoryDetail(answers.map((answer) => answer.answer.trim()).join(" ").slice(0, 500));
      if (result.kind === "question" && result.question) {
        setAssistantQuestion(result.question);
      } else if (result.kind === "ready" && result.draft_text) {
        setText(result.draft_text);
        setAssistantActive(false);
        setAssistantQuestion("");
      }
    },
  });

  const submit = useMutation({
    mutationFn: async () => {
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
      return api.post<PrivateReport>(`/meldungen/${id}/absenden`, {
        confirmed_text: text.trim(),
      });
    },
    onSuccess: (report) => {
      clearProblemReportDraft();
      setSubmitted(report);
    },
  });

  const resetAssistant = () => {
    setAssistantActive(false);
    setAssistantConsent(false);
    setAssistantQuestion("");
    setAssistantInput("");
    setAssistantAnswers([]);
    setAssistantRedacted(false);
    assistant.reset();
  };

  const chooseScope = (next: ProblemScope) => {
    setScope(next);
    setSuggestedProblem(null);
    setNoMatchingProblem(false);
    if (next === "citywide") {
      setPosition(null);
      setLocationLabel("");
    }
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
    return <Card className="mx-auto h-48 max-w-3xl animate-pulse bg-muted" aria-label="Meldeentwurf wird vorbereitet" />;
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

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <header>
        <p className="text-sm font-medium text-primary">Private Meldung</p>
        <h1 className="mt-1 font-display text-2xl font-bold tracking-tight text-foreground sm:text-[30px]">Problem melden</h1>
        <p className="mt-2 text-sm text-muted-foreground">Drei kurze Schritte. Keine Fotos, keine öffentliche Rohmeldung.</p>
      </header>

      <ol className="grid grid-cols-3 gap-2" aria-label="Fortschritt">
        {["Ort", "Beobachtung", "Prüfen"].map((label, index) => (
          <li key={label} className={cn(
            "rounded-lg border px-2 py-2 text-center text-xs font-medium",
            index === step ? "border-primary bg-primary/5 text-primary" : index < step ? "border-emerald-300 text-emerald-700 dark:text-emerald-300" : "border-border text-muted-foreground",
          )} aria-current={index === step ? "step" : undefined}>
            {index < step && <Check className="mr-1 inline h-3.5 w-3.5" aria-hidden />}{label}
          </li>
        ))}
      </ol>

      <Card className="p-4 sm:p-6">
        {step === 0 && (
          <section aria-labelledby="report-location-heading" className="space-y-5">
            <div>
              <h2 ref={stepHeadingRef} tabIndex={-1} id="report-location-heading" className="text-lg font-semibold text-foreground outline-none">Wo besteht das Problem?</h2>
              <p className="mt-1 text-sm text-muted-foreground">Wähle den räumlichen Bezug so genau wie nötig.</p>
            </div>
            <div className="grid gap-2 sm:grid-cols-2" role="group" aria-label="Räumlicher Bezug">
              {SCOPES.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  aria-pressed={scope === item.value}
                  onClick={() => chooseScope(item.value)}
                  className={cn(
                    "rounded-xl border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    scope === item.value ? "border-primary bg-primary/5" : "border-border hover:border-primary/40",
                  )}
                >
                  <span className="block text-sm font-semibold text-foreground">{item.label}</span>
                  <span className="mt-0.5 block text-xs text-muted-foreground">{item.hint}</span>
                </button>
              ))}
            </div>
            {scope !== "citywide" && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="report-location-label">Ort kurz benennen</Label>
                  <Input
                    id="report-location-label"
                    value={locationLabel}
                    maxLength={160}
                    onChange={(event) => {
                      setLocationLabel(event.target.value);
                      setSuggestedProblem(null);
                      setNoMatchingProblem(false);
                    }}
                    placeholder="z. B. Theaterwall an der Querung"
                    autoComplete="street-address"
                  />
                </div>
                <LocationPicker value={position} onChange={(next) => {
                  setPosition(next);
                  setSuggestedProblem(null);
                  setNoMatchingProblem(false);
                }} />
              </>
            )}

            {locationComplete && (
              <div className="rounded-xl border border-border bg-muted/35 p-3" aria-live="polite">
                <h3 className="text-sm font-semibold text-foreground">Schon öffentlich sichtbar?</h3>
                {publicProblems.isLoading ? (
                  <p className="mt-2 text-sm text-muted-foreground">Öffentliche Probleme werden verglichen…</p>
                ) : publicProblems.isError ? (
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted-foreground" role="status">
                    <span>Der öffentliche Vergleich ist gerade nicht erreichbar. Deine private Meldung ist davon nicht betroffen.</span>
                    <Button type="button" size="sm" variant="secondary" onClick={() => void publicProblems.refetch()}>
                      Erneut versuchen
                    </Button>
                  </div>
                ) : (
                  <>
                    <p className="mt-1 text-xs text-muted-foreground">Wenn eines passt, schlagen wir diese Zuordnung vor. Ein Mensch prüft sie später.</p>
                    {suggestions.length > 0 && (
                      <div className="mt-3 space-y-2">
                        {suggestions.map((problem) => (
                          <button
                            key={problem.id}
                            type="button"
                            aria-pressed={suggestedProblem?.id === problem.id}
                            onClick={() => {
                              const selected = suggestedProblem?.id === problem.id ? null : problem;
                              setSuggestedProblem(selected);
                              setNoMatchingProblem(false);
                            }}
                            className={cn(
                              "flex w-full items-start gap-2 rounded-lg border bg-card p-3 text-left",
                              suggestedProblem?.id === problem.id ? "border-primary ring-2 ring-primary/15" : "border-border",
                            )}
                          >
                            <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden />
                            <span className="min-w-0">
                              <span className="block text-sm font-medium text-foreground">{problem.title}</span>
                              <span className="block truncate text-xs text-muted-foreground">{problem.location_label || PROBLEM_SCOPE[problem.scope_kind]}</span>
                            </span>
                          </button>
                        ))}
                      </div>
                    )}
                    <button
                      type="button"
                      aria-pressed={noMatchingProblem}
                      onClick={() => {
                        setNoMatchingProblem(true);
                        setSuggestedProblem(null);
                      }}
                      className={cn(
                        "mt-3 w-full rounded-lg border px-3 py-2 text-left text-sm font-medium",
                        noMatchingProblem ? "border-primary bg-primary/5 text-primary" : "border-border bg-card text-foreground",
                      )}
                    >
                      Kein passendes Problem dabei
                    </button>
                  </>
                )}
              </div>
            )}
          </section>
        )}

        {step === 1 && (
          <section aria-labelledby="report-details-heading" className="space-y-5">
            <div>
              <h2 ref={stepHeadingRef} tabIndex={-1} id="report-details-heading" className="text-lg font-semibold text-foreground outline-none">Was hast du beobachtet?</h2>
              <p className="mt-1 text-sm text-muted-foreground">Beschreibe Tatsachen, keine Vermutungen über Personen.</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="report-category">Thema</Label>
              <select
                id="report-category"
                value={category}
                onChange={(event) => {
                  setCategory(event.target.value);
                  setCategoryDetail("");
                  resetAssistant();
                }}
                className="flex h-11 w-full rounded-md border border-input bg-card px-3 py-2 text-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring maus:text-sm"
              >
                <option value="">Bitte wählen</option>
                {Object.entries(PROBLEM_KATEGORIEN).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </div>
            {category && (
              <div className="rounded-xl border border-primary/20 bg-primary/5 p-4">
                <div className="flex items-start gap-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                    <Sparkles className="h-4 w-4" aria-hidden />
                  </span>
                  <div className="min-w-0 flex-1">
                    <h3 className="text-sm font-semibold text-foreground">Interaktive KI-Schreibhilfe</h3>
                    <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                      Sie fragt gezielt nach fehlenden Fakten und erstellt daraus einen bearbeitbaren Entwurf. Konto, Kartenpunkt und Ortsname werden nicht an den KI-Dienst gesendet.
                    </p>
                  </div>
                </div>

                {!assistantActive && assistantAnswers.length === 0 && (
                  <div className="mt-4 space-y-3">
                    <label className="flex items-start gap-2 text-xs leading-relaxed text-muted-foreground">
                      <input
                        type="checkbox"
                        checked={assistantConsent}
                        onChange={(event) => setAssistantConsent(event.target.checked)}
                        className="mt-0.5 h-4 w-4 rounded border-input accent-primary"
                      />
                      <span>Ich möchte die optionale externe KI-Schreibhilfe nutzen. Meine Antworten werden vorher lokal um E-Mail-Adressen, Telefonnummern, genaue Adressen und mit Anrede genannte Namen bereinigt. Ich trage trotzdem keine personenbezogenen Daten ein.</span>
                    </label>
                    <Button
                      type="button"
                      size="sm"
                      disabled={!assistantConsent}
                      onClick={() => {
                        setAssistantActive(true);
                        setAssistantQuestion(CATEGORY_QUESTIONS[category]);
                      }}
                    >
                      <Sparkles className="h-4 w-4" aria-hidden /> Geführt starten
                    </Button>
                  </div>
                )}

                {assistantActive && (
                  <div className="mt-4 space-y-3" aria-live="polite">
                    {assistantAnswers.map((answer, index) => (
                      <div key={`${answer.question}-${index}`} className="rounded-lg border border-border bg-card p-3 text-sm">
                        <p className="font-medium text-foreground">{answer.question}</p>
                        <p className="mt-1 text-muted-foreground">{answer.answer}</p>
                      </div>
                    ))}
                    <div className="rounded-lg border border-primary/30 bg-card p-3">
                      <Label htmlFor="report-assistant-answer">{assistantQuestion}</Label>
                      <Textarea
                        id="report-assistant-answer"
                        value={assistantInput}
                        onChange={(event) => setAssistantInput(event.target.value)}
                        maxLength={1_000}
                        rows={3}
                        placeholder="Nur selbst beobachtete Fakten – keine Namen oder Kontaktdaten"
                        className="mt-2"
                      />
                      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                        <button type="button" className="text-xs font-medium text-muted-foreground hover:text-foreground" onClick={resetAssistant}>
                          Ohne KI weiterschreiben
                        </button>
                        <Button
                          type="button"
                          size="sm"
                          disabled={assistantInput.trim().length < 2 || assistant.isPending}
                          onClick={() => assistant.mutate([
                            ...assistantAnswers,
                            { question: assistantQuestion, answer: assistantInput.trim() },
                          ])}
                        >
                          {assistant.isPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Send className="h-4 w-4" aria-hidden />}
                          {assistant.isPending ? "Denkt nach…" : "Antwort senden"}
                        </Button>
                      </div>
                    </div>
                  </div>
                )}

                {!assistantActive && assistantAnswers.length > 0 && text && (
                  <p className="mt-4 rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-200" role="status">
                    Der Entwurf ist übernommen. Lies ihn unten und ändere alles, was nicht genau deiner Beobachtung entspricht.
                  </p>
                )}
                {assistantRedacted && (
                  <p className="mt-3 text-xs text-muted-foreground">Direkte personenbezogene Angaben wurden vor dem KI-Aufruf lokal entfernt.</p>
                )}
                {assistant.isError && (
                  <p className="mt-3 text-sm text-destructive" role="alert">
                    {assistant.error instanceof ApiError ? assistant.error.message : "Die KI-Schreibhilfe ist gerade nicht erreichbar."}
                  </p>
                )}
              </div>
            )}
            {category && (
              <div className="space-y-2">
                <Label htmlFor="report-category-detail">Wichtigste konkrete Angabe</Label>
                <Textarea
                  id="report-category-detail"
                  value={categoryDetail}
                  onChange={(event) => setCategoryDetail(event.target.value)}
                  minLength={10}
                  maxLength={500}
                  rows={3}
                  placeholder={CATEGORY_QUESTIONS[category]}
                />
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="report-text">Beobachtung auf Deutsch</Label>
              <Textarea
                id="report-text"
                value={text}
                onChange={(event) => setText(event.target.value)}
                minLength={20}
                maxLength={2_000}
                rows={7}
                placeholder="Was ist konkret passiert oder fehlt? Seit wann besteht es?"
              />
              <p className="text-right text-xs tabular-nums text-muted-foreground">{text.trim().length}/2000</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="report-observed-on">Zuletzt selbst beobachtet</Label>
              <Input
                id="report-observed-on"
                type="date"
                value={observedOn}
                max={todayISO()}
                onChange={(event) => setObservedOn(event.target.value)}
              />
            </div>
          </section>
        )}

        {step === 2 && (
          <section aria-labelledby="report-review-heading" className="space-y-5">
            <div>
              <h2 ref={stepHeadingRef} tabIndex={-1} id="report-review-heading" className="text-lg font-semibold text-foreground outline-none">Kurz prüfen und absenden</h2>
              <p className="mt-1 text-sm text-muted-foreground">Dieser bestätigte Text wird privat geprüft.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge>{PROBLEM_KATEGORIEN[category as keyof typeof PROBLEM_KATEGORIEN]}</Badge>
              <Badge>{PROBLEM_SCOPE[scope]}</Badge>
              {scope !== "citywide" && <Badge>{locationLabel.trim()}</Badge>}
            </div>
            {suggestedProblem && (
              <p className="rounded-lg border border-border bg-muted/35 p-3 text-sm text-muted-foreground">
                Vorgeschlagene Zuordnung: <strong className="text-foreground">{suggestedProblem.title}</strong>
              </p>
            )}
            <div className="rounded-lg border border-border bg-muted/35 p-3 text-sm">
              <p className="font-medium text-foreground">{CATEGORY_QUESTIONS[category]}</p>
              <p className="mt-1 text-muted-foreground">{categoryDetail.trim()}</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="report-confirmed-text">Dein bestätigter Meldetext</Label>
              <Textarea
                id="report-confirmed-text"
                value={text}
                onChange={(event) => setText(event.target.value)}
                minLength={20}
                maxLength={2_000}
                rows={7}
                disabled={draftId !== null}
              />
            </div>
            <label className="flex items-start gap-3 rounded-xl border border-primary/20 bg-primary/5 p-4 text-sm leading-relaxed text-foreground">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(event) => setConfirmedText(event.target.checked ? confirmationSnapshot : null)}
                className="mt-0.5 h-4 w-4 rounded border-input accent-primary"
              />
              <span>
                Ich habe Text und Angaben geprüft. Kontokennung, Rohtext und der genaue Eingabeort bleiben privat. Nach eigenständiger Vorprüfung und menschlicher Freigabe können nur eine moderierte Zusammenfassung und ein geeigneter geografischer Bezug öffentlich erscheinen. <Link href="/datenschutz" className="font-medium text-primary hover:underline">Datenschutz</Link>
              </span>
            </label>
            <div className="flex items-start gap-2 text-xs leading-relaxed text-muted-foreground">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              Keine Fotos oder Anhänge. Bitte keine Namen, Kontaktdaten, Notfälle, Straftaten oder Vorwürfe gegen einzelne Personen eintragen.
            </div>
            {submit.isError && (
              <p className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive" role="alert">
                {submit.error instanceof ApiError ? submit.error.message : "Die Meldung konnte nicht abgesendet werden."}
                {draftId !== null && " Der private Entwurf ist gesichert; du kannst erneut absenden."}
              </p>
            )}
          </section>
        )}

        <div className="mt-6 flex items-center justify-between gap-3 border-t border-border pt-4">
          {step > 0 && draftId === null ? (
            <Button type="button" variant="ghost" onClick={() => setStep((value) => value - 1)}>
              <ChevronLeft className="h-4 w-4" aria-hidden /> Zurück
            </Button>
          ) : <span />}
          {step < 2 ? (
            <Button
              type="button"
              onClick={() => setStep((value) => value + 1)}
              disabled={step === 0 ? !locationReady : !detailsComplete}
            >
              Weiter <ChevronRight className="h-4 w-4" aria-hidden />
            </Button>
          ) : (
            <Button
              type="button"
              variant="signal"
              disabled={!confirmed || text.trim().length < 20 || submit.isPending}
              onClick={() => submit.mutate()}
            >
              {submit.isPending ? "Wird privat gesendet…" : draftId !== null ? "Erneut absenden" : "Privat absenden"}
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}
