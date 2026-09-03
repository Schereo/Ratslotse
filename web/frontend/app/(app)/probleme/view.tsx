"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState, type MouseEvent } from "react";
import {
  ArrowRight,
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
import { ProblemHelp } from "@/components/problem-help";
import { PublicProblemDetail } from "@/components/public-problem-detail";
import { EmptyState, ErrorState, PageHeader, Segmented, Spinner } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { isNativeApp } from "@/lib/platform";
import { cn } from "@/lib/utils";
import { usePublicProblem } from "@/lib/use-public-problem";
import { vertrag } from "@/lib/vertrag";
import {
  isProblemMappable,
  PROBLEM_ANGEBOT,
  PROBLEM_KATEGORIEN,
  PROBLEM_SCOPE,
  parseProblemId,
  problemAppDetailHref,
  problemDetailHref,
  reportCountLabel,
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
const EMPTY_PROBLEMS: PublicProblem[] = [];

export default function View() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const detailParam = searchParams.get("problem");
  const detailId = parseProblemId(detailParam ?? "");
  const query = useQuery({
    queryKey: ["public-problems"],
    queryFn: () => vertrag.get("/probleme"),
    enabled: detailParam === null,
    staleTime: 60_000,
  });
  const detailQuery = usePublicProblem(detailId);
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
  const fictional = detailQuery.data?.fictional ?? all.some((problem) => problem.fictional);

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

  const closeDetail = useCallback(() => {
    const url = new URL(window.location.href);
    url.searchParams.delete("problem");
    router.replace(`${url.pathname}${url.search}`);
  }, [router]);

  return (
    <div className="space-y-4">
      <PageHeader title={PROBLEM_ANGEBOT.name} />

      {detailParam === null && fictional && (
        <div className="inline-flex min-h-10 max-w-full items-center rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950/35 dark:text-amber-100">
          <span role="status"><strong>Feature-Vorschau</strong> · frei erfundene Beispiele</span>
        </div>
      )}

      {detailParam !== null ? (
        detailId === null ? (
          <ProblemNotFound onClose={closeDetail} />
        ) : detailQuery.isLoading ? (
          <Spinner label="Problem wird geladen…" className="min-h-[420px] rounded-xl border border-border bg-card" />
        ) : detailQuery.error instanceof ApiError && detailQuery.error.status === 404 ? (
          <ProblemNotFound onClose={closeDetail} />
        ) : detailQuery.isError || !detailQuery.data ? (
          <ErrorState hint="Die öffentliche Detailseite konnte nicht geladen werden." onRetry={() => void detailQuery.refetch()} busy={detailQuery.isFetching} />
        ) : (
          <PublicProblemDetail problem={detailQuery.data} onClose={closeDetail} headingLevel={2} />
        )
      ) : (
        <>
          <Segmented
            value={ansicht}
            onChange={changeView}
            options={[
              { value: "karte", label: "Karte", icon: MapIcon },
              { value: "meistgemeldet", label: "Rangliste", icon: ListOrdered },
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

          <div className="flex justify-end">
            <ProblemHelp view={ansicht === "karte" ? "karte" : "rangliste"} fictional={fictional} />
          </div>

          {query.isLoading ? (
            <Spinner label="Probleme werden geladen…" className="min-h-[420px] rounded-xl border border-border bg-card" />
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
        </>
      )}
    </div>
  );
}

function ProblemNotFound({ onClose }: { onClose: () => void }) {
  return (
    <EmptyState
      mascot="search"
      title="Problem nicht gefunden"
      headingLevel={2}
      hint="Es ist nicht öffentlich oder der Link ist nicht mehr gültig."
      action={<button type="button" onClick={onClose} className="min-h-11 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium text-primary hover:bg-muted">Zur Übersicht</button>}
    />
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
    <section aria-label="Rangliste">
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
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" onClick={onShowMap} aria-label={`${problem.title} auf der Karte zeigen`} className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-primary/25 bg-primary/5 px-3 py-2 text-sm font-semibold text-primary transition-colors hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <Navigation className="h-4 w-4" aria-hidden /> Auf der Karte zeigen
          </button>
          <ProblemDetailLink problem={problem} />
        </div>
      ) : (
        <>
          <p className="mt-3 rounded-lg border border-dashed border-border bg-muted/45 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
            {problem.scope_kind === "citywide"
              ? "Kein einzelner Kartenort: Dieses Beispiel gilt für das gesamte Stadtgebiet."
              : "Keine brauchbare Geometrie: Dieses Beispiel kann nicht ehrlich auf der Karte gezeigt werden."}
          </p>
          <ProblemDetailLink problem={problem} className="mt-3" />
        </>
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
      <ProblemDetailLink problem={problem} className="mt-3" />
    </div>
  );
}

function ProblemDetailLink({ problem, className }: { problem: PublicProblem; className?: string }) {
  const router = useRouter();
  const open = (event: MouseEvent<HTMLAnchorElement>) => {
    if (!isNativeApp()) return;
    event.preventDefault();
    router.push(problemAppDetailHref(problem.id));
  };
  return (
    <Link
      href={problemDetailHref(problem.id)}
      prefetch={false}
      onClick={open}
      className={cn(
        "inline-flex min-h-11 items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-semibold text-primary hover:bg-primary/5 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
    >
      Details ansehen <ArrowRight className="h-4 w-4" aria-hidden />
    </Link>
  );
}
