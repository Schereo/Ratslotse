"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CalendarClock, CheckCircle2, MapPin, Radio, Users } from "lucide-react";
import { api } from "@/lib/api";
import type { ProblemListResponse, PublicProblem, ProblemStatus } from "@/lib/types";
import { PROBLEM_KATEGORIEN, PROBLEM_SCOPE, PROBLEM_STATUS, VORSCHAU_PROBLEME } from "@/lib/probleme";
import { Badge, Card, ErrorState, PageHeader, Select, Spinner, formatDate } from "@/components/ui";
import { cn } from "@/lib/utils";

const ProblemMap = dynamic(
  () => import("@/components/problem-map").then((module) => module.ProblemMap),
  { ssr: false, loading: () => <div className="h-[440px] animate-pulse rounded-xl border border-border bg-muted" /> },
);

const STATUS_OPTIONS = Object.entries(PROBLEM_STATUS) as [ProblemStatus, (typeof PROBLEM_STATUS)[ProblemStatus]][];

export default function View({ vorschau }: { vorschau: boolean }) {
  const query = useQuery({
    queryKey: ["public-problems"],
    queryFn: () => api.get<ProblemListResponse>("/probleme"),
    enabled: !vorschau,
    staleTime: 60_000,
  });
  const all = vorschau ? VORSCHAU_PROBLEME : (query.data?.problems ?? []);
  const [category, setCategory] = useState("all");
  const [status, setStatus] = useState<ProblemStatus | "all">("all");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const problems = useMemo(() => all.filter((problem) =>
    (category === "all" || problem.category === category)
    && (status === "all" || problem.status === status),
  ), [all, category, status]);

  useEffect(() => {
    if (problems.length === 0) {
      setSelectedId(null);
      return;
    }
    if (!problems.some((problem) => problem.id === selectedId)) setSelectedId(problems[0].id);
  }, [problems, selectedId]);

  useEffect(() => {
    const raw = new URLSearchParams(window.location.search).get("problem");
    const initial = Number(raw);
    if (Number.isSafeInteger(initial) && all.some((problem) => problem.id === initial)) setSelectedId(initial);
  }, [all]);

  const select = useCallback((id: number) => {
    setSelectedId(id);
    const url = new URL(window.location.href);
    url.searchParams.set("problem", String(id));
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  }, []);

  const selected = problems.find((problem) => problem.id === selectedId) ?? null;
  const categories = useMemo(() => {
    const present = new Set(all.map((problem) => problem.category));
    return Object.entries(PROBLEM_KATEGORIEN).filter(([key]) => present.has(key));
  }, [all]);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Oldenburgs Problemkarte"
        description="Private Beobachtungen werden geprüft, gebündelt und ohne persönliche Angaben sichtbar gemacht."
      />

      {vorschau && (
        <div className="flex items-start gap-3 rounded-xl border border-amber-300/70 bg-amber-50 px-4 py-3 text-sm text-amber-950 dark:border-amber-700/60 dark:bg-amber-950/35 dark:text-amber-100" role="status">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <p><strong>Vorschau mit frei erfundenen Beispieldaten.</strong> Hier geht es zuerst um Karte, Filter und verständliche Statusangaben. Noch kann niemand etwas melden.</p>
        </div>
      )}

      <Card className="overflow-hidden border-primary/20 bg-gradient-to-r from-primary/[0.08] to-transparent p-4 sm:p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-display text-lg font-bold text-foreground">Gemeinsam Muster erkennen</p>
            <p className="mt-1 max-w-3xl text-sm leading-relaxed text-muted-foreground">
              Die Zahl zeigt unabhängige Reporter*innen, nicht Stimmen. Ein Status wie „geprüft“ beschreibt die Ratslotse-Prüfung und niemals automatisch eine Bearbeitung durch die Stadt.
            </p>
          </div>
          <Badge color="blue" className="w-fit shrink-0">Unabhängiges Bürgerprojekt</Badge>
        </div>
      </Card>

      <div className="grid gap-3 sm:grid-cols-3">
        <Metric icon={MapPin} value={all.length} label="öffentliche Probleme" />
        <Metric icon={Users} value={all.reduce((sum, problem) => sum + problem.unique_reporters, 0)} label="eindeutige Reporter*innen" />
        <Metric icon={Radio} value={all.reduce((sum, problem) => sum + problem.current_observations, 0)} label="aktuelle Beobachtungen" />
      </div>

      {!vorschau && query.isLoading ? (
        <Spinner className="min-h-[420px]" />
      ) : !vorschau && query.isError ? (
        <ErrorState onRetry={() => void query.refetch()} busy={query.isFetching} hint="Die öffentliche Problemkarte konnte nicht geladen werden." />
      ) : (
        <>
          <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-3 sm:flex-row sm:items-center">
            <label className="flex min-w-0 flex-1 items-center gap-2 text-sm font-medium text-foreground">
              <span className="shrink-0">Thema</span>
              <Select value={category} onChange={(event) => setCategory(event.target.value)} aria-label="Nach Thema filtern">
                <option value="all">Alle Themen</option>
                {categories.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
              </Select>
            </label>
            <label className="flex min-w-0 flex-1 items-center gap-2 text-sm font-medium text-foreground">
              <span className="shrink-0">Status</span>
              <Select value={status} onChange={(event) => setStatus(event.target.value as ProblemStatus | "all")} aria-label="Nach Status filtern">
                <option value="all">Alle Status</option>
                {STATUS_OPTIONS.map(([key, meta]) => <option key={key} value={key}>{meta.label}</option>)}
              </Select>
            </label>
            <span className="shrink-0 text-xs tabular-nums text-muted-foreground">{problems.length} sichtbar</span>
          </div>

          {problems.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border bg-card px-6 py-16 text-center">
              <p className="font-medium text-foreground">Keine Probleme für diese Filter</p>
              <button type="button" onClick={() => { setCategory("all"); setStatus("all"); }} className="mt-2 text-sm font-medium text-primary hover:underline">
                Filter zurücksetzen
              </button>
            </div>
          ) : (
            <div className="grid min-w-0 gap-4 breit:grid-cols-[minmax(0,1.65fr)_minmax(19rem,0.85fr)]">
              <div className="min-w-0 space-y-4">
                <ProblemMap problems={problems} selectedId={selectedId} onSelect={select} className="h-[440px] sm:h-[540px] breit:sticky breit:top-6" />
                {selected && <SelectedProblem problem={selected} />}
              </div>
              <div className="space-y-2" aria-label="Problemliste">
                {problems.map((problem) => (
                  <ProblemCard key={problem.id} problem={problem} selected={problem.id === selectedId} onSelect={select} />
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Metric({ icon: Icon, value, label }: { icon: typeof MapPin; value: number; label: string }) {
  return (
    <Card className="flex items-center gap-3 p-4">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"><Icon className="h-5 w-5" aria-hidden /></span>
      <span><strong className="block text-xl leading-none tabular-nums text-foreground">{value}</strong><span className="mt-1 block text-xs text-muted-foreground">{label}</span></span>
    </Card>
  );
}

function ProblemCard({ problem, selected, onSelect }: { problem: PublicProblem; selected: boolean; onSelect: (id: number) => void }) {
  const status = PROBLEM_STATUS[problem.status];
  const category = PROBLEM_KATEGORIEN[problem.category as keyof typeof PROBLEM_KATEGORIEN] ?? problem.category;
  return (
    <button
      type="button"
      onClick={() => onSelect(problem.id)}
      aria-pressed={selected}
      className={cn(
        "w-full rounded-xl border bg-card p-4 text-left transition-[border-color,box-shadow,transform] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        selected ? "border-primary shadow-lifted" : "border-border hover:border-primary/35",
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge color={status.color}>{status.label}</Badge>
        <span className="text-[11px] font-medium text-muted-foreground">{category}</span>
      </div>
      <h2 className="mt-2 text-base font-bold leading-snug text-foreground">{problem.title}</h2>
      <p className="mt-1 line-clamp-2 text-sm leading-relaxed text-muted-foreground">{problem.summary}</p>
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1"><MapPin className="h-3.5 w-3.5" aria-hidden />{problem.location_label || PROBLEM_SCOPE[problem.scope_kind]}</span>
        <span className="inline-flex items-center gap-1"><Users className="h-3.5 w-3.5" aria-hidden />{problem.unique_reporters}</span>
        <span className="inline-flex items-center gap-1"><CalendarClock className="h-3.5 w-3.5" aria-hidden />{formatDate(problem.last_observed_at)}</span>
      </div>
    </button>
  );
}

function SelectedProblem({ problem }: { problem: PublicProblem }) {
  const status = PROBLEM_STATUS[problem.status];
  return (
    <Card className="p-5" aria-live="polite">
      <div className="flex flex-wrap items-center gap-2">
        <Badge color={status.color}>{status.label}</Badge>
        <span className="text-xs text-muted-foreground">{PROBLEM_SCOPE[problem.scope_kind]} · zuletzt {formatDate(problem.last_observed_at)}</span>
      </div>
      <h2 className="mt-3 text-xl font-bold text-foreground">{problem.title}</h2>
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{problem.summary}</p>
      <dl className="mt-4 grid grid-cols-3 gap-2 border-t border-border pt-4 text-center">
        <div><dt className="text-[11px] text-muted-foreground">Reporter*innen</dt><dd className="mt-1 font-bold tabular-nums text-foreground">{problem.unique_reporters}</dd></div>
        <div><dt className="text-[11px] text-muted-foreground">Aktuell</dt><dd className="mt-1 font-bold tabular-nums text-foreground">{problem.current_observations}</dd></div>
        <div><dt className="text-[11px] text-muted-foreground">Insgesamt</dt><dd className="mt-1 font-bold tabular-nums text-foreground">{problem.total_observations}</dd></div>
      </dl>
      {problem.events && problem.events.length > 0 && (
        <div className="mt-5 border-t border-border pt-4">
          <h3 className="text-sm font-semibold text-foreground">Letzte öffentliche Änderung</h3>
          <div className="mt-2 flex gap-2 text-sm text-muted-foreground">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden />
            <p><span className="font-medium text-foreground">{problem.events[0].title}</span><br />{problem.events[0].detail}</p>
          </div>
        </div>
      )}
    </Card>
  );
}
