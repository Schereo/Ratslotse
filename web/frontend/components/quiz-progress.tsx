"use client";

import Link from "next/link";
import { TrendingUp, Play, MapPin, Sparkles, Flame, RotateCcw, ChevronRight } from "lucide-react";
import { QuizStats, QuizBadge } from "@/lib/types";
import { Card, Button } from "@/components/ui";
import { cn } from "@/lib/utils";

const quote = (correct: number, answered: number) =>
  answered ? Math.round((correct / answered) * 100) : 0;

/** Farbe der Trefferquote: rot (Schwäche) → gelb → grün. So springt „wo bin
 *  ich schwach?" sofort ins Auge. */
function barColor(p: number) {
  return p >= 67 ? "bg-emerald-500" : p >= 34 ? "bg-amber-500" : "bg-rose-500";
}

const TIER: Record<QuizBadge["tier"], string> = {
  gold: "bg-amber-100 text-amber-800 dark:bg-amber-400/15 dark:text-amber-300",
  silber: "bg-slate-200 text-slate-700 dark:bg-slate-400/15 dark:text-slate-300",
  bronze: "bg-orange-100 text-orange-800 dark:bg-orange-400/15 dark:text-orange-300",
};

function Stat({ value, label }: { value: string | number; label: string }) {
  return (
    <div>
      <div className="text-2xl font-bold tabular-nums text-foreground">{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}

/** Kompakte Statistik-Zeile für die Quiz-Startseite: nur die Kernzahlen +
 *  Direktlink „Meine Fehler üben" und zur ausführlichen Statistik-Seite. Die
 *  Details (je-Gebiet-Balken, Abzeichen) liegen unter /quiz/stats, damit die
 *  Startseite übersichtlich bleibt. */
export function QuizStatsStrip({ stats, onReview }: { stats: QuizStats; onReview: () => void }) {
  const total = quote(stats.total.correct, stats.total.answered);
  return (
    <Card className="flex flex-wrap items-center gap-x-6 gap-y-3 p-4">
      <Stat value={stats.total.points} label={stats.total.points === 1 ? "Punkt" : "Punkte"} />
      <Stat value={`${total} %`} label="Trefferquote" />
      {stats.streak > 0 && (
        <div className="flex items-center gap-1.5">
          <Flame className="h-6 w-6 text-orange-500" />
          <Stat value={stats.streak} label="Tage-Serie" />
        </div>
      )}
      <div className="ml-auto flex flex-wrap items-center gap-x-4 gap-y-2">
        {stats.wrong > 0 && (
          <Button variant="secondary" size="sm" onClick={onReview}>
            <RotateCcw className="!size-4" /> {stats.wrong} {stats.wrong === 1 ? "Fehler" : "Fehler"} üben
          </Button>
        )}
        <Link href="/quiz/stats" className="inline-flex items-center gap-0.5 text-sm font-medium text-primary hover:underline">
          Alle Statistiken <ChevronRight className="h-4 w-4" />
        </Link>
      </div>
    </Card>
  );
}

/** „Mein Fortschritt" — Gesamtstand, Serie, Abzeichen und je-Gebiet-Balken
 *  (schwächste zuerst) mit Direktstart. Plus „Meine Fehler üben", wenn welche
 *  offen sind. Datenquelle: GET /api/quiz/stats. */
export function QuizProgress({
  stats,
  themeLabels,
  onPractice,
  onReview,
}: {
  stats: QuizStats;
  themeLabels: Record<string, string>;
  onPractice: (area: string) => void;
  onReview: () => void;
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
          {stats.streak > 0 && (
            <div className="flex items-center gap-1.5">
              <Flame className="h-6 w-6 text-orange-500" />
              <div>
                <div className="text-2xl font-bold tabular-nums text-foreground">{stats.streak}</div>
                <div className="text-xs text-muted-foreground">Tage-Serie</div>
              </div>
            </div>
          )}
        </div>

        {stats.badges.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {stats.badges.map((b) => (
              <span key={b.key}
                className={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold", TIER[b.tier])}>
                {b.label}
              </span>
            ))}
          </div>
        )}

        {stats.wrong > 0 && (
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3">
            <span className="text-sm text-foreground">
              Du hast <span className="font-semibold">{stats.wrong}</span>{" "}
              {stats.wrong === 1 ? "Frage" : "Fragen"} zuletzt falsch beantwortet.
            </span>
            <Button variant="secondary" size="sm" className="shrink-0" onClick={onReview}>
              <RotateCcw className="!size-4" /> Meine Fehler üben
            </Button>
          </div>
        )}

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

/** Tages-Challenge-Karte: 5 feste Fragen pro Tag. Vor dem Spielen ein
 *  Start-Aufruf, danach das Ergebnis des Tages. */
export function QuizDailyCard({
  done,
  count,
  onStart,
}: {
  done: { correct: number; total: number } | null;
  count: number;
  onStart: () => void;
}) {
  if (!done && count === 0) return null; // kein Fragenpool → keine Challenge
  return (
    <Card className="flex flex-wrap items-center justify-between gap-3 border-primary/30 bg-primary/5 p-4">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
          <Sparkles className="h-5 w-5" />
        </div>
        <div>
          <p className="font-semibold text-foreground">Tägliche Challenge</p>
          <p className="text-sm text-muted-foreground">
            {done
              ? `Heute erledigt — ${done.correct}/${done.total} richtig. Morgen gibt's neue Fragen.`
              : `${count} Fragen quer durch Oldenburg — jeden Tag neu.`}
          </p>
        </div>
      </div>
      {!done && (
        <Button className="shrink-0" onClick={onStart}>
          <Play className="!size-4" /> Challenge starten
        </Button>
      )}
    </Card>
  );
}
