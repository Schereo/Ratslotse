"use client";

import dynamic from "next/dynamic";
import { type ReactElement, type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { Columns3, Info, Map as MapIcon, MapPin, X } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
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
  type ProblemFrequency,
  type ProblemStatus,
  type PublicProblem,
} from "@/lib/probleme";

const ProblemMap = dynamic(
  () => import("@/components/problem-map").then((module) => module.ProblemMap),
  { ssr: false, loading: () => <div className="h-[62dvh] min-h-[420px] max-h-[720px] animate-pulse rounded-xl border border-border bg-muted" /> },
);

type Ansicht = "karte" | "status";
const STATUS_OPTIONS = Object.entries(PROBLEM_STATUS) as [ProblemStatus, string][];
const CATEGORY_OPTIONS = Object.entries(PROBLEM_KATEGORIEN) as [PublicProblem["category"], string][];
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
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const mappable = useMemo(() => all.filter(isProblemMappable), [all]);
  const mapProblems = useMemo(
    () => mappable.filter((problem) => category === "all" || problem.category === category),
    [mappable, category],
  );
  const selected = all.find((problem) => problem.id === selectedId) ?? null;
  const fictional = all.some((problem) => problem.fictional);

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("view") === "status") {
      setAnsicht("status");
    }
  }, []);

  const changeView = useCallback((next: Ansicht) => {
    setAnsicht(next);
    const url = new URL(window.location.href);
    if (next === "status") url.searchParams.set("view", "status");
    else url.searchParams.delete("view");
    window.history.replaceState(null, "", `${url.pathname}${url.search}`);
  }, []);

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
          { value: "status", label: "Status", icon: Columns3 },
        ]}
        className="w-full sm:w-64"
      />

      {ansicht === "karte" && (
        <div className="flex flex-wrap gap-2" role="group" aria-label="Kartenthemen">
          <ThemeFilter active={category === "all"} onClick={() => setCategory("all")}>Alle</ThemeFilter>
          {CATEGORY_OPTIONS.map(([key, label]) => (
            <ThemeFilter key={key} active={category === key} onClick={() => setCategory(key)}>{label}</ThemeFilter>
          ))}
        </div>
      )}

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
          <FrequencyLegend />
          <p className="mt-3 font-semibold text-foreground">Status</p>
          <p className="mt-1">Status sind Einordnungen von Ratslotse, keine amtlichen Bearbeitungsstände.</p>
          <p className="mt-1">Eine Bearbeitung durch die Stadt zeigen wir nur mit überprüfbarer städtischer Quelle.</p>
        </InfoPopover>
      </div>

      {query.isLoading ? (
        <Spinner className="min-h-[420px] rounded-xl border border-border bg-card" />
      ) : query.isError ? (
        <ErrorState hint="Die öffentliche Problemkarte konnte nicht geladen werden." onRetry={() => void query.refetch()} busy={query.isFetching} />
      ) : all.length === 0 ? (
        <EmptyState mascot="search" title="Noch keine veröffentlichten Probleme" hint="Schau später noch einmal vorbei." />
      ) : ansicht === "karte" ? (
        mapProblems.length === 0 ? (
          <EmptyState
            mascot="search"
            title="Keine kartierbaren Probleme für dieses Thema"
            action={<button type="button" onClick={() => setCategory("all")} className="min-h-11 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium text-primary hover:bg-muted">Alle Themen zeigen</button>}
          />
        ) : (
          <div className="space-y-3">
            <ProblemMap problems={mapProblems} selectedId={selectedId} onSelect={setSelectedId} className="h-[62dvh] min-h-[420px] max-h-[720px]" />
            {selected && isProblemMappable(selected) && <SelectedProblem problem={selected} onClose={() => setSelectedId(null)} />}
          </div>
        )
      ) : (
        <div className="space-y-3">
          <KanbanBoard problems={all} onSelect={setSelectedId} />
          {selected && <SelectedProblem problem={selected} onClose={() => setSelectedId(null)} />}
        </div>
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

function FrequencyLegend() {
  return (
    <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1" aria-label="Legende der Meldehäufigkeit">
      {(Object.entries(MELDE_HAEUFIGKEIT) as [ProblemFrequency, string][]).map(([frequency, label]) => (
        <span key={frequency} className="inline-flex items-center gap-1">
          <span className={`problem-frequency-dot frequency-${frequency}`} aria-hidden />{label}
        </span>
      ))}
    </div>
  );
}

function KanbanBoard({ problems, onSelect }: { problems: PublicProblem[]; onSelect: (id: number) => void }) {
  return (
    <div className="overflow-x-auto pb-2" aria-label="Probleme nach Status" tabIndex={0}>
      <div className="grid min-w-[82rem] grid-cols-5 gap-3">
        {STATUS_OPTIONS.map(([status, label]) => {
          const entries = problems.filter((problem) => problem.status === status);
          return (
            <section key={status} className="rounded-xl bg-muted/55 p-2.5" aria-labelledby={`status-${status}`}>
              <div className="flex items-center justify-between gap-2 px-1 pb-2">
                <h2 id={`status-${status}`} className="text-sm font-semibold text-foreground">{label}</h2>
                <span className="rounded-full bg-card px-2 py-0.5 text-xs tabular-nums text-muted-foreground">{entries.length}</span>
              </div>
              <div className="space-y-2">
                {entries.map((problem) => <ProblemCard key={problem.id} problem={problem} onSelect={onSelect} />)}
                {entries.length === 0 && <p className="rounded-lg border border-dashed border-border/80 px-3 py-5 text-center text-xs text-muted-foreground">Keine Probleme</p>}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}

function ProblemCard({ problem, onSelect }: { problem: PublicProblem; onSelect: (id: number) => void }) {
  return (
    <button type="button" onClick={() => onSelect(problem.id)} className="w-full rounded-lg border border-border bg-card p-3 text-left shadow-sm transition-colors hover:border-primary/35 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" aria-label={`${problem.title} · ${MELDE_HAEUFIGKEIT[problem.frequency]}`}>
      <div className="flex items-start gap-2">
        <span className={`problem-frequency-dot frequency-${problem.frequency} mt-1 shrink-0`} aria-hidden />
        <h3 className="text-sm font-semibold leading-snug text-foreground">{problem.title}</h3>
      </div>
      <p className="mt-2 flex items-center gap-1 text-xs text-muted-foreground">
        <MapPin className="h-3.5 w-3.5 shrink-0" aria-hidden />
        <span className="truncate">{problem.location_label || PROBLEM_SCOPE[problem.scope_kind]}</span>
      </p>
    </button>
  );
}

function SelectedProblem({ problem, onClose }: { problem: PublicProblem; onClose: () => void }) {
  return (
    <div className="relative rounded-xl border border-primary/20 bg-card p-4" aria-live="polite">
      <button type="button" onClick={onClose} aria-label="Auswahl schließen" className="absolute right-2 top-2 flex h-10 w-10 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted">
        <X className="h-4 w-4" aria-hidden />
      </button>
      <p className="pr-10 text-xs font-medium text-primary">{PROBLEM_STATUS[problem.status]}</p>
      <h2 className="mt-1 pr-10 text-base font-bold text-foreground">{problem.title}</h2>
      <p className="mt-1 text-sm text-muted-foreground">{problem.location_label || PROBLEM_SCOPE[problem.scope_kind]}</p>
    </div>
  );
}
