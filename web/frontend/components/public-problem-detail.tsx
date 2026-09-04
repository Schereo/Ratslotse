"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { ArrowLeft, MapPin, X } from "lucide-react";
import { ProblemHelp } from "@/components/problem-help";
import { ShareButton } from "@/components/share-button";
import {
  isProblemMappable,
  PROBLEM_KATEGORIEN,
  PROBLEM_SCOPE_META,
  problemDetailHref,
  reportCountLabel,
  type PublicProblem,
} from "@/lib/probleme";

const ProblemMap = dynamic(
  () => import("@/components/problem-map").then((module) => module.ProblemMap),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-80 items-center justify-center rounded-xl border border-border bg-muted motion-safe:animate-pulse" role="status">
        <span className="sr-only">Karte wird geladen…</span>
      </div>
    ),
  },
);

export function PublicProblemDetail({
  problem,
  onClose,
  headingLevel = 1,
}: {
  problem: PublicProblem;
  onClose?: () => void;
  headingLevel?: 1 | 2;
}) {
  const mappable = isProblemMappable(problem);
  const Heading = headingLevel === 1 ? "h1" : "h2";
  const SectionHeading = headingLevel === 1 ? "h2" : "h3";

  return (
    <article className="mx-auto max-w-[76ch] space-y-5 text-[15px]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {onClose ? (
          <button
            type="button"
            onClick={onClose}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-lg text-sm font-semibold text-primary hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X className="h-4 w-4" aria-hidden /> Details schließen
          </button>
        ) : (
          <Link
            href="/probleme"
            className="inline-flex min-h-11 items-center gap-1.5 rounded-lg text-sm font-semibold text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden /> Zur Übersicht
          </Link>
        )}
        <ShareButton path={problemDetailHref(problem.id)} title={problem.title} />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        {problem.fictional && (
          <p className="inline-flex min-h-10 items-center rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950/35 dark:text-amber-100" role="status">
            <strong>Feature-Vorschau</strong>&nbsp;· frei erfundenes Beispiel
          </p>
        )}
        <div className="ml-auto">
          <ProblemHelp view="detail" fictional={problem.fictional} />
        </div>
      </div>

      <header className={`frequency-${problem.frequency} rounded-2xl border border-primary/20 bg-primary/[0.055] p-5 sm:p-7`}>
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-[var(--problem-frequency)]">
          {reportCountLabel(problem.independent_reports)}
        </p>
        <Heading className="mt-2 font-display text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
          {problem.title}
        </Heading>
        <p className="mt-4 leading-relaxed text-foreground/85">{problem.summary}</p>
      </header>

      <section className="rounded-xl border border-border bg-card p-5" aria-labelledby="problem-ort">
        <SectionHeading id="problem-ort" className="font-display text-base font-bold text-foreground">Ort und Thema</SectionHeading>
        <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <MapPin className="h-4 w-4" aria-hidden />
            {problem.location_label || PROBLEM_SCOPE_META[problem.scope_kind].publicLabel}
          </span>
          <span>{PROBLEM_KATEGORIEN[problem.category]}</span>
        </div>
        {mappable && (
          <ProblemMap
            problems={[problem]}
            selectedId={problem.id}
            className="mt-4 h-80 sm:h-96"
          />
        )}
        {!mappable && (
          <p className="mt-4 rounded-lg border border-dashed border-border bg-muted/45 px-3 py-2 text-sm leading-relaxed text-muted-foreground">
            {problem.scope_kind === "citywide"
              ? "Kein einzelner Kartenort: Dieses Problem gilt für das gesamte Stadtgebiet."
              : "Keine brauchbare Geometrie: Dieses Problem kann nicht ehrlich auf der Karte gezeigt werden."}
          </p>
        )}
      </section>

      <p className="font-mono text-[11px] leading-relaxed text-muted-foreground">
        Quelle: Freigegebene unabhängige Meldungen im Ratslotse-Meldungsbestand · gesamter Zeitraum
      </p>
    </article>
  );
}
