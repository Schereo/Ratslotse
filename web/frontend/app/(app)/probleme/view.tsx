"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Columns3, Info, Map as MapIcon, MapPin, MessageCircle, X } from "lucide-react";
import { api } from "@/lib/api";
import type { ProblemListResponse, PublicProblem, PublicProblemSummary, ProblemStatus } from "@/lib/types";
import { isProblemMappable, MELDE_HAEUFIGKEIT, meldeHaeufigkeit, PROBLEM_ANGEBOT, PROBLEM_KATEGORIEN, PROBLEM_SCOPE, PROBLEM_STATUS, unabhaengigeMeldungen, VORSCHAU_PROBLEME } from "@/lib/probleme";
import { Badge, Card, ErrorState, PageHeader, Segmented, Spinner, formatDate } from "@/components/ui";
import { cn } from "@/lib/utils";
import { isNativeApp } from "@/lib/platform";
import { PublicProblemDetail } from "@/components/public-problem-detail";

const ProblemMap = dynamic(
  () => import("@/components/problem-map").then((module) => module.ProblemMap),
  { ssr: false, loading: () => <div className="h-[62dvh] min-h-[420px] max-h-[720px] animate-pulse rounded-xl border border-border bg-muted" /> },
);

type Ansicht = "karte" | "status";
const STATUS_OPTIONS = Object.entries(PROBLEM_STATUS) as [ProblemStatus, (typeof PROBLEM_STATUS)[ProblemStatus]][];

export default function View({ vorschau }: { vorschau: boolean }) {
  const searchParams = useSearchParams();
  const linkedProblem = searchParams.get("problem");
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
  const [native, setNative] = useState(false);

  const mappableProblems = useMemo(() => all.filter(isProblemMappable), [all]);
  const mapProblems = useMemo(
    () => mappableProblems.filter((problem) => category === "all" || problem.category === category),
    [mappableProblems, category],
  );
  // Das Status-Board bleibt vollständig; die Karte zeigt nur ehrlich verortbare Probleme.
  const visibleProblems = ansicht === "status" ? all : mapProblems;
  const detailQuery = useQuery({
    queryKey: ["public-problem", selectedId],
    queryFn: () => api.get<PublicProblem>(`/probleme/${selectedId}`),
    enabled: !vorschau && selectedId !== null,
    staleTime: 60_000,
  });
  const selected = vorschau
    ? VORSCHAU_PROBLEME.find((problem) => problem.id === selectedId) ?? null
    : detailQuery.data ?? null;
  const categories = useMemo(() => {
    const present = new Set(mappableProblems.map((problem) => problem.category));
    return Object.entries(PROBLEM_KATEGORIEN).filter(([key]) => present.has(key));
  }, [mappableProblems]);

  useEffect(() => {
    setNative(isNativeApp());
  }, []);

  useEffect(() => {
    setAnsicht(searchParams.get("view") === "status" ? "status" : "karte");
  }, [searchParams]);

  useEffect(() => {
    if (all.length === 0) return;
    const linkedId = Number(linkedProblem);
    const linked = Number.isSafeInteger(linkedId)
      ? all.find((problem) => problem.id === linkedId)
      : null;
    if (!linked) {
      if (selectedId !== null) setSelectedId(null);
      return;
    }
    if (selectedId !== linkedId) {
      setSelectedId(linkedId);
      if (isProblemMappable(linked) && category !== "all" && category !== linked.category) {
        setCategory("all");
      }
    }
    if (isProblemMappable(linked)) return;
    setAnsicht("status");
    const url = new URL(window.location.href);
    if (url.searchParams.get("view") === "status") return;
    url.searchParams.set("view", "status");
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  }, [all, linkedProblem, selectedId, category]);

  useEffect(() => {
    if (
      selectedId === null
      || Number(linkedProblem) !== selectedId
      || visibleProblems.some((problem) => problem.id === selectedId)
    ) return;
    setSelectedId(null);
    const url = new URL(window.location.href);
    url.searchParams.delete("problem");
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  }, [visibleProblems, selectedId, linkedProblem]);

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
    if (next === "status") {
      url.searchParams.set("view", "status");
    } else {
      url.searchParams.delete("view");
      const selectedProblem = all.find((problem) => problem.id === selectedId);
      if (selectedProblem && !isProblemMappable(selectedProblem)) {
        setSelectedId(null);
        url.searchParams.delete("problem");
      }
    }
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  }, [all, selectedId]);

  const detailPanel = selectedId === null ? null : selected ? (
    <SelectedProblem problem={selected} onClose={closeDetail} native={native} />
  ) : !vorschau && detailQuery.isError ? (
    <ErrorState
      title="Details konnten nicht geladen werden"
      onRetry={() => void detailQuery.refetch()}
      busy={detailQuery.isFetching}
    />
  ) : (
    <Spinner className="rounded-xl border border-border bg-card py-8" />
  );

  return (
    <div className="space-y-4">
      <PageHeader
        title={PROBLEM_ANGEBOT.name}
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
      </div>

      {ansicht === "karte" && (
        <div className="flex flex-wrap gap-2" role="group" aria-label="Kartenthemen">
          <ThemeFilter active={category === "all"} onClick={() => setCategory("all")}>
            Alle
          </ThemeFilter>
          {categories.map(([key, label]) => (
            <ThemeFilter key={key} active={category === key} onClick={() => setCategory(key)}>
              {label}
            </ThemeFilter>
          ))}
        </div>
      )}

      <div className="flex flex-col gap-2 text-xs leading-relaxed text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
        <p className="flex items-start gap-1.5">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          Farben zeigen nur die Meldehäufigkeit, nicht die amtliche Dringlichkeit. Status sind Ratslotse-Einordnungen, keine amtlichen Bearbeitungsstände. Exakte Zahlen erscheinen nach Auswahl.
        </p>
        <FrequencyLegend />
      </div>

      {!vorschau && query.isLoading ? (
        <Spinner className="min-h-[420px]" />
      ) : !vorschau && query.isError ? (
        <ErrorState onRetry={() => void query.refetch()} busy={query.isFetching} hint="Die öffentliche Problemkarte konnte nicht geladen werden." />
      ) : native && selectedId !== null ? (
        detailPanel
      ) : visibleProblems.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border bg-card px-6 py-16 text-center">
          <p className="font-medium text-foreground">
            {category === "all" ? "Noch keine veröffentlichten Probleme" : "Keine Probleme für dieses Thema"}
          </p>
          {category !== "all" && (
            <button type="button" onClick={() => setCategory("all")} className="mt-2 text-sm font-medium text-primary hover:underline">
              Alle Themen zeigen
            </button>
          )}
        </div>
      ) : ansicht === "karte" ? (
        <div className="space-y-4">
          <ProblemMap
            problems={mapProblems}
            selectedId={selectedId}
            onSelect={select}
            className="h-[62dvh] min-h-[420px] max-h-[720px]"
          />
          {detailPanel}
        </div>
      ) : (
        <div className="space-y-4">
          <KanbanBoard problems={all} selectedId={selectedId} onSelect={select} />
          {detailPanel}
        </div>
      )}
    </div>
  );
}

function ThemeFilter({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "min-h-10 shrink-0 rounded-full border px-3.5 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border bg-card text-muted-foreground hover:border-primary/40 hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

function FrequencyLegend() {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1" aria-label="Legende der Meldehäufigkeit">
      {[1, 2, 5, 10].map((count) => {
        const frequency = meldeHaeufigkeit(count);
        return (
          <span key={frequency} className="inline-flex items-center gap-1">
            <span className={`problem-frequency-dot frequency-${frequency}`} aria-hidden />
            {MELDE_HAEUFIGKEIT[frequency]}
          </span>
        );
      })}
    </div>
  );
}

function KanbanBoard({
  problems,
  selectedId,
  onSelect,
}: {
  problems: PublicProblemSummary[];
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
  problem: PublicProblemSummary;
  selected: boolean;
  onSelect: (id: number) => void;
}) {
  const frequency = problem.frequency;
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
      <div className="flex items-start gap-2">
        <span className={`problem-frequency-dot frequency-${frequency} mt-1 shrink-0`} aria-hidden />
        <h3 className="text-sm font-semibold leading-snug text-foreground">
          {problem.title}<span className="sr-only"> · {MELDE_HAEUFIGKEIT[frequency]}</span>
        </h3>
      </div>
      <p className="mt-2 flex items-center gap-1 text-xs text-muted-foreground">
        <MapPin className="h-3.5 w-3.5 shrink-0" aria-hidden />
        <span className="truncate">{problem.location_label || PROBLEM_SCOPE[problem.scope_kind]}</span>
      </p>
    </button>
  );
}

function SelectedProblem({
  problem,
  onClose,
  native,
}: {
  problem: PublicProblem;
  onClose: () => void;
  native: boolean;
}) {
  const status = PROBLEM_STATUS[problem.status];
  if (native) return <PublicProblemDetail problem={problem} onClose={onClose} headingLevel={2} />;
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
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{problem.summary}</p>
      <div className="mt-4 flex items-center gap-2.5 rounded-xl border border-primary/15 bg-primary/5 px-3 py-2.5 text-sm font-semibold text-foreground">
        <MessageCircle className="h-4 w-4 shrink-0 text-primary" aria-hidden />
        <span className="tabular-nums">{unabhaengigeMeldungen(problem.independent_reports)}</span>
      </div>
      {problem.events && problem.events.length > 0 && (
        <div className="mt-5 border-t border-border pt-4">
          <h3 className="text-sm font-semibold text-foreground">Letzte öffentliche Änderung</h3>
          <div className="mt-2 flex gap-2 text-sm text-muted-foreground">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden />
            <p><span className="font-medium text-foreground">{problem.events[0].title}</span><br />{problem.events[0].detail}</p>
          </div>
        </div>
      )}
      <Link
        href={`/probleme/${problem.id}`}
        className="mt-5 inline-flex rounded-md text-sm font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        Problemseite öffnen
      </Link>
    </Card>
  );
}
