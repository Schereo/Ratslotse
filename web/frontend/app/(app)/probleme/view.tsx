"use client";

import dynamic from "next/dynamic";
import { type ReactElement, type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import {
  ChevronDown,
  Info,
  ListOrdered,
  Map as MapIcon,
  MapPin,
  Navigation,
  X,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { MeldeRangbalken } from "@/components/grafik/melde-rangbalken";
import { Mascot } from "@/components/mascot";
import { EmptyState, ErrorState, PageHeader, Segmented, Spinner } from "@/components/ui";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import { vertrag } from "@/lib/vertrag";
import {
  isProblemMappable,
  MELDE_HAEUFIGKEIT,
  PROBLEM_ANGEBOT,
  PROBLEM_KATEGORIEN,
  PROBLEM_SCOPE,
  PROBLEM_STATUS,
  reportCountLabel,
  type ProblemFrequency,
  type ProblemStatus,
  type PublicProblem,
} from "@/lib/probleme";

const ProblemMap = dynamic(
  () => import("@/components/problem-map").then((module) => module.ProblemMap),
  {
    ssr: false,
    loading: () => (
      <div className="h-[62dvh] min-h-[420px] max-h-[720px] motion-safe:animate-pulse rounded-xl border border-border bg-muted" />
    ),
  },
);

type Ansicht = "karte" | "meistgemeldet";
const STATUS_OPTIONS = Object.entries(PROBLEM_STATUS) as [ProblemStatus, string][];
const CATEGORY_OPTIONS = Object.entries(PROBLEM_KATEGORIEN) as [PublicProblem["category"], string][];
const FREQUENCY_OPTIONS = Object.entries(MELDE_HAEUFIGKEIT) as [ProblemFrequency, string][];
const EMPTY_PROBLEMS: PublicProblem[] = [];

export default function View() {
  const query = useQuery({
    queryKey: ["public-problems"],
    queryFn: () => vertrag.get("/probleme"),
    staleTime: 60_000,
  });
  const all = query.data?.problems ?? EMPTY_PROBLEMS;
  const [ansicht, setAnsicht] = useState<Ansicht>("karte");
  const [category, setCategory] = useState<PublicProblem["category"] | "all">("all");
  const [problemStatus, setProblemStatus] = useState<ProblemStatus | "all">("all");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const statusProblems = useMemo(
    () => all.filter((problem) => problemStatus === "all" || problem.status === problemStatus),
    [all, problemStatus],
  );
  const mapProblems = useMemo(
    () => statusProblems.filter((problem) => (
      isProblemMappable(problem) && (category === "all" || problem.category === category)
    )),
    [statusProblems, category],
  );
  const selected = all.find((problem) => problem.id === selectedId) ?? null;
  const fictional = all.some((problem) => problem.fictional);

  useEffect(() => {
    const view = new URLSearchParams(window.location.search).get("view");
    if (view === "meistgemeldet" || view === "status") setAnsicht("meistgemeldet");
  }, []);

  useEffect(() => {
    if (selected && problemStatus !== "all" && selected.status !== problemStatus) {
      setSelectedId(null);
    }
  }, [problemStatus, selected]);

  const changeView = useCallback((next: Ansicht) => {
    setAnsicht(next);
    const url = new URL(window.location.href);
    if (next === "meistgemeldet") url.searchParams.set("view", "meistgemeldet");
    else url.searchParams.delete("view");
    window.history.replaceState(null, "", `${url.pathname}${url.search}`);
  }, []);

  const showOnMap = useCallback((problem: PublicProblem) => {
    setCategory("all");
    setProblemStatus("all");
    setSelectedId(problem.id);
    changeView("karte");
  }, [changeView]);

  return (
    <div className="space-y-4">
      <PageHeader title={PROBLEM_ANGEBOT.name} />

      {fictional && (
        <div className="inline-flex min-h-10 max-w-full items-center gap-1 rounded-full border border-amber-200 bg-amber-50 py-1 pl-3 pr-1 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950/35 dark:text-amber-100">
          <span role="status"><strong>Feature-Vorschau</strong> · frei erfundene Beispiele</span>
          <InfoPopover
            contentLabel="Fiktive Beispiele"
            trigger={(
              <button type="button" aria-label="Mehr zu den fiktiven Beispielen" className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-colors hover:bg-amber-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:hover:bg-amber-900/60">
                <Info className="h-3.5 w-3.5" aria-hidden />
              </button>
            )}
          >
            <p>Alle als Beispiel bezeichneten Einträge und Zahlen sind frei erfunden.</p>
            <p className="mt-2">Sie zeigen nur, wie die Übersicht funktioniert.</p>
          </InfoPopover>
        </div>
      )}

      <Segmented
        value={ansicht}
        onChange={changeView}
        options={[
          { value: "karte", label: "Karte", icon: MapIcon },
          { value: "meistgemeldet", label: "Meistgemeldet", icon: ListOrdered },
        ]}
        className="w-full sm:w-80"
      />

      <div className="flex flex-wrap items-end justify-between gap-3">
        {ansicht === "karte" ? (
          <div className="flex flex-wrap gap-2" role="group" aria-label="Kartenthemen">
            <ThemeFilter active={category === "all"} onClick={() => setCategory("all")}>Alle</ThemeFilter>
            {CATEGORY_OPTIONS.map(([key, label]) => (
              <ThemeFilter key={key} active={category === key} onClick={() => setCategory(key)}>{label}</ThemeFilter>
            ))}
          </div>
        ) : <span />}
        <label className="grid gap-1 text-[11px] font-medium text-muted-foreground">
          <span className="font-mono uppercase tracking-[0.1em]">Status filtern</span>
          <select
            aria-label="Status filtern"
            value={problemStatus}
            onChange={(event) => setProblemStatus(event.target.value as ProblemStatus | "all")}
            className="min-h-11 rounded-lg border border-border bg-card px-3 text-sm font-medium text-foreground shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <option value="all">Alle ungelösten Status</option>
            {STATUS_OPTIONS.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select>
        </label>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <p className="flex items-center gap-1.5">
          <Info className="h-3.5 w-3.5 shrink-0" aria-hidden />
          Unabhängig · kein Angebot der Stadt Oldenburg · keine amtlichen Status.
        </p>
        <InfoPopover
          contentLabel="Farben und Status"
          align="end"
          className="w-80"
          trigger={(
            <button type="button" aria-label="Farben und Status erklären" className="inline-flex min-h-10 items-center gap-1.5 rounded-lg px-2 font-medium text-primary transition-colors hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
              <Info className="h-3.5 w-3.5" aria-hidden /> Farben &amp; Status
            </button>
          )}
        >
          <p className="font-semibold text-foreground">Farben</p>
          <p className="mt-1">Farben zeigen die Zahl unabhängiger Meldungen, nicht die Dringlichkeit.</p>
          <p className="mt-3 font-semibold text-foreground">Status</p>
          <p className="mt-1">Status sind Einordnungen von Ratslotse, keine amtlichen Bearbeitungsstände.</p>
          <p className="mt-1">Eine Bearbeitung durch die Stadt zeigen wir nur mit überprüfbarer städtischer Quelle.</p>
        </InfoPopover>
      </div>

      <FrequencyScale />

      {query.isLoading ? (
        <Spinner className="min-h-[420px] rounded-xl border border-border bg-card" />
      ) : query.isError ? (
        <ErrorState hint="Die öffentliche Problemkarte konnte nicht geladen werden." onRetry={() => void query.refetch()} busy={query.isFetching} />
      ) : all.length === 0 ? (
        <EmptyState mascot="search" title="Noch keine veröffentlichten ungelösten Probleme" hint="Schau später noch einmal vorbei." />
      ) : ansicht === "karte" ? (
        mapProblems.length === 0 ? (
          <EmptyState
            mascot="search"
            title="Keine kartierbaren Probleme für diese Auswahl"
            action={<button type="button" onClick={() => { setCategory("all"); setProblemStatus("all"); }} className="min-h-11 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium text-primary hover:bg-muted">Alle ungelösten Probleme zeigen</button>}
          />
        ) : (
          <div className="space-y-3">
            <ProblemMap problems={mapProblems} selectedId={selectedId} onSelect={setSelectedId} className="h-[62dvh] min-h-[420px] max-h-[720px]" />
            {selected && isProblemMappable(selected) && <SelectedProblem problem={selected} onClose={() => setSelectedId(null)} />}
          </div>
        )
      ) : statusProblems.length === 0 ? (
        <EmptyState mascot="search" title="Keine ungelösten Probleme mit diesem Status" hint="Wähle einen anderen Status." />
      ) : (
        <Leaderboard problems={statusProblems} allProblems={all} selectedId={selectedId} onSelect={setSelectedId} onShowMap={showOnMap} />
      )}
    </div>
  );
}

function InfoPopover({ trigger, contentLabel, align = "start", className, children }: {
  trigger: ReactElement;
  contentLabel: string;
  align?: "start" | "center" | "end";
  className?: string;
  children: ReactNode;
}) {
  return (
    <Popover>
      <PopoverTrigger asChild>{trigger}</PopoverTrigger>
      <PopoverContent aria-label={contentLabel} align={align} className={cn("w-72 max-w-[calc(100vw-2rem)] p-3 text-xs leading-relaxed text-muted-foreground", className)}>
        {children}
      </PopoverContent>
    </Popover>
  );
}

function ThemeFilter({ active, onClick, children }: { active: boolean; onClick: () => void; children: string }) {
  return (
    <button type="button" aria-pressed={active} onClick={onClick} className={cn(
      "min-h-11 rounded-full border px-3.5 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      active ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card text-muted-foreground hover:border-primary/40 hover:text-foreground",
    )}>{children}</button>
  );
}

function FrequencyScale() {
  return (
    <div className="rounded-xl border border-border bg-card px-3 py-2.5 shadow-sm" aria-label="Hafenblau-Skala der Meldehäufigkeit">
      <div className="flex items-center justify-between gap-3">
        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">Meldehäufigkeit</span>
        <span className="text-[10px] text-muted-foreground">hell bis dunkel</span>
      </div>
      <div className="mt-2 grid grid-cols-4 gap-1.5">
        {FREQUENCY_OPTIONS.map(([frequency, label]) => (
          <span key={frequency} className="min-w-0 text-center text-[10px] font-medium text-muted-foreground">
            <span className={`frequency-${frequency} block h-2 rounded-full bg-[var(--problem-frequency)]`} aria-hidden />
            <span className="mt-1 block leading-tight">{label}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

function Leaderboard({ problems, allProblems, selectedId, onSelect, onShowMap }: {
  problems: PublicProblem[];
  allProblems: PublicProblem[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  onShowMap: (problem: PublicProblem) => void;
}) {
  const observedProblem = problems[0];
  const maxReports = Math.max(...allProblems.map((problem) => problem.independent_reports));
  const ranks = new Map(allProblems.map((problem, index) => [problem.id, index + 1]));

  return (
    <section className="space-y-4" aria-labelledby="meistgemeldet-heading">
      <div className="overflow-hidden rounded-2xl border border-primary/20 bg-primary/[0.045] px-4 py-3 sm:px-6 sm:py-4">
        <div className="grid items-center gap-3 sm:grid-cols-[7rem_1fr]">
          <Mascot
            pose="point"
            regie="ruhig"
            label={`Lotti zeigt auf das meistgemeldete Problem dieser Auswahl: ${observedProblem.title}`}
            className="mx-auto h-24 w-24 sm:h-28 sm:w-28"
          />
          <div>
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-primary">Gemeinschaftliche Aufmerksamkeit</p>
            <h2 id="meistgemeldet-heading" className="mt-1 font-display text-2xl font-bold text-foreground sm:text-3xl">Meistgemeldet</h2>
            <p id="report-count-explanation" className="mt-2 max-w-[76ch] text-[13px] leading-relaxed text-muted-foreground">
              Die lebenszeitliche Zahl unabhängiger freigegebener Meldungen zeigt gemeinschaftliche Aufmerksamkeit. Sie ist keine Aussage über Wahrheit, Dringlichkeit, Schadenshöhe oder die Zahl betroffener Personen.
            </p>
          </div>
        </div>
      </div>

      <ol className="space-y-2.5" aria-label="Meistgemeldete ungelöste Probleme">
        {problems.map((problem) => {
          const rank = ranks.get(problem.id) ?? 0;
          const expanded = selectedId === problem.id;
          return (
            <LeaderboardEntry
              key={problem.id}
              problem={problem}
              rank={rank}
              maxReports={maxReports}
              expanded={expanded}
              onToggle={() => onSelect(expanded ? null : problem.id)}
              onShowMap={() => onShowMap(problem)}
            />
          );
        })}
      </ol>
    </section>
  );
}

function LeaderboardEntry({ problem, rank, maxReports, expanded, onToggle, onShowMap }: {
  problem: PublicProblem;
  rank: number;
  maxReports: number;
  expanded: boolean;
  onToggle: () => void;
  onShowMap: () => void;
}) {
  const previewId = `problem-preview-${problem.id}`;
  const countLabel = reportCountLabel(problem.independent_reports);
  const topThree = rank <= 3;

  return (
    <li
      data-ranggruppe={topThree ? "top-drei" : "weitere"}
      className={cn(
        "problem-disclosure-card overflow-hidden rounded-xl border bg-card shadow-sm transition-[border-color,background-color]",
        topThree ? "border-primary/25 bg-primary/[0.025]" : "border-border",
        expanded && "border-primary/45",
      )}
    >
      <button
        type="button"
        aria-expanded={expanded}
        aria-controls={previewId}
        aria-describedby="report-count-explanation"
        aria-label={`${rank}. ${problem.title}, ${countLabel}`}
        onClick={onToggle}
        className="grid min-h-[5.5rem] w-full grid-cols-[2.75rem_1fr_auto] items-center gap-2.5 px-3 py-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring sm:grid-cols-[3.5rem_1fr_auto] sm:gap-4 sm:px-4"
      >
        <span className={cn(
          "font-sans text-xl font-bold tabular-nums text-muted-foreground",
          topThree && "text-primary sm:text-2xl",
        )} aria-hidden>{String(rank).padStart(2, "0")}</span>
        <span className="min-w-0">
          <span className="block text-sm font-semibold leading-snug text-foreground sm:text-[15px]">{problem.title}</span>
          <span className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
            <strong className="font-semibold tabular-nums text-foreground">{countLabel}</strong>
            <span aria-hidden>·</span>
            <StatusBadge status={problem.status} />
          </span>
          <span className="mt-2 block">
            <MeldeRangbalken
              wert={problem.independent_reports}
              maximum={maxReports}
              haeufigkeit={problem.frequency}
            />
          </span>
        </span>
        <ChevronDown className={cn("problem-disclosure-chevron h-5 w-5 text-muted-foreground transition-transform", expanded && "rotate-180")} aria-hidden />
      </button>

      {expanded && (
        <div id={previewId} className="problem-preview border-t border-border/70 px-4 py-3 sm:ml-[4.5rem] sm:px-0 sm:pr-4" role="region" aria-label={`Vorschau: ${problem.title}`}>
          <p className="max-w-[76ch] text-[13px] leading-relaxed text-foreground/85">{problem.summary}</p>
          <p className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
            <MapPin className="h-3.5 w-3.5 shrink-0" aria-hidden />
            {problem.location_label || PROBLEM_SCOPE[problem.scope_kind]}
            <span aria-hidden>·</span>
            {PROBLEM_KATEGORIEN[problem.category]}
          </p>
          {isProblemMappable(problem) ? (
            <button type="button" onClick={onShowMap} aria-label={`${problem.title} auf der Karte zeigen`} className="mt-3 inline-flex min-h-11 items-center gap-2 rounded-lg border border-primary/25 bg-primary/5 px-3 py-2 text-sm font-semibold text-primary transition-colors hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
              <Navigation className="h-4 w-4" aria-hidden /> Auf der Karte zeigen
            </button>
          ) : (
            <p className="mt-3 rounded-lg border border-dashed border-border bg-muted/45 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
              {problem.scope_kind === "citywide"
                ? "Kein einzelner Kartenort: Dieses Beispiel gilt für das gesamte Stadtgebiet."
                : "Keine brauchbare Geometrie: Dieses Beispiel kann nicht ehrlich auf der Karte gezeigt werden."}
            </p>
          )}
        </div>
      )}
    </li>
  );
}

function StatusBadge({ status }: { status: PublicProblem["status"] }) {
  return (
    <span className="inline-flex rounded-full border border-border bg-muted/65 px-2 py-0.5 text-[10.5px] font-semibold text-muted-foreground">
      {PROBLEM_STATUS[status]}
    </span>
  );
}

function SelectedProblem({ problem, onClose }: { problem: PublicProblem; onClose: () => void }) {
  return (
    <div className="relative rounded-xl border border-primary/20 bg-card p-4" aria-live="polite">
      <button type="button" onClick={onClose} aria-label="Auswahl schließen" className="absolute right-2 top-2 flex h-10 w-10 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
        <X className="h-4 w-4" aria-hidden />
      </button>
      <div className="flex flex-wrap items-center gap-2 pr-10">
        <StatusBadge status={problem.status} />
        <strong className="text-xs font-semibold tabular-nums text-primary">{reportCountLabel(problem.independent_reports)}</strong>
      </div>
      <h2 className="mt-2 pr-10 font-display text-base font-bold text-foreground">{problem.title}</h2>
      <p className="mt-1 max-w-[76ch] text-[13px] leading-relaxed text-foreground/85">{problem.summary}</p>
      <p className="mt-2 flex items-center gap-1 text-xs text-muted-foreground">
        <MapPin className="h-3.5 w-3.5 shrink-0" aria-hidden />
        {problem.location_label || PROBLEM_SCOPE[problem.scope_kind]}
      </p>
    </div>
  );
}
