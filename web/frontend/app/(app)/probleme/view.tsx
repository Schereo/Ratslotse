"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Info,
  ListOrdered,
  Map as MapIcon,
  MapPin,
  Navigation,
  X,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import {
  MeldeRanglisteGrafik,
  type MeldeRangzeile,
} from "@/components/grafik/melde-rangbalken";
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
  reportCountLabel,
  type ProblemFrequency,
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
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const mapProblems = useMemo(
    () => all.filter((problem) => (
      isProblemMappable(problem) && (category === "all" || problem.category === category)
    )),
    [all, category],
  );
  const selected = all.find((problem) => problem.id === selectedId) ?? null;
  const fictional = all.some((problem) => problem.fictional);

  useEffect(() => {
    const view = new URLSearchParams(window.location.search).get("view");
    if (view === "meistgemeldet" || view === "status") setAnsicht("meistgemeldet");
  }, []);

  const changeView = useCallback((next: Ansicht) => {
    setAnsicht(next);
    const url = new URL(window.location.href);
    if (next === "meistgemeldet") url.searchParams.set("view", "meistgemeldet");
    else url.searchParams.delete("view");
    window.history.replaceState(null, "", `${url.pathname}${url.search}`);
  }, []);

  const showOnMap = useCallback((problem: PublicProblem) => {
    setCategory("all");
    setSelectedId(problem.id);
    changeView("karte");
  }, [changeView]);

  return (
    <div className="space-y-4">
      <PageHeader title={PROBLEM_ANGEBOT.name} />

      {fictional && (
        <div className="inline-flex min-h-10 max-w-full items-center rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950/35 dark:text-amber-100">
          <span role="status"><strong>Feature-Vorschau</strong> · frei erfundene Beispiele</span>
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
          Unabhängige Meldungen · privates Bürgerprojekt, kein Angebot der Stadt Oldenburg.
        </p>
        <LottiHelp ansicht={ansicht} fictional={fictional} />
      </div>

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
            action={<button type="button" onClick={() => setCategory("all")} className="min-h-11 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium text-primary hover:bg-muted">Alle ungelösten Probleme zeigen</button>}
          />
        ) : (
          <div className="space-y-3">
            <ProblemMap problems={mapProblems} selectedId={selectedId} onSelect={setSelectedId} className="h-[62dvh] min-h-[420px] max-h-[720px]" />
            {selected && isProblemMappable(selected) && <SelectedProblem problem={selected} onClose={() => setSelectedId(null)} />}
          </div>
        )
      ) : (
        <Leaderboard problems={all} selectedId={selectedId} onSelect={setSelectedId} onShowMap={showOnMap} />
      )}
    </div>
  );
}

function LottiHelp({ ansicht, fictional }: { ansicht: Ansicht; fictional: boolean }) {
  const [open, setOpen] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const leaderboard = ansicht === "meistgemeldet";
  const viewLabel = leaderboard ? "Rangliste" : "Karte";

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`Lotti-Hilfe ${open ? "schließen" : "öffnen"}: ${viewLabel} erklären`}
          aria-expanded={open}
          className="problem-lotti-help group inline-flex min-h-11 items-center gap-2 rounded-xl border border-primary/20 bg-primary/[0.045] py-1 pl-1 pr-3 text-left text-primary shadow-sm transition-[border-color,background-color,transform] hover:border-primary/35 hover:bg-primary/[0.075] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Mascot
            regung={open ? "erklaert" : leaderboard ? "zeigt-runter" : "ruht"}
            regie="ruhig"
            decorative
            className="problem-lotti-figur h-11 w-11 shrink-0"
          />
          <span>
            <span className="block font-mono text-[9px] font-medium uppercase tracking-[0.11em]">Lotti hilft</span>
            <span className="block text-xs font-semibold text-foreground">{viewLabel} verstehen</span>
          </span>
        </button>
      </PopoverTrigger>
      <PopoverContent
        ref={contentRef}
        aria-label={`Lotti erklärt die ${viewLabel}`}
        align="end"
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          contentRef.current?.focus();
        }}
        className="max-h-[var(--radix-popover-content-available-height)] w-[22rem] max-w-[calc(100vw-2rem)] overflow-y-auto p-4 text-xs leading-relaxed text-muted-foreground"
      >
        <div className="grid grid-cols-[3rem_1fr_2.75rem] items-start gap-3">
          <Mascot regung="erklaert" regie="ruhig" decorative className="h-12 w-12 shrink-0" />
          <div className="min-w-0">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-primary">Lotti erklärt</p>
            <p className="mt-1 font-display text-base font-bold text-foreground">{viewLabel} verstehen</p>
          </div>
          <button type="button" onClick={() => setOpen(false)} aria-label="Hilfe schließen" className="flex h-11 w-11 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
        {leaderboard ? (
          <p className="mt-3">
            Die lebenszeitliche Zahl zählt freigegebene unabhängige Meldungen. Aktualisierungen derselben Person erhöhen sie nicht. Rang und Zahl zeigen Aufmerksamkeit, nicht Wahrheit, Dringlichkeit, Schadenshöhe oder die Zahl betroffener Personen.
          </p>
        ) : (
          <p className="mt-3">
            Die Karte zeigt nur freigegebene, ehrlich kartierbare Orte und Flächen. Stadtweite Probleme und unbrauchbare Geometrien bekommen keinen erfundenen Punkt.
          </p>
        )}
        <div className="mt-3"><FrequencyScale /></div>
        <p className="mt-3">Hafenblau zeigt ausschließlich die Zahl unabhängiger Meldungen, von hell nach dunkel. Es ist kein Dringlichkeits- oder Wahrheitsurteil.</p>
        {fictional && <p className="mt-3">Alle als Beispiel bezeichneten Einträge und Zahlen sind frei erfunden. Sie zeigen nur, wie die Übersicht funktioniert.</p>}
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

function Leaderboard({ problems, selectedId, onSelect, onShowMap }: {
  problems: PublicProblem[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  onShowMap: (problem: PublicProblem) => void;
}) {
  const zeilen: MeldeRangzeile[] = problems.map((problem) => {
    const offen = selectedId === problem.id;
    return {
      key: problem.id,
      label: problem.title,
      wert: problem.independent_reports,
      haeufigkeit: problem.frequency,
      offen,
      umschalten: () => onSelect(offen ? null : problem.id),
      vorschau: <ProblemPreview problem={problem} onShowMap={() => onShowMap(problem)} />,
    };
  });

  return (
    <section className="space-y-4" aria-labelledby="meistgemeldet-heading">
      <div className="overflow-hidden rounded-2xl border border-primary/20 bg-primary/[0.045] px-4 py-3 sm:px-6 sm:py-4">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-primary">Gemeinschaftliche Aufmerksamkeit</p>
        <div className="mt-1 flex flex-wrap items-end justify-between gap-2">
          <h2 id="meistgemeldet-heading" className="font-display text-2xl font-bold text-foreground sm:text-3xl">Meistgemeldet</h2>
          <p className="text-xs font-medium text-muted-foreground">Rang · unabhängige Meldungen · gesamter Zeitraum</p>
        </div>
      </div>

      <MeldeRanglisteGrafik
        zeilen={zeilen}
        beleg={(
          <>
            <span className="font-mono font-medium uppercase tracking-[0.07em] text-foreground/75">Quelle der Rangfolge:</span>{" "}
            Freigegebene unabhängige Meldungen im Ratslotse-Meldungsbestand · gesamter Zeitraum
          </>
        )}
      />
    </section>
  );
}

function ProblemPreview({ problem, onShowMap }: { problem: PublicProblem; onShowMap: () => void }) {
  return (
    <>
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
    </>
  );
}

function SelectedProblem({ problem, onClose }: { problem: PublicProblem; onClose: () => void }) {
  return (
    <div className="relative rounded-xl border border-primary/20 bg-card p-4" aria-live="polite">
      <button type="button" onClick={onClose} aria-label="Auswahl schließen" className="absolute right-2 top-2 flex h-10 w-10 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
        <X className="h-4 w-4" aria-hidden />
      </button>
      <strong className="block pr-10 text-xs font-semibold tabular-nums text-primary">{reportCountLabel(problem.independent_reports)}</strong>
      <h2 className="mt-1 pr-10 font-display text-base font-bold text-foreground">{problem.title}</h2>
      <p className="mt-1 max-w-[76ch] text-[13px] leading-relaxed text-foreground/85">{problem.summary}</p>
      <p className="mt-2 flex items-center gap-1 text-xs text-muted-foreground">
        <MapPin className="h-3.5 w-3.5 shrink-0" aria-hidden />
        {problem.location_label || PROBLEM_SCOPE[problem.scope_kind]}
      </p>
    </div>
  );
}
