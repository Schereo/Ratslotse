"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";

type Heute =
  | { state: "heute"; committee: string; session_time: string; tops: string[]; rest: number; n_sessions_today: number }
  | { state: "naechste"; committee: string; session_date: string; session_time: string }
  | { state: "pause"; label: string | null; until: string | null };

const fmt = (iso: string) =>
  new Date(iso + "T12:00:00").toLocaleDateString("de-DE", { weekday: "short", day: "numeric", month: "short" });

/** „Heute im Rat"-Leiste auf der Landing (RL-301, Design 2a): dezente Zeile
 *  unter dem Header mit Mono-Kicker + Punkt. Drei Zustände (heute · nächste
 *  Sitzung · Pause) — die Leiste verschwindet nie; feste Höhe verhindert
 *  Layout-Shift, bis die Daten da sind. */
export function HeuteLeiste() {
  const [data, setData] = useState<Heute | null>(null);
  useEffect(() => {
    fetch("/api/council/heute")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d && setData(d))
      .catch(() => {});
  }, []);

  const heute = data?.state === "heute";
  return (
    <div
      className={cn(
        "border-b border-border",
        heute ? "bg-[hsl(19_92%_55%/0.06)]" : "bg-muted/30",
      )}
      role="status"
    >
      <div className="mx-auto flex min-h-11 max-w-6xl items-center gap-3 px-5 py-2 text-sm">
        <span
          className={cn("h-2 w-2 shrink-0 rounded-full", heute ? "bg-signal" : "bg-muted-foreground/50")}
          aria-hidden
        />
        <span className="shrink-0 font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
          {data?.state === "heute" ? "Heute im Rat" : data?.state === "naechste" ? "Nächste Sitzung" : data?.state === "pause" ? "Sitzungspause" : " "}
        </span>
        <span className="min-w-0 flex-1 truncate text-foreground">
          {data?.state === "heute" && (
            <>
              {data.committee}, {data.session_time} Uhr
              {data.tops.length > 0 && <span className="text-muted-foreground"> — {data.tops.join(" · ")}</span>}
              {data.rest > 0 && <span className="text-muted-foreground"> + {data.rest} weitere</span>}
            </>
          )}
          {data?.state === "naechste" && (
            <>
              {fmt(data.session_date)} · {data.committee}
              {data.session_time && `, ${data.session_time} Uhr`}
            </>
          )}
          {data?.state === "pause" && (
            <>
              {data.label ?? "Gerade keine Sitzungen"}
              {data.until && <span className="text-muted-foreground"> — bis {fmt(data.until)}</span>}
            </>
          )}
        </span>
        {/* RL-F05: jeder Zustand verlinkt — heute prominent zur Tagesordnung,
            sonst dezent in den Sitzungskalender (Login-Gate übernimmt (app)/). */}
        {data && (
          <Link
            href="/council?tab=sessions"
            className="hidden shrink-0 items-center gap-1 font-medium text-primary hover:underline sm:inline-flex"
          >
            {data.state === "heute" ? "Zur Tagesordnung" : "Kalender"} <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        )}
      </div>
    </div>
  );
}
