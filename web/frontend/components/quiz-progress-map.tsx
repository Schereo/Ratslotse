"use client";

import { useMemo } from "react";
import dynamic from "next/dynamic";
import type { QuizStats } from "@/lib/types";
import type { DistrictLevel } from "@/components/quiz-map";
import { cn } from "@/lib/utils";

// Leaflet ist client-only und schwer — erst laden, wenn die Karte dran ist.
const QuizMap = dynamic(() => import("@/components/quiz-map").then((m) => m.QuizMap), {
  ssr: false,
  loading: () => <div className="h-full w-full animate-pulse rounded-xl bg-muted" />,
});

// Dieselben Deckkräfte wie auf der Karte (quiz-map.tsx, LEVEL).
const SWATCH = ["bg-slate-400/10", "bg-primary/15", "bg-primary/35", "bg-primary/60"];
const LEGEND = ["unentdeckt", "entdeckt", "vertraut", "gemeistert"];

/** „Deine Stadtkarte": Jeder Ortsbereich getönt nach dem, was man dort schon
 *  weiß. Aus einer Prozentzahl wird ein Ziel, das man sieht — und ein Tipp
 *  auf eine blasse Fläche startet genau dort die nächste Runde. Stufen und
 *  Wörter entscheidet der Server (`/quiz/stats` → `districts`). */
export function QuizProgressMap({ districts, onPlay, className }: {
  districts: NonNullable<QuizStats["districts"]>;
  onPlay: (district: string) => void;
  className?: string;
}) {
  const progress = useMemo(() => Object.fromEntries(districts.map((d) => [d.district, {
    level: d.level, label: d.level_label, answered: d.answered, correct: d.correct,
  } satisfies DistrictLevel])), [districts]);
  const perLevel = LEGEND.map((_, i) => districts.filter((d) => d.level === i).length);
  const found = districts.length - perLevel[0];

  // Mobil: Kopf, Karte, Legende untereinander. Am Schreibtisch steht die
  // Karte links über beide Zeilen, Kopf und Legende rechts daneben.
  return (
    <section className={cn("grid gap-3 rounded-2xl border border-border bg-card p-4 sm:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] sm:grid-rows-[auto_1fr] sm:gap-x-5", className)}>
      <div className="sm:col-start-2 sm:row-start-1 sm:mt-1">
        <h2 className="text-base font-semibold text-foreground">Deine Stadtkarte</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          <span className="font-medium tabular-nums text-foreground">{found}</span> von {districts.length} Ortsbereichen entdeckt.
          {" "}Je mehr du dort richtig beantwortest, desto kräftiger wird die Fläche.
        </p>
      </div>
      <QuizMap picked={null} solution={null} disabled={false} progress={progress}
        onPick={onPlay} label="Fortschrittskarte: Ortsbereiche nach Quiz-Stand getönt"
        className="aspect-[4/3] w-full sm:col-start-1 sm:row-span-2 sm:row-start-1" />
      <div className="flex flex-col sm:col-start-2 sm:row-start-2">
        <ul className="space-y-2 text-sm">
          {LEGEND.map((word, i) => (
            <li key={word} className="flex items-center gap-2.5">
              <span className={cn("h-3.5 w-3.5 shrink-0 rounded-sm border border-primary/20", SWATCH[i])} aria-hidden />
              <span className="text-foreground">{word}</span>
              <span className="ml-auto tabular-nums text-muted-foreground">{perLevel[i]}</span>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-xs text-muted-foreground sm:mt-auto sm:pt-4">
          Tippe auf einen Ortsbereich, um dort eine Runde zu spielen.
        </p>
      </div>
    </section>
  );
}
