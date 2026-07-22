"use client";

import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BarChart3, Bell, CalendarDays, Compass, Map as MapIcon, Sparkles, Tags, Trophy,
  type LucideIcon,
} from "lucide-react";
import { api } from "@/lib/api";
import { Card, toast } from "@/components/ui";
import { ConfettiBurst } from "@/components/confetti";
import { cn } from "@/lib/utils";

/**
 * RL-U12 (Design 10a/11a): Lotsen-Abzeichen — Sammeln fürs ERKUNDEN, nie
 * Konsumzwang: kein Ranking, keine Verlust-Serien, einmal verdient bleibt
 * verdient. Ereignisse melden die jeweiligen Screens über reportBadgeEvent();
 * das Verdienen erkennt der Server und liefert es einmalig als newly_earned —
 * der BadgeCelebrator macht daraus Konfetti + Toast (7a-Muster).
 */

type Badge = {
  id: string;
  title: string;
  hint: string;
  earned: boolean;
  progress: { current: number; target: number } | null;
};
type BadgesResponse = {
  badges: Badge[];
  earned_count: number;
  total: number;
  next: { id: string; title: string; hint: string } | null;
  newly_earned: { id: string; title: string }[];
};

const ICONS: Record<string, LucideIcon> = {
  "erste-frage": Sparkles,
  "themen-lotse": Tags,
  "quiz-serie": Trophy,
  kartograf: MapIcon,
  analyst: BarChart3,
  sitzungsgast: CalendarDays,
  fruehwarner: Bell,
  kompass: Compass,
};

const DIRTY_EVENT = "ratslotse:badges-dirty";

/** Ereignis melden (fire-and-forget) — Fehler stören den eigentlichen Flow nie. */
export function reportBadgeEvent(type: "frage" | "sitzung" | "tour" | "map_place", key?: string) {
  api
    .post("/badges/event", { type, key })
    .then(() => window.dispatchEvent(new Event(DIRTY_EVENT)))
    .catch(() => {});
}

function useBadges() {
  return useQuery({
    queryKey: ["badges"],
    queryFn: () => api.get<BadgesResponse>("/badges"),
    staleTime: 60_000,
  });
}

/** Global im App-Layout: feiert neu verdiente Abzeichen — überall. */
export function BadgeCelebrator() {
  const qc = useQueryClient();
  const { data } = useBadges();
  const [celebrate, setCelebrate] = useState(false);

  useEffect(() => {
    const onDirty = () => qc.invalidateQueries({ queryKey: ["badges"] });
    window.addEventListener(DIRTY_EVENT, onDirty);
    return () => window.removeEventListener(DIRTY_EVENT, onDirty);
  }, [qc]);

  useEffect(() => {
    if (!data?.newly_earned?.length) return;
    for (const b of data.newly_earned) {
      toast.success(`Abzeichen verdient: ${b.title}!`);
    }
    setCelebrate(true);
  }, [data]);

  if (!celebrate) return null;
  return (
    <div className="pointer-events-none fixed inset-x-0 top-24 z-[90] flex justify-center">
      <ConfettiBurst onDone={() => setCelebrate(false)} />
    </div>
  );
}

/** Konto-Karte „Deine Lotsen-Abzeichen" (11a ④). */
export function BadgesCard() {
  const { data } = useBadges();
  if (!data) return null;
  return (
    <Card className="p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-semibold text-foreground">Deine Lotsen-Abzeichen</h2>
        <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-bold tabular-nums text-primary">
          {data.earned_count}/{data.total}
        </span>
      </div>
      <div className="mt-4 grid grid-cols-4 gap-2.5">
        {data.badges.map((b) => {
          const Icon = ICONS[b.id] ?? Sparkles;
          return (
            <div
              key={b.id}
              title={b.earned ? b.title : `${b.title} — ${b.hint}`}
              className={cn(
                "flex flex-col items-center gap-1.5 rounded-xl border p-2 text-center",
                b.earned ? "border-primary/25 bg-primary/[0.06]" : "border-border opacity-45",
              )}
            >
              <span
                className={cn(
                  "flex h-9 w-9 items-center justify-center rounded-full",
                  b.earned ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground",
                )}
              >
                <Icon className="h-4.5 w-4.5" />
              </span>
              <span className="text-[10px] font-medium leading-tight text-foreground">
                {b.title}
                {b.progress && !b.earned && (
                  <span className="block tabular-nums text-muted-foreground">
                    {b.progress.current}/{b.progress.target}
                  </span>
                )}
              </span>
            </div>
          );
        })}
      </div>
      {data.next && (
        <p className="mt-3 text-xs text-muted-foreground">
          <span className="font-semibold text-foreground">Als Nächstes: {data.next.title}</span>
          {" "}— {data.next.hint}
        </p>
      )}
    </Card>
  );
}
