"use client";

// Die Detailseite eines Plans (Schalter `plaene`, docs/plan-ziele-plaene.md § 3.2).
//
// Der Aufbau folgt vier Fragen: Was ist der Plan, und wie lange gilt er?
// (Kopfbühne mit Zeitband) Was steht drin? (Zweck und Kernpunkte, jeder mit
// Beleg) Was wurde seither berichtet? (Zeitstrahl) Was hat
// er sich vorgenommen, und was hat der Rat dazu beschlossen? (Maßnahmen,
// Beschlüsse). Kein leerer Platzhalter für das, was fehlt.
//
// Alles Rechnen steht in council/plan_pages.py; hier wird gezeichnet.

import { Suspense, useState } from "react";
import { notFound, useSearchParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { DetailSkeleton } from "@/components/ui";
import { CityStatus } from "@/components/plans/city-status";
import { Content } from "@/components/plans/content";
import { Decisions } from "@/components/plans/decisions";
import { Indicators } from "@/components/plans/indicators";
import { Measures } from "@/components/plans/measures";
import { PlanHeader } from "@/components/plans/plan-header";
import { ReportLog } from "@/components/plans/report-log";
import { Review } from "@/components/plans/review";
import { AbrufFehler } from "@/components/abruf-fehler";
import { ShareButton } from "@/components/share-button";
import { useFetch } from "@/lib/use-fetch";
import { istNichtGefunden } from "@/lib/api";
import { useAppConfig, featureAktiv } from "@/lib/features";
import { planHref, plaeneHref } from "@/lib/routes";
import { useZurueck } from "@/lib/zurueck";
import type { PlanDetail } from "@/lib/plans";
import { cn } from "@/lib/utils";

function PlanInner() {
  const key = useSearchParams().get("key");
  const { zeigen: showBack, zurueck: goBack } = useZurueck();
  const config = useAppConfig();
  const enabled = featureAktiv(config.data, "plaene");
  const { data, loading, error, refetch } = useFetch<PlanDetail>(
    key && enabled ? `/council/plan/${encodeURIComponent(key)}` : null, { quiet: true });
  // Ein Tipp auf eine Marke im Zeitband führt zum Eintrag im Zeitstrahl.
  const [target, setTarget] = useState<{ station: number; n: number } | null>(null);

  // Erst die Konfiguration, dann der Plan. `!data && !error` gilt als Laden:
  // Im Durchlauf, in dem der Schalter angeht, hat `useFetch` den neuen Pfad
  // noch nicht gesehen und meldet kein Laden — ein `notFound()` dort trifft
  // jede Seite beim ersten Aufruf.
  if (config.isPending || (enabled && (loading || (!data && !error)))) return <DetailSkeleton />;
  if (!enabled) notFound();
  if (!data) {
    if (error && !istNichtGefunden(error)) return <AbrufFehler error={error} onRetry={refetch} was="Dieser Plan" />;
    notFound();
  }
  const hasAside = data.decision_groups.length > 0;
  return (
    <div className="@container mx-auto max-w-[1180px] weit:max-w-[1480px]">
      <div className="print-hidden flex items-center justify-between gap-3">
        {showBack ? (
          <button onClick={() => goBack(plaeneHref)} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" /> Pläne der Stadt
          </button>
        ) : <span />}
        <ShareButton path={planHref(data.key)} title={`${data.title} — Ratslotse`} />
      </div>
      <div className="mt-3">
        <PlanHeader plan={data} onStation={(station) => setTarget((t) => ({ station, n: (t?.n ?? 0) + 1 }))} />
      </div>
      {/* Breit zwei SPALTEN, die je für sich stapeln — ein Raster aus Zeilen
          ließe unter der kurzen Karte Leere stehen (DESIGNSPRACHE § 4). Links,
          was den Plan ausmacht (Berichte, Maßnahmen), rechts die Beschlüsse.
          Ohne Beschlüsse bleibt es bei einer Spalte. */}
      <div className={cn("mt-4 flex flex-col gap-4 @4xl:mt-5 @4xl:gap-5",
        hasAside && "@4xl:grid @4xl:grid-cols-[minmax(0,1fr)_minmax(0,24rem)] @4xl:items-start")}>
        <div className="flex min-w-0 flex-col gap-4 @4xl:gap-5">
          {data.content && <Content content={data.content} />}
          {data.review && <Review review={data.review} />}
          <ReportLog plan={data} target={target} />
          {data.city_status && <CityStatus status={data.city_status} />}
          <Indicators indicators={data.indicators} />
          {data.measures && <Measures measures={data.measures} />}
        </div>
        <div className="flex min-w-0 flex-col gap-4 @4xl:gap-5">
          {hasAside && <Decisions plan={data} />}
          <p className="max-w-[76ch] text-hinweis text-muted-foreground">
            Gefunden über die Titel und Vorlagen der Tagesordnungspunkte im Ratsinformationssystem.
            Nichtöffentliche Sitzungen, Mitteilungen ohne Vorlage und Berichte außerhalb des
            Ratsinformationssystems sieht Ratslotse nicht.
          </p>
        </div>
      </div>
    </div>
  );
}

export default function PlanPage() {
  return (
    <Suspense fallback={<DetailSkeleton />}>
      <PlanInner />
    </Suspense>
  );
}
