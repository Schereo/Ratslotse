"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CalendarClock, CheckCircle2, Columns3, Info, Map as MapIcon, MapPin, Users, X } from "lucide-react";
import { api } from "@/lib/api";
import type { ProblemListResponse, PublicProblem, ProblemStatus } from "@/lib/types";
import { PROBLEM_KATEGORIEN, PROBLEM_SCOPE, PROBLEM_STATUS, VORSCHAU_PROBLEME } from "@/lib/probleme";
import { Badge, Card, ErrorState, PageHeader, Segmented, Select, Spinner, formatDate } from "@/components/ui";
import { cn } from "@/lib/utils";

const ProblemMap = dynamic(
  () => import("@/components/problem-map").then((module) => module.ProblemMap),
  { ssr: false, loading: () => <div className="h-[62dvh] min-h-[420px] max-h-[720px] animate-pulse rounded-xl border border-border bg-muted" /> },
);

type Ansicht = "karte" | "status";
const STATUS_OPTIONS = Object.entries(PROBLEM_STATUS) as [ProblemStatus, (typeof PROBLEM_STATUS)[ProblemStatus]][];

export default function View({ vorschau }: { vorschau: boolean }) {
  const query = useQuery({
    queryKey: ["public-problems"],
    queryFn: () => api.get<ProblemListResponse>("/probleme"),
    enabled: !vorschau,
    staleTime: 60_000,
  });
  const all = vorschau ? VORSCHAU_PROBLEME : (query.data?.problems ?? []);
  const [ansicht, setAnsicht] = useState<Ansicht>("karte");
  const [category, setCategory] = useState("all");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const problems = useMemo(
    () => all.filter((problem) => category === "all" || problem.category === category),
    [all, category],
  );
  const selected = problems.find((problem) => problem.id === selectedId) ?? null;
  const categories = useMemo(() => {
    const present = new Set(all.map((problem) => problem.category));
    return Object.entries(PROBLEM_KATEGORIEN).filter(([key]) => present.has(key));
  }, [all]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("view") === "status") setAnsicht("status");
  }, []);

  useEffect(() => {
    if (selectedId !== null || all.length === 0) return;
    const initial = Number(new URLSearchParams(window.location.search).get("problem"));
    if (Number.isSafeInteger(initial) && all.some((problem) => problem.id === initial)) setSelectedId(initial);
  }, [all, selectedId]);

  useEffect(() => {
    if (selectedId === null || problems.some((problem) => problem.id === selectedId)) return;
    setSelectedId(null);
    const url = new URL(window.location.href);
    url.searchParams.delete("problem");
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  }, [problems, selectedId]);

  const select = useCallback((id: number) => {
    setSelectedId(id);
    const url = new URL(window.location.href);
    url.searchParams.set("problem", String(id));
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  }, []);

  const closeDetail = useCallback(() => {
    setSelectedId(null);
    const url = new URL(window.location.href);
    url.searchParams.delete("problem");
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  }, []);

  const changeView = useCallback((next: Ansicht) => {
    setAnsicht(next);
    const url = new URL(window.location.href);
    if (next === "status") url.searchParams.set("view", "status");
    else url.searchParams.delete("view");
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  }, []);

  return (
    <div className="space-y-4">
      <PageHeader
        title="Oldenburgs Problemkarte"
        description="Beobachtungen aus der Stadt, geprüft und ohne persönliche Angaben gebündelt."
      />

      {vorschau && (
        <p className="rounded-lg border border-amber-300/70 bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-950 dark:border-amber-700/60 dark:bg-amber-950/35 dark:text-amber-100" role="status">
          <strong>Vorschau:</strong> Alle gezeigten Probleme und Zahlen sind frei erfunden. Noch kann niemand etwas melden.
        </p>
      )}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Segmented
          value={ansicht}
          onChange={changeView}
          options={[
            { value: "karte", label: "Karte", icon: MapIcon },
            { value: "status", label: "Status", icon: Columns3 },
          ]}
          className="w-full sm:w-64"
        />
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="shrink-0">Thema</span>
          <Select
            value={category}
            onChange={(event) => setCategory(event.target.value)}
            aria-label="Nach Thema filtern"
            className="min-w-0 sm:w-64"
          >
            <option value="all">Alle Themen</option>
            {categories.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </Select>
        </label>
      </div>

      <p className="flex items-start gap-1.5 text-xs leading-relaxed text-muted-foreground">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
        Die Zahl am Problem meint unabhängige Reporter*innen. Angezeigte Status sind Ratslotse-Einordnungen, keine amtlichen Bearbeitungsstände.
      </p>

      {!vorschau && query.isLoading ? (
        <Spinner className="min-h-[420px]" />
      ) : !vorschau && query.isError ? (
        <ErrorState onRetry={() => void query.refetch()} busy={query.isFetching} hint="Die öffentliche Problemkarte konnte nicht geladen werden." />
      ) : problems.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border bg-card px-6 py-16 text-center">
          <p className="font-medium text-foreground">Keine Probleme für dieses Thema</p>
          <button type="button" onClick={() => setCategory("all")} className="mt-2 text-sm font-medium text-primary hover:underline">
            Alle Themen zeigen
          </button>
        </div>
      ) : ansicht === "karte" ? (
        <div className="space-y-4">
          <ProblemMap
            problems={problems}
            selectedId={selectedId}
            onSelect={select}
            className="h-[62dvh] min-h-[420px] max-h-[720px]"
          />
          {selected && <SelectedProblem problem={selected} onClose={closeDetail} />}
        </div>
      ) : (
        <div className="space-y-4">
          <KanbanBoard problems={problems} selectedId={selectedId} onSelect={select} />
          {selected && <SelectedProblem problem={selected} onClose={closeDetail} />}
        </div>
      )}
    </div>
  );
}

function KanbanBoard({
  problems,
  selectedId,
  onSelect,
}: {
  problems: PublicProblem[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}) {
  return (
    <div className="overflow-x-auto pb-2" aria-label="Probleme nach Status">
      <div className="grid min-w-[82rem] grid-cols-5 gap-3">
        {STATUS_OPTIONS.map(([status, meta]) => {
          const entries = problems.filter((problem) => problem.status === status);
          return (
            <section key={status} className="rounded-xl bg-muted/55 p-2.5" aria-labelledby={`status-${status}`}>
              <div className="flex items-center justify-between gap-2 px-1 pb-2">
                <h2 id={`status-${status}`} className="text-sm font-semibold text-foreground">{meta.label}</h2>
                <span className="rounded-full bg-card px-2 py-0.5 text-xs tabular-nums text-muted-foreground">{entries.length}</span>
              </div>
              <div className="space-y-2">
                {entries.map((problem) => (
                  <KanbanCard
                    key={problem.id}
                    problem={problem}
                    selected={problem.id === selectedId}
                    onSelect={onSelect}
                  />
                ))}
                {entries.length === 0 && (
                  <p className="rounded-lg border border-dashed border-border/80 px-3 py-5 text-center text-xs text-muted-foreground">Keine Probleme</p>
                )}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}

function KanbanCard({
  problem,
  selected,
  onSelect,
}: {
  problem: PublicProblem;
  selected: boolean;
  onSelect: (id: number) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect(problem.id)}
      aria-pressed={selected}
      className={cn(
        "w-full rounded-lg border bg-card p-3 text-left shadow-sm transition-[border-color,box-shadow,transform] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        selected ? "border-primary shadow-lifted" : "border-border hover:border-primary/35",
      )}
    >
      <h3 className="text-sm font-semibold leading-snug text-foreground">{problem.title}</h3>
      <p className="mt-2 flex items-center gap-1 text-xs text-muted-foreground">
        <MapPin className="h-3.5 w-3.5 shrink-0" aria-hidden />
        <span className="truncate">{problem.location_label || PROBLEM_SCOPE[problem.scope_kind]}</span>
      </p>
      <div className="mt-3 flex items-center justify-between gap-2 border-t border-border/70 pt-2 text-[11px] text-muted-foreground">
        <span className="inline-flex items-center gap-1"><Users className="h-3.5 w-3.5" aria-hidden />{problem.unique_reporters}</span>
        <span>{formatDate(problem.last_observed_at)}</span>
      </div>
    </button>
  );
}

function SelectedProblem({ problem, onClose }: { problem: PublicProblem; onClose: () => void }) {
  const status = PROBLEM_STATUS[problem.status];
  return (
    <Card className="relative p-5" aria-live="polite">
      <button
        type="button"
        onClick={onClose}
        aria-label="Detail schließen"
        className="absolute right-3 top-3 flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground"
      >
        <X className="h-4 w-4" />
      </button>
      <div className="flex flex-wrap items-center gap-2 pr-10">
        <Badge color={status.color}>{status.label}</Badge>
        <span className="text-xs text-muted-foreground">{PROBLEM_SCOPE[problem.scope_kind]} · zuletzt {formatDate(problem.last_observed_at)}</span>
      </div>
      <h2 className="mt-3 text-xl font-bold text-foreground">{problem.title}</h2>
      <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">{problem.summary}</p>
      <dl className="mt-4 grid max-w-xl grid-cols-3 gap-2 border-t border-border pt-4 text-center">
        <div><dt className="text-[11px] text-muted-foreground">Reporter*innen</dt><dd className="mt-1 font-bold tabular-nums text-foreground">{problem.unique_reporters}</dd></div>
        <div><dt className="text-[11px] text-muted-foreground">Aktuell</dt><dd className="mt-1 font-bold tabular-nums text-foreground">{problem.current_observations}</dd></div>
        <div><dt className="text-[11px] text-muted-foreground">Insgesamt</dt><dd className="mt-1 font-bold tabular-nums text-foreground">{problem.total_observations}</dd></div>
      </dl>
      {problem.events && problem.events.length > 0 && (
        <div className="mt-5 max-w-3xl border-t border-border pt-4">
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
