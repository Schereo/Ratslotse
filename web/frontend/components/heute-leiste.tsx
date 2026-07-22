"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { isLiveTodayTime, isStadtrat, minutesSinceTime, O1_STREAM_URL } from "@/lib/live";
import { cn } from "@/lib/utils";

type Heute =
  | { state: "heute"; committee: string; session_time: string; tops: string[]; rest: number; n_sessions_today: number }
  | { state: "naechste"; committee: string; session_date: string; session_time: string }
  | { state: "pause"; label: string | null; until: string | null };

const fmt = (iso: string) =>
  new Date(iso + "T12:00:00").toLocaleDateString("de-DE", { weekday: "short", day: "numeric", month: "short" });

/** „Heute im Rat"-Leiste auf der Landing (RL-301, Design 2a): dezente Zeile
 *  unter dem Header mit Mono-Kicker + Punkt. Vier Zustände (LIVE · heute ·
 *  nächste Sitzung · Pause) — die Leiste verschwindet nie; feste Höhe
 *  verhindert Layout-Shift, bis die Daten da sind. LIVE (RL-U10) wird rein
 *  clientseitig aus der Startzeit abgeleitet (bis Start + 4 h) und tickt
 *  minütlich; beim Stadtrat verlinkt sie auf den O1-Stream. */
export function HeuteLeiste() {
  const [data, setData] = useState<Heute | null>(null);
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    fetch("/api/council/heute")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d && setData(d))
      .catch(() => {});
    const id = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(id);
  }, []);

  const live = data?.state === "heute" && isLiveTodayTime(data.session_time, now);
  const heute = data?.state === "heute" && !live;
  const nTops = data?.state === "heute" ? data.tops.length + data.rest : 0;
  const stadtrat = data?.state === "heute" && isStadtrat(data.committee);

  return (
    <div
      className={cn(
        "border-b border-border",
        live ? "bg-red-500/[0.06]" : heute ? "bg-[hsl(19_92%_55%/0.06)]" : "bg-muted/30",
      )}
      role="status"
    >
      <div className="mx-auto flex min-h-11 max-w-6xl items-center gap-3 px-5 py-2 text-sm">
        {live ? (
          <span className="relative flex h-2 w-2 shrink-0" aria-hidden>
            <span className="absolute inset-0 rounded-full bg-red-500 motion-safe:animate-ping" />
            <span className="relative h-2 w-2 rounded-full bg-red-500" />
          </span>
        ) : (
          <span
            className={cn("h-2 w-2 shrink-0 rounded-full", heute ? "bg-signal" : "bg-muted-foreground/50")}
            aria-hidden
          />
        )}
        <span
          className={cn(
            "shrink-0 font-mono text-[11px] font-medium uppercase tracking-[0.14em]",
            live ? "text-red-700 dark:text-red-400" : "text-muted-foreground",
          )}
        >
          {live ? "Live" : data?.state === "heute" ? "Heute im Rat" : data?.state === "naechste" ? "Nächste Sitzung" : data?.state === "pause" ? "Sitzungspause" : " "}
        </span>
        <span className="min-w-0 flex-1 truncate text-foreground">
          {live && data?.state === "heute" && (
            <>
              {stadtrat ? "Der Stadtrat tagt" : `${data.committee} tagt`} — seit{" "}
              {minutesSinceTime(data.session_time, now)} Minuten
              {nTops > 0 && <span className="text-muted-foreground">, {nTops} TOPs</span>}
            </>
          )}
          {heute && data?.state === "heute" && (
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
        {/* RL-F05: jeder Zustand verlinkt — live beim Stadtrat zum O1-Stream,
            heute zur Tagesordnung, sonst dezent in den Sitzungskalender. */}
        {live && stadtrat ? (
          <a
            href={O1_STREAM_URL}
            target="_blank"
            rel="noreferrer"
            className="hidden shrink-0 items-center gap-1 font-medium text-red-700 hover:underline dark:text-red-400 sm:inline-flex"
          >
            Zum O1-Stream <ArrowRight className="h-3.5 w-3.5" />
          </a>
        ) : data ? (
          <Link
            href="/council?tab=sessions"
            className="hidden shrink-0 items-center gap-1 font-medium text-primary hover:underline sm:inline-flex"
          >
            {data.state === "heute" ? "Zur Tagesordnung" : "Kalender"} <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        ) : null}
      </div>
    </div>
  );
}
