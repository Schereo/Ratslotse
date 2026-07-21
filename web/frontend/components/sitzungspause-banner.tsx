"use client";

import { useQuery } from "@tanstack/react-query";
import { CalendarOff } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type Pause = {
  active: boolean;
  label: string | null;
  until: string | null;              // letzter Pausentag (ISO)
  next_session_date: string | null;  // nächste veröffentlichte Sitzung (ISO)
  note: string;
};

const fmt = (iso: string) =>
  new Date(iso + "T12:00:00").toLocaleDateString("de-DE", { day: "numeric", month: "long" });

/** Hinweis-Banner auf der Übersicht: Der Rat pausiert in den Schulferien
 *  (offizielle Praxis der Stadt) — damit sich niemand wundert, warum keine
 *  neuen Sitzungen erscheinen. Erscheint nur, wenn wirklich Pause ist. */
export function SitzungspauseBanner({ className }: { className?: string }) {
  const { data } = useQuery({
    queryKey: ["sitzungspause"],
    queryFn: () => api.get<Pause>("/council/sitzungspause"),
    staleTime: 60 * 60 * 1000, // ändert sich höchstens täglich
  });

  if (!data?.active) return null;

  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4",
        className,
      )}
      role="status"
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400">
        <CalendarOff className="h-5 w-5" />
      </span>
      <div className="min-w-0">
        <p className="font-semibold text-foreground">
          {data.label}
          {data.until && (
            <span className="font-normal text-muted-foreground"> · bis {fmt(data.until)}</span>
          )}
        </p>
        <p className="mt-0.5 text-sm leading-relaxed text-muted-foreground">{data.note}</p>
      </div>
    </div>
  );
}
