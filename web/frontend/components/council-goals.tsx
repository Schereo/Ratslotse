"use client";

import { useState } from "react";
import { Target, ArrowRight } from "lucide-react";
import { GoalSummary, GoalDetail } from "@/lib/types";
import { Card, Spinner, EmptyState } from "@/components/ui";
import { cn } from "@/lib/utils";
import { useFetch } from "@/lib/use-fetch";
import { DecisionLinkCard } from "@/components/decision-ui";

const STANCE = {
  voran: { label: "bringt voran", bar: "bg-green-500/80", chip: "bg-green-50 text-green-700 dark:bg-green-950/40 dark:text-green-300" },
  bremst: { label: "bremst", bar: "bg-red-500/80", chip: "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300" },
  neutral: { label: "neutral", bar: "bg-muted-foreground/40", chip: "bg-muted text-muted-foreground" },
} as const;

type Stance = keyof typeof STANCE;

function StanceBar({ s }: { s: { voran: number; bremst: number; neutral: number; total: number } }) {
  const t = s.total || 1;
  return (
    <div className="flex h-2 overflow-hidden rounded-full bg-muted">
      <div className={STANCE.voran.bar} style={{ width: `${(s.voran / t) * 100}%` }} />
      <div className={STANCE.bremst.bar} style={{ width: `${(s.bremst / t) * 100}%` }} />
      <div className={STANCE.neutral.bar} style={{ width: `${(s.neutral / t) * 100}%` }} />
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

export function GoalsTab() {
  const { data, loading } = useFetch<{ goals: GoalSummary[] }>("/council/goals");
  const [open, setOpen] = useState<string | null>(null);

  if (loading) return <div className="py-10"><Spinner /></div>;
  const goals = data?.goals ?? [];
  const tracked = goals.some((g) => g.total > 0);
  if (!tracked) return <EmptyState icon={Target} title="Ziel-Tracking wird vorbereitet" hint="Die Beschlüsse werden gerade den Stadtzielen zugeordnet." />;

  return (
    <div className="mt-4 space-y-3">
      <div className="rounded-lg border border-border bg-muted/40 p-3 text-xs leading-relaxed text-muted-foreground">
        Wie viele Ratsbeschlüsse jedes übergeordnete Ziel <span className="font-medium text-foreground">voranbringen</span>,
        ihm <span className="font-medium text-foreground">entgegenwirken</span> oder es neutral berühren. Das misst die
        <span className="font-medium text-foreground"> Aktivität und Richtung</span> des Rats zum Ziel — nicht die reale Kennzahl.
      </div>
      {goals.map((g) => (
        <Card key={g.key} className="p-4">
          <button type="button" onClick={() => setOpen(open === g.key ? null : g.key)} className="w-full text-left">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="font-medium text-foreground">{g.label}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">{g.description}</p>
              </div>
              <ArrowRight className={cn("mt-1 h-4 w-4 shrink-0 text-muted-foreground/50 transition-transform", open === g.key && "rotate-90")} />
            </div>
            <div className="mt-3 flex items-center gap-3">
              <StanceBar s={g} />
              <span className="shrink-0 text-xs text-muted-foreground">
                <span className="text-green-600 dark:text-green-400">{g.voran} ↑</span>{" · "}
                <span className="text-red-600 dark:text-red-400">{g.bremst} ↓</span>{" · "}
                {g.total} ges.
              </span>
            </div>
          </button>
          {open === g.key && <GoalDetailView goalKey={g.key} />}
        </Card>
      ))}
    </div>
  );
}
