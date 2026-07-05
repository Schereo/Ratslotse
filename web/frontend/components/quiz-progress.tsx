"use client";

import { TrendingUp, Play, MapPin, Sparkles } from "lucide-react";
import { QuizStats } from "@/lib/types";
import { Card, Button } from "@/components/ui";
import { cn } from "@/lib/utils";

const quote = (correct: number, answered: number) =>
  answered ? Math.round((correct / answered) * 100) : 0;

/** Farbe der Trefferquote: rot (Schwäche) → gelb → grün. So springt „wo bin
 *  ich schwach?" sofort ins Auge. */
function barColor(p: number) {
  return p >= 67 ? "bg-emerald-500" : p >= 34 ? "bg-amber-500" : "bg-rose-500";
}

function Stat({ value, label }: { value: string | number; label: string }) {
  return (
    <div>
      <div className="text-2xl font-bold tabular-nums text-foreground">{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}

/** „Mein Fortschritt" — Gesamtstand plus je-Gebiet-Balken, schwächste zuerst,
 *  mit Direktstart („Üben"). Datenquelle: GET /api/quiz/stats. */
export function QuizProgress({
  stats,
  themeLabels,
  onPractice,
}: {
  stats: QuizStats;
  themeLabels: Record<string, string>;
  onPractice: (area: string) => void;
}) {
  const areas = [...stats.by_area].sort(
    (a, b) => quote(a.correct, a.answered) - quote(b.correct, b.answered),
  );
  const total = quote(stats.total.correct, stats.total.answered);
  const label = (a: QuizStats["by_area"][number]) =>
    a.area_type === "thema" ? themeLabels[a.area_key] ?? a.area_key : a.area_key;

  return (
    <section>
      <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-muted-foreground">
        <TrendingUp className="h-4 w-4" /> Mein Fortschritt
      </h2>
      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
          <Stat value={stats.total.points} label={stats.total.points === 1 ? "Punkt" : "Punkte"} />
          <Stat value={`${total} %`} label="Trefferquote" />
          <Stat value={stats.total.answered} label="Fragen gespielt" />
        </div>

        {areas.length > 0 && (
          <div className="mt-4 space-y-2.5 border-t border-border pt-3">
            <p className="text-xs font-medium text-muted-foreground">
              Nach Gebiet — schwächste zuerst
            </p>
            {areas.map((a) => {
              const p = quote(a.correct, a.answered);
              const Icon = a.area_type === "thema" ? Sparkles : MapPin;
              return (
                <div key={`${a.area_type}:${a.area_key}`} className="flex items-center gap-2 sm:gap-3">
                  <span className="flex w-24 shrink-0 items-center gap-1.5 truncate text-sm text-foreground sm:w-32">
                    <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                    <span className="truncate">{label(a)}</span>
                  </span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                    <div className={cn("h-full rounded-full transition-[width] duration-500 ease-out-strong", barColor(p))}
                         style={{ width: `${Math.max(p, 3)}%` }} />
                  </div>
                  <span className="w-12 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
                    {a.correct}/{a.answered}
                  </span>
                  <Button variant="secondary" size="sm" className="shrink-0"
                          onClick={() => onPractice(`${a.area_type}:${a.area_key}`)}>
                    <Play className="!size-3.5" /> Üben
                  </Button>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </section>
  );
}
