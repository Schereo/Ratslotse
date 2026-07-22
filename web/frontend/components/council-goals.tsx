"use client";

import { useState } from "react";
import { Bus, ChevronDown, Cpu, GraduationCap, Home, Leaf, Store, Target, type LucideIcon } from "lucide-react";
import { GoalSummary, GoalDetail } from "@/lib/types";
import { Card, Spinner, EmptyState } from "@/components/ui";
import { cn } from "@/lib/utils";
import { useFetch } from "@/lib/use-fetch";
import { DecisionLinkCard } from "@/components/decision-ui";
import { AnalysisIntro } from "@/components/analysis-intro";

const STANCE = {
  voran: { label: "bringt voran", bar: "bg-green-500/80", chip: "bg-green-50 text-green-700 dark:bg-green-950/40 dark:text-green-300" },
  bremst: { label: "bremst", bar: "bg-red-500/80", chip: "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300" },
  neutral: { label: "neutral", bar: "bg-muted-foreground/40", chip: "bg-muted text-muted-foreground" },
} as const;

type Stance = keyof typeof STANCE;

// Ein Icon je Stadtziel (Design 18a) — visueller Anker in der Liste.
const GOAL_ICON: Record<string, LucideIcon> = {
  klima_2035: Leaf,
  verkehrswende: Bus,
  wohnungsbau: Home,
  bildung_betreuung: GraduationCap,
  innenstadt: Store,
  digitalisierung: Cpu,
};

// Netto-Verdikt eines Ziels + zugehörige Farbtöne (Chip + Icon-Kachel).
const TONE = {
  voran: { chip: "bg-green-500/15 text-green-700 dark:bg-green-500/20 dark:text-green-300", tile: "bg-green-500/10 text-green-600 dark:text-green-400" },
  bremst: { chip: "bg-red-500/15 text-red-700 dark:bg-red-500/20 dark:text-red-300", tile: "bg-red-500/10 text-red-600 dark:text-red-400" },
  umkaempft: { chip: "bg-amber-500/15 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300", tile: "bg-amber-500/10 text-amber-600 dark:text-amber-400" },
  neutral: { chip: "bg-muted text-muted-foreground", tile: "bg-muted text-muted-foreground" },
} as const;
type Tone = keyof typeof TONE;

/** Richtung eines Ziels aus voran/bremst ableiten: „umkämpft“, wenn beide
 *  Seiten stark sind, sonst überwiegend/leicht voran bzw. gebremst (Design 18a). */
function verdict(g: GoalSummary): { tone: Tone; label: string } {
  const d = g.voran + g.bremst;
  if (d === 0) return { tone: "neutral", label: "kaum Bewegung" };
  if (Math.min(g.voran, g.bremst) / d >= 0.35) return { tone: "umkaempft", label: "umkämpft" };
  const strong = Math.abs(g.voran - g.bremst) / d >= 0.5;
  return g.voran >= g.bremst
    ? { tone: "voran", label: strong ? "überwiegend vorangebracht" : "leicht vorangebracht" }
    : { tone: "bremst", label: strong ? "überwiegend gebremst" : "leicht gebremst" };
}

/** Diverging-Balken (Design 18a): bremst wächst rot nach links, voran grün
 *  nach rechts, dazwischen der neutrale Mittelstrich. Breite = Anteil an total,
 *  das Unbesetzte in der Mitte ist der neutrale Rest. */
function DivergingBar({ g }: { g: GoalSummary }) {
  const t = g.total || 1;
  return (
    <div className="grid h-3.5 items-center" style={{ gridTemplateColumns: "1fr 2px 1fr" }}>
      <span className="flex justify-end">
        <span className="block h-3.5 rounded-l-full bg-red-500/80" style={{ width: `${(g.bremst / t) * 100}%` }} />
      </span>
      <span className="h-3.5 bg-muted-foreground/25" />
      <span className="flex justify-start">
        <span className="block h-3.5 rounded-r-full bg-green-500/80" style={{ width: `${(g.voran / t) * 100}%` }} />
      </span>
    </div>
  );
}

function GoalDetailView({ goalKey }: { goalKey: string }) {
  const { data, loading } = useFetch<GoalDetail>(`/council/goal/${goalKey}`);
  const [filter, setFilter] = useState<Stance | "">("");

  if (loading) return <div className="py-6"><Spinner /></div>;
  if (!data) return null;
  const shown = data.decisions.filter((d) => !filter || d.stance === filter);

  return (
    <div className="mt-3">
      <div className="mb-3 flex flex-wrap gap-1">
        {([["", "Alle"], ["voran", "Bringt voran"], ["bremst", "Bremst"], ["neutral", "Neutral"]] as [Stance | "", string][]).map(([v, l]) => (
          <button key={v} type="button" onClick={() => setFilter(v)}
            className={cn("rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
              filter === v ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:text-foreground")}>
            {l}
          </button>
        ))}
      </div>
      <div className="space-y-2">
        {shown.map((d) => {
          const st = STANCE[(d.stance as Stance)] ?? STANCE.neutral;
          return (
            <DecisionLinkCard key={d.id} id={d.id} title={d.title} committee={d.committee}
              session_date={d.session_date} sub={d.rationale}
              leading={<span className={cn("mt-0.5 shrink-0 whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium", st.chip)}>{st.label}</span>} />
          );
        })}
        {shown.length === 0 && <p className="py-4 text-center text-sm text-muted-foreground">Keine Beschlüsse in dieser Kategorie.</p>}
      </div>
    </div>
  );
}

export function GoalsView() {
  const { data, loading } = useFetch<{ goals: GoalSummary[] }>("/council/goals");
  const [open, setOpen] = useState<string | null>(null);

  if (loading) return <div className="py-10"><Spinner /></div>;
  const goals = data?.goals ?? [];
  const tracked = goals.some((g) => g.total > 0);
  if (!tracked) return <EmptyState mascot="sleep" title="Ziel-Tracking wird vorbereitet" hint="Die Beschlüsse werden gerade den Stadtzielen zugeordnet." />;

  return (
    <div className="space-y-3">
      <AnalysisIntro summary={<>Wie stark der Rat jedes übergeordnete Stadtziel <strong className="font-semibold text-foreground">voranbringt</strong>.</>}>
        Wie viele Ratsbeschlüsse jedes übergeordnete Ziel{" "}
        <strong className="font-semibold text-foreground">voranbringen</strong>, ihm{" "}
        <strong className="font-semibold text-foreground">entgegenwirken</strong> oder es neutral berühren. Das misst
        die <strong className="font-semibold text-foreground">Aktivität und Richtung</strong> des Rats zum Ziel — nicht
        die reale Kennzahl.
      </AnalysisIntro>
      {goals.map((g) => {
        const v = verdict(g);
        const Icon = GOAL_ICON[g.key] ?? Target;
        const isOpen = open === g.key;
        return (
          <Card key={g.key} className="p-4">
            <button type="button" onClick={() => setOpen(isOpen ? null : g.key)} className="w-full text-left">
              <div className="flex items-start gap-3">
                <span className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-xl", TONE[v.tone].tile)}>
                  <Icon className="h-[18px] w-[18px]" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between sm:gap-2.5">
                    <p className="min-w-0 break-words font-medium text-foreground">{g.label}</p>
                    <span className={cn("w-fit shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-semibold", TONE[v.tone].chip)}>{v.label}</span>
                  </div>
                  <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{g.description}</p>
                </div>
                <ChevronDown className={cn("mt-0.5 h-4 w-4 shrink-0 text-muted-foreground/50 transition-transform", isOpen && "rotate-180")} />
              </div>
              <div className="mt-3">
                <DivergingBar g={g} />
                <div className="mt-1.5 flex items-center justify-between text-[11.5px]">
                  <span className="font-medium text-red-600 dark:text-red-400">{g.bremst} bremsen</span>
                  <span className="text-muted-foreground">{g.neutral} neutral · {g.total} gesamt</span>
                  <span className="font-medium text-green-600 dark:text-green-400">{g.voran} bringen voran</span>
                </div>
              </div>
            </button>
            {isOpen && <GoalDetailView goalKey={g.key} />}
          </Card>
        );
      })}
    </div>
  );
}
